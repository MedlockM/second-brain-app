"""
Email service for sending notifications (welcome emails, etc.).
"""
import os
import logging
from typing import Optional, Dict, Any
import aioboto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)

# Email configuration
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@example.com")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


# Session for SES (created lazily)
_session = None

def get_session():
    """Get or create aioboto3 session."""
    global _session
    if _session is None:
        _session = aioboto3.Session(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
    return _session


class EmailService:
    """Service for sending emails via AWS SES."""

    def __init__(self):
        # Read environment at initialization to allow test-time overrides
        self.from_email = os.environ.get("FROM_EMAIL", FROM_EMAIL)
        self.frontend_url = os.environ.get("FRONTEND_URL", FRONTEND_URL)
        self.email_verification_expire_hours = int(os.environ.get("EMAIL_VERIFICATION_EXPIRE_HOURS", "24"))

    async def send_email_verification(self, email: str, verification_token: str) -> bool:
        """
        Send an email verification link to the user.
        """
        try:
            verify_link = f"{self.frontend_url}/verify-email?token={verification_token}&email={email}"
            subject = "Verify your email - Media Summarizer"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset=\"utf-8\">
                <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
                <title>Verify your email - Media Summarizer</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #22c1c3 0%, #fdbb2d 100%); color: white; padding: 24px; text-align: center; border-radius: 8px 8px 0 0; }}
                    .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 8px 8px; }}
                    .button {{ display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }}
                    .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 12px; border-radius: 6px; margin: 16px 0; }}
                    .code {{ word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 3px; font-family: monospace; }}
                </style>
            </head>
            <body>
                <div class=\"header\">
                    <h1>Confirm your email</h1>
                </div>
                <div class=\"content\">
                    <p>Thanks for creating an account at Media Summarizer.</p>
                    <p>Please confirm that <strong>{email}</strong> is your email address by clicking the button below:</p>
                    <p style=\"text-align: center;\"><a href=\"{verify_link}\" class=\"button\">Verify email</a></p>
                    <div class=\"warning\">This link will expire in {self.email_verification_expire_hours} hours.</div>
                    <p>If the button doesn’t work, copy and paste this link:</p>
                    <p class=\"code\">{verify_link}</p>
                    <p>If you didn’t create this account, you can safely ignore this email.</p>
                </div>
            </body>
            </html>
            """

            text_body = f"""
            Verify your email for Media Summarizer

            Please open this link to verify your email ({email}):

            {verify_link}

            This link will expire in {self.email_verification_expire_hours} hours.

            If you didn't create this account, you can ignore this email.
            """

            return await self._send_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )
        except Exception as e:
            logger.error(f"Error sending verification email to {email}: {str(e)}")
            return False

    async def send_welcome_email(self, email: str, credits: int = 100) -> bool:
        """
        Send a welcome email to new users.

        Args:
            email: Recipient email address
            credits: Number of initial credits

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            subject = "Welcome to Media Summarizer!"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to Media Summarizer</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                    }}
                    .content {{
                        background: #f8f9fa;
                        padding: 30px;
                        border-radius: 0 0 8px 8px;
                    }}
                    .credits-box {{
                        background: #d4edda;
                        border: 1px solid #c3e6cb;
                        color: #155724;
                        padding: 15px;
                        border-radius: 5px;
                        text-align: center;
                        margin: 20px 0;
                    }}
                    .footer {{
                        text-align: center;
                        color: #6c757d;
                        font-size: 14px;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎧 Welcome to Media Summarizer!</h1>
                    <p>Turn your podcasts into digestible summaries</p>
                </div>

                <div class="content">
                    <h2>Thanks for joining us!</h2>
                    <p>Your account has been created successfully. We're excited to help you get more value from your favorite podcasts.</p>

                    <div class="credits-box">
                        <h3>🎁 Welcome Bonus</h3>
                        <p><strong>{credits} credits</strong> have been added to your account!</p>
                        <p>Each credit allows you to summarize one podcast episode.</p>
                    </div>

                    <h3>What's Next?</h3>
                    <ul>
                        <li>🎵 Find a podcast episode you want to summarize</li>
                        <li>📝 Get an AI-powered summary in minutes</li>
                        <li>⚡ Save time and extract key insights</li>
                    </ul>

                    <p>Ready to get started? Visit our platform and submit your first podcast URL!</p>

                    <p style="text-align: center;">
                        <a href="{self.frontend_url}" style="display: inline-block; background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            Start Summarizing
                        </a>
                    </p>
                </div>

                <div class="footer">
                    <p>Happy summarizing!</p>
                    <p>The Media Summarizer Team</p>
                </div>
            </body>
            </html>
            """

            text_body = f"""
            Welcome to Media Summarizer!

            Thanks for joining us! Your account has been created successfully.

            Welcome Bonus: {credits} credits have been added to your account!
            Each credit allows you to summarize one podcast episode.

            What's Next?
            - Find a podcast episode you want to summarize
            - Get an AI-powered summary in minutes
            - Save time and extract key insights

            Ready to get started? Visit: {self.frontend_url}

            Happy summarizing!
            The Media Summarizer Team
            """

            return await self._send_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

        except Exception as e:
            logger.error(f"Error sending welcome email to {email}: {str(e)}")
            return False

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Send an email via AWS SES.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body
            reply_to: Optional reply-to address

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            session = get_session()
            async with session.client('ses', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION) as ses_client:

                # Prepare email message
                message = {
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                    }
                }

                # Prepare destination
                destination = {'ToAddresses': [to_email]}

                # Prepare reply-to if provided
                reply_to_addresses = [reply_to] if reply_to else []

                # Send email
                response = await ses_client.send_email(
                    Source=self.from_email,
                    Destination=destination,
                    Message=message,
                    ReplyToAddresses=reply_to_addresses
                )

                message_id = response.get('MessageId')
                logger.info(f"Email sent successfully to {to_email}, MessageId: {message_id}")
                return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES error sending email to {to_email}: {error_code} - {error_message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")
            return False

    async def verify_email_address(self, email: str) -> bool:
        """
        Verify an email address with SES (for development/testing).

        Args:
            email: Email address to verify

        Returns:
            True if verification was initiated successfully
        """
        try:
            session = get_session()
            async with session.client('ses', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION) as ses_client:

                await ses_client.verify_email_identity(EmailAddress=email)
                logger.info(f"Email verification initiated for {email}")
                return True

        except ClientError as e:
            logger.error(f"Error verifying email {email}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error verifying email {email}: {str(e)}")
            return False

    async def check_sending_quota(self) -> Dict[str, Any]:
        """
        Check the current SES sending quota and statistics.

        Returns:
            Dictionary with quota information
        """
        try:
            session = get_session()
            async with session.client('ses', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION) as ses_client:

                quota_response = await ses_client.get_send_quota()
                stats_response = await ses_client.get_send_statistics()

                return {
                    'max_24_hour_send': quota_response.get('Max24HourSend', 0),
                    'max_send_rate': quota_response.get('MaxSendRate', 0),
                    'sent_last_24_hours': quota_response.get('SentLast24Hours', 0),
                    'send_data_points': stats_response.get('SendDataPoints', [])
                }

        except ClientError as e:
            logger.error(f"Error checking SES quota: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error checking SES quota: {str(e)}")
            return {}


# Singleton instance
email_service = EmailService()
