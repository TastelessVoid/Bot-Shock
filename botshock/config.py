"""
Configuration management for Bot Shock.

This module handles loading and validating configuration from environment variables.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from botshock.constants import (
    API_MAX_CONNECTIONS,
    API_REQUESTS_PER_MINUTE,
    API_TIMEOUT_SECONDS,
    DEFAULT_DB_PATH,
    DEFAULT_POOL_SIZE,
    MAX_OLD_LOGS,
    OPENSHOCK_API_BASE_URL,
)
from botshock.exceptions import ConfigurationError


@dataclass(frozen=True)
class BotConfig:
    """Immutable configuration object for the bot."""

    # Required settings
    discord_token: str
    encryption_key: str

    # Database settings
    database_path: str = DEFAULT_DB_PATH
    database_pool_size: int = DEFAULT_POOL_SIZE

    # API settings
    api_base_url: str = OPENSHOCK_API_BASE_URL
    api_timeout: int = API_TIMEOUT_SECONDS
    api_max_connections: int = API_MAX_CONNECTIONS
    api_requests_per_minute: int = API_REQUESTS_PER_MINUTE

    # Logging settings
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_retention_days: int = 0  # 0 or less disables time-based pruning
    log_max_old_files: int = MAX_OLD_LOGS  # count-based pruning


def load_config(env_file: Path | None = None) -> BotConfig:
    """
    Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file. If None, uses default .env location.

    Returns:
        BotConfig: Validated configuration object.

    Raises:
        ConfigurationError: If required configuration is missing or invalid.
    """
    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Validate required variables
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise ConfigurationError(
            "ENCRYPTION_KEY not found in environment variables.\n"
            "The bot requires an encryption key to securely store API tokens.\n"
            "To generate a key, run: botshock-keygen (or python -m botshock.scripts.generate_key)\n"
            "Then add it to your .env as ENCRYPTION_KEY=<your_key>"
        )

    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        raise ConfigurationError(
            "DISCORD_TOKEN not found in environment variables.\n"
            "Please add your Discord bot token to the .env file as DISCORD_TOKEN=<your_bot_token>"
        )

    # Optional logging retention
    retention_env = os.getenv("LOG_RETENTION_DAYS", "0").strip()
    try:
        log_retention_days = int(retention_env)
    except ValueError:
        raise ConfigurationError("LOG_RETENTION_DAYS must be an integer (>= 0)") from None

    max_old_env = os.getenv("LOG_MAX_OLD_FILES", str(MAX_OLD_LOGS)).strip()
    try:
        log_max_old_files = int(max_old_env)
    except ValueError:
        raise ConfigurationError("LOG_MAX_OLD_FILES must be an integer (>= 0)") from None

    # Load optional settings with defaults
    return BotConfig(
        discord_token=discord_token,
        encryption_key=encryption_key,
        database_path=os.getenv("DATABASE_PATH", DEFAULT_DB_PATH),
        database_pool_size=int(os.getenv("DATABASE_POOL_SIZE", DEFAULT_POOL_SIZE)),
        api_base_url=os.getenv("API_BASE_URL", OPENSHOCK_API_BASE_URL),
        api_timeout=int(os.getenv("API_TIMEOUT", API_TIMEOUT_SECONDS)),
        api_max_connections=int(os.getenv("API_MAX_CONNECTIONS", API_MAX_CONNECTIONS)),
        api_requests_per_minute=int(os.getenv("API_REQUESTS_PER_MINUTE", API_REQUESTS_PER_MINUTE)),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_dir=os.getenv("LOG_DIR", "logs"),
        log_retention_days=log_retention_days,
        log_max_old_files=log_max_old_files,
    )


def validate_config(config: BotConfig) -> None:
    """
    Validate configuration values.

    Args:
        config: Configuration to validate.

    Raises:
        ConfigurationError: If configuration is invalid.
    """
    if config.database_pool_size < 1:
        raise ConfigurationError("DATABASE_POOL_SIZE must be at least 1")

    if config.api_timeout < 1:
        raise ConfigurationError("API_TIMEOUT must be at least 1 second")

    if config.api_max_connections < 1:
        raise ConfigurationError("API_MAX_CONNECTIONS must be at least 1")

    if config.api_requests_per_minute < 1:
        raise ConfigurationError("API_REQUESTS_PER_MINUTE must be at least 1")

    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.log_level not in valid_log_levels:
        raise ConfigurationError(
            f"LOG_LEVEL must be one of {valid_log_levels}, got {config.log_level}"
        )

    if config.log_retention_days < 0:
        raise ConfigurationError("LOG_RETENTION_DAYS must be >= 0")

    if config.log_max_old_files < 0:
        raise ConfigurationError("LOG_MAX_OLD_FILES must be >= 0")
