"""Tests for token encryption utilities."""

import pytest
from cryptography.fernet import InvalidToken

from app.core.security import decrypt_token, encrypt_token


def test_encrypt_and_decrypt_token() -> None:
    """An encrypted token can be decrypted to its original value."""
    original_token = "test-oauth-token-123"

    encrypted_token = encrypt_token(original_token)

    assert encrypted_token != original_token
    assert decrypt_token(encrypted_token) == original_token


def test_decrypt_invalid_token() -> None:
    """Decrypting invalid data raises InvalidToken."""
    with pytest.raises(InvalidToken):
        decrypt_token("invalid-encrypted-token")
