"""Schemas for user settings."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    avatar_url: str | None = Field(None, max_length=500)


class NotificationSettings(BaseModel):
    email_digest: bool = True
    push_new_paper: bool = False
    push_recommendation: bool = True
    frequency: str = "daily"  # daily, weekly, none


class SystemSettings(BaseModel):
    theme: Literal["light", "dark", "midnight", "graphite"] = "light"
    language: str = "zh-CN"
    default_page_size: int = Field(default=20, ge=5, le=100)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
