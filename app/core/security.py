"""Utilities for encrypting and decrypting sensitive data."""

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.encryption_key.encode("utf-8"))


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token and return its encoded representation."""
    encrypted = _fernet.encrypt(token.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted OAuth token."""
    decrypted = _fernet.decrypt(encrypted_token.encode("utf-8"))
    return decrypted.decode("utf-8")
