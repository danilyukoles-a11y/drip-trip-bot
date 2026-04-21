"""Хендлер кошика: перегляд, очищення."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from vape_bot.bot.keyboards.inline import cart_kb
from vape_bot.database.cart import clear_cart, get_cart, get_cart_total
from vape_bot.database.users import get_or_create_user

router = Router()


def _format_cart(items: list[dict], total: float) -> str:
    """Форматування тексту кошика."""
    lines = ["🛒 Ваш кошик:"]
    for item in items:
        price = float(item["price"])
        qty = item["quantity"]
        subtotal = price * qty
        lines.append(f"• {item['product_name']}: {qty} шт. x {price:.0f} = {subtotal:.2f} грн")
    lines.append(f"\nЗагальна сума: {total:.2f} грн")
    return "\n".join(lines)


@router.message(F.text == "🛒 Кошик")
async def show_cart(message: Message):
    """Показати кошик."""
    get_or_create_user(message.from_user.id, message.from_user.username)
    items = get_cart(message.from_user.id)

    if not items:
        await message.answer("Ваш кошик порожній.")
        return

    total = get_cart_total(message.from_user.id)
    await message.answer(_format_cart(items, total), reply_markup=cart_kb())


@router.callback_query(F.data == "go_cart")
async def go_to_cart(callback: CallbackQuery):
    """Перейти до кошика (з inline кнопки)."""
    items = get_cart(callback.from_user.id)

    if not items:
        await callback.message.edit_text("Ваш кошик порожній.")
        await callback.answer()
        return

    total = get_cart_total(callback.from_user.id)
    await callback.message.edit_text(_format_cart(items, total), reply_markup=cart_kb())
    await callback.answer()


@router.message(F.text == "🧹 Очистити кошик")
async def clear_cart_message(message: Message):
    """Очистити кошик (Reply keyboard)."""
    clear_cart(message.from_user.id)
    await message.answer("Ваш кошик порожній.")


@router.callback_query(F.data == "clear_cart")
async def clear_cart_callback(callback: CallbackQuery):
    """Очистити кошик (Inline кнопка)."""
    clear_cart(callback.from_user.id)
    await callback.message.edit_text("Ваш кошик порожній.")
    await callback.answer("Кошик очищено!")
