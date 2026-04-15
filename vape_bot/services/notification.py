"""Сповіщення в Telegram-канал при новому замовленні."""

from aiogram import Bot

from vape_bot.config.settings import NOTIFICATION_CHANNEL_ID


async def notify_new_order(bot: Bot, order: dict, username: str | None = None) -> None:
    """Надіслати сповіщення про нове замовлення в канал."""
    if not NOTIFICATION_CHANNEL_ID:
        return

    username_text = f"@{username}" if username else "невідомо"

    items_text = "\n".join(
        f"- {item['name']}: {item['qty']} шт."
        for item in order["items"]
    )

    text = (
        f"🎉 НОВА ЗАЯВКА №{order['order_number']}\n\n"
        f"👤 Клієнт: {order['full_name']} ({username_text})\n"
        f"📞 Телефон: {order['phone']}\n"
        f"🏙️ Місто: {order['city']}\n"
        f"📦 Адреса: {order['address']}\n\n"
        f"💳 Спосіб оплати: {order['payment_method']}\n\n"
        f"🛒 Товари:\n{items_text}\n\n"
        f"💰 Загальна сума: {float(order['total']):.2f} грн"
    )

    await bot.send_message(chat_id=NOTIFICATION_CHANNEL_ID, text=text)


async def notify_poster_sync_failed(bot: Bot, order_number: str) -> None:
    """Second message to channel when Poster sync fails after all retries."""
    if not NOTIFICATION_CHANNEL_ID:
        return
    await bot.send_message(
        chat_id=NOTIFICATION_CHANNEL_ID,
        text=(
            f"⚠️ Замовлення №{order_number} НЕ синхронізовано з Poster.\n"
            "Додайте вручну в CRM."
        ),
    )
