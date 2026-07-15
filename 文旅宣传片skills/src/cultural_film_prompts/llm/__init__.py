"""LLM 适配层。"""

from .client import LLMClient, LLMResponse, structured_call

__all__ = [
    "LLMClient",
    "LLMResponse",
    "structured_call",
]
