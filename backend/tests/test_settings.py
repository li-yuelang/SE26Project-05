"""Tests for settings service — profile update, notification / system settings, password change."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.settings import SettingsService


class FakeUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.username = kwargs.get("username", "testuser")
        self.email = kwargs.get("email", "test@example.com")
        self.display_name = kwargs.get("display_name", "Test User")
        self.avatar_url = kwargs.get("avatar_url", None)
        self.is_active = kwargs.get("is_active", True)
        self.password_hash = kwargs.get(
            "password_hash",
            "$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        )
        self._saved = None

    def __setattr__(self, name, value):
        if name not in ("_saved",):
            object.__setattr__(self, name, value)


class FakePreference:
    def __init__(self, user_id, notification_settings=None, system_settings=None):
        self.user_id = user_id
        self.notification_settings = notification_settings or {}
        self.system_settings = system_settings or {}


class FakeSession:
    def __init__(self, preferences=None):
        self._preferences = preferences or {}
        self._added: list = []
        self.commit_called = False

    async def scalar(self, statement):
        del statement
        # Return the first preference keyed by any user_id
        for v in self._preferences.values():
            return v[0] if isinstance(v, list) else v
        return None

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        self.commit_called = True

    async def refresh(self, obj):
        pass


def test_serialise_user() -> None:
    user = FakeUser(
        id=uuid4(), username="alice", email="alice@test.com",
        display_name="Alice", avatar_url="http://img/1.png",
    )
    result = SettingsService._serialise_user(user)
    assert result["username"] == "alice"
    assert result["email"] == "alice@test.com"
    assert result["display_name"] == "Alice"
    assert result["avatar_url"] == "http://img/1.png"
    assert result["is_active"] is True


def test_update_profile_changes_fields() -> None:
    service = SettingsService()
    user = FakeUser(display_name="Old Name")
    db = FakeSession()
    import asyncio
    result = asyncio.run(service.update_profile(db, user, display_name="New Name"))
    assert user.display_name == "New Name"
    assert result["display_name"] == "New Name"
    assert db.commit_called


def test_update_profile_only_updates_provided_fields() -> None:
    service = SettingsService()
    user = FakeUser(display_name="Keep Me", avatar_url="http://old/avatar.png")
    db = FakeSession()
    import asyncio
    result = asyncio.run(service.update_profile(db, user, avatar_url="http://new/avatar.png"))
    assert user.display_name == "Keep Me"  # unchanged
    assert user.avatar_url == "http://new/avatar.png"
    assert result["display_name"] == "Keep Me"


def test_get_notification_settings_returns_empty_when_no_preference() -> None:
    service = SettingsService()
    user = FakeUser()
    db = FakeSession()
    import asyncio
    result = asyncio.run(service.get_notification_settings(db, user))
    assert result == {}


def test_update_notification_settings_creates_when_not_exists() -> None:
    service = SettingsService()
    user = FakeUser()
    db = FakeSession()
    import asyncio
    result = asyncio.run(
        service.update_notification_settings(db, user, {"email": True, "push": False})
    )
    assert result == {"email": True, "push": False}
    assert len(db._added) == 1


def test_update_notification_settings_merges_when_exists() -> None:
    service = SettingsService()
    user = FakeUser()
    pref = FakePreference(user.id, notification_settings={"email": False})
    db = FakeSession(preferences={user.id: pref})
    import asyncio
    result = asyncio.run(
        service.update_notification_settings(db, user, {"push": True})
    )
    assert result == {"email": False, "push": True}
    assert len(db._added) == 0  # updated in-place


def test_change_password_success() -> None:
    from app.core.security import hash_password, verify_password

    plain = "old-password"
    service = SettingsService()
    user = FakeUser(password_hash=hash_password(plain))
    db = FakeSession()
    import asyncio
    asyncio.run(service.change_password(db, user, "old-password", "new-password"))
    assert db.commit_called
    assert verify_password("new-password", user.password_hash)


def test_change_password_rejects_wrong_current() -> None:
    from app.core.security import hash_password

    service = SettingsService()
    user = FakeUser(password_hash=hash_password("real-password"))
    db = FakeSession()
    import asyncio
    with pytest.raises(ValueError, match="Current password"):
        asyncio.run(service.change_password(db, user, "wrong-password", "new-password"))


def test_change_password_rejects_same_password() -> None:
    from app.core.security import hash_password

    service = SettingsService()
    user = FakeUser(password_hash=hash_password("same-pwd"))
    db = FakeSession()
    import asyncio
    with pytest.raises(ValueError, match="must differ"):
        asyncio.run(service.change_password(db, user, "same-pwd", "same-pwd"))


def test_get_system_settings_returns_empty_when_no_preference() -> None:
    service = SettingsService()
    user = FakeUser()
    db = FakeSession()
    import asyncio
    result = asyncio.run(service.get_system_settings(db, user))
    assert result == {}


def test_update_system_settings_creates_when_not_exists() -> None:
    service = SettingsService()
    user = FakeUser()
    db = FakeSession()
    import asyncio
    result = asyncio.run(service.update_system_settings(db, user, {"theme": "dark"}))
    assert result == {"theme": "dark"}
    assert len(db._added) == 1
