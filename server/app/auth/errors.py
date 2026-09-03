"""Deterministic, non-sensitive authentication error codes.

External codes never distinguish "no such account" from "wrong password"
(AUTH-007, anti-enumeration). Internal reasons are logged separately so
operators keep the diagnostic detail that users must not receive.
"""

from __future__ import annotations

from enum import StrEnum


class AuthErrorCode(StrEnum):
    """Codes returned to clients."""

    INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    REQUIRED = "AUTH_REQUIRED"
    TOKEN_INVALID = "AUTH_TOKEN_INVALID"  # noqa: S105 - error code, not a credential
    TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"  # noqa: S105 - error code, not a credential
    SESSION_REVOKED = "AUTH_SESSION_REVOKED"
    RATE_LIMITED = "AUTH_RATE_LIMITED"
    ACCOUNT_UNAVAILABLE = "AUTH_ACCOUNT_UNAVAILABLE"
    REGISTRATION_REJECTED = "AUTH_REGISTRATION_REJECTED"
    VALIDATION_FAILED = "AUTH_VALIDATION_FAILED"


#: Fixed, non-sensitive descriptions. No database errors, no library stack
#: traces, no Argon2 internals, no token signature details.
AUTH_ERROR_DESCRIPTIONS: dict[AuthErrorCode, str] = {
    AuthErrorCode.INVALID_CREDENTIALS: "Invalid credentials.",
    AuthErrorCode.REQUIRED: "Authentication required.",
    AuthErrorCode.TOKEN_INVALID: "Authentication token is not valid.",
    AuthErrorCode.TOKEN_EXPIRED: "Authentication token has expired.",
    AuthErrorCode.SESSION_REVOKED: "Session is no longer valid.",
    AuthErrorCode.RATE_LIMITED: "Too many attempts. Try again later.",
    AuthErrorCode.ACCOUNT_UNAVAILABLE: "Account is not available.",
    AuthErrorCode.REGISTRATION_REJECTED: "Registration could not be completed.",
    AuthErrorCode.VALIDATION_FAILED: "Request failed validation.",
}


class AuthError(Exception):
    """An authentication failure with a safe external code.

    `internal_reason` is for logs only and is never serialized to a client.
    """

    def __init__(
        self,
        code: AuthErrorCode,
        *,
        status_code: int = 401,
        internal_reason: str | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = status_code
        self.internal_reason = internal_reason

    @property
    def detail(self) -> str:
        """The fixed, non-sensitive description for this code."""
        return AUTH_ERROR_DESCRIPTIONS[self.code]


def describe(code: AuthErrorCode) -> str:
    """Return the non-sensitive description for an authentication code."""
    return AUTH_ERROR_DESCRIPTIONS[code]
