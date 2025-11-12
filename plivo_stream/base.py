"""Base WebSocket streaming handler for Plivo"""

import base64
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Any
from plivo_stream.types import (
    EventType,
    StreamEvent,
    EventCallback,
    MediaCallback,
    StartCallback,
    DtmfCallback,
    PlayedStreamCallback,
    ClearedAudioCallback,
    ErrorCallback,
    ConnectionCallback,
)


class BaseStreamingHandler(ABC):
    """
    Base class for Plivo streaming handlers.
    Contains all shared logic for event handling, callbacks, and message processing.
    """

    def __init__(self):
        self._callbacks: dict[EventType, list[EventCallback]] = {
            event: [] for event in EventType
        }
        self._media_callbacks: list[MediaCallback] = []
        self._start_callbacks: list[StartCallback] = []
        self._dtmf_callbacks: list[DtmfCallback] = []
        self._played_stream_callbacks: list[PlayedStreamCallback] = []
        self._cleared_audio_callbacks: list[ClearedAudioCallback] = []
        self._error_callbacks: list[ErrorCallback] = []
        self._connected_callbacks: list[ConnectionCallback] = []
        self._disconnected_callbacks: list[ConnectionCallback] = []
        self._running = False
        self._stream_id: Optional[str] = None
        self._call_id: Optional[str] = None
        self._account_id: Optional[str] = None
        self._headers: Optional[dict[str, str]] = None

    def get_stream_id(self) -> Optional[str]:
        return self._stream_id

    def get_header(self, key: str) -> Optional[str]:
        return self._headers.get(key)

    def get_all_headers(self) -> Optional[dict[str, str]]:
        return self._headers

    def get_call_id(self) -> Optional[str]:
        return self._call_id

    def get_account_id(self) -> Optional[str]:
        return self._account_id

    def on_event(self, event_type: EventType):
        """Decorator to register a callback for a specific event type"""

        def decorator(func: EventCallback):
            self._callbacks[event_type].append(func)
            return func

        return decorator

    def on_start(self, func: StartCallback) -> StartCallback:
        """
        Decorator to register a callback for start events.
        The callback automatically receives a StartEvent parameter.
        """
        self._start_callbacks.append(func)
        return func

    def on_media(self, func: MediaCallback) -> MediaCallback:
        """
        Decorator to register a callback for media events.
        The callback automatically receives a MediaEvent parameter.
        """
        self._media_callbacks.append(func)
        return func

    def on_dtmf(self, func: DtmfCallback) -> DtmfCallback:
        """
        Decorator to register a callback for DTMF events.
        The callback automatically receives a DtmfEvent parameter.
        """
        self._dtmf_callbacks.append(func)
        return func

    def on_played_stream(self, func: PlayedStreamCallback) -> PlayedStreamCallback:
        """
        Decorator to register a callback for playedStream events.
        The callback automatically receives a PlayedStreamEvent parameter.
        """
        self._played_stream_callbacks.append(func)
        return func

    def on_cleared_audio(self, func: ClearedAudioCallback) -> ClearedAudioCallback:
        """
        Decorator to register a callback for clearedAudio events.
        The callback automatically receives a ClearedAudioEvent parameter.
        """
        self._cleared_audio_callbacks.append(func)
        return func

    def on_connected(self, func: ConnectionCallback) -> ConnectionCallback:
        """
        Decorator to register a callback for connection events.
        The callback receives no parameters.
        """
        self._connected_callbacks.append(func)
        return func

    def on_disconnected(self, func: ConnectionCallback) -> ConnectionCallback:
        """
        Decorator to register a callback for disconnection events.
        The callback receives no parameters.
        """
        self._disconnected_callbacks.append(func)
        return func

    def on_error(self, func: ErrorCallback) -> ErrorCallback:
        """
        Decorator to register a callback for error events.
        The callback automatically receives an Exception parameter.
        """
        self._error_callbacks.append(func)
        return func

    async def _trigger_callbacks(self, event: StreamEvent):
        """Trigger all callbacks for a given event"""
        from plivo_stream.types import (
            StartEvent,
            MediaEvent,
            DtmfEvent,
            PlayedStreamEvent,
            ClearedAudioEvent,
        )

        callbacks = self._callbacks.get(event.event, [])
        await asyncio.gather(
            *[callback(event) for callback in callbacks], return_exceptions=True
        )

        # Special handling for specific event types with dedicated callbacks
        # Parse raw dict into Pydantic models for type safety and attribute access
        try:
            if event.event == EventType.START:
                start_event = StartEvent(**event.data)
                # Extract and store streamId, callId, accountId from start event
                self._stream_id = start_event.start.stream_id
                self._call_id = start_event.start.call_id
                self._account_id = start_event.start.account_id
                await asyncio.gather(
                    *[callback(start_event) for callback in self._start_callbacks],
                    return_exceptions=True,
                )
            elif event.event == EventType.MEDIA:
                media_event = MediaEvent(**event.data)
                media_event.get_raw_media = lambda: base64.b64decode(
                    media_event.media.payload
                )
                await asyncio.gather(
                    *[callback(media_event) for callback in self._media_callbacks],
                    return_exceptions=True,
                )
            elif event.event == EventType.DTMF:
                dtmf_event = DtmfEvent(**event.data)
                await asyncio.gather(
                    *[callback(dtmf_event) for callback in self._dtmf_callbacks],
                    return_exceptions=True,
                )
            elif event.event == EventType.PLAYED_STREAM:
                played_event = PlayedStreamEvent(**event.data)
                await asyncio.gather(
                    *[
                        callback(played_event)
                        for callback in self._played_stream_callbacks
                    ],
                    return_exceptions=True,
                )
            elif event.event == EventType.CLEARED_AUDIO:
                cleared_event = ClearedAudioEvent(**event.data)
                await asyncio.gather(
                    *[
                        callback(cleared_event)
                        for callback in self._cleared_audio_callbacks
                    ],
                    return_exceptions=True,
                )
        except Exception as e:
            # If Pydantic validation fails, trigger error callbacks
            await self._trigger_error_callbacks(e)

    async def _trigger_connection_callbacks(self):
        """Trigger connection callbacks"""
        await asyncio.gather(
            *[callback() for callback in self._connected_callbacks],
            return_exceptions=True,
        )

    async def _trigger_disconnection_callbacks(self):
        """Trigger disconnection callbacks"""
        await asyncio.gather(
            *[callback() for callback in self._disconnected_callbacks],
            return_exceptions=True,
        )

    async def _trigger_error_callbacks(self, error: Exception):
        """Trigger error callbacks"""
        await asyncio.gather(
            *[callback(error) for callback in self._error_callbacks],
            return_exceptions=True,
        )

    @abstractmethod
    async def _send_raw(self, data: str):
        """
        Send raw string data through the WebSocket.
        Must be implemented by subclasses.
        """
        pass

    async def send_json(self, data: dict[str, Any]):
        """Send JSON data through the WebSocket"""
        try:
            await self._send_raw(json.dumps(data))
        except Exception as e:
            await self._trigger_error_callbacks(e)
            raise

    async def send_text(self, message: str):
        """Send text message through the WebSocket"""
        try:
            await self._send_raw(message)
        except Exception as e:
            await self._trigger_error_callbacks(e)
            raise

    async def send_media(
        self,
        media_data: bytes,
        content_type: str = "audio/x-mulaw",
        sample_rate: int = 8000,
    ):
        """
        Send media data through the WebSocket

        Args:
            media_data: The media payload (raw bytes)
            content_type: Audio content type (default: "audio/x-mulaw")
            sample_rate: Audio sample rate (default: 8000)
        """
        from plivo_stream.types import PlayAudioEvent, PlayAudioMedia

        encoded_media_data = base64.b64encode(media_data).decode("utf-8")
        payload = PlayAudioEvent(
            event="playAudio",
            media=PlayAudioMedia(
                contentType=content_type,
                payload=encoded_media_data,
                sampleRate=sample_rate,
            ),
        )
        await self.send_json(payload.model_dump(by_alias=True))

    async def send_checkpoint(self, checkpoint_name: str):
        """
        Send a checkpoint event to track message processing

        Args:
            checkpoint_name: Label to identify this checkpoint
        """
        if not self._stream_id:
            raise ValueError("streamId not available. Wait for 'start' event first.")

        from plivo_stream.types import CheckpointEvent

        payload = CheckpointEvent(
            event="checkpoint", name=checkpoint_name, stream_id=self._stream_id
        )
        await self.send_json(payload.model_dump(by_alias=True))

    async def send_clear_audio(self):
        """Clear the audio buffer on the stream"""
        if not self._stream_id:
            raise ValueError("streamId not available. Wait for 'start' event first.")

        from plivo_stream.types import ClearAudioEvent

        payload = ClearAudioEvent(event="clearAudio", stream_id=self._stream_id)
        await self.send_json(payload.model_dump(by_alias=True))

    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            event_type = data.get("event")

            if event_type:
                try:
                    event = StreamEvent(event=EventType(event_type), data=data)
                    await self._trigger_callbacks(event)
                except ValueError:
                    # Unknown event type, trigger generic error
                    await self._trigger_error_callbacks(
                        ValueError(f"Unknown event type: {event_type}")
                    )
        except json.JSONDecodeError as e:
            await self._trigger_error_callbacks(e)
        except Exception as e:
            await self._trigger_error_callbacks(e)
