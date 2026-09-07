"""Authentication HTTP routes.

Endpoints: register, login, refresh, logout, current session, delete account,
and a public description of the password policy.

The refresh token travels only in an HttpOnly cookie. Access tokens are
returned in the response body and are expected to live in the client's memory,
never in `localStorage` (`AUTH-009`). No token appears in any URL.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.dependencies import (
    REFRESH_COOKIE_NAME,
    AuthServiceDep,
    CurrentIdentity,
    DatabaseSession,
)
from app.auth.errors import AuthError, AuthErrorCode
from app.auth.repository import UserRepository
from app.auth.schemas import (
    AuthenticationResponse,
    DeleteAccountRequest,
    LoginRequest,
    PasswordPolicyInfo,
    PublicUser,
    RegistrationRequest,
    SessionStatus,
)
from app.auth.service import IssuedCredentials

router = APIRouter(prefix="/auth", tags=["authentication"])

#: Per-IP limiter. Complements the per-account failure tracker in
#: `rate_limit.py`; neither alone is sufficient (see that module).
limiter = Limiter(key_func=get_remote_address, default_limits=[])

#: Rate limits, overridable so tests can exercise threshold behaviour.
LOGIN_RATE_LIMIT = os.environ.get("AUTH_LOGIN_RATE_LIMIT", "10/minute")
REGISTER_RATE_LIMIT = os.environ.get("AUTH_REGISTER_RATE_LIMIT", "5/minute")


def _set_refresh_cookie(
    response: Response, credentials: IssuedCredentials, *, secure: bool
) -> None:
    """Attach the refresh token as a restrictive cookie.

    * `httponly` keeps it out of reach of page scripts, so an XSS bug cannot
      exfiltrate the long-lived credential.
    * `samesite="strict"` means a cross-site page cannot trigger a refresh.
    * `secure` is driven by configuration: forcing it on in local HTTP
      development would silently break the cookie, so it is switched by
      `AUTH_COOKIE_SECURE` and must be on in production.
    * `path` scopes the cookie to the auth routes that actually need it.
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=credentials.refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/auth",
        max_age=60 * 60 * 24 * 14,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh cookie."""
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/auth", httponly=True, samesite="strict")


def _cookie_secure() -> bool:
    """Whether the refresh cookie should carry the Secure attribute."""
    return os.environ.get("AUTH_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}


def _authentication_response(credentials: IssuedCredentials) -> AuthenticationResponse:
    """Build the body returned by login and refresh."""
    return AuthenticationResponse(
        access_token=credentials.access_token,
        expires_in=credentials.expires_in_seconds,
        user=PublicUser(
            user_id=credentials.user_id,
            username=credentials.username,
            created_at=credentials.created_at,
        ),
    )


@router.get("/policy", response_model=PasswordPolicyInfo)
async def password_policy(service: AuthServiceDep) -> PasswordPolicyInfo:
    """Describe the password and identifier policy."""
    return PasswordPolicyInfo.from_config(service.config)


@router.post("/register", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
@limiter.limit(REGISTER_RATE_LIMIT)
async def register(
    request: Request,
    payload: RegistrationRequest,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> PublicUser:
    """Create an account.

    `request` is required by the rate limiter even though it is unused here.
    """
    _ = request
    user = await service.register(db, username=payload.username, password=payload.password)
    return PublicUser.from_model(user)


@router.post("/login", response_model=AuthenticationResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> AuthenticationResponse:
    """Authenticate and open a session."""
    _ = request
    credentials = await service.login(db, username=payload.username, password=payload.password)
    _set_refresh_cookie(response, credentials, secure=_cookie_secure())
    return _authentication_response(credentials)


@router.post("/refresh", response_model=AuthenticationResponse)
async def refresh(
    request: Request,
    response: Response,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> AuthenticationResponse:
    """Exchange the refresh cookie for a new access token.

    The refresh token is read only from the HttpOnly cookie, never from a
    query parameter or a JSON body.
    """
    presented = request.cookies.get(REFRESH_COOKIE_NAME)
    if not presented:
        raise AuthError(AuthErrorCode.REQUIRED, internal_reason="missing refresh cookie")

    credentials = await service.refresh(db, presented)
    _set_refresh_cookie(response, credentials, secure=_cookie_secure())
    return _authentication_response(credentials)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    identity: CurrentIdentity,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> Response:
    """Revoke the caller's session server-side."""
    await service.logout(db, identity.session_id)
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/session", response_model=SessionStatus)
async def current_session(
    identity: CurrentIdentity,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> SessionStatus:
    """Report the caller's authentication state."""
    _ = service
    user = await UserRepository(db).get_by_id(identity.user_id)
    if user is None:
        raise AuthError(AuthErrorCode.SESSION_REVOKED, internal_reason="account vanished")
    return SessionStatus(user=PublicUser.from_model(user), session_id=identity.session_id)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    response: Response,
    payload: DeleteAccountRequest,
    identity: CurrentIdentity,
    db: DatabaseSession,
    service: AuthServiceDep,
) -> Response:
    """Delete the caller's own account.

    Only ever the caller's own: the target is taken from the authenticated
    identity, so there is no user-supplied identifier to tamper with and no
    way to address someone else's account.
    """
    _ = response
    await service.delete_account(db, identity=identity, password=payload.password)
    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(result)
    return result


__all__ = ["limiter", "router"]
