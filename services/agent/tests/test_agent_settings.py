"""The configuration of the agent: models from the environment, defaults for the rest."""

import pytest

from agent.settings import Settings

REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u@h/d",
    "AGENT_SERVICE_KEY": "agent-key",
    "KB_SERVICE_KEY": "kb-key",
}


def test_the_models_default_to_haiku_for_the_fast_and_sonnet_for_the_strong_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("AGENT_MODEL_FAST", "AGENT_MODEL_STRONG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)

    settings = Settings()

    assert settings.agent_model_fast == "anthropic:claude-haiku-4-5-20251001"
    assert settings.agent_model_strong == "anthropic:claude-sonnet-5-5"
    assert settings.langfuse_host is None


def test_the_models_are_chosen_by_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("AGENT_MODEL_FAST", "openai:gpt-5-mini")
    monkeypatch.setenv("AGENT_MODEL_STRONG", "")

    settings = Settings()

    assert settings.agent_model_fast == "openai:gpt-5-mini"
    assert settings.agent_model_strong == "anthropic:claude-sonnet-5-5"


def test_the_default_models_are_ones_pydantic_ai_accepts() -> None:
    from pydantic_ai.models import infer_model

    settings = Settings.model_construct()
    for name in (settings.agent_model_fast, settings.agent_model_strong):
        # A key is only read when the model is built; a placeholder is enough to check the name.
        import os

        os.environ.setdefault("ANTHROPIC_API_KEY", "placeholder")
        assert infer_model(name).model_name in name
