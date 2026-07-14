"""User settings API endpoints – profile, notifications, system preferences, password."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.settings import (
    NotificationSettings, PasswordChange, ProfileUpdate, SystemSettings,
)
from app.services.settings import settings_service

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.put("/profile", response_model=dict)
async def update_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession):
    result = await settings_service.update_profile(
        db, user, body.display_name, body.avatar_url,
    )
    return success(result, "Profile updated")


@router.get("/notifications", response_model=dict)
async def get_notification_settings(user: CurrentUser, db: DbSession):
    result = await settings_service.get_notification_settings(db, user)
    return success(result)


@router.put("/notifications", response_model=dict)
async def update_notification_settings(
    body: NotificationSettings, user: CurrentUser, db: DbSession,
):
    result = await settings_service.update_notification_settings(
        db, user, body.model_dump(exclude_unset=True),
    )
    return success(result, "Notification settings updated")


@router.get("/system", response_model=dict)
async def get_system_settings(user: CurrentUser, db: DbSession):
    result = await settings_service.get_system_settings(db, user)
    return success(result)


@router.put("/system", response_model=dict)
async def update_system_settings(
    body: SystemSettings, user: CurrentUser, db: DbSession,
):
    result = await settings_service.update_system_settings(
        db, user, body.model_dump(exclude_unset=True),
    )
    return success(result, "System settings updated")


@router.put("/password", response_model=dict)
async def change_password(body: PasswordChange, user: CurrentUser, db: DbSession):
    try:
        await settings_service.change_password(
            db, user, body.current_password, body.new_password,
        )
        return success(None, "Password changed")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
