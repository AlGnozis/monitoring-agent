"""Unit tests for app.llm.gigachat_client.

No network: GigaChat construction is inert (auth is lazy on first invoke), so we
build with a dummy credential and assert configuration only.
"""

import pytest
from langchain_gigachat import GigaChat

from app.config import Settings
from app.llm.gigachat_client import build_gigachat


def _settings() -> Settings:
    return Settings(_env_file=None, gigachat_auth_key="dummy-key")


def test_build_returns_configured_client() -> None:
    llm = build_gigachat(settings=_settings(), temperature=0.0)
    assert isinstance(llm, GigaChat)
    assert llm.temperature == 0.0
    assert llm.model == "GigaChat"


def test_missing_credentials_raises() -> None:
    with pytest.raises(ValueError, match="GIGACHAT_AUTH_KEY"):
        build_gigachat(settings=Settings(_env_file=None, gigachat_auth_key=""))
