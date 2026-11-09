"""Run the PEIARS API locally (development server).

Usage (from the repository root)::

    python backend/scripts/serve.py          # reads .env / environment
    python backend/scripts/serve.py --host 0.0.0.0 --port 9000

Equivalent direct uvicorn invocation (from ``backend/``)::

    uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the PEIARS API locally.")
    parser.add_argument("--host", default=None, help="Bind host (default: PEIARS_API_HOST or 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: PEIARS_API_PORT or 8000).")
    args = parser.parse_args()

    settings = Settings()
    host = args.host or settings.api_host
    port = args.port or settings.api_port

    import uvicorn

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
