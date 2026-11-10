"""Alembic migration tests (real PostgreSQL).

Verifies (PR-03 §12):

* Migration from an empty database upgrades to head cleanly.
* The schema, indexes, constraints, and append-only trigger are present.
* Downgrade reverses the schema in a disposable database.
* Repeated upgrade is idempotent (no unexpected changes).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.usefixtures("pg_server")


@pytest.fixture()
def fresh_db_url(pg_server):
    """A brand-new empty database for migration testing.

    Drops and recreates the ``peiars_migration_test`` database before
    each test, terminating any leftover connections first so the DROP
    succeeds even if a previous test's engine pool is still open.
    """
    admin_uri = pg_server.get_uri()
    admin_engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    db_name = "peiars_migration_test"
    with admin_engine.connect() as conn:
        # Terminate any leftover connections to the test database.
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
    # The URL is passed via the PEIARS_DATABASE_URL environment variable
    # (read by migrations/env.py) to avoid configparser interpolation
    # issues with URL-encoded characters in pgserver socket paths.
    os.environ["PEIARS_DATABASE_URL"] = db_url
    return cfg


class TestMigrationUpgrade:
    def test_upgrade_from_empty_database(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")

        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "review_cases" in tables
        assert "case_events" in tables
        engine.dispose()

    def test_review_cases_columns(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("review_cases")}
        assert columns == {
            "id", "dataset_id", "snapshot_id", "record_ref",
            "status", "title", "summary",
            "created_at", "updated_at", "version", "created_by",
        }
        engine.dispose()

    def test_case_events_columns(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("case_events")}
        assert columns == {
            "id", "case_id", "event_type", "event_at", "actor_ref",
            "previous_status", "new_status", "reason",
            "event_payload", "case_version", "event_seq",
        }
        engine.dispose()

    def test_indexes_present(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        rc_indexes = {i["name"] for i in insp.get_indexes("review_cases")}
        ce_indexes = {i["name"] for i in insp.get_indexes("case_events")}
        assert "ix_review_cases_dataset_id" in rc_indexes
        assert "ix_review_cases_snapshot_id" in rc_indexes
        assert "ix_review_cases_record_ref" in rc_indexes
        assert "ix_review_cases_created_by" in rc_indexes
        assert "ix_review_cases_dataset_snapshot" in rc_indexes
        assert "ix_review_cases_status_created" in rc_indexes
        assert "ix_case_events_case_id" in ce_indexes
        assert "ix_case_events_event_at" in ce_indexes
        assert "ix_case_events_actor_ref" in ce_indexes
        assert "ix_case_events_case_version" in ce_indexes
        assert "ix_case_events_case_version_seq" in ce_indexes
        engine.dispose()

    def test_check_constraints_present(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.connect() as conn:
            # The status CHECK constraint rejects invalid status values.
            result = conn.execute(text(
                "SELECT con.conname FROM pg_constraint con "
                "JOIN pg_class cls ON con.conrelid = cls.oid "
                "WHERE cls.relname = 'review_cases' AND con.contype = 'c'"
            ))
            constraint_names = {r[0] for r in result}
            assert "ck_review_cases_review_cases_status_enum" in constraint_names

            result = conn.execute(text(
                "SELECT con.conname FROM pg_constraint con "
                "JOIN pg_class cls ON con.conrelid = cls.oid "
                "WHERE cls.relname = 'case_events' AND con.contype = 'c'"
            ))
            constraint_names = {r[0] for r in result}
            assert "ck_case_events_case_events_event_type_enum" in constraint_names
        engine.dispose()

    def test_append_only_trigger_exists(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.connect() as conn:
            # The trigger function exists.
            result = conn.execute(text(
                "SELECT proname FROM pg_proc WHERE proname = 'enforce_case_events_append_only'"
            ))
            assert result.fetchone() is not None

            # The UPDATE trigger exists.
            result = conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgname = 'trg_case_events_no_update'"
            ))
            assert result.fetchone() is not None

            # The DELETE trigger exists.
            result = conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgname = 'trg_case_events_no_delete'"
            ))
            assert result.fetchone() is not None
        engine.dispose()


class TestMigrationDowngrade:
    def test_downgrade_drops_tables(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        command.downgrade(_alembic_config(fresh_db_url), "base")

        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "review_cases" not in tables
        assert "case_events" not in tables
        engine.dispose()

    def test_downgrade_drops_trigger_function(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        command.downgrade(_alembic_config(fresh_db_url), "base")

        engine = create_engine(fresh_db_url)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT proname FROM pg_proc WHERE proname = 'enforce_case_events_append_only'"
            ))
            assert result.fetchone() is None
        engine.dispose()


class TestMigrationIdempotence:
    def test_repeated_upgrade_no_changes(self, fresh_db_url):
        from alembic import command

        cfg = _alembic_config(fresh_db_url)
        command.upgrade(cfg, "head")
        # A second upgrade to head should be a no-op.
        command.upgrade(cfg, "head")

        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        assert "review_cases" in insp.get_table_names()
        assert "case_events" in insp.get_table_names()
        engine.dispose()


class TestEventSeqMigration:
    """PR-03 hardening §2: the 0002 migration adds event_seq."""

    def test_event_seq_column_present_after_upgrade(self, fresh_db_url):
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"]: c for c in insp.get_columns("case_events")}
        assert "event_seq" in columns
        # The column is NOT NULL and has a server default (IDENTITY).
        assert not columns["event_seq"]["nullable"]
        engine.dispose()

    def test_event_seq_is_identity_column(self, fresh_db_url):
        """The column is a PostgreSQL IDENTITY column (GENERATED ALWAYS)."""
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT attidentity FROM pg_attribute "
                "WHERE attrelid = 'case_events'::regclass "
                "AND attname = 'event_seq'"
            ))
            # 'a' = GENERATED ALWAYS, 'd' = GENERATED BY DEFAULT
            assert result.fetchone()[0] == "a"
        engine.dispose()

    def test_event_seq_auto_populated_on_insert(self, fresh_db_url):
        """Inserting an event without specifying event_seq succeeds and
        the column is auto-populated by the IDENTITY sequence."""
        import uuid

        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        # First insert a case (required by FK).
        with engine.begin() as conn:
            case_id = str(uuid.uuid4())
            conn.execute(text(
                "INSERT INTO review_cases (id, dataset_id, snapshot_id, "
                "record_ref, status, title, created_by) "
                "VALUES (:id, 'ulb-benchmark', 'snap-001', 'row-1', "
                "'not_reviewed', 'Test', 'fixture')"
            ), {"id": case_id})
            # Insert an event without event_seq.
            conn.execute(text(
                "INSERT INTO case_events (id, case_id, event_type, "
                "actor_ref, case_version) "
                "VALUES (:eid, :cid, 'created', 'fixture', 1)"
            ), {"eid": str(uuid.uuid4()), "cid": case_id})
            # Read back event_seq.
            result = conn.execute(text(
                "SELECT event_seq FROM case_events WHERE case_id = :cid"
            ), {"cid": case_id})
            seq = result.scalar_one()
            assert seq is not None
            assert seq >= 1
        engine.dispose()

    def test_event_seq_cannot_be_overridden(self, fresh_db_url):
        """GENERATED ALWAYS means the application cannot set event_seq."""
        import uuid

        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        engine = create_engine(fresh_db_url)
        with engine.begin() as conn:
            case_id = str(uuid.uuid4())
            conn.execute(text(
                "INSERT INTO review_cases (id, dataset_id, snapshot_id, "
                "record_ref, status, title, created_by) "
                "VALUES (:id, 'ulb-benchmark', 'snap-001', 'row-1', "
                "'not_reviewed', 'Test', 'fixture')"
            ), {"id": case_id})
            # Attempt to set event_seq explicitly — must fail.
            with pytest.raises(Exception):  # psycopg.errors.GeneratedAlways
                conn.execute(text(
                    "INSERT INTO case_events (id, case_id, event_type, "
                    "actor_ref, case_version, event_seq) "
                    "VALUES (:eid, :cid, 'created', 'fixture', 1, 999)"
                ), {"eid": str(uuid.uuid4()), "cid": case_id})
        engine.dispose()

    def test_downgrade_removes_event_seq(self, fresh_db_url):
        """Downgrading to 0001 drops the event_seq column."""
        from alembic import command

        command.upgrade(_alembic_config(fresh_db_url), "head")
        command.downgrade(_alembic_config(fresh_db_url), "0001_initial_review_cases")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns = {c["name"] for c in insp.get_columns("case_events")}
        assert "event_seq" not in columns
        # The new index is also gone.
        ce_indexes = {i["name"] for i in insp.get_indexes("case_events")}
        assert "ix_case_events_case_version_seq" not in ce_indexes
        engine.dispose()

    def test_upgrade_from_0001_to_head_adds_column(self, fresh_db_url):
        """Upgrading to 0001 first, then to head, adds event_seq."""
        from alembic import command

        cfg = _alembic_config(fresh_db_url)
        command.upgrade(cfg, "0001_initial_review_cases")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns_before = {c["name"] for c in insp.get_columns("case_events")}
        assert "event_seq" not in columns_before
        engine.dispose()

        command.upgrade(cfg, "head")
        engine = create_engine(fresh_db_url)
        insp = inspect(engine)
        columns_after = {c["name"] for c in insp.get_columns("case_events")}
        assert "event_seq" in columns_after
        engine.dispose()
