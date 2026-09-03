"""Account and session persistence models.

Only what authentication needs is stored. Deliberately absent, and prohibited
by Phase 0 (`AUTH-003`, `CRYPTO-002`, `SERVER-002`):

* plaintext or reversibly encrypted passwords;
* password recovery answers;
* message plaintext or message keys;
* cryptographic identity private keys (Phase 4 keeps those on the endpoint).

Refresh tokens are stored only as a SHA-256 hash, so a database compromise
does not yield usable refresh credentials.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all persistence models."""


class AccountStatus(StrEnum):
    """Lifecycle state of an account."""

    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    """A user account.

    `username_normalized` carries the uniqueness constraint so that
    case-insensitive and Unicode-equivalent variants cannot collide, while
    `username` preserves what the user typed for display.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username_normalized", name="uq_users_username_normalized"),)

    #: Public, opaque identifier. Used in tokens and routing instead of a
    #: sequential database key.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    username: Mapped[str] = mapped_column(String(32), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    #: Argon2id encoded hash (algorithm, parameters and salt are embedded).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AccountStatus.ACTIVE.value
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def is_active(self) -> bool:
        """Whether the account may authenticate."""
        return self.status == AccountStatus.ACTIVE.value


class AuthSession(Base):
    """A server-side authentication session.

    This is what makes revocation real: every access token carries this
    session's id (`sid`), and every use of an access token re-checks the
    session row. Deleting or revoking the row invalidates outstanding access
    tokens without waiting for them to expire (AUTH-004, AUTH-005).
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    #: SHA-256 of the opaque refresh token. The raw value is returned to the
    #: client once and never stored.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped[User] = relationship(back_populates="sessions")

    def is_usable(self, now: datetime) -> bool:
        """Whether this session may still authorize requests."""
        return self.revoked_at is None and self.expires_at > now
