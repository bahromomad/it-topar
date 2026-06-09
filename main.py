import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

load_dotenv()

from database.models import init_db
from bot.handlers import router
from bot.admin import admin_router
from collector.collector import start_client, track_loop, set_bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


async def on_startup(bot: Bot):
    await init_db()
    logger.info("✅ Baza tayyor!")
    try:
        set_bot(bot)
        await start_client()
        asyncio.create_task(track_loop())
        logger.info("✅ Telethon tayyor!")
    except Exception as e:
        logger.error(f"❌ Telethon xato: {e}")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ <b>IT Topar Bot ishga tushdi!</b>")
        except Exception:
            pass


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN topilmadi!")
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(router)
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
