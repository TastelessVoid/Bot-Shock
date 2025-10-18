"""
Encryption utilities for sensitive data with enhanced security
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("BotShock.Encryption")


class EncryptionHandler:
    """Handles encryption and decryption of sensitive data with per-user key derivation"""

    def __init__(self, master_key: str = None):
        """
        Initialize encryption handler with a master key

        Args:
            master_key: Base64 encoded master encryption key or password
        """
        if not master_key:
            raise ValueError(
                "Encryption key is required. "
                "Please set ENCRYPTION_KEY in your .env file. "
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )

        try:
            # Try to use as direct key (Fernet base64 key)
            key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
            self.master_fernet = Fernet(key_bytes)
            self.master_key = key_bytes
        except Exception:
            # If not a valid Fernet key, derive one from password
            if isinstance(master_key, bytes):
                master_key = master_key.decode()
            self.master_key = self._derive_key(master_key)
            self.master_fernet = Fernet(self.master_key)

        # Cache for derived keys to improve performance
        self._key_cache = {}

    @staticmethod
    def _derive_key(password: str) -> bytes:
        """Derive a Fernet key from a password"""
        # Use a fixed salt (for deterministic derivation across runs/tests)
        # In production, consider a configurable or stored salt.
        salt = b"botshock_salt_v2_"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def _derive_user_key(self, user_id: int, guild_id: int) -> Fernet:
        """
        Derive a unique encryption key for a specific user in a specific guild

        This provides an additional layer of security:
        - Even if the database is compromised, each user's data requires knowing their Discord ID and guild ID
        - An attacker can't decrypt all data with just the master key alone
        - Limits blast radius if a single key is compromised

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            Fernet instance with user-specific key
        """
        cache_key = f"{user_id}:{guild_id}"

        if cache_key in self._key_cache:
            return self._key_cache[cache_key]

        # Combine master key with user/guild identifiers to create unique key
        context = f"user:{user_id}:guild:{guild_id}".encode()

        # Use SHA-256 to derive a deterministic key from master key + context
        h = hashlib.sha256()
        h.update(self.master_key)
        h.update(context)
        derived_raw = h.digest()

        # Convert to valid Fernet key
        user_key = base64.urlsafe_b64encode(derived_raw)
        user_fernet = Fernet(user_key)

        # Cache for performance
        self._key_cache[cache_key] = user_fernet

        return user_fernet

    def encrypt(self, data: str, user_id: int = None, guild_id: int = None) -> str:
        """
        Encrypt a string with optional user-specific key derivation

        Args:
            data: Plain text string to encrypt
            user_id: Optional Discord user ID for per-user encryption
            guild_id: Optional Discord guild ID for per-guild encryption

        Returns:
            Encrypted string (base64 encoded)
        """
        if not data:
            return data

        try:
            # Use user-specific key if IDs provided, otherwise use master key
            if user_id is not None and guild_id is not None:
                fernet = self._derive_user_key(user_id, guild_id)
            else:
                fernet = self.master_fernet

            encrypted = fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: str, user_id: int = None, guild_id: int = None) -> str:
        """
        Decrypt a string with optional user-specific key derivation

        Args:
            encrypted_data: Encrypted string (base64 encoded)
            user_id: Optional Discord user ID for per-user decryption
            guild_id: Optional Discord guild ID for per-guild decryption

        Returns:
            Decrypted plain text string
        """
        if not encrypted_data:
            return encrypted_data

        try:
            # Use user-specific key if IDs provided, otherwise use master key
            if user_id is not None and guild_id is not None:
                fernet = self._derive_user_key(user_id, guild_id)
            else:
                fernet = self.master_fernet

            decrypted = fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    @staticmethod
    def generate_key() -> str:
        """Generate a new master encryption key"""
        return Fernet.generate_key().decode()

    def clear_key_cache(self):
        """Clear the derived key cache (useful after key rotation)"""
        self._key_cache.clear()
        logger.info("Encryption key cache cleared")
