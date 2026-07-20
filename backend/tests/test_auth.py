"""Tests for auth API endpoints — register, login, get_me, update_me."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db_session
from app.core.security import hash_password
from app.main import app
from app.models.user import User


# ---------------------------------------------------------------------------
# Fake database session
# ---------------------------------------------------------------------------
from uuid import uuid4 as _uuid4


class FakeAuthSession:
    """Mimics enough of AsyncSession for the auth router."""

    def __init__(self, *, scalar_result=None, get_result=None):
        self._scalar = scalar_result
        self._get = get_result
        self.added: list = []
        self.commit_called = False
        self.rollback_called = False

    async def scalar(self, statement):
        del statement
        return self._scalar

    async def get(self, model, ident):
        return self._get

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_called = True
        # Simulate DB assigning an id to newly added objects
        for obj in self.added:
            if not hasattr(obj, "id") or obj.id is None:
                object.__setattr__(obj, "id", _uuid4())

    async def rollback(self):
        self.rollback_called = True

    async def refresh(self, obj):
        pass


# ---------------------------------------------------------------------------
# Helper: create a valid User ORM object
# ---------------------------------------------------------------------------
def _make_user(**override):
    return User(
        id=override.get("id", uuid4()),
        username=override.get("username", "testuser"),
        email=override.get("email", "test@example.com"),
        password_hash=override.get("password_hash", hash_password("password123")),
        display_name=override.get("display_name", "Test User"),
        bio=override.get("bio", None),
        avatar_url=override.get("avatar_url", None),
        is_active=override.get("is_active", True),
        created_at=override.get("created_at", datetime.now(timezone.utc)),
        updated_at=override.get("updated_at", datetime.now(timezone.utc)),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestRegister:
    def test_register_success(self, monkeypatch) -> None:
        user = _make_user()
        db = FakeAuthSession(scalar_result=None)
        db._scalar = None  # no existing user

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/register",
                    json={
                        "username": "newuser",
                        "email": "new@example.com",
                        "password": "password123",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201
        data = response.json()["data"]
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert db.commit_called

    def test_register_existing_user_conflict(self) -> None:
        existing_user = _make_user(username="taken", email="taken@example.com")
        db = FakeAuthSession(scalar_result=existing_user)

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/register",
                    json={
                        "username": "taken",
                        "email": "taken@example.com",
                        "password": "password123",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 409


class TestLogin:
    def test_login_success(self) -> None:
        user = _make_user()
        db = FakeAuthSession(scalar_result=user)

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "password123"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"

    def test_login_wrong_password(self) -> None:
        user = _make_user()
        db = FakeAuthSession(scalar_result=user)

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "wrong-password"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 401

    def test_login_nonexistent_user(self) -> None:
        db = FakeAuthSession(scalar_result=None)

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={"email": "noone@example.com", "password": "password123"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 401

    def test_login_disabled_user(self) -> None:
        user = _make_user(is_active=False)
        db = FakeAuthSession(scalar_result=user)

        async def fake_get_db():
            return db

        app.dependency_overrides[get_db_session] = fake_get_db

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "password123"},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 403


class TestGetMe:
    def test_get_me_authenticated(self) -> None:
        user = _make_user()
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            with TestClient(app) as client:
                response = client.get("/api/auth/me")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["username"] == "testuser"

    def test_get_me_unauthenticated(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/auth/me")

        assert response.status_code == 401
