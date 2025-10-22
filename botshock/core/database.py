"""
Database module for Bot Shock.

This module provides the Database class which manages an aiosqlite connection pool
and a set of synchronous helpers used by scheduler components. The Database no
longer performs schema initialization synchronously at import time; instead,
callers should await Database.initialize() during application startup.
"""

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta

import aiosqlite

from botshock.utils.encryption import EncryptionHandler

logger = logging.getLogger("BotShock.Database")


class Database:
    """Database handler for BotShock with multi-guild support and async operations.

    Usage:
        db = Database(encryption_key=..., pool_size=5)
        await db.initialize()
    """

    def __init__(
        self, db_path: str = "botshock.db", encryption_key: str = None, pool_size: int = 5
    ):
        self.db_path = db_path
        # Normalize in-memory DB to shared-cache URI so multiple connections see the same schema
        self._use_uri = False
        if self.db_path == ":memory":
            # Accept both ':memory' and ':memory:' corner cases
            self.db_path = ":memory:"
        if self.db_path == ":memory:":
            # Use a named shared in-memory database
            self.db_path = "file:botshock_memdb?mode=memory&cache=shared"
            self._use_uri = True
        elif isinstance(self.db_path, str) and self.db_path.startswith("file:"):
            # It's already a URI; ensure we pass uri=True when connecting
            self._use_uri = True
        # Track if the DB is in-memory (shared) to decide schema init strategy
        self._is_memory = self._use_uri and ("mode=memory" in self.db_path)

        self.encryptor = EncryptionHandler(encryption_key)
        self._connection_pool: list[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._pool_size = pool_size
        self._initialized = False

        # NOTE: initialization (schema creation and pool warmup) is deferred to
        # the asynchronous initialize() method so importing this module is side effect free.

    async def initialize(self):
        """Initialize database schema and create a connection pool.

        This method is idempotent and safe to call multiple times.
        """
        if self._initialized:
            return

        if self._is_memory:
            # Create first async connection and initialize schema to keep the in-memory DB alive
            first_conn = await aiosqlite.connect(self.db_path, uri=self._use_uri)
            first_conn.row_factory = aiosqlite.Row
            await self._init_schema_async(first_conn)
            self._connection_pool.append(first_conn)
            # Create remaining connections
            for _ in range(self._pool_size - 1):
                conn = await aiosqlite.connect(self.db_path, uri=self._use_uri)
                conn.row_factory = aiosqlite.Row
                self._connection_pool.append(conn)
        else:
            # Disk-based DB: create schema synchronously then open pool
            self.init_database()
            for _ in range(self._pool_size):
                conn = await aiosqlite.connect(self.db_path, uri=self._use_uri)
                conn.row_factory = aiosqlite.Row
                self._connection_pool.append(conn)

        self._initialized = True
        logger.info(f"Database initialized with connection pool of {self._pool_size}")

    async def close(self):
        """Close all pooled connections"""
        async with self._pool_lock:
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()
        logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections from pool"""
        if not self._initialized:
            await self.initialize()

        conn = None
        async with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()

        if conn is None:
            # Fallback: create new connection if pool is exhausted
            conn = await aiosqlite.connect(self.db_path, uri=self._use_uri)
            conn.row_factory = aiosqlite.Row
            logger.warning("Connection pool exhausted, creating new connection")

        try:
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            # Return connection to pool
            async with self._pool_lock:
                if len(self._connection_pool) < self._pool_size:
                    self._connection_pool.append(conn)
                else:
                    await conn.close()

    @contextmanager
    def get_connection_sync(self):
        """Synchronous context manager for database connections (used only for initialization)"""
        conn = sqlite3.connect(self.db_path, uri=self._use_uri)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize database tables (synchronous, called once at startup)"""
        with self.get_connection_sync() as conn:
            cursor = conn.cursor()

            # Create guild settings table for per-guild role configuration
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    control_role_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create users table - now includes guild_id for multi-guild support
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    discord_username TEXT NOT NULL,
                    openshock_api_token TEXT NOT NULL,
                    api_server TEXT,
                    device_worn BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(discord_id, guild_id),
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
            """
            )

            # Migration: Add device_worn column if it doesn't exist (for existing databases)
            cursor.execute(
                """
                PRAGMA table_info(users)
                """
            )
            columns = [column[1] for column in cursor.fetchall()]
            if "device_worn" not in columns:
                cursor.execute(
                    """
                    ALTER TABLE users ADD COLUMN device_worn BOOLEAN NOT NULL DEFAULT 1
                    """
                )
                logger.info("Migration: Added device_worn column to users table")

            # Create shockers table - now linked to user-guild pair
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS shockers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    shocker_id TEXT NOT NULL,
                    shocker_name TEXT,
                    last_shock_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, shocker_id)
                )
            """
            )

            # Create controller permissions table - for consent-based control
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_user_id INTEGER NOT NULL,
                    controller_discord_id INTEGER,
                    controller_role_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sub_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CHECK ((controller_discord_id IS NOT NULL AND controller_role_id IS NULL) OR
                           (controller_discord_id IS NULL AND controller_role_id IS NOT NULL))
                )
            """
            )

            # Create controller cooldowns table - track when controllers last used control
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    controller_discord_id INTEGER NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    last_control_time TIMESTAMP NOT NULL,
                    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(controller_discord_id, target_discord_id, guild_id)
                )
            """
            )

            # Create controller action logs table - comprehensive audit trail
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    controller_discord_id INTEGER NOT NULL,
                    controller_username TEXT NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    target_username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    shock_type TEXT,
                    intensity INTEGER,
                    duration INTEGER,
                    shocker_id TEXT,
                    shocker_name TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    source TEXT,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
            """
            )

            # Create triggers table - now linked to user-guild pair
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    trigger_name TEXT,
                    regex_pattern TEXT NOT NULL,
                    shock_type TEXT NOT NULL DEFAULT 'Shock',
                    intensity INTEGER NOT NULL DEFAULT 50,
                    duration INTEGER NOT NULL DEFAULT 1000,
                    cooldown_seconds INTEGER NOT NULL DEFAULT 60,
                    last_trigger_time TIMESTAMP,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            )

            # Create reminders table for scheduled shocks
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    creator_discord_id INTEGER NOT NULL,
                    scheduled_time TIMESTAMP NOT NULL,
                    reason TEXT,
                    shock_type TEXT NOT NULL DEFAULT 'Shock',
                    intensity INTEGER NOT NULL DEFAULT 50,
                    duration INTEGER NOT NULL DEFAULT 1000,
                    channel_id INTEGER,
                    completed BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_recurring BOOLEAN NOT NULL DEFAULT 0,
                    recurrence_pattern TEXT,
                    last_executed TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
            """
            )

            # Create controller preferences table for smart defaults
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    controller_discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    target_discord_id INTEGER,
                    default_intensity INTEGER DEFAULT 30,
                    default_duration INTEGER DEFAULT 1000,
                    default_shock_type TEXT DEFAULT 'Shock',
                    last_used_intensity INTEGER,
                    last_used_duration INTEGER,
                    last_used_shock_type TEXT,
                    last_used_target_id INTEGER,
                    use_smart_defaults BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(controller_discord_id, guild_id, target_discord_id),
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
            """
            )

            # Create indexes for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_discord_guild
                ON users(discord_id, guild_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_shockers_user_id
                ON shockers(user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_sub
                ON controller_permissions(sub_user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_user
                ON controller_permissions(controller_discord_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_role
                ON controller_permissions(controller_role_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triggers_user_id
                ON triggers(user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triggers_enabled
                ON triggers(enabled)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reminders_scheduled
                ON reminders(scheduled_time, completed)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_target
                ON controller_action_logs(target_discord_id, guild_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_controller
                ON controller_action_logs(controller_discord_id, guild_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_timestamp
                ON controller_action_logs(timestamp DESC)
            """
            )

            conn.commit()
            logger.info("Database initialized successfully")

    @staticmethod
    async def _init_schema_async(conn: aiosqlite.Connection) -> None:
        """Initialize database tables using an existing aiosqlite connection (async).
        Mirrors init_database but keeps the in-memory DB alive during schema creation.
        """
        try:
            cursor = await conn.cursor()
            # Create guild settings table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    control_role_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Users table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    discord_username TEXT NOT NULL,
                    openshock_api_token TEXT NOT NULL,
                    api_server TEXT,
                    device_worn BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(discord_id, guild_id),
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
                """
            )
            # Migration: Add device_worn column if it doesn't exist (for existing databases)
            try:
                await cursor.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in await cursor.fetchall()]
                if "device_worn" not in columns:
                    await cursor.execute(
                        "ALTER TABLE users ADD COLUMN device_worn BOOLEAN NOT NULL DEFAULT 1"
                    )
                    logger.info("Migration: Added device_worn column to users table")
            except Exception as e:
                logger.warning(f"Migration check for device_worn column failed (may already exist): {e}")
            # Shockers table
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS shockers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    shocker_id TEXT NOT NULL,
                    shocker_name TEXT,
                    last_shock_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, shocker_id)
                )
                """
            )
            # Controller permissions
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_user_id INTEGER NOT NULL,
                    controller_discord_id INTEGER,
                    controller_role_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sub_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CHECK ((controller_discord_id IS NOT NULL AND controller_role_id IS NULL) OR
                           (controller_discord_id IS NULL AND controller_role_id IS NOT NULL))
                )
                """
            )
            # Controller cooldowns
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    controller_discord_id INTEGER NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    last_control_time TIMESTAMP NOT NULL,
                    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(controller_discord_id, target_discord_id, guild_id)
                )
                """
            )
            # Controller action logs
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    controller_discord_id INTEGER NOT NULL,
                    controller_username TEXT NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    target_username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    shock_type TEXT,
                    intensity INTEGER,
                    duration INTEGER,
                    shocker_id TEXT,
                    shocker_name TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    source TEXT,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
                """
            )
            # Triggers
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    trigger_name TEXT,
                    regex_pattern TEXT NOT NULL,
                    shock_type TEXT NOT NULL DEFAULT 'Shock',
                    intensity INTEGER NOT NULL DEFAULT 50,
                    duration INTEGER NOT NULL DEFAULT 1000,
                    cooldown_seconds INTEGER NOT NULL DEFAULT 60,
                    last_trigger_time TIMESTAMP,
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            # Reminders
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    target_discord_id INTEGER NOT NULL,
                    creator_discord_id INTEGER NOT NULL,
                    scheduled_time TIMESTAMP NOT NULL,
                    reason TEXT,
                    shock_type TEXT NOT NULL DEFAULT 'Shock',
                    intensity INTEGER NOT NULL DEFAULT 50,
                    duration INTEGER NOT NULL DEFAULT 1000,
                    channel_id INTEGER,
                    completed BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_recurring BOOLEAN NOT NULL DEFAULT 0,
                    recurrence_pattern TEXT,
                    last_executed TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
                """
            )
            # Controller preferences
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS controller_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    controller_discord_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    target_discord_id INTEGER,
                    default_intensity INTEGER DEFAULT 30,
                    default_duration INTEGER DEFAULT 1000,
                    default_shock_type TEXT DEFAULT 'Shock',
                    last_used_intensity INTEGER,
                    last_used_duration INTEGER,
                    last_used_shock_type TEXT,
                    last_used_target_id INTEGER,
                    use_smart_defaults BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(controller_discord_id, guild_id, target_discord_id),
                    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
                )
                """
            )
            # Indexes
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_discord_guild
                ON users(discord_id, guild_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_shockers_user_id
                ON shockers(user_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_sub
                ON controller_permissions(sub_user_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_user
                ON controller_permissions(controller_discord_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_controller_permissions_role
                ON controller_permissions(controller_role_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triggers_user_id
                ON triggers(user_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triggers_enabled
                ON triggers(enabled)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reminders_scheduled
                ON reminders(scheduled_time, completed)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_target
                ON controller_action_logs(target_discord_id, guild_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_controller
                ON controller_action_logs(controller_discord_id, guild_id)
                """
            )
            await cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_logs_timestamp
                ON controller_action_logs(timestamp DESC)
                """
            )
            await conn.commit()
            logger.info("Async database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize schema asynchronously: {e}")
            raise

    # Guild Settings Methods

    async def set_guild_control_roles(
        self, guild_id: int, guild_name: str, role_ids: list[int]
    ) -> bool:
        """Set the control role IDs for a guild"""
        try:
            role_ids_str = ",".join(str(rid) for rid in role_ids) if role_ids else ""
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO guild_settings (guild_id, guild_name, control_role_ids)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        guild_name = excluded.guild_name,
                        control_role_ids = excluded.control_role_ids,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (guild_id, guild_name, role_ids_str),
                )
                logger.info(f"Set control roles for guild {guild_name} ({guild_id}): {role_ids}")
                return True
        except Exception as e:
            logger.error(f"Failed to set guild control roles: {e}")
            return False

    async def get_guild_control_roles(self, guild_id: int) -> list[int]:
        """Get the control role IDs for a guild"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT control_role_ids FROM guild_settings WHERE guild_id = ?
                """,
                    (guild_id,),
                )
                row = await cursor.fetchone()
                if row and row["control_role_ids"]:
                    return [int(rid) for rid in row["control_role_ids"].split(",") if rid]
                return []
        except Exception as e:
            logger.error(f"Failed to get guild control roles: {e}")
            return []

    async def get_guild_settings(self, guild_id: int) -> dict | None:
        """Get all settings for a guild"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT guild_id, guild_name, control_role_ids, created_at, updated_at
                    FROM guild_settings WHERE guild_id = ?
                """,
                    (guild_id,),
                )
                row = await cursor.fetchone()
                if row:
                    from typing import Any

                    settings: dict[str, Any] = dict(row)
                    control_roles = settings.get("control_role_ids")
                    if control_roles:
                        settings["control_role_ids"] = [
                            int(rid) for rid in str(control_roles).split(",") if rid
                        ]
                    else:
                        settings["control_role_ids"] = []
                    return settings
                return None
        except Exception as e:
            logger.error(f"Failed to get guild settings: {e}")
            return None

    # Helper methods for time handling

    @staticmethod
    def _parse_db_timestamp(ts: str) -> datetime:
        """Parse a SQLite CURRENT_TIMESTAMP string as a timezone-aware UTC datetime.

        SQLite CURRENT_TIMESTAMP is stored as UTC in the format 'YYYY-MM-DD HH:MM:SS'
        (optionally with microseconds). We treat naive parsed values as UTC.
        """
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            # Fallback parsing
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                # Last resort: replace space with T and try again
                dt = datetime.fromisoformat(ts.replace(" ", "T"))
        # Normalize to UTC-aware
        dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        return dt

    # User Methods (guild-aware)

    async def add_user(
        self,
        discord_id: int,
        guild_id: int,
        discord_username: str,
        api_token: str,
        api_server: str = None,
    ) -> bool:
        """Add or update a user with encrypted API token (guild-specific)"""
        try:
            # Use per-user encryption for enhanced security
            encrypted_token = self.encryptor.encrypt(
                api_token, user_id=discord_id, guild_id=guild_id
            )
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO users (discord_id, guild_id, discord_username, openshock_api_token, api_server)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(discord_id, guild_id) DO UPDATE SET
                        discord_username = excluded.discord_username,
                        openshock_api_token = excluded.openshock_api_token,
                        api_server = excluded.api_server,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (discord_id, guild_id, discord_username, encrypted_token, api_server),
                )
                logger.info(
                    f"Added/updated user: {discord_username} ({discord_id}) in guild {guild_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to add user {discord_id} in guild {guild_id}: {e}")
            return False

    async def get_user(self, discord_id: int, guild_id: int) -> dict | None:
        """Get user by Discord ID and guild ID with decrypted API token"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT id, discord_id, guild_id, discord_username, openshock_api_token, api_server, created_at, updated_at
                    FROM users WHERE discord_id = ? AND guild_id = ?
                """,
                    (discord_id, guild_id),
                )
                row = await cursor.fetchone()
                if row:
                    user_dict = dict(row)
                    # Decrypt the API token with user-specific key
                    user_dict["openshock_api_token"] = self.encryptor.decrypt(
                        user_dict["openshock_api_token"], user_id=discord_id, guild_id=guild_id
                    )
                    return user_dict
                return None
        except Exception as e:
            logger.error(f"Failed to get user {discord_id} in guild {guild_id}: {e}")
            return None

    async def add_shocker(
        self, discord_id: int, guild_id: int, shocker_id: str, shocker_name: str | None = None
    ) -> bool:
        """Add a shocker to a user - shocker IDs are stored in plain text"""
        try:
            # Get user's internal ID
            user = await self.get_user(discord_id, guild_id)
            if not user:
                logger.error(f"Cannot add shocker: user {discord_id} not found in guild {guild_id}")
                return False

            # Shocker IDs are NOT encrypted - they need to be sent to OpenShock API in plain text
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO shockers (user_id, shocker_id, shocker_name)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, shocker_id) DO UPDATE SET
                        shocker_name = excluded.shocker_name
                """,
                    (user["id"], shocker_id, shocker_name),
                )
                logger.info(f"Added shocker for user {discord_id} in guild {guild_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to add shocker for user {discord_id} in guild {guild_id}: {e}")
            return False

    async def remove_shocker(self, discord_id: int, guild_id: int, shocker_id: str) -> bool:
        """Remove a shocker from a user"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            # Shocker IDs are stored in plain text
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    DELETE FROM shockers WHERE user_id = ? AND shocker_id = ?
                """,
                    (user["id"], shocker_id),
                )
                if cursor.rowcount > 0:
                    logger.info(f"Removed shocker for user {discord_id} in guild {guild_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove shocker for user {discord_id} in guild {guild_id}: {e}")
            return False

    async def get_shockers(self, discord_id: int, guild_id: int) -> list[dict]:
        """Get all shockers for a user - shocker IDs are in plain text"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return []

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT id, shocker_id, shocker_name, last_shock_time, created_at
                    FROM shockers WHERE user_id = ?
                    ORDER BY created_at
                """,
                    (user["id"],),
                )
                shockers = []
                async for row in cursor:
                    shocker_dict = dict(row)
                    shockers.append(shocker_dict)
                return shockers
        except Exception as e:
            logger.error(f"Failed to get shockers for user {discord_id} in guild {guild_id}: {e}")
            return []

    async def update_shocker_cooldown(
        self, discord_id: int, guild_id: int, shocker_id: str
    ) -> bool:
        """Update the last shock time for a shocker (global cooldown)"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            # Shocker IDs are stored in plain text
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE shockers SET last_shock_time = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND shocker_id = ?
                """,
                    (user["id"], shocker_id),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update shocker cooldown: {e}")
            return False

    async def check_shocker_cooldown(
        self, discord_id: int, guild_id: int, shocker_id: str, cooldown_seconds: int = 60
    ) -> bool:
        """Check if a shocker is off cooldown (global per-device cooldown)"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            # Shocker IDs are stored in plain text
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT last_shock_time FROM shockers
                    WHERE user_id = ? AND shocker_id = ?
                """,
                    (user["id"], shocker_id),
                )
                row = await cursor.fetchone()

                if not row or not row["last_shock_time"]:
                    return True

                last_time = self._parse_db_timestamp(row["last_shock_time"])  # UTC-aware
                now_utc = datetime.now(UTC)
                time_since = now_utc - last_time

                return time_since.total_seconds() >= cooldown_seconds
        except Exception as e:
            logger.error(f"Failed to check shocker cooldown: {e}")
            return False

    async def add_trigger(
        self,
        discord_id: int,
        guild_id: int,
        regex_pattern: str,
        trigger_name: str | None = None,
        shock_type: str = "Shock",
        intensity: int = 50,
        duration: int = 1000,
        cooldown_seconds: int = 60,
    ) -> int | None:
        """Add a regex trigger for a user with cooldown"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                logger.error(f"Cannot add trigger: user {discord_id} not found in guild {guild_id}")
                return None

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO triggers (user_id, trigger_name, regex_pattern, shock_type, intensity, duration, cooldown_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user["id"],
                        trigger_name,
                        regex_pattern,
                        shock_type,
                        intensity,
                        duration,
                        cooldown_seconds,
                    ),
                )
                trigger_id = cursor.lastrowid
                logger.info(
                    f"Added trigger {trigger_id} for user {discord_id} in guild {guild_id}: {regex_pattern} (cooldown: {cooldown_seconds}s)"
                )
                return trigger_id
        except Exception as e:
            logger.error(f"Failed to add trigger for user {discord_id} in guild {guild_id}: {e}")
            return None

    async def remove_trigger(self, discord_id: int, guild_id: int, trigger_id: int) -> bool:
        """Remove a trigger"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    DELETE FROM triggers WHERE id = ? AND user_id = ?
                """,
                    (trigger_id, user["id"]),
                )
                if cursor.rowcount > 0:
                    logger.info(
                        f"Removed trigger {trigger_id} for user {discord_id} in guild {guild_id}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove trigger {trigger_id}: {e}")
            return False

    async def toggle_trigger(
        self, discord_id: int, guild_id: int, trigger_id: int, enabled: bool
    ) -> bool:
        """Enable or disable a trigger"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE triggers SET enabled = ? WHERE id = ? AND user_id = ?
                """,
                    (enabled, trigger_id, user["id"]),
                )
                if cursor.rowcount > 0:
                    logger.info(
                        f"Toggled trigger {trigger_id} to {enabled} for user {discord_id} in guild {guild_id}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to toggle trigger {trigger_id}: {e}")
            return False

    async def update_trigger_cooldown(self, trigger_id: int) -> bool:
        """Update the last trigger time for a trigger"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE triggers SET last_trigger_time = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (trigger_id,),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update trigger cooldown: {e}")
            return False

    async def check_trigger_cooldown(self, trigger_id: int) -> tuple[bool, int]:
        """
        Check if a trigger is off cooldown

        Returns:
            tuple: (is_ready: bool, seconds_remaining: int)
        """
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT last_trigger_time, cooldown_seconds FROM triggers
                    WHERE id = ?
                """,
                    (trigger_id,),
                )
                row = await cursor.fetchone()

                if not row:
                    return False, 0

                cooldown_seconds = row["cooldown_seconds"]

                if not row["last_trigger_time"]:
                    return True, 0  # Never triggered, ready to go

                last_time = self._parse_db_timestamp(row["last_trigger_time"])  # UTC-aware
                now_utc = datetime.now(UTC)
                seconds_since = (now_utc - last_time).total_seconds()

                if seconds_since >= cooldown_seconds:
                    return True, 0
                else:
                    return False, int(cooldown_seconds - seconds_since)
        except Exception as e:
            logger.error(f"Failed to check trigger cooldown: {e}")
            return False, 0

    async def get_triggers(
        self, discord_id: int, guild_id: int, enabled_only: bool = False
    ) -> list[dict]:
        """Get all triggers for a user"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return []

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                if enabled_only:
                    await cursor.execute(
                        """
                        SELECT id, trigger_name, regex_pattern, shock_type, intensity, duration,
                               cooldown_seconds, last_trigger_time, enabled, created_at
                        FROM triggers WHERE user_id = ? AND enabled = 1
                        ORDER BY created_at
                    """,
                        (user["id"],),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, trigger_name, regex_pattern, shock_type, intensity, duration,
                               cooldown_seconds, last_trigger_time, enabled, created_at
                        FROM triggers WHERE user_id = ?
                        ORDER BY created_at
                    """,
                        (user["id"],),
                    )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get triggers for user {discord_id} in guild {guild_id}: {e}")
            return []

    async def get_all_enabled_triggers_for_guild(self, guild_id: int) -> dict[int, list[dict]]:
        """Get all enabled triggers grouped by discord_id for a specific guild"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT u.discord_id, t.id, t.trigger_name, t.regex_pattern, t.shock_type,
                           t.intensity, t.duration, t.cooldown_seconds, t.last_trigger_time, t.created_at
                    FROM triggers t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.enabled = 1 AND u.guild_id = ?
                    ORDER BY u.discord_id, t.created_at
                """,
                    (guild_id,),
                )

                triggers_by_user = {}
                async for row in cursor:
                    row_dict = dict(row)
                    user_id = row_dict["discord_id"]
                    if user_id not in triggers_by_user:
                        triggers_by_user[user_id] = []
                    triggers_by_user[user_id].append(row_dict)

                return triggers_by_user
        except Exception as e:
            logger.error(f"Failed to get all enabled triggers for guild {guild_id}: {e}")
            return {}

    # Reminder Methods (converted to async)

    async def add_reminder(
        self,
        guild_id: int,
        target_discord_id: int,
        creator_discord_id: int,
        scheduled_time: datetime,
        reason: str = None,
        shock_type: str = "Shock",
        intensity: int = 50,
        duration: int = 1000,
        channel_id: int = None,
        is_recurring: bool = False,
        recurrence_pattern: str = None,
    ) -> int | None:
        """Add a scheduled reminder/shock with optional recurrence (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO reminders (guild_id, target_discord_id, creator_discord_id, scheduled_time,
                                         reason, shock_type, intensity, duration, channel_id,
                                         is_recurring, recurrence_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        guild_id,
                        target_discord_id,
                        creator_discord_id,
                        scheduled_time.isoformat(),
                        reason,
                        shock_type,
                        intensity,
                        duration,
                        channel_id,
                        is_recurring,
                        recurrence_pattern,
                    ),
                )
                reminder_id = cursor.lastrowid
                recurrence_info = f" (recurring: {recurrence_pattern})" if is_recurring else ""
                logger.info(
                    f"Added reminder {reminder_id} in guild {guild_id} for user {target_discord_id} at {scheduled_time}{recurrence_info}"
                )
                return reminder_id
        except Exception as e:
            logger.error(f"Failed to add reminder: {e}")
            return None

    async def get_pending_reminders(self) -> list[dict]:
        """Get all pending reminders that are due (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                current_time = datetime.now().isoformat()
                await cursor.execute(
                    """
                    SELECT id, guild_id, target_discord_id, creator_discord_id, scheduled_time,
                           reason, shock_type, intensity, duration, channel_id, created_at,
                           is_recurring, recurrence_pattern, last_executed
                    FROM reminders
                    WHERE completed = 0 AND scheduled_time <= ?
                    ORDER BY scheduled_time
                """,
                    (current_time,),
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get pending reminders: {e}")
            return []

    async def update_recurring_reminder(self, reminder_id: int, next_scheduled_time: datetime) -> bool:
        """Update a recurring reminder with next scheduled time (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE reminders
                    SET scheduled_time = ?, last_executed = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (next_scheduled_time.isoformat(), reminder_id),
                )
                if cursor.rowcount > 0:
                    logger.info(
                        f"Updated recurring reminder {reminder_id} to next occurrence: {next_scheduled_time}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to update recurring reminder {reminder_id}: {e}")
            return False

    async def mark_reminder_completed(self, reminder_id: int) -> bool:
        """Mark a reminder as completed (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE reminders SET completed = 1 WHERE id = ?
                """,
                    (reminder_id,),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to mark reminder {reminder_id} as completed: {e}")
            return False

    async def delete_reminder(self, reminder_id: int, guild_id: int) -> bool:
        """Delete a reminder (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    DELETE FROM reminders WHERE id = ? AND guild_id = ?
                """,
                    (reminder_id, guild_id),
                )
                if cursor.rowcount > 0:
                    logger.info(f"Deleted reminder {reminder_id} from guild {guild_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete reminder {reminder_id}: {e}")
            return False

    async def get_reminders_for_guild(self, guild_id: int, include_completed: bool = False) -> list[dict]:
        """Get all reminders for a guild (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                if include_completed:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ?
                        ORDER BY scheduled_time
                    """,
                        (guild_id,),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ? AND completed = 0
                        ORDER BY scheduled_time
                    """,
                        (guild_id,),
                    )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get reminders for guild {guild_id}: {e}")
            return []

    async def get_reminders_by_creator(
        self, guild_id: int, creator_discord_id: int, include_completed: bool = False
    ) -> list[dict]:
        """Get all reminders created by a specific user in a guild (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                if include_completed:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ? AND creator_discord_id = ?
                        ORDER BY scheduled_time
                    """,
                        (guild_id, creator_discord_id),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ? AND creator_discord_id = ? AND completed = 0
                        ORDER BY scheduled_time
                    """,
                        (guild_id, creator_discord_id),
                    )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get reminders for creator {creator_discord_id}: {e}")
            return []

    async def get_reminders_for_user(
        self, guild_id: int, target_discord_id: int, include_completed: bool = False
    ) -> list[dict]:
        """Get all reminders targeting a specific user in a guild (async)."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                if include_completed:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ? AND target_discord_id = ?
                        ORDER BY scheduled_time
                    """,
                        (guild_id, target_discord_id),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                               reason, shock_type, intensity, duration, channel_id, completed, created_at
                        FROM reminders
                        WHERE guild_id = ? AND target_discord_id = ? AND completed = 0
                        ORDER BY scheduled_time
                    """,
                        (guild_id, target_discord_id),
                    )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(
                f"Failed to get reminders for target {target_discord_id} in guild {guild_id}: {e}"
            )
            return []

    async def get_reminder(self, reminder_id: int, guild_id: int) -> dict | None:
        """Get a specific reminder by ID (async)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT id, target_discord_id, creator_discord_id, scheduled_time,
                           reason, shock_type, intensity, duration, channel_id, completed, created_at
                    FROM reminders
                    WHERE id = ? AND guild_id = ?
                """,
                    (reminder_id, guild_id),
                )
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get reminder {reminder_id}: {e}")
            return None

    async def get_guild_users(self, guild_id: int) -> list[dict]:
        """Get all registered users in a guild"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT id, discord_id, guild_id, discord_username, created_at, updated_at
                    FROM users
                    WHERE guild_id = ?
                    ORDER BY discord_username
                """,
                    (guild_id,),
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get users for guild {guild_id}: {e}")
            return []

    async def remove_user(self, discord_id: int, guild_id: int) -> bool:
        """Remove a user and all associated data (shockers, triggers, controller permissions)"""
        try:
            user = await self.get_user(discord_id, guild_id)
            if not user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                # Delete user (CASCADE will handle shockers, triggers, and controller_permissions)
                await cursor.execute(
                    """
                    DELETE FROM users WHERE discord_id = ? AND guild_id = ?
                """,
                    (discord_id, guild_id),
                )

                if cursor.rowcount > 0:
                    logger.info(f"Removed user {discord_id} from guild {guild_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove user {discord_id} from guild {guild_id}: {e}")
            return False

    # Controller Permission Methods (Consent-based control)

    async def add_controller_permission(
        self,
        sub_discord_id: int,
        guild_id: int,
        controller_discord_id: int = None,
        controller_role_id: int = None,
    ) -> bool:
        """Add a controller permission for a Sub user."""
        try:
            # Validate that exactly one is provided
            if (controller_discord_id is None) == (controller_role_id is None):
                logger.error(
                    "Must provide exactly one of controller_discord_id or controller_role_id"
                )
                return False

            # Get sub user's internal ID
            sub_user = await self.get_user(sub_discord_id, guild_id)
            if not sub_user:
                logger.error(
                    f"Cannot add controller permission: Sub user {sub_discord_id} not found in guild {guild_id}"
                )
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO controller_permissions (sub_user_id, controller_discord_id, controller_role_id)
                    VALUES (?, ?, ?)
                """,
                    (sub_user["id"], controller_discord_id, controller_role_id),
                )

                if controller_discord_id:
                    logger.info(
                        f"Added controller permission: User {controller_discord_id} can control {sub_discord_id} in guild {guild_id}"
                    )
                else:
                    logger.info(
                        f"Added controller permission: Role {controller_role_id} can control {sub_discord_id} in guild {guild_id}"
                    )
                return True
        except Exception as e:
            logger.error(f"Failed to add controller permission: {e}")
            return False

    async def remove_controller_permission(
        self,
        sub_discord_id: int,
        guild_id: int,
        controller_discord_id: int = None,
        controller_role_id: int = None,
    ) -> bool:
        """Remove a controller permission for a Sub user."""
        try:
            sub_user = await self.get_user(sub_discord_id, guild_id)
            if not sub_user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                if controller_discord_id:
                    await cursor.execute(
                        """
                        DELETE FROM controller_permissions
                        WHERE sub_user_id = ? AND controller_discord_id = ?
                    """,
                        (sub_user["id"], controller_discord_id),
                    )
                elif controller_role_id:
                    await cursor.execute(
                        """
                        DELETE FROM controller_permissions
                        WHERE sub_user_id = ? AND controller_role_id = ?
                    """,
                        (sub_user["id"], controller_role_id),
                    )
                else:
                    return False

                if cursor.rowcount > 0:
                    logger.info(
                        f"Removed controller permission for {sub_discord_id} in guild {guild_id}"
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove controller permission: {e}")
            return False

    async def get_controller_permissions(
        self, sub_discord_id: int, guild_id: int
    ) -> dict[str, list[int]]:
        """Get all controller permissions for a Sub user."""
        try:
            sub_user = await self.get_user(sub_discord_id, guild_id)
            if not sub_user:
                return {"users": [], "roles": []}

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT controller_discord_id, controller_role_id
                    FROM controller_permissions
                    WHERE sub_user_id = ?
                """,
                    (sub_user["id"],),
                )

                users = []
                roles = []
                async for row in cursor:
                    if row["controller_discord_id"]:
                        users.append(row["controller_discord_id"])
                    if row["controller_role_id"]:
                        roles.append(row["controller_role_id"])

                return {"users": users, "roles": roles}
        except Exception as e:
            logger.error(f"Failed to get controller permissions: {e}")
            return {"users": [], "roles": []}

    async def clear_all_controller_permissions(self, sub_discord_id: int, guild_id: int) -> bool:
        """Clear all controller permissions for a Sub user."""
        try:
            sub_user = await self.get_user(sub_discord_id, guild_id)
            if not sub_user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    DELETE FROM controller_permissions WHERE sub_user_id = ?
                """,
                    (sub_user["id"],),
                )
                logger.info(
                    f"Cleared all controller permissions for {sub_discord_id} in guild {guild_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to clear controller permissions: {e}")
            return False

    async def can_user_control(
        self,
        controller_discord_id: int,
        sub_discord_id: int,
        guild_id: int,
        controller_role_ids: list[int] = None,
    ) -> bool:
        """Check if a controller has permission to control a Sub user."""
        try:
            # User can always control themselves
            if controller_discord_id == sub_discord_id:
                return True

            sub_user = await self.get_user(sub_discord_id, guild_id)
            if not sub_user:
                return False

            async with self.get_connection() as conn:
                cursor = await conn.cursor()

                # Check for direct user permission
                await cursor.execute(
                    """
                    SELECT id FROM controller_permissions
                    WHERE sub_user_id = ? AND controller_discord_id = ?
                """,
                    (sub_user["id"], controller_discord_id),
                )
                if await cursor.fetchone():
                    return True

                # Check for role-based permission
                if controller_role_ids:
                    placeholders = ",".join("?" * len(controller_role_ids))
                    await cursor.execute(
                        f"""
                        SELECT id FROM controller_permissions
                        WHERE sub_user_id = ? AND controller_role_id IN ({placeholders})
                    """,
                        (sub_user["id"], *controller_role_ids),
                    )
                    if await cursor.fetchone():
                        return True

                return False
        except Exception as e:
            logger.error(f"Failed to check controller permission: {e}")
            return False

    # Controller Cooldown Methods

    async def check_controller_cooldown(
        self,
        controller_discord_id: int,
        target_discord_id: int,
        guild_id: int,
        cooldown_seconds: int = 300,
    ) -> tuple[bool, int]:
        """Check if a controller is off cooldown for controlling a specific target user."""
        try:
            # User controlling themselves has no cooldown
            if controller_discord_id == target_discord_id:
                return True, 0

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT last_control_time, cooldown_seconds
                    FROM controller_cooldowns
                    WHERE controller_discord_id = ? AND target_discord_id = ? AND guild_id = ?
                """,
                    (controller_discord_id, target_discord_id, guild_id),
                )
                row = await cursor.fetchone()

                if not row or not row["last_control_time"]:
                    return True, 0  # Never used control, ready to go

                # Use the stored cooldown or the provided default
                actual_cooldown = (
                    row["cooldown_seconds"] if row["cooldown_seconds"] else cooldown_seconds
                )
                last_time = self._parse_db_timestamp(row["last_control_time"])  # UTC-aware
                now_utc = datetime.now(UTC)
                seconds_since = (now_utc - last_time).total_seconds()

                if seconds_since >= actual_cooldown:
                    return True, 0
                else:
                    return False, int(actual_cooldown - seconds_since)
        except Exception as e:
            logger.error(f"Failed to check controller cooldown: {e}")
            return True, 0  # On error, allow the action

    async def update_controller_cooldown(
        self,
        controller_discord_id: int,
        target_discord_id: int,
        guild_id: int,
        cooldown_seconds: int = 300,
    ) -> bool:
        """Update the last control time for a controller-target pair."""
        try:
            # Don't track cooldown for self-control
            if controller_discord_id == target_discord_id:
                return True

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO controller_cooldowns
                        (controller_discord_id, target_discord_id, guild_id, last_control_time, cooldown_seconds)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(controller_discord_id, target_discord_id, guild_id) DO UPDATE SET
                        last_control_time = CURRENT_TIMESTAMP,
                        cooldown_seconds = excluded.cooldown_seconds
                """,
                    (controller_discord_id, target_discord_id, guild_id, cooldown_seconds),
                )
                logger.debug(
                    f"Updated controller cooldown: {controller_discord_id} -> {target_discord_id} in guild {guild_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update controller cooldown: {e}")
            return False

    async def set_controller_cooldown_duration(
        self, target_discord_id: int, guild_id: int, cooldown_seconds: int
    ) -> bool:
        """Set the cooldown duration for all controllers of a specific target user."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                # Update all existing cooldown records for this target
                await cursor.execute(
                    """
                    UPDATE controller_cooldowns
                    SET cooldown_seconds = ?
                    WHERE target_discord_id = ? AND guild_id = ?
                """,
                    (cooldown_seconds, target_discord_id, guild_id),
                )
                logger.info(
                    f"Set controller cooldown duration to {cooldown_seconds}s for target {target_discord_id} in guild {guild_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to set controller cooldown duration: {e}")
            return False

    async def get_controller_cooldown_duration(self, target_discord_id: int, guild_id: int) -> int:
        """Get the configured cooldown duration for a target user."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT cooldown_seconds
                    FROM controller_cooldowns
                    WHERE target_discord_id = ? AND guild_id = ?
                    LIMIT 1
                """,
                    (target_discord_id, guild_id),
                )
                row = await cursor.fetchone()
                return row["cooldown_seconds"] if row else 300  # Default: 5 minutes
        except Exception as e:
            logger.error(f"Failed to get controller cooldown duration: {e}")
            return 300  # Default: 5 minutes

    # Controller Action Logging Methods

    async def log_controller_action(
        self,
        guild_id: int,
        controller_discord_id: int,
        controller_username: str,
        target_discord_id: int,
        target_username: str,
        action_type: str,
        shock_type: str = None,
        intensity: int = None,
        duration: int = None,
        shocker_id: str = None,
        shocker_name: str = None,
        success: bool = True,
        error_message: str = None,
        source: str = "manual",
        metadata: str = None,
    ) -> bool:
        """Log a controller action for audit trail purposes."""
        try:
            # Don't store raw shocker_id for privacy - store only last 4 chars or hash
            safe_shocker_id = None
            if shocker_id:
                safe_shocker_id = f"...{shocker_id[-4:]}" if len(shocker_id) > 4 else "****"

            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO controller_action_logs (
                        guild_id, controller_discord_id, controller_username,
                        target_discord_id, target_username, action_type,
                        shock_type, intensity, duration, shocker_id, shocker_name,
                        success, error_message, source, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        guild_id,
                        controller_discord_id,
                        controller_username,
                        target_discord_id,
                        target_username,
                        action_type,
                        shock_type,
                        intensity,
                        duration,
                        safe_shocker_id,
                        shocker_name,
                        success,
                        error_message,
                        source,
                        metadata,
                    ),
                )

                logger.debug(
                    f"Logged action: {action_type} by {controller_username} on {target_username} "
                    f"in guild {guild_id} - Success: {success}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to log controller action: {e}", exc_info=True)
            return False

    async def get_action_logs_for_target(
        self,
        target_discord_id: int,
        guild_id: int,
        limit: int = 100,
        offset: int = 0,
        days: int = None,
    ) -> list[dict]:
        """Get action logs for a specific target user."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()

                if days:
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    await cursor.execute(
                        """
                        SELECT id, guild_id, controller_discord_id, controller_username,
                               target_discord_id, target_username, action_type,
                               shock_type, intensity, duration, shocker_id, shocker_name,
                               success, error_message, source, metadata, timestamp
                        FROM controller_action_logs
                        WHERE target_discord_id = ? AND guild_id = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    """,
                        (target_discord_id, guild_id, cutoff_date, limit, offset),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, guild_id, controller_discord_id, controller_username,
                               target_discord_id, target_username, action_type,
                               shock_type, intensity, duration, shocker_id, shocker_name,
                               success, error_message, source, metadata, timestamp
                        FROM controller_action_logs
                        WHERE target_discord_id = ? AND guild_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    """,
                        (target_discord_id, guild_id, limit, offset),
                    )

                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get action logs for target {target_discord_id}: {e}")
            return []

    async def get_action_logs_by_controller(
        self, controller_discord_id: int, guild_id: int, limit: int = 100, offset: int = 0, days: int = None
    ) -> list[dict]:
        """Get action logs for a specific controller."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()

                if days:
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    await cursor.execute(
                        """
                        SELECT id, guild_id, controller_discord_id, controller_username,
                               target_discord_id, target_username, action_type,
                               shock_type, intensity, duration, shocker_id, shocker_name,
                               success, error_message, source, metadata, timestamp
                        FROM controller_action_logs
                        WHERE controller_discord_id = ? AND guild_id = ? AND timestamp >= ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    """,
                        (controller_discord_id, guild_id, cutoff_date, limit, offset),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT id, guild_id, controller_discord_id, controller_username,
                               target_discord_id, target_username, action_type,
                               shock_type, intensity, duration, shocker_id, shocker_name,
                               success, error_message, source, metadata, timestamp
                        FROM controller_action_logs
                        WHERE controller_discord_id = ? AND guild_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ? OFFSET ?
                    """,
                        (controller_discord_id, guild_id, limit, offset),
                    )

                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get action logs by controller {controller_discord_id}: {e}")
            return []

    async def get_action_log_count(
        self, target_discord_id: int, guild_id: int, days: int = None
    ) -> int:
        """Get the total count of action logs for a target user."""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()

                if days:
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM controller_action_logs
                        WHERE target_discord_id = ? AND guild_id = ? AND timestamp >= ?
                    """,
                        (target_discord_id, guild_id, cutoff_date),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM controller_action_logs
                        WHERE target_discord_id = ? AND guild_id = ?
                    """,
                        (target_discord_id, guild_id),
                    )

                row = await cursor.fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"Failed to get action log count: {e}")
            return 0

    async def delete_old_action_logs(self, days: int = 90) -> int:
        """Delete action logs older than the specified number of days."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    DELETE FROM controller_action_logs
                    WHERE timestamp < ?
                """,
                    (cutoff_date,),
                )
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} action logs older than {days} days")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete old action logs: {e}")
            return 0

    # Controller Preferences Methods (Smart Defaults)

    async def get_controller_preferences(
        self, controller_discord_id: int, guild_id: int, target_discord_id: int = None
    ) -> dict | None:
        """Get controller preferences (defaults and last-used values)"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT * FROM controller_preferences
                    WHERE controller_discord_id = ? AND guild_id = ? AND
                          (target_discord_id = ? OR target_discord_id IS NULL)
                    ORDER BY target_discord_id DESC
                    LIMIT 1
                """,
                    (controller_discord_id, guild_id, target_discord_id),
                )
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get controller preferences: {e}")
            return None

    async def set_controller_defaults(
        self,
        controller_discord_id: int,
        guild_id: int,
        target_discord_id: int = None,
        default_intensity: int = None,
        default_duration: int = None,
        default_shock_type: str = None,
        use_smart_defaults: bool = True,
    ) -> bool:
        """Set default preferences for a controller"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    INSERT INTO controller_preferences
                        (controller_discord_id, guild_id, target_discord_id,
                         default_intensity, default_duration, default_shock_type, use_smart_defaults)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(controller_discord_id, guild_id, target_discord_id) DO UPDATE SET
                        default_intensity = COALESCE(excluded.default_intensity, controller_preferences.default_intensity),
                        default_duration = COALESCE(excluded.default_duration, controller_preferences.default_duration),
                        default_shock_type = COALESCE(excluded.default_shock_type, controller_preferences.default_shock_type),
                        use_smart_defaults = excluded.use_smart_defaults,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        controller_discord_id,
                        guild_id,
                        target_discord_id,
                        default_intensity,
                        default_duration,
                        default_shock_type,
                        use_smart_defaults,
                    ),
                )
                logger.info(
                    f"Set controller defaults for {controller_discord_id} in guild {guild_id}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to set controller defaults: {e}")
            return False

    async def update_last_used_values(
        self,
        controller_discord_id: int,
        guild_id: int,
        target_discord_id: int,
        intensity: int,
        duration: int,
        shock_type: str,
    ) -> bool:
        """Update the last-used values for a controller"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                # Update both specific target and general preferences
                for target_id in [target_discord_id, None]:
                    await cursor.execute(
                        """
                        INSERT INTO controller_preferences
                            (controller_discord_id, guild_id, target_discord_id,
                             last_used_intensity, last_used_duration, last_used_shock_type, last_used_target_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(controller_discord_id, guild_id, target_discord_id) DO UPDATE SET
                            last_used_intensity = excluded.last_used_intensity,
                            last_used_duration = excluded.last_used_duration,
                            last_used_shock_type = excluded.last_used_shock_type,
                            last_used_target_id = excluded.last_used_target_id,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (
                            controller_discord_id,
                            guild_id,
                            target_id,
                            intensity,
                            duration,
                            shock_type,
                            target_discord_id,
                        ),
                    )
                return True
        except Exception as e:
            logger.error(f"Failed to update last used values: {e}")
            return False

    async def get_controllable_users(
        self, controller_discord_id: int, guild_id: int, controller_role_ids: list[int] = None
    ) -> list[int]:
        """Get list of Discord IDs that a controller can control in a guild"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT DISTINCT u.discord_id
                    FROM users u
                    JOIN controller_permissions cp ON u.id = cp.sub_user_id
                    WHERE u.guild_id = ? AND (
                        cp.controller_discord_id = ?
                        OR (cp.controller_role_id IN ({}) AND cp.controller_role_id IS NOT NULL)
                    )
                """.format(
                        ",".join("?" * len(controller_role_ids)) if controller_role_ids else "NULL"
                    ),
                    (guild_id, controller_discord_id, *(controller_role_ids or [])),
                )

                rows = await cursor.fetchall()
                return [row["discord_id"] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get controllable users: {e}")
            return []

    async def get_device_worn_status(self, discord_id: int, guild_id: int) -> bool:
        """Get whether a user's device is worn"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    SELECT device_worn FROM users WHERE discord_id = ? AND guild_id = ?
                """,
                    (discord_id, guild_id),
                )
                row = await cursor.fetchone()
                if row:
                    # SQLite stores booleans as 0 or 1
                    return bool(row["device_worn"])
                return True  # Default to worn if user not found
        except Exception as e:
            logger.error(f"Failed to get device_worn status for user {discord_id}: {e}")
            return True  # Default to worn on error

    async def set_device_worn(self, discord_id: int, guild_id: int, is_worn: bool) -> bool:
        """Update whether a user's device is worn"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    """
                    UPDATE users SET device_worn = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ? AND guild_id = ?
                """,
                    (1 if is_worn else 0, discord_id, guild_id),
                )
                if cursor.rowcount > 0:
                    logger.info(f"Updated device_worn to {is_worn} for user {discord_id} in guild {guild_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to set device_worn status for user {discord_id}: {e}")
            return False

