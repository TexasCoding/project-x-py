"""CLI entry points for environment and config checks."""

from project_x_py.cli import check_setup, create_config, main


def test_check_setup_missing_credentials(monkeypatch, capsys):
    monkeypatch.delenv("PROJECT_X_API_KEY", raising=False)
    monkeypatch.delenv("PROJECT_X_USERNAME", raising=False)
    assert check_setup() == 1
    assert "Missing required environment variables" in capsys.readouterr().err


def test_check_setup_ok(monkeypatch, capsys):
    monkeypatch.setenv("PROJECT_X_API_KEY", "test-key")
    monkeypatch.setenv("PROJECT_X_USERNAME", "test-user")
    assert check_setup() == 0
    assert "configured" in capsys.readouterr().out


def test_create_config(capsys):
    assert create_config() == 0
    assert "api.topstepx.com" in capsys.readouterr().out


def test_main_delegates_to_check(monkeypatch):
    monkeypatch.setenv("PROJECT_X_API_KEY", "test-key")
    monkeypatch.setenv("PROJECT_X_USERNAME", "test-user")
    assert main() == 0
