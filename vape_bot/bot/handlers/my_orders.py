"""Хендлер: Мої замовлення."""

from aiogram import F, Router
from aiogram.types import Message

from vape_bot.database.orders import get_user_orders

router = Router()


@router.message(F.text == "📦 Мої замовлення")
async def show_my_orders(message: Message):
    """Показати історію замовлень."""
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("У вас ще немає замовлень.")
        return

    lines = ["📜 Ваші останні замовлення:\n"]
    for order in orders:
        lines.append(f"📦 Замовлення: {order['order_number']}")
        lines.append(f"📅 Дата: {order['created_at'][:19].replace('T', ' ')}")
        lines.append("🛍️ Товари:")
        for item in order["items"]:
            lines.append(f"🔹 {item['name']} ({item['qty']} шт.) - {item['price']:.0f}")
        lines.append(f"💰 Загальна сума: {float(order['total']):.2f} грн")
        lines.append("-" * 20)

    await message.answer("\n".join(lines))
