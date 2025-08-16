"""
SES utilities for email operations.

This module provides async utility functions for interacting
with Amazon SES in the Media Summarizer application using aiobotocore.
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


async def send_email(
    recipient: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    reply_to: Optional[List[str]] = None
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

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error sending the email
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

    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.send_email(**email_message)
            logger.info(f"Email sent to {recipient}: {response['MessageId']}")
            return response
    except Exception as e:
        logger.error(f"Error sending email to {recipient}: {str(e)}")
        raise


async def send_bulk_email(
    recipients: List[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    reply_to: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send a bulk email to multiple recipients using Amazon SES.

    Args:
        recipients: List of email addresses
        subject: Email subject
        body_text: Plain text email body
        body_html: HTML email body (optional)
        sender: Email address of the sender (optional, defaults to DEFAULT_SENDER)
        reply_to: List of reply-to email addresses (optional)

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error sending the email
    """
    if not sender:
        sender = DEFAULT_SENDER

    if not reply_to:
        reply_to = [DEFAULT_SENDER]

    email_message = {
        "Destination": {
            "ToAddresses": recipients
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

    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.send_email(**email_message)
            logger.info(f"Bulk email sent to {len(recipients)} recipients: {response['MessageId']}")
            return response
    except Exception as e:
        logger.error(f"Error sending bulk email: {str(e)}")
        raise


async def send_raw_email(
    raw_message: str,
    sender: Optional[str] = None,
    destinations: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send a raw email message using Amazon SES.

    Args:
        raw_message: Raw email message (including headers)
        sender: Email address of the sender (optional, defaults to DEFAULT_SENDER)
        destinations: List of destination email addresses (optional)

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error sending the email
    """
    if not sender:
        sender = DEFAULT_SENDER

    raw_email_params = {
        "Source": sender,
        "RawMessage": {
            "Data": raw_message
        }
    }

    if destinations:
        raw_email_params["Destinations"] = destinations

    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.send_raw_email(**raw_email_params)
            logger.info(f"Raw email sent: {response['MessageId']}")
            return response
    except Exception as e:
        logger.error(f"Error sending raw email: {str(e)}")
        raise


async def send_templated_email(
    recipient: str,
    template_name: str,
    template_data: Dict[str, Any],
    sender: Optional[str] = None,
    reply_to: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send an email using an SES template.

    Args:
        recipient: Email address of the recipient
        template_name: Name of the SES template to use
        template_data: Data to substitute in the template
        sender: Email address of the sender (optional, defaults to DEFAULT_SENDER)
        reply_to: List of reply-to email addresses (optional)

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error sending the email
    """
    if not sender:
        sender = DEFAULT_SENDER

    if not reply_to:
        reply_to = [DEFAULT_SENDER]

    templated_email_params = {
        "Source": sender,
        "Destination": {
            "ToAddresses": [recipient]
        },
        "ReplyToAddresses": reply_to,
        "Template": template_name,
        "TemplateData": str(template_data) if isinstance(template_data, dict) else template_data
    }

    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.send_templated_email(**templated_email_params)
            logger.info(f"Templated email sent to {recipient}: {response['MessageId']}")
            return response
    except Exception as e:
        logger.error(f"Error sending templated email to {recipient}: {str(e)}")
        raise


async def verify_email_identity(email: str) -> Dict[str, Any]:
    """
    Verify an email address for use with Amazon SES.

    Args:
        email: Email address to verify

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error verifying the email
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.verify_email_identity(EmailAddress=email)
            logger.info(f"Email verification initiated for {email}")
            return response
    except Exception as e:
        logger.error(f"Error verifying email {email}: {str(e)}")
        raise


async def get_send_quota() -> Dict[str, Any]:
    """
    Get the send quota for the AWS account.

    Returns:
        Dict containing send quota information

    Raises:
        Exception: If there's an error getting the send quota
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.get_send_quota()
            logger.info("Retrieved SES send quota")
            return response
    except Exception as e:
        logger.error(f"Error getting send quota: {str(e)}")
        raise


async def get_send_statistics() -> Dict[str, Any]:
    """
    Get send statistics for the AWS account.

    Returns:
        Dict containing send statistics

    Raises:
        Exception: If there's an error getting send statistics
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.get_send_statistics()
            logger.info("Retrieved SES send statistics")
            return response
    except Exception as e:
        logger.error(f"Error getting send statistics: {str(e)}")
        raise


async def list_verified_email_addresses() -> List[str]:
    """
    List all verified email addresses for the AWS account.

    Returns:
        List of verified email addresses

    Raises:
        Exception: If there's an error listing verified emails
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.list_verified_email_addresses()
            emails = response.get('VerifiedEmailAddresses', [])
            logger.info(f"Retrieved {len(emails)} verified email addresses")
            return emails
    except Exception as e:
        logger.error(f"Error listing verified email addresses: {str(e)}")
        raise


async def create_template(
    template_name: str,
    subject: str,
    text_part: str,
    html_part: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an email template in SES.

    Args:
        template_name: Name of the template
        subject: Subject line template (can include {{variables}})
        text_part: Text body template (can include {{variables}})
        html_part: HTML body template (optional, can include {{variables}})

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error creating the template
    """
    template = {
        "TemplateName": template_name,
        "Subject": subject,
        "TextPart": text_part
    }

    if html_part:
        template["HtmlPart"] = html_part

    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.create_template(Template=template)
            logger.info(f"Email template created: {template_name}")
            return response
    except Exception as e:
        logger.error(f"Error creating email template {template_name}: {str(e)}")
        raise


async def delete_template(template_name: str) -> Dict[str, Any]:
    """
    Delete an email template from SES.

    Args:
        template_name: Name of the template to delete

    Returns:
        Dict containing the response from SES

    Raises:
        Exception: If there's an error deleting the template
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.delete_template(TemplateName=template_name)
            logger.info(f"Email template deleted: {template_name}")
            return response
    except Exception as e:
        logger.error(f"Error deleting email template {template_name}: {str(e)}")
        raise


async def get_template(template_name: str) -> Dict[str, Any]:
    """
    Get an email template from SES.

    Args:
        template_name: Name of the template to retrieve

    Returns:
        Dict containing the template information

    Raises:
        Exception: If there's an error getting the template
    """
    try:
        async with session.create_client(
            'ses',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as ses:
            response = await ses.get_template(TemplateName=template_name)
            logger.info(f"Retrieved email template: {template_name}")
            return response
    except Exception as e:
        logger.error(f"Error getting email template {template_name}: {str(e)}")
        raise
