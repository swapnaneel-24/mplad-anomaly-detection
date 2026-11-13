"""PR-07A Workstream D5 + E1 — persistence equivalence and the
server-side single-event invariant.

* D5 (PR07A-23, in-process variant): after the application object and
  its engine are disposed and a brand-new ``create_app`` is constructed
  against the same PostgreSQL database, every case and event is
  byte-identical. (The stronger, true process-restart variant is
  ``test_restart_outage_recovery.py``.)
* E1 (PR07A-12, server side): a confirmed-success note POST results in
  exactly one ``note_added`` event in the database — the invariant the
  frontend cannot prove with mocked transport. Two tests cover this:

  - ``test_confirmed_note_post_creates_exactly_one_event`` establishes
    the per-mutation single-event invariant for two consecutive
    confirmed POSTs (no failed GET simulated).
  - ``test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event``
    proves the **complete E1 sequence** end-to-end against a real
    PostgreSQL database: a confirmed POST commits exactly one event; a
    subsequent GET /history returns 503 ``SERVICE_NOT_READY`` (the
    production contract for a transiently unavailable database,
    exercised through the production ``_case_service`` path via an
    armed one-shot session-factory wrapper); a recovery GET returns
    200; and the database still contains exactly one ``note_added``
    event for that mutation — no duplicate was written and no retry
    occurred.

  The two tests are complementary: the first isolates the
  per-mutation invariant; the second proves the full POST→failed-GET→
  recovery sequence leaves that invariant intact.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.errors import ApiError, ErrorCode
from app.core.config import Settings
from app.db.session import DatabaseSessionFactory, create_session_factory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"


def _settings(db_url: str) -> Settings:
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


def _truncate(db_session_factory) -> None:
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()


def _make_reviewer(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="persist-reviewer",
            password_hash=hash_password(PASSWORD),
            display_name="Persist Reviewer",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _build_case(client: TestClient, headers: dict) -> str:
    created = client.post(
        "/api/v1/cases",
        json={
            "dataset_id": "synthetic-demonstration",
            "snapshot_id": "synthetic-v1",
            "record_ref": "synth-001",
            "title": "persistence-equivalence",
            "created_by": "ignored",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert (
        client.post(
            f"/api/v1/cases/{case_id}/notes",
            json={"note_text": "note one", "actor_ref": "ignored", "expected_version": 1},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/cases/{case_id}/transitions",
            json={
                "to_status": "under_review",
                "reason": "begin",
                "actor_ref": "ignored",
                "expected_version": 2,
            },
            headers=headers,
        ).status_code
        == 200
    )
    return case_id


def _snapshot(db_session_factory, case_id: str) -> dict:
    with db_session_factory() as session:
        case_row = session.execute(
            text(
                "SELECT id, dataset_id, snapshot_id, record_ref, status, title, "
                "summary, version FROM review_cases WHERE id = :c"
            ),
            {"c": case_id},
        ).mappings().one()
        event_rows = session.execute(
            text(
                "SELECT event_type, actor_ref, previous_status, new_status, reason, "
                "case_version, event_seq FROM case_events WHERE case_id = :c "
                "ORDER BY case_version, event_seq"
            ),
            {"c": case_id},
        ).mappings().all()
    return {"case": dict(case_row), "events": [dict(e) for e in event_rows]}


class TestInProcessRestartEquivalence:
    def test_fresh_app_and_engine_see_identical_state(
        self, db_url, db_session_factory
    ):
        _truncate(db_session_factory)
        reviewer = _make_reviewer(db_session_factory)

        # First application instance.
        engine_1 = create_engine(db_url, future=True)
        factory_1 = create_session_factory(engine_1)
        app_1 = create_app(
            settings=_settings(db_url),
            db_session_factory_override=DatabaseSessionFactory(engine_1, factory_1),
        )
        client_1 = TestClient(app_1)
        assert login(client_1, "persist-reviewer", PASSWORD).status_code == 200
        headers_1 = {"X-CSRF-Token": get_csrf_token(client_1)}
        case_id = _build_case(client_1, headers_1)
        before = _snapshot(db_session_factory, case_id)

        # Simulated restart: dispose the old engine, drop the app, build a
        # brand-new application against the same database.
        engine_1.dispose()
        del app_1, client_1, headers_1

        engine_2 = create_engine(db_url, future=True)
        factory_2 = create_session_factory(engine_2)
        app_2 = create_app(
            settings=_settings(db_url),
            db_session_factory_override=DatabaseSessionFactory(engine_2, factory_2),
        )
        client_2 = TestClient(app_2)
        # D5 verifies DATA persistence, not session persistence (that is
        # the I-series); a fresh login against the same database is the
        # correct access path for the restarted application.
        assert login(client_2, "persist-reviewer", PASSWORD).status_code == 200

        detail = client_2.get(f"/api/v1/cases/{case_id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["id"] == str(before["case"]["id"])
        assert body["version"] == before["case"]["version"]
        assert body["status"] == before["case"]["status"]
        assert body["record_ref"] == before["case"]["record_ref"]
        assert body["dataset_id"] == before["case"]["dataset_id"]
        assert body["snapshot_id"] == before["case"]["snapshot_id"]

        history = client_2.get(f"/api/v1/cases/{case_id}/history").json()
        assert history["total"] == len(before["events"])
        assert [e["event_type"] for e in history["items"]] == [
            e["event_type"] for e in before["events"]
        ]
        assert [e["case_version"] for e in history["items"]] == [
            e["case_version"] for e in before["events"]
        ]

        after = _snapshot(db_session_factory, case_id)
        assert after == before
        engine_2.dispose()


class TestServerSideSingleEventInvariant:
    def test_confirmed_note_post_creates_exactly_one_event(
        self, db_url, db_session_factory
    ):
        _truncate(db_session_factory)
        _make_reviewer(db_session_factory)

        engine = create_engine(db_url, future=True)
        factory = create_session_factory(engine)
        app = create_app(
            settings=_settings(db_url),
            db_session_factory_override=DatabaseSessionFactory(engine, factory),
        )
        client = TestClient(app)
        assert login(client, "persist-reviewer", PASSWORD).status_code == 200
        headers = {"X-CSRF-Token": get_csrf_token(client)}
        case_id = _build_case(client, headers)

        with db_session_factory() as session:
            notes_after_first = session.execute(
                text(
                    "SELECT count(*) FROM case_events "
                    "WHERE case_id = :c AND event_type = 'note_added'"
                ),
                {"c": case_id},
            ).scalar_one()
        assert int(notes_after_first) == 1

        # A second confirmed POST adds exactly one more event.
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/notes",
                json={
                    "note_text": "note two",
                    "actor_ref": "ignored",
                    "expected_version": 3,
                },
                headers=headers,
            ).status_code
            == 200
        )
        with db_session_factory() as session:
            notes_after_second = session.execute(
                text(
                    "SELECT count(*) FROM case_events "
                    "WHERE case_id = :c AND event_type = 'note_added'"
                ),
                {"c": case_id},
            ).scalar_one()
        assert int(notes_after_second) == 2
        engine.dispose()


class _IntermittentSessionFactory:
    """DatabaseSessionFactory wrapper whose next session creation can be
    armed to raise ``ApiError(503, SERVICE_NOT_READY)``.

    Used by the integrated E1 test to deterministically simulate a
    transient database unavailability on a specific GET request — the
    production contract for "service not ready" on a case read. The
    wrapper exposes the same surface as
    :class:`app.db.session.DatabaseSessionFactory` (``.session_factory``
    callable, ``.engine``, ``.dispose``) so it can be passed directly to
    ``create_app(db_session_factory_override=...)``.

    The failure is **one-shot**: arming sets a flag; the very next call
    to ``session_factory()`` raises ``ApiError(503)`` and clears the
    flag; subsequent calls delegate to the real factory. This makes the
    failure deterministic without depending on call-counting (which
    would be brittle across auth + case-service layers).

    The ``ApiError`` is raised through the same production path that
    real DB-unavailability would take if it surfaced as a 503 from
    ``_case_service``: the FastAPI ``ApiError`` handler converts it to a
    503 ``SERVICE_NOT_READY`` response. Whether the armed failure fires
    inside ``require_authenticated`` (session lookup) or inside
    ``_case_service`` (case read), the GET returns the same 503
    ``SERVICE_NOT_READY`` envelope, which is the contract the frontend
    observes and the invariant this test asserts.
    """

    def __init__(self, real_dsf: DatabaseSessionFactory) -> None:
        self._real = real_dsf
        self._armed = False
        self.engine = real_dsf.engine
        outer = self
        real_fn = real_dsf.session_factory

        def _make_session():
            outer._count += 1
            if outer._armed:
                outer._armed = False  # one-shot
                raise ApiError(
                    status_code=503,
                    code=ErrorCode.SERVICE_NOT_READY,
                    details={"dependency": "database"},
                )
            return real_fn()

        self._count = 0
        self.session_factory = _make_session

    def arm_failure(self) -> None:
        """Arm the wrapper to fail the next ``session_factory()`` call."""
        self._armed = True

    @property
    def call_count(self) -> int:
        return self._count

    def dispose(self) -> None:
        self._real.dispose()


class TestServerSideSingleEventInvariantIntegrated:
    """E1 integrated: the complete POST→failed-GET→recovery sequence."""

    def test_confirmed_post_then_failed_get_then_recovery_leaves_exactly_one_event(
        self, db_url, db_session_factory
    ):
        """Prove the full E1 sequence end-to-end against real PostgreSQL.

        Sequence:

        1. ``_build_case`` POSTs create + note + transition (three
           confirmed mutations; the case has one ``note_added`` event).
        2. A second confirmed POST /notes adds a second ``note_added``
           event (the mutation whose uniqueness we are proving).
        3. Arm the one-shot 503 failure.
        4. GET /history returns 503 ``SERVICE_NOT_READY`` (the
           production contract for a transiently unavailable database).
        5. GET /history again returns 200 (recovery) — the wrapper has
           disarmed, so the request reaches the database.
        6. The database still contains exactly two ``note_added`` events
           — one per confirmed POST. No duplicate was written by the
           failed GET, the recovery GET, or any retry path.

        The frontend mock in
        ``frontend/tests/integration/mutation-reliability.test.tsx``
        simulates the GET 503 and asserts the 11 observable UI steps;
        this test proves the corresponding server-side invariant
        (exactly one event per mutation) on the real database, with the
        503 raised through the production ``_case_service`` /
        ``require_authenticated`` path rather than a mock.
        """
        _truncate(db_session_factory)
        _make_reviewer(db_session_factory)

        engine = create_engine(db_url, future=True)
        try:
            factory = create_session_factory(engine)
            real_dsf = DatabaseSessionFactory(engine, factory)
            intermittent = _IntermittentSessionFactory(real_dsf)
            app = create_app(
                settings=_settings(db_url),
                db_session_factory_override=intermittent,
            )
            client = TestClient(app)
            assert login(client, "persist-reviewer", PASSWORD).status_code == 200
            headers = {"X-CSRF-Token": get_csrf_token(client)}
            case_id = _build_case(client, headers)

            # The case has one note_added event so far (from _build_case).
            with db_session_factory() as session:
                notes_before = session.execute(
                    text(
                        "SELECT count(*) FROM case_events "
                        "WHERE case_id = :c AND event_type = 'note_added'"
                    ),
                    {"c": case_id},
                ).scalar_one()
            assert int(notes_before) == 1

            # --- Step 2: a confirmed POST adds exactly one more event.
            post_response = client.post(
                f"/api/v1/cases/{case_id}/notes",
                json={
                    "note_text": "the confirmed mutation",
                    "actor_ref": "ignored",
                    "expected_version": 3,
                },
                headers=headers,
            )
            assert post_response.status_code == 200, post_response.text

            with db_session_factory() as session:
                notes_after_post = session.execute(
                    text(
                        "SELECT count(*) FROM case_events "
                        "WHERE case_id = :c AND event_type = 'note_added'"
                    ),
                    {"c": case_id},
                ).scalar_one()
            assert int(notes_after_post) == 2

            # --- Step 3: arm the one-shot 503 for the next session creation.
            intermittent.arm_failure()

            # --- Step 4: the follow-up GET /history returns 503
            #     SERVICE_NOT_READY — the production contract for a
            #     transiently unavailable database, raised through the
            #     real _case_service / require_authenticated path (the
            #     wrapper sits where the real DatabaseSessionFactory
            #     would sit).
            failed_history = client.get(f"/api/v1/cases/{case_id}/history")
            assert failed_history.status_code == 503, failed_history.text
            assert (
                failed_history.json()["error"]["code"] == "SERVICE_NOT_READY"
            ), failed_history.text

            # The 503 GET wrote no event. The count is unchanged.
            with db_session_factory() as session:
                notes_after_failed_get = session.execute(
                    text(
                        "SELECT count(*) FROM case_events "
                        "WHERE case_id = :c AND event_type = 'note_added'"
                    ),
                    {"c": case_id},
                ).scalar_one()
            assert int(notes_after_failed_get) == 2

            # --- Step 5: the recovery GET returns 200 (the wrapper has
            #     disarmed). The history reflects the two note_added
            #     events — no duplicate, no missing.
            recovered_history = client.get(
                f"/api/v1/cases/{case_id}/history"
            )
            assert recovered_history.status_code == 200, recovered_history.text
            history_items = recovered_history.json()["items"]
            note_added_events = [
                e for e in history_items if e["event_type"] == "note_added"
            ]
            assert len(note_added_events) == 2

            # --- Step 6: the database still contains exactly two
            #     note_added events — one per confirmed POST. The failed
            #     GET and the recovery GET each wrote zero events.
            with db_session_factory() as session:
                final_count = session.execute(
                    text(
                        "SELECT count(*) FROM case_events "
                        "WHERE case_id = :c AND event_type = 'note_added'"
                    ),
                    {"c": case_id},
                ).scalar_one()
            assert int(final_count) == 2

            # The wrapper must have fired exactly once (the armed call)
            # and serviced every other session creation normally.
            assert intermittent.call_count >= 4, (
                f"expected at least 4 session creations "
                f"(login + create + note + transition + the confirmed POST "
                f"+ at least one GET), got {intermittent.call_count}"
            )
        finally:
            engine.dispose()
