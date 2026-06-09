from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    TGUser, BotUser, NameHistory, GroupMembership,
    TGGroup, TGMessage, TrackRequest, async_session
)
from collector.collector import (
    fetch_user, save_user_to_db,
    fetch_group, get_group_members, get_user_messages
)
from utils.keyboards import (
    main_menu_kb, back_kb, user_detail_kb,
    group_detail_kb, tracks_kb
)
from datetime import datetime
from loguru import logger
import os

router = Router()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


class States(StatesGroup):
    search_user = State()
    search_group = State()


async def upsert_bot_user(session: AsyncSession, msg: Message) -> BotUser:
    r = await session.execute(select(BotUser).where(BotUser.id == msg.from_user.id))
    u = r.scalar_one_or_none()
    if not u:
        u = BotUser(
            id=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
            is_admin=msg.from_user.id in ADMIN_IDS,
        )
        session.add(u)
        await session.commit()
    else:
        u.last_active = datetime.utcnow()
        await session.commit()
    return u


def format_user(u: TGUser, g_count=0, m_count=0, n_count=0) -> str:
    online = u.last_online.strftime("%d.%m.%Y %H:%M") if u.last_online else "Noma'lum"
    seen = u.first_seen.strftime("%d.%m.%Y") if u.first_seen else "—"
    badges = []
    if u.is_premium: badges.append("⭐ Premium")
    if u.is_verified: badges.append("✅ Tasdiqlangan")
    if u.is_scam: badges.append("⚠️ Scam")
    if u.is_bot: badges.append("🤖 Bot")
    return (
        f"👤 <b>{u.first_name or ''} {u.last_name or ''}</b>\n"
        f"🔖 Username: {'@' + u.username if u.username else '—'}\n"
        f"🆔 ID: <code>{u.id}</code>\n"
        f"{'  '.join(badges) if badges else ''}\n"
        f"👥 Guruhlarda: <b>{g_count}</b> ta\n"
        f"💬 Xabarlar: <b>{m_count}</b> ta\n"
        f"🕒 Ism tarixi: <b>{n_count}</b> ta o'zgarish\n"
        f"📶 So'nggi faollik: {online}\n"
        f"📅 Birinchi ko'rilgan: {seen}"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        await upsert_bot_user(session, message)
    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        f"🔎 <b>IT Topar</b> — Telegram foydalanuvchilarini topish va tahlil qilish vositasi.\n\n"
        f"Quyidagi tugmalardan birini tanlang 👇",
        reply_markup=main_menu_kb()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "/start — Bosh menyu\n"
        "/search @username — Foydalanuvchi qidirish\n"
        "/group @guruh — Guruh tahlili\n"
        "/track @username — Kuzatishni boshlash\n"
        "/tracks — Kuzatilayotganlar\n"
        "/stats — Umumiy statistika\n\n"
        "<b>Imkoniyatlar:</b>\n"
        "🔍 Username yoki ID bo'yicha qidirish\n"
        "👥 Foydalanuvchi guruhlarini ko'rish\n"
        "💬 Ommaviy xabarlar tarixini ko'rish\n"
        "🕒 Ism/username o'zgarishlari tarixi\n"
        "👁 Real vaqtda kuzatish va bildirishnoma\n"
        "📊 Guruh a'zolari ro'yxati",
        reply_markup=back_kb()
    )


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await do_user_search(message, args[1].strip())
    else:
        await message.answer("🔍 Qidirmoqchi bo'lgan username yoki ID ni yuboring:")
        await state.set_state(States.search_user)


@router.message(Command("group"))
async def cmd_group(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await do_group_search(message, args[1].strip())
    else:
        await message.answer("👥 Guruh username yoki havolasini yuboring:")
        await state.set_state(States.search_group)


@router.message(Command("track"))
async def cmd_track(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Misol: /track @username")
        return
    await do_track(message, args[1].strip())


@router.message(Command("tracks"))
async def cmd_tracks(message: Message):
    async with async_session() as session:
        r = await session.execute(
            select(TrackRequest).where(
                TrackRequest.tracker_id == message.from_user.id,
                TrackRequest.is_active == True
            )
        )
        tracks = r.scalars().all()
    if not tracks:
        await message.answer(
            "👁 <b>Kuzatilayotganlar yo'q</b>\n\n"
            "Biror foydalanuvchini qidirib, 'Kuzatish' tugmasini bosing.",
            reply_markup=back_kb()
        )
        return
    await message.answer(
        f"👁 <b>Kuzatilayotganlar: {len(tracks)} ta</b>\n\nTo'xtatish uchun ❌ bosing:",
        reply_markup=tracks_kb(tracks)
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    async with async_session() as session:
        u = (await session.execute(select(func.count()).select_from(TGUser))).scalar()
        g = (await session.execute(select(func.count()).select_from(TGGroup))).scalar()
        m = (await session.execute(select(func.count()).select_from(TGMessage))).scalar()
        b = (await session.execute(select(func.count()).select_from(BotUser))).scalar()
    await message.answer(
        "📊 <b>IT Topar statistikasi:</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{u:,}</b>\n"
        f"👥 Guruhlar: <b>{g:,}</b>\n"
        f"💬 Xabarlar: <b>{m:,}</b>\n"
        f"🤖 Bot foydalanuvchilari: <b>{b:,}</b>",
        reply_markup=back_kb()
    )


@router.message(States.search_user)
async def state_search_user(message: Message, state: FSMContext):
    await state.clear()
    await do_user_search(message, message.text.strip())


@router.message(States.search_group)
async def state_search_group(message: Message, state: FSMContext):
    await state.clear()
    await do_group_search(message, message.text.strip())


async def do_user_search(message: Message, query: str):
    async with async_session() as session:
        bu = await upsert_bot_user(session, message)
        if bu.is_banned:
            await message.answer("❌ Siz bloklangansiz.")
            return
    wait = await message.answer("⏳ <b>Qidirilmoqda...</b>")
    query_clean = query.lstrip("@")
    async with async_session() as session:
        if query_clean.isdigit():
            r = await session.execute(select(TGUser).where(TGUser.id == int(query_clean)))
        else:
            r = await session.execute(select(TGUser).where(TGUser.username == query_clean))
        db_user = r.scalar_one_or_none()
    if db_user:
        async with async_session() as session:
            gc = (await session.execute(select(func.count()).where(
                GroupMembership.user_id == db_user.id, GroupMembership.is_active == True
            ))).scalar()
            mc = (await session.execute(select(func.count()).where(TGMessage.user_id == db_user.id))).scalar()
            nc = (await session.execute(select(func.count()).where(NameHistory.user_id == db_user.id))).scalar()
        text = "✅ <b>Bazadan topildi!</b>\n\n" + format_user(db_user, gc, mc, nc)
        await wait.edit_text(text, reply_markup=user_detail_kb(db_user.id))
        asyncio.create_task(_refresh_user(db_user.id, query_clean))
        return
    info = await fetch_user(query_clean)
    if info:
        await save_user_to_db(info)
        async with async_session() as session:
            r = await session.execute(select(TGUser).where(TGUser.id == info["id"]))
            user = r.scalar_one_or_none()
        text = "🌐 <b>Telegram'dan topildi!</b>\n\n" + format_user(user)
        await wait.edit_text(text, reply_markup=user_detail_kb(info["id"]))
        async with async_session() as session:
            bu = await upsert_bot_user(session, message)
            bu.total_searches += 1
            await session.commit()
    else:
        await wait.edit_text(
            f"❌ <b>Topilmadi:</b> {query}\n\nUsername noto'g'ri yoki mavjud emas.",
            reply_markup=back_kb()
        )


async def _refresh_user(user_id: int, query: str):
    try:
        info = await fetch_user(query if not str(query).isdigit() else user_id)
        if info:
            await save_user_to_db(info)
    except Exception:
        pass


async def do_group_search(message: Message, query: str):
    wait = await message.answer("⏳ <b>Guruh qidirilmoqda...</b>")
    query_clean = query.lstrip("@").split("/")[-1]
    info = await fetch_group(query_clean)
    if not info:
        await wait.edit_text("❌ Guruh topilmadi.", reply_markup=back_kb())
        return
    async with async_session() as session:
        r = await session.execute(select(TGGroup).where(TGGroup.id == info["id"]))
        grp = r.scalar_one_or_none()
        if not grp:
            grp = TGGroup(
                id=info["id"], username=info.get("username"), title=info["title"],
                description=info.get("description"), members_count=info.get("members_count", 0),
                is_channel=info.get("is_channel", False), is_megagroup=info.get("is_megagroup", False),
                is_verified=info.get("is_verified", False), is_scam=info.get("is_scam", False),
            )
            session.add(grp)
            await session.commit()
        else:
            grp.members_count = info.get("members_count", 0)
            grp.last_scanned = datetime.utcnow()
            await session.commit()
    icon = "📢" if info["is_channel"] else "👥"
    text = (
        f"{icon} <b>{info['title']}</b>\n"
        f"🔖 Username: {'@' + info['username'] if info.get('username') else '—'}\n"
        f"🆔 ID: <code>{info['id']}</code>\n"
        f"👥 A'zolar: <b>{info.get('members_count', 0):,}</b>\n"
        f"📝 Tavsif: {(info.get('description') or '—')[:150]}"
    )
    await wait.edit_text(text, reply_markup=group_detail_kb(info["id"]))


async def do_track(message: Message, query: str):
    query_clean = query.lstrip("@")
    wait = await message.answer("⏳ <b>Tekshirilmoqda...</b>")
    info = await fetch_user(query_clean)
    if not info:
        await wait.edit_text(f"❌ Foydalanuvchi topilmadi: {query}", reply_markup=back_kb())
        return
    await save_user_to_db(info)
    async with async_session() as session:
        bu_r = await session.execute(select(BotUser).where(BotUser.id == message.from_user.id))
        bu = bu_r.scalar_one_or_none()
        if not bu:
            bu = BotUser(id=message.from_user.id, username=message.from_user.username,
                         first_name=message.from_user.first_name)
            session.add(bu)
            await session.commit()
        r = await session.execute(
            select(TrackRequest).where(
                TrackRequest.tracker_id == message.from_user.id,
                TrackRequest.target_id == info["id"],
                TrackRequest.is_active == True
            )
        )
        if r.scalar_one_or_none():
            await wait.edit_text(
                f"ℹ️ <b>{info.get('first_name') or query}</b> allaqachon kuzatilmoqda!",
                reply_markup=back_kb()
            )
            return
        track = TrackRequest(
            tracker_id=message.from_user.id,
            target_id=info["id"],
            target_username=info.get("username"),
        )
        session.add(track)
        await session.commit()
    await wait.edit_text(
        f"✅ <b>{info.get('first_name') or query}</b> kuzatuvga qo'shildi!\n\n"
        f"Ism, username yoki bio o'zgarganda xabardor qilinasiz. 🔔\n\n"
        f"/tracks — barcha kuzatilayotganlar",
        reply_markup=back_kb()
    )


@router.callback_query(F.data == "main_menu")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("🏠 <b>Bosh menyu</b>\n\nNima qilmoqchisiz?", reply_markup=main_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "search_user")
async def cb_search_user(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("🔍 Username yoki ID yuboring:")
    await state.set_state(States.search_user)
    await cb.answer()


@router.callback_query(F.data == "search_group")
async def cb_search_group(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("👥 Guruh username yoki havolasini yuboring:")
    await state.set_state(States.search_group)
    await cb.answer()


@router.callback_query(F.data == "statistics")
async def cb_stats(cb: CallbackQuery):
    async with async_session() as session:
        u = (await session.execute(select(func.count()).select_from(TGUser))).scalar()
        g = (await session.execute(select(func.count()).select_from(TGGroup))).scalar()
        m = (await session.execute(select(func.count()).select_from(TGMessage))).scalar()
    await cb.message.edit_text(
        "📊 <b>IT Topar statistikasi:</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{u:,}</b>\n"
        f"👥 Guruhlar: <b>{g:,}</b>\n"
        f"💬 Xabarlar: <b>{m:,}</b>",
        reply_markup=back_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    await cb.message.edit_text(
        "❓ <b>Yordam</b>\n\n/search @username — Qidirish\n"
        "/group @guruh — Guruh tahlili\n/track @username — Kuzatish\n"
        "/tracks — Kuzatilayotganlar\n/stats — Statistika",
        reply_markup=back_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "my_tracks")
async def cb_my_tracks(cb: CallbackQuery):
    async with async_session() as session:
        r = await session.execute(
            select(TrackRequest).where(
                TrackRequest.tracker_id == cb.from_user.id,
                TrackRequest.is_active == True
            )
        )
        tracks = r.scalars().all()
    if not tracks:
        await cb.message.edit_text(
            "👁 <b>Kuzatilayotganlar yo'q</b>\n\n"
            "/search buyrug'i bilan foydalanuvchi qidirib, 'Kuzatish' tugmasini bosing.",
            reply_markup=back_kb()
        )
    else:
        await cb.message.edit_text(f"👁 <b>Kuzatilayotganlar: {len(tracks)} ta</b>", reply_markup=tracks_kb(tracks))
    await cb.answer()


@router.callback_query(F.data.startswith("untrack_"))
async def cb_untrack(cb: CallbackQuery):
    track_id = int(cb.data.split("_")[1])
    async with async_session() as session:
        r = await session.execute(select(TrackRequest).where(TrackRequest.id == track_id))
        track = r.scalar_one_or_none()
        if track:
            track.is_active = False
            await session.commit()
    await cb.answer("✅ Kuzatish to'xtatildi!", show_alert=True)
    async with async_session() as session:
        r = await session.execute(
            select(TrackRequest).where(
                TrackRequest.tracker_id == cb.from_user.id,
                TrackRequest.is_active == True
            )
        )
        tracks = r.scalars().all()
    if tracks:
        await cb.message.edit_reply_markup(reply_markup=tracks_kb(tracks))
    else:
        await cb.message.edit_text("👁 Kuzatilayotganlar yo'q.", reply_markup=back_kb())


@router.callback_query(F.data.startswith("names_"))
async def cb_names(cb: CallbackQuery):
    uid = int(cb.data.split("_")[1])
    async with async_session() as session:
        r = await session.execute(
            select(NameHistory).where(NameHistory.user_id == uid)
            .order_by(desc(NameHistory.changed_at)).limit(15)
        )
        history = r.scalars().all()
    if not history:
        await cb.answer("Tarix yo'q", show_alert=True)
        return
    text = "🕒 <b>Ism o'zgarishlari tarixi:</b>\n\n"
    for h in history:
        text += f"📅 {h.changed_at.strftime('%d.%m.%Y %H:%M')}\n   👤 {h.first_name or '—'} {h.last_name or ''}\n   🔖 @{h.username or '—'}\n\n"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ugroups_"))
async def cb_ugroups(cb: CallbackQuery):
    uid = int(cb.data.split("_")[1])
    async with async_session() as session:
        r = await session.execute(
            select(TGGroup).join(GroupMembership, GroupMembership.group_id == TGGroup.id)
            .where(GroupMembership.user_id == uid, GroupMembership.is_active == True).limit(20)
        )
        groups = r.scalars().all()
    if not groups:
        await cb.answer("Guruhlar topilmadi", show_alert=True)
        return
    text = "👥 <b>Foydalanuvchi guruhlari:</b>\n\n"
    for g in groups:
        icon = "📢" if g.is_channel else "👥"
        link = f"@{g.username}" if g.username else f"ID {g.id}"
        text += f"{icon} {g.title} — {link}\n"
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("track_"))
async def cb_track(cb: CallbackQuery):
    uid = int(cb.data.split("_")[1])
    async with async_session() as session:
        r = await session.execute(
            select(TrackRequest).where(
                TrackRequest.tracker_id == cb.from_user.id,
                TrackRequest.target_id == uid,
                TrackRequest.is_active == True
            )
        )
        if r.scalar_one_or_none():
            await cb.answer("ℹ️ Allaqachon kuzatilmoqda!", show_alert=True)
            return
        ur = await session.execute(select(TGUser).where(TGUser.id == uid))
        target = ur.scalar_one_or_none()
        bu_r = await session.execute(select(BotUser).where(BotUser.id == cb.from_user.id))
        bu = bu_r.scalar_one_or_none()
        if not bu:
            bu = BotUser(id=cb.from_user.id, username=cb.from_user.username, first_name=cb.from_user.first_name)
            session.add(bu)
        track = TrackRequest(
            tracker_id=cb.from_user.id, target_id=uid,
            target_username=target.username if target else None,
        )
        session.add(track)
        await session.commit()
    name = target.first_name if target else f"ID {uid}"
    await cb.answer(f"✅ {name} kuzatuvga qo'shildi!", show_alert=True)


@router.callback_query(F.data.startswith("gmembers_"))
async def cb_gmembers(cb: CallbackQuery):
    gid = int(cb.data.split("_")[1])
    wait_msg = await cb.message.edit_text("⏳ A'zolar yuklanmoqda...")
    async with async_session() as session:
        r = await session.execute(select(TGGroup).where(TGGroup.id == gid))
        grp = r.scalar_one_or_none()
    if not grp:
        await wait_msg.edit_text("❌ Guruh topilmadi.", reply_markup=back_kb())
        return
    members = await get_group_members(grp.username or str(gid), limit=100)
    if not members:
        await wait_msg.edit_text("❌ A'zolar olinmadi.", reply_markup=back_kb())
        return
    async with async_session() as session:
        for m in members[:50]:
            r = await session.execute(select(TGUser).where(TGUser.id == m["id"]))
            user = r.scalar_one_or_none()
            if not user:
                session.add(TGUser(id=m["id"], username=m.get("username"),
                                   first_name=m.get("first_name"), last_name=m.get("last_name")))
            mr = await session.execute(
                select(GroupMembership).where(
                    GroupMembership.user_id == m["id"], GroupMembership.group_id == gid
                )
            )
            if not mr.scalar_one_or_none():
                session.add(GroupMembership(user_id=m["id"], group_id=gid, is_active=True))
        await session.commit()
    text = f"👥 <b>{grp.title} — A'zolar ({len(members)} ta):</b>\n\n"
    for m in members[:30]:
        name = m.get("first_name") or "Noma'lum"
        uname = f" @{m['username']}" if m.get("username") else ""
        text += f"• {name}{uname}\n"
    if len(members) > 30:
        text += f"\n<i>...va yana {len(members) - 30} ta</i>"
    await wait_msg.edit_text(text, reply_markup=back_kb())
    await cb.answer()


import asyncio
