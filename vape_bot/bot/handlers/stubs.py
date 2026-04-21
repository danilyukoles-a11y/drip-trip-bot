"""Заглушки для post-MVP кнопок."""

from aiogram import F, Router
from aiogram.types import Message

router = Router()

STUB_BUTTONS = {
    "🔍 Пошук",
    "🎯 Рекомендації",
    "🔥 Топ продажів",
    "⭐ Улюблене",
    "🗂 Мій профіль",
    "🔄 Історія переглядів",
    "ℹ️ FAQ",
    "✉️ Зворотній зв'язок",
}


@router.message(F.text.in_(STUB_BUTTONS))
async def stub_handler(message: Message):
    await message.answer("🚧 Ця функція буде доступна найближчим часом.")
