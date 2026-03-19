import pytest
from pydantic import ValidationError

from app.auth.schemas import UserLoginRequest, UserRegisterRequest


def test_register_request_normalizes_email() -> None:
    payload = UserRegisterRequest(email="  USER@Example.com  ", password="password123")

    assert payload.email == "user@example.com"


@pytest.mark.parametrize("email", ["invalid", "@example.com", "user@"])
def test_register_request_rejects_invalid_email(email: str) -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(email=email, password="password123")


def test_login_request_reuses_registration_validation() -> None:
    payload = UserLoginRequest(email=" LOGIN@Example.com ", password="password123")

    assert payload.email == "login@example.com"
