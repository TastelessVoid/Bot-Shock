# Empty file to make utils a package
"""
OpenShock API client for handling all API communication
"""
import logging

import aiohttp

logger = logging.getLogger("BotShock.APIClient")


class OpenShockAPIClient:
    """Handles all communication with the OpenShock API"""

    def __init__(self, api_url: str = "https://api.openshock.app/2/shockers/control"):
        self.api_url = api_url

    async def send_control(
        self,
        api_token: str,
        shocker_id: str,
        shock_type: str,
        intensity: int,
        duration: int,
        custom_name: str = "Discord Bot",
    ) -> tuple[bool, int, str]:
        """
        Send a control command to the OpenShock API

        Returns:
            tuple: (success: bool, status_code: int, response_text: str)
        """
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
            logger.debug(f"Sending control request to {self.api_url}")
            async with aiohttp.ClientSession() as session, session.post(
                self.api_url, json=payload, headers=headers
            ) as response:
                response_text = await response.text()
                success = response.status == 200

                if success:
                    logger.info(
                        f"Control successful | Type: {shock_type} | "
                        f"Intensity: {intensity}% | Duration: {duration}ms"
                    )
                else:
                    logger.error(
                        f"Control failed | Status: {response.status} | Response: {response_text}"
                    )

                return success, response.status, response_text

        except aiohttp.ClientError as e:
            logger.exception(f"HTTP error during control request: {e}")
            return False, 0, str(e)
        except Exception as e:
            logger.exception(f"Unexpected error during control request: {e}")
            return False, 0, str(e)
