"""Start a disposable pgserver-backed PostgreSQL and print a usable URL.

Outputs a single line: a SQLAlchemy/psycopg URL pointing at a freshly
created `peiars_e2e` database within the disposable server. The server
stays alive for the lifetime of this process (used as a parent for the
backend E2E run).

Usage:
    python scripts/start-pgserver-e2e.py &
    # ... read URL from stdout, run backend, run tests ...
    # kill the python process to dispose the server
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pgserver
from sqlalchemy import create_engine, text


def main() -> None:
    data_dir = tempfile.mkdtemp(prefix="e2e_pg_")
    server = pgserver.get_server(data_dir)
    server.ensure_postgres_running()
    admin_uri = server.get_uri()

    # Create the peiars_e2e database.
    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS peiars_e2e"))
        conn.execute(text("CREATE DATABASE peiars_e2e"))
    engine.dispose()

    from sqlalchemy import make_url
    url = make_url(admin_uri).set(database="peiars_e2e")
    print(str(url), flush=True)

    # Keep alive until killed.
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        server.cleanup()


if __name__ == "__main__":
    main()
