"""Точка входу: запуск бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from vape_bot.bot.handlers import admin, cart, categories, my_orders, order, start, stubs
from vape_bot.config.settings import TELEGRAM_BOT_TOKEN
from vape_bot.services.poster import poster_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # Порядок важливий: order router має бути перед stubs,
    # щоб FSM стани перехоплювались до заглушок.
    # admin перед order — щоб /cleanup_test_orders не перехоплювався FSM.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(order.router)
    dp.include_router(categories.router)
    dp.include_router(cart.router)
    dp.include_router(my_orders.router)
    dp.include_router(stubs.router)

    logging.info("Bot starting...")
    await poster_cache.preload()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
