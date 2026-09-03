"""FastAPI application for the Encrypted Chat Application.

SCOPE WARNING
-------------
Phase 3 adds **account authentication**. It does not add cryptography:

* no cryptographic identity keys (Phase 4);
* no identity verification or safety numbers (Phase 4);
* no key agreement (Phase 5);
* no end-to-end encryption (Phase 6);
* no ratcheting or cryptographic replay protection (Phase 7).

An authenticated account is NOT a cryptographically verified conversation
identity, and message payloads remain readable by the relay. See
docs/AUTHENTICATION.md and docs/WEBSOCKET_PROTOCOL.md.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.auth import AuthConfig, AuthError, AuthErrorCode, AuthService, default_auth_config
from app.auth import limiter as auth_limiter
from app.auth import router as auth_router
from app.auth.errors import describe as describe_auth_error
from app.db import create_engine, create_schema, create_session_factory
from app.websocket import ConnectionManager, TransportLimits, default_limits
from app.websocket import router as websocket_router


class HealthResponse(BaseModel):
    """Non-sensitive health payload.

    Intentionally excludes configuration, environment variables, dependency
    versions, and any internal diagnostic detail (SERVER-008).
    """

    status: Literal["ok"]
    phase: Literal["3"]
    authentication: Literal["implemented"]
    encrypted_messaging: Literal["not_implemented"]


async def health() -> HealthResponse:
    """Return a static development health response."""
    return HealthResponse(
        status="ok",
        phase="3",
        authentication="implemented",
        encrypted_messaging="not_implemented",
    )


async def _auth_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render an `AuthError` as a deterministic, non-sensitive response.

    Only the stable code and its fixed description are returned. The internal
    reason stays server-side, so a client cannot tell "no such account" from
    "wrong password" (`AUTH-007`).
    """
    _ = request
    if not isinstance(exc, AuthError):  # pragma: no cover - defensive
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code.value, "detail": exc.detail},
    )


async def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render a slowapi rate-limit rejection in the authentication error shape."""
    _ = request, exc
    return JSONResponse(
        status_code=429,
        content={
            "code": AuthErrorCode.RATE_LIMITED.value,
            "detail": describe_auth_error(AuthErrorCode.RATE_LIMITED),
        },
    )


def create_app(
    limits: TransportLimits | None = None,
    *,
    auth_config: AuthConfig | None = None,
    database_url: str | None = None,
) -> FastAPI:
    """Build an application instance.

    Limits, authentication configuration, and the database URL are injectable
    so tests can exercise boundary behaviour with an isolated database and
    small limits, without mutating global state.
    """
    resolved_limits = default_limits() if limits is None else limits
    resolved_auth = default_auth_config() if auth_config is None else auth_config

    @asynccontextmanager
    async def lifespan(instance: FastAPI) -> AsyncIterator[None]:
        """Own transport, authentication and database state for the app's life."""
        engine: AsyncEngine = create_engine(database_url)
        await create_schema(engine)

        instance.state.db_engine = engine
        instance.state.session_factory = create_session_factory(engine)
        instance.state.auth_service = AuthService(resolved_auth)
        instance.state.ws_manager = ConnectionManager(resolved_limits)
        try:
            yield
        finally:
            instance.state.ws_manager.reset()
            await engine.dispose()

    instance = FastAPI(
        title="Encrypted Chat Application (development)",
        version=__version__,
        description=(
            "Phase 3: account authentication and authorized WebSocket transport. "
            "No cryptographic identity, key agreement, or end-to-end encryption "
            "is implemented."
        ),
        lifespan=lifespan,
    )

    instance.state.limiter = auth_limiter
    instance.add_middleware(SlowAPIMiddleware)
    instance.add_exception_handler(AuthError, _auth_error_handler)
    instance.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    instance.include_router(auth_router)
    instance.include_router(websocket_router)
    instance.get("/health")(health)
    return instance


app = create_app()
