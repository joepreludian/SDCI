import asyncio
import json
import logging
from typing import Optional

from sdci.server_runner import UploadProgressReporter, format_bytes
from sdci.settings import Settings

logger = logging.getLogger(__name__)


class UploadMonitorMiddleware:
    """Counts upload bytes as they arrive and bounds the request in wall-clock time.

    FastAPI spools the whole multipart body before the endpoint function runs, so
    both the progress counter and the timeout have to sit below it, at the ASGI
    layer, where the body is still a stream of chunks.
    """

    UPLOAD_PATH = "/upload_file/"

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if not self._is_upload(scope):
            await self.app(scope, receive, send)
            return

        client = self._client_label(scope)
        reporter = UploadProgressReporter(
            client, total_bytes=self._content_length(scope)
        )
        response_started = False

        async def receive_with_progress():
            message = await receive()

            if message["type"] == "http.request":
                reporter.advance(len(message.get("body", b"")))

                if not message.get("more_body", False):
                    reporter.finish()

            return message

        async def send_tracking_start(message):
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True

            await send(message)

        timeout_seconds = Settings.UPLOAD_TIMEOUT_SECONDS

        try:
            await asyncio.wait_for(
                self.app(scope, receive_with_progress, send_tracking_start),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"UPLOAD TIMEOUT - {client} - aborted after {timeout_seconds}s "
                f"({format_bytes(reporter.bytes_received)} received)"
            )

            # Headers are already on the wire: the status can no longer be
            # changed, so let the server tear the connection down.
            if response_started:
                raise

            await self._send_timeout_response(send, timeout_seconds)

    def _is_upload(self, scope) -> bool:
        return (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") == self.UPLOAD_PATH
        )

    @staticmethod
    def _client_label(scope) -> str:
        client = scope.get("client")

        return client[0] if client else "unknown"

    @staticmethod
    def _content_length(scope) -> Optional[int]:
        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue

            try:
                return int(value)
            except ValueError:
                return None

        return None

    @staticmethod
    async def _send_timeout_response(send, timeout_seconds) -> None:
        body = json.dumps(
            {"detail": f"UPLOAD TIMEOUT - exceeded {timeout_seconds}s"}
        ).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 408,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
