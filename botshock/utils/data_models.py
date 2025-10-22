"""
Data normalization and validation for consistent database field handling.

This module provides utilities to normalize database records and ensure
consistent field naming across the application, eliminating patterns like
`s.get("id") or s.get("shocker_id")`.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Shocker:
    """Normalized shocker data model"""

    shocker_id: str
    name: Optional[str] = None
    is_paused: bool = False

    @classmethod
    def from_db(cls, db_record: dict) -> "Shocker":
        """
        Create Shocker from database record, normalizing field names.

        Args:
            db_record: Raw record from database

        Returns:
            Normalized Shocker instance
        """
        shocker_id = db_record.get("id") or db_record.get("shocker_id")
        if not shocker_id:
            raise ValueError("Shocker record missing 'id' or 'shocker_id'")

        return cls(
            shocker_id=str(shocker_id),
            name=db_record.get("name") or db_record.get("shocker_name"),
            is_paused=db_record.get("isPaused") or db_record.get("is_paused", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations"""
        return {
            "shocker_id": self.shocker_id,
            "shocker_name": self.name,
            "isPaused": self.is_paused,
        }


@dataclass
class User:
    """Normalized user data model"""

    discord_id: int
    guild_id: int
    username: str
    api_token: str
    api_server: Optional[str] = None

    @classmethod
    def from_db(cls, db_record: dict) -> "User":
        """
        Create User from database record.

        Args:
            db_record: Raw record from database

        Returns:
            Normalized User instance
        """
        return cls(
            discord_id=db_record["discord_id"],
            guild_id=db_record["guild_id"],
            username=db_record["discord_username"],
            api_token=db_record["openshock_api_token"],
            api_server=db_record.get("api_server"),
        )


@dataclass
class Trigger:
    """Normalized trigger data model"""

    trigger_id: int
    target_id: int
    guild_id: int
    pattern: str
    shock_type: str
    intensity: int
    duration: int
    cooldown_seconds: int
    enabled: bool = True
    name: Optional[str] = None

    @classmethod
    def from_db(cls, db_record: dict) -> "Trigger":
        """Create Trigger from database record"""
        return cls(
            trigger_id=db_record["id"],
            target_id=db_record["target_discord_id"],
            guild_id=db_record["guild_id"],
            pattern=db_record["regex_pattern"],
            shock_type=db_record["shock_type"],
            intensity=db_record["intensity"],
            duration=db_record["duration"],
            cooldown_seconds=db_record.get("cooldown_seconds", 60),
            enabled=db_record.get("enabled", True),
            name=db_record.get("trigger_name"),
        )


@dataclass
class Reminder:
    """Normalized reminder data model"""

    reminder_id: int
    target_id: int
    guild_id: int
    creator_id: int
    scheduled_time: str
    shock_type: str
    intensity: int
    duration: int
    reason: Optional[str] = None
    is_recurring: bool = False
    completed: bool = False

    @classmethod
    def from_db(cls, db_record: dict) -> "Reminder":
        """Create Reminder from database record"""
        return cls(
            reminder_id=db_record["id"],
            target_id=db_record["target_discord_id"],
            guild_id=db_record["guild_id"],
            creator_id=db_record["creator_discord_id"],
            scheduled_time=db_record["scheduled_time"],
            shock_type=db_record["shock_type"],
            intensity=db_record["intensity"],
            duration=db_record["duration"],
            reason=db_record.get("reason"),
            is_recurring=db_record.get("is_recurring", False),
            completed=db_record.get("completed", False),
        )


def normalize_shockers(records: list[dict]) -> list[Shocker]:
    """
    Normalize a list of shocker records.

    Args:
        records: List of raw shocker records from database

    Returns:
        List of normalized Shocker instances
    """
    return [Shocker.from_db(record) for record in records]


def normalize_triggers(records: list[dict]) -> list[Trigger]:
    """
    Normalize a list of trigger records.

    Args:
        records: List of raw trigger records from database

    Returns:
        List of normalized Trigger instances
    """
    return [Trigger.from_db(record) for record in records]


def normalize_reminders(records: list[dict]) -> list[Reminder]:
    """
    Normalize a list of reminder records.

    Args:
        records: List of raw reminder records from database

    Returns:
        List of normalized Reminder instances
    """
    return [Reminder.from_db(record) for record in records]

