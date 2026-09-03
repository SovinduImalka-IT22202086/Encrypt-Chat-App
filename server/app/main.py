"""Minimal FastAPI application used to prove the Phase 1 development environment.

SCOPE WARNING
-------------
This module exists only to demonstrate that imports, the ASGI application,
linting, type checking, and pytest all work in a clean environment. It
deliberately implements no Phase 2+ functionality:

* no WebSocket transport or message routing;
* no registration, login, sessions, or tokens;
* no password hashing;
* no cryptographic identity, key agreement, or message encryption.

The single endpoint below returns non-sensitive static development
information only. Per docs/SECURITY_REQUIREMENTS.md (SERVER-008), health
endpoints must not expose sensitive configuration or internal diagnostics.
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__

app = FastAPI(
    title="Encrypted Chat Application (development scaffold)",
    version=__version__,
    description=(
        "Phase 1 development scaffold. No encrypted messaging, authentication, "
        "or cryptographic functionality is implemented."
    ),
)


class HealthResponse(BaseModel):
    """Non-sensitive health payload.

    Intentionally excludes configuration, environment variables, dependency
    versions, and any internal diagnostic detail (SERVER-008).
    """

    status: Literal["ok"]
    phase: Literal["1"]
    encrypted_messaging: Literal["not_implemented"]


@app.get("/health")
async def health() -> HealthResponse:
    """Return a static development health response."""
    return HealthResponse(
        status="ok",
        phase="1",
        encrypted_messaging="not_implemented",
    )
