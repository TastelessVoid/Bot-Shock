"""
Time parsing utility for flexible time input formats
"""

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger("BotShock.TimeParser")


class TimeParser:
    """Handles parsing of various time input formats"""

    @staticmethod
    def parse(time_str: str) -> datetime | None:
        """
        Parse time string into datetime

        Supports:
        - HH:MM format (e.g., "15:00", "09:30")
        - Xd format (e.g., "5d", "2d")
        - Xh format (e.g., "2h", "1h")
        - Xm format (e.g., "30m", "90m")
        - Combined (e.g., "1d12h", "2h30m", "5d3h15m")

        Args:
            time_str: The time string to parse

        Returns:
            datetime object or None if invalid
        """
        time_str = time_str.strip()

        # Try HH:MM format first
        if ":" in time_str:
            return TimeParser._parse_clock_time(time_str)

        # Try relative time format
        return TimeParser._parse_relative_time(time_str)

    @staticmethod
    def _parse_clock_time(time_str: str) -> datetime | None:
        """Parse HH:MM format"""
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None

            now = datetime.now()
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time has passed today, schedule for tomorrow
            if scheduled <= now:
                scheduled += timedelta(days=1)

            return scheduled
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _parse_relative_time(time_str: str) -> datetime | None:
        """Parse relative time format (e.g., 5d, 2h, 30m, 1d12h30m)"""
        days = 0
        hours = 0
        minutes = 0

        # Match days
        day_match = re.search(r"(\d+)d", time_str, re.IGNORECASE)
        if day_match:
            days = int(day_match.group(1))

        # Match hours
        hour_match = re.search(r"(\d+)h", time_str, re.IGNORECASE)
        if hour_match:
            hours = int(hour_match.group(1))

        # Match minutes
        minute_match = re.search(r"(\d+)m", time_str, re.IGNORECASE)
        if minute_match:
            minutes = int(minute_match.group(1))

        # If we found any time component, calculate scheduled time
        if days > 0 or hours > 0 or minutes > 0:
            return datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)

        return None

    @staticmethod
    def format_duration(time_diff: timedelta) -> str:
        """
        Format a timedelta into human-readable duration

        Args:
            time_diff: The time difference to format

        Returns:
            Human-readable duration string (e.g., "5d 3h 15m")
        """
        total_seconds = int(time_diff.total_seconds())

        if total_seconds < 0:
            return "past"

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "less than 1m"

    # noinspection GrazieInspection
    @staticmethod
    def format_preview(time_str: str) -> str:
        """
        Format a preview of the parsed time for autocomplete

        Args:
            time_str: The input time string

        Returns:
            Preview string for Discord autocomplete
        """
        parsed_time = TimeParser.parse(time_str)

        if not parsed_time:
            return f"{time_str} → Invalid format"

        now = datetime.now()
        time_formatted = parsed_time.strftime("%Y-%m-%d %H:%M")
        time_diff = parsed_time - now

        if time_diff.total_seconds() < 0:
            return f"{time_str} → Invalid (past time)"

        duration_str = TimeParser.format_duration(time_diff)
        preview = f"{time_str} → {time_formatted} (in {duration_str})"

        # Discord has a 100 character limit for autocomplete
        return preview[:100]

    @staticmethod
    def get_example_suggestions() -> list[str]:
        """Get example time format suggestions"""
        return [
            "15:00 (3:00 PM today)",
            "2h (2 hours from now)",
            "30m (30 minutes from now)",
            "1h30m (1 hour 30 min from now)",
            "5d (5 days from now)",
        ]
