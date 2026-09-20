from uuid import uuid4

from app.core.security import (
    generate_secure_password,
    hash_otp,
    hash_password,
    verify_otp,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    plain = "SuperSecure-Pass-123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_otp_hash_verification() -> None:
    session_id = uuid4()
    pepper = "test-pepper-value-12345"
    otp = "482910"
    digest = hash_otp(otp, session_id, pepper)
    assert verify_otp(otp, session_id, pepper, digest)
    assert not verify_otp("000000", session_id, pepper, digest)


def test_generated_password_entropy() -> None:
    a = generate_secure_password()
    b = generate_secure_password()
    assert a != b
    assert len(a) == 16
