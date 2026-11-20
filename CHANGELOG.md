# v0.2.0
- Validate `X-Plivo-Signature-V3` against the stream URL as configured (`ws`/`wss`, host and port, path and sorted query), and accept multiple comma-separated signatures.
- Add `public_url` and `allow_legacy_signature` (default `True`) options to `PlivoFastAPIStreamingHandler.start()`.
- Add `validate_stream_signature()` for validating a connection outside the FastAPI handler.
- Remove the runtime dependency on the `plivo` package.

# v0.1.0
- Initial release including FastAPI and Websocket support.
