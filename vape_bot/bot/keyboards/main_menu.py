"""Reply keyboard головного меню."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📁 Категорії"), KeyboardButton(text="🛒 Кошик")],
        [KeyboardButton(text="✅ Оформити замовлення")],
        [KeyboardButton(text="🧹 Очистити кошик")],
    ],
    resize_keyboard=True,
)

# Кнопки оплати (для FSM замовлення)
payment_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Передплата (на карту)"),
            KeyboardButton(text="Накладений платіж"),
        ],
        [KeyboardButton(text="❌ Скасувати замовлення")],
    ],
    resize_keyboard=True,
)

# Кнопка для запиту контакту (під час оформлення замовлення)
phone_request_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Поділитися своїм номером", request_contact=True)],
    ],
    resize_keyboard=True,
)
