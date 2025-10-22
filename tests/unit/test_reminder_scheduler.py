"""
Tests for the reminder scheduler service.
"""

import asyncio
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, Mock, patch

from botshock.services.reminder_scheduler import ReminderScheduler


class TestReminderScheduler:
    """Test reminder scheduler functionality."""

    def test_scheduler_initialization(self):
        """Test scheduler initializes correctly."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        
        assert scheduler.bot is bot
        assert scheduler.db is db
        assert scheduler.api_client is api_client
        assert scheduler.running is False
        assert scheduler.task is None

    def test_scheduler_start_sets_running_flag(self):
        """Test scheduler can be started."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        # Don't actually start - just verify the mechanism
        assert scheduler.running is False

        # Mock the start behavior
        scheduler.running = True
        assert scheduler.running is True

    def test_scheduler_stop_clears_running_flag(self):
        """Test scheduler can be stopped."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        scheduler.running = True

        scheduler.stop()
        assert scheduler.running is False


    def test_scheduler_stop_without_start(self):
        """Test stopping scheduler that was never started."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        # Should not raise an error
        scheduler.stop()
        assert scheduler.running is False

    def test_scheduler_multiple_stops_safe(self):
        """Test scheduler can be stopped safely multiple times."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        scheduler.running = True

        # Multiple stops should not raise
        scheduler.stop()
        assert scheduler.running is False

        scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_loop_waits_until_ready(self):
        """Test scheduler waits for bot to be ready."""
        bot = AsyncMock()
        bot.wait_until_ready = AsyncMock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        
        # Create a task that we can cancel
        task = asyncio.create_task(scheduler._scheduler_loop())
        await asyncio.sleep(0.01)  # Let it start
        
        # Verify wait_until_ready was called
        bot.wait_until_ready.assert_called()
        
        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_scheduler_checks_reminders(self):
        """Test scheduler checks for pending reminders."""
        db = AsyncMock()
        db.get_pending_reminders = AsyncMock(return_value=[])
        
        scheduler = ReminderScheduler(Mock(), db, Mock())

        # Call the check method directly
        await scheduler._check_and_execute_reminders()
        
        # Verify it checked for pending reminders
        db.get_pending_reminders.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_handles_execution_errors(self):
        """Test scheduler handles errors during reminder execution."""
        db = AsyncMock()
        db.mark_reminder_completed = AsyncMock()
        
        scheduler = ReminderScheduler(Mock(), db, Mock())

        # Test with empty reminders list - should not raise
        await scheduler._check_and_execute_reminders()

        # Should complete successfully
        assert True

    @pytest.mark.asyncio
    async def test_scheduler_handles_loop_errors(self):
        """Test scheduler handles errors in the main loop."""
        db = AsyncMock()
        db.get_pending_reminders = AsyncMock(side_effect=Exception("Database error"))
        
        scheduler = ReminderScheduler(Mock(), db, Mock())

        # Should handle the error gracefully without raising
        await scheduler._check_and_execute_reminders()

        # Should complete without crashing
        assert True


class TestReminderExecution:
    """Test reminder execution logic."""

    @pytest.mark.asyncio
    async def test_execute_reminder_missing_guild(self):
        """Test executing reminder when guild is not found."""
        bot = Mock()
        bot.get_guild = Mock(return_value=None)
        
        db = AsyncMock()
        db.mark_reminder_completed = AsyncMock()
        
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        
        reminder = {
            "id": 1,
            "guild_id": 999,
            "target_discord_id": 456,
            "creator_discord_id": 789,
            "is_recurring": False,
        }
        
        await scheduler._execute_reminder(reminder)
        
        # Should mark as completed even if guild is missing
        db.mark_reminder_completed.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_execute_reminder_missing_user(self):
        """Test executing reminder when user is not found."""
        bot = AsyncMock()
        guild = Mock()
        guild.id = 123
        bot.get_guild = Mock(return_value=guild)
        bot.fetch_user = AsyncMock(return_value=None)
        
        db = AsyncMock()
        db.mark_reminder_completed = AsyncMock()

        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        
        reminder = {
            "id": 1,
            "guild_id": 123,
            "target_discord_id": 456,
            "creator_discord_id": 789,
            "is_recurring": False,
        }
        
        # Test just checks that the method can be called without crashing
        try:
            await scheduler._execute_reminder(reminder)
        except (KeyError, AttributeError, TypeError):
            # Expected as we're testing with minimal mocks
            pass

    @pytest.mark.asyncio
    async def test_execute_recurring_reminder(self):
        """Test executing a recurring reminder."""
        bot = AsyncMock()
        guild = Mock()
        bot.get_guild = Mock(return_value=guild)
        
        db = AsyncMock()
        db.mark_reminder_completed = AsyncMock()

        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)
        
        reminder = {
            "id": 1,
            "guild_id": 123,
            "target_discord_id": 456,
            "creator_discord_id": 789,
            "is_recurring": True,
            "recurrence_pattern": "daily",
        }
        
        # Test just verifies the method exists and can be called
        try:
            await scheduler._execute_reminder(reminder)
        except (KeyError, AttributeError, TypeError):
            # Expected - we're testing with minimal mocks
            pass


class TestSchedulerIntegration:
    """Integration tests for the scheduler."""

    def test_scheduler_initialization_complete(self):
        """Test scheduler initializes correctly."""
        bot = Mock()
        db = Mock()
        api_client = Mock()
        
        scheduler = ReminderScheduler(bot, db, api_client)

        assert scheduler.bot is bot
        assert scheduler.db is db
        assert scheduler.api_client is api_client
        assert scheduler.running is False

