FROM python:3.11-slim

WORKDIR /app

# Install uv for faster package management
RUN pip install uv

# Copy the root plivo-streaming-python package first (workspace dependency)
COPY plivo_stream /app/plivo_stream
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Copy the example application
COPY examples/demo /app/examples/demo

WORKDIR /app/examples/demo

# Install dependencies
RUN uv pip install --system -r pyproject.toml

# Expose the FastAPI port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "server.py"]

