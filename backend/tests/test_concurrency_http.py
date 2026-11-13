"""PR-07A Workstream C — HTTP-level optimistic-concurrency tests.

C1 (PR07A-08): two authenticated reviewer sessions submit permitted
mutations based on the same case version, dispatched concurrently
against the real pgserver-backed PostgreSQL database.

Determinism and overlap proof:

* Both POSTs are released simultaneously by a ``threading.Barrier(2)``.
* Overlap is NOT merely assumed from the barrier dispatch: a SQLAlchemy
  ``before_cursor_execute`` hook parks BOTH request threads at a second
  barrier at the moment each is about to execute its
  ``UPDATE review_cases ...`` statement. The barrier only fires when
  both transactions are open and in flight; if one request had fully
  completed before the other started, the barrier would break
  (``BrokenBarrierError``) instead of silently passing.
* The winner is decided by PostgreSQL row locking on the atomic
  ``UPDATE ... WHERE id = :id AND version = :expected``; the invariant
  (exactly one 2xx, exactly one 409) holds regardless of which wins.

C3 (PR07A-08 extension): a repeated stale mutation stays 409 without
any authorized retry, until the client re-reads the current version.
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def conc_settings(db_url):
    """Settings with DB + auth + demonstration sources enabled."""
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://test.example"],
        git_commit_sha=None,
        docs_enabled=True,
        database_url=db_url,
        database_required=True,
        session_secret=TEST_SESSION_SECRET,
        session_cookie_secure=False,
        demonstration_sources=True,
    )


@pytest.fixture()
def conc_app(conc_settings, db_session_factory):
    """Application with DB + auth + synthetic source wired in (clean state)."""
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=conc_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


def _make_user(db_session_factory, username: str, role: str = "reviewer"):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password(PASSWORD),
            display_name=username.title(),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _db_counts(db_session_factory, case_id: str) -> tuple[int, int]:
    """Return (case version, total event count) read directly from the DB."""
    with db_session_factory() as session:
        version = session.execute(
            text("SELECT version FROM review_cases WHERE id = :cid"), {"cid": case_id}
        ).scalar_one()
        events = session.execute(
            text("SELECT count(*) FROM case_events WHERE case_id = :cid"), {"cid": case_id}
        ).scalar_one()
    return int(version), int(events)


def _note_payload(expected_version: int, note: str) -> dict:
    return {
        "note_text": note,
        "actor_ref": "ignored-client-value",
        "expected_version": expected_version,
    }


class TestTwoReviewerConcurrencyHttp:
    def test_concurrent_same_version_mutations_exactly_one_wins(
        self, conc_app, db_session_factory, db_engine
    ):
        reviewer_a = _make_user(db_session_factory, "conc-reviewer-a")
        reviewer_b = _make_user(db_session_factory, "conc-reviewer-b")

        client_a = TestClient(conc_app)
        client_b = TestClient(conc_app)
        assert login(client_a, "conc-reviewer-a", PASSWORD).status_code == 200
        assert login(client_b, "conc-reviewer-b", PASSWORD).status_code == 200
        headers_a = {"X-CSRF-Token": get_csrf_token(client_a)}
        headers_b = {"X-CSRF-Token": get_csrf_token(client_b)}

        # Reviewer A creates the case (version 1).
        created = client_a.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "c1-concurrency",
                "created_by": "ignored",
            },
            headers=headers_a,
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]

        # Both reviewers independently read version 1.
        for client in (client_a, client_b):
            detail = client.get(f"/api/v1/cases/{case_id}")
            assert detail.status_code == 200
            assert detail.json()["version"] == 1

        version_before, events_before = _db_counts(db_session_factory, case_id)
        assert (version_before, events_before) == (1, 1)

        # Second barrier: fires only when BOTH transactions are in flight,
        # each about to execute its UPDATE review_cases statement. This is
        # the proof of genuine transaction-level overlap — not just
        # barrier-synchronized dispatch.
        in_flight = threading.Barrier(2, timeout=30)
        overlap_confirmed = threading.Event()

        def _gate(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE REVIEW_CASES"):
                try:
                    in_flight.wait(timeout=30)
                except threading.BrokenBarrierError:
                    return
                overlap_confirmed.set()

        event.listen(db_engine, "before_cursor_execute", _gate)
        try:
            results: dict[str, object] = {}

            def _submit(tag: str, client: TestClient, headers: dict) -> None:
                response = client.post(
                    f"/api/v1/cases/{case_id}/notes",
                    json=_note_payload(1, f"concurrent note from {tag}"),
                    headers=headers,
                )
                results[tag] = response.status_code

            thread_a = threading.Thread(
                target=_submit, args=("a", client_a, headers_a), name="reviewer-a"
            )
            thread_b = threading.Thread(
                target=_submit, args=("b", client_b, headers_b), name="reviewer-b"
            )
            thread_a.start()
            thread_b.start()
            thread_a.join(timeout=60)
            thread_b.join(timeout=60)
        finally:
            event.remove(db_engine, "before_cursor_execute", _gate)

        # The overlap barrier actually fired: both UPDATE statements were
        # in flight simultaneously.
        assert overlap_confirmed.is_set(), (
            "The in-flight barrier never fired — the two mutations did not "
            "overlap at the transaction level."
        )

        # Exactly one mutation succeeded and exactly one conflicted.
        statuses = sorted(results.values())
        assert statuses == [200, 409], f"expected one 200 and one 409, got {results}"

        # Final state: version advanced exactly once, exactly one new event.
        version_after, events_after = _db_counts(db_session_factory, case_id)
        assert version_after == 2
        assert events_after == 2

        # The surviving note event is attributed to the WINNING reviewer.
        winner_tag = next(tag for tag, code in results.items() if code == 200)
        winner_id = reviewer_a.id if winner_tag == "a" else reviewer_b.id
        with db_session_factory() as session:
            note_events = session.execute(
                text(
                    "SELECT actor_ref FROM case_events "
                    "WHERE case_id = :cid AND event_type = 'note_added'"
                ),
                {"cid": case_id},
            ).scalars().all()
        assert len(note_events) == 1
        assert note_events[0] == winner_id

        # The 409 response carries the concurrency details.
        loser_tag = next(tag for tag, code in results.items() if code == 409)
        loser_client = client_a if loser_tag == "a" else client_b
        loser_response = loser_client.post(
            f"/api/v1/cases/{case_id}/notes",
            json=_note_payload(1, "repeated stale attempt"),
            headers=headers_a if loser_tag == "a" else headers_b,
        )
        assert loser_response.status_code == 409
        assert loser_response.json()["error"]["code"] == "CONFLICT"

        # No lost update, no duplicate event after the repeat.
        version_final, events_final = _db_counts(db_session_factory, case_id)
        assert (version_final, events_final) == (2, 2)


class TestRepeatedStaleMutation:
    def test_repeated_stale_mutation_stays_409_until_fresh_version(
        self, conc_app, db_session_factory
    ):
        reviewer = _make_user(db_session_factory, "conc-reviewer-solo")
        client = TestClient(conc_app)
        assert login(client, "conc-reviewer-solo", PASSWORD).status_code == 200
        headers = {"X-CSRF-Token": get_csrf_token(client)}

        created = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "c3-repeated-stale",
                "created_by": "ignored",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]

        # Advance to version 2.
        first = client.post(
            f"/api/v1/cases/{case_id}/notes",
            json=_note_payload(1, "first note"),
            headers=headers,
        )
        assert first.status_code == 200

        # Repeated stale mutation (expected_version=1, current is 2).
        for attempt in range(2):
            stale = client.post(
                f"/api/v1/cases/{case_id}/notes",
                json=_note_payload(1, f"stale attempt {attempt}"),
                headers=headers,
            )
            assert stale.status_code == 409
            assert stale.json()["error"]["code"] == "CONFLICT"

        version, events = _db_counts(db_session_factory, case_id)
        assert (version, events) == (2, 2)

        # Authorized retry with the fresh version succeeds.
        fresh = client.post(
            f"/api/v1/cases/{case_id}/notes",
            json=_note_payload(2, "retry with fresh version"),
            headers=headers,
        )
        assert fresh.status_code == 200
        version, events = _db_counts(db_session_factory, case_id)
        assert (version, events) == (3, 3)
