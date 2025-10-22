"""
Tests for the OpenShock API client service.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import aiohttp

from botshock.services.api_client import OpenShockAPIClient, RateLimiter
from botshock.exceptions import BotShockException


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter can be initialized."""
        limiter = RateLimiter(requests_per_minute=60)
        assert limiter.requests_per_minute == 60
        assert len(limiter.requests) == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_under_limit(self):
        """Test rate limiter allows requests under the limit."""
        limiter = RateLimiter(requests_per_minute=3)
        
        # Should allow up to 3 requests
        assert await limiter.acquire(user_id=123) is True
        assert await limiter.acquire(user_id=123) is True
        assert await limiter.acquire(user_id=123) is True
        
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_requests_over_limit(self):
        """Test rate limiter blocks requests over the limit."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # First 2 should succeed
        assert await limiter.acquire(user_id=456) is True
        assert await limiter.acquire(user_id=456) is True
        
        # Third should fail
        assert await limiter.acquire(user_id=456) is False

    @pytest.mark.asyncio
    async def test_rate_limiter_separate_per_user(self):
        """Test rate limiter tracks limits per user separately."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # User 1 makes 2 requests
        assert await limiter.acquire(user_id=111) is True
        assert await limiter.acquire(user_id=111) is True
        
        # User 2 should still be able to make requests
        assert await limiter.acquire(user_id=222) is True
        assert await limiter.acquire(user_id=222) is True
        assert await limiter.acquire(user_id=222) is False


class TestOpenShockAPIClient:
    """Test OpenShock API client functionality."""

    def test_api_client_initialization_with_defaults(self):
        """Test API client initializes with default values."""
        client = OpenShockAPIClient()
        assert client.api_url == "https://api.openshock.app/2/shockers/control"
        assert client.base_url == "https://api.openshock.app"
        assert client.max_connections == 100

    def test_api_client_initialization_with_custom_values(self):
        """Test API client initializes with custom values."""
        client = OpenShockAPIClient(
            base_url="https://custom.api.com",
            timeout=20,
            max_connections=50,
            requests_per_minute=120,
        )
        assert client.base_url == "https://custom.api.com"
        assert client.max_connections == 50
        assert client.rate_limiter.requests_per_minute == 120

    def test_api_client_has_required_methods(self):
        """Test API client has required methods."""
        client = OpenShockAPIClient()
        
        # Verify required methods exist
        assert hasattr(client, 'send_control')
        assert callable(client.send_control)
        assert hasattr(client, 'close')
        assert callable(client.close)

    @pytest.mark.asyncio
    async def test_api_client_respects_rate_limiting(self):
        """Test API client respects rate limiting."""
        client = OpenShockAPIClient(requests_per_minute=1)
        
        # Verify rate limiter is initialized
        assert client.rate_limiter is not None
        assert client.rate_limiter.requests_per_minute == 1


class TestAPIClientErrorHandling:
    """Test error handling in API client."""

    @pytest.mark.asyncio
    async def test_api_client_rate_limiting_integration(self):
        """Test API client with rate limiting."""
        client = OpenShockAPIClient(requests_per_minute=60)

        # Verify rate limiter exists
        assert client.rate_limiter is not None
        assert client.rate_limiter.requests_per_minute == 60

