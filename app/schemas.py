"""Pydantic request/response schemas (input validation)."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class LoginIn(BaseModel):
    email: str
    password: str


class OnboardingIn(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=1, le=120)
    timezone: str = "UTC"
    notification_prefs: dict = Field(default_factory=dict)
    auto_confirm: bool = False


class ProfileIn(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=1, le=120)
    timezone: Optional[str] = None


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_minutes: int = Field(ge=0, le=1439)
    end_minutes: int = Field(ge=0, le=1439)
    category: str = "Other"
    notes: str = ""
    on_holiday: bool = False

    @field_validator("end_minutes")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_minutes")
        if start is not None and v <= start:
            raise ValueError("end_minutes must be after start_minutes")
        return v


class GoalPatch(BaseModel):
    name: Optional[str] = None
    start_minutes: Optional[int] = Field(default=None, ge=0, le=1439)
    end_minutes: Optional[int] = Field(default=None, ge=0, le=1439)
    category: Optional[str] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None
    on_holiday: Optional[bool] = None


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    goals_json: List[dict] = Field(default_factory=list)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SettingsIn(BaseModel):
    theme: Optional[str] = None
    auto_confirm: Optional[bool] = None
    notification_prefs: Optional[dict] = None

    @field_validator("theme")
    @classmethod
    def theme_ok(cls, v):
        if v is not None and v not in ("light", "dark", "system"):
            raise ValueError("theme must be light, dark or system")
        return v


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ImportIn(BaseModel):
    data: dict
