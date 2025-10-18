"""
Pytest configuration and shared fixtures for BotShock tests.

This module provides fixtures for mocking Discord objects and bot components,
solving the "context" problem when testing Discord bots.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import disnake
import pytest

from botshock.config import BotConfig
from botshock.core.bot import BotShock
from botshock.core.database import Database

# ==================== Pytest Configuration ====================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")


# ==================== Configuration Fixtures ====================


@pytest.fixture
def mock_config() -> BotConfig:
    """Provide a mock bot configuration for testing."""
    return BotConfig(
        discord_token="test_token",
        encryption_key="test_encryption_key_1234567890123456",
        database_path=":memory:",  # In-memory database for tests
        database_pool_size=2,
        api_base_url="https://api.openshock.app",
        api_timeout=10,
        api_max_connections=10,
        api_requests_per_minute=60,
        log_level="DEBUG",
        log_dir="logs",
    )


# ==================== Discord Mock Fixtures ====================


@pytest.fixture
def mock_user() -> Mock:
    """Create a mock Discord user."""
    user = Mock(spec=disnake.User)
    user.id = 123456789
    user.name = "TestUser"
    user.discriminator = "0001"
    user.bot = False
    user.display_name = "TestUser"
    user.mention = "<@123456789>"
    user.avatar = None
    return user


@pytest.fixture
def mock_member(mock_user) -> Mock:
    """Create a mock Discord member (user in a guild)."""
    member = Mock(spec=disnake.Member)
    member.id = mock_user.id
    member.name = mock_user.name
    member.discriminator = mock_user.discriminator
    member.bot = False
    member.display_name = "TestUser"
    member.mention = "<@123456789>"
    member.avatar = None
    member.guild_permissions = disnake.Permissions.all()
    member.roles = []
    return member


@pytest.fixture
def mock_guild() -> Mock:
    """Create a mock Discord guild (server)."""
    guild = Mock(spec=disnake.Guild)
    guild.id = 987654321
    guild.name = "Test Guild"
    guild.owner_id = 123456789
    guild.member_count = 100
    guild.roles = []
    guild.channels = []
    return guild


@pytest.fixture
def mock_channel() -> Mock:
    """Create a mock Discord text channel."""
    channel = Mock(spec=disnake.TextChannel)
    channel.id = 111222333
    channel.name = "test-channel"
    channel.mention = "<#111222333>"
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def mock_interaction(mock_user, mock_guild, mock_channel) -> Mock:
    """Create a mock Discord interaction (slash command context)."""
    interaction = Mock(spec=disnake.ApplicationCommandInteraction)
    interaction.user = mock_user
    interaction.author = mock_user
    interaction.guild = mock_guild
    interaction.guild_id = mock_guild.id
    interaction.channel = mock_channel
    interaction.channel_id = mock_channel.id

    # Mock response handling
    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = Mock(return_value=False)

    # Mock followup
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    # Mock application command
    interaction.application_command = Mock()
    interaction.application_command.name = "test_command"

    return interaction


@pytest.fixture
def mock_message(mock_user, mock_channel, mock_guild) -> Mock:
    """Create a mock Discord message."""
    message = Mock(spec=disnake.Message)
    message.id = 444555666
    message.author = mock_user
    message.channel = mock_channel
    message.guild = mock_guild
    message.content = "Test message content"
    message.created_at = datetime.now(UTC)
    message.delete = AsyncMock()
    message.edit = AsyncMock()
    message.reply = AsyncMock()
    return message


# ==================== Bot Component Fixtures ====================


@pytest.fixture
def mock_database(mock_config) -> Mock:
    """Create a mock database for simple tests."""
    db = Mock()

    # Storage for test data
    db._permissions = []
    db._users = {}
    db._shockers = {}
    db._triggers = {}

    async def grant_permission(user_id, guild_id, controller_id, max_intensity, max_duration):
        perm = {
            "user_id": user_id,
            "guild_id": guild_id,
            "controller_id": controller_id,
            "max_intensity": max_intensity,
            "max_duration": max_duration,
        }
        db._permissions.append(perm)

    async def get_permissions(user_id, guild_id):
        return [p for p in db._permissions if p["user_id"] == user_id and p["guild_id"] == guild_id]

    async def register_user(user_id, guild_id, api_token):
        key = (user_id, guild_id)
        db._users[key] = {"user_id": user_id, "guild_id": guild_id, "api_token": api_token}

    async def is_user_registered(user_id, guild_id):
        key = (user_id, guild_id)
        return key in db._users

    async def add_shocker(user_id, guild_id, shocker_id, shocker_name):
        key = (user_id, guild_id)
        if key not in db._shockers:
            db._shockers[key] = []
        db._shockers[key].append({"shocker_id": shocker_id, "shocker_name": shocker_name})

    async def get_user_shockers(user_id, guild_id):
        key = (user_id, guild_id)
        return db._shockers.get(key, [])

    async def check_permission(controller_id, target_id, guild_id):
        for perm in db._permissions:
            if (
                perm["controller_id"] == controller_id
                and perm["user_id"] == target_id
                and perm["guild_id"] == guild_id
            ):
                return True
        return False

    async def add_trigger(user_id, guild_id, pattern, action, intensity, duration):
        trigger_id = len(db._triggers) + 1
        key = (user_id, guild_id)
        if key not in db._triggers:
            db._triggers[key] = []
        db._triggers[key].append(
            {
                "id": trigger_id,
                "pattern": pattern,
                "action": action,
                "intensity": intensity,
                "duration": duration,
            }
        )
        return trigger_id

    async def get_user_triggers(user_id, guild_id):
        key = (user_id, guild_id)
        return db._triggers.get(key, [])

    db.grant_permission = grant_permission
    db.get_permissions = get_permissions
    db.register_user = register_user
    db.is_user_registered = is_user_registered
    db.add_shocker = add_shocker
    db.get_user_shockers = get_user_shockers
    db.check_permission = check_permission
    db.get_user = AsyncMock(return_value=None)
    db.add_trigger = add_trigger
    db.get_user_triggers = get_user_triggers
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_api_client() -> Mock:
    """Create a mock OpenShock API client."""
    client = Mock()
    client.send_action = AsyncMock(return_value={"success": True})
    client.get_shockers = AsyncMock(
        return_value=[
            {"id": "shocker1", "name": "Test Shocker 1", "isPaused": False},
            {"id": "shocker2", "name": "Test Shocker 2", "isPaused": False},
        ]
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_bot(mock_config) -> Mock:
    """Create a mock BotShock instance."""
    bot = Mock(spec=BotShock)
    bot.config = mock_config
    bot.db = Mock()
    bot.api_client = Mock()
    bot.scheduler = Mock()
    bot.trigger_manager = Mock()
    bot.user = Mock()
    bot.user.id = 999888777
    bot.user.name = "BotShock"
    bot.guilds = []
    return bot


@pytest.fixture
async def real_bot(mock_config) -> AsyncGenerator[BotShock]:
    """
    Create a real BotShock instance for integration tests.

    Note: This creates an actual bot instance but doesn't connect to Discord.
    """
    bot = BotShock(mock_config)

    # Initialize services without starting the bot
    bot.db = Database(db_path=":memory:", encryption_key=mock_config.encryption_key)
    await bot.db.initialize()

    yield bot

    # Cleanup
    if bot.db:
        await bot.db.close()


# ==================== Helper Fixtures ====================


@pytest.fixture
def sample_shocker_data() -> dict:
    """Provide sample shocker data for tests."""
    return {
        "id": "test_shocker_123",
        "name": "Test Shocker",
        "isPaused": False,
        "model": "PetTrainer998",
    }


@pytest.fixture
def sample_api_token() -> str:
    """Provide a sample API token for tests."""
    return "test_api_token_1234567890abcdef"


@pytest.fixture
def sample_trigger_data() -> dict:
    """Provide sample trigger data for tests."""
    return {
        "pattern": r"test.*pattern",
        "action": "vibrate",
        "intensity": 50,
        "duration": 2,
        "enabled": True,
    }


@pytest.fixture
def sample_reminder_data() -> dict:
    """Provide sample reminder data for tests."""
    return {
        "action": "shock",
        "intensity": 30,
        "duration": 1,
        "scheduled_time": datetime.now(UTC),
        "recurrence_pattern": None,
    }


# ==================== Async Test Helpers ====================


@pytest.fixture
def async_return():
    """Helper to create async functions that return a value."""

    def _async_return(value):
        async def _wrapper(*args, **kwargs):
            return value

        return _wrapper

    return _async_return


@pytest.fixture
def async_raise():
    """Helper to create async functions that raise an exception."""

    def _async_raise(exception):
        async def _wrapper(*args, **kwargs):
            raise exception

        return _wrapper

    return _async_raise


# ==================== Context Managers ====================


@pytest.fixture
def mock_discord_context():
    """
    Provide a context manager that patches Discord-related functionality.

    This helps solve the "context" problem by providing a complete Discord
    environment for tests without needing an actual bot connection.
    """

    class DiscordContext:
        def __init__(self):
            self.user = None
            self.guild = None
            self.channel = None
            self.interaction = None

        def setup(self, user=None, guild=None, channel=None, interaction=None):
            self.user = user
            self.guild = guild
            self.channel = channel
            self.interaction = interaction
            return self

    return DiscordContext()
