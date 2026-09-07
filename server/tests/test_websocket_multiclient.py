"""Multi-client transport test against a real uvicorn server.

Unlike the other suites, these drive an actual network socket with the
`websockets` client rather than the in-process TestClient, so the ASGI server,
the WebSocket handshake, and real framing are all exercised.

SCOPE: this measures transport reliability and cleanup, not throughput. The
numbers here are a correctness signal on one machine and must NOT be read as a
scalability or performance claim.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import uvicorn
from fastapi import FastAPI
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Origin

from app.main import create_app
from app.websocket import WEBSOCKET_PATH, TransportLimits

ALLOWED_ORIGIN = Origin("http://localhost:5173")
_STARTUP_TIMEOUT_SECONDS = 10.0


@asynccontextmanager
async def running_server(
    limits: TransportLimits | None = None,
) -> AsyncIterator[tuple[int, FastAPI]]:
    """Run the app on an ephemeral port, yielding the port and the app.

    The app is yielded so tests can assert on real server-side state (the
    connection registry) rather than only on what a client can observe.
    """
    application = create_app(limits)
    config = uvicorn.Config(
        application,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    deadline = asyncio.get_running_loop().time() + _STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if asyncio.get_running_loop().time() > deadline:
            server.should_exit = True
            await task
            msg = "uvicorn did not start within the timeout"
            raise RuntimeError(msg)
        await asyncio.sleep(0.02)

    port: int = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield port, application
    finally:
        server.should_exit = True
        await task


def _url(port: int, client_id: str) -> str:
    """Build a real ws:// URL for a transport identity."""
    return f"ws://127.0.0.1:{port}{WEBSOCKET_PATH}?client_id={client_id}"


def _envelope(sender: str, recipient: str, payload: dict[str, Any]) -> str:
    """Serialize a valid message.send envelope."""
    return json.dumps(
        {
            "version": "1",
            "message_id": str(uuid4()),
            "type": "message.send",
            "sender": sender,
            "recipient": recipient,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "payload": payload,
        }
    )


@pytest.mark.asyncio
async def test_many_clients_connect_and_route_over_a_real_socket() -> None:
    """20 clients connect over real sockets and exchange messages in pairs."""
    client_count = 20
    async with running_server() as (port, _application):
        sockets = [
            await connect(_url(port, f"client-{index}"), origin=ALLOWED_ORIGIN)
            for index in range(client_count)
        ]
        try:
            ready = [json.loads(await socket.recv()) for socket in sockets]
            assert all(message["type"] == "connection.ready" for message in ready)
            assert all(message["authenticated"] is False for message in ready)
            assert len({message["connection_id"] for message in ready}) == client_count

            # Pair up: even index sends to the following odd index.
            for index in range(0, client_count, 2):
                await sockets[index].send(
                    _envelope(f"client-{index}", f"client-{index + 1}", {"n": index})
                )

            delivered = 0
            acked = 0
            for index in range(0, client_count, 2):
                receipt = json.loads(await asyncio.wait_for(sockets[index + 1].recv(), 5))
                ack = json.loads(await asyncio.wait_for(sockets[index].recv(), 5))

                assert receipt["type"] == "message.receipt"
                assert receipt["sender"] == f"client-{index}"
                assert receipt["payload"] == {"n": index}
                assert ack["status"] == "delivered"
                delivered += 1
                acked += 1

            assert delivered == client_count // 2
            assert acked == client_count // 2
        finally:
            for socket in sockets:
                await socket.close()


@pytest.mark.asyncio
async def test_real_socket_disconnect_cleans_up_server_state() -> None:
    """After every real client disconnects, the registry drains to zero."""
    async with running_server() as (port, application):
        manager = application.state.ws_manager
        sockets = [
            await connect(_url(port, f"client-{index}"), origin=ALLOWED_ORIGIN)
            for index in range(8)
        ]
        for socket in sockets:
            await socket.recv()
        assert manager.connection_count == 8

        for socket in sockets:
            await socket.close()

        # Wait for the server loop to observe each close, then assert the
        # registry actually drained rather than assuming it did.
        for _ in range(100):
            if manager.connection_count == 0:
                break
            await asyncio.sleep(0.02)

        assert manager.connection_count == 0
        assert manager.client_count == 0


@pytest.mark.asyncio
async def test_unauthorized_origin_is_rejected_over_a_real_handshake() -> None:
    """Assertion C at the network level: the HTTP upgrade itself is refused."""
    async with running_server() as (port, _application):
        with pytest.raises(InvalidStatus) as excinfo:
            await connect(_url(port, "attacker"), origin=Origin("http://malicious.example"))

    assert excinfo.value.response.status_code == 403


@pytest.mark.asyncio
async def test_no_broadcast_over_real_sockets() -> None:
    """Assertion A at the network level: C never sees an A->B message."""
    async with running_server() as (port, _application):
        socket_a = await connect(_url(port, "alice"), origin=ALLOWED_ORIGIN)
        socket_b = await connect(_url(port, "bob"), origin=ALLOWED_ORIGIN)
        socket_c = await connect(_url(port, "carol"), origin=ALLOWED_ORIGIN)
        try:
            for socket in (socket_a, socket_b, socket_c):
                await socket.recv()

            await socket_a.send(_envelope("alice", "bob", {"secret": "for bob"}))

            receipt = json.loads(await asyncio.wait_for(socket_b.recv(), 5))
            ack = json.loads(await asyncio.wait_for(socket_a.recv(), 5))
            assert receipt["payload"] == {"secret": "for bob"}
            assert ack["status"] == "delivered"

            # Carol must have nothing waiting.
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(socket_c.recv(), 0.5)
        finally:
            for socket in (socket_a, socket_b, socket_c):
                await socket.close()


@pytest.mark.asyncio
async def test_connection_limit_is_enforced_over_real_sockets() -> None:
    """The global connection cap refuses the upgrade on a real handshake."""
    async with running_server(TransportLimits(max_total_connections=3)) as (port, _application):
        sockets = [
            await connect(_url(port, f"client-{index}"), origin=ALLOWED_ORIGIN)
            for index in range(3)
        ]
        try:
            for socket in sockets:
                await socket.recv()

            with pytest.raises(InvalidStatus):
                await connect(_url(port, "one-too-many"), origin=ALLOWED_ORIGIN)
        finally:
            for socket in sockets:
                await socket.close()
