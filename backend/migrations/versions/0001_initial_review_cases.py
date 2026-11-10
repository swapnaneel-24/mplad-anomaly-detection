"""Initial review-case schema with append-only event trigger.

Creates the ``review_cases`` and ``case_events`` tables, their indexes,
CHECK constraints, and the PostgreSQL trigger that rejects ``UPDATE`` and
``DELETE`` on ``case_events`` (append-only enforcement at the database
boundary, PR-03 §7).

Revision ID: 0001_initial_review_cases
Revises:
Create Date: 2026-11-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_review_cases"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- review_cases --------------------------------------------------------
    op.create_table(
        "review_cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("dataset_id", sa.String(64), nullable=False),
        sa.Column("snapshot_id", sa.String(128), nullable=False),
        sa.Column("record_ref", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.String(4000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_reviewed','under_review','explained_deviation',"
            "'needs_source_verification','escalated_for_examination')",
            name="review_cases_status_enum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_cases"),
    )
    op.create_index(
        "ix_review_cases_dataset_id",
        "review_cases",
        ["dataset_id"],
    )
    op.create_index(
        "ix_review_cases_snapshot_id",
        "review_cases",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_review_cases_record_ref",
        "review_cases",
        ["record_ref"],
    )
    op.create_index(
        "ix_review_cases_created_by",
        "review_cases",
        ["created_by"],
    )
    op.create_index(
        "ix_review_cases_dataset_snapshot",
        "review_cases",
        ["dataset_id", "snapshot_id", "created_at"],
    )
    op.create_index(
        "ix_review_cases_status_created",
        "review_cases",
        ["status", "created_at"],
    )

    # --- case_events (append-only) ------------------------------------------
    op.create_table(
        "case_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column(
            "event_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("actor_ref", sa.String(128), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("event_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('created','note_added','status_changed',"
            "'decision_recorded','reopened')",
            name="case_events_event_type_enum",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["review_cases.id"],
            name="fk_case_events_case_id_review_cases",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_events"),
    )
    op.create_index(
        "ix_case_events_case_id",
        "case_events",
        ["case_id"],
    )
    op.create_index(
        "ix_case_events_event_at",
        "case_events",
        ["event_at"],
    )
    op.create_index(
        "ix_case_events_actor_ref",
        "case_events",
        ["actor_ref"],
    )
    op.create_index(
        "ix_case_events_case_version",
        "case_events",
        ["case_id", "case_version"],
    )

    # --- Append-only trigger (PR-03 §7) -------------------------------------
    # A PostgreSQL trigger rejects UPDATE and DELETE on case_events. This
    # enforces append-only behavior at the database boundary, not solely
    # through ORM convention. The trigger function raises an exception
    # that aborts the transaction.
    #
    # Note: this is an application-level append-only audit trail. It is
    # not tamper-proof against a database superuser (PR-03 §7). Application
    # privileges should additionally restrict the role used by the app.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_case_events_append_only()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'case_events is append-only: UPDATE and DELETE are not permitted (event_id=%)',
                OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_case_events_no_update
        BEFORE UPDATE ON case_events
        FOR EACH ROW
        EXECUTE FUNCTION enforce_case_events_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_case_events_no_delete
        BEFORE DELETE ON case_events
        FOR EACH ROW
        EXECUTE FUNCTION enforce_case_events_append_only();
        """
    )

    # Note: gen_random_uuid() is a built-in function on PostgreSQL 13+.
    # No extension creation is needed. If deploying on PostgreSQL < 13,
    # install pgcrypto separately before running this migration.


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_case_events_no_delete ON case_events")
    op.execute("DROP TRIGGER IF EXISTS trg_case_events_no_update ON case_events")
    op.execute("DROP FUNCTION IF EXISTS enforce_case_events_append_only()")
    op.drop_index("ix_case_events_case_version", table_name="case_events")
    op.drop_index("ix_case_events_actor_ref", table_name="case_events")
    op.drop_index("ix_case_events_event_at", table_name="case_events")
    op.drop_index("ix_case_events_case_id", table_name="case_events")
    op.drop_table("case_events")
    op.drop_index("ix_review_cases_status_created", table_name="review_cases")
    op.drop_index("ix_review_cases_dataset_snapshot", table_name="review_cases")
    op.drop_index("ix_review_cases_created_by", table_name="review_cases")
    op.drop_index("ix_review_cases_record_ref", table_name="review_cases")
    op.drop_index("ix_review_cases_snapshot_id", table_name="review_cases")
    op.drop_index("ix_review_cases_dataset_id", table_name="review_cases")
    op.drop_table("review_cases")
