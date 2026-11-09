"""Export the API's OpenAPI schema deterministically.

Usage (from the repository root)::

    python backend/scripts/export_openapi.py
    python backend/scripts/export_openapi.py --output path/to/openapi.json

Determinism guarantees:

* the application is built from canonical settings that read neither
  ``.env`` nor environment variables;
* the JSON is serialized with sorted keys, stable indentation and a
  trailing newline;
* FastAPI's schema generation embeds no timestamps and no random
  identifiers, so the same code version always produces byte-identical
  output.

The exported snapshot is committed at ``backend/contracts/openapi.json``
and guarded against unintended drift by
``backend/tests/test_openapi.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import canonical_settings  # noqa: E402
from app.main import create_app  # noqa: E402

DEFAULT_OUTPUT = _BACKEND_ROOT / "contracts" / "openapi.json"


def export_schema(output: Path) -> bytes:
    """Build the app and serialize its OpenAPI schema deterministically."""
    app = create_app(settings=canonical_settings())
    schema = app.openapi()
    content = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False)
    return (content + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the deterministic OpenAPI schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args()

    payload = export_schema(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"Wrote OpenAPI schema ({len(payload)} bytes) to {args.output}")


if __name__ == "__main__":
    main()
