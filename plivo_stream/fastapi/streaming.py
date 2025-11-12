"""FastAPI WebSocket streaming handler for Plivo"""

from operator import contains
from fastapi import WebSocket, WebSocketDisconnect
from plivo_stream.base import BaseStreamingHandler
import plivo.utils as plivoutils


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
        self, with_signature_verification: bool = False, auth_token: str = None
    ):
        """
        Start the WebSocket listener loop.
        This should be awaited in your FastAPI WebSocket endpoint.
        """

        if with_signature_verification and not auth_token:
            raise ValueError("Auth token is required")
        try:
            headers = dict(self.websocket.headers)
            if with_signature_verification:
                parsed_uri = self.websocket.url._url
                if "ws://" in self.websocket.url._url:
                    parsed_uri = self.websocket.url._url.replace("ws://", "http://")
                elif "wss://" in self.websocket.url._url:
                    parsed_uri = self.websocket.url._url.replace("wss://", "http://")
                valid_v3_signature = plivoutils.validate_v3_signature(
                    uri=parsed_uri + "/websocket",
                    method="GET",
                    nonce=headers.get("x-plivo-signature-v3-nonce"),
                    v3_signature=headers.get("x-plivo-signature-v3"),
                    auth_token=auth_token,
                )
                if not valid_v3_signature:
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
