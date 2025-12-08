import os
import logging
from typing import Dict, Any, Optional

from media_summarizer.utils import ses

logger = logging.getLogger(__name__)

async def send_ops_alert(
    job_id: str,
    user_email: str,
    error_step: str,
    error_message: str,
    retry_count: int,
    max_retries: int,
    traceback_info: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send detailed technical alert to ops team when a job fails permanently.
    """
    subject = f"🚨 Job Failed Permanently: {job_id}"
    
    # Default to "Not available" if traceback is missing
    traceback_info = traceback_info or "Stack trace not available in notification payload."
    
    body_text = f"""Job Processing Failed After Max Retries

Job ID: {job_id}
User Email: {user_email}
Error Step: {error_step}
Retry Count: {retry_count}/{max_retries}

Error Message:
{error_message}

Stack Trace:
{traceback_info}

CloudWatch Logs:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/media-summarizer-workers

DynamoDB Job:
Job ID: {job_id}

Action Required:
- Investigate the root cause
- Check if this is a recurring issue
- Consider manual retry if appropriate
"""
    
    body_html = f"""
    <html>
    <body style="font-family: monospace; font-size: 12px;">
        <h2 style="color: #e74c3c;">🚨 Job Failed Permanently</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr><td style="font-weight: bold;">Job ID:</td><td>{job_id}</td></tr>
            <tr><td style="font-weight: bold;">User Email:</td><td>{user_email}</td></tr>
            <tr><td style="font-weight: bold;">Error Step:</td><td>{error_step}</td></tr>
            <tr><td style="font-weight: bold;">Retry Count:</td><td>{retry_count}/{max_retries}</td></tr>
        </table>
        
        <h3>Error Message:</h3>
        <pre style="background: #f4f4f4; padding: 10px; border-radius: 5px; white-space: pre-wrap;">{error_message}</pre>
        
        <h3>Stack Trace:</h3>
        <pre style="background: #f4f4f4; padding: 10px; border-radius: 5px; max-height: 300px; overflow-y: auto; white-space: pre-wrap;">{traceback_info}</pre>
        
        <h3>Quick Links:</h3>
        <ul>
            <li><a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/media-summarizer-workers">CloudWatch Logs</a></li>
            <li><a href="https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=processing_jobs">DynamoDB Jobs Table</a></li>
        </ul>
    </body>
    </html>
    """
    
    # Send to ops team email (from environment variable)
    ops_email = os.environ.get("OPS_ALERT_EMAIL", "ops@media-summarizer.com")
    sender = os.environ.get("DEFAULT_EMAIL_SENDER", "alerts@media-summarizer.com")
    
    try:
        response = await ses.send_email(
            recipient=ops_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            sender=sender
        )
        logger.info(f"Sent ops alert for job {job_id} to {ops_email}")
        return response
    except Exception as e:
        logger.error(f"Failed to send ops alert: {e}")
        # Return empty dict or re-raise depending on preference. 
        # Here we log and return empty to not crash the worker.
        return {}
