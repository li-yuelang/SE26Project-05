"""Tests for JWT token creation / decoding and password hashing."""

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_round_trip() -> None:
    plain = "super-secret-pwd"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_password_is_stable_for_same_input() -> None:
    h1 = hash_password("abc")
    h2 = hash_password("abc")
    # Argon2 hashes differ each call (different salt)
    assert h1 != h2
    assert verify_password("abc", h1)
    assert verify_password("abc", h2)


def test_create_and_decode_access_token_round_trip() -> None:
    token = create_access_token("test-user-uuid")
    subject = decode_access_token(token)
    assert subject == "test-user-uuid"


def test_decode_expired_token_raises() -> None:
    import time
    from app.config import settings

    # Create an already-expired token by overriding expiration directly
    expires_at = 0  # epoch 0 = long expired
    token = jwt.encode({"sub": "user-1", "exp": expires_at}, settings.jwt_secret_key, settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_token_without_subject_raises() -> None:
    from app.config import settings

    token = jwt.encode({"exp": 9999999999}, settings.jwt_secret_key, settings.jwt_algorithm)
    with pytest.raises(jwt.InvalidTokenError, match="subject"):
        decode_access_token(token)


def test_decode_token_with_invalid_signature_raises() -> None:
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not.a.valid.token")
