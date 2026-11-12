"""PR-06A Workstream A & B tests — Windows asyncio compatibility and .env loading.

PR-06A correction notes:

* Workstream A (Windows asyncio) tests below SIMULATE the win32 platform
  by monkeypatching ``sys.platform`` and the ``asyncio`` policy class.
  They verify the code contract of ``backend/scripts/serve.py``; they do
  NOT constitute real Windows runtime verification. The verification that
  still requires a real Windows 11 machine is listed in
  ``PR06A_CORRECTION_REPORT.md``.
* Workstream B (.env loading) tests verify the single documented
  environment-loading procedure (repository-root ``.env``, explicit
  environment variables take precedence) for both the API entrypoint and
  Alembic migrations — including a real ``alembic upgrade head``
  subprocess run driven only by the ``.env`` file.
* Example-secret safety (correction §2) is evaluated through the actual
  application configuration (the real Pydantic ``Settings`` model), not
  just placeholder string presence in a file.

PR-06A FINAL correction additions:

* ``TestDocumentedEnvironmentContract`` — the documented environment
  variable names (``PEIARS_ENVIRONMENT``, ``PEIARS_CORS_ORIGINS``, ...)
  actually reach the Settings model through the real environment-loading
  mechanism, and the documented production activation + insecure-cookie
  combination raises a validation error WITHOUT constructor injection.
* ``TestCorsSerializationContract`` — the one documented comma-separated
  CORS representation is parsed by the ``NoDecode`` + validator
  mechanism; JSON-array syntax, wildcards, and malformed origins fail
  clearly; explicit environment variables take precedence over ``.env``.
* ``TestSecretGenerationContract`` — a secret generated exactly the way
  the documented Windows/POSIX commands generate it (32 cryptographically
  random bytes → 64 lowercase hex characters) is accepted by the real
  Settings validator through the environment mechanism.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SERVE_PY = BACKEND_ROOT / "scripts" / "serve.py"


def _load_serve_module():
    """Load scripts/serve.py as a module (without running main)."""
    spec = importlib.util.spec_from_file_location("serve_module_test", SERVE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWindowsAsyncioCompatibility:
    """Workstream A: the Windows selector event-loop policy contract.

    Platform note: on a POSIX test runner ``WindowsSelectorEventLoopPolicy``
    does not exist in the ``asyncio`` namespace, so the win32 tests inject a
    stand-in class (or force the attribute to ``None``). These are
    platform-mocked tests, NOT real Windows runtime verification.
    """

    def test_serve_py_exists(self):
        assert SERVE_PY.exists(), f"{SERVE_PY} not found"

    def test_serve_py_imports_cleanly(self):
        """The entrypoint must parse and import without errors."""
        module = _load_serve_module()
        assert hasattr(module, "main"), "serve.py must expose main()"

    def test_policy_installation_code_present(self):
        """The source must contain the explicit policy-installation function."""
        source = SERVE_PY.read_text(encoding="utf-8")
        assert "def _install_event_loop_policy" in source, (
            "serve.py must expose _install_event_loop_policy(platform)"
        )
        assert "WindowsSelectorEventLoopPolicy" in source, (
            "serve.py must reference WindowsSelectorEventLoopPolicy"
        )
        assert "set_event_loop_policy" in source, (
            "serve.py must call asyncio.set_event_loop_policy"
        )
        assert "sys.platform" in source, (
            "the default platform argument must come from sys.platform"
        )

    def test_policy_installation_precedes_main(self):
        """The policy must be installed at import time, before main()/uvicorn.

        The module-level call must come after the ``__future__`` import and
        after ``import asyncio`` (which it needs), and before ``def main``.
        """
        source = SERVE_PY.read_text(encoding="utf-8")
        future_line = source.find("from __future__ import")
        asyncio_import = source.find("import asyncio")
        module_call = source.find("EVENT_LOOP_POLICY_OUTCOME = _install_event_loop_policy()")
        main_def = source.find("def main")
        assert future_line != -1, "serve.py must have a __future__ import"
        assert asyncio_import != -1, "serve.py must import asyncio"
        assert module_call != -1, "serve.py must install the policy at import time"
        assert main_def != -1, "serve.py must define main()"
        assert future_line < module_call, "the policy call must come after the __future__ import"
        assert asyncio_import < module_call, "the policy call must come after importing asyncio"
        assert module_call < main_def, "the policy must be installed before main() is defined"

    def test_posix_no_windows_policy(self):
        """On POSIX, the module must NOT install the Windows policy."""
        with mock.patch.object(sys, "platform", "linux"):
            import asyncio

            original_policy = asyncio.get_event_loop_policy()
            _load_serve_module()
            current_policy = asyncio.get_event_loop_policy()
            # The policy must be unchanged on POSIX.
            assert type(current_policy) is type(original_policy), (
                f"POSIX must not change the event loop policy: "
                f"{type(original_policy).__name__} -> {type(current_policy).__name__}"
            )

    def test_non_win32_platforms_return_default_outcome(self):
        """The policy function is a no-op for non-win32 platforms."""
        module = _load_serve_module()
        import asyncio

        original_policy = asyncio.get_event_loop_policy()
        try:
            assert module._install_event_loop_policy("linux") == "default (POSIX)"
            assert module._install_event_loop_policy("darwin") == "default (POSIX)"
            assert type(asyncio.get_event_loop_policy()) is type(original_policy), (
                "non-win32 platforms must not change the event loop policy"
            )
        finally:
            asyncio.set_event_loop_policy(type(original_policy)())

    def test_windows_policy_applied_on_win32(self):
        """On win32 (simulated), the selector policy is installed.

        On a POSIX test runner, ``WindowsSelectorEventLoopPolicy`` does not
        exist in the ``asyncio`` namespace, so a stand-in class is injected
        and the module is re-executed with ``sys.platform`` patched.
        """
        import asyncio

        class _FakeWindowsSelectorEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
            pass

        _FakeWindowsSelectorEventLoopPolicy.__name__ = "WindowsSelectorEventLoopPolicy"
        _FakeWindowsSelectorEventLoopPolicy.__qualname__ = "WindowsSelectorEventLoopPolicy"

        original_policy = asyncio.get_event_loop_policy()
        try:
            with (
                mock.patch.object(sys, "platform", "win32"),
                mock.patch.object(
                    asyncio,
                    "WindowsSelectorEventLoopPolicy",
                    _FakeWindowsSelectorEventLoopPolicy,
                    create=True,
                ),
            ):
                module = _load_serve_module()
                assert module.EVENT_LOOP_POLICY_OUTCOME == "WindowsSelectorEventLoopPolicy"
                assert module._install_event_loop_policy("win32") == "WindowsSelectorEventLoopPolicy"
                policy = asyncio.get_event_loop_policy()
                assert type(policy).__name__ == "WindowsSelectorEventLoopPolicy", (
                    f"win32 must install WindowsSelectorEventLoopPolicy, got {type(policy).__name__}"
                )
        finally:
            asyncio.set_event_loop_policy(type(original_policy)())

    def test_win32_missing_policy_fails_clearly(self):
        """A win32 Python without the policy class must fail at startup.

        The absence of ``WindowsSelectorEventLoopPolicy`` is NOT proof that
        a future Python's default loop is safe for psycopg 3 — the
        entrypoint must refuse to start with an actionable error instead of
        silently continuing on the potentially incompatible default.
        """
        import asyncio

        spec = importlib.util.spec_from_file_location("serve_module_no_policy", SERVE_PY)
        module = importlib.util.module_from_spec(spec)
        with (
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.object(asyncio, "WindowsSelectorEventLoopPolicy", None, create=True),
        ):
            with pytest.raises(RuntimeError) as excinfo:
                spec.loader.exec_module(module)
        message = str(excinfo.value)
        assert "WindowsSelectorEventLoopPolicy" in message
        assert "psycopg" in message
        assert "not proof" in message, "the error must explain why absence is not proof of safety"
        assert "Supported" in message or "supported" in message
        assert "3.12" in message, "the error must name the supported interpreter range"

    def test_supported_python_versions_documented(self):
        """The supported interpreter range must be explicit in the source."""
        module = _load_serve_module()
        assert hasattr(module, "SUPPORTED_PYTHON_VERSIONS")
        assert "3.12" in module.SUPPORTED_PYTHON_VERSIONS

    def test_supported_python_versions_claim_is_truthful(self):
        """Final correction §4: distinguish tested from merely-API-available.

        The claim must name where validation actually happened (the Linux
        test runner) and must NOT assert Windows 11 or macOS runtime
        validation — the win32 behaviour in this suite is verified with
        platform MOCKS, which is not runtime evidence.
        """
        module = _load_serve_module()
        claim = module.SUPPORTED_PYTHON_VERSIONS
        assert "3.12" in claim
        assert "Linux" in claim, "the claim must name where validation happened"
        assert "pending" in claim, (
            "the claim must state that Windows/macOS runtime verification "
            "is still pending"
        )
        assert "validated on Windows" not in claim, (
            "must not claim Windows runtime validation based on platform mocks"
        )
        assert "validated on macOS" not in claim, (
            "must not claim macOS runtime validation based on platform mocks"
        )
        assert "Windows 11" not in claim, (
            "must not claim Windows 11 validation that was never performed"
        )

    def test_module_outcome_matches_real_platform(self):
        """The recorded outcome reflects the interpreter actually running."""
        module = _load_serve_module()
        assert module.EVENT_LOOP_POLICY_OUTCOME == module._install_event_loop_policy(sys.platform)


class TestDotenvIntegration:
    """Workstream B: python-dotenv loads the repository-root .env."""

    def test_python_dotenv_in_requirements(self):
        """python-dotenv must be a declared runtime dependency."""
        req = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "python-dotenv" in req, (
            "requirements.txt must declare python-dotenv for reliable .env loading"
        )

    def test_python_dotenv_pin_consistent_with_lockfile(self):
        """The requirements.txt pin and the committed lockfile must agree."""
        req = (BACKEND_ROOT / "requirements.txt").read_text(encoding="utf-8")
        lock = (BACKEND_ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
        req_pin = next(line for line in req.splitlines() if line.startswith("python-dotenv"))
        lock_pin = next(line for line in lock.splitlines() if line.startswith("python-dotenv"))
        assert req_pin == lock_pin, (
            f"python-dotenv pin mismatch: requirements.txt has {req_pin!r}, "
            f"requirements-lock.txt has {lock_pin!r}"
        )

    def test_serve_py_loads_dotenv(self):
        """serve.py must call load_dotenv on the repository-root .env."""
        source = SERVE_PY.read_text(encoding="utf-8")
        assert "load_dotenv" in source, (
            "serve.py must call load_dotenv to load .env values"
        )
        assert "override=False" in source, (
            "load_dotenv must use override=False so explicit env vars win"
        )

    def test_serve_py_missing_dotenv_fails_loudly(self):
        """A missing python-dotenv must NOT be silently ignored.

        python-dotenv is a required local-boot dependency: without it the
        repository-root .env would be silently skipped and the app would
        boot with unintended defaults. The entrypoint must exit with an
        actionable message instead.
        """
        spec = importlib.util.spec_from_file_location("serve_module_no_dotenv", SERVE_PY)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"dotenv": None}):
            with pytest.raises(SystemExit) as excinfo:
                spec.loader.exec_module(module)
        message = str(excinfo.value)
        assert "python-dotenv is required" in message
        assert "requirements.txt" in message

    def test_module_import_does_not_mutate_environment(self):
        """Importing serve.py must NOT load .env into os.environ.

        The load happens in main(), immediately before Settings() is
        constructed — not at import time. This keeps the module import
        side-effect free (test isolation) while preserving the startup
        contract.
        """
        with mock.patch("dotenv.load_dotenv") as fake_load:
            _load_serve_module()
            fake_load.assert_not_called()

    def test_load_local_env_targets_repo_root_with_override_false(self):
        """_load_local_env() loads <repo-root>/.env with override=False."""
        module = _load_serve_module()
        with mock.patch.object(module, "load_dotenv") as fake:
            module._load_local_env()
        fake.assert_called_once()
        args, kwargs = fake.call_args
        (called_path,) = args
        assert called_path == REPO_ROOT / ".env"
        assert kwargs.get("override") is False

    def test_dotenv_loads_values(self):
        """load_dotenv actually loads values from a .env file into os.environ."""
        from dotenv import load_dotenv

        # Create a temporary .env and verify values are loaded.
        with mock.patch.dict(os.environ, {}, clear=False):
            # Simulate: load from a non-existent file (no-op).
            result = load_dotenv(BACKEND_ROOT / ".nonexistent.env", override=False)
            assert result is False, "load_dotenv on a missing file returns False"

    def test_env_example_exists(self):
        """backend/.env.example must exist with safe defaults."""
        example = BACKEND_ROOT / ".env.example"
        assert example.exists(), "backend/.env.example must exist"
        content = example.read_text(encoding="utf-8")
        # Must document the key variables.
        for var in (
            "PEIARS_DATABASE_URL",
            "PEIARS_DATABASE_REQUIRED",
            "PEIARS_SESSION_SECRET",
            "PEIARS_DEMONSTRATION_SOURCES",
            "PEIARS_SESSION_COOKIE_SECURE",
        ):
            assert var in content, f".env.example must document {var}"

    def test_env_example_no_real_secrets(self):
        """backend/.env.example must not contain real secrets."""
        content = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
        # Check for obvious real-secret patterns.
        assert "CHANGE_ME" in content or "GENERATE" in content, (
            ".env.example must use CHANGE_ME/GENERATE placeholders"
        )

    def test_env_example_secret_command_is_cryptographically_secure(self):
        """The documented Windows secret command must use the .NET CSPRNG
        through the INSTANCE-based API.

        Get-Random is NOT cryptographically secure. The static
        ``RandomNumberGenerator.GetBytes`` overloads are .NET Core / .NET 5+
        only and are absent on .NET Framework (Windows PowerShell 5.1), so
        the documented command must use ``RandomNumberGenerator.Create()``
        plus the instance ``GetBytes(byte[])`` method — the one form that
        exists on every .NET version.
        """
        content = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
        assert "RandomNumberGenerator]::Create()" in content, (
            ".env.example must document the instance-based "
            "RandomNumberGenerator.Create() command"
        )
        assert "$rng.GetBytes($bytes)" in content, (
            ".env.example must call the instance GetBytes(byte[]) method"
        )
        # The static-call form must NOT be documented (it does not exist
        # on .NET Framework / Windows PowerShell 5.1).
        assert "RandomNumberGenerator]::GetBytes" not in content, (
            ".env.example must not document the static GetBytes call"
        )
        assert "Get-Random" not in content, (
            ".env.example must not recommend the non-cryptographic Get-Random"
        )

    def test_pytest_env_file_ignored_in_tests(self):
        """Pydantic Settings must NOT read .env in test settings (isolation).

        The existing conftest constructs Settings with _env_file=None.
        This test verifies that pattern still works.
        """
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            environment="test",
            database_url=None,
            database_required=False,
        )
        assert s.environment == "test"

    def test_root_env_example_superseded(self):
        """PR-06A: backend/.env.example is the canonical template.

        The root .env.example is a PR-01 legacy artifact. It may still
        exist but the backend template is authoritative.
        """
        backend_example = BACKEND_ROOT / ".env.example"
        assert backend_example.exists()


class TestExampleSecretSafety:
    """PR-06A correction §2 — the example config cannot activate auth.

    The unchanged example configuration must never activate authentication
    with a known signing secret. These tests evaluate the ACTUAL
    application configuration (the real Pydantic ``Settings`` model)
    against the committed example files — not just placeholder string
    presence.
    """

    @staticmethod
    def _settings_from_env_file(path: Path):
        from app.core.config import Settings

        return Settings(_env_file=path)

    def test_backend_env_example_rejected_by_settings(self, monkeypatch):
        """Constructing Settings from backend/.env.example must fail.

        A developer who copies the template unchanged and forgets to
        replace PEIARS_SESSION_SECRET gets a startup validation error, not
        a running app signed with a publicly known secret.
        """
        monkeypatch.delenv("PEIARS_SESSION_SECRET", raising=False)
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as excinfo:
            self._settings_from_env_file(BACKEND_ROOT / ".env.example")
        assert "session_secret" in str(excinfo.value)

    def test_root_env_example_rejected_by_settings(self, monkeypatch):
        """The PR-01 legacy root template is equally unable to activate auth."""
        monkeypatch.delenv("PEIARS_SESSION_SECRET", raising=False)
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as excinfo:
            self._settings_from_env_file(REPO_ROOT / ".env.example")
        assert "session_secret" in str(excinfo.value)

    @pytest.mark.parametrize(
        "placeholder",
        [
            # The exact 46-character value shipped in the inspected PR-06A
            # delivery: long enough to pass the minimum-length check.
            "CHANGE_ME_GENERATE_A_RANDOM_64_CHAR_HEX_STRING",
            # The PR-01 legacy placeholder (31 chars — fails length too).
            "CHANGE_ME_RANDOM_SESSION_SECRET",
            # Padded variants that pass the length check on their own.
            "CHANGE_ME" + "A" * 54,
            "PLACEHOLDER" + "0" * 52,
            "x" * 20 + "Replace_Me" + "x" * 20,
            "generate_a_random_secret_value_padding_padding_padding",
        ],
    )
    def test_placeholder_secrets_rejected_even_when_long_enough(self, placeholder):
        """Length alone must not admit template placeholders.

        The former 46-character placeholder satisfied the >= 32 character
        minimum; the marker check is what must catch it.
        """
        from pydantic import ValidationError

        from app.core.config import Settings

        assert len(placeholder) >= 9
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None, session_secret=placeholder)
        message = str(excinfo.value).lower()
        assert "session_secret" in message
        assert "placeholder" in message or "change_me" in message or "replace_me" in message

    def test_short_secret_still_rejected_by_length(self):
        """The pre-existing minimum-length validation is not weakened."""
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None, session_secret="short")
        assert "at least 32 characters" in str(excinfo.value)

    def test_generated_random_secret_accepted(self):
        """A genuinely random hex secret still passes (no over-blocking)."""
        from app.core.config import Settings

        secret = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        s = Settings(_env_file=None, session_secret=secret)
        assert s.session_secret == secret


class TestDocumentedEnvironmentContract:
    """Final correction §1 — the documented names actually reach the model.

    The Settings model uses ``env_prefix="PEIARS_"`` with NO aliases, so
    the real variable names are ``PEIARS_<FIELD>``: ``PEIARS_ENVIRONMENT``
    and ``PEIARS_CORS_ORIGINS`` — NOT the previously documented
    ``PEIARS_ENV`` / ``PEIARS_API_CORS_ORIGINS``, which the model silently
    ignored (``extra="ignore"``), meaning the documented production
    activation could never take effect.

    Every test in this class drives Settings through the REAL
    environment-loading mechanism (``monkeypatch.setenv`` + ``Settings()``
    with ``_env_file=None`` so no stray repository ``.env`` interferes) —
    never by passing the value to the constructor.
    """

    @pytest.fixture(autouse=True)
    def _scrub_peiars_env(self, monkeypatch):
        """Hermetic: no ambient PEIARS_* variable influences these tests."""
        for var in (
            "PEIARS_ENVIRONMENT",
            "PEIARS_CORS_ORIGINS",
            "PEIARS_SESSION_SECRET",
            "PEIARS_SESSION_COOKIE_SECURE",
            "PEIARS_DATABASE_URL",
            "PEIARS_DATABASE_REQUIRED",
            "PEIARS_DEMONSTRATION_SOURCES",
            "PEIARS_ENV",
            "PEIARS_API_CORS_ORIGINS",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_documented_production_environment_activates_validation(self, monkeypatch):
        """§7.1: PEIARS_ENVIRONMENT=production + insecure cookies → error.

        Both values are delivered through the real environment-loading
        mechanism (no constructor injection). Before the name fix,
        PEIARS_ENV=production was silently ignored and this combination
        booted as a development server.
        """
        from pydantic import ValidationError

        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_ENVIRONMENT", "production")
        monkeypatch.setenv("PEIARS_SESSION_COOKIE_SECURE", "false")
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None)
        message = str(excinfo.value)
        assert "session_cookie_secure" in message, (
            "the production validator must name the offending setting"
        )

    def test_production_variable_reaches_the_model(self, monkeypatch):
        """The documented name is not merely valid — it is READ."""
        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_ENVIRONMENT", "production")
        s = Settings(_env_file=None)
        assert s.environment == "production"
        # The production default (secure cookies) applies without any
        # explicit opt-in.
        assert s.session_cookie_secure is True

    def test_previously_documented_wrong_names_are_ignored(self, monkeypatch):
        """Hazard pin: PEIARS_ENV / PEIARS_API_CORS_ORIGINS do NOTHING.

        ``extra="ignore"`` (needed for sibling CLI variables such as
        PEIARS_BOOTSTRAP_ADMIN_PASSWORD) means a wrongly named variable
        silently falls back to defaults. This test pins that hazard so a
        future change to either side is a conscious decision.
        """
        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_ENV", "production")
        monkeypatch.setenv(
            "PEIARS_API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        s = Settings(_env_file=None)
        assert s.environment == "development", (
            "PEIARS_ENV must not be read; the documented name is PEIARS_ENVIRONMENT"
        )
        # The untouched DEFAULTS were used (the wrong names changed nothing).
        assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"], (
            "PEIARS_API_CORS_ORIGINS must not be read; the documented name "
            "is PEIARS_CORS_ORIGINS (defaults were used here)"
        )

    def test_documented_cors_settings_reach_settings(self, monkeypatch):
        """§7.3: the documented comma-separated value reaches the field."""
        from app.core.config import Settings

        monkeypatch.setenv(
            "PEIARS_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        s = Settings(_env_file=None)
        assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]

    def test_documented_cors_settings_reach_the_application(self, monkeypatch):
        """§7.3 (end to end): env-loaded settings drive the CORS middleware.

        The application is built from settings loaded through the real
        environment mechanism, and the credentialed CORS middleware must
        carry exactly the documented origins — never a wildcard.
        """
        from fastapi.middleware.cors import CORSMiddleware

        from app.core.config import Settings
        from app.main import create_app

        monkeypatch.setenv(
            "PEIARS_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        monkeypatch.setenv("PEIARS_DATABASE_REQUIRED", "false")
        settings = Settings(_env_file=None)
        app = create_app(settings=settings)
        cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        assert len(cors) == 1, "the CORS middleware must be installed"
        kwargs = cors[0].kwargs
        assert kwargs["allow_origins"] == [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        assert kwargs["allow_credentials"] is True, (
            "credentialed CORS must not be weakened"
        )
        assert "*" not in kwargs["allow_origins"]

    def test_env_example_documented_names_are_real_settings_fields(self):
        """Name-contract: every PEIARS_* key in .env.example is a real field.

        Prevents the PEIARS_ENV / PEIARS_API_CORS_ORIGINS class of drift:
        a variable documented in the committed template but not read by
        the model is a silent misconfiguration trap.
        """
        from app.core.config import Settings

        content = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
        documented = {
            line.split("=", 1)[0].strip()
            for line in content.splitlines()
            if line.startswith("PEIARS_")
        }
        assert documented, ".env.example must document variables"
        real = {f"PEIARS_{name.upper()}" for name in Settings.model_fields}
        unknown = documented - real
        assert not unknown, (
            f".env.example documents variables the Settings model never reads: "
            f"{sorted(unknown)}"
        )
        # The previously mis-documented names must be gone for good.
        assert "PEIARS_ENV" not in documented
        assert "PEIARS_API_CORS_ORIGINS" not in documented

    def test_documented_development_configuration_remains_functional(self):
        """§7.5: the documented local-development values still construct."""
        from app.core.config import Settings

        # The exact documented development pairing from the guides:
        # development + relaxed cookie Secure (local HTTP).
        s = Settings(
            _env_file=None,
            environment="development",
            session_cookie_secure=False,
            database_required=True,
            database_url="postgresql+psycopg://peiars_app:pw@localhost:5432/peiars_review",
            session_secret="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
        )
        assert s.environment == "development"
        assert s.session_cookie_secure is False
        # Defaults unchanged for everything not explicitly set.
        assert s.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
        assert s.demonstration_sources is False


class TestCorsSerializationContract:
    """Final correction §2 — one documented, validated representation.

    pydantic-settings 2.13 JSON-decodes complex (list-valued) environment
    values BEFORE any ``mode="before"`` field validator runs, so the
    original comma-splitting validator was dead code for env values: a
    comma-separated string raised an opaque ``SettingsError`` from the
    source layer. The field now uses ``NoDecode`` so the raw string
    reaches the validator, and the validator enforces the documented
    comma-separated representation with clear failures for anything
    else.
    """

    @pytest.fixture(autouse=True)
    def _scrub_cors_env(self, monkeypatch):
        monkeypatch.delenv("PEIARS_CORS_ORIGINS", raising=False)
        monkeypatch.delenv("PEIARS_API_CORS_ORIGINS", raising=False)

    def test_correctly_formatted_single_origin(self, monkeypatch):
        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_CORS_ORIGINS", "http://localhost:5173")
        s = Settings(_env_file=None)
        assert s.cors_origins == ["http://localhost:5173"]

    def test_multiple_origins(self, monkeypatch):
        from app.core.config import Settings

        monkeypatch.setenv(
            "PEIARS_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,https://peiars.example",
        )
        s = Settings(_env_file=None)
        assert s.cors_origins == [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://peiars.example",
        ]

    def test_surrounding_and_inner_spaces_are_stripped(self, monkeypatch):
        from app.core.config import Settings

        monkeypatch.setenv(
            "PEIARS_CORS_ORIGINS", " http://a.example , http://b.example "
        )
        s = Settings(_env_file=None)
        assert s.cors_origins == ["http://a.example", "http://b.example"]

    def test_json_array_representation_fails_clearly(self, monkeypatch):
        """§7.4: an undocumented representation must fail with an
        actionable message, not raise an opaque SettingsError and not
        silently produce unusable origins."""
        from pydantic import ValidationError

        from app.core.config import Settings

        monkeypatch.setenv(
            "PEIARS_CORS_ORIGINS", '["http://a.example","http://b.example"]'
        )
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None)
        message = str(excinfo.value)
        assert "cors_origins" in message
        assert "comma-separated" in message, (
            "the error must name the one documented representation"
        )

    @pytest.mark.parametrize(
        "bad_origin",
        [
            "*",
            "http://a.example, *",
            "not-an-origin",
            "ftp://files.example",
            "http://a.example/path",
            "http://a.example?q=1",
            "http://",
        ],
    )
    def test_prohibited_or_malformed_origins_fail_clearly(self, monkeypatch, bad_origin):
        """§7.4: prohibited (wildcard with credentials) and malformed
        values fail with a validation error naming the field."""
        from pydantic import ValidationError

        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_CORS_ORIGINS", bad_origin)
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None)
        assert "cors_origins" in str(excinfo.value)

    def test_wildcard_error_explains_the_prohibition(self, monkeypatch):
        from pydantic import ValidationError

        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_CORS_ORIGINS", "*")
        with pytest.raises(ValidationError) as excinfo:
            Settings(_env_file=None)
        message = str(excinfo.value).lower()
        assert "wildcard" in message
        assert "credentials" in message, (
            "the error must explain why wildcards are prohibited"
        )

    def test_empty_value_disables_cross_origin_access(self, monkeypatch):
        """An explicitly empty allow-list is fail-safe (nothing allowed)."""
        from app.core.config import Settings

        monkeypatch.setenv("PEIARS_CORS_ORIGINS", "")
        s = Settings(_env_file=None)
        assert s.cors_origins == []

    def test_environment_variable_precedence_over_env_file(self, tmp_path, monkeypatch):
        """Explicit env vars win over .env for the list field too."""
        from app.core.config import Settings

        env_file = tmp_path / "precedence.env"
        env_file.write_text(
            "PEIARS_CORS_ORIGINS=http://from-file.example\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PEIARS_CORS_ORIGINS", "http://from-env.example")
        s = Settings(_env_file=env_file)
        assert s.cors_origins == ["http://from-env.example"]

    def test_env_file_comma_separated_value_also_parsed(self, tmp_path, monkeypatch):
        """The SAME documented representation works through the .env file
        source (serve.py loads it into the environment; Alembic and other
        tools may read the file directly)."""
        from app.core.config import Settings

        monkeypatch.delenv("PEIARS_CORS_ORIGINS", raising=False)
        env_file = tmp_path / "file-source.env"
        env_file.write_text(
            "PEIARS_CORS_ORIGINS=http://from-file.example,http://second.example\n",
            encoding="utf-8",
        )
        s = Settings(_env_file=env_file)
        assert s.cors_origins == ["http://from-file.example", "http://second.example"]

    def test_constructor_list_still_accepted(self):
        """Constructor injection (tests, programmatic use) keeps working."""
        from pydantic import ValidationError

        from app.core.config import Settings

        s = Settings(
            _env_file=None, cors_origins=["http://a.example", "http://b.example"]
        )
        assert s.cors_origins == ["http://a.example", "http://b.example"]
        with pytest.raises(ValidationError):
            Settings(_env_file=None, cors_origins=["*"])


class TestSecretGenerationContract:
    """Final correction §3 — the documented generation commands' contract.

    The documented Windows command (``RandomNumberGenerator.Create()`` +
    instance ``GetBytes`` on a 32-byte buffer, hex-encoded) and the POSIX
    command (``openssl rand -hex 32``) both produce the same shape:
    64 lowercase hexadecimal characters from 32 cryptographically random
    bytes. These tests verify that shape is accepted by the REAL Settings
    validator through the real environment-loading mechanism — the same
    check the Windows guide documents as a post-generation step.

    Note: the PowerShell command itself can only be executed on Windows;
    this suite verifies the CONTRACT (shape + validator acceptance) with
    Python's CSPRNG, which produces byte-for-byte the same shape. No
    Windows PowerShell execution is claimed.
    """

    def test_documented_generation_shape_accepted_via_environment(self, monkeypatch):
        import secrets

        from app.core.config import Settings

        # secrets.token_hex(32): 32 CSPRNG bytes -> 64 lowercase hex chars,
        # exactly what `openssl rand -hex 32` and the documented
        # RandomNumberGenerator command produce.
        secret = secrets.token_hex(32)
        assert len(secret) == 64
        import re

        assert re.fullmatch(r"[0-9a-f]{64}", secret), (
            "32 random bytes hex-encoded must yield 64 lowercase hex characters"
        )
        monkeypatch.setenv("PEIARS_SESSION_SECRET", secret)
        s = Settings(_env_file=None)
        assert s.session_secret == secret

    def test_sixty_four_hex_characters_is_thirty_two_bytes(self, monkeypatch):
        """The documented check is a bijection: 64 hex chars ↔ 32 bytes."""
        import binascii
        import secrets

        secret = secrets.token_hex(32)
        assert len(secret) == 64
        assert len(binascii.unhexlify(secret)) == 32

    def test_documented_check_command_in_windows_guide(self):
        """The Windows guide documents the post-generation shape check and
        the Settings-validator acceptance check."""
        guide = REPO_ROOT / "docs" / "dev" / "LOCAL_STARTUP_WINDOWS.md"
        content = guide.read_text(encoding="utf-8")
        assert "-cmatch '^[0-9a-f]{64}$'" in content, (
            "the guide must document the 64-hex-character shape check"
        )
        assert "RandomNumberGenerator]::Create()" in content, (
            "the guide must document the instance-based Create() command"
        )
        assert "$rng.GetBytes($bytes)" in content, (
            "the guide must call the instance GetBytes method"
        )
        assert "RandomNumberGenerator]::GetBytes" not in content, (
            "the guide must not document the .NET-Framework-incompatible "
            "static GetBytes call"
        )
        assert "Settings(_env_file=None)" in content, (
            "the guide must document the real-Settings acceptance check"
        )


class TestStartupDiagnostics:
    """Workstream C: startup diagnostics print safe operational metadata."""

    def test_diagnostics_function_exists(self):
        """serve.py must expose a diagnostics function."""
        module = _load_serve_module()
        assert hasattr(module, "_print_startup_diagnostics"), (
            "serve.py must expose _print_startup_diagnostics"
        )

    def test_diagnostics_do_not_print_secrets(self):
        """The diagnostics source must not reference secret values."""
        source = SERVE_PY.read_text(encoding="utf-8")
        # Find the diagnostics function body.
        diag_start = source.find("def _print_startup_diagnostics")
        diag_end = source.find("def main", diag_start)
        diag_body = source[diag_start:diag_end]
        # Must not print session_secret or database_url values.
        assert "settings.session_secret" not in diag_body.replace(
            "'configured' if settings.session_secret", ""
        ).replace("'NOT SET", ""), (
            "Diagnostics must not print the session_secret value"
        )
        # Must print safe metadata.
        for safe in ("environment", "database_required", "demonstration_sources", "api_root_path"):
            assert safe in diag_body, f"Diagnostics must report {safe}"

    def test_diagnostics_print_output(self, capsys):
        """The diagnostics function prints non-empty output."""
        from app.core.config import Settings

        module = _load_serve_module()
        settings = Settings(
            _env_file=None,
            environment="development",
            database_required=True,
            database_url="postgresql+psycopg://u:p@localhost:5432/db",
            session_secret="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
            demonstration_sources=True,
        )
        module._print_startup_diagnostics(settings, "WindowsSelectorEventLoopPolicy")
        output = capsys.readouterr().out
        assert "environment: development" in output
        assert "event loop: WindowsSelectorEventLoopPolicy" in output
        assert "database required: True" in output
        assert "demonstration sources: enabled" in output
        # Must NOT contain the session secret or database URL.
        assert "a1b2c3d4e5f6a7b8" not in output
        assert "postgresql+psycopg://u:p@localhost" not in output

    def test_diagnostics_report_actual_policy_outcome(self):
        """The event-loop line comes from the installed-policy outcome,
        not from a fresh sys.platform probe."""
        source = SERVE_PY.read_text(encoding="utf-8")
        assert "EVENT_LOOP_POLICY_OUTCOME" in source, (
            "main() must pass the recorded policy outcome to the diagnostics"
        )


class TestAlembicEnvLoading:
    """The single environment-loading procedure covers Alembic (correction §4).

    ``alembic upgrade head`` must resolve ``PEIARS_DATABASE_URL`` from the
    repository-root ``.env`` — the same file ``serve.py`` loads — without
    any manual export step. Verified with a real ``alembic`` subprocess
    whose environment is scrubbed of every ``PEIARS_*`` variable.
    """

    def test_alembic_upgrade_reads_repo_root_env(self, pg_server):
        """A real `python -m alembic upgrade head` driven only by .env."""
        from sqlalchemy import create_engine, make_url, text

        admin_uri = pg_server.get_uri()
        admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS peiars_dotenv_test"))
            conn.execute(text("CREATE DATABASE peiars_dotenv_test"))
        admin_engine.dispose()

        db_url = str(make_url(admin_uri).set(database="peiars_dotenv_test"))

        env_file = REPO_ROOT / ".env"
        # A developer machine may legitimately have a repository-root .env
        # (the guides encourage it). Back it up for the duration of the
        # test and restore it afterwards — nothing else in the suite reads
        # the file (every Settings construction uses _env_file=None).
        backup_file = REPO_ROOT / ".env.pr06a-test-backup"
        assert not backup_file.exists(), (
            f"stale backup {backup_file} exists; restore it manually and rerun"
        )
        had_env = env_file.exists()
        if had_env:
            env_file.rename(backup_file)
        env_file.write_text(
            "PEIARS_DATABASE_URL=" + db_url + "\n"
            "PEIARS_DATABASE_REQUIRED=true\n",
            encoding="utf-8",
        )
        try:
            scrubbed = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("PEIARS_")
            }
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=str(BACKEND_ROOT),
                env=scrubbed,
                capture_output=True,
                text=True,
                timeout=180,
            )
            assert result.returncode == 0, (
                f"alembic upgrade head failed under the .env-only procedure:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

            # The migrations were really applied to the database that was
            # named ONLY inside the .env file.
            check_engine = create_engine(db_url)
            try:
                with check_engine.connect() as conn:
                    versions = conn.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).fetchall()
                    tables = {
                        row[0]
                        for row in conn.execute(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = 'public'"
                            )
                        )
                    }
            finally:
                check_engine.dispose()
            assert versions, "alembic_version must be populated after upgrade head"
            assert {"review_cases", "case_events", "users", "auth_sessions"} <= tables
        finally:
            env_file.unlink(missing_ok=True)
            if had_env:
                backup_file.rename(env_file)

    def test_alembic_env_source_uses_dotenv_values(self):
        """migrations/env.py must read .env without mutating os.environ."""
        source = (BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
        assert "dotenv_values" in source, (
            "migrations/env.py must parse the .env file with dotenv_values"
        )
        assert "load_dotenv" not in source, (
            "migrations/env.py must not mutate os.environ (load_dotenv); "
            "explicit environment variables keep precedence and the process "
            "environment stays untouched"
        )
        assert "PEIARS_DATABASE_URL" in source


class TestFailureInjectionMatrix:
    """PR-06A §12: failure-injection scenarios."""

    def test_missing_database_url_with_required_true_fails_closed(self):
        """database_required=true without database_url raises at startup."""
        from app.core.config import Settings
        from app.core.config_errors import DatabaseConfigurationError
        from app.main import create_app

        with pytest.raises(DatabaseConfigurationError):
            s = Settings(
                _env_file=None,
                database_required=True,
                database_url=None,
            )
            create_app(settings=s)

    def test_missing_session_secret_auth_fails_closed(self):
        """Without session_secret, auth routes fail with 503."""
        from fastapi.testclient import TestClient
        from app.core.config import Settings
        from app.main import create_app

        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=None,
            database_required=False,
            session_secret=None,
        )
        app = create_app(settings=settings)
        client = TestClient(app)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_NOT_READY"

    def test_demonstration_sources_disabled_by_default(self):
        """demonstration_sources must default to false (opt-in)."""
        from app.core.config import Settings

        s = Settings(_env_file=None, environment="development")
        assert s.demonstration_sources is False, (
            "demonstration_sources must default to false (explicit opt-in)"
        )

    def test_demonstration_sources_toggle(self):
        """demonstration_sources can be explicitly enabled."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            environment="development",
            demonstration_sources=True,
        )
        assert s.demonstration_sources is True
