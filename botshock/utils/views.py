"""
Base view classes to reduce code duplication across cogs
"""


import disnake

# Default error message for unauthorized interactions
DEFAULT_UNAUTHORIZED_MESSAGE = "You cannot use this interaction."


class AuthorOnlyView(disnake.ui.View):
    """
    Base view that only allows the original author to interact.

    This view enforces author-only access with an optional custom error message.
    """

    def __init__(
        self,
        author_id: int,
        error_message: str = DEFAULT_UNAUTHORIZED_MESSAGE,
        timeout: float = 180,
    ):
        """
        Initialize the author-only view.

        Args:
            author_id: The ID of the user who can interact with this view
            error_message: Custom message shown when unauthorized users try to interact
            timeout: Timeout for the view in seconds
        """
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.error_message = error_message

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> bool:
        """Ensure only the original author can use this view"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(self.error_message, ephemeral=True)
            return False
        return True


# Backward compatibility alias
AuthorOnlyViewWithCustomMessage = AuthorOnlyView


class ShockerSelectView(AuthorOnlyView):
    """Reusable select view for choosing one or more shockers"""

    def __init__(
        self,
        shockers: list,
        author_id: int | None = None,
        multi_select: bool = False,
        timeout: float = 180,
        placeholder: str = "Select shocker(s)...",
    ):
        super().__init__(author_id or 0, timeout=timeout) if author_id else disnake.ui.View.__init__(self, timeout=timeout)  # type: ignore
        # Selected values
        self.selected_id: str | None = None
        self.selected_ids: list[str] = []
        # Back-compat alias used by some cogs
        self.selected_shockers: list[str] = self.selected_ids

        options = []
        for s in shockers[:25]:
            # Prefer friendly names if present
            name = s.get("name") or s.get("shocker_name") or "Unnamed"
            shocker_id = s.get("id") or s.get("shocker_id") or ""
            status = "⏸️ Paused" if s.get("isPaused", False) else "✅ Online"

            label = f"{name} ({status})"
            label = label[:100]  # Discord label limit
            desc = f"ID: {shocker_id[:30]}..." if len(shocker_id) > 30 else f"ID: {shocker_id}"

            options.append(
                disnake.SelectOption(
                    label=label, value=str(shocker_id), description=desc, emoji="🔌"
                )
            )

        # Use StringSelect with consistent custom_id for compatibility
        min_values = 1
        max_values = len(options) if multi_select else 1
        self.shocker_select = disnake.ui.StringSelect(
            placeholder=placeholder,
            options=options,
            min_values=min_values,
            max_values=max_values,
            custom_id="shocker_select",
        )
        self.shocker_select.callback = self._on_select
        self.add_item(self.shocker_select)

    async def _on_select(self, interaction: disnake.MessageInteraction):
        """Handle selection and store chosen IDs"""
        # Defer quickly to avoid "interaction failed"
        await interaction.response.defer()
        values = getattr(interaction, "values", []) or []
        self.selected_ids = [str(v) for v in values]
        self.selected_shockers = self.selected_ids  # keep alias updated
        self.selected_id = self.selected_ids[0] if self.selected_ids else None
