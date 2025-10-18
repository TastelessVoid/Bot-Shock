from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_add_and_get_reminder_async(real_bot):
    db = real_bot.db
    guild_id = 123
    target_id = 456
    creator_id = 789
    scheduled_time = datetime.now() + timedelta(minutes=5)

    reminder_id = await db.add_reminder(
        guild_id=guild_id,
        target_discord_id=target_id,
        creator_discord_id=creator_id,
        scheduled_time=scheduled_time,
        reason="Test",
        shock_type="Shock",
        intensity=42,
        duration=1000,
        channel_id=None,
        is_recurring=False,
        recurrence_pattern=None,
    )

    assert isinstance(reminder_id, int) and reminder_id > 0

    got = await db.get_reminder(reminder_id, guild_id)
    assert got is not None
    assert got["target_discord_id"] == target_id
    assert got["creator_discord_id"] == creator_id
    assert int(got["intensity"]) == 42


@pytest.mark.asyncio
async def test_pending_and_complete_reminder_async(real_bot):
    db = real_bot.db
    guild_id = 222
    target_id = 333
    creator_id = 444

    # Past-due reminder
    past_id = await db.add_reminder(
        guild_id=guild_id,
        target_discord_id=target_id,
        creator_discord_id=creator_id,
        scheduled_time=datetime.now() - timedelta(minutes=1),
        reason=None,
        shock_type="Shock",
        intensity=10,
        duration=500,
    )
    # Future reminder
    _future_id = await db.add_reminder(
        guild_id=guild_id,
        target_discord_id=target_id,
        creator_discord_id=creator_id,
        scheduled_time=datetime.now() + timedelta(minutes=10),
        reason=None,
        shock_type="Shock",
        intensity=10,
        duration=500,
    )

    pending = await db.get_pending_reminders()
    pending_ids = {r["id"] for r in pending}
    assert past_id in pending_ids
    assert all(r["guild_id"] in (guild_id,) for r in pending)  # sanity

    # Mark completed
    ok = await db.mark_reminder_completed(past_id)
    assert ok

    pending2 = await db.get_pending_reminders()
    # Should no longer include the completed reminder
    assert all(r["id"] != past_id for r in pending2)


@pytest.mark.asyncio
async def test_delete_reminder_async(real_bot):
    db = real_bot.db
    guild_id = 999
    target_id = 111
    creator_id = 222

    rid = await db.add_reminder(
        guild_id=guild_id,
        target_discord_id=target_id,
        creator_discord_id=creator_id,
        scheduled_time=datetime.now() + timedelta(minutes=2),
        reason="delete-me",
        shock_type="Shock",
        intensity=15,
        duration=750,
    )

    got = await db.get_reminder(rid, guild_id)
    assert got is not None

    deleted = await db.delete_reminder(rid, guild_id)
    assert deleted

    got2 = await db.get_reminder(rid, guild_id)
    assert got2 is None

