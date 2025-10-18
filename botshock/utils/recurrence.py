"""
Recurrence pattern parser for recurring reminders
"""
import re
from datetime import datetime, timedelta


class RecurrencePattern:
    """Handles parsing and calculation of recurring reminder patterns"""

    WEEKDAYS = {
        'monday': 0, 'mon': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2,
        'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }

    @staticmethod
    def parse_pattern(pattern: str) -> dict | None:
        """
        Parse a recurrence pattern string into a structured format

        Supported patterns:
        - "daily" or "every day"
        - "weekly" or "every week"
        - "every monday" or "every mon"
        - "every 2 days"
        - "every 3 hours"
        - "weekdays" (Monday-Friday)
        - "weekends" (Saturday-Sunday)

        Returns:
            dict with 'type' and relevant parameters, or None if invalid
        """
        pattern = pattern.lower().strip()

        # Daily
        if pattern in ['daily', 'every day', 'everyday']:
            return {'type': 'daily'}

        # Weekly
        if pattern in ['weekly', 'every week']:
            return {'type': 'weekly'}

        # Specific weekday
        for day_name, day_num in RecurrencePattern.WEEKDAYS.items():
            if pattern in [f'every {day_name}', f'{day_name}s', f'every {day_name}s']:
                return {'type': 'weekly', 'weekday': day_num}

        # Weekdays (Mon-Fri)
        if pattern in ['weekdays', 'every weekday', 'weekday']:
            return {'type': 'weekdays'}

        # Weekends (Sat-Sun)
        if pattern in ['weekends', 'every weekend', 'weekend']:
            return {'type': 'weekends'}

        # Every X days
        match = re.match(r'every (\d+) days?', pattern)
        if match:
            days = int(match.group(1))
            if 1 <= days <= 365:
                return {'type': 'interval', 'unit': 'days', 'value': days}

        # Every X hours
        match = re.match(r'every (\d+) hours?', pattern)
        if match:
            hours = int(match.group(1))
            if 1 <= hours <= 168:  # Max 1 week
                return {'type': 'interval', 'unit': 'hours', 'value': hours}

        return None

    @staticmethod
    def calculate_next_occurrence(pattern_dict: dict, last_time: datetime, base_time: datetime) -> datetime | None:
        """
        Calculate the next occurrence based on pattern

        Args:
            pattern_dict: Parsed pattern dictionary
            last_time: Last execution time
            base_time: Original scheduled time (for time of day reference)

        Returns:
            Next scheduled datetime or None if pattern invalid
        """
        if not pattern_dict:
            return None

        pattern_type = pattern_dict.get('type')

        if pattern_type == 'daily':
            # Same time tomorrow
            next_time = last_time + timedelta(days=1)
            # Use base_time for the exact time of day
            next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
            return next_time

        elif pattern_type == 'weekly':
            if 'weekday' in pattern_dict:
                # Specific weekday
                target_weekday = pattern_dict['weekday']
                next_time = last_time + timedelta(days=1)

                # Find next occurrence of target weekday
                while next_time.weekday() != target_weekday:
                    next_time += timedelta(days=1)

                next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
                return next_time
            else:
                # Every 7 days
                next_time = last_time + timedelta(days=7)
                next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
                return next_time

        elif pattern_type == 'weekdays':
            # Next weekday (Mon-Fri)
            next_time = last_time + timedelta(days=1)
            while next_time.weekday() >= 5:  # Skip Sat(5) and Sun(6)
                next_time += timedelta(days=1)
            next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
            return next_time

        elif pattern_type == 'weekends':
            # Next weekend day (Sat-Sun)
            next_time = last_time + timedelta(days=1)
            while next_time.weekday() < 5:  # Skip Mon-Fri
                next_time += timedelta(days=1)
            next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
            return next_time

        elif pattern_type == 'interval':
            unit = pattern_dict.get('unit')
            value = pattern_dict.get('value')

            if unit == 'days':
                next_time = last_time + timedelta(days=value)
                next_time = next_time.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
                return next_time
            elif unit == 'hours':
                next_time = last_time + timedelta(hours=value)
                return next_time

        return None

    @staticmethod
    def format_pattern(pattern_dict: dict) -> str:
        """Format a pattern dictionary into a human-readable string"""
        if not pattern_dict:
            return "Invalid pattern"

        pattern_type = pattern_dict.get('type')

        if pattern_type == 'daily':
            return "Every day"
        elif pattern_type == 'weekly':
            if 'weekday' in pattern_dict:
                weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                return f"Every {weekday_names[pattern_dict['weekday']]}"
            return "Every week"
        elif pattern_type == 'weekdays':
            return "Every weekday (Mon-Fri)"
        elif pattern_type == 'weekends':
            return "Every weekend (Sat-Sun)"
        elif pattern_type == 'interval':
            unit = pattern_dict.get('unit')
            value = pattern_dict.get('value')
            return f"Every {value} {unit}"

        return "Unknown pattern"

    @staticmethod
    def validate_pattern(pattern: str) -> tuple[bool, str]:
        """
        Validate a recurrence pattern string

        Returns:
            Tuple of (is_valid, error_message)
        """
        parsed = RecurrencePattern.parse_pattern(pattern)
        if parsed is None:
            return False, "Invalid recurrence pattern. Use formats like 'daily', 'every monday', 'every 2 days', etc."
        return True, RecurrencePattern.format_pattern(parsed)

    @staticmethod
    def get_examples() -> list:
        """Get example recurrence patterns"""
        return [
            "daily",
            "every monday",
            "every friday",
            "weekdays",
            "weekends",
            "every 3 days",
            "every 12 hours"
        ]
