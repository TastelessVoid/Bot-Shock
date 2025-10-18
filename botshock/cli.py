"""
Command-line interface for Bot Shock.
"""

import sys
from pathlib import Path

import disnake

from botshock.config import load_config, validate_config
from botshock.constants import APP_NAME
from botshock.core.bot import BotShock
from botshock.exceptions import ConfigurationError
from botshock.logging_config import setup_logging


def main() -> int:
    """
    Main entry point for the bot application.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    try:
        # Load and validate configuration
        config = load_config()
        validate_config(config)
    except ConfigurationError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        return 1

    # Setup logging (respect configured directory)
    log_dir_path = Path(config.log_dir)
    logger = setup_logging(
        log_level=config.log_level,
        log_dir=log_dir_path,
        max_old=config.log_max_old_files,
        retention_days=config.log_retention_days,
    )
    logger.info("Starting %s...", APP_NAME)
    logger.info("Logging to: %s", (log_dir_path / "bot.log").resolve())

    # Create and run bot
    bot = BotShock(config)

    try:
        # Prepare dependencies before loading cogs so they get valid references
        bot.prepare_cog_dependencies()

        # Load all cogs
        bot.load_all_cogs()

        # Run the bot
        logger.info("Starting bot (managed run)...")
        bot.run(config.discord_token)
        return 0

    except disnake.errors.PrivilegedIntentsRequired:
        logger.error(
            "Privileged intents are required but not enabled. Go to the Discord Developer Portal > Your Application > Bot > Privileged Gateway Intents and enable 'SERVER MEMBERS INTENT' and 'MESSAGE CONTENT INTENT'."
        )
        return 1
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down")
        return 0
    except Exception:
        logger.exception("Unhandled exception in main")
        return 1


if __name__ == "__main__":
    sys.exit(main())
