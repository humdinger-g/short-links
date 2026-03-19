from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.links.schemas import LinkCreateRequest


def test_link_create_request_strips_valid_alias() -> None:
    payload = LinkCreateRequest(
        original_url="https://example.com/path",
        custom_alias="  my_alias  ",
    )

    assert payload.custom_alias == "my_alias"


@pytest.mark.parametrize("alias", ["", "   ", "bad alias", "bad/alias"])
def test_link_create_request_rejects_invalid_alias(alias: str) -> None:
    with pytest.raises(ValidationError):
        LinkCreateRequest(
            original_url="https://example.com/path",
            custom_alias=alias,
        )


def test_link_create_request_normalizes_expires_at_to_utc() -> None:
    expires_at = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(
        minutes=10
    )
    naive_expires_at = expires_at.replace(tzinfo=None)

    payload = LinkCreateRequest(
        original_url="https://example.com/path",
        expires_at=naive_expires_at,
    )

    assert payload.expires_at == expires_at


def test_link_create_request_rejects_second_precision() -> None:
    expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=10)

    with pytest.raises(ValidationError, match="minute precision"):
        LinkCreateRequest(
            original_url="https://example.com/path",
            expires_at=expires_at,
        )


def test_link_create_request_rejects_past_expires_at() -> None:
    expires_at = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(
        minutes=1
    )

    with pytest.raises(ValidationError, match="must be in the future"):
        LinkCreateRequest(
            original_url="https://example.com/path",
            expires_at=expires_at,
        )
