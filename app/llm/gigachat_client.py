"""GigaChat chat-model factory.

Thin wrapper that builds a configured `langchain_gigachat.GigaChat`. The token
lifecycle (fetch + refresh) is handled inside the library when `credentials` +
`scope` are passed (invariant #10) — we deliberately do NOT reimplement the manual
Lock-cache from AI-Factory.

# Adapted from ai-factory/core/routes/agent/entrypoint.py
# Reason: reuse the proven GigaChat init params (credentials / scope /
# verify_ssl_certs). The manual token cache is intentionally dropped — langchain
# refreshes the access token itself (see docs/REUSED-FROM-AI-FACTORY.md).
"""

from typing import Any

from langchain_gigachat import GigaChat

from app.config import Settings, get_settings

DEFAULT_MODEL = "GigaChat"


def build_gigachat(
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    top_p: float = 0.9,
    max_tokens: int | None = None,
    settings: Settings | None = None,
) -> GigaChat:
    """Build a configured GigaChat chat model.

    Credentials come from settings; the library handles auth/refresh. No network
    call happens here (auth is lazy on first invoke).
    """
    settings = settings or get_settings()
    if not settings.gigachat_auth_key:
        raise ValueError("GIGACHAT_AUTH_KEY is not set (see .env.example)")

    kwargs: dict[str, Any] = {
        "credentials": settings.gigachat_auth_key,
        "scope": settings.gigachat_scope,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "verify_ssl_certs": False,
        "timeout": settings.gigachat_timeout,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return GigaChat(**kwargs)
