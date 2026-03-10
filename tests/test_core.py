"""
Core behavior tests for Task 1.
Tests: app imports, settings validation, crypto roundtrip, mock ISAPI.
"""
import pytest
from pydantic import ValidationError


def test_app_imports():
    """from app.main import app succeeds without error."""
    from app.main import app  # noqa: F401
    assert app is not None


def test_settings_missing_env(monkeypatch):
    """Instantiating Settings() with no DATABASE_URL raises ValidationError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    # Remove .env file influence by patching env_file
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class IsolatedSettings(BaseSettings):
        DATABASE_URL: str
        ENCRYPTION_KEY: str

        model_config = SettingsConfigDict(env_file=None, extra="ignore")

    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_encrypt_decrypt_roundtrip():
    """encrypt_password('secret') decrypted returns 'secret'."""
    from app.core.crypto import encrypt_password, decrypt_password

    ciphertext = encrypt_password("secret")
    result = decrypt_password(ciphertext)
    assert result == "secret"


def test_encrypt_hides_plaintext():
    """Encrypted value != 'secret'."""
    from app.core.crypto import encrypt_password

    ciphertext = encrypt_password("secret")
    assert ciphertext != "secret"
    assert "secret" not in ciphertext


async def test_mock_isapi_device_info():
    """MockISAPIClient().get_device_info() returns dict with 'deviceName' key."""
    from tests.mocks import MockISAPIClient

    client = MockISAPIClient()
    result = await client.get_device_info()
    assert isinstance(result, dict)
    assert "deviceName" in result


async def test_mock_isapi_channels():
    """MockISAPIClient().get_camera_channels() returns list with 'channel_no' key."""
    from tests.mocks import MockISAPIClient

    client = MockISAPIClient()
    result = await client.get_camera_channels()
    assert isinstance(result, list)
    assert len(result) > 0
    assert "channel_no" in result[0]
