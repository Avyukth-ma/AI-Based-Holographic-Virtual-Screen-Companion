from pathlib import Path
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment variables."""

    # Server Configuration
    PROJECT_NAME: str = "Multimodal AI Companion"
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Groq LPU Settings (Ultra-Fast Inference)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"

    # Google Gemini Settings
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"

    # LLM Settings (NVIDIA API / OpenAI compatible)
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL_NAME: str = "meta/llama-3.2-11b-vision-instruct"
    
    # New Reasoning Specific Settings
    NVIDIA_REASONING_API_KEY: str = ""
    NVIDIA_REASONING_MODEL_NAME: str = "nvidia/nemotron-3-ultra-550b-a55b"
    
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"

    # Audio Recognition & Synthesis Settings (Phase 3 & Phase 4)
    WHISPER_MODEL_SIZE: str = "tiny.en"
    EDGE_TTS_VOICE: str = "en-IN-PrabhatNeural"
    TTS_VOICE: str = "en-IN-PrabhatNeural"

    _backend_dir = Path(__file__).resolve().parent.parent.parent
    _project_root = _backend_dir.parent

    model_config = SettingsConfigDict(
        env_file=(
            str(_backend_dir / ".env"),
            str(_project_root / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
