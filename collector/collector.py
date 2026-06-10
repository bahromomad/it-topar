from telethon import TelegramClient
from telethon.tl.types import User, Channel, Chat, UserStatusOnline, UserStatusOffline
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, UsernameNotOccupiedError, PeerIdInvalidError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    TGUser, TGGroup, GroupMembership, TGMessage,
    NameHistory, TrackRequest, BotUser, async_session
)
from datetime import datetime
from loguru import logger
import asyncio
import os

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

client = TelegramClient("/app/it_topar_session", API_ID, API_HASH)
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def start_client():
    await client.start(phone=PHONE)
    me = await client.get_me()
    logger.info(f"✅ Telethon ulandi: {me.first_name}")


async def fetch_user(user_id_or_username) -> dict | None:
    try:
        if isinstance(user_id_or_username, str):
            user_id_or_username = user_id_or_username.lstrip("@")
        full = await client(GetFullUserRequest(user_id_or_username))
        user = full.users[0]
        full_user = full.full_user
        last_online = None
        if hasattr(user, "status"):
            if isinstance(user.status, UserStatusOnline):
                last_online = datetime.utcnow()
            elif isinstance(user.status, UserStatusOffline):
                last_online = user.status.was_online
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "bio": getattr(full_user, "about", None),
            "phone": getattr(user, "phone", None),
            "is_bot": bool(user.bot),
            "is_premium": bool(getattr(user, "premium", False)),
            "is_verified": bool(getattr(user, "verified", False)),
            "is_scam": bool(getattr(user, "scam", False)),
            "last_online": last_online,
        }
    except UserPrivacyRestrictedError:
        try:
            entity = await client.get_entity(user_id_or_username)
            return {
                "id": entity.id,
                "username": getattr(entity, "username", None),
                "first_name": getattr(entity, "first_name", None),
                "last_name": getattr(entity, "last_name", None),
                "bio": None, "phone": None,
                "is_bot": False, "is_premium": False,
                "is_verified": False, "is_scam": False,
                "last_online": None,
            }
        except Exception:
            return None
    except FloodWaitError as e:
        logger.warning(f"FloodWait {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return None
    except (UsernameNotOccupiedError, PeerIdInvalidError):
        return None
    except Exception as e:
        logger.error(f"fetch_user xato: {e}")
        return None


async def save_user_to_db(info: dict) -> TGUser:
    async with async_session() as session:
        result = await session.execute(select(TGUser).where(TGUser.id == info["id"]))
        user = result.scalar_one_or_none()
        if user is None:
            user = TGUser(
                id=info["id"],
                username=info.get("username"),
                first_name=info.get("first_name"),
                last_name=info.get("last_name"),
                bio=info.get("bio"),
                phone=info.get("phone"),
                is_bot=info.get("is_bot", False),
                is_premium=info.get("is_premium", False),
                is_verified=info.get("is_verified", False),
                is_scam=info.get("is_scam", False),
                last_online=info.get("last_online"),
            )
            session.add(user)
            logger.info(f"Yangi user saqlandi: {info['id']}")
        else:
            changed = (
                user.username != info.get("username") or
                user.first_name != info.get("first_name") or
                user.last_name != info.get("last_name") or
                user.bio != info.get("bio")
            )
            if changed:
                history = NameHistory(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    bio=user.bio,
                )
                session.add(history)
                await notify_trackers(session, user, info)
            user.username = info.get("username")
            user.first_name = info.get("first_name")
            user.last_name = info.get("last_name")
            user.bio = info.get("bio")
            user.last_online = info.get("last_online") or user.last_online
            user.last_seen = datetime.utcnow()
        await session.commit()
        await session.refresh(user)
        return user


async def notify_trackers(session: AsyncSession, old_user: TGUser, new_info: dict):
    if not _bot:
        return
    result = await session.execute(
        select(TrackRequest).where(
            TrackRequest.target_id == old_user.id,
            TrackRequest.is_active == True
        )
    )
    tracks = result.scalars().all()
    changes = []
    if old_user.username != new_info.get("username"):
        changes.append(f"🔖 Username: @{old_user.username or '—'} → @{new_info.get('username') or '—'}")
    if old_user.first_name != new_info.get("first_name"):
        changes.append(f"👤 Ism: {old_user.first_name or '—'} → {new_info.get('first_name') or '—'}")
    if old_user.last_name != new_info.get("last_name"):
        changes.append(f"👤 Familiya: {old_user.last_name or '—'} → {new_info.get('last_name') or '—'}")
    if old_user.bio != new_info.get("bio"):
        changes.append(f"📝 Bio o'zgardi")
    if not changes:
        return
    text = (
        f"🔔 <b>O'zgarish aniqlandi!</b>\n\n"
        f"👤 {new_info.get('first_name') or ''} "
        f"(@{new_info.get('username') or old_user.id})\n\n"
        + "\n".join(changes)
    )
    for track in tracks:
        try:
            await _bot.send_message(track.tracker_id, text)
        except Exception:
            pass


async def fetch_group(username_or_id) -> dict | None:
    try:
        if isinstance(username_or_id, str):
            username_or_id = username_or_id.lstrip("@")
        entity = await client.get_entity(username_or_id)
        if isinstance(entity, Channel):
            full = await client(GetFullChannelRequest(entity))
            return {
                "id": entity.id,
                "username": getattr(entity, "username", None),
                "title": entity.title,
                "description": getattr(full.full_chat, "about", None),
                "members_count": getattr(full.full_chat, "participants_count", 0) or 0,
                "is_channel": bool(entity.broadcast),
                "is_megagroup": bool(entity.megagroup),
                "is_verified": bool(getattr(entity, "verified", False)),
                "is_scam": bool(getattr(entity, "scam", False)),
            }
        elif isinstance(entity, Chat):
            return {
                "id": entity.id,
                "username": None,
                "title": entity.title,
                "description": None,
                "members_count": entity.participants_count or 0,
                "is_channel": False,
                "is_megagroup": False,
                "is_verified": False,
                "is_scam": False,
            }
        return None
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return None
    except Exception as e:
        logger.error(f"fetch_group xato: {e}")
        return None


async def get_group_members(username_or_id, limit: int = 200) -> list:
    try:
        entity = await client.get_entity(username_or_id)
        members = []
        async for participant in client.iter_participants(entity, limit=limit):
            if isinstance(participant, User) and not participant.bot:
                members.append({
                    "id": participant.id,
                    "username": participant.username,
                    "first_name": participant.first_name,
                    "last_name": participant.last_name,
                })
        return members
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        return []
    except Exception as e:
        logger.error(f"get_group_members xato: {e}")
        return []


async def get_user_messages(group_username, user_id: int, limit: int = 30) -> list:
    try:
        entity = await client.get_entity(group_username)
        messages = []
        async for msg in client.iter_messages(entity, from_user=user_id, limit=limit):
            if msg.text:
                messages.append({
                    "id": msg.id,
                    "text": msg.text[:200],
                    "date": msg.date,
                    "views": getattr(msg, "views", 0) or 0,
                })
        return messages
    except Exception as e:
        logger.error(f"get_user_messages xato: {e}")
        return []


async def track_loop():
    while True:
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(TrackRequest).where(TrackRequest.is_active == True)
                )
                tracks = result.scalars().all()
            checked_ids = set()
            for track in tracks:
                if track.target_id in checked_ids:
                    continue
                checked_ids.add(track.target_id)
                info = await fetch_user(track.target_id)
                if info:
                    await save_user_to_db(info)
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"track_loop xato: {e}")
        await asyncio.sleep(300)
