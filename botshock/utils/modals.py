"""
Base modal classes to reduce code duplication across cogs.

This module provides reusable modal templates with standardized components
and validation patterns.
"""

import disnake


class BotShockModal(disnake.ui.Modal):
    """
    Base modal class for BotShock with consistent styling and validation.

    This class provides a foundation for creating modals with standard
    BotShock formatting and component patterns.
    """

    def __init__(
        self,
        title: str,
        components: list,
        custom_id: str | None = None,
    ):
        """
        Initialize a BotShock modal.

        Args:
            title: Modal title (shown to user)
            components: List of disnake.ui.TextInput components
            custom_id: Optional custom ID (auto-generated if None)
        """
        super().__init__(
            title=title,
            components=components,
            custom_id=custom_id or f"modal_{title.lower().replace(' ', '_')}",
        )

    @staticmethod
    def create_text_input(
        label: str,
        custom_id: str,
        placeholder: str = "",
        style: int = 1,
        required: bool = True,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> disnake.ui.TextInput:
        """
        Factory method to create a standardized text input.

        Args:
            label: Input label
            custom_id: Unique identifier for this input
            placeholder: Placeholder text
            style: Input style (short, paragraph, etc.)
            required: Whether the field is required
            min_length: Minimum length
            max_length: Maximum length

        Returns:
            Configured TextInput component
        """
        return disnake.ui.TextInput(
            label=label,
            placeholder=placeholder,
            custom_id=custom_id,
            style=int(style),  # type: ignore
            min_length=min_length,
            max_length=max_length,
            required=required,
        )


class APITokenModal(BotShockModal):
    """Modal for registering OpenShock API token"""

    def __init__(self):
        components = [
            BotShockModal.create_text_input(
                label="OpenShock API Token",
                custom_id="api_token",
                placeholder="kUtJ4rPbDkSRzfVk8nYi2Mo...",
                min_length=10,
                max_length=200,
                required=True,
            ),
            BotShockModal.create_text_input(
                label="Custom API Server (optional)",
                custom_id="api_server",
                placeholder="https://api.openshock.app",
                required=False,
            ),
        ]
        super().__init__(
            title="Register OpenShock API Token",
            components=components,
            custom_id="register_modal",
        )



class TriggerModal(BotShockModal):
    """Modal for adding a regex trigger"""

    def __init__(self, for_user: str = "yourself"):
        components = [
            BotShockModal.create_text_input(
                label="Trigger Name",
                custom_id="trigger_name",
                placeholder="My Trigger",
                required=False,
            ),
            BotShockModal.create_text_input(
                label="Regex Pattern (case-insensitive)",
                custom_id="regex_pattern",
                placeholder="bad word|naughty phrase",
                required=True,
            ),
        ]
        super().__init__(
            title=f"Add Trigger for {for_user}",
            components=components,
            custom_id="add_trigger_modal",
        )


class ConfirmationModal(BotShockModal):
    """Modal for user confirmation with custom message"""

    def __init__(self, title: str = "Confirm Action", prompt: str = "Are you sure?"):
        components = [
            BotShockModal.create_text_input(
                label="Confirmation",
                custom_id="confirmation",
                placeholder=f"Type 'CONFIRM' to proceed",
                style=1,  # short text input
                required=True,
                min_length=7,
                max_length=7,
            ),
        ]
        super().__init__(
            title=title,
            components=components,
            custom_id="confirmation_modal",
        )

