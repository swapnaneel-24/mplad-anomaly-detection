"""No-leakage tests (PR-04 §16, AC-04-16).

Verifies that no credentials, session tokens, raw passwords or cookies
leak into logs or committed files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tests.conftest import get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class TestNoLogLeakage:
    def test_full_auth_flow_leaks_nothing_into_logs(
        self, auth_client, user_factory, caplog
    ):
        user_factory("alice", PASSWORD, role="reviewer")
        with caplog.at_level(logging.INFO):
            get_csrf_token(auth_client)
            login(auth_client, "alice", PASSWORD)
            auth_client.get("/api/v1/auth/me")
            # A failing login too (worst case for sensitive logging).
            login(auth_client, "alice", "wrong-password-attempt")
            csrf = get_csrf_token(auth_client)
            auth_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

        session_token = auth_client.cookies.get("peiars_session") or ""
        csrf_token = auth_client.cookies.get("peiars_csrf") or ""
        secrets = [s for s in (PASSWORD, "wrong-password-attempt", session_token, csrf_token) if s]

        for record in caplog.records:
            message = record.getMessage()
            rendered = str(record.__dict__)
            for secret in secrets:
                assert secret not in message, f"secret leaked into log message: {record.name}"
                assert secret not in rendered, f"secret leaked into record: {record.name}"

    def test_password_never_in_any_response(self, auth_client, user_factory):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        for response in (
            auth_client.get("/api/v1/auth/me"),
            auth_client.get("/api/v1/meta"),
            auth_client.get("/openapi.json"),
            auth_client.get("/api/v1/health/ready"),
        ):
            assert PASSWORD not in response.text
            assert "password_hash" not in response.text


class TestNoCommittedSecrets:
    def test_backend_sources_contain_no_password_literals(self):
        """Application and script sources contain no credential-shaped
        string literals (a password-like name assigned a real value)."""
        import re

        pattern = re.compile(
            r"(?i)\b(password|passwd|secret|token)\b\s*[:=]\s*[\"'][^\"'\n]{8,}[\"']"
        )
        scan_roots = [BACKEND_ROOT / "app", BACKEND_ROOT / "scripts"]
        for root in scan_roots:
            for path in root.rglob("*.py"):
                if "__pycache__" in str(path):
                    continue
                text = path.read_text(encoding="utf-8")
                match = pattern.search(text)
                assert match is None, (
                    f"credential-shaped literal in {path}: {match.group(0)!r}"
                )

    def test_fixture_passwords_absent_from_production_sources(self):
        scan_roots = [BACKEND_ROOT / "app", BACKEND_ROOT / "scripts"]
        for root in scan_roots:
            for path in root.rglob("*.py"):
                if "__pycache__" in str(path):
                    continue
                text = path.read_text(encoding="utf-8")
                for fixture_secret in (
                    "correct-horse-battery-staple",
                    "bootstrap-root-password",
                    "a-strong-bootstrap-password",
                    "test-session-secret-0123456789abcdef",
                ):
                    assert fixture_secret not in text, f"{fixture_secret!r} in {path}"

    def test_env_example_contains_placeholders_only(self):
        """The committed .env.example has placeholders, never real values."""
        env_example = BACKEND_ROOT.parent / ".env.example"
        text = env_example.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("PEIARS_SESSION_SECRET="):
                assert "CHANGE_ME" in line
            if line.startswith("PEIARS_DB_PASSWORD="):
                assert "CHANGE_ME" in line

    def test_dummy_hash_is_documented_non_credential(self):
        """The only embedded hash in source is the timing-equalization dummy,
        which corresponds to no usable account credential."""
        from app.auth.passwords import DUMMY_HASH, verify_password

        assert verify_password(DUMMY_HASH, "password") is False
        assert verify_password(DUMMY_HASH, PASSWORD) is False
        assert verify_password(DUMMY_HASH, "admin") is False
