"""
Cognition pipeline module (Faster-Whisper STT, LangChain LLM, and Edge-TTS).
"""
from .engine import CognitionEngine, get_cognition_engine

__all__ = ["CognitionEngine", "get_cognition_engine"]
