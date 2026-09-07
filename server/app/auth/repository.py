"""Data access for accounts and authentication sessions.

All queries go through the SQLAlchemy ORM with bound parameters. There is no
string-concatenated SQL here, and there must never be.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AccountStatus, AuthSession, User


class UsernameTakenError(Exception):
    """Raised when an account identifier is already in use."""


class UserRepository:
    """Account persistence."""

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        username: str,
        username_normalized: str,
        password_hash: str,
        now: datetime,
    ) -> User:
        """Insert a new account.

        Uniqueness is enforced by the database constraint, not by a preceding
        existence check. A check-then-insert would race: two concurrent
        registrations could both pass the check. The IntegrityError is the
        authoritative answer (`AUTH-007`, race safety).
        """
        user = User(
            id=user_id,
            username=username,
            username_normalized=username_normalized,
            password_hash=password_hash,
            status=AccountStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(user)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise UsernameTakenError from exc
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        """Look up an account by its opaque public id."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_normalized_username(self, username_normalized: str) -> User | None:
        """Look up an account by its normalized identifier."""
        result = await self._session.execute(
            select(User).where(User.username_normalized == username_normalized)
        )
        return result.scalar_one_or_none()

    async def delete(self, user: User) -> None:
        """Remove an account and, by cascade, all of its sessions."""
        await self._session.delete(user)
        await self._session.flush()


class SessionRepository:
    """Authentication-session persistence."""

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        session_id: str,
        user_id: str,
        refresh_token_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        """Record a new authentication session."""
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            created_at=now,
            expires_at=expires_at,
        )
        self._session.add(auth_session)
        await self._session.flush()
        return auth_session

    async def get(self, session_id: str) -> AuthSession | None:
        """Fetch a session by id."""
        result = await self._session.execute(
            select(AuthSession).where(AuthSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_refresh_hash(self, refresh_token_hash: str) -> AuthSession | None:
        """Fetch a session by the hash of its refresh token."""
        result = await self._session.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == refresh_token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, auth_session: AuthSession, now: datetime) -> None:
        """Revoke a single session, if not already revoked."""
        if auth_session.revoked_at is None:
            auth_session.revoked_at = now
            await self._session.flush()

    async def revoke_all_for_user(self, user_id: str, now: datetime) -> int:
        """Revoke every live session for an account.

        Used by account deletion and available for a future "sign out
        everywhere" action.
        """
        statement = (
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = cast("CursorResult[Any]", await self._session.execute(statement))
        await self._session.flush()
        return int(result.rowcount or 0)

    async def rotate_refresh_token(
        self,
        auth_session: AuthSession,
        *,
        refresh_token_hash: str,
        expires_at: datetime,
    ) -> None:
        """Replace a session's refresh token with a freshly issued one.

        Rotation means a stolen refresh token stops working as soon as the
        legitimate client refreshes.
        """
        auth_session.refresh_token_hash = refresh_token_hash
        auth_session.expires_at = expires_at
        await self._session.flush()
