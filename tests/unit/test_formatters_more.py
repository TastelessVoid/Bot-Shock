import disnake
import pytest

from botshock.utils.formatters import ResponseFormatter


class TestResponseFormatterEmbeds:
    def test_success_embed_with_fields(self):
        embed = ResponseFormatter.success_embed(
            "Operation Complete",
            "Everything worked",
            field_1=("A", "B"),
            field_2=("C", "D"),
        )
        assert isinstance(embed, disnake.Embed)
        assert embed.title == "✅ Operation Complete"
        assert embed.description == "Everything worked"
        assert embed.color.value == ResponseFormatter.COLOR_SUCCESS
        assert len(embed.fields) == 2
        assert embed.fields[0].name == "A"
        assert embed.fields[0].value == "B"

    def test_error_info_warning_embeds(self):
        err = ResponseFormatter.error_embed("Oops", "Something broke")
        inf = ResponseFormatter.info_embed("Heads up", "FYI")
        warn = ResponseFormatter.warning_embed("Careful", "Be cautious")

        assert err.title.startswith("❌ ")
        assert inf.title.startswith("ℹ️ ")
        assert warn.title.startswith("⚠️ ")
        assert err.color.value == ResponseFormatter.COLOR_ERROR
        assert inf.color.value == ResponseFormatter.COLOR_INFO
        assert warn.color.value == ResponseFormatter.COLOR_WARNING

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (5, "5s"),
            (60, "1m"),
            (75, "1m 15s"),
            (3600, "1h"),
            (3660, "1h 1m"),
        ],
    )
    def test_format_duration(self, seconds, expected):
        assert ResponseFormatter.format_duration(seconds) == expected

    def test_format_shocker_list_empty_vs_nonempty(self):
        empty = ResponseFormatter.format_shocker_list([])
        assert "No shockers" in (empty.description or "")

        shockers = [
            {"shocker_id": "abc123", "shocker_name": "My Device"},
            {"shocker_id": "xyz789", "shocker_name": None},
        ]
        nonempty = ResponseFormatter.format_shocker_list(shockers)
        # Should produce two fields for two shockers
        assert len(nonempty.fields) == 2
        assert "abc123" in nonempty.fields[0].value
