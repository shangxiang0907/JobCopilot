import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM


def encrypt(plaintext: str, key_hex: str) -> str:
    """AES-256-GCM encrypt. Returns a URL-safe base64 string: nonce || ciphertext."""
    key = bytes.fromhex(key_hex)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(token: str, key_hex: str) -> str:
    """AES-256-GCM decrypt. Raises ValueError on tampered or wrong-key input."""
    try:
        key = bytes.fromhex(key_hex)
        raw = base64.urlsafe_b64decode(token.encode())
        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        return AESGCM(key).decrypt(nonce, ciphertext, None).decode()
    except Exception as exc:
        raise ValueError("decryption failed: invalid token or key") from exc
