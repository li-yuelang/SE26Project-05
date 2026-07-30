"""Business logic for user settings."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserPreference


class SettingsService:
    """Stateless service for user settings management."""

    async def update_profile(
        self, db: AsyncSession, user: User,
        display_name: str | None = None, avatar_url: str | None = None,
    ) -> dict:
        if display_name is not None:
            user.display_name = display_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(user)
        return self._serialise_user(user)

    async def get_notification_settings(self, db: AsyncSession, user: User) -> dict:
        pref = await db.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        return pref.notification_settings if pref else {}

    async def update_notification_settings(
        self, db: AsyncSession, user: User, settings: dict,
    ) -> dict:
        pref = await db.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        if pref is None:
            pref = UserPreference(user_id=user.id, notification_settings=settings)
            db.add(pref)
        else:
            pref.notification_settings = {**pref.notification_settings, **settings}
        await db.commit()
        await db.refresh(pref)
        return pref.notification_settings

    async def get_system_settings(self, db: AsyncSession, user: User) -> dict:
        pref = await db.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        return pref.system_settings if pref else {}

    async def update_system_settings(
        self, db: AsyncSession, user: User, settings: dict,
    ) -> dict:
        pref = await db.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        if pref is None:
            pref = UserPreference(user_id=user.id, system_settings=settings)
            db.add(pref)
        else:
            pref.system_settings = {**pref.system_settings, **settings}
        await db.commit()
        await db.refresh(pref)
        return pref.system_settings

    async def change_password(
        self, db: AsyncSession, user: User,
        current_password: str, new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        if current_password == new_password:
            raise ValueError("New password must differ from current password")
        user.password_hash = hash_password(new_password)
        await db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _serialise_user(user: User) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
        }


settings_service = SettingsService()
