"""FastAPI application for the Encrypted Chat Application.

SCOPE WARNING
-------------
Phase 2 implements the WebSocket **transport** layer only. It deliberately
implements none of the following:

* no registration, login, sessions, or tokens;
* no password hashing;
* no cryptographic identity, key agreement, or message encryption;
* no ratcheting or cryptographic replay protection;
* no durable message persistence.

Connections carry a TRANSPORT_TEST_IDENTITY and are NOT_AUTHENTICATED. See
docs/WEBSOCKET_PROTOCOL.md for the protocol and its current limitations.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__
from app.websocket import ConnectionManager, TransportLimits, default_limits
from app.websocket import router as websocket_router


class HealthResponse(BaseModel):
    """Non-sensitive health payload.

    Intentionally excludes configuration, environment variables, dependency
    versions, and any internal diagnostic detail (SERVER-008).
    """

    status: Literal["ok"]
    phase: Literal["2"]
    encrypted_messaging: Literal["not_implemented"]


async def health() -> HealthResponse:
    """Return a static development health response."""
    return HealthResponse(
        status="ok",
        phase="2",
        encrypted_messaging="not_implemented",
    )


def create_app(limits: TransportLimits | None = None) -> FastAPI:
    """Build an application instance.

    `limits` is injectable so tests can exercise boundary behaviour with small
    limits without mutating global state or environment variables.
    """
    resolved = default_limits() if limits is None else limits

    @asynccontextmanager
    async def lifespan(instance: FastAPI) -> AsyncIterator[None]:
        """Own the connection manager for the application's lifetime.

        Held on `app.state` rather than in a module-level global so each
        application instance has isolated transport state.
        """
        instance.state.ws_manager = ConnectionManager(resolved)
        try:
            yield
        finally:
            instance.state.ws_manager.reset()

    instance = FastAPI(
        title="Encrypted Chat Application (development scaffold)",
        version=__version__,
        description=(
            "Phase 2 WebSocket transport scaffold. No authentication, cryptographic "
            "identity, or end-to-end encryption is implemented."
        ),
        lifespan=lifespan,
    )
    instance.include_router(websocket_router)
    instance.get("/health")(health)
    return instance


app = create_app()
