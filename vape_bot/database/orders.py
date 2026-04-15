"""CRUD операції для таблиці orders."""

from datetime import datetime

from vape_bot.database.supabase_client import get_client


def _generate_order_number() -> str:
    """Генерує номер замовлення у форматі order_YYYYMMDD_HHMMSS."""
    return f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def create_order(
    user_id: int,
    full_name: str,
    phone: str,
    city: str,
    address: str,
    payment_method: str,
    items: list[dict],
    total: float,
) -> dict:
    """Створити нове замовлення."""
    db = get_client()
    result = db.table("orders").insert({
        "user_id": user_id,
        "order_number": _generate_order_number(),
        "full_name": full_name,
        "phone": phone,
        "city": city,
        "address": address,
        "payment_method": payment_method,
        "items": items,
        "total": total,
        "status": "new",
    }).execute()
    return result.data[0]


def get_user_orders(user_id: int) -> list[dict]:
    """Отримати всі замовлення користувача (новіші першими)."""
    db = get_client()
    result = (
        db.table("orders")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def update_poster_ids(
    order_id: int,
    poster_order_id: int,
    poster_transaction_id: int,
) -> None:
    """Зберегти Poster incoming_order_id та transaction_id після успішної синхронізації."""
    db = get_client()
    db.table("orders").update({
        "poster_order_id": poster_order_id,
        "poster_transaction_id": poster_transaction_id,
    }).eq("id", order_id).execute()


def get_orders_by_phone(phone: str) -> list[dict]:
    """Знайти всі замовлення за номером телефону (для адмін cleanup)."""
    db = get_client()
    result = db.table("orders").select("*").eq("phone", phone).execute()
    return result.data or []


def delete_order_by_id(order_id: int) -> None:
    """Видалити одне замовлення з Supabase за id."""
    db = get_client()
    db.table("orders").delete().eq("id", order_id).execute()
