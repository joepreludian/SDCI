"""Tests for the ASGI middleware that watches upload transfers."""

import asyncio
import logging

import pytest

from sdci.server_middleware import UploadMonitorMiddleware
from sdci.settings import Settings

REPORTER_LOGGER = "sdci.server_runner"


def upload_scope(path="/upload_file/", method="POST", content_length=None):
    headers = []

    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))

    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "client": ("10.0.0.4", 51234),
    }


def receive_from(chunks):
    """ASGI receive callable replaying a body as http.request messages."""
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]

    async def receive():
        return messages.pop(0)

    return receive


def collecting_send(sent):
    async def send(message):
        sent.append(message)

    return send


async def draining_app(scope, receive, send):
    """Reads the whole body, then answers 200 - like the real endpoint."""
    while True:
        message = await receive()
        if not message.get("more_body", False):
            break

    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"{}"})


def test_upload_logs_the_total_transferred(caplog):
    sent = []
    middleware = UploadMonitorMiddleware(draining_app)

    with caplog.at_level(logging.INFO, logger=REPORTER_LOGGER):
        asyncio.run(
            middleware(
                upload_scope(content_length=3072),
                receive_from([b"a" * 1024] * 3),
                collecting_send(sent),
            )
        )

    assert any(
        message.startswith("UPLOAD RECEIVED - 10.0.0.4 - 3.0 KiB in ")
        for message in caplog.messages
    )
    assert sent[0]["status"] == 200


def test_upload_exceeding_the_budget_is_cancelled_with_408(monkeypatch):
    monkeypatch.setattr(Settings, "UPLOAD_TIMEOUT_SECONDS", 0.05)
    cancelled = []

    async def stalled_app(scope, receive, send):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    sent = []
    asyncio.run(
        UploadMonitorMiddleware(stalled_app)(
            upload_scope(), receive_from([b""]), collecting_send(sent)
        )
    )

    assert cancelled == [True]
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 408
    assert b"UPLOAD TIMEOUT" in sent[1]["body"]


def test_timeout_after_the_response_started_does_not_send_a_second_response(monkeypatch):
    monkeypatch.setattr(Settings, "UPLOAD_TIMEOUT_SECONDS", 0.05)

    async def stalled_after_headers_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await asyncio.sleep(5)

    sent = []

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(
            UploadMonitorMiddleware(stalled_after_headers_app)(
                upload_scope(), receive_from([b""]), collecting_send(sent)
            )
        )

    assert [message["type"] for message in sent] == ["http.response.start"]


@pytest.mark.parametrize(
    "scope",
    [
        pytest.param(upload_scope(path="/tasks/deploy/"), id="another-path"),
        pytest.param(upload_scope(method="GET"), id="not-a-post"),
        pytest.param({"type": "lifespan"}, id="lifespan"),
    ],
)
def test_unmonitored_scopes_are_passed_through_untouched(scope):
    seen = {}

    async def recording_app(scope, receive, send):
        seen["receive"] = receive
        seen["send"] = send

    receive = receive_from([b""])
    send = collecting_send([])

    asyncio.run(UploadMonitorMiddleware(recording_app)(scope, receive, send))

    assert seen["receive"] is receive
    assert seen["send"] is send
