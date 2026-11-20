"""Official Python SDK for the Plivo Streaming API with asyncio, WebSockets and FastAPI support"""

__version__ = "0.2.0"

from plivo_stream.base import BaseStreamingHandler
from plivo_stream.fastapi import PlivoFastAPIStreamingHandler
from plivo_stream.websockets import PlivoWebsocketStreamingHandler
from plivo_stream.signature import validate_stream_signature
from plivo_stream.types import (
    EventType,
    StreamEvent,
    # Callback types
    EventCallback,
    StartCallback,
    MediaCallback,
    DtmfCallback,
    PlayedStreamCallback,
    ClearedAudioCallback,
    ErrorCallback,
    ConnectionCallback,
    # Incoming event types
    StartEvent,
    StartData,
    MediaEvent,
    MediaData,
    DtmfEvent,
    DtmfData,
    PlayedStreamEvent,
    ClearedAudioEvent,
    MediaFormat,
    # Outgoing event types
    PlayAudioEvent,
    PlayAudioMedia,
    CheckpointEvent,
    ClearAudioEvent,
)

__all__ = [
    # Handlers
    "BaseStreamingHandler",
    "PlivoFastAPIStreamingHandler",
    "PlivoWebsocketStreamingHandler",
    # Signature validation
    "validate_stream_signature",
    # Enums
    "EventType",
    # Base types
    "StreamEvent",
    # Callback types
    "EventCallback",
    "StartCallback",
    "MediaCallback",
    "DtmfCallback",
    "PlayedStreamCallback",
    "ClearedAudioCallback",
    "ErrorCallback",
    "ConnectionCallback",
    # Incoming event types
    "StartEvent",
    "StartData",
    "MediaEvent",
    "MediaData",
    "DtmfEvent",
    "DtmfData",
    "PlayedStreamEvent",
    "ClearedAudioEvent",
    "MediaFormat",
    # Outgoing event types
    "PlayAudioEvent",
    "PlayAudioMedia",
    "CheckpointEvent",
    "ClearAudioEvent",
]

