import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


class PersonalInfo(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str | None = None
    years_of_experience: int | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


class Preferences(BaseModel):
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    preferred_job_types: list[str] = []
    target_salary_min: int | None = None
    target_salary_max: int | None = None
    excluded_companies: list[str] = []
    open_to_remote: bool = True


class ProfileUpsert(BaseModel):
    personal_info: PersonalInfo | None = None
    preferences: Preferences | None = None


class CredentialsUpdate(BaseModel):
    linkedin_cookie: str | None = None
    llm_api_key: str | None = None


class ProfileResponse(BaseModel):
    profile_id: uuid.UUID
    user_id: uuid.UUID
    personal_info: dict[str, Any] | None
    preferences: dict[str, Any] | None
    has_linkedin_cookie: bool
    has_llm_api_key: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, profile: Any) -> "ProfileResponse":
        return cls(
            profile_id=profile.profile_id,
            user_id=profile.user_id,
            personal_info=profile.personal_info,
            preferences=profile.preferences,
            has_linkedin_cookie=bool(profile.linkedin_cookie_enc),
            has_llm_api_key=bool(profile.llm_api_key_enc),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class InternalProfileResponse(BaseModel):
    """Full profile data for internal service calls — includes decrypted credentials."""

    profile_id: uuid.UUID
    user_id: uuid.UUID
    personal_info: dict[str, Any] | None
    preferences: dict[str, Any] | None
    linkedin_cookie: str | None
    llm_api_key: str | None
    active_resume: dict[str, Any] | None

    model_config = {"from_attributes": True}
