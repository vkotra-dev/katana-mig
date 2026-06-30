from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


PlatformRole = Literal["central_team", "project_stakeholder", "read_only_auditor"]
UserStatus = Literal["active", "disabled"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AuthenticatedUserResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    session_version: int
    user: AuthenticatedUserResponse


class SessionResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus
    expires_at: datetime
    session_version: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetAccepted(BaseModel):
    accepted: bool = True


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str | None
    role: PlatformRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None
    role: PlatformRole


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: PlatformRole | None = None
    status: UserStatus | None = None


class ProjectMemberResponse(BaseModel):
    project_id: str
    user_id: str
    created_at: datetime


class MembershipResponse(BaseModel):
    project_id: str
    user_id: str
    warning: str | None = None


class LookupValueMapCreateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)
    destination_table: list[dict[str, Any]]


class LookupValueMapResponse(BaseModel):
    lookup_value_map_id: str
    source_definition_id: str
    lookup_name: str
    destination_table: list[dict[str, Any]]
    status: Literal["draft", "approved"]
    created_at: datetime


class LookupSnapshotGenerateRequest(BaseModel):
    lookup_name: str = Field(min_length=1, max_length=128)


class LookupSnapshotResponse(BaseModel):
    lookup_snapshot_id: str
    project_id: str
    source_definition_id: str
    lookup_name: str
    lookup_snapshot_version: str
    value_map: dict[str, str]
    status: Literal["draft", "approved"]
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    created_at: datetime
