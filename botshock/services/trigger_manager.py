"""
Trigger management service for regex-based automatic shocks
"""

import logging
import re
from collections import OrderedDict
from datetime import datetime, timedelta

logger = logging.getLogger("BotShock.TriggerManager")


class LRUCache:
    """Simple LRU cache implementation for compiled regex patterns"""

    def __init__(self, max_size: int = 1000):
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> re.Pattern | None:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, value: re.Pattern):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            self.cache[key] = value
            if len(self.cache) > self.max_size:
                # Remove least recently used
                self.cache.popitem(last=False)


class TriggerManager:
    """Manages regex trigger compilation and matching with caching and memory management"""

    def __init__(self, database, max_cached_guilds: int = 100, cache_ttl_minutes: int = 30):
        self.db = database
        self.trigger_cache: dict[int, dict[int, list[dict]]] = (
            {}
        )  # {guild_id: {user_id: [triggers]}}
        self.guild_last_access: dict[int, datetime] = {}  # Track last access time
        self.regex_cache = LRUCache(max_size=1000)  # Cache compiled regex patterns
        self.max_cached_guilds = max_cached_guilds
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        logger.info(
            f"TriggerManager initialized with max {max_cached_guilds} cached guilds, TTL {cache_ttl_minutes}min"
        )

    def _cleanup_stale_caches(self) -> None:
        """Remove stale guild caches to prevent memory bloat"""
        now = datetime.now()
        stale_guilds = [
            guild_id
            for guild_id, last_access in self.guild_last_access.items()
            if now - last_access > self.cache_ttl
        ]

        for guild_id in stale_guilds:
            if guild_id in self.trigger_cache:
                del self.trigger_cache[guild_id]
            del self.guild_last_access[guild_id]

        if stale_guilds:
            logger.info(f"Cleaned up {len(stale_guilds)} stale guild caches")

        # If still over limit, remove least recently used
        if len(self.trigger_cache) > self.max_cached_guilds:
            sorted_guilds = sorted(self.guild_last_access.items(), key=lambda x: x[1])
            guilds_to_remove = sorted_guilds[: len(self.trigger_cache) - self.max_cached_guilds]
            for guild_id, _ in guilds_to_remove:
                if guild_id in self.trigger_cache:
                    del self.trigger_cache[guild_id]
                del self.guild_last_access[guild_id]
            logger.info(f"Removed {len(guilds_to_remove)} least recently used guild caches")

    def _get_compiled_pattern(self, pattern_str: str) -> re.Pattern | None:
        """Get compiled regex pattern from cache or compile and cache it"""
        cached = self.regex_cache.get(pattern_str)
        if cached:
            return cached

        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            self.regex_cache.put(pattern_str, compiled)
            return compiled
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern_str}': {e}")
            return None

    def load_all_triggers(self) -> None:
        """Load and compile all enabled triggers from all guilds into cache"""
        logger.info("Clearing trigger cache...")
        self.trigger_cache = {}
        self.guild_last_access = {}

    async def load_triggers_for_guild(self, guild_id: int) -> None:
        """Load and compile all enabled triggers for a specific guild into cache"""
        try:
            # Cleanup before loading new guild
            self._cleanup_stale_caches()

            triggers_by_user = await self.db.get_all_enabled_triggers_for_guild(guild_id)

            if guild_id not in self.trigger_cache:
                self.trigger_cache[guild_id] = {}

            self.trigger_cache[guild_id] = {}

            for user_id, triggers in triggers_by_user.items():
                compiled_triggers = []
                for trigger in triggers:
                    pattern = self._get_compiled_pattern(trigger["regex_pattern"])
                    if pattern:
                        compiled_triggers.append(
                            {
                                "id": trigger["id"],
                                "name": trigger["trigger_name"],
                                "pattern": pattern,
                                "pattern_str": trigger["regex_pattern"],  # Store for logging
                                "shock_type": trigger["shock_type"],
                                "intensity": trigger["intensity"],
                                "duration": trigger["duration"],
                                "cooldown_seconds": trigger["cooldown_seconds"],
                                "last_trigger_time": trigger.get("last_trigger_time"),
                            }
                        )

                if compiled_triggers:
                    self.trigger_cache[guild_id][user_id] = compiled_triggers

            # Update last access time
            self.guild_last_access[guild_id] = datetime.now()

            trigger_count = sum(len(t) for t in self.trigger_cache[guild_id].values())
            logger.info(
                f"Loaded {trigger_count} triggers for {len(self.trigger_cache[guild_id])} "
                f"users in guild {guild_id}"
            )
        except Exception as e:
            logger.error(f"Failed to load triggers for guild {guild_id}: {e}")

    async def check_message(
        self, guild_id: int, user_id: int, message_content: str
    ) -> tuple[bool, dict | None]:
        """
        Check if a message matches any triggers for the user in this guild
        Optimized for performance with caching

        Returns:
            tuple: (matched: bool, trigger_data: Dict or None)
        """
        # Load guild triggers if not cached
        if guild_id not in self.trigger_cache:
            await self.load_triggers_for_guild(guild_id)

        if guild_id not in self.trigger_cache or user_id not in self.trigger_cache[guild_id]:
            return False, None

        # Update last access time
        self.guild_last_access[guild_id] = datetime.now()

        # Optimized: check all patterns for the user
        for trigger in self.trigger_cache[guild_id][user_id]:
            if trigger["pattern"].search(message_content):
                return True, trigger

        return False, None

    async def reload_guild(self, guild_id: int) -> None:
        """Reload triggers for a specific guild"""
        await self.load_triggers_for_guild(guild_id)

    def reload(self) -> None:
        """Reload all triggers from database"""
        self.load_all_triggers()

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring"""
        return {
            "cached_guilds": len(self.trigger_cache),
            "total_triggers": sum(
                len(triggers)
                for guild_triggers in self.trigger_cache.values()
                for triggers in guild_triggers.values()
            ),
            "regex_cache_size": len(self.regex_cache.cache),
            "max_cached_guilds": self.max_cached_guilds,
        }
