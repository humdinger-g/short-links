import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.auth.security import (
    InvalidTokenError,
    _b64url_encode,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.settings import get_settings


def _make_signed_token(payload: dict[str, object]) -> str:
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(
        settings.auth_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def test_hash_password_roundtrip_and_wrong_password() -> None:
    password_hash = hash_password("password123")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("password123", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


@pytest.mark.parametrize(
    "stored_hash",
    [
        "not-a-valid-hash",
        "sha1$100$abc$def",
    ],
)
def test_verify_password_rejects_invalid_hash_format(stored_hash: str) -> None:
    assert verify_password("password123", stored_hash) is False


def test_create_and_decode_access_token_roundtrip() -> None:
    user_id = uuid4()

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_decode_access_token_rejects_invalid_format() -> None:
    with pytest.raises(InvalidTokenError, match="invalid format"):
        decode_access_token("invalid-token")


def test_decode_access_token_rejects_invalid_signature() -> None:
    token = create_access_token(uuid4())
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    tampered_signature = encoded_signature[:-1] + (
        "A" if encoded_signature[-1] != "A" else "B"
    )

    with pytest.raises(InvalidTokenError, match="signature is invalid"):
        decode_access_token(f"{encoded_header}.{encoded_payload}.{tampered_signature}")


def test_decode_access_token_rejects_expired_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "access_token_ttl_minutes", -1)
    token = create_access_token(uuid4())

    with pytest.raises(InvalidTokenError, match="expired"):
        decode_access_token(token)


def test_decode_access_token_rejects_incomplete_payload() -> None:
    token = _make_signed_token({"sub": str(uuid4())})

    with pytest.raises(InvalidTokenError, match="incomplete"):
        decode_access_token(token)


def test_decode_access_token_rejects_invalid_subject() -> None:
    token = _make_signed_token(
        {
            "sub": "not-a-uuid",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        }
    )

    with pytest.raises(InvalidTokenError, match="subject is invalid"):
        decode_access_token(token)
