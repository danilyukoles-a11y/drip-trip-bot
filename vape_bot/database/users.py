"""CRUD операції для таблиці users."""

from vape_bot.database.supabase_client import get_client


def get_or_create_user(user_id: int, username: str | None = None) -> dict:
    """Отримати користувача або створити нового."""
    db = get_client()
    result = db.table("users").select("*").eq("id", user_id).execute()

    if result.data:
        return result.data[0]

    new_user = {"id": user_id, "username": username}
    result = db.table("users").insert(new_user).execute()
    return result.data[0]


def get_user(user_id: int) -> dict | None:
    """Отримати користувача за ID."""
    db = get_client()
    result = db.table("users").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else None


def update_user(user_id: int, **fields) -> dict:
    """Оновити дані користувача (ПІБ, телефон, місто, адреса)."""
    db = get_client()
    result = db.table("users").update(fields).eq("id", user_id).execute()
    return result.data[0]
