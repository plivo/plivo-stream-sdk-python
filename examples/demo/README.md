# Full Voice AI Pipeline Example

Complete real-time Voice AI implementation using Plivo Streaming API with Deepgram, OpenAI, and ElevenLabs.

## Flow
```
1. Plivo Audio Stream (incoming)
2. Deepgram STT (speech to text)
3. OpenAI API (text completion)
4. ElevenLabs TTS (text to speech)
5. Plivo Audio Stream (outgoing)
```

## Setup

1. Navigate to the example directory:
```bash
cd examples/demo
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
uv pip install -e .
```

4. Configure environment variables:
```bash
cp env.example .env
# Edit .env with your own settings and API keys
```

5. Run the server:
```bash
python server.py
```

Server starts on `http://0.0.0.0:8000` with WebSocket endpoint at `ws://0.0.0.0:8000/stream`

## Run with Docker
1. Clone the repository if required
```bash
git clone https://github.com/plivo/plivo-stream-sdk-python
cd plivo-stream-sdk-python
```

2. Create a `.env` file with your API keys and configuration (see [env.example](env.example) for required variables)
```bash
cp examples/demo/env.example examples/demo/.env
```

3. Build and run with docker compose from the repo root:
```bash
docker compose -f examples/demo/docker-compose.yml up --build
```

The server will be available on: `http://localhost:8000` and `ws://localhost:8000`

## Usage

Configure your Plivo phone number to stream audio to your server's WebSocket endpoint. When a call comes in:

1. Audio chunks arrive via Plivo streaming
2. Deepgram transcribes in real-time
3. OpenAI generates conversational responses
4. ElevenLabs synthesizes natural-sounding speech
5. Audio plays back to the caller through Plivo

## Requirements

- Python >= 3.9
- Active API keys for Deepgram, OpenAI, and ElevenLabs
- Plivo account with streaming enabled
- Public endpoint (use ngrok for local development)

