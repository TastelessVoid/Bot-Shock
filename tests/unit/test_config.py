"""
Tests for configuration loading and validation.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch
from dotenv import load_dotenv

from botshock.config import BotConfig, load_config, validate_config
from botshock.exceptions import ConfigurationError


class TestBotConfig:
    """Test BotConfig dataclass."""

    def test_bot_config_initialization(self):
        """Test BotConfig can be initialized with required fields."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
        )
        
        assert config.discord_token == "test_token"
        assert config.encryption_key == "test_key_123456789012345"

    def test_bot_config_with_defaults(self):
        """Test BotConfig uses default values for optional fields."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
        )
        
        assert config.database_path == "botshock.db"
        assert config.database_pool_size == 5
        assert config.api_timeout == 10
        assert config.log_level == "INFO"

    def test_bot_config_immutable(self):
        """Test BotConfig is immutable (frozen dataclass)."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
        )
        
        with pytest.raises(AttributeError):
            config.discord_token = "new_token"

    def test_bot_config_custom_values(self):
        """Test BotConfig can be initialized with custom values."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            database_path="custom.db",
            api_timeout=30,
            log_level="DEBUG",
        )
        
        assert config.database_path == "custom.db"
        assert config.api_timeout == 30
        assert config.log_level == "DEBUG"


class TestConfigLoading:
    """Test configuration loading from environment variables."""

    def test_load_config_missing_discord_token(self):
        """Test loading config fails when DISCORD_TOKEN is missing."""
        # Note: Encryption key is checked first in the actual implementation
        env_vars = {"ENCRYPTION_KEY": "test_key_123456789012345"}
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("botshock.config.load_dotenv"):
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config()

                assert "DISCORD_TOKEN" in str(exc_info.value)

    def test_load_config_missing_encryption_key(self):
        """Test loading config fails when ENCRYPTION_KEY is missing."""
        with patch.dict(os.environ, {"DISCORD_TOKEN": "test_token"}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                load_config()
            
            assert "ENCRYPTION_KEY" in str(exc_info.value)

    def test_load_config_success(self):
        """Test successful config loading."""
        env_vars = {
            "DISCORD_TOKEN": "test_token",
            "ENCRYPTION_KEY": "test_key_123456789012345",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("botshock.config.load_dotenv"):
                config = load_config()
                
                assert config.discord_token == "test_token"
                assert config.encryption_key == "test_key_123456789012345"

    def test_load_config_with_custom_values(self):
        """Test config loading with custom environment values."""
        env_vars = {
            "DISCORD_TOKEN": "test_token",
            "ENCRYPTION_KEY": "test_key_123456789012345",
            "DATABASE_PATH": "custom.db",
            "API_TIMEOUT": "20",
            "LOG_LEVEL": "DEBUG",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("botshock.config.load_dotenv"):
                config = load_config()
                
                assert config.database_path == "custom.db"
                assert config.api_timeout == 20
                assert config.log_level == "DEBUG"

    def test_load_config_invalid_log_retention_days(self):
        """Test loading config with invalid LOG_RETENTION_DAYS."""
        env_vars = {
            "DISCORD_TOKEN": "test_token",
            "ENCRYPTION_KEY": "test_key_123456789012345",
            "LOG_RETENTION_DAYS": "not_a_number",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("botshock.config.load_dotenv"):
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config()
                
                assert "LOG_RETENTION_DAYS" in str(exc_info.value)

    def test_load_config_invalid_max_old_files(self):
        """Test loading config with invalid LOG_MAX_OLD_FILES."""
        env_vars = {
            "DISCORD_TOKEN": "test_token",
            "ENCRYPTION_KEY": "test_key_123456789012345",
            "LOG_MAX_OLD_FILES": "invalid",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("botshock.config.load_dotenv"):
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config()
                
                assert "LOG_MAX_OLD_FILES" in str(exc_info.value)


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_success(self):
        """Test validation passes for valid config."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            database_pool_size=5,
            api_timeout=10,
            api_max_connections=100,
            api_requests_per_minute=60,
            log_level="INFO",
        )
        
        # Should not raise
        validate_config(config)

    def test_validate_config_invalid_pool_size(self):
        """Test validation fails for invalid database pool size."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            database_pool_size=0,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "DATABASE_POOL_SIZE" in str(exc_info.value)

    def test_validate_config_invalid_api_timeout(self):
        """Test validation fails for invalid API timeout."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            api_timeout=0,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "API_TIMEOUT" in str(exc_info.value)

    def test_validate_config_invalid_api_max_connections(self):
        """Test validation fails for invalid max connections."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            api_max_connections=0,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "API_MAX_CONNECTIONS" in str(exc_info.value)

    def test_validate_config_invalid_requests_per_minute(self):
        """Test validation fails for invalid requests per minute."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            api_requests_per_minute=0,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "API_REQUESTS_PER_MINUTE" in str(exc_info.value)

    def test_validate_config_invalid_log_level(self):
        """Test validation fails for invalid log level."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            log_level="INVALID_LEVEL",
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "LOG_LEVEL" in str(exc_info.value)

    def test_validate_config_valid_log_levels(self):
        """Test validation passes for all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = BotConfig(
                discord_token="test_token",
                encryption_key="test_key_123456789012345",
                log_level=level,
            )
            
            # Should not raise
            validate_config(config)

    def test_validate_config_invalid_retention_days(self):
        """Test validation fails for negative retention days."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            log_retention_days=-1,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "LOG_RETENTION_DAYS" in str(exc_info.value)

    def test_validate_config_invalid_max_old_files(self):
        """Test validation fails for negative max old files."""
        config = BotConfig(
            discord_token="test_token",
            encryption_key="test_key_123456789012345",
            log_max_old_files=-1,
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_config(config)
        
        assert "LOG_MAX_OLD_FILES" in str(exc_info.value)

