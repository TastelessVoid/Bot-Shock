"""
OpenShock API client for handling all API communication
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import aiohttp

from botshock.constants import OPENSHOCK_API_BASE_URL

logger = logging.getLogger("BotShock.APIClient")


class RateLimiter:
    """Simple rate limiter to prevent API abuse"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: defaultdict = defaultdict(list)

    async def acquire(self, user_id: int) -> bool:
        """Check if request is allowed under the rate limit"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id] if req_time > cutoff
        ]

        if len(self.requests[user_id]) >= self.requests_per_minute:
            return False

        self.requests[user_id].append(now)
        return True


class OpenShockAPIClient:
    """Handles all communication with the OpenShock API with connection pooling and rate limiting"""

    def __init__(
        self,
        api_url: str | None = None,
        base_url: str = OPENSHOCK_API_BASE_URL,
        timeout: int = 10,
        max_connections: int = 100,
        requests_per_minute: int = 60,
    ):
        # Normalize and derive base/control URLs
        if api_url:
            stripped = api_url.rstrip("/")
            # If caller accidentally passed a base URL, derive control endpoint
            if stripped.endswith("/2/shockers/control"):
                self.api_url = stripped
                # Derive base from control URL prefix before "/2/"
                try:
                    self.base_url = stripped.split("/2/")[0]
                except Exception:
                    self.base_url = base_url.rstrip("/")
            else:
                self.base_url = stripped
                self.api_url = f"{stripped}/2/shockers/control"
        else:
            self.base_url = base_url.rstrip("/")
            self.api_url = f"{self.base_url}/2/shockers/control"

        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_connections = max_connections
        self.rate_limiter = RateLimiter(requests_per_minute)
        self._session: aiohttp.ClientSession | None = None
        logger.info(
            f"API Client initialized base={self.base_url}, control={self.api_url}, "
            f"max_conns={max_connections}, rate={requests_per_minute}/min"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session with connection pooling"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections, limit_per_host=30, ttl_dns_cache=300
            )
            self._session = aiohttp.ClientSession(connector=connector, timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("API client session closed")

    async def send_control(
        self,
        api_token: str,
        shocker_id: str,
        shock_type: str,
        intensity: int,
        duration: int,
        custom_name: str = "Discord Bot",
        user_id: int | None = None,
        base_url_override: str | None = None,
    ) -> tuple[bool, int, str]:
        """
        Send a control command to the OpenShock API (using v2 endpoint as recommended)

        Returns:
            tuple: (success: bool, status_code: int, response_text: str)
        """
        # Check rate limit if user_id provided
        if user_id and not await self.rate_limiter.acquire(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False, 429, "Rate limit exceeded. Please try again later."

        # Determine control endpoint
        if base_url_override:
            control_url = f"{base_url_override.rstrip('/')}/2/shockers/control"
        else:
            control_url = self.api_url

        # v2 API uses nested structure with "shocks" wrapper and "customName"
        payload = {
            "shocks": [
                {
                    "id": shocker_id,
                    "type": shock_type,
                    "intensity": intensity,
                    "duration": duration,
                    "exclusive": True,
                }
            ],
            "customName": custom_name,
        }

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "OpenShockToken": api_token,
        }

        try:
            logger.debug(f"Sending control request to {control_url}")
            logger.debug(
                f"Shocker ID: {shocker_id}, Type: {shock_type}, Intensity: {intensity}%, Duration: {duration}ms"
            )

            session = await self._get_session()
            async with session.post(control_url, json=payload, headers=headers) as response:
                response_text = await response.text()
                success = response.status == 200

                if success:
                    logger.info(
                        f"Control successful - Type: {shock_type} - "
                        f"Intensity: {intensity}% - Duration: {duration}ms"
                    )
                else:
                    logger.error(
                        f"Control failed - Status: {response.status} - Response: {response_text}"
                    )
                    # Add more detailed logging for 404 errors
                    if response.status == 404:
                        # Try to parse the error response for more details
                        try:
                            import json

                            error_data = json.loads(response_text)
                            error_type = error_data.get("type", "Unknown")
                            logger.error(
                                f"404 Error Details - Shocker ID: {shocker_id} - "
                                f"Error Type: {error_type} - "
                                f"This means: "
                                + (
                                    "The API token cannot control this shocker. "
                                    "Possible causes: (1) API token is for a different user than the shocker owner, "
                                    "(2) This is a shared shocker and the API token can't control shared shockers, "
                                    "(3) The shocker was deleted from OpenShock"
                                    if error_type == "Shocker.Control.NotFound"
                                    else "The shocker doesn't exist or the API token lacks 'shockers.use' permission"
                                )
                            )
                        except Exception:
                            logger.error(
                                f"404 Error Details - Shocker ID: {shocker_id} - "
                                f"Could not parse error response"
                            )

                return success, response.status, response_text

        except TimeoutError:
            error_msg = "Connection timeout - OpenShock server did not respond in time"
            logger.error(f"Timeout error during control request: {error_msg}")
            return False, 0, error_msg
        except aiohttp.ClientConnectionError as e:
            error_msg = f"Connection error - Unable to reach OpenShock server: {str(e)}"
            logger.error(f"Connection error during control request: {e}")
            return False, 0, error_msg
        except aiohttp.ClientResponseError as e:
            error_msg = f"HTTP response error - Status: {e.status}, Message: {e.message}"
            logger.error(f"Response error during control request: {e}")
            return False, e.status, error_msg
        except aiohttp.ClientError as e:
            error_msg = f"Network error - {type(e).__name__}: {str(e)}"
            logger.exception(f"HTTP error during control request: {e}")
            return False, 0, error_msg
        except Exception as e:
            error_msg = f"Unexpected error - {type(e).__name__}: {str(e)}"
            logger.exception(f"Unexpected error during control request: {e}")
            return False, 0, error_msg

    async def validate_token(
        self, api_token: str, base_url_override: str | None = None
    ) -> tuple[bool, str, dict]:
        """
        Validate an API token by fetching user's own shockers (using v1 endpoint)

        Returns:
            tuple: (is_valid: bool, message: str, data: dict)
                   data contains 'shockers' list if successful
        """
        headers = {"accept": "application/json", "OpenShockToken": api_token}

        # Determine base URL
        effective_base = base_url_override.rstrip("/") if base_url_override else self.base_url

        try:
            logger.info("Validating API token...")
            async with aiohttp.ClientSession(timeout=self.timeout) as session, session.get(
                f"{effective_base}/1/shockers/own", headers=headers
            ) as response:
                response_text = await response.text()

                if response.status == 200:
                    try:
                        data = await response.json()
                        # API v1 returns data in a nested 'data' field wrapped in LegacyDataResponse
                        shockers_data = data.get("data", [])
                        # v1 /shockers/own returns array of devices with shockers
                        all_shockers = []
                        if isinstance(shockers_data, list):
                            for device in shockers_data:
                                if isinstance(device, dict) and "shockers" in device:
                                    all_shockers.extend(device["shockers"])

                        shocker_count = len(all_shockers)
                        logger.info(
                            f"API token validated successfully. Found {shocker_count} controllable shockers."
                        )
                        return (
                            True,
                            f"Token valid! Found {shocker_count} shocker(s).",
                            {"shockers": all_shockers},
                        )
                    except Exception as e:
                        logger.error(f"Failed to parse validation response: {e}")
                        return (
                            True,
                            "Token valid but couldn't parse shocker data.",
                            {"shockers": []},
                        )
                elif response.status == 401:
                    logger.warning("API token validation failed: Unauthorized")
                    return (
                        False,
                        "Invalid API token. Please check your token and try again.",
                        {},
                    )
                elif response.status == 403:
                    logger.warning("API token validation failed: Forbidden")
                    return (
                        False,
                        "API token is forbidden. Please verify your token permissions.",
                        {},
                    )
                else:
                    logger.error(
                        f"Unexpected status during validation: {response.status} - {response_text}"
                    )
                    return (
                        False,
                        f"Validation failed with status {response.status}. Please try again later.",
                        {},
                    )

        except TimeoutError:
            error_msg = "Connection timeout - OpenShock server did not respond in time. Please try again later."
            logger.error(f"Timeout error during token validation: {error_msg}")
            return False, error_msg, {}
        except aiohttp.ClientConnectionError as e:
            error_msg = "Connection error - Unable to reach OpenShock server. Please check your internet connection."
            logger.error(f"Connection error during token validation: {e}")
            return False, error_msg, {}
        except aiohttp.ClientError as e:
            error_msg = f"Network error: {str(e)}"
            logger.exception(f"Network error during token validation: {e}")
            return False, error_msg, {}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Unexpected error during token validation: {e}")
            return False, error_msg, {}

    async def validate_shocker(
        self, api_token: str, shocker_id: str, base_url_override: str | None = None
    ) -> tuple[bool, str, dict]:
        """
        Validate that a specific shocker ID exists and is accessible with the given token

        Returns:
            tuple: (is_valid: bool, message: str, shocker_data: dict)
        """
        # First validate the token and get all shockers
        token_valid, token_msg, token_data = await self.validate_token(
            api_token, base_url_override=base_url_override
        )

        if not token_valid:
            return False, token_msg, {}

        shockers = token_data.get("shockers", [])

        # Look for the specific shocker ID
        for shocker in shockers:
            if shocker.get("id") == shocker_id:
                shocker_name = shocker.get("name", "Unnamed")
                logger.info(f"Shocker {shocker_id} validated successfully: {shocker_name}")
                return True, f"Shocker found: {shocker_name}", shocker

        # Shocker not found
        logger.warning(f"Shocker {shocker_id} not found in user's shockers")
        return (
            False,
            (
                f"Shocker ID not found. Please verify the ID is correct and belongs to your account.\n"
                f"You have {len(shockers)} shocker(s) registered with this token."
            ),
            {},
        )

    async def get_shocker_info(self, api_token: str, shocker_id: str) -> tuple[bool, dict]:
        """
        Get detailed information about a specific shocker

        Returns:
            tuple: (success: bool, shocker_info: dict)
        """
        is_valid, message, shocker_data = await self.validate_shocker(api_token, shocker_id)

        if is_valid:
            return True, {
                "id": shocker_data.get("id"),
                "name": shocker_data.get("name", "Unnamed"),
                "is_paused": shocker_data.get("isPaused", False),
                "is_online": not shocker_data.get("isPaused", True),
                "model": shocker_data.get("model", "Unknown"),
                "created_on": shocker_data.get("createdOn"),
            }
        else:
            return False, {}
