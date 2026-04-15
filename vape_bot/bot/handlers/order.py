"""Хендлер оформлення замовлення з FSM."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from vape_bot.bot.keyboards.inline import quick_order_kb
from vape_bot.bot.keyboards.main_menu import main_menu_kb, payment_kb
from vape_bot.bot.states.order import OrderStates
from vape_bot.config.settings import MANAGER_USERNAME
from vape_bot.database.cart import clear_cart, get_cart, get_cart_total
from vape_bot.database.orders import create_order, update_poster_ids
from vape_bot.database.users import get_or_create_user, get_user, update_user
from vape_bot.services.notification import notify_new_order, notify_poster_sync_failed
from vape_bot.services.phone import normalize_phone
from vape_bot.services.poster_orders import create_poster_order

router = Router()


async def _start_checkout(user_id: int, username: str | None, message: Message, state: FSMContext):
    """Почати оформлення замовлення."""
    items = get_cart(user_id)
    if not items:
        await message.answer("Ваш кошик порожній. Додайте товари перед оформленням.")
        return

    get_or_create_user(user_id, username)
    user = get_user(user_id)

    # Перевірити чи є збережені дані (повторне замовлення)
    if user and user.get("full_name") and user.get("phone"):
        normalized_phone = normalize_phone(user["phone"]) or user["phone"]
        await state.set_state(OrderStates.waiting_payment)
        await state.update_data(
            full_name=user["full_name"],
            phone=normalized_phone,
            city=user["city"],
            address=user["address"],
        )
        text = (
            "🚀 Швидке замовлення\n\n"
            "Знайдено ваші дані з попереднього замовлення:\n"
            f"👤 Отримувач: {user['full_name']}\n"
            f"📞 Телефон: {normalized_phone}\n"
            f"🏙 Місто: {user['city']}\n"
            f"📍 Адреса: {user['address']}\n\n"
            "Використати ці дані чи ввести нові?"
        )
        await message.answer(text, reply_markup=quick_order_kb())
        return

    # Перше замовлення — збір даних
    await state.set_state(OrderStates.waiting_full_name)
    await message.answer("📝 Введіть ПІБ отримувача (Прізвище Ім'я По батькові):")


@router.message(F.text == "✅ Оформити замовлення")
async def checkout_reply(message: Message, state: FSMContext):
    """Оформити замовлення (Reply keyboard)."""
    await _start_checkout(message.from_user.id, message.from_user.username, message, state)


@router.callback_query(F.data == "checkout")
async def checkout_inline(callback: CallbackQuery, state: FSMContext):
    """Оформити замовлення (Inline кнопка з кошика)."""
    await callback.answer()
    await _start_checkout(callback.from_user.id, callback.from_user.username, callback.message, state)


@router.callback_query(F.data == "quick_order")
async def quick_order(callback: CallbackQuery, state: FSMContext):
    """Використати збережені дані."""
    await callback.answer()
    await callback.message.edit_text("Відмінно! Оберіть спосіб оплати:")
    await callback.message.answer("Оберіть спосіб оплати:", reply_markup=payment_kb)


@router.callback_query(F.data == "new_order")
async def new_order(callback: CallbackQuery, state: FSMContext):
    """Ввести нові дані."""
    await callback.answer()
    await state.set_state(OrderStates.waiting_full_name)
    await callback.message.edit_text("📝 Введіть ПІБ отримувача (Прізвище Ім'я По батькові):")


# === FSM: збір даних ===

@router.message(OrderStates.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(OrderStates.waiting_phone)
    await message.answer("Введіть ваш номер телефону:")


@router.message(OrderStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    normalized = normalize_phone(message.text)
    if not normalized:
        await message.answer(
            "⚠️ Не вдалось розпізнати номер. Введіть український мобільний "
            "у форматі +380XXXXXXXXX або 0XXXXXXXXX:"
        )
        return
    await state.update_data(phone=normalized)
    await state.set_state(OrderStates.waiting_city)
    await message.answer("Введіть ваше місто:")


@router.message(OrderStates.waiting_city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OrderStates.waiting_address)
    await message.answer("Введіть адресу доставки (наприклад, Нова Пошта №12):")


@router.message(OrderStates.waiting_address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(OrderStates.waiting_payment)
    await message.answer("Будь ласка, оберіть спосіб оплати:", reply_markup=payment_kb)


@router.message(OrderStates.waiting_payment, F.text == "❌ Скасувати замовлення")
async def cancel_order(message: Message, state: FSMContext):
    """Скасування замовлення."""
    await state.clear()
    clear_cart(message.from_user.id)
    await message.answer(
        "💔 Оформлення замовлення скасовано. Ваш кошик очищено.",
        reply_markup=main_menu_kb,
    )


@router.message(OrderStates.waiting_payment, F.text.in_({"Передплата (на карту)", "Накладений платіж"}))
async def process_payment(message: Message, state: FSMContext):
    """Фінальний крок — створення замовлення."""
    data = await state.get_data()
    await state.clear()

    user_id = message.from_user.id
    items = get_cart(user_id)

    if not items:
        await message.answer("Ваш кошик порожній.", reply_markup=main_menu_kb)
        return

    total = get_cart_total(user_id)

    # Зберегти items як snapshot
    items_snapshot = [
        {
            "name": item["product_name"],
            "qty": item["quantity"],
            "price": float(item["price"]),
        }
        for item in items
    ]

    # Створити замовлення
    order = create_order(
        user_id=user_id,
        full_name=data["full_name"],
        phone=data["phone"],
        city=data["city"],
        address=data["address"],
        payment_method=message.text,
        items=items_snapshot,
        total=total,
    )

    # Оновити дані користувача
    update_user(
        user_id,
        full_name=data["full_name"],
        phone=data["phone"],
        city=data["city"],
        address=data["address"],
    )

    # Очистити кошик
    clear_cart(user_id)

    # Відповідь клієнту
    await message.answer(
        f"✅ Дякуємо! Ваша заявка №{order['order_number']} прийнята.\n"
        f"Для підтвердження, будь ласка, зв'яжіться з @{MANAGER_USERNAME}. "
        f"Без підтвердження з менеджером не відправляється!",
        reply_markup=main_menu_kb,
    )

    # Сповіщення менеджеру
    await notify_new_order(message.bot, order, message.from_user.username)

    # Синхронізація в Poster (3 ретраї 1/2/4s)
    poster_result = await create_poster_order(
        order=order,
        cart_items=items,
        telegram_username=message.from_user.username,
    )
    if poster_result:
        incoming_order_id, transaction_id = poster_result
        update_poster_ids(order["id"], incoming_order_id, transaction_id)
    else:
        await notify_poster_sync_failed(message.bot, order["order_number"])
