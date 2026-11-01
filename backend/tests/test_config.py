import pytest

from life200.core.config import Settings


def test_settings_read_prefixed_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFE200_ENV", "test")
    monkeypatch.setenv("LIFE200_ANTHROPIC_API_KEY", "sk-secret")

    settings = Settings(_env_file=None)

    assert settings.env == "test"
    assert settings.anthropic_api_key is not None
    assert "sk-secret" not in repr(settings)  # SecretStr keeps keys out of logs
    assert settings.anthropic_api_key.get_secret_value() == "sk-secret"
