from __future__ import annotations


def test_argon2id_roundtrip() -> None:
    from astloom_auth.hashing import hash_secret, verify_secret

    encoded = hash_secret("bootstrap-raw-value")
    assert verify_secret("bootstrap-raw-value", encoded)
    assert not verify_secret("wrong", encoded)


def test_verify_secret_rejects_malformed_hash() -> None:
    from astloom_auth.hashing import verify_secret

    assert verify_secret("any", "not-a-valid-argon2-hash") is False
