"""Хендлер категорій: кореневі → підкатегорії → товари → картка товару."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from vape_bot.bot.keyboards.inline import (
    after_add_cart_kb,
    categories_kb,
    modifications_kb,
    product_card_kb,
    products_kb,
    subcategories_kb,
    subcategories_l3_kb,
)
from vape_bot.config.settings import ROOT_CATEGORIES, SUBCATEGORIES, SUBCATEGORIES_L3
from vape_bot.database.cart import add_to_cart, get_cart_total
from vape_bot.database.users import get_or_create_user
from vape_bot.services.poster import poster_cache

router = Router()


def _find_category_path(category_id: int) -> list[str]:
    """Знайти шлях від кореня до категорії: ["Pod-системи", "Vaporesso"]."""
    # L3
    for parent_id, l3_subs in SUBCATEGORIES_L3.items():
        if category_id in l3_subs:
            for root_id, subs in SUBCATEGORIES.items():
                if parent_id in subs:
                    return [ROOT_CATEGORIES[root_id], subs[parent_id], l3_subs[category_id]]
    # L2
    for root_id, subs in SUBCATEGORIES.items():
        if category_id in subs:
            return [ROOT_CATEGORIES[root_id], subs[category_id]]
    # Root
    if category_id in ROOT_CATEGORIES:
        return [ROOT_CATEGORIES[category_id]]
    return [str(category_id)]


def _breadcrumb(category_id: int, suffix: str = "") -> str:
    """Побудувати деревоподібний breadcrumb для категорії.

    Приклад: 📁 Pod-системи
             ╰── 📁 Vaporesso (Стор. 1/5):
    """
    path = _find_category_path(category_id)
    lines = [f"📁 {path[0]}"]
    for i, name in enumerate(path[1:], 1):
        indent = "    " * (i - 1)
        lines.append(f"{indent}╰── 📁 {name}")
    lines[-1] += suffix
    return "\n".join(lines)


def _product_breadcrumb(category_id: int, product_name: str) -> str:
    """Breadcrumb з назвою товару на кінці.

    Приклад: 📁 Pod-системи
             ╰── 📁 Vaporesso
                 ╰── Vaporesso Xros 5 Mini
    """
    path = _find_category_path(category_id)
    lines = [f"📁 {path[0]}"]
    for i, name in enumerate(path[1:], 1):
        indent = "    " * (i - 1)
        lines.append(f"{indent}╰── 📁 {name}")
    indent = "    " * len(path[1:])
    lines.append(f"{indent}╰── {product_name}")
    return "\n".join(lines)


@router.message(F.text == "📁 Категорії")
async def show_categories(message: Message):
    """Показати кореневі категорії."""
    await message.answer("Оберіть категорію:", reply_markup=categories_kb())


@router.callback_query(F.data == "back_categories")
async def back_to_categories(callback: CallbackQuery):
    """Повернутись до кореневих категорій."""
    await callback.message.edit_text("Оберіть категорію:", reply_markup=categories_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("root_"))
async def show_subcategories(callback: CallbackQuery):
    """Показати підкатегорії (бренди) кореневої категорії."""
    root_id = int(callback.data.split("_")[1])
    name = ROOT_CATEGORIES.get(root_id, "")
    await callback.message.edit_text(
        f"📁 {name}\nОберіть підкатегорію:",
        reply_markup=subcategories_kb(root_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub_"))
async def show_products(callback: CallbackQuery):
    """Показати товари підкатегорії або L3 підкатегорії."""
    sub_id = int(callback.data.split("_")[1])

    # Перевірити чи це L3 категорія (має підкатегорії)
    l3_kb = subcategories_l3_kb(sub_id)
    if l3_kb:
        await callback.message.edit_text(
            _breadcrumb(sub_id) + "\nОберіть підкатегорію:",
            reply_markup=l3_kb,
        )
        await callback.answer()
        return

    # Знайти назву категорії та parent для кнопки "назад"
    name = str(sub_id)
    parent_callback = "back_categories"
    for root_id, subs in SUBCATEGORIES.items():
        if sub_id in subs:
            name = subs[sub_id]
            parent_callback = f"root_{root_id}"
            break
    # Може бути L3
    for parent_id, l3_subs in SUBCATEGORIES_L3.items():
        if sub_id in l3_subs:
            name = l3_subs[sub_id]
            parent_callback = f"sub_{parent_id}"
            break

    products = poster_cache.get_products_by_category(sub_id)

    if not products:
        await callback.message.edit_text(
            _breadcrumb(sub_id) + "\n\nТоварів не знайдено.",
            reply_markup=products_kb([], 0, sub_id, parent_callback),
        )
        await callback.answer()
        return

    total_pages = max(1, (len(products) + 9) // 10)
    await callback.message.edit_text(
        _breadcrumb(sub_id, f" (Стор. 1/{total_pages}):"),
        reply_markup=products_kb(products, 0, sub_id, parent_callback),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("page_"))
async def paginate_products(callback: CallbackQuery):
    """Пагінація товарів."""
    parts = callback.data.split("_")
    category_id = int(parts[1])
    page = int(parts[2])

    # Знайти назву та parent
    name = str(category_id)
    parent_callback = "back_categories"
    for root_id, subs in SUBCATEGORIES.items():
        if category_id in subs:
            name = subs[category_id]
            parent_callback = f"root_{root_id}"
            break
    for parent_id, l3_subs in SUBCATEGORIES_L3.items():
        if category_id in l3_subs:
            name = l3_subs[category_id]
            parent_callback = f"sub_{parent_id}"
            break

    products = poster_cache.get_products_by_category(category_id)
    total_pages = max(1, (len(products) + 9) // 10)

    await callback.message.edit_text(
        _breadcrumb(category_id, f" (Стор. {page + 1}/{total_pages}):"),
        reply_markup=products_kb(products, page, category_id, parent_callback),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery):
    """Картка товару або список модифікацій."""
    parts = callback.data.split("_")
    product_id = parts[1]
    cat_id = int(parts[2]) if len(parts) > 2 else 0
    page = int(parts[3]) if len(parts) > 3 else 0
    product = poster_cache.get_product_by_id(product_id)

    if not product:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    # Product with modifications
    if product.get("has_modifications"):
        if product.get("stock", 0) <= 0:
            await callback.answer("Немає в наявності", show_alert=True)
            return

        mods = product.get("modifications", [])
        effective_cat = cat_id or int(product["category_id"])
        await callback.message.edit_text(
            _product_breadcrumb(effective_cat, product["name"]) + "\nОберіть варіант:",
            reply_markup=modifications_kb(
                product_id, effective_cat, mods, page
            ),
        )
        await callback.answer()
        return

    # Regular product — out of stock
    if product.get("stock", 0) <= 0:
        await callback.answer("Немає в наявності", show_alert=True)
        return

    # Regular product — in stock
    stock_val = product.get("stock", 0)
    effective_cat = cat_id or int(product["category_id"])

    text = (
        _product_breadcrumb(effective_cat, product["name"])
        + f"\n\n💰 Ціна: {product['price']:.0f} грн\n"
        f"📦 Статус: ✅ В наявності ({stock_val:.0f} шт.)"
    )

    await callback.message.edit_text(
        text,
        reply_markup=product_card_kb(product_id, effective_cat, page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mod_"))
async def select_modification(callback: CallbackQuery):
    """Вибір модифікації — одразу додає в кошик."""
    parts = callback.data.split("_")
    parent_id = parts[1]
    mod_id = parts[2]
    cat_id = parts[3] if len(parts) > 3 else ""
    page = parts[4] if len(parts) > 4 else "0"

    product = poster_cache.get_product_by_id(parent_id)
    if not product:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    # Find the specific modification
    mod = None
    for m in product.get("modifications", []):
        if m["mod_id"] == mod_id:
            mod = m
            break

    if not mod:
        await callback.answer("Варіант не знайдено", show_alert=True)
        return

    if mod.get("stock", 0) <= 0:
        await callback.answer("Немає в наявності", show_alert=True)
        return

    # Add to cart with composite ID
    get_or_create_user(callback.from_user.id, callback.from_user.username)
    cart_product_id = f"{parent_id}_{mod_id}"
    cart_product_name = f"{product['name']} — {mod['name']}"
    add_to_cart(
        user_id=callback.from_user.id,
        product_id=cart_product_id,
        product_name=cart_product_name,
        price=mod["price"],
    )
    total = get_cart_total(callback.from_user.id)

    back_cb = f"page_{cat_id}_{page}" if cat_id else "back_categories"
    await callback.message.edit_text(
        f"✅ {cart_product_name} додано в кошик!\n"
        f"💰 Поточна сума кошика: {total:.2f} грн",
        reply_markup=after_add_cart_kb(back_cb),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addcart_"))
async def add_to_cart_handler(callback: CallbackQuery):
    """Додати товар в кошик."""
    parts = callback.data.split("_")
    product_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""
    page = parts[3] if len(parts) > 3 else "0"
    product = poster_cache.get_product_by_id(product_id)

    if not product:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    if product.get("stock", 0) <= 0:
        await callback.answer("Немає в наявності", show_alert=True)
        return

    get_or_create_user(callback.from_user.id, callback.from_user.username)
    add_to_cart(
        user_id=callback.from_user.id,
        product_id=product_id,
        product_name=product["name"],
        price=product["price"],
    )
    total = get_cart_total(callback.from_user.id)

    back_cb = f"page_{cat_id}_{page}" if cat_id else "back_categories"
    await callback.message.edit_text(
        f"✅ {product['name']} додано в кошик!\n"
        f"💰 Поточна сума кошика: {total:.2f} грн",
        reply_markup=after_add_cart_kb(back_cb),
    )
    await callback.answer()
