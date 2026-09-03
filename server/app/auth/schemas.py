"""Request and response models for the authentication API.

Response models are deliberately narrow. A password hash, an internal database
key, `status`, session bookkeeping, or any authentication secret must never
appear in a response body.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.auth.config import AuthConfig
from app.auth.models import User

#: Upper bound on accepted password length. Matches AuthConfig's default and
#: exists so an oversized body is refused before it reaches Argon2.
MAX_PASSWORD_FIELD_LENGTH = 1024


class RegistrationRequest(BaseModel):
    """Registration input."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_FIELD_LENGTH)


class LoginRequest(BaseModel):
    """Login input."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_FIELD_LENGTH)


class DeleteAccountRequest(BaseModel):
    """Account deletion input. Re-authentication is required."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=MAX_PASSWORD_FIELD_LENGTH)


class PublicUser(BaseModel):
    """The only account shape ever returned to a client.

    Contains no password hash, no internal key, no session data.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    username: str
    created_at: datetime

    @classmethod
    def from_model(cls, user: User) -> PublicUser:
        """Project a persistence model onto its safe public shape."""
        return cls(user_id=user.id, username=user.username, created_at=user.created_at)


class AuthenticationResponse(BaseModel):
    """Returned by login and refresh.

    The refresh token is **not** in this body: it is set as an HttpOnly cookie
    so page scripts cannot read it (`AUTH-009`). The access token is returned
    for the client to hold in memory only.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 - scheme name, not a credential
    expires_in: int
    user: PublicUser


class SessionStatus(BaseModel):
    """Describes the caller's current authentication state.

    Reports account authentication only. It deliberately says nothing about
    encryption, because none exists yet.
    """

    model_config = ConfigDict(extra="forbid")

    authenticated: Literal[True] = True
    user: PublicUser
    session_id: str
    encryption_status: Literal["not_implemented"] = "not_implemented"
    identity_verification_status: Literal["not_implemented"] = "not_implemented"


class AuthErrorResponse(BaseModel):
    """A deterministic, non-sensitive authentication error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    detail: str


class PasswordPolicyInfo(BaseModel):
    """Public description of the password policy.

    Safe to expose: it states the rules a client should enforce locally, and
    reveals nothing about any account.
    """

    model_config = ConfigDict(extra="forbid")

    min_password_length: int
    max_password_length: int
    min_username_length: int
    max_username_length: int

    @classmethod
    def from_config(cls, config: AuthConfig) -> PasswordPolicyInfo:
        """Build the policy description from configuration."""
        return cls(
            min_password_length=config.min_password_length,
            max_password_length=config.max_password_length,
            min_username_length=config.min_username_length,
            max_username_length=config.max_username_length,
        )
