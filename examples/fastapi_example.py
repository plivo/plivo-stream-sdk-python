"""Example FastAPI application using Plivo Streaming SDK"""

import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from plivo_stream import (
    PlivoFastAPIStreamingHandler,
    StartEvent,
    MediaEvent,
    DtmfEvent,
    PlayedStreamEvent,
    ClearedAudioEvent,
    StreamEvent,
)

app = FastAPI()

# Module logger
logger = logging.getLogger(__name__)

# Add CORS middleware for ngrok
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for Plivo streaming"""
    # Create handler instance
    handler = PlivoFastAPIStreamingHandler(websocket)
    
    # Register event handlers
    @handler.on_connected
    async def on_connect():
        logger.info("Client connected")
    
    @handler.on_disconnected
    async def on_disconnect():
        logger.info("Client disconnected")
    
    @handler.on_start
    async def on_start(data: StartEvent):
        """Handle stream start event"""
        logger.info("Stream started")
        logger.info(f"Stream ID: {handler.get_stream_id()}")
        logger.info(f"Call ID: {handler.get_call_id()}")
        logger.info(f"Account ID: {handler.get_account_id()}")
    
    @handler.on_media
    async def on_media(data: MediaEvent):
        """Handle incoming media (audio) data"""
        payload = data.media.payload
        logger.info(f"Received media chunk: {len(payload)} bytes")
        
        # Echo the media back
        if payload:
            await handler.send_media(payload)
    
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
        logger.info(f"Audio buffer cleared for stream: {data.streamId}")

    
    @handler.on_error
    async def on_error(error):
        """Handle errors"""
        logger.error(f"Error: {error}")
    
    # Start the handler (this will block until connection closes)
    await handler.start()


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000)

