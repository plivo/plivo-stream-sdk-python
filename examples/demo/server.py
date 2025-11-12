import asyncio
import base64
import os
import logging

from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v2.socket_client import AsyncV2SocketClient
from elevenlabs.client import AsyncElevenLabs
from fastapi import FastAPI, Request, Response, WebSocket
from openai import AsyncOpenAI
from dotenv import load_dotenv

from plivo import plivoxml
from plivo.xml import StreamElement
from plivo_stream import ClearedAudioEvent, DtmfEvent, PlayedStreamEvent, PlivoFastAPIStreamingHandler, MediaEvent, StartEvent
from plivo_stream import __version__ as plivo_stream_version
from utils import validate_and_normalize_env, env_flag, get_log_level_from_env

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(get_log_level_from_env())

# ============================================================================
# Configuration & API Keys
# ============================================================================

# Validate and normalize before reading configuration
validate_and_normalize_env()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Audio configuration
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE"))
AUDIO_CONTENT_TYPE = os.getenv("AUDIO_CONTENT_TYPE")
RECORDING_CALLBACK_URL = os.getenv("RECORDING_CALLBACK_URL")

# Model configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID")

# System prompt
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")

# ============================================================================
# Client Initialization
# ============================================================================

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
elevenlabs_client = AsyncElevenLabs(api_key=ELEVENLABS_API_KEY)
deepgram_client = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)

# Conversation history is tracked per session stream ID within the websocket handler

# ============================================================================
# Helper Functions
# ============================================================================


async def get_openai_response(history: list[dict]) -> str:
    """Get a response from OpenAI based on provided conversation history."""
    response = await openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
        ],
    )
    return response.choices[0].message.content


async def add_message_and_get_response(user_message: str, history: list[dict]) -> str:
    """Add user message to provided history and get AI response."""
    history.append({"role": "user", "content": user_message})
    assistant_response = await get_openai_response(history)
    history.append({"role": "assistant", "content": assistant_response})
    
    # Keep only the last 10 pairs (20 messages)
    if len(history) > 20:
        history[:] = history[-20:]
    
    return assistant_response


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI()

# ============================================================================
# HTTP Routes
# ============================================================================


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Plivo Stream SDK {} for Python is running".format(plivo_stream_version)}

# ======================================================
# Callback Routes
# ======================================================

@app.post("/recording")
async def recording_callback(request: Request):
    """Optional endpoint to receive recording metadata/events from Plivo."""
    try:
        payload = await request.body()
        logger.info("Recording callback received: headers=%s body=%s", dict(request.headers), payload.decode(errors="ignore"))
    except Exception as e:
        logger.error("Error processing recording callback: %s", e)
    return {"status": "ok"}

@app.post("/hangup")
async def hangup_callback(request: Request):
    """Callback endpoint invoked by Plivo when the call ends (hangup)."""
    try:
        payload = await request.body()
        logger.info("Hangup callback received: headers=%s body=%s", dict(request.headers), payload.decode(errors="ignore"))
    except Exception as e:
        logger.error("Error processing hangup callback: %s", e)
    return {"status": "ok"}

@app.post("/stream")
async def stream_xml(request: Request):
    """Initialize a Plivo streaming session with bidirectional audio."""
    host = request.headers.get("Host")

    # Build Plivo XML response
    plivo_response = plivoxml.ResponseElement()
    # Recording controls (default: enabled)
    enable_recording = env_flag("ENABLE_RECORDING", default=True)
    if enable_recording:
        record_kwargs = {
            "max_length": 86400,
            "record_session": True,
        }
        # Configure recording callback URL (default to 'auto' if unset/empty)
        callback_env_raw = os.getenv("RECORDING_CALLBACK_URL")
        mode = (callback_env_raw or "auto").strip().lower()
        if mode == "":
            mode = "auto"
        if mode == "auto":
            record_kwargs["callback_url"] = f"http://{host}/recording"
        elif mode == "auto+https":
            record_kwargs["callback_url"] = f"https://{host}/recording"
        else:
            record_kwargs["callback_url"] = (callback_env_raw or "").strip()
        plivo_response.add_record(**record_kwargs)

    # WebSocket URL controls
    # Default WEBSOCKET_URL to 'auto' if unset or empty
    explicit_ws_url = os.getenv("WEBSOCKET_URL", "auto")
    mode = (explicit_ws_url or "auto").strip().lower()
    if mode == "":
        mode = "auto"
    if mode == "auto":
        ws_url = f"ws://{host}/stream"
    elif mode == "auto+wss":
        ws_url = f"wss://{host}/stream"
    else:
        # Use as-is
        ws_url = explicit_ws_url
    plivo_response.add(
        StreamElement(
            bidirectional=True,
            keepCallAlive=True,
            contentType=f"{AUDIO_CONTENT_TYPE};rate={AUDIO_SAMPLE_RATE}",
            content=ws_url,
        )
    )

    return Response(content=plivo_response.to_string(), media_type="application/xml")


# ============================================================================
# WebSocket Routes for bidirectional audio streaming
# ============================================================================

@app.websocket("/ws")
async def stream_websocket_handler(websocket: WebSocket):
    """
    Handle bidirectional audio streaming between Plivo, Deepgram, and ElevenLabs.

    Flow:
    1. Receive audio from Plivo call
    2. Send to Deepgram for transcription
    3. Process transcription with OpenAI
    4. Convert response to speech with ElevenLabs
    5. Stream audio back to Plivo call
    """
    try:
        deepgram_connection: AsyncV2SocketClient = None
        plivo_handler = PlivoFastAPIStreamingHandler(websocket)
        playing = False
        current_stream_id: str | None = None
        conversation_history_by_stream_id: dict[str, list[dict]] = {}

        async def stream_elevenlabs_audio(text: str):
            """Convert text to speech using ElevenLabs and stream to Plivo."""
            nonlocal playing
            logger.debug(f"TTS: converting text to speech on stream {current_stream_id or 'unknown'} for text: {text}")
            audio_stream = elevenlabs_client.text_to_speech.convert(
                text=text,
                voice_id=ELEVENLABS_VOICE_ID,
                model_id=ELEVENLABS_MODEL_ID,
                output_format="pcm_16000",
            )
            playing = True
            sample = bytearray()
            async for audio_chunk in audio_stream:
                await plivo_handler.send_media(
                    media_data=audio_chunk,
                    content_type=AUDIO_CONTENT_TYPE,
                    sample_rate=AUDIO_SAMPLE_RATE,
                )
                sample += audio_chunk
                await asyncio.sleep(0.015) # Wait for 15ms to allow the audio to play
            sample_b64 = base64.b64encode(sample).decode("utf-8")
            logger.debug(f"TTS: text {text} - raw audio bytes: {sample_b64}")
            # Send checkpoint to indicate that all audio has been played
            await plivo_handler.send_checkpoint("all_audio_played")

        async def connect_and_listen_deepgram():
            """Connect to Deepgram and handle transcription events."""
            nonlocal deepgram_connection
            nonlocal current_stream_id
            nonlocal conversation_history_by_stream_id

            async with deepgram_client.listen.v2.connect(
                model=DEEPGRAM_MODEL,
                encoding="linear16",
                sample_rate=str(AUDIO_SAMPLE_RATE),
            ) as connection:

                async def on_deepgram_message(message):
                    nonlocal playing
                    nonlocal current_stream_id
                    nonlocal conversation_history_by_stream_id
                    """Handle incoming Deepgram transcription messages."""
                    if message.type == "TurnInfo" and message.event == "StartOfTurn":
                        logger.debug(f"TurnInfo: {message.event} for stream {current_stream_id or 'unknown'}")
                    if message.type == "TurnInfo" and message.event == "EndOfTurn":
                        logger.debug(f"TurnInfo: {message.event} for stream {current_stream_id or 'unknown'}")
                        logger.info(f"[User]: {message.transcript}")

                        # Get AI response for the transcribed text
                        stream_id = current_stream_id or "unknown"
                        history = conversation_history_by_stream_id.setdefault(stream_id, [])
                        ai_response = await add_message_and_get_response(message.transcript, history)
                        logger.info(f"[AIAgent]: {ai_response}")

                        # Convert AI response to speech and stream back
                        if playing:
                            # If the audio is still being played to the user, we need to clear the audio buffer
                            await plivo_handler.send_clear_audio()
                            # The audio has been stopped playing to the user, so we can start playing the new audio
                            playing = False
                        await stream_elevenlabs_audio(ai_response)

                deepgram_connection = connection
                logger.debug(f"Connected to Deepgram for stream {current_stream_id or 'unknown'}")
                connection.on(EventType.MESSAGE, on_deepgram_message)
                await connection.start_listening()

        @plivo_handler.on_media
        async def on_plivo_media(event: MediaEvent):
            """Forward incoming audio from Plivo to Deepgram for transcription."""
            if deepgram_connection is not None:
                await deepgram_connection.send_media(
                    event.get_raw_media()
                )
            else:
                logger.warning(f"No Deepgram connection established for stream {current_stream_id or 'unknown'}")

        @plivo_handler.on_start
        async def on_start(event: StartEvent):
            """Handle the start event."""
            logger.info(f"Stream started: {event.start.stream_id} on call {event.start.call_id}")
            nonlocal current_stream_id
            nonlocal conversation_history_by_stream_id
            current_stream_id = event.start.stream_id
            conversation_history_by_stream_id.setdefault(current_stream_id, [])
            logger.info(f"Conversation history for stream {current_stream_id} initialized")

        @plivo_handler.on_disconnected
        async def on_disconnected():
            """Handle the disconnected event."""
            logger.info("Disconnected from Plivo")
            nonlocal current_stream_id
            nonlocal conversation_history_by_stream_id
            if current_stream_id and current_stream_id in conversation_history_by_stream_id:
                try:
                    del conversation_history_by_stream_id[current_stream_id]
                except KeyError:
                    pass
            logger.info(f"Cleared conversation history for stream {current_stream_id or 'unknown'}")

        @plivo_handler.on_dtmf
        async def on_dtmf(event: DtmfEvent):
            """Handle the DTMF event."""
            logger.info(f"DTMF detected: {event.dtmf.digit}")

        @plivo_handler.on_cleared_audio
        async def on_cleared_audio(event: ClearedAudioEvent):
            """Handle the cleared audio event."""
            logger.info(f"Cleared audio: {event.stream_id}")

        @plivo_handler.on_disconnected
        async def on_disconnected():
            """Handle the disconnected event."""
            logger.info(f"Disconnected from Plivo stream {current_stream_id or 'unknown'}")

        @plivo_handler.on_error
        async def on_error(error: Exception):
            """Handle the error event."""
            logger.error(f"Error: {error}")

        @plivo_handler.on_played_stream
        async def on_played_stream(event: PlayedStreamEvent):
            nonlocal playing
            """Handle the played stream event."""
            # All audio has been played to the user, so we can stop playing
            logger.info(f"Audio finished playing: {event.name} on stream {event.stream_id}")
            playing = False

        # Run both Deepgram listener and Plivo handler concurrently
        deepgram_task = asyncio.create_task(connect_and_listen_deepgram())
        plivo_task = asyncio.create_task(plivo_handler.start())
        await asyncio.gather(deepgram_task, plivo_task)

    except Exception as e:
        logger.error(f"Error: {e}")
        return {"message": "Error occurred"}


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
