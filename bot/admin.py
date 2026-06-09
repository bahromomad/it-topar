from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, func
from database.models import TGUser, BotUser, TGGroup, TGMessage, TrackRequest, async_session
from collector.collector import fetch_user, save_user_to_db
import os

admin_router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


def admin_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            return
        return await func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@admin_router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    async with async_session() as session:
        u = (await session.execute(select(func.count()).select_from(TGUser))).scalar()
        b = (await session.execute(select(func.count()).select_from(BotUser))).scalar()
        g = (await session.execute(select(func.count()).select_from(TGGroup))).scalar()
        t = (await session.execute(select(func.count()).where(TrackRequest.is_active == True))).scalar()
    await message.answer(
        "🛡 <b>Admin Panel</b>\n\n"
        f"👤 TG foydalanuvchilar: {u:,}\n"
        f"🤖 Bot foydalanuvchilari: {b:,}\n"
        f"👥 Guruhlar: {g:,}\n"
        f"👁 Faol kuzatishlar: {t:,}\n\n"
        "<b>Buyruqlar:</b>\n"
        "/ban ID — Bloklash\n"
        "/unban ID — Blokdan chiqarish\n"
        "/adduser @username — Foydalanuvchi qo'shish\n"
        "/broadcast matn — Hammaga xabar\n"
        "/dbstats — Baza holati"
    )


@admin_router.message(Command("ban"))
@admin_only
async def cmd_ban(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Misol: /ban 123456789")
        return
    async with async_session() as session:
        r = await session.execute(select(BotUser).where(BotUser.id == int(args[1])))
        u = r.scalar_one_or_none()
        if u:
            u.is_banned = True
            await session.commit()
            await message.answer(f"✅ {args[1]} bloklandi.")
        else:
            await message.answer("❌ Topilmadi.")


@admin_router.message(Command("unban"))
@admin_only
async def cmd_unban(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Misol: /unban 123456789")
        return
    async with async_session() as session:
        r = await session.execute(select(BotUser).where(BotUser.id == int(args[1])))
        u = r.scalar_one_or_none()
        if u:
            u.is_banned = False
            await session.commit()
            await message.answer(f"✅ {args[1]} blokdan chiqarildi.")
        else:
            await message.answer("❌ Topilmadi.")


@admin_router.message(Command("adduser"))
@admin_only
async def cmd_adduser(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Misol: /adduser @username")
        return
    wait = await message.answer("⏳ Qidirilmoqda...")
    info = await fetch_user(args[1].lstrip("@"))
    if info:
        await save_user_to_db(info)
        await wait.edit_text(
            f"✅ Saqlandi:\n"
            f"👤 {info.get('first_name')} | @{info.get('username')} | ID: {info['id']}"
        )
    else:
        await wait.edit_text("❌ Topilmadi.")


@admin_router.message(Command("broadcast"))
@admin_only
async def cmd_broadcast(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Misol: /broadcast Xabar matni")
        return
    text = args[1]
    async with async_session() as session:
        r = await session.execute(select(BotUser).where(BotUser.is_banned == False))
        users = r.scalars().all()
    from aiogram import Bot
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    sent, failed = 0, 0
    for u in users:
        try:
            await bot.send_message(u.id, f"📢 <b>Xabar:</b>\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
    await bot.session.close()
    await message.answer(f"✅ Yuborildi: {sent}\n❌ Xato: {failed}")


@admin_router.message(Command("dbstats"))
@admin_only
async def cmd_dbstats(message: Message):
    async with async_session() as session:
        u = (await session.execute(select(func.count()).select_from(TGUser))).scalar()
        g = (await session.execute(select(func.count()).select_from(TGGroup))).scalar()
        m = (await session.execute(select(func.count()).select_from(TGMessage))).scalar()
        b = (await session.execute(select(func.count()).select_from(BotUser))).scalar()
        t = (await session.execute(select(func.count()).where(TrackRequest.is_active == True))).scalar()
    await message.answer(
        "🗄 <b>Baza holati:</b>\n\n"
        f"TGUser: {u:,}\n"
        f"TGGroup: {g:,}\n"
        f"TGMessage: {m:,}\n"
        f"BotUser: {b:,}\n"
        f"TrackRequest (faol): {t:,}"
    )
