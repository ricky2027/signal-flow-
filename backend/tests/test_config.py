from pathlib import Path

import pytest

from app.config import Settings


@pytest.mark.parametrize("scheme", ["postgresql", "postgres", "postgresql+psycopg"])
def test_neon_url_uses_psycopg_and_preserves_tls(scheme):
    config = Settings(
        database_url=f"{scheme}://user:p%40ss@host/db?sslmode=require&channel_binding=require",
        _env_file=None,
    )
    assert config.database_url == (
        "postgresql+psycopg://user:p%40ss@host/db?sslmode=require&channel_binding=require"
    )
    assert "p%40ss" not in repr(config)


def test_env_file_resolves_independently_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    env_path = Settings.model_config["env_file"]
    assert Path(env_path).is_absolute()
    assert env_path == Path(__file__).resolve().parents[1] / ".env"


def test_process_environment_retains_precedence(monkeypatch, tmp_path):
    file = tmp_path / "settings.env"
    file.write_text("OPENAI_API_KEY=file-fixture\n")
    monkeypatch.setenv("OPENAI_API_KEY", "process-fixture")
    assert Settings(_env_file=file).openai_api_key.get_secret_value() == "process-fixture"
