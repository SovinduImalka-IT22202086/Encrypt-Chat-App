"""Authentication business logic.

Holds the security decisions in one auditable place: registration, login,
refresh, logout, account deletion, and the validation of an access token
against live server-side session state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.config import AuthConfig
from app.auth.errors import AuthError, AuthErrorCode
from app.auth.identifiers import InvalidUsernameError, validate_username
from app.auth.models import AuthSession, User
from app.auth.password import PasswordHashing, PasswordPolicyError
from app.auth.rate_limit import FailedLoginTracker
from app.auth.repository import SessionRepository, UsernameTakenError, UserRepository
from app.auth.tokens import TokenService

logger = logging.getLogger("app.auth")


def _log(event: str, **fields: object) -> None:
    """Emit a structured authentication event.

    Passwords, Authorization headers, raw access tokens, raw refresh tokens,
    and password hashes are never passed here (`LOG-002`).
    """
    record: dict[str, object] = {"event": event}
    record.update(fields)
    logger.info(event, extra={"auth": record})


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    """A verified account identity resolved from an access token."""

    user_id: str
    username: str
    session_id: str


@dataclass(frozen=True, slots=True)
class IssuedCredentials:
    """Credentials returned after a successful login or refresh."""

    access_token: str
    refresh_token: str
    expires_in_seconds: int
    user_id: str
    username: str
    created_at: datetime
    session_id: str


class AuthService:
    """Coordinates account and session operations."""

    __slots__ = ("_config", "_failed_logins", "_passwords", "_tokens")

    def __init__(
        self,
        config: AuthConfig,
        *,
        failed_logins: FailedLoginTracker | None = None,
    ) -> None:
        self._config = config
        self._passwords = PasswordHashing(config)
        self._tokens = TokenService(config)
        self._failed_logins = failed_logins or FailedLoginTracker(
            max_failures=config.max_failed_logins_per_account,
            window_seconds=config.failed_login_window_seconds,
        )

    @property
    def passwords(self) -> PasswordHashing:
        """The password hashing helper."""
        return self._passwords

    @property
    def tokens(self) -> TokenService:
        """The token helper."""
        return self._tokens

    @property
    def failed_logins(self) -> FailedLoginTracker:
        """The per-account failure tracker."""
        return self._failed_logins

    @property
    def config(self) -> AuthConfig:
        """Authentication configuration."""
        return self._config

    # --- Registration ------------------------------------------------------

    async def register(self, db: AsyncSession, *, username: str, password: str) -> User:
        """Create an account.

        Every failure returns the same external code so registration cannot be
        used to probe which identifiers exist (`AUTH-007`).
        """
        try:
            normalized = validate_username(username)
        except InvalidUsernameError as exc:
            raise AuthError(
                AuthErrorCode.VALIDATION_FAILED,
                status_code=400,
                internal_reason=f"invalid username: {exc.reason}",
            ) from exc

        try:
            self._passwords.validate_policy(password)
        except PasswordPolicyError as exc:
            raise AuthError(
                AuthErrorCode.VALIDATION_FAILED,
                status_code=400,
                internal_reason=f"invalid password: {exc.reason}",
            ) from exc

        password_hash = self._passwords.hash(password)
        now = datetime.now(UTC)
        users = UserRepository(db)

        try:
            user = await users.create(
                user_id=uuid4().hex,
                username=username.strip(),
                username_normalized=normalized,
                password_hash=password_hash,
                now=now,
            )
        except UsernameTakenError as exc:
            _log("registration_rejected", reason="identifier_taken")
            raise AuthError(
                AuthErrorCode.REGISTRATION_REJECTED,
                status_code=409,
                internal_reason="identifier already registered",
            ) from exc

        _log("registration_success", user_id=user.id)
        return user

    # --- Login -------------------------------------------------------------

    async def login(self, db: AsyncSession, *, username: str, password: str) -> IssuedCredentials:
        """Authenticate and open a session.

        Unknown account, wrong password, and disabled account all produce the
        same external `AUTH_INVALID_CREDENTIALS`. The unknown-account path also
        performs a dummy Argon2 verification so it does the same work as a real
        one (`AUTH-007`).
        """
        try:
            normalized = validate_username(username)
        except InvalidUsernameError:
            # Still pay the hashing cost: skipping it would make malformed
            # identifiers instantly distinguishable from real ones.
            self._passwords.dummy_verify()
            raise AuthError(
                AuthErrorCode.INVALID_CREDENTIALS, internal_reason="malformed identifier"
            ) from None

        if self._failed_logins.is_blocked(normalized):
            _log("authentication_rate_limited", scope="account")
            raise AuthError(
                AuthErrorCode.RATE_LIMITED,
                status_code=429,
                internal_reason="per-account failure threshold reached",
            )

        users = UserRepository(db)
        user = await users.get_by_normalized_username(normalized)

        if user is None:
            self._passwords.dummy_verify()
            self._failed_logins.record_failure(normalized)
            _log("authentication_failure", reason="unknown_account")
            raise AuthError(AuthErrorCode.INVALID_CREDENTIALS, internal_reason="unknown account")

        if not self._passwords.verify(user.password_hash, password):
            self._failed_logins.record_failure(normalized)
            _log("authentication_failure", reason="password_mismatch", user_id=user.id)
            raise AuthError(AuthErrorCode.INVALID_CREDENTIALS, internal_reason="password mismatch")

        if not user.is_active:
            self._failed_logins.record_failure(normalized)
            _log("authentication_failure", reason="account_disabled", user_id=user.id)
            raise AuthError(AuthErrorCode.INVALID_CREDENTIALS, internal_reason="account disabled")

        # Opportunistic upgrade when Argon2 parameters change (AUTH-PASS-006).
        if self._passwords.needs_rehash(user.password_hash):
            user.password_hash = self._passwords.hash(password)
            user.updated_at = datetime.now(UTC)
            _log("password_rehashed", user_id=user.id)

        self._failed_logins.reset(normalized)
        credentials = await self._open_session(db, user)
        _log("authentication_success", user_id=user.id, session_id=credentials.session_id)
        return credentials

    async def _open_session(self, db: AsyncSession, user: User) -> IssuedCredentials:
        """Create a session and mint the credential pair."""
        now = datetime.now(UTC)
        session_id = uuid4().hex
        refresh_token = self._tokens.generate_refresh_token()

        await SessionRepository(db).create(
            session_id=session_id,
            user_id=user.id,
            refresh_token_hash=self._tokens.hash_refresh_token(refresh_token),
            now=now,
            expires_at=self._tokens.refresh_expiry(now=now),
        )
        _log("session_created", user_id=user.id, session_id=session_id)

        return IssuedCredentials(
            access_token=self._tokens.issue_access_token(user.id, session_id, now=now),
            refresh_token=refresh_token,
            expires_in_seconds=self._config.access_token_ttl_minutes * 60,
            user_id=user.id,
            username=user.username,
            created_at=user.created_at,
            session_id=session_id,
        )

    # --- Access-token validation ------------------------------------------

    async def resolve_access_token(self, db: AsyncSession, token: str) -> AuthenticatedIdentity:
        """Validate an access token against live session state.

        Signature and expiry alone are not enough: the session row is
        re-checked on every use, which is what gives logout and account
        deletion immediate effect rather than waiting out the token TTL.
        """
        claims = self._tokens.decode_access_token(token)
        now = datetime.now(UTC)

        auth_session = await SessionRepository(db).get(claims.session_id)
        if auth_session is None:
            raise AuthError(
                AuthErrorCode.SESSION_REVOKED, internal_reason="session no longer exists"
            )
        if not auth_session.is_usable(now):
            reason = "session revoked" if auth_session.revoked_at else "session expired"
            raise AuthError(AuthErrorCode.SESSION_REVOKED, internal_reason=reason)

        user = await UserRepository(db).get_by_id(claims.user_id)
        if user is None:
            raise AuthError(
                AuthErrorCode.SESSION_REVOKED, internal_reason="account no longer exists"
            )
        if not user.is_active:
            raise AuthError(
                AuthErrorCode.ACCOUNT_UNAVAILABLE,
                status_code=403,
                internal_reason="account disabled",
            )
        if auth_session.user_id != user.id:
            raise AuthError(AuthErrorCode.TOKEN_INVALID, internal_reason="session/user mismatch")

        return AuthenticatedIdentity(
            user_id=user.id, username=user.username, session_id=auth_session.id
        )

    # --- Refresh -----------------------------------------------------------

    async def refresh(self, db: AsyncSession, refresh_token: str) -> IssuedCredentials:
        """Exchange a refresh token for a new credential pair.

        The refresh token is rotated, so the presented one stops working
        immediately after a successful refresh.
        """
        token_hash = self._tokens.hash_refresh_token(refresh_token)
        sessions = SessionRepository(db)
        auth_session = await sessions.get_by_refresh_hash(token_hash)
        now = datetime.now(UTC)

        if auth_session is None:
            raise AuthError(
                AuthErrorCode.SESSION_REVOKED, internal_reason="refresh token not recognized"
            )
        if not auth_session.is_usable(now):
            reason = "session revoked" if auth_session.revoked_at else "session expired"
            raise AuthError(AuthErrorCode.SESSION_REVOKED, internal_reason=reason)

        user = await UserRepository(db).get_by_id(auth_session.user_id)
        if user is None or not user.is_active:
            raise AuthError(AuthErrorCode.SESSION_REVOKED, internal_reason="account unavailable")

        new_refresh = self._tokens.generate_refresh_token()
        await sessions.rotate_refresh_token(
            auth_session,
            refresh_token_hash=self._tokens.hash_refresh_token(new_refresh),
            expires_at=self._tokens.refresh_expiry(now=now),
        )
        _log("session_refreshed", user_id=user.id, session_id=auth_session.id)

        return IssuedCredentials(
            access_token=self._tokens.issue_access_token(user.id, auth_session.id, now=now),
            refresh_token=new_refresh,
            expires_in_seconds=self._config.access_token_ttl_minutes * 60,
            user_id=user.id,
            username=user.username,
            created_at=user.created_at,
            session_id=auth_session.id,
        )

    # --- Logout and deletion ----------------------------------------------

    async def logout(self, db: AsyncSession, session_id: str) -> None:
        """Revoke one session server-side.

        This is real revocation, not a client-side token discard: the session
        row is marked revoked and every subsequent access-token validation
        fails against it.
        """
        sessions = SessionRepository(db)
        auth_session: AuthSession | None = await sessions.get(session_id)
        if auth_session is None:
            return
        await sessions.revoke(auth_session, datetime.now(UTC))
        _log("session_revoked", session_id=session_id, user_id=auth_session.user_id)
        _log("logout", session_id=session_id, user_id=auth_session.user_id)

    async def delete_account(
        self, db: AsyncSession, *, identity: AuthenticatedIdentity, password: str
    ) -> None:
        """Delete the caller's own account after re-authentication.

        Deletion requires the current password even though the caller is
        already authenticated: a stolen access token alone must not be enough
        to destroy an account.
        """
        users = UserRepository(db)
        user = await users.get_by_id(identity.user_id)
        if user is None:
            raise AuthError(
                AuthErrorCode.SESSION_REVOKED, internal_reason="account no longer exists"
            )

        if not self._passwords.verify(user.password_hash, password):
            _log("account_deletion_rejected", reason="reauthentication_failed", user_id=user.id)
            raise AuthError(
                AuthErrorCode.INVALID_CREDENTIALS, internal_reason="re-authentication failed"
            )

        revoked = await SessionRepository(db).revoke_all_for_user(user.id, datetime.now(UTC))
        await users.delete(user)
        _log("account_deleted", user_id=user.id, sessions_revoked=revoked)
