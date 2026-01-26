import asyncio


class APNsClient:
    """Apple Push Notification service client for Wallet pass updates."""

    def __init__(
        self,
        cert_path: str,
        pass_type_id: str,
        use_sandbox: bool = True,
    ):
        self.cert_path = cert_path
        self.pass_type_id = pass_type_id
        self.use_sandbox = use_sandbox
        self._client = None

    def _get_client(self):
        """Get or create the APNs client."""
        if self._client is None:
            from aioapns import APNs
            # aioapns expects a single PEM file with both cert and key
            self._client = APNs(
                client_cert=self.cert_path,
                use_sandbox=self.use_sandbox,
            )
        return self._client

    async def send_pass_update(self, push_token: str) -> bool:
        """
        Send a push notification to update a Wallet pass.

        For Wallet passes, the payload is empty - Apple just signals
        the device to fetch the updated pass from our web service.
        """
        try:
            from aioapns import NotificationRequest

            client = self._get_client()

            # For Wallet passes, Apple requires an empty payload
            # The push just signals the device to fetch the updated pass
            request = NotificationRequest(
                device_token=push_token,
                message={},
                apns_topic=self.pass_type_id,
            )

            response = await client.send_notification(request)

            if response.is_successful:
                print(f"Push sent successfully to {push_token[:20]}...")
                return True
            else:
                print(f"Push failed: {response.status} - {response.description}")
                return False

        except Exception as e:
            print(f"Push error: {e}")
            return False

    async def send_to_all_devices(self, push_tokens: list[str]) -> dict:
        """Send push notifications to multiple devices."""
        results = {"success": 0, "failed": 0}

        # Send notifications concurrently
        tasks = [self.send_pass_update(token) for token in push_tokens]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if outcome is True:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results


def create_apns_client() -> APNsClient:
    """Factory function to create APNsClient from settings."""
    from app.core.config import settings

    return APNsClient(
        cert_path=settings.apns_cert_path,
        pass_type_id=settings.apple_pass_type_id,
        use_sandbox=settings.apns_use_sandbox,
    )
