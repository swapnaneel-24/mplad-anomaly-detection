"""Bootstrap CLI tests (PR-04 §11).

The CLI is exercised through its ``main()`` with a controlled environment
(password via the documented env var; interactive prompts are avoided in
tests). A dedicated disposable database is used so no real data is
touched.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.usefixtures("pg_server")


@pytest.fixture()
def cli_db_url(pg_server):
    """A disposable database with migrations applied for CLI runs."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    admin_uri = pg_server.get_uri()
    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    db_name = f"peiars_cli_{uuid.uuid4().hex[:8]}"
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin_engine.dispose()

    from sqlalchemy import make_url

    url = str(make_url(admin_uri).set(database=db_name))

    backend_root = Path(__file__).resolve().parents[1]
    os.environ["PEIARS_DATABASE_URL"] = url
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    command.upgrade(cfg, "head")

    yield url

    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
        ))
        conn.execute(text(f"DROP DATABASE {db_name}"))
    admin_engine.dispose()


def _run_cli(monkeypatch, argv: list[str], password_env: str | None):
    """Load the CLI module and invoke its main() under a controlled argv/env."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "create_admin.py"
    spec = importlib.util.spec_from_file_location("create_admin_under_test", script)
    module = importlib.util.module_from_spec(spec)

    monkeypatch.setattr("sys.argv", ["create_admin.py", *argv])
    if password_env is None:
        monkeypatch.delenv("PEIARS_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("PEIARS_BOOTSTRAP_ADMIN_PASSWORD", password_env)

    spec.loader.exec_module(module)
    module.main()
    return module


class TestCreateAdmin:
    def test_creates_active_administrator(self, cli_db_url, monkeypatch, capsys):
        _run_cli(
            monkeypatch,
            ["--username", "admin", "--display-name", "Administrator"],
            "a-strong-bootstrap-password",
        )
        out = capsys.readouterr().out
        assert "created successfully" in out
        # The password is never displayed.
        assert "a-strong-bootstrap-password" not in out

        engine = create_engine(cli_db_url)
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT role, is_active, password_hash FROM users WHERE username = 'admin'"
            )).fetchone()
        assert row is not None
        assert row[0] == "admin"
        assert row[1] is True
        assert row[2].startswith("$argon2id$")
        engine.dispose()

    def test_refuses_duplicate_bootstrap(self, cli_db_url, monkeypatch, capsys):
        _run_cli(
            monkeypatch,
            ["--username", "admin", "--display-name", "Administrator"],
            "a-strong-bootstrap-password",
        )
        with pytest.raises(SystemExit):
            _run_cli(
                monkeypatch,
                ["--username", "admin", "--display-name", "Administrator"],
                "another-password-attempt",
            )

    def test_refuses_short_password(self, cli_db_url, monkeypatch):
        with pytest.raises(SystemExit):
            _run_cli(
                monkeypatch,
                ["--username", "admin", "--display-name", "Administrator"],
                "short",  # < 8 chars
            )
        engine = create_engine(cli_db_url)
        with engine.connect() as conn:
            count = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
        assert count == 0
        engine.dispose()

    def test_refuses_without_database_url(self, monkeypatch):
        monkeypatch.delenv("PEIARS_DATABASE_URL", raising=False)
        with pytest.raises(SystemExit):
            _run_cli(
                monkeypatch,
                ["--username", "admin", "--display-name", "Administrator"],
                "a-strong-bootstrap-password",
            )

    def test_created_admin_can_log_in(self, cli_db_url, monkeypatch, auth_settings):
        """End-to-end: the bootstrapped admin can authenticate via the API."""
        from fastapi.testclient import TestClient

        from app.db.session import DatabaseSessionFactory
        from app.main import create_app
        from tests.conftest import get_csrf_token

        _run_cli(
            monkeypatch,
            ["--username", "root", "--display-name", "Root Admin"],
            "bootstrap-root-password",
        )
        # Point a fresh app at the CLI database.
        settings = auth_settings.model_copy(update={"database_url": cli_db_url})
        app = create_app(
            settings=settings,
            db_session_factory_override=DatabaseSessionFactory.from_settings(settings),
        )
        client = TestClient(app)
        csrf = get_csrf_token(client)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": "bootstrap-root-password"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"
