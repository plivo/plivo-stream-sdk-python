"""Type definitions for Plivo Streaming SDK"""

from enum import Enum
from typing import Any, Callable, Awaitable, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Event types for Plivo MS streaming"""

    # Incoming events from Plivo MS
    START = "start"
    MEDIA = "media"
    PLAYED_STREAM = "playedStream"
    CLEARED_AUDIO = "clearedAudio"
    DTMF = "dtmf"


# ========== Incoming Event Payloads from Plivo MS ==========


class MediaFormat(BaseModel):
    """Media format specification"""

    model_config = ConfigDict(populate_by_name=True)

    encoding: str = Field(
        ...,
        description="Audio encoding, e.g., 'audio/x-mulaw'",
        docstring="The audio encoding type, such as 'audio/x-mulaw'.",
    )
    sample_rate: int = Field(
        ...,
        alias="sampleRate",
        description="Sample rate, e.g., 8000",
        docstring="The audio sample rate in Hz. For example, 8000.",
    )


class StartData(BaseModel):
    """Start event data structure"""

    call_id: str = Field(..., alias="callId", description="Unique call identifier")
    stream_id: str = Field(
        ..., alias="streamId", description="Unique stream identifier"
    )
    account_id: str = Field(..., alias="accountId", description="Plivo account ID")
    tracks: list[str] = Field(..., description="Audio tracks, e.g., ['inbound']")
    media_format: MediaFormat = Field(
        ..., alias="mediaFormat", description="Media format specification"
    )


class StartEvent(BaseModel):
    """Start event payload from Plivo MS"""

    sequence_number: int = Field(
        ..., alias="sequenceNumber", description="Message sequence number"
    )
    event: Literal["start"] = Field(..., description="Event type")
    start: StartData = Field(..., description="Start event data")
    extra_headers: Optional[str] = Field(
        None, description="Extra headers as JSON string"
    )


class MediaData(BaseModel):
    """Media event data structure"""

    track: str = Field(..., description="Audio track, e.g., 'inbound'")
    timestamp: str = Field(
        ..., description="Presentation timestamp in milliseconds from stream start"
    )
    chunk: int = Field(..., description="Chunk number, starts at 1 and increments")
    payload: str = Field(..., description="Base64 encoded audio data")


class MediaEvent(BaseModel):
    """Media event payload from Plivo MS"""

    sequence_number: int = Field(
        ..., alias="sequenceNumber", description="Message sequence number"
    )
    stream_id: str = Field(..., alias="streamId", description="Stream identifier")
    event: Literal["media"] = Field(..., description="Event type")
    media: MediaData = Field(..., description="Media data")
    extra_headers: Optional[str] = Field(
        None, description="Extra headers as JSON string"
    )
    get_raw_media: Optional[Callable[[], bytes]] = Field(
        default=None, exclude=True, description="Get raw audio data"
    )


class DtmfData(BaseModel):
    """DTMF event data structure"""

    track: str = Field(..., description="Audio track, e.g., 'inbound'")
    digit: str = Field(..., description="The detected DTMF digit")
    timestamp: str = Field(..., description="Timestamp in milliseconds")


class DtmfEvent(BaseModel):
    """DTMF event payload from Plivo MS"""

    event: Literal["dtmf"] = Field(..., description="Event type")
    sequence_number: int = Field(
        ..., alias="sequenceNumber", description="Message sequence number"
    )
    stream_id: str = Field(..., alias="streamId", description="Stream identifier")
    dtmf: DtmfData = Field(..., description="DTMF data")
    extra_headers: Optional[str] = Field(
        None, description="Extra headers as JSON string"
    )


class PlayedStreamEvent(BaseModel):
    """PlayedStream event payload from Plivo MS"""

    event: Literal["playedStream"] = Field(..., description="Event type")
    sequence_number: int = Field(
        ...,
        alias="sequenceNumber",
        description="Message sequence number (can be string)",
    )
    stream_id: str = Field(..., alias="streamId", description="Stream identifier")
    name: str = Field(..., description="Checkpoint name")


class ClearedAudioEvent(BaseModel):
    """ClearedAudio event payload from Plivo MS"""

    sequence_number: int = Field(
        ..., alias="sequenceNumber", description="Message sequence number"
    )
    event: Literal["clearedAudio"] = Field(..., description="Event type")
    stream_id: str = Field(..., alias="streamId", description="Stream identifier")


# ========== Outgoing Event Payloads to Plivo MS ==========


class PlayAudioMedia(BaseModel):
    """Media data for playAudio event"""

    model_config = ConfigDict(populate_by_name=True)
    content_type: str = Field(
        ...,
        alias="contentType",
        description="Audio content type, e.g., 'audio/x-mulaw' or 'audio/x-l16'",
    )
    sample_rate: int = Field(
        ..., alias="sampleRate", description="Sample rate, e.g., 8000"
    )
    payload: str = Field(..., description="Raw Audio data")


class PlayAudioEvent(BaseModel):
    """PlayAudio event to send to Plivo MS"""

    model_config = ConfigDict(populate_by_name=True)
    event: Literal["playAudio"] = Field(..., description="Event type")
    media: PlayAudioMedia = Field(..., description="Media data")


class CheckpointEvent(BaseModel):
    """Checkpoint event to send to Plivo MS"""

    model_config = ConfigDict(populate_by_name=True)
    event: Literal["checkpoint"] = Field(..., description="Event type")
    stream_id: str = Field(..., alias="streamId", description="Stream identifier")
    name: str = Field(..., description="Checkpoint label")


class ClearAudioEvent(BaseModel):
    """ClearAudio event to send to Plivo MS"""

    model_config = ConfigDict(populate_by_name=True)
    event: Literal["clearAudio"] = Field(..., description="Event type")
    stream_id: str = Field(
        ...,
        alias="streamId",
        description="Stream identifier",
    )


# ========== Generic Event Structure ==========


class StreamEvent(BaseModel):
    """Base event structure"""

    event: EventType
    data: dict[str, Any]


# ========== Callback Type Aliases ==========

EventCallback = Callable[[StreamEvent], Awaitable[None]]
StartCallback = Callable[[StartEvent], Awaitable[None]]
MediaCallback = Callable[[MediaEvent], Awaitable[None]]
DtmfCallback = Callable[[DtmfEvent], Awaitable[None]]
PlayedStreamCallback = Callable[[PlayedStreamEvent], Awaitable[None]]
ClearedAudioCallback = Callable[[ClearedAudioEvent], Awaitable[None]]
ErrorCallback = Callable[[Exception], Awaitable[None]]
ConnectionCallback = Callable[[], Awaitable[None]]
