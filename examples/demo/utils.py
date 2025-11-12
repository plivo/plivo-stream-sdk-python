import os
import logging


def env_flag(name: str, default: bool = True) -> bool:
    """Return boolean value from an environment variable with sensible defaults."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def validate_and_normalize_env() -> None:
    """
    Validate presence of mandatory environment variables and normalize aliases.
    - Supports ELEVEN_LABS_VOICE_ID and ELEVEN_LABS_MODEL_ID as aliases.
    - Ensures AUDIO_SAMPLE_RATE is an integer.
    """
    # Normalize known aliases
    if not os.getenv("ELEVENLABS_VOICE_ID") and os.getenv("ELEVEN_LABS_VOICE_ID"):
        os.environ["ELEVENLABS_VOICE_ID"] = os.getenv("ELEVEN_LABS_VOICE_ID", "")
    if not os.getenv("ELEVENLABS_MODEL_ID") and os.getenv("ELEVEN_LABS_MODEL_ID"):
        os.environ["ELEVENLABS_MODEL_ID"] = os.getenv("ELEVEN_LABS_MODEL_ID", "")

    required_vars = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "SYSTEM_PROMPT",
        "DEEPGRAM_API_KEY",
        "DEEPGRAM_MODEL",
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_VOICE_ID",
        "ELEVENLABS_MODEL_ID",
        "AUDIO_SAMPLE_RATE",
        "AUDIO_CONTENT_TYPE",
    ]
    missing = [var for var in required_vars if not os.getenv(var)]

    # Type validations
    invalid = []
    sample_rate_value = os.getenv("AUDIO_SAMPLE_RATE")
    if sample_rate_value:
        try:
            int(sample_rate_value)
        except ValueError:
            invalid.append("AUDIO_SAMPLE_RATE (must be integer)")

    if missing or invalid:
        messages = []
        if missing:
            messages.append(f"Missing required environment variables: {', '.join(missing)}")
        if invalid:
            messages.append(f"Invalid environment variables: {', '.join(invalid)}")
        raise RuntimeError("; ".join(messages))


def get_log_level_from_env(env_var_name: str = "LOG_LEVEL") -> int:
    """
    Return a logging level based on an environment variable.
    Accepted values (case-insensitive): debug, info, warn/warning, error.
    Defaults to INFO when unset or unrecognized.
    """
    name = (os.getenv(env_var_name) or "info").strip().lower()
    mapping = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARN,
        "warning": logging.WARN,
        "error": logging.ERROR,
    }
    return mapping.get(name, logging.INFO)


