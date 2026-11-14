"""PR-07A Workstream K6 — synthetic demonstration boundary at the API
surface.

With ``demonstration_sources`` disabled:

* the synthetic record endpoints are unavailable (503, sanitized),
* the source registry lists nothing,
* no other GET endpoint exposes synthetic demonstration record content,
* case creation from the demonstration source is rejected.

Two sweeps cover the GET surface:

* ``test_no_get_endpoint_exposes_synthetic_content`` sweeps the
  documented non-parameterized GET paths against an empty case table
  (no synthetic record payload can be returned because no case exists
  and the synthetic source is disabled).
* ``test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case``
  warms a case from the synthetic source while
  ``demonstration_sources`` is enabled, then recreates the application
  with the flag disabled and probes the four parameterized GETs
  (``/api/v1/cases/{case_id}``, ``/api/v1/cases/{case_id}/history``,
  ``/api/v1/sources/{source_id}``,
  ``/api/v1/synthetic/records/{record_ref}``) against the persisted
  case. It asserts that the case detail/history endpoints return 200
  carrying only the case's own provenance fields (``record_ref``,
  ``dataset_id``, ``snapshot_id`` — which legitimately persist on the
  case row), and that no synthetic record **payload** marker
  (``SYNTHETIC DEMONSTRATION RECORD``, ``Fictional administrative
  record``, ``Synthetic evidence:``, etc.) leaks through any
  parameterized GET. The source-detail and synthetic-record-detail
  endpoints are unavailable (404 / 503) under the disabled flag.

The payload-marker set is a strict subset of the empty-table sweep's
``SYNTHETIC_MARKERS``: it excludes the case-provenance refs
(``synth-001``, ``synthetic-v1``) because a persisted case
legitimately carries them as its own immutable provenance — that is
not a leak, it is the case's identity.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.db.session import DatabaseSessionFactory, create_session_factory
from app.main import create_app
from tests.conftest import TEST_SESSION_SECRET, get_csrf_token, login

PASSWORD = "correct-horse-battery-staple"

#: Content markers that must never appear while the source is disabled.
SYNTHETIC_MARKERS = (
    "SYNTHETIC DEMONSTRATION RECORD",
    "synth-001",
    "synth-002",
    "Fictional administrative record",
    "synthetic-v1",
)

#: Synthetic record PAYLOAD markers — strings that appear only inside
#: the fictional record body (``title``, ``description``,
#: ``evidence_summary``, ``administrative_context``, ``limitations``),
#: never inside a case's own provenance fields. A persisted case
#: legitimately carries ``record_ref="synth-001"``,
#: ``dataset_id="synthetic-demonstration"`` and
#: ``snapshot_id="synthetic-v1"`` as its own identity — those are
#: provenance, not synthetic content, and are excluded from this set.
SYNTHETIC_RECORD_PAYLOAD_MARKERS = (
    "SYNTHETIC DEMONSTRATION RECORD",
    "Fictional administrative record",
    "Synthetic evidence:",
    "Synthetic context:",
    "Synthetic data does not reflect the verified ULB benchmark",
    "NOT A RESEARCH FINDING",
)


@pytest.fixture()
def boundary_settings(db_url):
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
        demonstration_sources=False,
    )


@pytest.fixture()
def boundary_app(boundary_settings, db_session_factory):
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    return create_app(
        settings=boundary_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


@pytest.fixture()
def boundary_reviewer(db_session_factory):
    from app.auth.passwords import hash_password
    from app.db.models import User

    with db_session_factory() as session:
        user = User(
            username="boundary-reviewer",
            password_hash=hash_password(PASSWORD),
            display_name="Boundary Reviewer",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def boundary_persisted_case(db_url, db_session_factory):
    """Create a case from the synthetic source, then return its identity.

    Builds a *warm* application with ``demonstration_sources=True`` so
    that case creation from the synthetic source succeeds, creates
    exactly one case bound to ``synth-001``, then disposes the warm
    engine. The case row persists in the shared PostgreSQL database
    after this fixture returns; the *cold* application built by
    ``boundary_app_with_case`` (``demonstration_sources=False``) will
    see it via the parameterized GET endpoints.

    Returns a dict with ``case_id``, ``record_ref`` and ``source_id``
    for the cold probe to use.
    """
    from app.auth.passwords import hash_password
    from app.db.models import User

    # Clean slate (auth + case tables) so the persisted case is the
    # only one present.
    from tests.conftest import _truncate_auth_tables

    _truncate_auth_tables(db_session_factory)
    with db_session_factory() as session:
        session.execute(text("TRUNCATE TABLE case_events RESTART IDENTITY CASCADE"))
        session.execute(text("TRUNCATE TABLE review_cases RESTART IDENTITY CASCADE"))
        session.commit()

    # Create the reviewer directly in the DB (the cold app will use
    # the same row for login).
    with db_session_factory() as session:
        user = User(
            username="boundary-reviewer",
            password_hash=hash_password(PASSWORD),
            display_name="Boundary Reviewer",
            role="reviewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    warm_settings = Settings(
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
    warm_engine = create_engine(db_url, future=True)
    try:
        warm_factory = create_session_factory(warm_engine)
        warm_app = create_app(
            settings=warm_settings,
            db_session_factory_override=DatabaseSessionFactory(warm_engine, warm_factory),
        )
        warm_client = TestClient(warm_app)
        assert login(warm_client, "boundary-reviewer", PASSWORD).status_code == 200
        headers = {"X-CSRF-Token": get_csrf_token(warm_client)}
        created = warm_client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "persisted-for-cold-probe",
                "created_by": "ignored",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]
        warm_client.close()
    finally:
        warm_engine.dispose()

    return {
        "case_id": case_id,
        "record_ref": "synth-001",
        "source_id": "synthetic-demonstration",
    }


@pytest.fixture()
def boundary_app_with_case(boundary_settings, db_session_factory, boundary_persisted_case):
    """Cold app (demonstration_sources=False) against a DB with a
    persisted synthetic-source case.

    Does NOT truncate — the warm case must survive for the parameterized
    GET probe. The cold app uses the same shared DB engine as the rest
    of the suite.
    """
    return create_app(
        settings=boundary_settings,
        db_session_factory_override=DatabaseSessionFactory(
            db_session_factory.kw["bind"], db_session_factory
        ),
    )


class TestDisabledSourceExposureSweep:
    def test_no_get_endpoint_exposes_synthetic_content(
        self, boundary_app, boundary_reviewer
    ):
        client = TestClient(boundary_app)
        assert login(client, "boundary-reviewer", PASSWORD).status_code == 200
        csrf_headers = {"X-CSRF-Token": get_csrf_token(client)}

        # The documented non-parameterized GET surface (auth + CSRF not
        # needed for most, but sending them harms nothing and matches a
        # real client). Parameterized GETs (paths containing ``{``) are
        # swept separately by ``test_parameterized_gets_...`` against a
        # persisted case, because probing them requires a real case_id
        # / record_ref / source_id that does not exist when the case
        # table is empty and the source is disabled.
        get_paths = [
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/api/v1/meta",
            "/api/v1/sources",
            "/api/v1/cases",
            "/api/v1/synthetic/records",
            "/api/v1/synthetic/records/synth-001",
            "/api/v1/auth/me",
            "/api/v1/auth/csrf",
            "/api/v1/research/sources",
        ]
        # OpenAPI-driven completeness: sweep every documented non-
        # parameterized GET path. Parameterized GETs are covered by the
        # persisted-case test below.
        spec = client.get("/openapi.json").json()
        documented_non_param_gets = {
            path for path, item in spec["paths"].items()
            if "get" in item and "{" not in path
        }
        assert documented_non_param_gets <= set(get_paths) | {"/openapi.json"}, (
            f"new non-parameterized GET route(s) not swept: "
            f"{documented_non_param_gets - set(get_paths)}"
        )

        bodies: dict[str, str] = {}
        for path in get_paths:
            response = client.get(path, headers=csrf_headers)
            bodies[path] = response.text

        # The demonstration endpoints are explicitly unavailable.
        assert client.get("/api/v1/synthetic/records").status_code == 503
        assert client.get("/api/v1/synthetic/records/synth-001").status_code == 503

        # The source registry is empty.
        sources = client.get("/api/v1/sources").json()
        assert sources["count"] == 0
        assert sources["sources"] == []

        # No swept body carries synthetic demonstration content.
        for path, body in bodies.items():
            for marker in SYNTHETIC_MARKERS:
                assert marker not in body, (
                    f"{path} leaked synthetic content marker {marker!r} "
                    "while demonstration_sources is disabled"
                )

    def test_parameterized_gets_do_not_leak_synthetic_payload_with_persisted_case(
        self, boundary_app_with_case, boundary_persisted_case
    ):
        """With demonstration_sources disabled but a case already
        persisted (created while the source was enabled, then the flag
        flipped off), probe every parameterized GET and assert that no
        synthetic record PAYLOAD content leaks through any of them.

        The case's own provenance fields (``record_ref="synth-001"``,
        ``dataset_id="synthetic-demonstration"``,
        ``snapshot_id="synthetic-v1"``) legitimately appear in the case
        detail response — these are the case's identity, not synthetic
        record content. The assertion uses
        ``SYNTHETIC_RECORD_PAYLOAD_MARKERS`` (the strict subset of
        ``SYNTHETIC_MARKERS`` that excludes provenance refs) so the
        test does not false-positive on legitimate provenance.
        """
        client = TestClient(boundary_app_with_case)
        assert login(client, "boundary-reviewer", PASSWORD).status_code == 200
        csrf_headers = {"X-CSRF-Token": get_csrf_token(client)}

        case_id = boundary_persisted_case["case_id"]
        source_id = boundary_persisted_case["source_id"]
        record_ref = boundary_persisted_case["record_ref"]
        # The research source ID is a frozen scientific artifact identifier,
        # NOT a synthetic demonstration source — it is always available
        # regardless of the demonstration_sources flag.
        research_source_id = "phase6-reference-values"

        # OpenAPI-driven completeness: every parameterized GET path in
        # the contract is probed.
        spec = client.get("/openapi.json").json()
        documented_param_gets = {
            path for path, item in spec["paths"].items()
            if "get" in item and "{" in path
        }
        # The parameterized GETs we will probe, with the persisted
        # case's identity and the research source ID substituted in.
        probe_paths = {
            f"/api/v1/cases/{case_id}",
            f"/api/v1/cases/{case_id}/history",
            f"/api/v1/sources/{source_id}",
            f"/api/v1/synthetic/records/{record_ref}",
            f"/api/v1/research/sources/{research_source_id}",
            f"/api/v1/research/sources/{research_source_id}/results",
        }
        # All parameterized GET paths documented in the OpenAPI contract
        # must be covered by the probe (substituting the persisted
        # case's identity for the path parameters).
        documented_param_templates = {
            # Collapse the substituted probe paths back to their
            # templates for comparison.
            path.replace(case_id, "{case_id}")
            .replace(source_id, "{source_id}")
            .replace(record_ref, "{record_ref}")
            .replace(research_source_id, "{source_id}")
            for path in probe_paths
        }
        assert documented_param_gets <= documented_param_templates, (
            f"parameterized GET route(s) not probed: "
            f"{documented_param_gets - documented_param_templates}"
        )

        bodies: dict[str, str] = {}
        statuses: dict[str, int] = {}
        for path in probe_paths:
            response = client.get(path, headers=csrf_headers)
            bodies[path] = response.text
            statuses[path] = response.status_code

        # The case detail and history endpoints return 200 — the case
        # exists in the DB; the disabled flag does not gate reads of
        # already-persisted cases.
        assert statuses[f"/api/v1/cases/{case_id}"] == 200, bodies[f"/api/v1/cases/{case_id}"]
        assert statuses[f"/api/v1/cases/{case_id}/history"] == 200, bodies[f"/api/v1/cases/{case_id}/history"]

        # The synthetic record detail endpoint is unavailable (503)
        # under the disabled flag — the synthetic source's record
        # payload is gated behind demonstration_sources.
        assert statuses[f"/api/v1/synthetic/records/{record_ref}"] == 503, (
            bodies[f"/api/v1/synthetic/records/{record_ref}"]
        )
        assert (
            "SERVICE_NOT_READY"
            in bodies[f"/api/v1/synthetic/records/{record_ref}"]
        )

        # The source descriptor lookup returns 404 SOURCE_NOT_FOUND —
        # the registry is empty when demonstration_sources is disabled,
        # so even the synthetic-demonstration source ID is unresolvable.
        assert statuses[f"/api/v1/sources/{source_id}"] == 404, (
            bodies[f"/api/v1/sources/{source_id}"]
        )
        assert (
            "SOURCE_NOT_FOUND"
            in bodies[f"/api/v1/sources/{source_id}"]
        )

        # No parameterized GET body carries synthetic record PAYLOAD
        # content. The case's own provenance refs may legitimately
        # appear (``synth-001``, ``synthetic-demonstration``,
        # ``synthetic-v1``) — those are the case's identity, not
        # synthetic record content.
        for path, body in bodies.items():
            for marker in SYNTHETIC_RECORD_PAYLOAD_MARKERS:
                assert marker not in body, (
                    f"{path} leaked synthetic record payload marker "
                    f"{marker!r} while demonstration_sources is disabled"
                )

        # Sanity: the case detail body DOES carry the case's own
        # provenance refs (these are not "leaked synthetic content";
        # they are the case's identity, persisted when it was created
        # from the synthetic source while that source was enabled).
        case_detail_body = bodies[f"/api/v1/cases/{case_id}"]
        assert "synth-001" in case_detail_body, (
            "the persisted case's record_ref should appear in its own detail"
        )
        assert "synthetic-demonstration" in case_detail_body
        assert "synthetic-v1" in case_detail_body

    def test_case_creation_from_demonstration_source_rejected(
        self, boundary_app, boundary_reviewer
    ):
        client = TestClient(boundary_app)
        assert login(client, "boundary-reviewer", PASSWORD).status_code == 200
        headers = {"X-CSRF-Token": get_csrf_token(client)}

        response = client.post(
            "/api/v1/cases",
            json={
                "dataset_id": "synthetic-demonstration",
                "snapshot_id": "synthetic-v1",
                "record_ref": "synth-001",
                "title": "should-not-exist",
                "created_by": "ignored",
            },
            headers=headers,
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
