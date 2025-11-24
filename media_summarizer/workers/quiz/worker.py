"""
Quiz generation worker: consumes messages with transcript_s3_key and metadata,
produces a quiz JSON (no persistence of answers) and enqueues email completion
with quiz content included.
"""
from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List

from media_summarizer.utils import s3, sqs, database_async

logger = logging.getLogger(__name__)

QUIZ_QUEUE = os.environ.get("QUIZ_QUEUE", "quiz-queue")
NOTIFICATION_QUEUE = os.environ.get("NOTIFICATION_QUEUE", "email-notification-queue")
TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "media-summarizer-transcriptions")
QUIZ_BUCKET = os.environ.get("QUIZ_BUCKET", "media-summarizer-quizzes")
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_QUIZ_LANGUAGE", "EN")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")


async def _download_transcript(key: str) -> str:
    content = await s3.download_file_to_memory(bucket=TRANSCRIPT_BUCKET, key=key)
    return content.decode("utf-8")


async def _upload_quiz(job_id: str, quiz_data: Dict[str, Any]) -> str:
    """Upload quiz JSON to S3 and return the S3 key."""
    from io import BytesIO
    
    quiz_s3_key = f"{job_id}.json"
    quiz_json = json.dumps(quiz_data, indent=2, ensure_ascii=False)
    quiz_bytes = quiz_json.encode("utf-8")
    
    quiz_file = BytesIO(quiz_bytes)
    
    await s3.upload_file_object(
        bucket=QUIZ_BUCKET,
        key=quiz_s3_key,
        file_obj=quiz_file,
        content_type="application/json",
        metadata={
            "content-type": "application/json",
            "job-type": "podcast-quiz",
        },
    )
    
    logger.info(f"Quiz uploaded to s3://{QUIZ_BUCKET}/{quiz_s3_key}")
    return quiz_s3_key


def _build_quiz_prompt(transcript: str, language: str, max_questions: int = 15) -> str:
    return f"""
You are to create a multiple-question quiz in {language}. The quiz helps a listener
check recall of the MAIN PODCAST CONTENT and topics discussed.

CRITICAL INSTRUCTIONS:
- The transcript contains sponsor messages and ads. DO NOT create questions about sponsors, products being advertised, or promotional content.
- ONLY create questions about the main discussion, topics, stories, and ideas presented in the podcast episode itself.
- Read through the ENTIRE transcript to identify the main content after any introductory ads.

Brand/tone requirements:
- Friendly, concise, professional. No emojis.
- Sentence case (avoid ALL CAPS). Neutral tone consistent with an AI summaries product.

Rules:
- Create an appropriate number of questions (between 5 and {max_questions}) based on the length and complexity of the episode.
- The number of questions should match the amount of substantive content discussed.
- Quality over quantity: only create questions about topics that were actually discussed in depth.
- Each question should have 3–4 choices (prefer 4). Some questions may require multiple correct answers (multiple: true).
- Keep each question prompt concise (<= 160 chars). Keep each choice concise (<= 100 chars). Provide a short explanation (<= 200 chars) when helpful.
- Output STRICT JSON matching this schema exactly:
{{
  "id": "string",
  "episode_id": null,
  "language": "{language}",
  "questions": [
    {{
      "id": "q1",
      "prompt": "...",
      "multiple": false,
      "choices": [
        {{"id": "a", "text": "...", "correct": false}},
        {{"id": "b", "text": "...", "correct": true}}
      ],
      "explanation": "..."
    }}
  ]
}}

Transcript:
{transcript}
"""


async def _call_llm_for_quiz(transcript: str, language: str) -> Dict[str, Any]:
    # Simple direct call using aiohttp like summarization worker to avoid adding new client code
    import aiohttp

    if not OPENAI_API_KEY:
        # Fallback tiny demo quiz if no key
        return {
            "id": "demo",
            "episode_id": None,
            "language": language,
            "questions": [
                {
                    "id": "q1",
                    "prompt": "Which topic was discussed?",
                    "multiple": False,
                    "choices": [
                        {"id": "a", "text": "AI", "correct": True},
                        {"id": "b", "text": "Cooking", "correct": False},
                        {"id": "c", "text": "Travel", "correct": False},
                        {"id": "d", "text": "Sports", "correct": False},
                    ],
                    "explanation": None,
                }
            ],
        }

    prompt = _build_quiz_prompt(transcript, language, max_questions=15)  # Back to 15 questions
    timeout = aiohttp.ClientTimeout(total=int(os.environ.get("LLM_TIMEOUT_SECONDS", "180")))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        # No max_tokens limit - let the model complete the full 15 questions naturally
        payload = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.5}
        async with session.post(LLM_API_URL, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            content = data["choices"][0]["message"]["content"]
            
            # Try to extract JSON from markdown code blocks if present
            import re
            # First try to remove markdown code block markers
            if content.strip().startswith('```'):
                # Remove opening ```json or ``` and closing ```
                content = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
                content = re.sub(r'\n?```\s*$', '', content.strip())
                logger.info("Removed markdown code block markers")
            
            try:
                obj = json.loads(content)
                logger.info(f"Successfully parsed quiz JSON with {len(obj.get('questions', []))} questions")
            except Exception as e:
                logger.error(f"Failed to parse quiz JSON: {e}")
                logger.error(f"Content (first 500 chars): {content[:500]}")
                # Minimal fallback structure
                obj = {
                    "id": "fallback",
                    "episode_id": None,
                    "language": language,
                    "questions": [
                        {
                            "id": "q1",
                            "prompt": content[:150],
                            "multiple": False,
                            "choices": [
                                {"id": "a", "text": "OK", "correct": True},
                                {"id": "b", "text": "Not mentioned", "correct": False},
                            ],
                            "explanation": None,
                        }
                    ],
                }
            return obj


async def process_message(message: Dict[str, Any]) -> None:
    body = json.loads(message.get("Body", "{}"))
    job_id = body.get("job_id")
    email = body.get("email")
    transcript_s3_key = body.get("transcript_s3_key")
    podcast_title = body.get("podcast_title")
    episode_title = body.get("episode_title")
    language = body.get("language") or DEFAULT_LANGUAGE
    summary_content = body.get("summary_content")

    if not all([job_id, email, transcript_s3_key]):
        logger.error("Missing fields for quiz generation")
        return

    transcript = await _download_transcript(transcript_s3_key)
    quiz = await _call_llm_for_quiz(transcript, language)
    
    # Upload quiz to S3 for persistence
    quiz_s3_key = await _upload_quiz(job_id, quiz)
    logger.info(f"Quiz generated and stored for job {job_id}: {len(quiz.get('questions', []))} questions")
    
    # Update ProcessingJob with quiz_s3_key
    try:
        job = await database_async.get_processing_job_by_id(job_id)
        if job:
            job.set_quiz_location(quiz_s3_key)
            await database_async.update_processing_job(job)
            logger.info(f"Updated job {job_id} with quiz_s3_key")
    except Exception as e:
        logger.warning(f"Failed to update job {job_id} with quiz_s3_key: {e}")

    # Enqueue email notification with quiz and summary
    payload = {
        "notification_type": "completion",
        "job_id": job_id,
        "email": email,
        "podcast_title": podcast_title,
        "episode_title": episode_title,
        "quiz": quiz,
        "quiz_s3_key": quiz_s3_key,
        "summary_content": summary_content,
        "language": language,
    }
    await sqs.send_message(queue_name=NOTIFICATION_QUEUE, message_body=payload)


async def poll_queue() -> None:
    import asyncio
    while True:
        try:
            messages = await sqs.receive_messages(queue_name=QUIZ_QUEUE, max_messages=5, wait_time_seconds=20)
            if messages:
                for m in messages:
                    try:
                        await process_message(m)
                    finally:
                        rh = m.get("ReceiptHandle")
                        if rh:
                            await sqs.delete_message(queue_name=QUIZ_QUEUE, receipt_handle=rh)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Quiz worker error: {e}")
            await asyncio.sleep(5)


async def main() -> None:
    logger.info("Starting quiz worker")
    await poll_queue()


if __name__ == "__main__":
    import asyncio
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
