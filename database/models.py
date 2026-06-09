from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, BigInteger, DateTime, Text, ForeignKey, Integer, Boolean
from datetime import datetime
from typing import Optional, List
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/it_topar_db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TGUser(Base):
    __tablename__ = "tg_users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_scam: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_online: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    name_history: Mapped[List["NameHistory"]] = relationship(back_populates="user", cascade="all, delete")
    group_memberships: Mapped[List["GroupMembership"]] = relationship(back_populates="user", cascade="all, delete")
    messages: Mapped[List["TGMessage"]] = relationship(back_populates="user", cascade="all, delete")
    track_requests: Mapped[List["TrackRequest"]] = relationship(back_populates="target", cascade="all, delete")


class NameHistory(Base):
    __tablename__ = "name_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id"), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["TGUser"] = relationship(back_populates="name_history")


class TGGroup(Base):
    __tablename__ = "tg_groups"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    members_count: Mapped[int] = mapped_column(Integer, default=0)
    is_channel: Mapped[bool] = mapped_column(Boolean, default=False)
    is_megagroup: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_scam: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_scanned: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invite_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    members: Mapped[List["GroupMembership"]] = relationship(back_populates="group", cascade="all, delete")
    messages: Mapped[List["TGMessage"]] = relationship(back_populates="group", cascade="all, delete")


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id"), index=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_groups.id"), index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user: Mapped["TGUser"] = relationship(back_populates="group_memberships")
    group: Mapped["TGGroup"] = relationship(back_populates="members")


class TGMessage(Base):
    __tablename__ = "tg_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id"), index=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_groups.id"), index=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    forwards: Mapped[int] = mapped_column(Integer, default=0)
    reply_to: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped["TGUser"] = relationship(back_populates="messages")
    group: Mapped["TGGroup"] = relationship(back_populates="messages")


class BotUser(Base):
    __tablename__ = "bot_users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    total_searches: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    track_requests: Mapped[List["TrackRequest"]] = relationship(
        back_populates="tracker", cascade="all, delete",
        foreign_keys="TrackRequest.tracker_id"
    )


class TrackRequest(Base):
    __tablename__ = "track_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bot_users.id"), index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id"), index=True)
    target_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tracker: Mapped["BotUser"] = relationship(back_populates="track_requests", foreign_keys=[tracker_id])
    target: Mapped["TGUser"] = relationship(back_populates="track_requests", foreign_keys=[target_id])


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
