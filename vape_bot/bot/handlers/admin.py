"""Admin-only commands (cleanup test orders, etc.)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from vape_bot.config.settings import ADMIN_USER_ID, TEST_PHONE
from vape_bot.database.cart import clear_cart
from vape_bot.database.orders import delete_order_by_id, get_orders_by_phone

router = Router()


@router.message(Command("cleanup_test_orders"))
async def cleanup_test_orders(message: Message):
    """Видалити всі тестові замовлення з Supabase (Poster не чіпаємо)."""
    if message.from_user.id != ADMIN_USER_ID:
        return  # silent ignore for non-admins

    if not TEST_PHONE:
        await message.answer("⚠️ TEST_PHONE не налаштовано в .env")
        return

    orders = get_orders_by_phone(TEST_PHONE)
    if not orders:
        await message.answer(f"Тестових замовлень не знайдено (phone={TEST_PHONE})")
        return

    deleted = 0
    poster_refs: list[str] = []
    for o in orders:
        tx_id = o.get("poster_transaction_id")
        if tx_id:
            poster_refs.append(str(tx_id))
        delete_order_by_id(o["id"])
        deleted += 1

    # На випадок якщо є недооформлений кошик — очистити
    clear_cart(message.from_user.id)

    refs_text = (
        f"\nℹ️ Poster чеки залишені (Дмитро закриє вручну): {', '.join(poster_refs)}"
        if poster_refs
        else ""
    )
    await message.answer(
        f"✅ Видалено {deleted} замовлень з Supabase{refs_text}"
    )
