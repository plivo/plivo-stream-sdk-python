"""Example WebSocket server with path routing (like /stream endpoint)"""

import asyncio
import base64
import websockets
from websockets.server import ServerConnection
from plivo_stream import (
    PlivoWebsocketStreamingHandler,
    StartEvent,
    MediaEvent,
    DtmfEvent,
    PlayedStreamEvent,
    ClearedAudioEvent,
    StreamEvent,
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_stream(websocket: ServerConnection):
    """Handle /stream endpoint"""

    handler = PlivoWebsocketStreamingHandler()

    @handler.on_connected
    async def on_connect():
        logger.info(f"Stream connected: {websocket.remote_address}")

    @handler.on_disconnected
    async def on_disconnect():
        logger.info(f"Stream disconnected: {websocket.remote_address}")

    @handler.on_start
    async def on_start(data: StartEvent):
        """Handle stream start event"""
        logger.info(f"Stream started")
        logger.info(f"   Stream ID: {handler.get_stream_id()}")
        logger.info(f"   Call ID: {handler.get_call_id()}")
        logger.info(f"   Account ID: {handler.get_account_id()}")

    @handler.on_media
    async def on_media(data: MediaEvent):
        """Handle incoming media (audio) data"""
        payload = data.media.payload
        logger.info(f"Received media chunk: {len(payload)} bytes")

        # Echo the media back
        if payload:
            await handler.send_media(base64.b64decode(payload))

    @handler.on_dtmf
    async def on_dtmf(data: DtmfEvent):
        """Handle DTMF tone detection"""
        digit = data.dtmf.digit
        logger.info(f"DTMF detected: {digit}")

    @handler.on_played_stream
    async def on_played_stream(data: PlayedStreamEvent):
        """Handle playedStream event (audio finished playing)"""
        logger.info(f"Audio finished playing: {data.name}")

    @handler.on_cleared_audio
    async def on_cleared_audio(data: ClearedAudioEvent):
        """Handle clearedAudio event (audio buffer cleared)"""
        logger.info(f"Audio buffer cleared for stream: {data.stream_id}")

    @handler.on_error
    async def on_error(error):
        """Handle errors"""
        logger.error(f"Error: {error}")

    await handler.handle(websocket)


async def router(websocket: ServerConnection):
    """Route requests based on path"""
    path = websocket.request.path if hasattr(websocket, "request") else websocket.path

    logger.info(f"Connection to {path} from {websocket.remote_address}")

    if path == "/stream":
        await handle_stream(websocket)
    else:
        # Return 404-like message
        await websocket.send('{"error": "Not found"}')
        await websocket.close()


async def main():
    """Start the WebSocket server with routing"""
    host = "0.0.0.0"
    port = 8000

    logger.info(f"Starting WebSocket server on ws://{host}:{port}")
    logger.info(f"Available endpoints:")
    logger.info(f"   - ws://{host}:{port}/stream")

    async with websockets.serve(router, host, port):
        logger.info("Server running! Press Ctrl+C to stop.")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
