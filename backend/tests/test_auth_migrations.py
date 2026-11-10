"""PR-04 authentication migration tests (real PostgreSQL).

Covers migration 0003: users, auth_sessions, login_throttles — schema,
constraints, indexes, FK cascades, downgrade, and preservation of the
PR-03 case/event data across upgrade.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.usefixtures("pg_server")


@pytest.fixture()
def fresh_db_url(pg_server):
    """A brand-new empty database for migration testing."""
    admin_uri = pg_server.get_uri()
    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    db_name = "peiars_auth_migration_test"
    with admin_engine.connect() as conn:
        conn.execute(text(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
        ))
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin_engine.dispose()
    from sqlalchemy import make_url

    url = make_url(admin_uri)
    return str(url.set(database=db_name))


def _alembic_config(db_url):
    from alembic.config import Config
    from pathlib import Path

    BACKEND_ROOT = Path(__file__).resolve().parents[1]
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    os.environ["PEIARS_DATABASE_URL"] = db_url
    return cfg


def _insert_case_and_event(conn) -> tuple[str, str]:
    """Insert a PR-03 case + event; return (case_id, event_id)."""
    case_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    conn.execute(text(
        "INSERT INTO review_cases (id, dataset_id, snapshot_id, record_ref, "
        "status, title, created_by) VALUES (:id, 'ulb-benchmark', 'snap-001', "
        "'row-1', 'not_reviewed', 'Migration test', 'fixture-actor')"
    ), {"id": case_id})
    conn.execute(text(
        "INSERT INTO case_events (id, case_id, event_type, actor_ref, case_version) "
        "VALUES (:eid, :cid, 'created', 'fixture-actor', 1)"
    ), {"eid": event_id, "cid": case_id})
    return case_id, event_id


class TestUpgradeSchema:
    def test_tables_created(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert {"users", "auth_sessions", "login_throttles"} <= tables
        engine.dispose()

    def test_users_columns(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("users")}
        assert columns == {
            "id", "username", "password_hash", "display_name", "role",
            "is_active", "created_at", "updated_at", "last_login_at",
        }
        engine.dispose()

    def test_auth_sessions_columns(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("auth_sessions")}
        assert columns == {
            "id", "user_id", "token_hash", "created_at",
            "expires_at", "last_seen_at", "revoked_at",
        }
        engine.dispose()

    def test_login_throttles_columns(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("login_throttles")}
        assert columns == {
            "key", "failed_count", "first_failed_at",
            "last_failed_at", "locked_until", "updated_at",
        }
        engine.dispose()

    def test_indexes_present(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        user_indexes = {i["name"] for i in insp.get_indexes("users")}
        session_indexes = {i["name"] for i in insp.get_indexes("auth_sessions")}
        assert "ix_users_username" in user_indexes
        assert "ix_auth_sessions_user_id" in session_indexes
        assert "ix_auth_sessions_token_hash" in session_indexes
        assert "ix_auth_sessions_expires_at" in session_indexes
        engine.dispose()

    def test_role_check_constraint(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT con.conname FROM pg_constraint con "
                "JOIN pg_class cls ON con.conrelid = cls.oid "
                "WHERE cls.relname = 'users' AND con.contype = 'c'"
            ))
            names = {r[0] for r in result}
            assert "ck_users_users_role_enum" in names

            # Invalid roles rejected.
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO users (username, password_hash, display_name, role) "
                    "VALUES ('x1', 'h', 'X', 'superuser')"
                ))
                conn.commit()
            conn.rollback()
        engine.dispose()

    def test_duplicate_username_rejected(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (username, password_hash, display_name, role) "
                "VALUES ('admin', 'h', 'Admin', 'admin')"
            ))
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO users (username, password_hash, display_name, role) "
                    "VALUES ('admin', 'h2', 'Admin2', 'viewer')"
                ))
        engine.dispose()

    def test_session_fk_cascades_on_user_delete(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            user_id = str(uuid.uuid4())
            conn.execute(text(
                "INSERT INTO users (id, username, password_hash, display_name, role) "
                "VALUES (:id, 'cascade-user', 'h', 'C', 'viewer')"
            ), {"id": user_id})
            conn.execute(text(
                "INSERT INTO auth_sessions (user_id, token_hash, expires_at) "
                "VALUES (:uid, :th, now() + interval '1 hour')"
            ), {"uid": user_id, "th": "a" * 64})
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            count = conn.execute(text("SELECT count(*) FROM auth_sessions")).scalar_one()
            assert count == 0  # ON DELETE CASCADE removed the session
        engine.dispose()

    def test_duplicate_token_hash_rejected(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            user_id = str(uuid.uuid4())
            conn.execute(text(
                "INSERT INTO users (id, username, password_hash, display_name, role) "
                "VALUES (:id, 'tok-user', 'h', 'T', 'viewer')"
            ), {"id": user_id})
            conn.execute(text(
                "INSERT INTO auth_sessions (user_id, token_hash, expires_at) "
                "VALUES (:uid, :th, now() + interval '1 hour')"
            ), {"uid": user_id, "th": "b" * 64})
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO auth_sessions (user_id, token_hash, expires_at) "
                    "VALUES (:uid, :th, now() + interval '1 hour')"
                ), {"uid": str(uuid.uuid4()), "th": "b" * 64})
        engine.dispose()


class TestCaseDataPreservation:
    def test_upgrade_from_0002_preserves_case_and_events(self, fresh_db_url):
        """Existing PR-03 rows survive the 0003 upgrade untouched."""
        from alembic import command

        cfg = _alembic_config(fresh_db_url)
        command.upgrade(cfg, "0002_add_event_seq")

        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            case_id, event_id = _insert_case_and_event(conn)
        engine.dispose()

        command.upgrade(cfg, "head")

        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            case = conn.execute(text(
                "SELECT status, created_by FROM review_cases WHERE id = :id"
            ), {"id": case_id}).fetchone()
            assert case is not None
            assert case[0] == "not_reviewed"
            assert case[1] == "fixture-actor"  # historical actor_ref untouched
            event = conn.execute(text(
                "SELECT event_type, actor_ref, case_version FROM case_events WHERE id = :id"
            ), {"id": event_id}).fetchone()
            assert event is not None
            assert event[0] == "created"
            assert event[1] == "fixture-actor"
        engine.dispose()


class TestDowngrade:
    def test_downgrade_to_0002_drops_auth_tables(self, fresh_db_url):
        from alembic import command

        cfg = _alembic_config(fresh_db_url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "0002_add_event_seq")

        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "users" not in tables
        assert "auth_sessions" not in tables
        assert "login_throttles" not in tables
        # PR-03 tables remain.
        assert "review_cases" in tables
        assert "case_events" in tables
        engine.dispose()

    def test_empty_database_upgrade_to_head(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert {
            "review_cases", "case_events", "users", "auth_sessions", "login_throttles",
        } <= tables
        engine.dispose()
