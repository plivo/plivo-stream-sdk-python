"""Plain WebSocket streaming handler for Plivo using websockets library"""

from typing import Optional
from websockets.server import ServerConnection
from plivo_stream.base import BaseStreamingHandler


class PlivoWebsocketStreamingHandler(BaseStreamingHandler):
    """
    Plain WebSocket handler for Plivo streaming using websockets library.
    
    Usage:
        handler = PlivoWebsocketStreamingHandler()
        
        @handler.on_connected
        async def handle_connect():
            print("Client connected")
        
        @handler.on_media
        async def handle_media(data):
            print(f"Received media: {data}")
        
        async def connection_handler(websocket):
            await handler.handle(websocket)
        
        async with websockets.serve(connection_handler, "0.0.0.0", 8000):
            await asyncio.Future()  # run forever
    """
    
    def __init__(self):
        super().__init__()
        self._websocket: Optional[ServerConnection] = None
    
    async def _send_raw(self, data: str):
        """Send raw string data through plain WebSocket"""
        if not self._websocket:
            raise RuntimeError("WebSocket not connected")
        await self._websocket.send(data)
    
    async def handle(self, websocket: ServerConnection):
        """
        Handle a WebSocket connection.
        This should be called from your websockets.serve handler.
        
        Args:
            websocket: The WebSocket connection from websockets.serve
        """
        self._websocket = websocket
        self._running = True
        
        try:
            await self._trigger_connection_callbacks()
            
            # Listen for messages
            async for message in websocket:
                if not self._running:
                    break
                await self._process_message(message)
                    
        except Exception as e:
            await self._trigger_error_callbacks(e)
        finally:
            self._running = False
            self._websocket = None
            await self._trigger_disconnection_callbacks()
    
    async def stop(self):
        """Stop the WebSocket listener"""
        self._running = False
        if self._websocket:
            await self._websocket.close()

