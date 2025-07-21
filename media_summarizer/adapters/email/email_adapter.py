"""
Email adapter for Media Summarizer.

This adapter provides an interface for sending emails using Amazon SES.
It handles email formatting, sending, and error handling.
"""
import os
import logging
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")

# Import AWS session
try:
    from aiobotocore.session import get_session
    session = get_session()
except ImportError:
    logger.error("aiobotocore is not installed. Please install it with 'pip install aiobotocore'.")
    raise

# Email configuration
DEFAULT_SENDER = os.environ.get("DEFAULT_EMAIL_SENDER", "noreply@media-summarizer.com")


class EmailAdapter:
    """
    Adapter for sending emails using Amazon SES.
    """
    
    def __init__(self, region_name: Optional[str] = None, endpoint_url: Optional[str] = None):
        """
        Initialize the email adapter.
        
        Args:
            region_name: AWS region name (optional, defaults to AWS_REGION)
            endpoint_url: AWS endpoint URL (optional, defaults to AWS_ENDPOINT_URL)
        """
        self.region_name = region_name or AWS_REGION
        self.endpoint_url = endpoint_url or AWS_ENDPOINT_URL
        self.session = get_session()
    
    async def send_email(
        self,
        recipient: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender: Optional[str] = None,
        reply_to: Optional[List[str]] = None,
        ses_client=None
    ) -> Dict[str, Any]:
        """
        Send an email using Amazon SES.
        
        Args:
            recipient: Email address of the recipient
            subject: Email subject
            body_text: Plain text email body
            body_html: HTML email body (optional)
            sender: Email address of the sender (optional, defaults to DEFAULT_SENDER)
            reply_to: List of reply-to email addresses (optional)
            ses_client: SES client for testing (optional)
            
        Returns:
            Dict containing the response from SES
            
        Raises:
            ClientError: If there's an error sending the email
        """
        if not sender:
            sender = DEFAULT_SENDER
            
        if not reply_to:
            reply_to = [DEFAULT_SENDER]
            
        email_message = {
            "Destination": {
                "ToAddresses": [recipient]
            },
            "Message": {
                "Body": {
                    "Text": {
                        "Charset": "UTF-8",
                        "Data": body_text
                    }
                },
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": subject
                }
            },
            "Source": sender,
            "ReplyToAddresses": reply_to
        }
        
        # Add HTML body if provided
        if body_html:
            email_message["Message"]["Body"]["Html"] = {
                "Charset": "UTF-8",
                "Data": body_html
            }
        
        # Send the email
        if ses_client is None:
            async with self.session.create_client(
                "ses", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as ses_client:
                response = await ses_client.send_email(**email_message)
                return response
        else:
            # Use provided client (for testing)
            response = await ses_client.send_email(**email_message)
            return response
    
    async def send_template_email(
        self,
        recipient: str,
        template_name: str,
        template_data: Dict[str, Any],
        sender: Optional[str] = None,
        reply_to: Optional[List[str]] = None,
        ses_client=None
    ) -> Dict[str, Any]:
        """
        Send a templated email using Amazon SES.
        
        Args:
            recipient: Email address of the recipient
            template_name: Name of the SES template to use
            template_data: Data to populate the template
            sender: Email address of the sender (optional, defaults to DEFAULT_SENDER)
            reply_to: List of reply-to email addresses (optional)
            ses_client: SES client for testing (optional)
            
        Returns:
            Dict containing the response from SES
            
        Raises:
            ClientError: If there's an error sending the email
        """
        if not sender:
            sender = DEFAULT_SENDER
            
        if not reply_to:
            reply_to = [DEFAULT_SENDER]
            
        email_message = {
            "Destination": {
                "ToAddresses": [recipient]
            },
            "Template": template_name,
            "TemplateData": template_data,
            "Source": sender,
            "ReplyToAddresses": reply_to
        }
        
        # Send the email
        if ses_client is None:
            async with self.session.create_client(
                "ses", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as ses_client:
                response = await ses_client.send_templated_email(**email_message)
                return response
        else:
            # Use provided client (for testing)
            response = await ses_client.send_templated_email(**email_message)
            return response
    
    async def verify_email_identity(self, email_address: str, ses_client=None) -> Dict[str, Any]:
        """
        Verify an email identity with Amazon SES.
        
        Args:
            email_address: Email address to verify
            ses_client: SES client for testing (optional)
            
        Returns:
            Dict containing the response from SES
            
        Raises:
            ClientError: If there's an error verifying the email identity
        """
        # Verify the email identity
        if ses_client is None:
            async with self.session.create_client(
                "ses", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as ses_client:
                response = await ses_client.verify_email_identity(EmailAddress=email_address)
                return response
        else:
            # Use provided client (for testing)
            response = await ses_client.verify_email_identity(EmailAddress=email_address)
            return response
    
    async def get_send_quota(self, ses_client=None) -> Dict[str, Any]:
        """
        Get the SES sending quota.
        
        Args:
            ses_client: SES client for testing (optional)
            
        Returns:
            Dict containing the response from SES
            
        Raises:
            ClientError: If there's an error getting the sending quota
        """
        # Get the sending quota
        if ses_client is None:
            async with self.session.create_client(
                "ses", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as ses_client:
                response = await ses_client.get_send_quota()
                return response
        else:
            # Use provided client (for testing)
            response = await ses_client.get_send_quota()
            return response
    
    async def get_send_statistics(self, ses_client=None) -> Dict[str, Any]:
        """
        Get the SES sending statistics.
        
        Args:
            ses_client: SES client for testing (optional)
            
        Returns:
            Dict containing the response from SES
            
        Raises:
            ClientError: If there's an error getting the sending statistics
        """
        # Get the sending statistics
        if ses_client is None:
            async with self.session.create_client(
                "ses", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as ses_client:
                response = await ses_client.get_send_statistics()
                return response
        else:
            # Use provided client (for testing)
            response = await ses_client.get_send_statistics()
            return response