"""
Reminder scheduler service for executing scheduled shocks
"""

import asyncio
import logging
from datetime import datetime

import disnake

from botshock.utils.recurrence import RecurrencePattern

logger = logging.getLogger("BotShock.ReminderScheduler")


class ReminderScheduler:
    """Handles scheduled reminder execution"""

    def __init__(self, bot: disnake.Client, database, api_client):
        self.bot = bot
        self.db = database
        self.api_client = api_client
        self.running = False
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the reminder scheduler"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._scheduler_loop())
            logger.info("Reminder scheduler started")

    def stop(self) -> None:
        """Stop the reminder scheduler"""
        self.running = False
        if self.task:
            self.task.cancel()
            logger.info("Reminder scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop that checks for due reminders"""
        await self.bot.wait_until_ready()

        while self.running:
            try:
                await self._check_and_execute_reminders()
                # Check every 30 seconds
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminder scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on error

    async def _check_and_execute_reminders(self) -> None:
        """Check for due reminders and execute them"""
        try:
            # get_pending_reminders is async and uses aiosqlite
            pending_reminders = await self.db.get_pending_reminders()

            for reminder in pending_reminders:
                try:
                    await self._execute_reminder(reminder)
                except Exception as e:
                    logger.error(
                        f"Failed to execute reminder {reminder.get('id')}: {e}", exc_info=True
                    )
                    # Mark as completed even on error to prevent retry loops
                    try:
                        await self.db.mark_reminder_completed(reminder["id"])
                    except Exception:
                        logger.exception("Failed to mark reminder completed after execution error")
        except Exception as e:
            logger.error(f"Error checking pending reminders: {e}", exc_info=True)

    async def _execute_reminder(self, reminder: dict) -> None:
        """Execute a single reminder"""
        reminder_id = reminder["id"]
        guild_id = reminder["guild_id"]
        target_id = reminder["target_discord_id"]
        creator_id = reminder["creator_discord_id"]
        is_recurring = bool(reminder.get("is_recurring", False))
        recurrence_pattern = reminder.get("recurrence_pattern")

        logger.info(
            f"Executing reminder {reminder_id} - Guild: {guild_id} - "
            f"Target: {target_id} - Creator: {creator_id}"
            + (f" - Recurring: {recurrence_pattern}" if is_recurring else "")
        )

        # Get guild
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.warning(f"Guild {guild_id} not found for reminder {reminder_id}")
            try:
                await self.db.mark_reminder_completed(reminder_id)
            except Exception:
                logger.exception("Failed to mark reminder completed when guild missing")
            return

        # Get target user (async)
        target_user = await self.db.get_user(target_id, guild_id)
        if not target_user:
            logger.warning(
                f"Target user {target_id} not registered in guild {guild_id} for reminder {reminder_id}"
            )
            try:
                await self.db.mark_reminder_completed(reminder_id)
            except Exception:
                logger.exception("Failed to mark reminder completed when user missing")
            return

        # Get shockers (async)
        shockers = await self.db.get_shockers(target_id, guild_id)
        if not shockers:
            logger.warning(
                f"Target user {target_id} has no shockers in guild {guild_id} for reminder {reminder_id}"
            )
            try:
                await self.db.mark_reminder_completed(reminder_id)
            except Exception:
                logger.exception("Failed to mark reminder completed when no shockers")
            return

        # Use first shocker
        target_shocker = shockers[0]

        # Check device cooldown (async)
        device_ready = await self.db.check_shocker_cooldown(
            target_id, guild_id, target_shocker["shocker_id"], cooldown_seconds=60
        )

        if not device_ready:
            logger.info(
                f"Reminder {reminder_id} postponed - device on cooldown. Will retry in next cycle."
            )
            return  # Don't mark as completed, will retry

        # Send the shock
        success, status_code, response_text = await self.api_client.send_control(
            api_token=target_user["openshock_api_token"],
            shocker_id=target_shocker["shocker_id"],
            shock_type=reminder.get("shock_type"),
            intensity=reminder.get("intensity"),
            duration=reminder.get("duration"),
            custom_name="Reminder from Discord",
            user_id=target_id,
            base_url_override=target_user.get("api_server"),
        )

        if success:
            try:
                await self.db.update_shocker_cooldown(
                    target_id, guild_id, target_shocker["shocker_id"]
                )
            except Exception:
                logger.exception("Failed to update shocker cooldown after reminder success")

            logger.info(
                f"Reminder shock sent successfully - Reminder: {reminder_id} - "
                f"Target: {target_id} - Type: {reminder.get('shock_type')} - "
                f"Intensity: {reminder.get('intensity')}% - Duration: {reminder.get('duration')}ms"
            )

            await self._send_notification(reminder, guild, target_id, creator_id)

            # Handle recurring reminders
            if is_recurring and recurrence_pattern:
                await self._schedule_next_occurrence(reminder)
            else:
                # Mark as completed for non-recurring (async)
                try:
                    await self.db.mark_reminder_completed(reminder_id)
                except Exception:
                    logger.exception("Failed to mark non-recurring reminder completed")
        else:
            logger.error(
                f"Reminder shock failed - Reminder: {reminder_id} - Status: {status_code} - Response: {response_text}"
            )
            # Mark as completed to prevent infinite retries (async)
            try:
                await self.db.mark_reminder_completed(reminder_id)
            except Exception:
                logger.exception("Failed to mark reminder completed after failed shock")

    async def _schedule_next_occurrence(self, reminder: dict) -> None:
        """Schedule the next occurrence of a recurring reminder"""
        reminder_id = reminder["id"]
        recurrence_pattern = reminder.get("recurrence_pattern")

        try:
            # Parse the recurrence pattern
            pattern_dict = RecurrencePattern.parse_pattern(recurrence_pattern)
            if not pattern_dict:
                logger.error(
                    f"Invalid recurrence pattern for reminder {reminder_id}: {recurrence_pattern}"
                )
                try:
                    await self.db.mark_reminder_completed(reminder_id)
                except Exception:
                    logger.exception("Failed to mark reminder completed for invalid recurrence")
                return

            # Get original scheduled time (for time of day reference)
            original_time = datetime.fromisoformat(
                reminder.get("created_at") or reminder.get("scheduled_time")
            )
            last_executed = datetime.now()

            # Calculate next occurrence
            next_time = RecurrencePattern.calculate_next_occurrence(
                pattern_dict, last_executed, original_time
            )

            if next_time:
                # Update reminder with next scheduled time (async)
                success = await self.db.update_recurring_reminder(reminder_id, next_time)
                if success:
                    logger.info(
                        f"Scheduled next occurrence of recurring reminder {reminder_id} for {next_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                else:
                    logger.error(f"Failed to update recurring reminder {reminder_id}")
            else:
                logger.error(f"Could not calculate next occurrence for reminder {reminder_id}")
                try:
                    await self.db.mark_reminder_completed(reminder_id)
                except Exception:
                    logger.exception(
                        "Failed to mark reminder completed when next occurrence not found"
                    )

        except Exception as e:
            logger.error(
                f"Error scheduling next occurrence for reminder {reminder_id}: {e}", exc_info=True
            )
            try:
                await self.db.mark_reminder_completed(reminder_id)
            except Exception:
                logger.exception("Failed to mark reminder completed after scheduling error")

    @staticmethod
    async def _send_notification(
        reminder: dict, guild: disnake.Guild, target_id: int, creator_id: int
    ) -> None:
        """Send notification message about the reminder"""
        try:
            target_member = guild.get_member(target_id)
            creator_member = guild.get_member(creator_id)

            if not target_member:
                logger.warning(f"Target member {target_id} not found in guild")
                return

            reason_text = (
                f"\n**Reason:** {reminder.get('reason')}" if reminder.get("reason") else ""
            )
            creator_text = creator_member.mention if creator_member else f"User ID {creator_id}"

            is_recurring = bool(reminder.get("is_recurring", False))
            recurring_text = ""
            if is_recurring:
                pattern = reminder.get("recurrence_pattern", "")
                pattern_dict = RecurrencePattern.parse_pattern(pattern)
                if pattern_dict:
                    recurring_text = (
                        f"\n🔄 **Recurring:** {RecurrencePattern.format_pattern(pattern_dict)}"
                    )

            message = (
                f"{target_member.mention} ⚡ Reminder executed!\n"
                f"**Set by:** {creator_text}\n"
                f"**Type:** {reminder.get('shock_type')}\n"
                f"**Intensity:** {reminder.get('intensity')}%\n"
                f"**Duration:** {reminder.get('duration')}ms"
                f"{reason_text}"
                f"{recurring_text}"
            )

            # Try to send DM first
            try:
                await target_member.send(message)
                logger.info(f"Reminder notification sent via DM to {target_id}")
                return
            except (disnake.Forbidden, disnake.HTTPException):
                logger.info(f"Cannot send DM to {target_id}, falling back to channel")

            # Fall back to channel if specified
            if reminder.get("channel_id"):
                channel = guild.get_channel(reminder.get("channel_id"))
                if channel and isinstance(channel, disnake.TextChannel):
                    try:
                        await channel.send(message)
                        logger.info(
                            f"Reminder notification sent to channel {channel.name} in guild {guild.name}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification to channel: {e}")
        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
