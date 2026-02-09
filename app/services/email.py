import logging
import resend
from app.core.config import get_settings

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Admin",
    "scanner": "Scanner",
}


class EmailService:
    """Service for sending emails via Resend."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.resend_api_key
        resend.api_key = self.api_key
        self.web_app_url = settings.web_app_url

        # Log configuration status (without exposing full key)
        if self.api_key:
            logger.info(f"Resend configured with key: {self.api_key[:10]}...")
        else:
            logger.warning("RESEND_API_KEY is not set!")

    def send_invitation(
        self,
        to: str,
        invitee_name: str | None,
        inviter_name: str,
        business_name: str,
        role: str,
        token: str,
    ) -> bool:
        """Send an invitation email."""
        invite_url = f"{self.web_app_url}/invite/{token}"
        role_label = ROLE_LABELS.get(role, role)
        greeting = f"Hi {invitee_name}," if invitee_name else "Hi there,"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">You're Invited!</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="font-size: 16px; margin-top: 0;">{greeting}</p>
        <p style="font-size: 16px;">
            <strong>{inviter_name}</strong> has invited you to join
            <strong>{business_name}</strong> on Stampeo as a <strong>{role_label}</strong>.
        </p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{invite_url}"
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white;
                      padding: 14px 28px;
                      text-decoration: none;
                      border-radius: 8px;
                      font-weight: 600;
                      display: inline-block;">
                Accept Invitation
            </a>
        </div>
        <p style="font-size: 14px; color: #666;">
            This invitation expires in 7 days.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; margin-bottom: 0;">
            If you didn't expect this invitation, you can safely ignore this email.
        </p>
    </div>
    <div style="text-align: center; padding: 20px;">
        <p style="font-size: 12px; color: #999; margin: 0;">
            – The Stampeo Team
        </p>
    </div>
</body>
</html>
"""

        try:
            logger.info(f"Sending invitation email to {to} (invite URL: {invite_url})")
            result = resend.Emails.send({
                "from": "Stampeo <noreply@contact.stampeo.app>",
                "to": [to],
                "subject": f"You've been invited to join {business_name} on Stampeo",
                "html": html_content,
            })
            logger.info(f"Email sent successfully: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send invitation email to {to}: {e}")
            raise

    def send_activation_email(
        self,
        to: str,
        owner_name: str,
        business_name: str,
    ) -> bool:
        """Send an account activation email to a business owner."""
        greeting = f"Hi {owner_name}," if owner_name else "Hi there,"
        dashboard_url = self.web_app_url

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); padding: 30px; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Your account is activated!</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="font-size: 16px; margin-top: 0;">{greeting}</p>
        <p style="font-size: 16px;">
            Great news! <strong>{business_name}</strong> has been activated on Stampeo.
            You can now start issuing loyalty cards to your customers.
        </p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{dashboard_url}"
               style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
                      color: white;
                      padding: 14px 28px;
                      text-decoration: none;
                      border-radius: 8px;
                      font-weight: 600;
                      display: inline-block;">
                Go to Dashboard
            </a>
        </div>
        <p style="font-size: 14px; color: #666;">
            Welcome to the Stampeo founding partner program! As an early partner,
            you'll help shape the product and enjoy lifetime founder pricing.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; margin-bottom: 0;">
            If you have any questions, just reply to this email.
        </p>
    </div>
    <div style="text-align: center; padding: 20px;">
        <p style="font-size: 12px; color: #999; margin: 0;">
            – The Stampeo Team
        </p>
    </div>
</body>
</html>
"""

        try:
            logger.info(f"Sending activation email to {to} for business {business_name}")
            result = resend.Emails.send({
                "from": "Stampeo <noreply@contact.stampeo.app>",
                "to": [to],
                "subject": f"Your {business_name} account is now active on Stampeo!",
                "html": html_content,
            })
            logger.info(f"Activation email sent successfully: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send activation email to {to}: {e}")
            raise

    def send_pass_email(
        self,
        to: str,
        customer_name: str | None,
        business_name: str,
        pass_url: str,
        google_wallet_url: str | None = None,
    ) -> bool:
        """Send a loyalty card pass download email to a customer."""
        greeting = f"Hi {customer_name}," if customer_name else "Hi there,"

        # Build wallet buttons - always show Apple, conditionally show Google
        apple_button = f"""
            <a href="{pass_url}"
               style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
                      color: white;
                      padding: 14px 28px;
                      text-decoration: none;
                      border-radius: 8px;
                      font-weight: 600;
                      display: inline-block;">
                Add to Apple Wallet
            </a>
        """

        google_button = ""
        if google_wallet_url:
            google_button = f"""
            <a href="{google_wallet_url}"
               style="background: #1a1a1a;
                      color: white;
                      padding: 14px 28px;
                      text-decoration: none;
                      border-radius: 8px;
                      font-weight: 600;
                      display: inline-block;
                      margin-top: 12px;">
                Add to Google Wallet
            </a>
            """

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); padding: 30px; border-radius: 10px 10px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Your Loyalty Card</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="font-size: 16px; margin-top: 0;">{greeting}</p>
        <p style="font-size: 16px;">
            Here's your loyalty card for <strong>{business_name}</strong>.
            Add it to your wallet to start collecting stamps!
        </p>
        <div style="text-align: center; margin: 30px 0;">
            {apple_button}
            {google_button}
        </div>
        <p style="font-size: 14px; color: #666;">
            Once added to your wallet, your card will automatically update when you earn stamps.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="font-size: 12px; color: #999; margin-bottom: 0;">
            If you didn't request this, you can safely ignore this email.
        </p>
    </div>
    <div style="text-align: center; padding: 20px;">
        <p style="font-size: 12px; color: #999; margin: 0;">
            – The Stampeo Team
        </p>
    </div>
</body>
</html>
"""

        try:
            logger.info(f"Sending pass email to {to} for business {business_name}")
            result = resend.Emails.send({
                "from": "Stampeo <noreply@contact.stampeo.app>",
                "to": [to],
                "subject": f"Your {business_name} loyalty card",
                "html": html_content,
            })
            logger.info(f"Pass email sent successfully: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send pass email to {to}: {e}")
            raise


# Singleton instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
