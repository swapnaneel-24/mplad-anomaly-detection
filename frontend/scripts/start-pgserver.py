#!/usr/bin/env python3
"""Start a disposable pgserver for PEIARS E2E and keep it running.

Writes the connection URI to /tmp/peiars_pgserver_uri.txt and blocks
forever. Kill the process to stop the server (the pgdata dir is left
in place; rerun to reuse it).

Usage::

    python scripts/start-pgserver.py &
    URI=$(cat /tmp/peiars_pgserver_uri.txt)
    kill %1  # stop the server when done
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from pgserver import postgres_server

PGDATA = "/tmp/peiars_pgdata"
URI_FILE = "/tmp/peiars_pgserver_uri.txt"


def main() -> None:
    os.makedirs(PGDATA, exist_ok=True)
    # cleanup_mode=None keeps the server running after this script exits
    # (we block forever below; but if killed, the server stays up too).
    server = postgres_server.get_server(PGDATA, cleanup_mode=None)
    server.ensure_postgres_running()

    # Create the e2e database if it doesn't exist.
    try:
        server.psql("CREATE DATABASE peiars_e2e;")
    except Exception as exc:  # noqa: BLE001
        if "already exists" not in str(exc):
            # CREATE DATABASE errors are non-fatal if the DB exists.
            sys.stderr.write(f"CREATE DATABASE note: {exc}\n")

    uri = server.get_uri()
    # Rewrite for psycopg with the peiars_e2e database.
    # The pgserver URI is: postgresql://postgres:@/postgres?host=<pgdata>
    # We swap the dbname from postgres → peiars_e2e.
    psycopg_uri = uri.replace("/postgres?", "/peiars_e2e?").replace(
        "/postgres$", "/peiars_e2e"
    )
    # Format for SQLAlchemy + psycopg.
    sqlalchemy_uri = psycopg_uri.replace("postgresql://", "postgresql+psycopg://")
    Path(URI_FILE).write_text(sqlalchemy_uri, encoding="utf-8")
    print(f"pgserver URI written to {URI_FILE}")
    print(f"  {sqlalchemy_uri}")
    sys.stdout.flush()

    # Block forever so the server stays up.
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Stopping pgserver...")


if __name__ == "__main__":
    main()
