import os

from app.config import ConfigLoader


class TestLLMConfigDefaults:
    def test_llm_disabled_by_default(self) -> None:
        cfg = ConfigLoader.load()
        assert cfg.llm.enabled is False

    def test_llm_has_default_model(self) -> None:
        cfg = ConfigLoader.load()
        assert cfg.llm.default_model == "deepseek-v4-flash"

    def test_llm_has_system_prompt(self) -> None:
        cfg = ConfigLoader.load()
        assert "genshen" in cfg.llm.system_prompt


class TestLLMConfigEnvOverrides:
    def test_env_enabled(self) -> None:
        cfg = ConfigLoader.load(environ={"APP_LLM_ENABLED": "true"})
        assert cfg.llm.enabled is True

    def test_env_api_key(self) -> None:
        cfg = ConfigLoader.load(environ={"APP_LLM_API_KEY": "sk-test"})
        assert cfg.llm.api_key == "sk-test"

    def test_env_model(self) -> None:
        cfg = ConfigLoader.load(environ={
            "APP_LLM_DEFAULT_MODEL": "deepseek-v4-pro",
            "APP_LLM_UPGRADE_MODEL": "deepseek-v4-flash",
        })
        assert cfg.llm.default_model == "deepseek-v4-pro"
        assert cfg.llm.upgrade_model == "deepseek-v4-flash"

    def test_env_temperature_float(self) -> None:
        cfg = ConfigLoader.load(environ={"APP_LLM_TEMPERATURE": "0.3"})
        assert cfg.llm.temperature == 0.3

    def test_env_invalid_temperature_raises(self) -> None:
        from app.errors import ConfigError
        import pytest
        with pytest.raises(ConfigError):
            ConfigLoader.load(environ={"APP_LLM_TEMPERATURE": "not-a-number"})
