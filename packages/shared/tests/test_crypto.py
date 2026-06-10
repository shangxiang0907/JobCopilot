import pytest

from jobcopilot_shared.crypto import decrypt, encrypt

_KEY = "a" * 64  # 32-byte AES-256 key expressed as 64 hex chars


def test_roundtrip() -> None:
    plaintext = "linkedin-session-cookie-value"
    assert decrypt(encrypt(plaintext, _KEY), _KEY) == plaintext


def test_each_call_produces_unique_ciphertext() -> None:
    # Different nonce each time — ciphertext must differ
    plaintext = "same-input"
    assert encrypt(plaintext, _KEY) != encrypt(plaintext, _KEY)


def test_tampered_ciphertext_raises() -> None:
    token = encrypt("secret", _KEY)
    tampered = token[:-4] + "XXXX"
    with pytest.raises(Exception):
        decrypt(tampered, _KEY)


def test_wrong_key_raises() -> None:
    token = encrypt("secret", _KEY)
    wrong_key = "b" * 64
    with pytest.raises(Exception):
        decrypt(token, wrong_key)
