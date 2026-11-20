"""FastAPI WebSocket streaming handler for Plivo"""

from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from plivo_stream.base import BaseStreamingHandler
from plivo_stream.signature import stream_url_from_scope, validate_stream_signature


class PlivoFastAPIStreamingHandler(BaseStreamingHandler):
    """
    FastAPI WebSocket handler for Plivo streaming.

    Usage:
        handler = PlivoFastAPIStreamingHandler(websocket)

        @handler.on_connected
        async def handle_connect():
            print("Client connected")

        @handler.on_media
        async def handle_media(data):
            print(f"Received media: {data}")

        await handler.start()
    """

    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket

    async def _send_raw(self, data: str):
        """Send raw string data through FastAPI WebSocket"""
        await self.websocket.send_text(data)

    async def start(
        self,
        with_signature_verification: bool = False,
        auth_token: Optional[str] = None,
        public_url: Optional[str] = None,
        allow_legacy_signature: bool = True,
    ):
        """
        Start the WebSocket listener loop.
        This should be awaited in your FastAPI WebSocket endpoint.

        Args:
            with_signature_verification: Validate the X-Plivo-Signature-V3 header
                before accepting the connection.
            auth_token: Your Plivo auth token. Required with signature verification.
            public_url: Public base URL of the stream endpoint as configured in your
                <Stream> XML, e.g. "wss://example.com". The request path and query are
                appended to it. Set this when a proxy in front of the server changes the
                scheme, host or path prefix. If omitted, the URL is built from the Host
                header, using wss if x-forwarded-proto is https/wss, else the request scheme.
            allow_legacy_signature: Also accept the legacy signed form
                (http://host/path, query dropped). Transitional; it will be removed
                in a future release.
        """

        if with_signature_verification and not auth_token:
            raise ValueError("Auth token is required")
        try:
            if with_signature_verification:
                url = stream_url_from_scope(self.websocket.scope, public_url)
                if not validate_stream_signature(
                    url,
                    self.websocket.headers,
                    auth_token,
                    allow_legacy_signature=allow_legacy_signature,
                ):
                    # Closing before accept rejects the handshake with HTTP 403.
                    await self.websocket.close(code=1008)
                    raise ValueError("Invalid socket signature")

            self._running = True
            # Accept the WebSocket connection
            await self.websocket.accept()
            await self._trigger_connection_callbacks()

            # Listen for messages
            while self._running:
                try:
                    message = await self.websocket.receive_text()
                    await self._process_message(message)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    await self._trigger_error_callbacks(e)

        except Exception as e:
            await self._trigger_error_callbacks(e)
        finally:
            self._running = False
            await self._trigger_disconnection_callbacks()

    async def stop(self):
        """Stop the WebSocket listener"""
        self._running = False
        try:
            await self.websocket.close()
        except:
            pass
