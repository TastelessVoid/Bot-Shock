"""
Centralized logger factory for consistent logging across the application.

This module eliminates redundancy in logger initialization and ensures
consistent naming conventions throughout the codebase.
"""

import logging

LOGGER_NAMESPACE = "BotShock"


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger instance for a module with consistent naming.

    This factory function ensures all loggers follow the naming convention:
    "BotShock.ModuleName"

    Args:
        module_name: The module name (can include dots for submodules)
                    Examples: "CommandHelpers", "Cogs.ShockCommand", "Services.APIClient"

    Returns:
        Configured logger instance

    Example:
        Instead of:
            logger = logging.getLogger("BotShock.CommandHelpers")

        Use:
            from botshock.utils.logger import get_logger
            logger = get_logger("CommandHelpers")
    """
    full_name = f"{LOGGER_NAMESPACE}.{module_name}"
    return logging.getLogger(full_name)

