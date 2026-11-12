"""Run the PEIARS API locally (development server).

Usage (from the repository root)::

    python backend/scripts/serve.py          # reads .env / environment
    python backend/scripts/serve.py --host 0.0.0.0 --port 9000

Equivalent direct uvicorn invocation (from ``backend/``)::

    uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import asyncio
import sys

SUPPORTED_PYTHON_VERSIONS = (
    "Python 3.12 (tested on Linux CI runner; Windows/macOS runtime verification pending)"
)


def _install_event_loop_policy(platform: str | None = None) -> str:
    """Install WindowsSelectorEventLoopPolicy on win32 for psycopg 3 async compatibility."""
    target = sys.platform if platform is None else platform
    if target != "win32":
        return "default (POSIX)"
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_cls is None:
        raise RuntimeError(
            "asyncio.WindowsSelectorEventLoopPolicy is unavailable on win32; "
            "absence of the policy class is not proof of psycopg compatibility. "
            f"Supported runtime: {SUPPORTED_PYTHON_VERSIONS}."
        )
    asyncio.set_event_loop_policy(policy_cls())
    return "WindowsSelectorEventLoopPolicy"


EVENT_LOOP_POLICY_OUTCOME = _install_event_loop_policy()

import argparse  # noqa: E402
from pathlib import Path  # noqa: E402

try:
    from dotenv import load_dotenv  # noqa: E402
except ImportError as exc:
    raise SystemExit(
        "python-dotenv is required to load the repository-root .env file. "
        "Install backend dependencies from backend/requirements.txt (or backend/requirements-lock.txt)."
    ) from exc

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402


def _load_local_env() -> bool:
    """Load <repo-root>/.env without overriding explicit environment variables."""
    return bool(load_dotenv(_REPO_ROOT / ".env", override=False))


def _print_startup_diagnostics(settings: Settings, policy_outcome: str) -> None:
    """Print safe operational startup diagnostics without exposing secrets."""
    secret_state = 'configured' if settings.session_secret else 'NOT SET'
    demo_state = "enabled" if settings.demonstration_sources else "disabled"
    print(f"environment: {settings.environment}")
    print(f"event loop: {policy_outcome}")
    print(f"database required: {settings.database_required}")
    print(f"session secret: {secret_state}")
    print(f"demonstration sources: {demo_state}")
    print(f"api root path: {settings.api_root_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the PEIARS API locally.")
    parser.add_argument("--host", default=None, help="Bind host (default: PEIARS_API_HOST or 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: PEIARS_API_PORT or 8000).")
    args = parser.parse_args()

    _load_local_env()
    settings = Settings()
    host = args.host or settings.api_host
    port = args.port or settings.api_port

    import uvicorn

    _print_startup_diagnostics(settings, EVENT_LOOP_POLICY_OUTCOME)
    print(f"Serving {settings.app_name} v{settings.app_version} on http://{host}:{port}")
    print(f"API prefix: {settings.api_root_path} (docs: {'/docs' if settings.docs_enabled else 'disabled'})")
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()