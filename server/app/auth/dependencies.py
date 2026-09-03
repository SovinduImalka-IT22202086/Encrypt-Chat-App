"""Reusable authentication dependencies.

Route handlers never re-implement token validation. They depend on
`get_current_identity`, which performs the full sequence in one place:
extract, validate signature, check expiry, check token type, check revocation,
resolve the account, and fail closed on anything unexpected.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.errors import AuthError, AuthErrorCode
from app.auth.service import AuthenticatedIdentity, AuthService

#: Name of the HttpOnly cookie carrying the opaque refresh token.
REFRESH_COOKIE_NAME = "ecapp_refresh"


def get_auth_service(request: Request) -> AuthService:
    """Return the application's authentication service."""
    service: AuthService = request.app.state.auth_service
    return service


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a transactional database session for one request."""
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def extract_bearer_token(request: Request) -> str:
    """Read the access token from the Authorization header.

    Header-only by design. Accepting a token from the query string would leak
    it into server logs, browser history, proxies and referrers, so no such
    fallback exists (`AUTH-008`).
    """
    header = request.headers.get("authorization")
    if not header:
        raise AuthError(AuthErrorCode.REQUIRED, internal_reason="missing Authorization header")

    scheme, _, credential = header.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise AuthError(AuthErrorCode.REQUIRED, internal_reason="malformed Authorization header")
    return credential.strip()


async def get_current_identity(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedIdentity:
    """Resolve and verify the caller's authenticated identity."""
    token = extract_bearer_token(request)
    return await service.resolve_access_token(db, token)


CurrentIdentity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
