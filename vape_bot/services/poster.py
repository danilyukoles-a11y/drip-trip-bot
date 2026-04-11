"""Робота з Poster API. Кешування товарів з залишками та модифікаціями."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

import requests

from vape_bot.config.settings import (
    CACHE_TTL_MINUTES,
    POSTER_API_URL,
    POSTER_TOKEN,
    STORAGE_ID,
    SUBCATEGORIES,
    SUBCATEGORIES_L3,
)

logger = logging.getLogger(__name__)


class PosterCache:
    """Кеш товарів з Poster API. Оновлюється раз на CACHE_TTL_MINUTES."""

    def __init__(self):
        self._products: dict[str, list[dict]] = {}  # category_id → products
        self._last_update: datetime | None = None
        self._refreshing: bool = False

    def _is_expired(self) -> bool:
        if self._last_update is None:
            return True
        return datetime.now() - self._last_update > timedelta(minutes=CACHE_TTL_MINUTES)

    def _api_get(self, method: str, params: dict | None = None) -> dict:
        p = {"token": POSTER_TOKEN}
        if params:
            p.update(params)
        resp = requests.get(f"{POSTER_API_URL}/{method}", params=p, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _fetch_stock_map(self) -> dict[str, float]:
        """Завантажити залишки зі складу. Повертає {ingredient_id: кількість}."""
        try:
            data = self._api_get(
                "storage.getStorageLeftovers",
                {"storage_id": STORAGE_ID},
            )
            items = data.get("response", [])
            return {
                item["ingredient_id"]: float(item["ingredient_left"])
                for item in items
            }
        except Exception:
            logger.warning("Failed to fetch stock data, all stock will be 0")
            return {}

    def _fetch_modifications(
        self, parent_products: list[dict], stock_map: dict[str, float]
    ) -> None:
        """Завантажити модифікації для батьківських товарів (ціна 0)."""
        for product in parent_products:
            try:
                data = self._api_get(
                    "menu.getProduct",
                    {"product_id": product["id"]},
                )
                details = data.get("response", {})
                mods_raw = details.get("modifications", [])

                if not mods_raw:
                    logger.warning(
                        "Product %s (%s) has price=0 but no modifications, skipping",
                        product["id"],
                        product["name"],
                    )
                    continue

                mods = []
                for m in mods_raw:
                    spots = m.get("spots", [])
                    mod_price = int(spots[0].get("price", "0")) / 100 if spots else 0
                    mod_ingredient_id = m.get("ingredient_id", "")
                    mod_stock = stock_map.get(mod_ingredient_id, 0.0)

                    mods.append({
                        "mod_id": m["modificator_id"],
                        "name": m["modificator_name"],
                        "price": mod_price,
                        "stock": mod_stock,
                    })

                prices = [m["price"] for m in mods if m["price"] > 0]
                any_in_stock = any(m["stock"] > 0 for m in mods)

                product["has_modifications"] = True
                product["modifications"] = mods
                product["price_min"] = min(prices) if prices else 0
                product["price_max"] = max(prices) if prices else 0
                product["stock"] = 1.0 if any_in_stock else 0.0

                cat_id = str(product["category_id"])
                if cat_id not in self._products:
                    self._products[cat_id] = []
                self._products[cat_id].append(product)

            except Exception:
                logger.warning(
                    "Failed to fetch modifications for product %s (%s), skipping",
                    product["id"],
                    product["name"],
                )

            time.sleep(0.1)

    def _fetch_all_products(self) -> None:
        """Завантажити всі товари, залишки та модифікації."""
        # 1. Fetch stock map
        stock_map = self._fetch_stock_map()

        # 2. Fetch all products
        data = self._api_get("menu.getProducts")
        raw_products = data.get("response", [])

        self._products.clear()
        parent_products = []

        for p in raw_products:
            cat_id = str(p["menu_category_id"])
            ingredient_id = p.get("ingredient_id", "")
            spots = p.get("spots", [])
            price = int(spots[0].get("price", "0")) / 100 if spots else 0
            stock = stock_map.get(ingredient_id, 0.0)

            product = {
                "id": p["product_id"],
                "name": p["product_name"],
                "category_id": cat_id,
                "price": price,
                "stock": stock,
                "ingredient_id": ingredient_id,
                "photo": p.get("photo") or p.get("photo_origin") or None,
                "has_modifications": False,
            }

            if price <= 0:
                parent_products.append(product)
                continue

            if cat_id not in self._products:
                self._products[cat_id] = []
            self._products[cat_id].append(product)

        # 3. Fetch modifications for parent products
        self._fetch_modifications(parent_products, stock_map)

        self._last_update = datetime.now()

    def _ensure_cache(self) -> None:
        """Перевірити кеш. Якщо протух — запустити фоновий рефреш (не блокує)."""
        if self._is_expired() and not self._refreshing:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._refresh_in_background())
            except RuntimeError:
                # No event loop — sync context (tests, scripts)
                self._fetch_all_products()

    async def _refresh_in_background(self) -> None:
        """Оновити кеш у фоновому потоці, не блокуючи event loop."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            logger.info("Background cache refresh started...")
            await asyncio.to_thread(self._fetch_all_products)
            logger.info("Background cache refresh done")
        except Exception:
            logger.exception("Background cache refresh failed")
        finally:
            self._refreshing = False

    async def preload(self) -> None:
        """Pre-load кешу при старті бота. Викликати перед polling."""
        logger.info("Pre-loading product cache...")
        await asyncio.to_thread(self._fetch_all_products)
        logger.info(
            "Cache loaded: %d products",
            sum(len(v) for v in self._products.values()),
        )

    def get_products_by_category(self, category_id: int) -> list[dict]:
        """Товари по категорії. Автоматично оновлює кеш."""
        self._ensure_cache()
        return self._products.get(str(category_id), [])

    def get_product_by_id(self, product_id: str) -> dict | None:
        """Знайти товар за ID у кеші."""
        self._ensure_cache()
        for products in self._products.values():
            for p in products:
                if p["id"] == product_id:
                    return p
        return None

    def get_all_category_ids(self, root_category_id: int) -> list[int]:
        """Отримати всі підкатегорії (включно з L3) для кореневої категорії."""
        ids = []
        subs = SUBCATEGORIES.get(root_category_id, {})
        for sub_id in subs:
            ids.append(sub_id)
            # L3 підкатегорії
            l3 = SUBCATEGORIES_L3.get(sub_id, {})
            ids.extend(l3.keys())
        return ids

    def get_product_modifications(self, product_id: str) -> list[dict]:
        """Отримати модифікації товару з кешу."""
        product = self.get_product_by_id(product_id)
        if product and product.get("has_modifications"):
            return product.get("modifications", [])
        return []


# Singleton
poster_cache = PosterCache()
