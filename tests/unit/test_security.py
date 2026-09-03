from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_roundtrip():
    token = create_access_token(subject="user-123", extra_claims={"role": "citizen"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "citizen"
    assert payload["type"] == "access"
