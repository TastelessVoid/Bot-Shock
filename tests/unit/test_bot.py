"""
Unit tests for the BotShock core bot class.

These tests demonstrate how to test Discord bot functionality without
needing actual Discord context, using the fixtures from conftest.py.
"""

from unittest.mock import AsyncMock, Mock, patch

import disnake
import pytest

from botshock.core.bot import BotShock
from botshock.exceptions import BotShockException


class TestBotShockInitialization:
    """Test bot initialization."""

    def test_bot_creation(self, mock_config):
        """Test that bot can be created with config."""
        bot = BotShock(mock_config)

        assert bot.config == mock_config
        assert bot.db is None  # Not initialized yet
        assert bot.api_client is None
        assert bot.scheduler is None
        assert bot.trigger_manager is None

    def test_bot_has_correct_intents(self, mock_config):
        """Test that bot is created with correct intents."""
        bot = BotShock(mock_config)

        assert bot.intents.message_content is True
        assert bot.intents.members is True


class TestBotLifecycle:
    """Test bot lifecycle methods."""

    @pytest.mark.asyncio
    async def test_setup_hook_initializes_services(self, mock_config):
        """Test that setup_hook initializes all services."""
        bot = BotShock(mock_config)

        # Mock the service initialization
        with (
            patch("botshock.core.bot.Database") as mock_db_class,
            patch("botshock.core.bot.OpenShockAPIClient"),
            patch("botshock.core.bot.TriggerManager"),
            patch("botshock.core.bot.ReminderScheduler") as mock_scheduler_class,
        ):

            # Setup mocks
            mock_db = Mock()
            mock_db.initialize = AsyncMock()
            mock_db_class.return_value = mock_db

            mock_scheduler = Mock()
            mock_scheduler.start = Mock()
            mock_scheduler_class.return_value = mock_scheduler

            # Run setup hook
            await bot.setup_hook()

            # Verify services were initialized
            assert bot.db is not None
            assert bot.api_client is not None
            assert bot.trigger_manager is not None
            assert bot.scheduler is not None

            # Verify database was initialized
            mock_db.initialize.assert_called_once()

            # Verify scheduler was started
            mock_scheduler.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_stops_all_services(self, mock_config):
        """Test that close() properly shuts down all services."""
        bot = BotShock(mock_config)

        # Mock services
        bot.scheduler = Mock()
        bot.scheduler.stop = Mock()

        bot.api_client = Mock()
        bot.api_client.close = AsyncMock()

        bot.db = Mock()
        bot.db.close = AsyncMock()

        # Close bot - patch super().close() to avoid actual bot shutdown
        with patch("disnake.ext.commands.InteractionBot.close", new_callable=AsyncMock):
            await bot.close()

        # Verify all services were stopped
        bot.scheduler.stop.assert_called_once()
        bot.api_client.close.assert_called_once()
        bot.db.close.assert_called_once()


class TestCogLoading:
    """Test cog loading functionality."""

    def test_load_all_cogs(self, mock_config):
        """Test that load_all_cogs loads all cogs."""
        bot = BotShock(mock_config)

        with patch.object(bot, "load_extension") as mock_load:
            bot.load_all_cogs()

            # Verify load_extension was called for each cog
            assert mock_load.call_count == 9  # We have 9 cogs

            # Verify specific cogs were loaded
            loaded_cogs = [call[0][0] for call in mock_load.call_args_list]
            assert "botshock.cogs.user_commands" in loaded_cogs
            assert "botshock.cogs.shock_command" in loaded_cogs
            assert "botshock.cogs.trigger_commands" in loaded_cogs

    def test_load_all_cogs_handles_failures(self, mock_config):
        """Test that cog loading continues even if some cogs fail."""
        bot = BotShock(mock_config)

        def mock_load_extension(cog_name):
            if "user_commands" in cog_name:
                raise Exception("Failed to load")

        with patch.object(bot, "load_extension", side_effect=mock_load_extension):
            # Should not raise exception
            bot.load_all_cogs()


class TestErrorHandling:
    """Test error handling in commands."""

    @pytest.mark.asyncio
    async def test_on_slash_command_error_handles_missing_permissions(
        self, mock_config, mock_interaction
    ):
        """Test error handler for missing permissions."""
        from disnake.ext.commands import MissingPermissions

        bot = BotShock(mock_config)
        error = MissingPermissions(["administrator"])

        await bot.on_slash_command_error(mock_interaction, error)

        # Verify error message was sent
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "don't have permission" in call_args[0][0]
        assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_on_slash_command_error_handles_cooldown(self, mock_config, mock_interaction):
        """Test error handler for command cooldown."""
        from disnake.ext.commands import BucketType, CommandOnCooldown

        bot = BotShock(mock_config)
        # Create a mock cooldown object with retry_after attribute
        cooldown = Mock()
        cooldown.retry_after = 5.5
        error = CommandOnCooldown(cooldown, 5.5, BucketType.user)

        await bot.on_slash_command_error(mock_interaction, error)

        # Verify cooldown message was sent
        call_args = mock_interaction.response.send_message.call_args
        assert "cooldown" in call_args[0][0]
        assert "5.5" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_on_slash_command_error_handles_custom_exceptions(
        self, mock_config, mock_interaction
    ):
        """Test error handler for BotShock custom exceptions."""
        bot = BotShock(mock_config)
        error = BotShockException("Custom error message")

        await bot.on_slash_command_error(mock_interaction, error)

        # Verify custom error message was sent
        call_args = mock_interaction.response.send_message.call_args
        assert "Custom error message" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_on_slash_command_error_uses_followup_when_response_done(
        self, mock_config, mock_interaction
    ):
        """Test that followup is used if response is already done."""
        bot = BotShock(mock_config)
        error = Exception("Test error")

        # Simulate response already sent
        mock_interaction.response.is_done.return_value = True

        await bot.on_slash_command_error(mock_interaction, error)

        # Verify followup was used instead of response
        mock_interaction.followup.send.assert_called_once()
        mock_interaction.response.send_message.assert_not_called()


# noinspection PyShadowingNames
class TestBotEvents:
    """Test bot event handlers."""

    # noinspection PyShadowingNames
    @pytest.mark.asyncio
    async def test_on_ready_sets_presence(self, mock_config):
        """Test that on_ready sets bot presence."""
        bot = BotShock(mock_config)

        # Mock the user property and other attributes
        mock_user = Mock()
        mock_user.id = 123456789

        with (
            patch.object(type(bot), "user", new_callable=lambda: property(lambda self: mock_user)),
            patch.object(type(bot), "guilds", new_callable=lambda: property(lambda self: [])),
        ):
            bot.change_presence = AsyncMock()

            await bot.on_ready()

            # Verify presence was set
            bot.change_presence.assert_called_once()
            call_args = bot.change_presence.call_args
            assert call_args[1]["activity"].type == disnake.ActivityType.watching
