"""Хендлер /start — перевірка 18+ та головне меню."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from vape_bot.bot.keyboards.main_menu import main_menu_kb
from vape_bot.database.users import get_or_create_user

router = Router()

AGE_TEXT = (
    "⚠️ Цей бот містить інформацію про продукцію для осіб віком від 18 років.\n\n"
    "Вам є 18 років?"
)

age_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Так, мені є 18", callback_data="age_yes"),
        InlineKeyboardButton(text="❌ Ні", callback_data="age_no"),
    ],
])


@router.message(CommandStart())
async def cmd_start(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(AGE_TEXT, reply_markup=age_kb)


@router.callback_query(F.data == "age_yes")
async def age_confirmed(callback: CallbackQuery):
    await callback.message.edit_text("✅ Дякуємо! Доступ підтверджено.")
    await callback.message.answer(
        "Вітаємо! Оберіть опцію для початку:",
        reply_markup=main_menu_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "age_no")
async def age_denied(callback: CallbackQuery):
    await callback.answer(
        "Для використання бота необхідно бути старше 18 років",
        show_alert=True,
    )
