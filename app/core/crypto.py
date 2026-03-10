"""Fernet encryption helpers for NVR passwords."""
from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext password string. Returns base64-encoded ciphertext."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted password string. Returns plaintext."""
    return _fernet.decrypt(ciphertext.encode()).decode()
