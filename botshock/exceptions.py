"""
Custom exception classes for Bot Shock.
"""


class BotShockException(Exception):
    """Base exception for all BotShock errors."""

    pass


class ConfigurationError(BotShockException):
    """Raised when there's a configuration error."""

    pass


class DatabaseError(BotShockException):
    """Raised when there's a database operation error."""

    pass


class EncryptionError(BotShockException):
    """Raised when there's an encryption/decryption error."""

    pass


class APIError(BotShockException):
    """Raised when there's an API communication error."""

    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    pass


class AuthenticationError(APIError):
    """Raised when API authentication fails."""

    pass


class PermissionError(BotShockException):
    """Raised when a user lacks required permissions."""

    pass


class ValidationError(BotShockException):
    """Raised when input validation fails."""

    pass
