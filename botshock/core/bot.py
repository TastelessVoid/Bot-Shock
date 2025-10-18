"""
Core bot class for Bot Shock.

This module contains the main BotShock class that extends disnake's InteractionBot
and manages all bot functionality including cogs, services, and lifecycle.
"""

import logging

import disnake
from disnake.ext import commands

from botshock.config import BotConfig
from botshock.core.database import Database
from botshock.exceptions import BotShockException
from botshock.services.api_client import OpenShockAPIClient
from botshock.services.reminder_scheduler import ReminderScheduler
from botshock.services.trigger_manager import TriggerManager
from botshock.utils.command_helpers import CommandHelper
from botshock.utils.formatters import ResponseFormatter
from botshock.utils.permissions import PermissionChecker

logger = logging.getLogger("BotShock")


class BotShock(commands.InteractionBot):
    """
    Main bot class for Bot Shock.

    This class extends disnake's InteractionBot and manages:
    - Database connections
    - Service initialization (API client, scheduler, trigger manager)
    - Cog loading and lifecycle
    - Graceful shutdown

    Attributes:
        config: Bot configuration
        db: Database instance
        api_client: OpenShock API client
        scheduler: Reminder scheduler service
        trigger_manager: Trigger management service
    """

    def __init__(self, config: BotConfig):
        """
        Initialize the bot.

        Args:
            config: Bot configuration object containing all settings
        """
        # Initialize the bot with appropriate intents
        intents = disnake.Intents.default()
        setattr(intents, "message_content", True)
        setattr(intents, "members", True)

        super().__init__(
            intents=intents,
            test_guilds=config.test_guilds if hasattr(config, "test_guilds") else None,
        )

        self.config = config

        # Initialize core service references (actual construction deferred)
        self.api_client: OpenShockAPIClient | None = None
        self.scheduler: ReminderScheduler | None = None
        self.trigger_manager: TriggerManager | None = None

        # Defer database and dependent helpers until setup or explicit prep
        self.db: Database | None = None
        self.permission_checker: PermissionChecker | None = None
        self.formatter: ResponseFormatter = ResponseFormatter()
        self.command_helper: CommandHelper | None = None

        logger.info("Bot Shock instance created")

    def prepare_cog_dependencies(self):
        """Create DB and helper objects before loading cogs (no I/O/awaits).

        This ensures cogs that access bot.db, permission_checker, or command_helper
        during their __init__ will receive valid references. The database connection
        itself is initialized asynchronously later in setup_hook().
        """
        if self.db is None:
            self.db = Database(
                db_path=self.config.database_path,
                encryption_key=self.config.encryption_key,
                pool_size=getattr(self.config, "database_pool_size", 5),
            )
        if self.permission_checker is None:
            self.permission_checker = PermissionChecker(self.db)
        if self.command_helper is None:
            self.command_helper = CommandHelper(self.db, self.permission_checker, self.formatter)
        if self.trigger_manager is None:
            self.trigger_manager = TriggerManager(database=self.db)

    def get_api_client(self) -> OpenShockAPIClient:
        """Get or lazily create the API client.
        Useful in cogs during early interactions before setup_hook completes.
        """
        if self.api_client is None:
            self.api_client = OpenShockAPIClient(
                base_url=self.config.api_base_url,
                timeout=self.config.api_timeout,
                max_connections=self.config.api_max_connections,
                requests_per_minute=self.config.api_requests_per_minute,
            )
        return self.api_client

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info("Bot is ready!")

        # Set bot presence
        await self.change_presence(
            activity=disnake.Activity(type=disnake.ActivityType.watching, name="OpenShock users")
        )

    @commands.slash_command(name="ping", description="Check if the bot is responsive")
    async def ping(self, inter: disnake.ApplicationCommandInteraction):
        """Check if the bot is responsive."""
        await inter.response.send_message("Pong! 🏓")

    @staticmethod
    async def on_connect():
        """Called when the bot connects to Discord."""
        logger.info("Connected to Discord")

    @staticmethod
    async def on_disconnect():
        """Called when the bot disconnects from Discord."""
        logger.warning("Disconnected from Discord")

    @staticmethod
    async def on_resumed():
        """Called when the bot resumes a session."""
        logger.info("Resumed Discord session")

    async def setup_hook(self):
        """
        Setup hook called before the bot starts.

        This initializes all services and prepares the bot for operation.
        """
        logger.info("Running setup hook...")

        # Ensure DB and helper objects exist before attempting async initialization.
        # This covers cases where prepare_cog_dependencies wasn't called earlier
        # (e.g. during tests) so that self.db is not None when we call initialize().
        self.prepare_cog_dependencies()

        try:
            # Initialize database connection pool/schema asynchronously
            logger.info("Initializing database...")
            await self.db.initialize()
            logger.info("Database initialized successfully")

            # Initialize API client
            logger.info("Initializing API client...")
            self.api_client = OpenShockAPIClient(
                base_url=self.config.api_base_url,
                timeout=self.config.api_timeout,
                max_connections=self.config.api_max_connections,
                requests_per_minute=self.config.api_requests_per_minute,
            )
            logger.info("API client initialized successfully")

            # Initialize trigger manager (only if not already created during prep)
            logger.info("Initializing trigger manager...")
            if self.trigger_manager is None:
                self.trigger_manager = TriggerManager(database=self.db)
            logger.info("Trigger manager initialized successfully")

            # Initialize and start reminder scheduler
            logger.info("Initializing reminder scheduler...")
            self.scheduler = ReminderScheduler(
                bot=self, database=self.db, api_client=self.api_client
            )
            self.scheduler.start()
            logger.info("Reminder scheduler started successfully")

        except Exception as e:
            logger.exception("Error during setup hook")
            raise BotShockException(f"Failed to initialize bot services: {e}") from e

    async def close(self):
        """
        Cleanup method called when the bot is shutting down.

        Ensures all services are properly closed and resources are released.
        """
        logger.info("Shutting down Bot Shock...")

        try:
            # Stop scheduler
            if self.scheduler:
                logger.info("Stopping reminder scheduler...")
                self.scheduler.stop()

            # Close API client session
            if self.api_client:
                logger.info("Closing API client...")
                await self.api_client.close()

            # Close database connections
            if self.db:
                logger.info("Closing database connections...")
                await self.db.close()

            logger.info("All services closed successfully")

        except Exception as e:
            logger.exception(f"Error during shutdown:\n{e}")

        # Call parent close
        await super().close()
        logger.info("Bot Shock shutdown complete")

    def load_all_cogs(self):
        """
        Load all cogs from the cogs directory.

        This method loads all command modules and event listeners.
        """
        cogs_to_load = [
            "botshock.cogs.user_commands",
            "botshock.cogs.controller_commands",
            "botshock.cogs.shock_command",
            "botshock.cogs.trigger_commands",
            "botshock.cogs.reminder_commands",
            "botshock.cogs.controller_preferences",
            "botshock.cogs.settings",
            "botshock.cogs.action_logs",
            "botshock.cogs.event_listeners",
        ]

        loaded = 0
        failed = 0

        for cog in cogs_to_load:
            try:
                self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}", exc_info=True)
                failed += 1

        logger.info(f"Loaded {loaded} cogs successfully, {failed} failed")

        if failed > 0:
            logger.warning(f"{failed} cogs failed to load - bot may have reduced functionality")

    async def on_slash_command_error(
        self, interaction: disnake.ApplicationCommandInteraction, error: commands.CommandError
    ):
        """
        Global error handler for slash commands.

        Args:
            interaction: The command interaction
            error: The error that occurred
        """
        # Log the error
        logger.error(
            f"Error in command {interaction.application_command.name}: {error}", exc_info=error
        )

        # Prepare user-friendly error message
        if isinstance(error, commands.MissingPermissions):
            message = "❌ You don't have permission to use this command."
        elif isinstance(error, commands.BotMissingPermissions):
            message = "❌ I don't have the necessary permissions to execute this command."
        elif isinstance(error, commands.CommandOnCooldown):
            message = f"⏱️ This command is on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, commands.MissingRole):
            message = f"❌ You need the {error.missing_role} role to use this command."
        elif isinstance(error, BotShockException):
            # Our custom exceptions already have user-friendly messages
            message = f"❌ {error}"
        else:
            # Generic error message for unexpected errors
            message = "❌ An unexpected error occurred. Please try again later."
            # Log the full error for debugging
            logger.exception(f"Unhandled error in {interaction.application_command.name}")

        # Send error message to user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")
