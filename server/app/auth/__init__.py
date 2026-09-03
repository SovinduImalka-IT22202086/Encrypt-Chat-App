"""Authentication and account security (Phase 3).

Provides account registration, Argon2id password storage, login, short-lived
access tokens bound to server-side sessions, refresh with rotation, real
server-side revocation, brute-force controls, anti-enumeration behaviour,
account deletion, and authenticated WebSocket authorization.

PHASE 3 BOUNDARY
----------------
This layer proves **account/session identity**. It does NOT provide
cryptographic conversation identity. An authenticated user is not a
cryptographically verified conversation partner:

CRYPTOGRAPHIC IDENTITY:      NOT IMPLEMENTED - Phase 4.
IDENTITY VERIFICATION:       NOT IMPLEMENTED - Phase 4.
AUTHENTICATED KEY AGREEMENT: NOT IMPLEMENTED - Phase 5.
END-TO-END ENCRYPTION:       NOT IMPLEMENTED - Phase 6.
FORWARD-SECRECY RATCHET:     NOT IMPLEMENTED - Phase 7.
"""

from app.auth.config import AuthConfig, default_auth_config
from app.auth.errors import AuthError, AuthErrorCode
from app.auth.rate_limit import FailedLoginTracker
from app.auth.routes import limiter, router
from app.auth.service import AuthenticatedIdentity, AuthService, IssuedCredentials

__all__ = [
    "AuthConfig",
    "AuthError",
    "AuthErrorCode",
    "AuthService",
    "AuthenticatedIdentity",
    "FailedLoginTracker",
    "IssuedCredentials",
    "default_auth_config",
    "limiter",
    "router",
]
