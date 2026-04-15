"""Poster incomingOrders integration with retries — native async via httpx.

Important implementation notes (verified against live Poster API 2026-04-14):
- Token must be in URL query string, NOT in body.
- Body must be JSON (application/json), NOT form-encoded.
- Phone must be in valid Ukrainian format (e.g. +380XXXXXXXXX).
- Response contains both incoming_order_id and transaction_id;
  Дмитро references orders by transaction_id in Poster UI.
- There is no API to delete an incoming order — cleanup is Supabase-only.
"""

import asyncio
import logging
from typing import Any

import httpx

from vape_bot.config.settings import POSTER_API_URL, POSTER_TOKEN, SPOT_ID

logger = logging.getLogger(__name__)

PAYMENT_MAP = {
    "Передплата (на карту)": 2,  # non-cash
    "Накладений платіж": 1,       # cash-equivalent
}

RETRY_DELAYS = [1, 2, 4]
HTTP_TIMEOUT = 15.0


def _split_full_name(full_name: str) -> tuple[str, str]:
    """ПІБ → (last_name, first_name+patronymic)."""
    parts = full_name.strip().split(" ", 1)
    last = parts[0]
    first = parts[1] if len(parts) > 1 else ""
    return last, first


def _parse_cart_product_id(cart_product_id: str) -> tuple[int, int | None]:
    """`{parent}_{mod}` → (parent, mod) or `123` → (123, None)."""
    s = str(cart_product_id)
    if "_" in s:
        parent, mod = s.split("_", 1)
        return int(parent), int(mod)
    return int(s), None


def _build_products_payload(items: list[dict]) -> list[dict]:
    """Supabase cart items → Poster products array."""
    out: list[dict[str, Any]] = []
    for item in items:
        product_id, mod_id = _parse_cart_product_id(item["product_id"])
        entry: dict[str, Any] = {
            "product_id": product_id,
            "count": int(item["quantity"]),
        }
        if mod_id is not None:
            entry["modificator_id"] = mod_id
        out.append(entry)
    return out


def _build_comment(order: dict, telegram_username: str | None) -> str:
    username = f"@{telegram_username}" if telegram_username else "невідомо"
    return (
        f"Заявка з Telegram-бота №{order['order_number']}\n"
        f"Спосіб оплати: {order['payment_method']}\n"
        f"Telegram: {username}"
    )


def _build_payload(
    order: dict,
    cart_items: list[dict],
    telegram_username: str | None,
) -> dict:
    last_name, first_name = _split_full_name(order["full_name"])
    return {
        "spot_id": SPOT_ID,
        "first_name": first_name,
        "last_name": last_name,
        "phone": order["phone"],
        "address": order["address"],
        "city": order["city"],
        "comment": _build_comment(order, telegram_username),
        "payment_type": PAYMENT_MAP.get(order["payment_method"], 1),
        "products": _build_products_payload(cart_items),
    }


async def _create_once(
    client: httpx.AsyncClient, payload: dict
) -> tuple[int, int] | None:
    """Single POST attempt. Returns (incoming_order_id, transaction_id) or None."""
    try:
        resp = await client.post(
            f"{POSTER_API_URL}/incomingOrders.createIncomingOrder",
            params={"token": POSTER_TOKEN},
            json=payload,
        )
        data = resp.json()
        if "error" in data:
            logger.warning("Poster create error: %s", data["error"])
            return None
        response = data["response"]
        return (
            int(response["incoming_order_id"]),
            int(response.get("transaction_id") or 0),
        )
    except Exception:
        logger.exception("Poster create request failed")
        return None


async def create_poster_order(
    order: dict,
    cart_items: list[dict],
    telegram_username: str | None,
) -> tuple[int, int] | None:
    """Create incoming order in Poster with 3 retries (1s/2s/4s).

    Returns (incoming_order_id, transaction_id) on success, None on failure.
    """
    payload = _build_payload(order, cart_items, telegram_username)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for attempt, delay in enumerate([0, *RETRY_DELAYS]):
            if delay:
                await asyncio.sleep(delay)
            result = await _create_once(client, payload)
            if result is not None:
                if attempt > 0:
                    logger.info("Poster create succeeded on retry %d", attempt)
                return result
            logger.warning("Poster create attempt %d failed", attempt + 1)

    return None
