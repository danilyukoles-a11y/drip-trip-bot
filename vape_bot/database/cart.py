"""CRUD операції для таблиці cart_items."""

from vape_bot.database.supabase_client import get_client


def get_cart(user_id: int) -> list[dict]:
    """Отримати всі товари в кошику користувача."""
    db = get_client()
    result = db.table("cart_items").select("*").eq("user_id", user_id).execute()
    return result.data


def add_to_cart(user_id: int, product_id: str, product_name: str, price: float) -> dict:
    """Додати товар в кошик. Якщо вже є — збільшити quantity."""
    db = get_client()

    # Перевірити чи товар вже в кошику
    existing = (
        db.table("cart_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("product_id", product_id)
        .execute()
    )

    if existing.data:
        item = existing.data[0]
        result = (
            db.table("cart_items")
            .update({"quantity": item["quantity"] + 1})
            .eq("id", item["id"])
            .execute()
        )
        return result.data[0]

    result = db.table("cart_items").insert({
        "user_id": user_id,
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "quantity": 1,
    }).execute()
    return result.data[0]


def get_cart_total(user_id: int) -> float:
    """Порахувати загальну суму кошика."""
    items = get_cart(user_id)
    return sum(float(item["price"]) * item["quantity"] for item in items)


def clear_cart(user_id: int) -> None:
    """Очистити кошик користувача."""
    db = get_client()
    db.table("cart_items").delete().eq("user_id", user_id).execute()
