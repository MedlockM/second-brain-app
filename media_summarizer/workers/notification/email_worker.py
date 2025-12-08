"""
Email notification worker for Media Summarizer.

This worker handles sending email notifications to users, including:
- Error notifications when a job fails
- Completion notifications when a job is finished

Migrated to use the new utils for SES, SQS, and database operations.
"""
import json
import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from media_summarizer.utils import ses, sqs, database_async, episode_idempotence
from media_summarizer.core.models import JobStatus
from media_summarizer.workers.notification.ops_alert import send_ops_alert

# ... (imports existants)

async def process_message(message: Dict[str, Any], retries: int = 0, ses_client: Optional[Any] = None) -> None:
    """
    Process an SQS message and send the appropriate email notification.

    Args:
        message: SQS message to process
        retries: Number of retries attempted (used internally for retry logic)
    """
    try:
        # Parse the message body
        body = json.loads(message.get("Body", "{}"))

        # Extract common fields
        job_id = body.get("job_id")
        recipient = body.get("email")
        notification_type = body.get("notification_type")

        if not job_id or not recipient:
            logger.error(f"Missing required fields in message: {body}")
            return

        # Mark job as notifying before sending any email
        # BUT only if it's not an error notification (failed jobs should stay failed)
        job = None
        try:
            job = await database_async.get_processing_job_by_id(job_id)
            if job and notification_type != "error":
                job.mark_notifying()
                await database_async.update_processing_job(job)
        except Exception as e:
            logger.error(f"Error updating job status to notifying: {str(e)}")

        # Send the appropriate notification based on type
        if notification_type == "error":
            error_message = body.get("error", "Unknown error")
            step = body.get("step")
            traceback_info = body.get("traceback")
            
            # 1. Send user-friendly error email
            await send_error_notification(recipient, job_id, error_message, step)
            logger.info(f"Sent error notification for job {job_id} to {recipient}")

            # 2. Send Ops Alert (Technical details)
            if job:
                try:
                    await send_ops_alert(
                        job_id=job_id,
                        user_email=recipient,
                        error_step=step or "unknown",
                        error_message=error_message,
                        retry_count=job.retry_count,
                        max_retries=job.max_retries,
                        traceback_info=traceback_info
                    )
                except Exception as ops_e:
                    logger.error(f"Failed to send ops alert for job {job_id}: {ops_e}")

            # Idempotence: mark failed only for canonical processing jobs (skip cache-only emails)
            try:
                # Refresh job from DB just in case, or use existing 'job' object
                # (using existing 'job' object is fine as we just updated it to notifying)
                from_cache = body.get("from_cache", False)
                if job and getattr(job, "episode_guid", None) and not from_cache:
                    await episode_idempotence.mark_failed(job.episode_guid, job.id)
            except Exception as e:
                logger.error(f"Error marking idempotence failed: {str(e)}")

        elif notification_type == "completion":
    recipient: str,
    job_id: str,
    error_message: str,
    step: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send an error notification when a podcast processing job fails permanently.
    This is only sent after all retries have been exhausted.
    
    Args:
        recipient: Email address of the recipient
        job_id: ID of the processing job
        error_message: Description of the error (for internal logging only)
        step: Processing step where the error occurred (for internal logging only)

    Returns:
        Dict containing the response from SES
    """
    subject = "Unable to Process Your Podcast Episode"

    # Create user-friendly email body (NO technical details)
    body_text = """We're sorry, but we were unable to process your podcast episode.

Our team has been notified and is working to resolve the issue.

We apologize for any inconvenience this may cause.

Best regards,
The Media Summarizer Team"""

    # Create HTML version
    body_html = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #e74c3c;">Unable to Process Your Podcast Episode</h2>
            <p>We're sorry, but we were unable to process your podcast episode.</p>
            <p>Our team has been notified and is working to resolve the issue.</p>
            <p>We apologize for any inconvenience this may cause.</p>
            <p style="margin-top: 30px;">Best regards,<br>The Media Summarizer Team</p>
        </div>
    </body>
    </html>
    """

    # Log technical details for debugging (not sent to user)
    logger.error(
        "Sending error notification to user after max retries",
        extra={
            "job_id": job_id,
            "recipient": recipient,
            "error_step": step,
            "error_message": error_message
        }
    )

    return await ses.send_email(
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sender=DEFAULT_SENDER
    )


async def send_completion_notification(
    recipient: str,
    job_id: str,
    podcast_title: Optional[str] = None,
    episode_title: Optional[str] = None,
    summary_content: Optional[Dict[str, Any]] = None,
    quiz: Optional[Dict[str, Any]] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a completion notification when a podcast processing job is finished.

    Args:
        recipient: Email address of the recipient
        job_id: ID of the processing job
        podcast_title: Title of the podcast (optional)
        episode_title: Title of the episode (optional)
        summary_content: The actual summary content (optional)

    Returns:
        Dict containing the response from SES
    """
    subject = "Your podcast summary is ready"
    # If a quiz is present, render interactive/AMP email with quiz first
    if quiz:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            from media_summarizer.utils.mime_builder import build_multipart_amp_email

            templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "email_templates", "quiz")
            templates_dir = os.path.abspath(templates_dir)
            env = Environment(
                loader=FileSystemLoader(templates_dir),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )

            ui_strings = {
                "intro": "Answer the quiz below, then reveal the summary.",
                "correct": "Correct",
                "incorrect": "Incorrect",
                "your_score": "Your Score",
                "score_note": "Select answers for each question to update your score.",
                "reveal_summary": "Reveal Summary",
                "main_topics": "Main topics",
                "key_points": "Key points",
                "notable_quotes": "Notable quotes",
                "conclusion": "Conclusion",
                "prev": "Previous",
                "next": "Next",
                "final_note": "You can review your selections above.",
                "compat_note": "Interactive behavior works best in iOS/Apple/Samsung Mail. Others will see the static version.",
                "fallback_note": "Your email client does not support interactive content. Here is a static version of the quiz:",
                "intro_text": "Quiz (static view):",
            }

            brand = {
                "primary_start": "#2563eb",  # blue-600
                "primary_end": "#9333ea",    # purple-600
                "bg_from": "#eff6ff",       # blue-50
                "bg_to": "#faf5ff",         # purple-50
                "text": "#111827",          # gray-900
                "muted": "#6b7280",         # gray-500/600 mid
                "border": "#e5e7eb",        # gray-200
                "correct_bg": "#dcfce7",    # green-100
                "correct_text": "#166534",   # green-700
                "incorrect_bg": "#fee2e2",  # red-100
                "incorrect_text": "#991b1b", # red-800
                "button_text": "#ffffff",
            }

            context = {
                "podcast_title": podcast_title or "",
                "episode_title": episode_title or "",
                "quiz": quiz,
                "summary": summary_content or {},
                "ui_strings": ui_strings,
                "brand": brand,
            }

            amp_html = env.get_template("quiz_amp.html.j2").render(**context)
            interactive_html = env.get_template("quiz_interactive.html.j2").render(**context)
            fallback_html = env.get_template("quiz_fallback.html.j2").render(**context)
            text_part = env.get_template("quiz.txt.j2").render(**context)

            # Compose multipart/alternative with AMP and HTML (interactive as primary HTML, with fallback below via noscript-like copy)
            # For the HTML part, we can prefer the interactive version; some clients will ignore unsupported CSS.
            html_combined = interactive_html

            raw_message = build_multipart_amp_email(
                subject=subject,
                from_addr=os.environ.get("FROM_EMAIL", "noreply@example.com"),
                to_addr=recipient,
                text_part=text_part,
                amp_part=amp_html,
                html_part=html_combined,
            )

            await ses.send_raw_email(raw_message=raw_message)
            logger.info(f"Sent quiz+summary AMP email for job {job_id} to {recipient}")
            return {"MessageId": "raw-amp"}
        except Exception as e:
            logger.error(f"Failed to send AMP/interactive email, fallback to simple HTML: {e}")
    # Fallback to simple HTML/text (legacy path)

    # Create the email body with summary content
    body_text = "Your podcast summary is ready!\n\n"

    if podcast_title:
        body_text += f"Podcast: {podcast_title}\n"
    if episode_title:
        body_text += f"Episode: {episode_title}\n"

    body_text += f"Job ID: {job_id}\n\n"

    # Include the actual summary content
    if summary_content:
        body_text += "SUMMARY:\n"
        body_text += "=" * 50 + "\n\n"

        if isinstance(summary_content, dict):
            if "main_topics" in summary_content:
                body_text += "MAIN TOPICS:\n"
                if isinstance(summary_content["main_topics"], list):
                    for topic in summary_content["main_topics"]:
                        body_text += f"• {topic}\n"
                else:
                    body_text += f"{summary_content['main_topics']}\n"
                body_text += "\n"

            if "key_points" in summary_content:
                body_text += "KEY POINTS:\n"
                if isinstance(summary_content["key_points"], list):
                    for point in summary_content["key_points"]:
                        body_text += f"• {point}\n"
                else:
                    body_text += f"{summary_content['key_points']}\n"
                body_text += "\n"

            if "notable_quotes" in summary_content and summary_content["notable_quotes"]:
                body_text += "NOTABLE QUOTES:\n"
                if isinstance(summary_content["notable_quotes"], list):
                    for quote in summary_content["notable_quotes"]:
                        body_text += f"• \"{quote}\"\n"
                else:
                    body_text += f"• \"{summary_content['notable_quotes']}\"\n"
                body_text += "\n"

            if "conclusion" in summary_content:
                body_text += "CONCLUSION:\n"
                body_text += f"{summary_content['conclusion']}\n\n"
        else:
            # Fallback for non-structured summary
            body_text += f"{summary_content}\n\n"

        body_text += "=" * 50 + "\n\n"

    body_text += "Thank you for using Media Summarizer!\n\n"
    body_text += "The Media Summarizer Team"

    # Create HTML version
    body_html = f"""
    <html>
    <body>
        <h2>Your Podcast Summary is Ready</h2>
        <div style="margin-bottom: 20px;">
    """

    if podcast_title:
        body_html += f"<p><strong>Podcast:</strong> {podcast_title}</p>"
    if episode_title:
        body_html += f"<p><strong>Episode:</strong> {episode_title}</p>"

    body_html += f"<p><strong>Job ID:</strong> {job_id}</p></div>"

    # Include the actual summary content in HTML
    if summary_content:
        body_html += """
        <div style="border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 5px; background-color: #f9f9f9;">
            <h3>Summary</h3>
        """

        if isinstance(summary_content, dict):
            if "main_topics" in summary_content:
                body_html += "<h4>Main Topics:</h4><ul>"
                if isinstance(summary_content["main_topics"], list):
                    for topic in summary_content["main_topics"]:
                        body_html += f"<li>{topic}</li>"
                else:
                    body_html += f"<li>{summary_content['main_topics']}</li>"
                body_html += "</ul>"

            if "key_points" in summary_content:
                body_html += "<h4>Key Points:</h4><ul>"
                if isinstance(summary_content["key_points"], list):
                    for point in summary_content["key_points"]:
                        body_html += f"<li>{point}</li>"
                else:
                    body_html += f"<li>{summary_content['key_points']}</li>"
                body_html += "</ul>"

            if "notable_quotes" in summary_content and summary_content["notable_quotes"]:
                body_html += "<h4>Notable Quotes:</h4><ul>"
                if isinstance(summary_content["notable_quotes"], list):
                    for quote in summary_content["notable_quotes"]:
                        body_html += f"<li><em>\"{quote}\"</em></li>"
                else:
                    body_html += f"<li><em>\"{summary_content['notable_quotes']}\"</em></li>"
                body_html += "</ul>"

            if "conclusion" in summary_content:
                body_html += f"<h4>Conclusion:</h4><p>{summary_content['conclusion']}</p>"
        else:
            # Fallback for non-structured summary
            body_html += f"<p>{summary_content}</p>"

        body_html += "</div>"

    body_html += """
        <p>Thank you for using Media Summarizer!</p>
        <p>The Media Summarizer Team</p>
    </body>
    </html>
    """

    return await ses.send_email(
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sender=DEFAULT_SENDER
    )





async def process_message(message: Dict[str, Any], retries: int = 0, ses_client: Optional[Any] = None) -> None:
    """
    Process an SQS message and send the appropriate email notification.

    Args:
        message: SQS message to process
        retries: Number of retries attempted (used internally for retry logic)
    """
    try:
        # Parse the message body
        body = json.loads(message.get("Body", "{}"))

        # Extract common fields
        job_id = body.get("job_id")
        recipient = body.get("email")
        notification_type = body.get("notification_type")

        if not job_id or not recipient:
            logger.error(f"Missing required fields in message: {body}")
            return

        # Mark job as notifying before sending any email
        try:
            job = await database_async.get_processing_job_by_id(job_id)
            if job:
                job.mark_notifying()
                await database_async.update_processing_job(job)
        except Exception as e:
            logger.error(f"Error updating job status to notifying: {str(e)}")

        # Send the appropriate notification based on type
        if notification_type == "error":
            error_message = body.get("error", "Unknown error")
            step = body.get("step")
            traceback_info = body.get("traceback")
            
            # 1. Send user-friendly error email
            await send_error_notification(recipient, job_id, error_message, step)
            logger.info(f"Sent error notification for job {job_id} to {recipient}")

            # 2. Send Ops Alert (Technical details)
            if job:
                try:
                    await send_ops_alert(
                        job_id=job_id,
                        user_email=recipient,
                        error_step=step or "unknown",
                        error_message=error_message,
                        retry_count=job.retry_count,
                        max_retries=job.max_retries,
                        traceback_info=traceback_info
                    )
                except Exception as ops_e:
                    logger.error(f"Failed to send ops alert for job {job_id}: {ops_e}")

            # Idempotence: mark failed only for canonical processing jobs (skip cache-only emails)
            try:
                # Refresh job from DB just in case, or use existing 'job' object
                # (using existing 'job' object is fine as we just updated it to notifying)
                from_cache = body.get("from_cache", False)
                if job and getattr(job, "episode_guid", None) and not from_cache:
                    await episode_idempotence.mark_failed(job.episode_guid, job.id)
            except Exception as e:
                logger.error(f"Error marking idempotence failed: {str(e)}")

        elif notification_type == "completion":
            podcast_title = body.get("podcast_title")
            episode_title = body.get("episode_title")
            summary_content = body.get("summary_content")
            quiz = body.get("quiz")
            language = body.get("language")
            await send_completion_notification(recipient, job_id, podcast_title, episode_title, summary_content, quiz=quiz, language=language)
            logger.info(f"Sent completion notification for job {job_id} to {recipient}")

            # Mark job as completed after successful email sending
            try:
                job = await database_async.get_processing_job_by_id(job_id)
                if job:
                    job.mark_completed()
                    await database_async.update_processing_job(job)
                    # Idempotence: mark processed only for canonical processing jobs (skip cache-only emails)
                    try:
                        from_cache = body.get("from_cache", False)
                        if getattr(job, "episode_guid", None) and not from_cache and getattr(job, "summary_s3_key", None):
                            await episode_idempotence.mark_processed(job.episode_guid, job.id)
                    except Exception as e2:
                        logger.error(f"Error marking idempotence processed: {str(e2)}")
            except Exception as e:
                logger.error(f"Error updating job status to completed: {str(e)}")

        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return  # Don't delete the message for unknown notification types

        # Delete the message from the queue
        receipt_handle = message.get("ReceiptHandle")
        if receipt_handle:
            await sqs.delete_message(
                queue_name=EMAIL_QUEUE_NAME,
                receipt_handle=receipt_handle
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


async def poll_queue() -> None:
    """
    Poll the SQS queue for notification messages.
    """
    while True:
        try:
            # Receive messages from the queue
            messages = await sqs.receive_messages(
                queue_name=EMAIL_QUEUE_NAME,
                max_messages=10,
                wait_time_seconds=20  # Long polling
            )

            if messages:
                logger.info(f"Received {len(messages)} messages")

                # Process messages concurrently
                tasks = [process_message(message) for message in messages]
                await asyncio.gather(*tasks, return_exceptions=True)

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
    from media_summarizer.utils.logging_config import configure_logging
    # Configure logging with JSON formatter
    configure_logging()

    asyncio.run(main())
