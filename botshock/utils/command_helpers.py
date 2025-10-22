"""
Command helper functions to reduce code redundancy across cogs
"""

import logging
from datetime import datetime

import disnake

from botshock.utils.response_handler import ResponseHandler

logger = logging.getLogger("BotShock.CommandHelpers")


class CommandHelper:
    """Helper functions for common command operations"""

    def __init__(self, db, permission_checker, formatter):
        self.db = db
        self.permission_checker = permission_checker
        self.formatter = formatter
        self.response_handler = ResponseHandler(formatter)

    async def add_shockers_bulk(
        self,
        inter: disnake.Interaction,
        user_id: int,
        guild_id: int,
        selected_ids: list[str],
        lookup_list: list[dict],
        *,
        log_prefix: str = "",
    ) -> tuple[int, int, list[str]]:
        """
        Add multiple shockers for a user, returning (added_count, failed_count, added_names)

        Args:
            inter: The interaction (for logging guild context)
            user_id: Discord user ID
            guild_id: Guild ID
            selected_ids: Selected shocker IDs to add
            lookup_list: Source list containing objects with 'id' and optional 'name'
            log_prefix: Optional prefix string for log messages
        """
        added_count = 0
        failed_count = 0
        added_names: list[str] = []

        # Build a quick lookup map for id -> name
        name_map = {}
        for s in lookup_list:
            sid = s.get("id") or s.get("shocker_id")
            if sid:
                name_map[sid] = s.get("name") or s.get("shocker_name") or None

        for shocker_id in selected_ids:
            shocker_name = name_map.get(shocker_id)
            success = await self.db.add_shocker(
                discord_id=user_id,
                guild_id=guild_id,
                shocker_id=shocker_id,
                shocker_name=shocker_name,
            )

            if success:
                added_count += 1
                added_names.append(shocker_name or shocker_id[:8])
                logger.info(
                    f"{log_prefix}Shocker added: {shocker_id} ({shocker_name}) for user {user_id} in guild {guild_id}"
                )
            else:
                failed_count += 1

        return added_count, failed_count, added_names

    async def ensure_selection(
        self,
        inter: disnake.Interaction,
        selected: list,
        *,
        view: disnake.ui.View | None = None,
        include_skip_hint: bool = False,
    ) -> bool:
        """
        Ensure a non-empty selection exists; otherwise send a standard error embed.

        Args:
            inter: The interaction to edit (MessageInteraction or ApplicationCommandInteraction)
            selected: The current selection list
            view: Optional view to preserve on error
            include_skip_hint: Whether to include the Skip hint text

        Returns:
            True if selection is non-empty; False after sending an error embed otherwise
        """
        if selected:
            return True

        hint = (
            "Please select at least one shocker from the dropdown menu, or click **Skip for Now**."
            if include_skip_hint
            else "Please select at least one shocker from the dropdown menu."
        )
        embed = self.formatter.error_embed("No Selection", hint)
        # Try both edit_original_response and edit_original_message based on interaction type
        try:
            await inter.edit_original_response(embed=embed, view=view)
        except Exception:
            try:
                await inter.edit_original_message(embed=embed, view=view)
            except Exception:
                # As a last resort, send a followup if editing fails
                await inter.followup.send(embed=embed, ephemeral=True)
        return False

    async def check_and_respond_permission(
        self,
        inter: disnake.ApplicationCommandInteraction,
        author: disnake.User,
        target: disnake.User,
    ) -> tuple[bool, str | None]:
        """
        Check permissions and send error response if denied

        Args:
            inter: The interaction
            author: The user executing the command
            target: The target user

        Returns:
            Tuple of (has_permission, reason)
        """
        can_manage, reason = await self.permission_checker.can_manage_user(author, target)

        if not can_manage:
            error_msg = await self.permission_checker.get_permission_error_message(
                reason, target, inter.guild
            )
            embed = self.formatter.error_embed("Permission Denied", error_msg)
            await inter.edit_original_response(embed=embed)
            logger.warning(
                f"Permission denied: {author} ({author.id}) -> {target} ({target.id}) "
                f"in guild {inter.guild.id}, reason: {reason}"
            )
            return False, reason

        return True, reason

    async def check_permission_with_logging(
        self,
        inter: disnake.ApplicationCommandInteraction,
        author: disnake.User,
        target: disnake.User,
        action: str = "perform action",
    ) -> bool:
        """
        Check permissions, send error response if denied, and log the attempt

        Args:
            inter: The interaction
            author: The user executing the command
            target: The target user
            action: Description of the action being attempted (for logging)

        Returns:
            True if permission is granted, False otherwise
        """
        can_manage, reason = await self.permission_checker.can_manage_user(author, target)

        if not can_manage:
            error_msg = await self.permission_checker.get_permission_error_message(
                reason, target, inter.guild
            )
            embed = self.formatter.error_embed("Permission Denied", error_msg)
            await inter.edit_original_response(embed=embed)
            logger.warning(
                f"Permission denied: {author} ({author.id}) tried to {action} for "
                f"{target} ({target.id}) in guild {inter.guild.id} - Reason: {reason}"
            )
            return False

        return True

    @staticmethod
    def resolve_target_user(
        user: disnake.User | None, default_user: disnake.User
    ) -> disnake.User:
        """
        Resolve target user, defaulting to the command author if not specified

        Args:
            user: Optional user parameter
            default_user: Default user (usually inter.author)

        Returns:
            The resolved user
        """
        return user if user else default_user

    # ...existing code...

    async def send_success_with_log(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        log_message: str,
        **kwargs,
    ):
        """
        Send success embed and log the action.
        DEPRECATED: Use response_handler.send_success() instead.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            log_message: Message to log
            **kwargs: Additional fields for embed
        """
        await self.response_handler.send_success(
            inter, title, description, log_message=log_message, **kwargs
        )

    async def send_error_with_log(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        log_message: str,
        **kwargs,
    ):
        """
        Send error embed and log the error.
        DEPRECATED: Use response_handler.send_error() instead.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            log_message: Message to log
            **kwargs: Additional fields for embed
        """
        await self.response_handler.send_error(
            inter, title, description, log_message=log_message, **kwargs
        )

    async def check_user_registered(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_id: int,
        guild_id: int,
        send_response: bool = True,
    ) -> tuple[bool, dict | None]:
        """
        Check if a user is registered and optionally send error response

        Args:
            inter: The interaction
            user_id: User ID to check
            guild_id: Guild ID
            send_response: Whether to send error response if not registered

        Returns:
            Tuple of (is_registered, user_data)
        """
        user_data = await self.db.get_user(user_id, guild_id)

        if not user_data and send_response:
            embed = self.formatter.error_embed(
                "Not Registered",
                "You need to register your device first before using this command!",
                field_1=(
                    "Next Steps",
                    "Use `/openshock setup` to set up your API token and device.",
                ),
            )
            await inter.edit_original_response(embed=embed)

        return user_data is not None, user_data

    async def require_user_registered(
        self, inter: disnake.ApplicationCommandInteraction, user_id: int, guild_id: int
    ) -> dict | None:
        """
        Require user to be registered, send error if not, return user_data or None

        Args:
            inter: The interaction
            user_id: User ID to check
            guild_id: Guild ID

        Returns:
            User data dict if registered, None otherwise (error already sent)
        """
        is_registered, user_data = await self.check_user_registered(
            inter, user_id, guild_id, send_response=True
        )
        return user_data if is_registered else None

    @staticmethod
    async def defer_response(inter: disnake.ApplicationCommandInteraction, ephemeral: bool = True):
        """
        Safely defer a response

        Args:
            inter: The interaction
            ephemeral: Whether response should be ephemeral
        """
        try:
            await inter.response.defer(ephemeral=ephemeral)
        except Exception as e:
            logger.warning(f"Failed to defer response: {e}")

    @staticmethod
    async def wait_for_modal(
        bot, modal_id: str, author_id: int, timeout: int = 300
    ) -> disnake.ModalInteraction | None:
        """
        Wait for a modal submission

        Args:
            bot: Bot instance
            modal_id: Custom ID of the modal
            author_id: Expected author ID
            timeout: Timeout in seconds

        Returns:
            ModalInteraction if successful, None if timeout/error
        """
        try:
            modal_inter = await bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == modal_id and i.author.id == author_id,
                timeout=timeout,
            )
            return modal_inter
        except Exception as e:
            logger.debug(f"Modal wait failed: {e}")
            return None

    @staticmethod
    async def handle_button_confirmation(
        bot, inter: disnake.ApplicationCommandInteraction, timeout: int = 30
    ) -> disnake.MessageInteraction | None:
        """
        Wait for button confirmation from the command author

        Args:
            bot: Bot instance
            inter: Original interaction
            timeout: Timeout in seconds

        Returns:
            Button interaction if clicked, None if timeout
        """
        # Try to get the ID of the original response message (works for ephemeral too)
        message_id: int | None
        try:
            original_message = await inter.original_message()
            message_id = original_message.id
        except Exception:
            # Fallback: we couldn't resolve the original message (e.g., not yet sent)
            message_id = None

        def check_button(i: disnake.MessageInteraction) -> bool:
            same_author = i.author.id == inter.author.id
            if message_id is None:
                # Without a message to compare, rely on author match only
                return same_author
            return same_author and i.message.id == message_id

        try:
            button_inter = await bot.wait_for("button_click", check=check_button, timeout=timeout)
            return button_inter
        except Exception:
            return None

    async def get_controllable_users_or_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        controller_id: int,
        guild_id: int,
        controller_role_ids: list,
    ) -> list | None:
        """
        Get controllable users for a controller, send error if none

        Args:
            inter: The interaction
            controller_id: Controller's user ID
            guild_id: Guild ID
            controller_role_ids: List of role IDs the controller has

        Returns:
            List of controllable user IDs or None (error sent)
        """
        controllable = await self.db.get_controllable_users(
            controller_id, guild_id, controller_role_ids
        )

        if not controllable:
            embed = self.formatter.error_embed(
                "No Permissions",
                "You don't have permission to control any users.",
                field_1=(
                    "Need Permission?",
                    "Ask a user to grant you control with `/controllers add`",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return None

        return controllable

    def format_time_remaining(self, seconds: int) -> str:
        """
        Format seconds into human-readable time string using shared formatter
        """
        # Delegate to the shared formatter to avoid duplication
        try:
            return self.formatter.format_duration(int(seconds))
        except Exception:
            # Fallback simple formatting
            seconds = int(seconds)
            if seconds < 60:
                return f"{seconds}s"
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if minutes < 60:
                return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
            hours = minutes // 60
            remaining_minutes = minutes % 60
            return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"

    async def check_shocker_cooldown_with_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_id: int,
        guild_id: int,
        shocker_id: str,
        shocker_name: str,
        user_mention: str,
        cooldown_seconds: int = 60,
    ) -> bool:
        """
        Check shocker cooldown and send error if on cooldown

        Args:
            inter: The interaction
            user_id: User ID
            guild_id: Guild ID
            shocker_id: Shocker ID
            shocker_name: Display name for shocker
            user_mention: Mention string for user
            cooldown_seconds: Cooldown period

        Returns:
            True if ready, False if on cooldown (error sent)
        """
        is_ready = await self.db.check_shocker_cooldown(
            user_id, guild_id, shocker_id, cooldown_seconds
        )

        if not is_ready:
            embed = self.formatter.error_embed(
                "Cooldown Active",
                f"The shocker for {user_mention} is on cooldown. Please wait before sending another shock.",
                field_1=(
                    "Why?",
                    "Cooldowns prevent excessive shocking and protect device hardware.",
                ),
            )
            await inter.edit_original_response(embed=embed, view=None)
            return False

        return True

    async def check_controller_cooldown_with_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        controller_id: int,
        target_id: int,
        guild_id: int,
        user_mention: str,
    ) -> bool:
        """
        Check controller cooldown and send error if on cooldown

        Args:
            inter: The interaction
            controller_id: Controller's user ID
            target_id: Target user ID
            guild_id: Guild ID
            user_mention: Mention string for target user

        Returns:
            True if ready, False if on cooldown (error sent)
        """
        cooldown_duration = await self.db.get_controller_cooldown_duration(target_id, guild_id)
        controller_ready, seconds_remaining = await self.db.check_controller_cooldown(
            controller_id, target_id, guild_id, cooldown_seconds=cooldown_duration
        )

        if not controller_ready:
            time_str = self.format_time_remaining(seconds_remaining)
            embed = self.formatter.error_embed(
                "Controller Cooldown Active",
                f"You need to wait **{time_str}** before you can control {user_mention} again.",
                field_1=(
                    "Rate Limiting",
                    f"Controllers have a {cooldown_duration // 60} minute cooldown between actions to ensure responsible use.",
                ),
            )
            await inter.edit_original_response(embed=embed, view=None)
            return False

        return True

    @staticmethod
    def create_shocker_select_options(shockers: list, max_options: int = 25) -> list:
        """
        Create select options from shocker list

        Args:
            shockers: List of shocker dicts
            max_options: Maximum number of options (Discord limit)

        Returns:
            List of SelectOption objects
        """
        options = []
        for shocker in shockers[:max_options]:
            status = "⏸️ Paused" if shocker.get("isPaused", False) else "✅ Online"
            name = shocker.get("name") or shocker.get("shocker_name") or "Unnamed"
            shocker_id = shocker.get("id") or shocker.get("shocker_id", "")

            # Truncate for Discord limits
            label = f"{name} ({status})"[:100]
            desc = f"ID: {shocker_id[:30]}..." if len(shocker_id) > 30 else f"ID: {shocker_id}"

            options.append(
                disnake.SelectOption(label=label, value=shocker_id, description=desc, emoji="🔌")
            )
        return options

    async def auto_select_target_user(
        self,
        inter: disnake.ApplicationCommandInteraction,
        controller_id: int,
        guild_id: int,
        controller_role_ids: list,
    ) -> disnake.User | None:
        """
        Auto-select target user if controller only controls one person

        Args:
            inter: The interaction
            controller_id: Controller's user ID
            guild_id: Guild ID
            controller_role_ids: List of role IDs

        Returns:
            Auto-selected user or None (error sent if needed)
        """
        controllable = await self.get_controllable_users_or_error(
            inter, controller_id, guild_id, controller_role_ids
        )

        if controllable is None:
            return None

        if len(controllable) == 1:
            user = await inter.bot.fetch_user(controllable[0])
            logger.info(f"Auto-selected target user {user.name} for controller {inter.author.name}")
            return user
        else:
            embed = self.formatter.error_embed(
                "Target Required",
                f"You can control {len(controllable)} users. Please specify which one:",
                field_1=("Tip", "Use the `user` parameter to select your target."),
            )
            await inter.edit_original_response(embed=embed)
            return None

    async def validate_and_get_shocker(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_id: int,
        guild_id: int,
        shocker_id: str | None = None,
    ) -> dict | None:
        """
        Validate user has shockers and get specific shocker or handle selection

        Args:
            inter: The interaction
            user_id: Target user ID
            guild_id: Guild ID
            shocker_id: Specific shocker ID (optional)

        Returns:
            Selected shocker dict or None
        """
        shockers = await self.db.get_shockers(user_id, guild_id)

        if not shockers:
            return None

        if shocker_id:
            # Find specific shocker
            return next((s for s in shockers if s["shocker_id"] == shocker_id), None)
        elif len(shockers) == 1:
            # Auto-select if only one
            return shockers[0]
        else:
            # Multiple shockers - caller needs to handle selection
            return None

    @staticmethod
    def build_action_log_entry(log: dict) -> tuple[str, str]:
        """
        Build formatted action log entry for embeds

        Args:
            log: Log dict from database

        Returns:
            Tuple of (field_name, field_value) for embed
        """
        timestamp = datetime.fromisoformat(log["timestamp"])
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        action_details = []
        if log.get("shock_type"):
            action_details.append(f"Type: {log['shock_type']}")
        if log.get("intensity"):
            action_details.append(f"Intensity: {log['intensity']}%")
        if log.get("duration"):
            action_details.append(f"Duration: {log['duration']}ms")
        if log.get("shocker_name"):
            action_details.append(f"Device: {log['shocker_name']}")

        status_emoji = "✅" if log.get("success") else "❌"
        source_text = f"via {log['source']}" if log.get("source") else ""

        field_name = f"{status_emoji} {timestamp_str} {source_text}"
        field_value = f"**Controller:** {log.get('controller_username', 'Unknown')}\n"

        if action_details:
            field_value += "**Details:** " + " • ".join(action_details) + "\n"

        if not log.get("success") and log.get("error_message"):
            error_short = log["error_message"][:100]
            field_value += f"**Error:** {error_short}\n"

        return field_name, field_value
