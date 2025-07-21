"""
Email notification worker for Media Summarizer.

This worker handles sending email notifications to users, including:
- Confirmation emails when a job is submitted
- Error notifications when a job fails
- Completion notifications when a job is finished
"""
import json
import os
import asyncio
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
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def send_email(
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
        async with session.create_client(
            "ses", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL
        ) as ses_client:
            response = await ses_client.send_email(**email_message)
            return response
    else:
        # Use provided client (for testing)
        response = await ses_client.send_email(**email_message)
        return response


async def send_confirmation_email(
    recipient: str,
    job_id: str,
    podcast_title: Optional[str] = None,
    ses_client=None
) -> Dict[str, Any]:
    """
    Send a confirmation email when a podcast processing job is submitted.
    
    Args:
        recipient: Email address of the recipient
        job_id: ID of the processing job
        podcast_title: Title of the podcast (optional)
        ses_client: SES client for testing (optional)
        
    Returns:
        Dict containing the response from SES
    """
    subject = "Your podcast is being processed"
    
    # Create the email body
    if podcast_title:
        body_text = f"Thank you for submitting your podcast '{podcast_title}' for processing.\n\n"
    else:
        body_text = "Thank you for submitting your podcast for processing.\n\n"
        
    body_text += f"Your job ID is: {job_id}\n\n"
    body_text += "We'll send you another email when your summary is ready.\n\n"
    body_text += "The Media Summarizer Team"
    
    # Create HTML version
    if podcast_title:
        body_html = f"""
        <html>
        <body>
            <h2>Thank you for submitting your podcast</h2>
            <p>We've received your request to process the podcast: <strong>{podcast_title}</strong></p>
            <p>Your job ID is: <strong>{job_id}</strong></p>
            <p>We'll send you another email when your summary is ready.</p>
            <p>The Media Summarizer Team</p>
        </body>
        </html>
        """
    else:
        body_html = f"""
        <html>
        <body>
            <h2>Thank you for submitting your podcast</h2>
            <p>We've received your request to process your podcast.</p>
            <p>Your job ID is: <strong>{job_id}</strong></p>
            <p>We'll send you another email when your summary is ready.</p>
            <p>The Media Summarizer Team</p>
        </body>
        </html>
        """
    
    return await send_email(recipient, subject, body_text, body_html)


async def send_error_notification(
    recipient: str,
    job_id: str,
    error_message: str,
    step: Optional[str] = None,
    ses_client=None
) -> Dict[str, Any]:
    """
    Send an error notification when a podcast processing job fails.
    
    Args:
        recipient: Email address of the recipient
        job_id: ID of the processing job
        error_message: Description of the error
        step: Processing step where the error occurred (optional)
        
    Returns:
        Dict containing the response from SES
    """
    subject = "Error processing your podcast"
    
    # Create the email body
    body_text = f"We encountered an error while processing your podcast (Job ID: {job_id}).\n\n"
    
    if step:
        body_text += f"The error occurred during the {step} step.\n\n"
        
    body_text += f"Error details: {error_message}\n\n"
    body_text += "Our team has been notified and will investigate the issue.\n\n"
    body_text += "The Media Summarizer Team"
    
    # Create HTML version
    body_html = f"""
    <html>
    <body>
        <h2>Error Processing Your Podcast</h2>
        <p>We encountered an error while processing your podcast (Job ID: <strong>{job_id}</strong>).</p>
    """
    
    if step:
        body_html += f"<p>The error occurred during the <strong>{step}</strong> step.</p>"
        
    body_html += f"""
        <p>Error details: <em>{error_message}</em></p>
        <p>Our team has been notified and will investigate the issue.</p>
        <p>The Media Summarizer Team</p>
    </body>
    </html>
    """
    
    return await send_email(recipient, subject, body_text, body_html)


async def send_completion_notification(
    recipient: str,
    job_id: str,
    podcast_title: Optional[str] = None,
    summary_url: Optional[str] = None,
    ses_client=None
) -> Dict[str, Any]:
    """
    Send a completion notification when a podcast processing job is finished.
    
    Args:
        recipient: Email address of the recipient
        job_id: ID of the processing job
        podcast_title: Title of the podcast (optional)
        summary_url: URL to access the summary (optional)
        
    Returns:
        Dict containing the response from SES
    """
    subject = "Your podcast summary is ready"
    
    # Create the email body
    if podcast_title:
        body_text = f"Your podcast '{podcast_title}' has been processed successfully.\n\n"
    else:
        body_text = "Your podcast has been processed successfully.\n\n"
        
    body_text += f"Job ID: {job_id}\n\n"
    
    if summary_url:
        body_text += f"You can view your summary here: {summary_url}\n\n"
        
    body_text += "Thank you for using Media Summarizer!\n\n"
    body_text += "The Media Summarizer Team"
    
    # Create HTML version
    body_html = f"""
    <html>
    <body>
        <h2>Your Podcast Summary is Ready</h2>
    """
    
    if podcast_title:
        body_html += f"<p>Your podcast '<strong>{podcast_title}</strong>' has been processed successfully.</p>"
    else:
        body_html += "<p>Your podcast has been processed successfully.</p>"
        
    body_html += f"<p>Job ID: <strong>{job_id}</strong></p>"
    
    if summary_url:
        body_html += f"""
        <p>You can view your summary here: <a href="{summary_url}">{summary_url}</a></p>
        """
        
    body_html += """
        <p>Thank you for using Media Summarizer!</p>
        <p>The Media Summarizer Team</p>
    </body>
    </html>
    """
    
    return await send_email(recipient, subject, body_text, body_html)


def get_queue_url(queue_name: str) -> str:
    """
    Get the URL for an SQS queue.
    
    Args:
        queue_name: Name of the queue
        
    Returns:
        URL of the queue
    """
    if AWS_ENDPOINT_URL:
        # LocalStack format
        return f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"
    else:
        # AWS format (will be resolved by the SQS client)
        return queue_name


async def process_message(message: Dict[str, Any], retries: int = 0, ses_client=None, sqs_client=None) -> None:
    """
    Process an SQS message and send the appropriate email notification.
    
    Args:
        message: SQS message to process
        retries: Number of retries attempted (used internally for retry logic)
        ses_client: SES client for testing (optional)
        sqs_client: SQS client for testing (optional)
    """
    try:
        # Parse the message body
        body = json.loads(message.get("Body", "{}"))
        
        # Extract common fields
        job_id = body.get("job_id")
        recipient = body.get("email")
        notification_type = body.get("notification_type", "confirmation")
        
        if not job_id or not recipient:
            logger.error(f"Missing required fields in message: {body}")
            return
        
        # Send the appropriate notification based on type
        if notification_type == "confirmation":
            podcast_title = body.get("podcast_title")
            await send_confirmation_email(recipient, job_id, podcast_title, ses_client=ses_client)
            logger.info(f"Sent confirmation email for job {job_id} to {recipient}")
            
        elif notification_type == "error":
            error_message = body.get("error", "Unknown error")
            step = body.get("step")
            await send_error_notification(recipient, job_id, error_message, step, ses_client=ses_client)
            logger.info(f"Sent error notification for job {job_id} to {recipient}")
            
        elif notification_type == "completion":
            podcast_title = body.get("podcast_title")
            summary_url = body.get("summary_url")
            await send_completion_notification(recipient, job_id, podcast_title, summary_url, ses_client=ses_client)
            logger.info(f"Sent completion notification for job {job_id} to {recipient}")
            
        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return  # Don't delete the message for unknown notification types
            
        # Delete the message from the queue
        if sqs_client is None:
            async with session.create_client(
                "sqs", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL
            ) as sqs_client:
                queue_url = get_queue_url("email-notification-queue")
                await sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message.get("ReceiptHandle")
                )
        else:
            # Use provided client (for testing)
            queue_url = get_queue_url("email-notification-queue")
            await sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message.get("ReceiptHandle")
            )
            
    except Exception as e:
        logger.error(f"Error processing notification message: {str(e)}")
        
        # Implement retry logic
        if retries < MAX_RETRIES:
            logger.info(f"Retrying in {RETRY_DELAY} seconds (attempt {retries + 1}/{MAX_RETRIES})")
            await asyncio.sleep(RETRY_DELAY * (2 ** retries))  # Exponential backoff
            await process_message(message, retries + 1)
        else:
            logger.error(f"Max retries exceeded for message: {message}")
            # Log the error but don't raise, to avoid crashing the worker
            # In a production environment, this should be reported to a monitoring system


async def poll_queue() -> None:
    """
    Poll the SQS queue for notification messages.
    """
    while True:
        try:
            async with session.create_client(
                "sqs", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL
            ) as sqs_client:
                queue_url = get_queue_url("email-notification-queue")
                
                # Receive messages from the queue
                response = await sqs_client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20  # Long polling
                )
                
                messages = response.get("Messages", [])
                
                if messages:
                    logger.info(f"Received {len(messages)} messages")
                    
                    # Process messages concurrently
                    tasks = [process_message(message) for message in messages]
                    await asyncio.gather(*tasks)
                    
        except Exception as e:
            logger.error(f"Error polling queue: {str(e)}")
            # Wait before retrying
            await asyncio.sleep(5)


async def main() -> None:
    """
    Main entry point for the notification worker.
    """
    logger.info("Starting email notification worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())