import pytest

from botshock.utils.command_helpers import CommandHelper
from botshock.utils.formatters import ResponseFormatter


class FakeDB:
    def __init__(self, succeed_for=None):
        self.succeed_for = set(succeed_for or [])
        self.calls = []

    async def add_shocker(self, discord_id, guild_id, shocker_id, shocker_name=None):
        self.calls.append((discord_id, guild_id, shocker_id, shocker_name))
        return shocker_id in self.succeed_for


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, embed=None, ephemeral=None, **kwargs):
        self.sent.append((embed, ephemeral, kwargs))


class FakeInteraction:
    def __init__(self, edit_resp_ok=True, edit_msg_ok=True):
        self.edited_resp = None
        self.edited_msg = None
        self.edit_resp_ok = edit_resp_ok
        self.edit_msg_ok = edit_msg_ok
        self.followup = FakeFollowup()

    async def edit_original_response(self, embed=None, view=None, **kwargs):
        if not self.edit_resp_ok:
            raise RuntimeError("edit_original_response failed")
        self.edited_resp = (embed, view, kwargs)

    async def edit_original_message(self, embed=None, view=None, **kwargs):
        if not self.edit_msg_ok:
            raise RuntimeError("edit_original_message failed")
        self.edited_msg = (embed, view, kwargs)


@pytest.mark.asyncio
async def test_add_shockers_bulk_with_name_map_variants():
    formatter = ResponseFormatter()
    db = FakeDB(succeed_for={"a", "c"})
    helper = CommandHelper(db=db, permission_checker=None, formatter=formatter)

    # Variant 1: objects with 'id' and 'name'
    lookup1 = [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}]
    added, failed, names = await helper.add_shockers_bulk(
        inter=None,
        user_id=1,
        guild_id=2,
        selected_ids=["a", "b"],
        lookup_list=lookup1,
        log_prefix="Test - ",
    )
    assert added == 1 and failed == 1
    assert names == ["Alpha"]  # only success names are returned

    # Variant 2: objects with 'shocker_id' and 'shocker_name' (including None fallback)
    lookup2 = [
        {"shocker_id": "c", "shocker_name": None},
        {"shocker_id": "d", "shocker_name": "Delta"},
    ]
    added2, failed2, names2 = await helper.add_shockers_bulk(
        inter=None,
        user_id=3,
        guild_id=4,
        selected_ids=["c", "d"],
        lookup_list=lookup2,
    )
    assert added2 == 1 and failed2 == 1
    # name for 'c' should fall back to prefix of id
    assert names2 == ["c"]


@pytest.mark.asyncio
async def test_ensure_selection_paths():
    helper = CommandHelper(db=None, permission_checker=None, formatter=ResponseFormatter())

    # Non-empty selection returns True and does not attempt edits
    inter1 = FakeInteraction()
    ok = await helper.ensure_selection(inter1, ["something"])
    assert ok is True
    assert inter1.edited_resp is None and inter1.edited_msg is None and inter1.followup.sent == []

    # Empty selection, edit_original_response works
    inter2 = FakeInteraction(edit_resp_ok=True)
    ok = await helper.ensure_selection(inter2, [], view=None)
    assert ok is False and inter2.edited_resp is not None

    # Empty selection, edit_original_response fails, edit_original_message works
    inter3 = FakeInteraction(edit_resp_ok=False, edit_msg_ok=True)
    ok = await helper.ensure_selection(inter3, [], view=None)
    assert ok is False and inter3.edited_msg is not None

    # Both edit methods fail, fallback to followup.send
    inter4 = FakeInteraction(edit_resp_ok=False, edit_msg_ok=False)
    ok = await helper.ensure_selection(inter4, [], view=None)
    assert ok is False and len(inter4.followup.sent) == 1
