"""
Protocol describing the attributes and minimal methods our cogs expect on the bot instance.
This helps static type checkers/IDEs understand dynamically-attached attributes like `.db`,
`.formatter`, `.permission_checker`, `.command_helper`, and `.trigger_manager`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SupportsBotAttrs(Protocol):
    db: Any
    formatter: Any
    permission_checker: Any
    command_helper: Any
    trigger_manager: Any

    # Methods used by some cogs
    async def wait_for(
        self, event: str, check: Callable[[Any], bool] | None = ..., timeout: float | None = ...
    ) -> Any: ...

    def get_guild(self, guild_id: int) -> Any: ...

    # Optional: interaction/client-like lifecycle methods used elsewhere
    async def wait_until_ready(self) -> None: ...

    # Additional helpers exposed by our bot subclass and used across cogs
    def get_api_client(self) -> Any: ...

    async def fetch_user(self, user_id: int) -> Any: ...
