import os

from .openai_compatible import OpenAICompatibleProvider


def build_openrouter_provider(request_timeout_seconds: float) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
        request_timeout_seconds=request_timeout_seconds,
        extra_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://veeraops-ecommerce.example.com"),
            "X-Title": "VeeraOps E-Commerce Assistant",
        },
    )
