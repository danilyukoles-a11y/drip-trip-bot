"""Inline keyboards: категорії, товари, кошик."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from vape_bot.config.settings import (
    PRODUCTS_PER_PAGE,
    ROOT_CATEGORIES,
    SUBCATEGORIES,
    SUBCATEGORIES_L3,
)
from vape_bot.services.poster import poster_cache


def _sub_has_in_stock(sub_id: int) -> bool:
    """L2 категорія: товари напряму або через L3 підкатегорії."""
    if poster_cache.has_in_stock(sub_id):
        return True
    for l3_id in SUBCATEGORIES_L3.get(sub_id, {}):
        if poster_cache.has_in_stock(l3_id):
            return True
    return False


def _root_has_in_stock(root_id: int) -> bool:
    """Коренева категорія: хоч одна підкатегорія з товарами, або товар напряму на корені."""
    if poster_cache.has_in_stock(root_id):
        return True
    return any(_sub_has_in_stock(sub_id) for sub_id in SUBCATEGORIES.get(root_id, {}))


def categories_kb() -> InlineKeyboardMarkup:
    """Кореневі категорії — тільки з товарами в наявності."""
    buttons = []
    for cat_id, name in ROOT_CATEGORIES.items():
        if _root_has_in_stock(cat_id):
            buttons.append([InlineKeyboardButton(text=name, callback_data=f"root_{cat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subcategories_kb(root_id: int) -> InlineKeyboardMarkup:
    """Підкатегорії (бренди) — тільки з товарами в наявності.

    Якщо є товари, прив'язані в Poster напряму до кореневої категорії
    (без підкатегорії-бренду), додається кнопка "🗂 Інше", що веде на
    той самий обробник sub_ (show_products), бо кеш вже містить ці
    товари під ключем кореневої категорії.
    """
    subs = SUBCATEGORIES.get(root_id, {})
    buttons = []
    for sub_id, name in subs.items():
        if _sub_has_in_stock(sub_id):
            buttons.append([InlineKeyboardButton(text=name, callback_data=f"sub_{sub_id}")])
    if poster_cache.has_in_stock(root_id):
        buttons.append([InlineKeyboardButton(text="🗂 Інше", callback_data=f"sub_{root_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад до категорій", callback_data="back_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subcategories_l3_kb(parent_id: int) -> InlineKeyboardMarkup | None:
    """Підкатегорії 3-го рівня — тільки з товарами в наявності."""
    l3 = SUBCATEGORIES_L3.get(parent_id)
    if not l3:
        return None
    buttons = []
    for sub_id, name in l3.items():
        if poster_cache.has_in_stock(sub_id):
            buttons.append([InlineKeyboardButton(text=name, callback_data=f"sub_{sub_id}")])
    # Знайти батьківську кореневу для кнопки "назад"
    for root_id, subs in SUBCATEGORIES.items():
        if parent_id in subs:
            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"root_{root_id}")])
            break
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def products_kb(products: list[dict], page: int, category_id: int, parent_callback: str) -> InlineKeyboardMarkup:
    """Список товарів з пагінацією та індикаторами наявності."""
    total = len(products)
    total_pages = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    start = page * PRODUCTS_PER_PAGE
    end = start + PRODUCTS_PER_PAGE
    page_products = products[start:end]

    buttons = []
    for p in page_products:
        if p.get("has_modifications"):
            price_min = p.get("price_min", 0)
            price_max = p.get("price_max", 0)
            if price_min == price_max:
                price_str = f"{price_min:.0f} грн"
            else:
                price_str = f"від {price_min:.0f} до {price_max:.0f} грн"
            text = f"✅ {p['name']} — {price_str}"
        else:
            text = f"✅ {p['name']} — {p['price']:.0f} грн"
        buttons.append([InlineKeyboardButton(
            text=text, callback_data=f"prod_{p['id']}_{category_id}_{page}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text=f"⬅️ Стор. {page}/{total_pages}",
            callback_data=f"page_{category_id}_{page - 1}",
        ))
    if end < total:
        nav.append(InlineKeyboardButton(
            text=f"Стор. {page + 2}/{total_pages} ➡️",
            callback_data=f"page_{category_id}_{page + 1}",
        ))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=parent_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def modifications_kb(product_id: str, category_id: int, modifications: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    """Список модифікацій товару для вибору."""
    buttons = []
    for m in modifications:
        text = f"✅ {m['name']} — {m['price']:.0f} грн"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"mod_{product_id}_{m['mod_id']}_{category_id}_{page}",
        )])
    buttons.append([InlineKeyboardButton(
        text="⬅️ Назад до списку",
        callback_data=f"page_{category_id}_{page}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_card_kb(product_id: str, category_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Кнопки картки товару."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Додати в кошик", callback_data=f"addcart_{product_id}_{category_id}_{page}")],
        [InlineKeyboardButton(text="⬅️ Назад до списку", callback_data=f"page_{category_id}_{page}")],
    ])


def after_add_cart_kb(back_callback: str = "back_categories") -> InlineKeyboardMarkup:
    """Кнопки після додавання в кошик."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Перейти до кошика", callback_data="go_cart")],
        [InlineKeyboardButton(text="🛍 Продовжити покупки", callback_data=back_callback)],
    ])


def cart_kb() -> InlineKeyboardMarkup:
    """Кнопки кошика."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="checkout")],
        [InlineKeyboardButton(text="🧹 Очистити кошик", callback_data="clear_cart")],
    ])


def quick_order_kb() -> InlineKeyboardMarkup:
    """Кнопки швидкого замовлення (повторне)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Використати ці дані", callback_data="quick_order")],
        [InlineKeyboardButton(text="📦 Ввести нові дані", callback_data="new_order")],
    ])
