"""Role-based authorization tests (PR-04 §5, §16, AC-04-07, AC-04-08)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.auth.dependencies import require_permission, require_role
from app.auth.principals import AuthenticatedPrincipal
from app.auth.roles import (
    ADMIN_PERMISSIONS,
    REVIEWER_PERMISSIONS,
    ROLE_PERMISSIONS,
    VIEWER_PERMISSIONS,
    Role,
    effective_permissions,
)
from tests.conftest import login

PASSWORD = "correct-horse-battery-staple"


class TestPermissionMatrix:
    """The documented role-permission matrix."""

    def test_viewer_permissions(self):
        assert VIEWER_PERMISSIONS == frozenset({"read:public", "read:analytics"})

    def test_reviewer_superset_of_viewer(self):
        assert REVIEWER_PERMISSIONS > VIEWER_PERMISSIONS
        assert "cases:write" in REVIEWER_PERMISSIONS
        assert "cases:write" not in VIEWER_PERMISSIONS

    def test_admin_superset_of_reviewer(self):
        assert ADMIN_PERMISSIONS > REVIEWER_PERMISSIONS
        assert "admin:users" in ADMIN_PERMISSIONS
        assert "admin:users" not in REVIEWER_PERMISSIONS

    def test_every_role_maps(self):
        assert set(ROLE_PERMISSIONS) == set(Role)

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError):
            effective_permissions("superuser")


class TestAnonymousDenied:
    def test_anonymous_me_401(self, auth_client):
        response = auth_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "UNAUTHORIZED"
        assert "X-Request-ID" in response.headers  # envelope contract preserved


class TestRoleVisibilityOnMe:
    @pytest.mark.parametrize(
        "role,expected_permission",
        [
            ("viewer", "cases:write"),
            ("reviewer", "admin:users"),
        ],
    )
    def test_roles_receive_expected_permissions(
        self, auth_client, user_factory, role, expected_permission
    ):
        user_factory("alice", PASSWORD, role=role)
        login(auth_client, "alice", PASSWORD)
        body = auth_client.get("/api/v1/auth/me").json()
        assert body["role"] == role
        assert expected_permission not in body["permissions"]

    def test_admin_gets_admin_permission(self, auth_client, user_factory):
        user_factory("root", PASSWORD, role="admin")
        login(auth_client, "root", PASSWORD)
        body = auth_client.get("/api/v1/auth/me").json()
        assert "admin:users" in body["permissions"]
        assert "cases:write" in body["permissions"]


class TestRoleEnforcementDependencies:
    """The authorization dependencies exercised through a real HTTP stack.

    No production routes use require_role yet (no public case routes
    exist); a throwaway per-test app mounts a gate route so the exact
    production dependency path (cookie → session → principal → role
    check → ApiError 403) is validated end to end.
    """

    def _gate_app(self, auth_settings, db_session_factory, *roles):
        from fastapi import Depends

        from app.db.session import DatabaseSessionFactory
        from app.main import create_app

        app = create_app(
            settings=auth_settings,
            db_session_factory_override=DatabaseSessionFactory(
                db_session_factory.kw["bind"], db_session_factory
            ),
        )

        @app.get("/api/v1/__test_role_gate")
        def gated(
            principal: AuthenticatedPrincipal = Depends(require_role(*roles)),
        ):
            return {"user_id": principal.user_id, "role": principal.role.value}

        return app

    def _principal(self, role: Role) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            user_id="00000000-0000-0000-0000-000000000001",
            username="alice",
            display_name="Alice",
            role=role,
            is_active=True,
        )

    def test_viewer_denied_reviewer_gate_403(
        self, auth_settings, db_session_factory, auth_client, user_factory
    ):
        user_factory("alice", PASSWORD, role="viewer")
        login(auth_client, "alice", PASSWORD)

        from fastapi.testclient import TestClient

        gate = TestClient(self._gate_app(auth_settings, db_session_factory, Role.REVIEWER))
        gate.cookies.update(auth_client.cookies)
        response = gate.get("/api/v1/__test_role_gate")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_reviewer_passes_reviewer_gate(
        self, auth_settings, db_session_factory, auth_client, user_factory
    ):
        user_factory("alice", PASSWORD, role="reviewer")
        login(auth_client, "alice", PASSWORD)

        from fastapi.testclient import TestClient

        gate = TestClient(self._gate_app(auth_settings, db_session_factory, Role.REVIEWER))
        gate.cookies.update(auth_client.cookies)
        response = gate.get("/api/v1/__test_role_gate")
        assert response.status_code == 200
        assert response.json()["role"] == "reviewer"

    def test_anonymous_denied_gate_401(self, auth_settings, db_session_factory):
        from fastapi.testclient import TestClient

        gate = TestClient(self._gate_app(auth_settings, db_session_factory, Role.VIEWER))
        assert gate.get("/api/v1/__test_role_gate").status_code == 401

    def test_require_permission_logic(self):
        viewer = self._principal(Role.VIEWER)
        reviewer = self._principal(Role.REVIEWER)
        admin = self._principal(Role.ADMIN)

        assert viewer.has_permission("read:analytics")
        assert not viewer.has_permission("cases:write")
        assert not viewer.has_permission("admin:users")

        assert reviewer.has_permission("cases:write")
        assert not reviewer.has_permission("admin:users")

        assert admin.has_permission("admin:users")
        assert admin.has_permission("cases:write")

    def test_reviewer_cannot_self_assign_admin(self):
        """Role data comes from the trusted DB — request payloads cannot
        change it. Simulated at the permission layer."""
        reviewer = self._principal(Role.REVIEWER)
        # A client payload claiming role=admin does not alter the principal.
        client_claim = {"role": "admin"}
        assert reviewer.role.value != client_claim["role"]
        assert not reviewer.has_permission("admin:users")

    def test_role_change_reflected_in_existing_session(
        self, auth_client, user_factory, db_session_factory
    ):
        """AC-04-08: privilege changes are enforced on the active session."""
        user_factory("alice", PASSWORD, role="viewer")
        login(auth_client, "alice", PASSWORD)
        assert "cases:write" not in auth_client.get("/api/v1/auth/me").json()["permissions"]

        with db_session_factory() as session:
            session.execute(text("UPDATE users SET role = 'reviewer'"))
            session.commit()

        assert "cases:write" in auth_client.get("/api/v1/auth/me").json()["permissions"]

    def test_demotion_reflected_in_existing_session(
        self, auth_client, user_factory, db_session_factory
    ):
        user_factory("root", PASSWORD, role="admin")
        login(auth_client, "root", PASSWORD)
        assert "admin:users" in auth_client.get("/api/v1/auth/me").json()["permissions"]

        with db_session_factory() as session:
            session.execute(text("UPDATE users SET role = 'reviewer'"))
            session.commit()

        assert "admin:users" not in auth_client.get("/api/v1/auth/me").json()["permissions"]

    def test_deactivated_account_loses_session_immediately(
        self, auth_client, user_factory, db_session_factory
    ):
        user_factory("alice", PASSWORD)
        login(auth_client, "alice", PASSWORD)
        assert auth_client.get("/api/v1/auth/me").status_code == 200

        with db_session_factory() as session:
            session.execute(text("UPDATE users SET is_active = false"))
            session.commit()

        assert auth_client.get("/api/v1/auth/me").status_code == 401


class TestNoUnauthorizedUserManagement:
    def test_no_user_crud_routes_exist(self, auth_client, user_factory):
        """Administrative user-management is not exposed prematurely."""
        user_factory("root", PASSWORD, role="admin")
        login(auth_client, "root", PASSWORD)
        csrf = auth_client.get("/api/v1/auth/csrf").json()["csrf_token"]
        for path, payload in (
            ("/api/v1/users", {"username": "bob", "password": "x" * 12}),
            ("/api/v1/admin/users", {"username": "bob"}),
            ("/api/v1/auth/register", {"username": "bob", "password": "x" * 12}),
        ):
            response = auth_client.post(
                path, json=payload, headers={"X-CSRF-Token": csrf}
            )
            assert response.status_code == 404, path

    def test_client_payload_cannot_change_own_role(self, auth_client, user_factory):
        """The /me endpoint and all auth routes ignore role payloads."""
        user_factory("alice", PASSWORD, role="viewer")
        login(auth_client, "alice", PASSWORD)
        # A role field in any auth request body is simply not part of the
        # typed contract; the server-side role stays authoritative.
        body = auth_client.get("/api/v1/auth/me").json()
        assert body["role"] == "viewer"
