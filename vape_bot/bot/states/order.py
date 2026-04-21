"""FSM стани для оформлення замовлення."""

from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_address = State()
    waiting_payment = State()
