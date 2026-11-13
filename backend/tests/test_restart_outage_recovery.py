"""PR-07A Workstream I — restart, outage and recovery (I1-I8).

One scenario test against a **test-owned** pgserver PostgreSQL instance
and a **test-owned** uvicorn subprocess:

* I1 — backend process restart preserves cases and events exactly.
* I2 — a DB-backed session survives the restart and logout still revokes.
* I3/I4 — while PostgreSQL is stopped, readiness is truthfully 503
  (both probes unavailable) and liveness stays 200.
* I5/I6 — after PostgreSQL restarts, readiness returns to 200 and no
  stale healthy state was served in between.
* I7 — the case from before the outage is readable after recovery.
* I8 — writes succeed after recovery (connection pool recovers;
  ``pool_pre_ping`` is exercised through the outage).

Isolation and resource-cleanup guarantees (PR-07A A6 + bounded-correction
audit):

* The pgserver instance is created by this module in its own temporary
  data directory and fully owned by the test — the shared session
  fixtures are never touched, and no developer Compose volume exists
  here. The data directory is removed by ``server.cleanup()`` in the
  fixture teardown (which runs on both success and failure paths because
  the fixture is ``yield``-based).
* The uvicorn process is started/stopped only by this module, on a
  free local port, with explicit SIGTERM + bounded exit waits. Its
  stdout/stderr pipes are drained via ``communicate()`` so OS pipe
  buffers cannot keep a child alive on a blocked write. The process
  handle and the httpx client(s) opened during the scenario are
  tracked in resource lists and closed in a single ``finally`` block
  that runs even when an assertion fails mid-scenario.
* The ``PEIARS_DATABASE_URL`` environment variable is scoped via
  ``pytest.MonkeyPatch.setenv``/``undo`` — the prior process
  environment is restored after the IAC migrations complete, including
  on the failure path, so the IAC URL cannot leak into later test
  modules in the same session.
* All waiting is bounded-deadline health polling — no fixed sleeps are
  used to create or assume any race window.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "correct-horse-battery-staple"
SESSION_SECRET = "pr07a-restart-test-secret-0123456789abcdef"

READY_DEADLINE_S = 60
POLL_INTERVAL_S = 0.05
EXIT_DEADLINE_S = 20


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_of(process: subprocess.Popen) -> int:
    args = process.args
    return int(args[args.index("--port") + 1])


def _wait_ready(client: httpx.Client, deadline_s: float = READY_DEADLINE_S) -> dict:
    deadline = time.monotonic() + deadline_s
    last = None
    while time.monotonic() < deadline:
        try:
            response = client.get("/api/v1/health/ready")
            last = response
            if response.status_code == 200:
                return response.json()
        except httpx.TransportError:
            pass
        time.sleep(POLL_INTERVAL_S)
    raise AssertionError(f"readiness did not return 200 within {deadline_s}s: {last!r}")


def _start_backend(env: dict) -> subprocess.Popen:
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return process


def _stop_backend(process: subprocess.Popen) -> None:
    """Stop the backend, drain its stdio pipes, and assert exit.

    Idempotent: a no-op drain if the process already exited. Uses
    ``communicate()`` (not bare ``wait()``) so the OS pipe buffers are
    drained — without this, a child blocked on a write to a full stdout
    pipe can hang indefinitely past SIGTERM.
    """
    if process.poll() is not None:
        # Already exited; drain any residual pipe content to release the
        # OS resources, but tolerate a child that exited without writing.
        try:
            process.communicate(timeout=EXIT_DEADLINE_S)
        except subprocess.TimeoutExpired:
            pass
        return
    process.terminate()
    try:
        process.communicate(timeout=EXIT_DEADLINE_S)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=EXIT_DEADLINE_S)
        except subprocess.TimeoutExpired:
            # Last-resort: the OS will reap the process when the parent
            # exits; we record that we tried. This branch has not been
            # observed in practice but is guarded for defence-in-depth.
            pass
    assert process.returncode is not None


def _client(port: int) -> httpx.Client:
    return httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10.0)


def _login(client: httpx.Client) -> dict:
    csrf_response = client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200, csrf_response.text
    csrf = csrf_response.json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "restart-reviewer", "password": PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    fresh = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": fresh}


@pytest.fixture(scope="module")
def iac_server():
    """Test-owned disposable PostgreSQL (separate from the shared one).

    The pgserver data directory is created by this fixture and removed
    by ``server.cleanup()`` in teardown. teardown runs on both success
    and failure paths because the fixture is ``yield``-based.
    """
    import pgserver

    data_dir = tempfile.mkdtemp(prefix="peiars_pr07a_iac_")
    server = pgserver.get_server(data_dir)
    server.ensure_postgres_running()
    try:
        yield server
    finally:
        # ``cleanup()`` stops the server AND removes the data directory.
        # It is invoked in ``finally`` so an assertion failure during the
        # scenario still releases the PostgreSQL data directory.
        server.cleanup()


@pytest.fixture(scope="module")
def iac_db_url(iac_server):
    from sqlalchemy import make_url

    admin_uri = iac_server.get_uri()
    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS peiars_iac"))
            conn.execute(text("CREATE DATABASE peiars_iac"))
    finally:
        admin_engine.dispose()
    url = make_url(admin_uri)
    return str(url.set(database="peiars_iac"))


@pytest.fixture(scope="module")
def iac_migrated(iac_db_url):
    """Apply migrations + create the reviewer user (module scope).

    The ``PEIARS_DATABASE_URL`` environment variable is set ONLY for the
    duration of the alembic upgrade (and the user-creation step that
    reads it back through the same engine). The prior process
    environment is restored on the way out — including the case where
    the variable was previously unset and including the failure path —
    via ``pytest.MonkeyPatch``, the same primitive pytest itself uses
    for function-scoped ``monkeypatch`` fixtures. The backend
    subprocess started later by ``_start_backend`` receives the IAC URL
    through the explicit ``iac_env`` dict, NOT through ``os.environ``,
    so restoring the parent process's environment does not affect the
    subprocess.
    """
    from alembic import command
    from alembic.config import Config

    mp = pytest.MonkeyPatch()
    try:
        mp.setenv("PEIARS_DATABASE_URL", iac_db_url)
        alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location", str(BACKEND_ROOT / "migrations")
        )
        command.upgrade(alembic_cfg, "head")

        from app.auth.passwords import hash_password
        from app.db.models import User
        from app.db.session import create_session_factory

        engine = create_engine(iac_db_url, future=True)
        try:
            factory = create_session_factory(engine)
            with factory() as session:
                user = User(
                    username="restart-reviewer",
                    password_hash=hash_password(PASSWORD),
                    display_name="Restart Reviewer",
                    role="reviewer",
                    is_active=True,
                )
                session.add(user)
                session.commit()
        finally:
            engine.dispose()
        return iac_db_url
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def iac_env(iac_server, iac_db_url, iac_migrated):
    env = os.environ.copy()
    env.update(
        {
            "PEIARS_ENVIRONMENT": "test",
            "PEIARS_DATABASE_URL": iac_db_url,
            "PEIARS_DATABASE_REQUIRED": "true",
            "PEIARS_SESSION_SECRET": SESSION_SECRET,
            "PEIARS_SESSION_COOKIE_SECURE": "false",
            "PEIARS_DEMONSTRATION_SOURCES": "true",
            "PEIARS_CORS_ORIGINS": "http://test.example",
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return env


def _pg_stop(iac_server) -> None:
    from pgserver._commands import pg_ctl

    pg_ctl(["stop", "-m", "fast", "-w"], pgdata=iac_server.pgdata, timeout=30)


def _pg_start(iac_server) -> None:
    pinfo = getattr(iac_server, "_postmaster_info", None)
    port = getattr(pinfo, "port", None)
    socket_dir = getattr(pinfo, "socket_dir", None)
    if socket_dir is None and port is not None:
        from pgserver._commands import pg_ctl

        log_path = str(iac_server.pgdata / "log")
        pg_ctl(
            ["start", "-w", "-o", f'-h "127.0.0.1" -p {port}', "-l", log_path],
            pgdata=iac_server.pgdata,
            timeout=30,
        )
        return
    iac_server.ensure_postgres_running()


class TestRestartOutageRecovery:
    def test_full_scenario(self, iac_server, iac_env):
        # Resource tracking: every backend process and httpx client opened
        # during the scenario is appended to these lists so a single
        # ``finally`` block (which runs even when an assertion fails
        # mid-scenario) can close every client and stop every process.
        processes: list[subprocess.Popen] = []
        clients: list[httpx.Client] = []
        try:
            # --- Boot the backend and wait until ready (I-series pre-state).
            process = _start_backend(iac_env)
            processes.append(process)
            client = _client(_port_of(process))
            clients.append(client)
            ready = _wait_ready(client)
            assert ready["status"] == "ready"

            # --- I2 (pre-restart): log in; the session is DB-backed.
            headers = _login(client)
            me = client.get("/api/v1/auth/me")
            assert me.status_code == 200, me.text

            # --- I1 (pre-restart): create the case and three events.
            created = client.post(
                "/api/v1/cases",
                json={
                    "dataset_id": "synthetic-demonstration",
                    "snapshot_id": "synthetic-v1",
                    "record_ref": "synth-001",
                    "title": "restart-persistence",
                    "created_by": "ignored",
                },
                headers=headers,
            )
            assert created.status_code == 201, created.text
            case_id = created.json()["id"]
            case_pre = created.json()

            assert (
                client.post(
                    f"/api/v1/cases/{case_id}/notes",
                    json={
                        "note_text": "before restart",
                        "actor_ref": "ignored",
                        "expected_version": 1,
                    },
                    headers=headers,
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/api/v1/cases/{case_id}/transitions",
                    json={
                        "to_status": "under_review",
                        "reason": "before restart",
                        "actor_ref": "ignored",
                        "expected_version": 2,
                    },
                    headers=headers,
                ).status_code
                == 200
            )
            history_pre = client.get(f"/api/v1/cases/{case_id}/history").json()
            assert history_pre["total"] == 3

            # --- I1: clean process restart.
            # Stop the first backend; its client is closed in ``finally``.
            # The pre-restart cookies are captured BEFORE the client is
            # closed so the post-restart client can re-use them.
            pre_restart_cookies = dict(client.cookies)
            _stop_backend(process)
            process = _start_backend(iac_env)
            processes.append(process)
            client = _client(_port_of(process))
            clients.append(client)
            # I2 scenario: the same browser keeps its cookies; the session
            # is DB-backed and must survive the backend process restart.
            client.cookies.update(pre_restart_cookies)
            ready = _wait_ready(client)
            assert ready["status"] == "ready"

            detail = client.get(f"/api/v1/cases/{case_id}")
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["id"] == case_pre["id"]
            assert body["version"] == 3
            assert body["status"] == "under_review"
            assert body["record_ref"] == case_pre["record_ref"]
            assert body["dataset_id"] == case_pre["dataset_id"]
            assert body["snapshot_id"] == case_pre["snapshot_id"]

            history_post = client.get(f"/api/v1/cases/{case_id}/history").json()
            assert history_post["total"] == history_pre["total"]
            assert [e["id"] for e in history_post["items"]] == [
                e["id"] for e in history_pre["items"]
            ]
            assert [e["event_type"] for e in history_post["items"]] == [
                e["event_type"] for e in history_pre["items"]
            ]
            assert [e["case_version"] for e in history_post["items"]] == [
                e["case_version"] for e in history_pre["items"]
            ]

            # --- I2: the pre-restart session still authorizes (DB-backed)...
            me = client.get("/api/v1/auth/me")
            assert me.status_code == 200, me.text

            # --- I3/I4: database outage → truthful unready, live stays 200.
            _pg_stop(iac_server)

            deadline = time.monotonic() + 30
            saw_unready = False
            while time.monotonic() < deadline:
                ready_response = client.get("/api/v1/health/ready")
                if ready_response.status_code == 503:
                    saw_unready = True
                    payload = ready_response.json()
                    checks = {c["name"]: c["status"] for c in payload.get("checks", [])}
                    assert all(s != "ready" for s in checks.values()), checks
                    break
                time.sleep(POLL_INTERVAL_S)
            assert saw_unready, "readiness never reported the database outage"

            live = client.get("/api/v1/health/live")
            assert live.status_code == 200

            # No stale healthy state while the database is down.
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                assert client.get("/api/v1/health/ready").status_code == 503
                time.sleep(POLL_INTERVAL_S)

            # --- I5/I6: recovery restores readiness (bounded polling).
            _pg_start(iac_server)
            ready = _wait_ready(client)
            assert ready["status"] == "ready"

            # --- I7: the case is available after recovery.
            detail = client.get(f"/api/v1/cases/{case_id}")
            assert detail.status_code == 200
            assert detail.json()["version"] == 3

            # --- I8: writes work again (pool recovered through the outage).
            note = client.post(
                f"/api/v1/cases/{case_id}/notes",
                json={
                    "note_text": "after recovery",
                    "actor_ref": "ignored",
                    "expected_version": 3,
                },
                headers=headers,
            )
            assert note.status_code == 200, note.text
            assert note.json()["version"] == 4

            # --- I2 (post-restart): logout still revokes the session.
            logout = client.post("/api/v1/auth/logout", headers=headers)
            assert logout.status_code == 200, logout.text
            assert client.get("/api/v1/auth/me").status_code == 401
        finally:
            # Close every httpx client opened during the scenario. Each
            # ``httpx.Client`` owns a connection pool that should be
            # released deterministically rather than awaiting GC.
            for c in clients:
                try:
                    c.close()
                except Exception:
                    pass
            # Stop every backend process in reverse order of creation.
            # ``_stop_backend`` is idempotent: calling it on a process
            # that already exited (e.g. the first one stopped explicitly
            # before the restart) just drains its pipe and returns.
            for p in reversed(processes):
                try:
                    _stop_backend(p)
                except Exception:
                    pass
