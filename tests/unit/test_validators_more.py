import disnake
import pytest

from botshock.utils.validators import ReminderValidator, ShockValidator, TriggerValidator


class FakePermissionChecker:
    def __init__(self, allow=True, reason="not_allowed"):
        self.allow = allow
        self.reason = reason

    async def can_manage_user(self, author, target):
        return self.allow, self.reason

    @staticmethod
    async def get_permission_error_message(reason, target, guild):
        return f"DENIED: {reason}"


class FakeDB:
    def __init__(self, registered=True, shockers=None, device_worn=True):
        self.registered = registered
        self._shockers = shockers or []
        self.device_worn = device_worn

    async def get_user(self, user_id, guild_id):
        return {"id": user_id} if self.registered else None

    async def get_shockers(self, user_id, guild_id):
        return list(self._shockers)

    async def get_device_worn_status(self, user_id, guild_id):
        return self.device_worn


@pytest.mark.asyncio
async def test_reminder_validator_permission_denied():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "s1"}])
    perms = FakePermissionChecker(allow=False, reason="no_consent")
    v = ReminderValidator(db, perms)
    ok, msg = await v.validate_reminder_creation(disnake.Object(id=1), disnake.Object(id=2), 123)
    assert not ok and "DENIED" in msg


@pytest.mark.asyncio
async def test_reminder_validator_not_registered():
    db = FakeDB(registered=False)
    perms = FakePermissionChecker(allow=True)
    v = ReminderValidator(db, perms)
    ok, msg = await v.validate_reminder_creation(disnake.Object(id=1), disnake.Object(id=2), 123)
    assert not ok and "not registered" in msg.lower()


@pytest.mark.asyncio
async def test_reminder_validator_no_shockers():
    db = FakeDB(registered=True, shockers=[])
    perms = FakePermissionChecker(allow=True)
    v = ReminderValidator(db, perms)
    ok, msg = await v.validate_reminder_creation(disnake.Object(id=1), disnake.Object(id=2), 123)
    assert not ok and "no shockers" in msg.lower()


@pytest.mark.asyncio
async def test_reminder_validator_success():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "s1"}])
    perms = FakePermissionChecker(allow=True)
    v = ReminderValidator(db, perms)
    ok, msg = await v.validate_reminder_creation(disnake.Object(id=1), disnake.Object(id=2), 123)
    assert ok and msg is None


@pytest.mark.asyncio
async def test_shock_validator_specific_shocker():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "a"}, {"shocker_id": "b"}])
    perms = FakePermissionChecker(allow=True)
    v = ShockValidator(db, perms)
    ok, msg, target_user, shocker = await v.validate_shock_request(
        disnake.Object(id=1), disnake.Object(id=2), 123, shocker_id="b"
    )
    assert ok and shocker and shocker["shocker_id"] == "b"
    assert target_user is not None


@pytest.mark.asyncio
async def test_shock_validator_specific_not_found():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "a"}])
    perms = FakePermissionChecker(allow=True)
    v = ShockValidator(db, perms)
    ok, msg, target_user, shocker = await v.validate_shock_request(
        disnake.Object(id=1), disnake.Object(id=2), 123, shocker_id="zzz"
    )
    assert not ok and "not found" in msg.lower()


@pytest.mark.asyncio
async def test_trigger_validator_regex_invalid():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "a"}])
    perms = FakePermissionChecker(allow=True)
    v = TriggerValidator(db, perms)
    ok, msg = await v.validate_trigger_creation(
        disnake.Object(id=1), disnake.Object(id=2), 123, regex_pattern="[unclosed"
    )
    assert not ok and "invalid regex" in msg.lower()


@pytest.mark.asyncio
async def test_trigger_validator_success():
    db = FakeDB(registered=True, shockers=[{"shocker_id": "a"}])
    perms = FakePermissionChecker(allow=True)
    v = TriggerValidator(db, perms)
    ok, msg = await v.validate_trigger_creation(
        disnake.Object(id=1), disnake.Object(id=2), 123, regex_pattern=r"^ok$"
    )
    assert ok and msg is None
