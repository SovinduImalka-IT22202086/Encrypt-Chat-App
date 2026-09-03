"""JWT access tokens and opaque refresh tokens.

Access tokens are signed JWTs (HS256) carrying only minimal claims. Refresh
tokens are opaque random strings; only their SHA-256 hash reaches storage.

A signed JWT is readable by anyone holding it - signing proves integrity, not
confidentiality. Nothing secret goes in a claim (`AUTH-008`).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

import jwt

from app.auth.config import AuthConfig
from app.auth.errors import AuthError, AuthErrorCode

#: Bytes of entropy in an opaque refresh token.
REFRESH_TOKEN_BYTES = 32


class TokenType(StrEnum):
    """Token kinds. Presenting the wrong kind is rejected."""

    ACCESS = "access"


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated claims from an access token."""

    user_id: str
    session_id: str
    token_id: str
    issued_at: datetime
    expires_at: datetime


class TokenService:
    """Issues and validates authentication tokens."""

    __slots__ = ("_config",)

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    # --- Access tokens -----------------------------------------------------

    def issue_access_token(
        self, user_id: str, session_id: str, *, now: datetime | None = None
    ) -> str:
        """Mint a short-lived access token bound to a server-side session.

        `sid` is what makes revocation possible: every use re-checks that
        session, so revoking it invalidates outstanding tokens immediately.
        """
        issued_at = now if now is not None else datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=self._config.access_token_ttl_minutes)

        claims: dict[str, Any] = {
            "sub": user_id,
            "sid": session_id,
            "jti": uuid4().hex,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": self._config.issuer,
            "aud": self._config.audience,
            "token_type": TokenType.ACCESS.value,
        }
        return jwt.encode(claims, self._config.signing_secret, algorithm=self._config.algorithm)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        """Validate an access token and return its claims.

        Raises `AuthError` with a distinct code for expiry versus every other
        failure. Expiry is separated deliberately: it is an ordinary, benign
        condition a client should respond to by refreshing, whereas anything
        else is indistinguishable from tampering and gets one generic code.
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._config.signing_secret,
                algorithms=[self._config.algorithm],
                issuer=self._config.issuer,
                audience=self._config.audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError(
                AuthErrorCode.TOKEN_EXPIRED, internal_reason="access token expired"
            ) from exc
        except jwt.InvalidTokenError as exc:
            # Covers bad signature, wrong algorithm, wrong issuer/audience,
            # malformed structure, and missing required claims. The client is
            # told only that the token is invalid.
            raise AuthError(
                AuthErrorCode.TOKEN_INVALID, internal_reason=f"invalid token: {type(exc).__name__}"
            ) from exc

        if payload.get("token_type") != TokenType.ACCESS.value:
            raise AuthError(
                AuthErrorCode.TOKEN_INVALID, internal_reason="wrong token type presented"
            )

        user_id = payload.get("sub")
        session_id = payload.get("sid")
        token_id = payload.get("jti")
        if not (
            isinstance(user_id, str) and isinstance(session_id, str) and isinstance(token_id, str)
        ):
            raise AuthError(AuthErrorCode.TOKEN_INVALID, internal_reason="token claims malformed")

        return AccessTokenClaims(
            user_id=user_id,
            session_id=session_id,
            token_id=token_id,
            issued_at=datetime.fromtimestamp(int(payload["iat"]), tz=UTC),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
        )

    # --- Refresh tokens ----------------------------------------------------

    @staticmethod
    def generate_refresh_token() -> str:
        """Create an opaque, high-entropy refresh token."""
        return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        """Hash a refresh token for storage.

        SHA-256 without a salt is correct here, unlike for passwords: the input
        is 256 bits of uniform randomness, so there is nothing to brute-force
        and no dictionary to defend against. The hash exists so a database
        dump yields no usable credential.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def refresh_expiry(self, *, now: datetime | None = None) -> datetime:
        """When a newly created refresh session should expire."""
        issued_at = now if now is not None else datetime.now(UTC)
        return issued_at + timedelta(days=self._config.refresh_session_ttl_days)
