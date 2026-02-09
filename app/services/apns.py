import asyncio


class APNsClient:
    """Apple Push Notification service client for Wallet pass updates.

    Accepts either a cert file path (legacy) or PEM bytes (per-business).
    When PEM bytes are provided, a temp file is created per push batch.
    """

    def __init__(
        self,
        pass_type_id: str,
        use_sandbox: bool = True,
        cert_path: str | None = None,
        apns_cert_pem: bytes | None = None,
    ):
        if not cert_path and not apns_cert_pem:
            raise ValueError("Either cert_path or apns_cert_pem must be provided")
        self.cert_path = cert_path
        self.apns_cert_pem = apns_cert_pem
        self.pass_type_id = pass_type_id
        self.use_sandbox = use_sandbox
        # Only cache client when using file path (stable across calls)
        self._client = None

    def _get_client(self, cert_path: str | None = None):
        """Get or create the APNs client.

        Args:
            cert_path: Override cert path (for temp file usage).
                       If None, uses self.cert_path with cached client.
        """
        if cert_path:
            # Temp file path — create fresh client (not cached)
            from aioapns import APNs
            return APNs(client_cert=cert_path, use_sandbox=self.use_sandbox)

        if self._client is None:
            from aioapns import APNs
            self._client = APNs(
                client_cert=self.cert_path,
                use_sandbox=self.use_sandbox,
            )
        return self._client

    async def _send_single(self, push_token: str, client) -> bool:
        """Send a single push notification using the given client."""
        try:
            from aioapns import NotificationRequest

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

    async def send_pass_update(self, push_token: str) -> bool:
        """Send a push notification to update a Wallet pass."""
        if self.apns_cert_pem:
            from app.services.certificate_manager import get_certificate_manager
            cert_manager = get_certificate_manager()
            with cert_manager.apns_cert_tempfile(self.apns_cert_pem) as temp_path:
                client = self._get_client(cert_path=temp_path)
                return await self._send_single(push_token, client)
        else:
            client = self._get_client()
            return await self._send_single(push_token, client)

    async def send_to_all_devices(self, push_tokens: list[str]) -> dict:
        """Send push notifications to multiple devices.

        When using PEM bytes, creates one temp file for the entire batch.
        """
        results = {"success": 0, "failed": 0}

        if self.apns_cert_pem:
            from app.services.certificate_manager import get_certificate_manager
            cert_manager = get_certificate_manager()
            with cert_manager.apns_cert_tempfile(self.apns_cert_pem) as temp_path:
                client = self._get_client(cert_path=temp_path)
                tasks = [self._send_single(token, client) for token in push_tokens]
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            client = self._get_client()
            tasks = [self._send_single(token, client) for token in push_tokens]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if outcome is True:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results


def create_apns_client() -> APNsClient:
    """Factory function to create APNsClient from settings (shared certs)."""
    from app.core.config import settings

    return APNsClient(
        cert_path=settings.apns_cert_path,
        pass_type_id=settings.apple_pass_type_id,
        use_sandbox=settings.apns_use_sandbox,
    )


def create_apns_client_for_business(business_id: str) -> APNsClient:
    """Factory function to create APNsClient with per-business certs."""
    from app.core.config import settings
    from app.services.certificate_manager import get_certificate_manager

    cert_manager = get_certificate_manager()
    identifier, _, _, apns_combined = cert_manager.get_certs_for_business(business_id)

    return APNsClient(
        pass_type_id=identifier,
        use_sandbox=settings.apns_use_sandbox,
        apns_cert_pem=apns_combined,
    )


def create_demo_apns_client() -> APNsClient:
    """Factory function to create APNsClient for demo passes."""
    from app.core.config import settings

    return APNsClient(
        cert_path=settings.demo_apns_cert_path,
        pass_type_id=settings.demo_pass_type_id,
        use_sandbox=settings.apns_use_sandbox,
    )
