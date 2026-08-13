import os

from .openai_compatible import OpenAICompatibleProvider


def build_groq_provider(request_timeout_seconds: float) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        name="groq",
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        api_key=os.getenv("GROQ_API_KEY", ""),
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        request_timeout_seconds=request_timeout_seconds,
    )
