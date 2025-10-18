"""
Example integration tests demonstrating how to test complete workflows.

These tests show how to test interactions between multiple components
using the mock fixtures from conftest.py.
"""

import pytest

from botshock.utils.validators import validate_duration, validate_intensity


class TestPermissionWorkflow:
    """Test the complete permission granting and checking workflow."""

    @pytest.mark.asyncio
    async def test_grant_and_check_permission(self, mock_database, mock_user):
        """Test granting permission and then checking it."""
        user_id = 123456789
        target_id = 987654321
        guild_id = 111222333

        # Grant permission
        await mock_database.grant_permission(
            user_id=user_id,
            guild_id=guild_id,
            controller_id=target_id,
            max_intensity=50,
            max_duration=5
        )

        # Check permission exists
        permissions = await mock_database.get_permissions(user_id, guild_id)

        assert len(permissions) > 0
        perm = permissions[0]
        assert perm["controller_id"] == target_id
        assert perm["max_intensity"] == 50
        assert perm["max_duration"] == 5


class TestShockerRegistration:
    """Test the complete shocker registration workflow."""

    @pytest.mark.asyncio
    async def test_register_user_and_add_shocker(
        self, mock_database, sample_api_token, sample_shocker_data
    ):
        """Test registering a user and adding a shocker."""
        user_id = 123456789
        guild_id = 111222333

        # Register user
        await mock_database.register_user(
            user_id=user_id,
            guild_id=guild_id,
            api_token=sample_api_token
        )

        # Verify user is registered
        is_registered = await mock_database.is_user_registered(user_id, guild_id)
        assert is_registered is True

        # Add shocker
        await mock_database.add_shocker(
            user_id=user_id,
            guild_id=guild_id,
            shocker_id=sample_shocker_data["id"],
            shocker_name=sample_shocker_data["name"]
        )

        # Verify shocker was added
        shockers = await mock_database.get_user_shockers(user_id, guild_id)
        assert len(shockers) == 1
        assert shockers[0]["shocker_id"] == sample_shocker_data["id"]


class TestCommandInteraction:
    """Test command interactions with Discord context."""

    @pytest.mark.asyncio
    async def test_shock_command_with_permission(
        self, mock_bot, mock_interaction, mock_database, mock_api_client
    ):
        """Test shock command execution with proper permissions."""
        # Setup bot with mocked services
        mock_bot.db = mock_database
        mock_bot.api_client = mock_api_client

        # Setup users
        controller_id = 123456789
        target_id = 987654321
        guild_id = 111222333

        # Register both users
        await mock_database.register_user(controller_id, guild_id, "token1")
        await mock_database.register_user(target_id, guild_id, "token2")

        # Add shocker for target
        await mock_database.add_shocker(
            user_id=target_id,
            guild_id=guild_id,
            shocker_id="shocker123",
            shocker_name="Test Shocker"
        )

        # Grant permission
        await mock_database.grant_permission(
            user_id=target_id,
            guild_id=guild_id,
            controller_id=controller_id,
            max_intensity=100,
            max_duration=15
        )

        # Verify permission exists
        can_control = await mock_database.check_permission(
            controller_id=controller_id,
            target_id=target_id,
            guild_id=guild_id
        )

        assert can_control is True


class TestValidation:
    """Test validation functions."""

    def test_validate_intensity_accepts_valid_values(self):
        """Test that valid intensity values are accepted."""
        assert validate_intensity(1) == 1
        assert validate_intensity(50) == 50
        assert validate_intensity(100) == 100

    def test_validate_intensity_rejects_invalid_values(self):
        """Test that invalid intensity values are rejected."""
        from botshock.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_intensity(0)

        with pytest.raises(ValidationError):
            validate_intensity(101)

        with pytest.raises(ValidationError):
            validate_intensity(-5)

    def test_validate_duration_accepts_valid_values(self):
        """Test that valid duration values are accepted."""
        assert validate_duration(1) == 1
        assert validate_duration(5) == 5
        assert validate_duration(15) == 15

    def test_validate_duration_rejects_invalid_values(self):
        """Test that invalid duration values are rejected."""
        from botshock.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_duration(0)

        with pytest.raises(ValidationError):
            validate_duration(16)


class TestTriggerSystem:
    """Test trigger pattern matching and execution."""

    @pytest.mark.asyncio
    async def test_trigger_matches_pattern(self, mock_database):
        """Test that triggers correctly match message patterns."""
        user_id = 123456789
        guild_id = 111222333

        # Add a trigger
        _ = await mock_database.add_trigger(
            user_id=user_id,
            guild_id=guild_id,
            pattern=r"hello.*world",
            action="vibrate",
            intensity=50,
            duration=2
        )

        # Get triggers
        triggers = await mock_database.get_user_triggers(user_id, guild_id)

        assert len(triggers) > 0
        trigger = triggers[0]
        assert trigger["pattern"] == r"hello.*world"
        assert trigger["action"] == "vibrate"

