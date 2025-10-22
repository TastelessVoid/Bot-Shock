"""
Tests for time parsing utilities.
"""

import pytest
from datetime import datetime, timedelta

from botshock.utils.time_parser import TimeParser


class TestTimeParser:
    """Test time parsing functionality."""

    def test_parse_minutes(self):
        """Test parsing minute format."""
        result = TimeParser.parse("30m")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_hours(self):
        """Test parsing hour format."""
        result = TimeParser.parse("2h")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_days(self):
        """Test parsing day format."""
        result = TimeParser.parse("5d")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_combined_format(self):
        """Test parsing combined format."""
        result = TimeParser.parse("1d12h30m")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_clock_time_valid(self):
        """Test parsing valid clock time."""
        result = TimeParser.parse("15:00")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_clock_time_invalid_hour(self):
        """Test parsing invalid clock time with bad hour."""
        result = TimeParser.parse("25:00")
        assert result is None

    def test_parse_clock_time_invalid_minute(self):
        """Test parsing invalid clock time with bad minute."""
        result = TimeParser.parse("15:60")
        assert result is None

    def test_parse_invalid_format(self):
        """Test parsing completely invalid format."""
        result = TimeParser.parse("invalid")
        assert result is None

    def test_format_duration_days(self):
        """Test formatting duration with days."""
        duration = timedelta(days=5)
        result = TimeParser.format_duration(duration)
        assert "5d" in result

    def test_format_duration_hours(self):
        """Test formatting duration with hours."""
        duration = timedelta(hours=2)
        result = TimeParser.format_duration(duration)
        assert "2h" in result

    def test_format_duration_minutes(self):
        """Test formatting duration with minutes."""
        duration = timedelta(minutes=30)
        result = TimeParser.format_duration(duration)
        assert "30m" in result

    def test_format_duration_combined(self):
        """Test formatting combined duration."""
        duration = timedelta(days=1, hours=12, minutes=30)
        result = TimeParser.format_duration(duration)
        assert "1d" in result
        assert "12h" in result
        assert "30m" in result

    def test_format_duration_zero(self):
        """Test formatting zero duration."""
        duration = timedelta(seconds=0)
        result = TimeParser.format_duration(duration)
        assert result == "less than 1m"

    def test_format_preview_valid(self):
        """Test formatting preview for valid time."""
        preview = TimeParser.format_preview("2h")
        assert "2h" in preview
        assert "→" in preview

    def test_format_preview_invalid(self):
        """Test formatting preview for invalid time."""
        preview = TimeParser.format_preview("invalid")
        assert "Invalid" in preview

    def test_get_example_suggestions(self):
        """Test getting example suggestions."""
        suggestions = TimeParser.get_example_suggestions()
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

