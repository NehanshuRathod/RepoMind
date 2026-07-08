from app.core.security import hash_password, verify_password


def test_password_hash_round_trip():
    hashed = hash_password("Password123!")

    assert hashed != "Password123!"
    assert verify_password("Password123!", hashed)
    assert not verify_password("wrong-password", hashed)
