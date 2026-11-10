"""Add event_seq for deterministic intra-version event ordering.

PR-03 hardening §2: ``record_decision()`` can generate a status-change
event and a decision-recorded event sharing the same ``case_version``.
The original ordering (``case_version, event_at, id``) is non-deterministic
within a version because ``clock_timestamp()`` can return the same value
for two rows inserted in the same transaction and the UUID is random.

This migration adds ``event_seq``, a PostgreSQL ``BIGINT GENERATED ALWAYS
AS IDENTITY`` column, to ``case_events``. The identity column provides a
monotonic, database-generated sequence that gives a deterministic total
order across all events. Combined with ``case_version`` it produces a
defensible chronological history: events are ordered by version first,
then by insertion sequence within a version.

The column is added as ``NOT NULL`` with a server-generated default, so
existing rows (if any) receive sequential values during the migration.
A new index ``ix_case_events_case_version_seq`` replaces the reliance on
``event_at`` for deterministic retrieval.

No uniqueness constraint is added on ``(case_id, case_version)`` because
multiple events per version are intentional (PR-03 hardening §2).

Revision ID: 0002_add_event_seq
Revises: 0001_initial_review_cases
Create Date: 2026-11-10

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_event_seq"
down_revision: Union[str, None] = "0001_initial_review_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the event_seq column as a PostgreSQL IDENTITY column.
    # GENERATED ALWAYS AS IDENTITY produces a monotonic BIGINT sequence
    # managed by PostgreSQL. The START WITH 1 INCREMENT BY 1 defaults are
    # fine; we specify them explicitly for documentation.
    #
    # Existing rows (if the table is not empty) receive sequential values
    # during the column addition because IDENTITY populates defaults for
    # existing rows.
    op.execute(
        "ALTER TABLE case_events "
        "ADD COLUMN event_seq BIGINT GENERATED ALWAYS AS IDENTITY "
        "(START WITH 1 INCREMENT BY 1) NOT NULL"
    )

    # New index for deterministic history retrieval: ordered by case,
    # version, then sequence. This replaces the reliance on event_at for
    # deterministic ordering within a version.
    op.create_index(
        "ix_case_events_case_version_seq",
        "case_events",
        ["case_id", "case_version", "event_seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_case_events_case_version_seq", table_name="case_events")
    op.execute("ALTER TABLE case_events DROP COLUMN event_seq")
