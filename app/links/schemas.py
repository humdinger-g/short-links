import re
from datetime import datetime, timezone

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _normalize_expires_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)

    if normalized.second != 0 or normalized.microsecond != 0:
        raise ValueError("expires_at must be provided with minute precision.")

    if normalized <= datetime.now(timezone.utc):
        raise ValueError("expires_at must be in the future.")

    return normalized


class LinkCreateRequest(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: str | None = Field(default=None, min_length=1, max_length=64)
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, value: str | None) -> str | None:
        if value is None:
            return None

        alias = value.strip()
        if not alias:
            raise ValueError("custom_alias must not be empty.")
        if not ALIAS_PATTERN.fullmatch(alias):
            raise ValueError(
                "custom_alias may contain only letters, digits, '-' and '_'."
            )
        return alias

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_expires_at(value)


class LinkUpdateRequest(BaseModel):
    original_url: AnyHttpUrl


class LinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None


class LinkStatsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    click_count: int


class ArchivedLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    click_count: int
    deleted_at: datetime
    deletion_reason: str
