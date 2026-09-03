"""Authentication configuration.

Every security-relevant value is read from the environment. There is no
hardcoded signing secret and no fallback constant: if `AUTH_SIGNING_SECRET` is
absent, a random per-process secret is generated so the application still runs
in development, but every previously issued token becomes invalid on restart.
That is deliberate - a predictable default secret is a far worse failure than
an inconvenient one (AUTH-008, DEPLOY-002).
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass

logger = logging.getLogger("app.auth")

#: Minimum acceptable length for a configured signing secret.
MIN_SIGNING_SECRET_LENGTH = 32


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    """Read a bounded integer from the environment."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _load_signing_secret() -> str:
    """Return the JWT signing secret, generating an ephemeral one if unset."""
    configured = os.environ.get("AUTH_SIGNING_SECRET", "").strip()
    if not configured:
        logger.warning(
            "auth_signing_secret_missing",
            extra={
                "auth": {
                    "event": "auth_signing_secret_missing",
                    "detail": (
                        "AUTH_SIGNING_SECRET is not set; generated an ephemeral "
                        "per-process secret. All sessions become invalid on restart. "
                        "Set it explicitly outside development."
                    ),
                }
            },
        )
        return secrets.token_urlsafe(64)

    if len(configured) < MIN_SIGNING_SECRET_LENGTH:
        logger.warning(
            "auth_signing_secret_weak",
            extra={
                "auth": {
                    "event": "auth_signing_secret_weak",
                    "minimum_length": MIN_SIGNING_SECRET_LENGTH,
                }
            },
        )
    return configured


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Authentication settings.

    The signing secret is excluded from `repr` so it cannot leak into a log
    line, an exception trace, or a debugger dump.
    """

    signing_secret: str
    algorithm: str = "HS256"
    issuer: str = "encrypted-chat-app"
    audience: str = "encrypted-chat-app-client"

    # --- Lifetimes ---------------------------------------------------------
    # Access tokens are deliberately short-lived: they are bearer credentials
    # and are only revocable via the session lookup performed on every use.
    access_token_ttl_minutes: int = 15
    refresh_session_ttl_days: int = 14

    # --- Password policy ---------------------------------------------------
    # Long passphrases are allowed and never truncated; the upper bound only
    # exists to stop an attacker forcing unbounded Argon2 work.
    min_password_length: int = 12
    max_password_length: int = 1024

    # --- Identifier policy -------------------------------------------------
    min_username_length: int = 3
    max_username_length: int = 32

    # --- Brute-force controls ---------------------------------------------
    # Per-IP limits are applied by slowapi; these bound repeated failures
    # against a single account from any source.
    max_failed_logins_per_account: int = 10
    failed_login_window_seconds: float = 300.0

    # --- Argon2id parameters ----------------------------------------------
    # Chosen for development. DECISION-005 in SECURITY_ASSUMPTIONS.md requires
    # these to be re-tuned against real deployment hardware before production.
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 4

    def __repr__(self) -> str:
        """Never render the signing secret."""
        return (
            f"AuthConfig(algorithm={self.algorithm!r}, issuer={self.issuer!r}, "
            f"audience={self.audience!r}, "
            f"access_token_ttl_minutes={self.access_token_ttl_minutes}, "
            f"refresh_session_ttl_days={self.refresh_session_ttl_days}, "
            "signing_secret=<redacted>)"
        )


def default_auth_config() -> AuthConfig:
    """Build authentication configuration from the environment."""
    return AuthConfig(
        signing_secret=_load_signing_secret(),
        access_token_ttl_minutes=_int_env("ACCESS_TOKEN_TTL_MINUTES", 15),
        refresh_session_ttl_days=_int_env("REFRESH_SESSION_TTL_DAYS", 14),
        min_password_length=_int_env("AUTH_MIN_PASSWORD_LENGTH", 12, minimum=8),
        max_failed_logins_per_account=_int_env("AUTH_MAX_FAILED_LOGINS", 10),
        failed_login_window_seconds=float(_int_env("AUTH_FAILED_LOGIN_WINDOW_SECONDS", 300)),
        argon2_time_cost=_int_env("ARGON2_TIME_COST", 3),
        argon2_memory_cost_kib=_int_env("ARGON2_MEMORY_COST_KIB", 65536),
        argon2_parallelism=_int_env("ARGON2_PARALLELISM", 4),
    )
