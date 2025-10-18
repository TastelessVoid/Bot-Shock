"""
Example tests for utils modules demonstrating testing without Discord context.
"""

from datetime import UTC, datetime

import pytest

from botshock.exceptions import EncryptionError, ValidationError
from botshock.utils.encryption import EncryptionHandler
from botshock.utils.validators import (
    validate_action_type,
    validate_duration,
    validate_intensity,
)


class TestEncryption:
    """Test encryption and decryption functionality."""

    def test_encryption_roundtrip(self):
        """Test that data can be encrypted and decrypted."""
        handler = EncryptionHandler("test_key_1234567890123456")

        original = "secret_api_token"
        encrypted = handler.encrypt(original, user_id=123, guild_id=456)
        decrypted = handler.decrypt(encrypted, user_id=123, guild_id=456)

        assert decrypted == original

    def test_encryption_with_different_user_fails(self):
        """Test that decryption fails with wrong user/guild."""
        handler = EncryptionHandler("test_key_1234567890123456")

        original = "secret_api_token"
        encrypted = handler.encrypt(original, user_id=123, guild_id=456)

        # Try to decrypt with different user_id - should fail
        # The exact exception type depends on implementation
        with pytest.raises((EncryptionError, Exception)):
            handler.decrypt(encrypted, user_id=999, guild_id=456)

    def test_encryption_handles_empty_string(self):
        """Test encryption of empty string."""
        handler = EncryptionHandler("test_key_1234567890123456")

        original = ""
        encrypted = handler.encrypt(original, user_id=123, guild_id=456)
        decrypted = handler.decrypt(encrypted, user_id=123, guild_id=456)

        assert decrypted == original


class TestValidators:
    """Test validation functions."""

    @pytest.mark.parametrize("intensity", [1, 25, 50, 75, 100])
    def test_validate_intensity_valid_range(self, intensity):
        """Test valid intensity values."""
        assert validate_intensity(intensity) == intensity

    @pytest.mark.parametrize("intensity", [0, -1, 101, 200])
    def test_validate_intensity_invalid_range(self, intensity):
        """Test invalid intensity values."""
        with pytest.raises(ValidationError):
            validate_intensity(intensity)

    @pytest.mark.parametrize("duration", [1, 5, 10, 15])
    def test_validate_duration_valid_range(self, duration):
        """Test valid duration values."""
        assert validate_duration(duration) == duration

    @pytest.mark.parametrize("duration", [0, -1, 16, 30])
    def test_validate_duration_invalid_range(self, duration):
        """Test invalid duration values."""
        with pytest.raises(ValidationError):
            validate_duration(duration)

    @pytest.mark.parametrize("action", ["shock", "vibrate", "beep"])
    def test_validate_action_type_valid(self, action):
        """Test valid action types."""
        assert validate_action_type(action) == action

    @pytest.mark.parametrize("action", ["invalid", "zap", ""])
    def test_validate_action_type_invalid(self, action):
        """Test invalid action types."""
        with pytest.raises(ValidationError):
            validate_action_type(action)


class TestFormatters:
    """Test response formatters."""

    def test_format_action_log(self):
        """Test formatting of action logs."""
        from botshock.utils.formatters import ResponseFormatter

        formatter = ResponseFormatter()

        log_data = {
            "timestamp": datetime.now(UTC),
            "controller_id": 123,
            "target_id": 456,
            "action": "shock",
            "intensity": 50,
            "duration": 2,
        }

        formatted = formatter.format_action_log(log_data)

        assert "shock" in formatted.lower()
        assert "50" in formatted
        assert "2" in formatted

    def test_format_permission_list(self):
        """Test formatting of permission lists."""
        from botshock.utils.formatters import ResponseFormatter

        formatter = ResponseFormatter()

        permissions = [
            {
                "controller_id": 123,
                "max_intensity": 50,
                "max_duration": 5,
                "created_at": datetime.now(UTC),
            }
        ]

        formatted = formatter.format_permission_list(permissions)

        assert "123" in formatted
        assert "50" in formatted
        assert "5" in formatted
