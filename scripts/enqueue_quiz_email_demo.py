#!/usr/bin/env python3
"""
Enqueue a synthetic quiz-completion message to the email-notification-queue for local testing.
Requires LocalStack (SES/SQS) and the email worker running.

Usage:
  uv run python scripts/enqueue_quiz_email_demo.py --to you@example.com --lang FR
"""
from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any, Dict

from media_summarizer.utils import sqs


def make_demo_payload(to_email: str, language: str) -> Dict[str, Any]:
    quiz = {
        "id": "demo-quiz",
        "episode_id": None,
        "language": language,
        "questions": [
            {
                "id": "q1",
                "prompt": "Quelle est la capitale de la France ?" if language.upper() == "FR" else "What is the capital of France?",
                "multiple": False,
                "choices": [
                    {"id": "a", "text": "Paris", "correct": True},
                    {"id": "b", "text": "Lyon", "correct": False},
                    {"id": "c", "text": "Marseille", "correct": False},
                    {"id": "d", "text": "Bordeaux", "correct": False},
                ],
                "explanation": None,
            },
            {
                "id": "q2",
                "prompt": "Sélectionnez les langages typiquement utilisés côté frontend" if language.upper() == "FR" else "Select languages typically used on the frontend",
                "multiple": True,
                "choices": [
                    {"id": "a", "text": "JavaScript", "correct": True},
                    {"id": "b", "text": "CSS", "correct": True},
                    {"id": "c", "text": "Python", "correct": False},
                    {"id": "d", "text": "HTML", "correct": True},
                ],
                "explanation": None,
            },
        ],
    }

    summary = {
        "main_topics": [
            "Démo quiz interactif" if language.upper() == "FR" else "Interactive quiz demo",
        ],
        "key_points": [
            "Email AMP + HTML interactif", "Fallback universel"
        ],
        "notable_quotes": [],
        "conclusion": "Fin de la démo"
        if language.upper() == "FR"
        else "End of demo",
    }

    return {
        "notification_type": "completion",
        "job_id": "demo-job-123",
        "email": to_email,
        "podcast_title": "Demo Podcast",
        "episode_title": "Episode de démonstration" if language.upper() == "FR" else "Demo Episode",
        "summary_content": summary,
        "quiz": quiz,
        "language": language,
    }


async def main_async(to_email: str, language: str) -> None:
    queue = os.environ.get("NOTIFICATION_QUEUE", "email-notification-queue")
    payload = make_demo_payload(to_email, language)
    await sqs.send_message(queue_name=queue, message_body=payload)
    print(f"Enqueued quiz-completion message to '{queue}' for {to_email}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--lang", default=os.environ.get("DEFAULT_QUIZ_LANGUAGE", "EN"))
    args = parser.parse_args()
    asyncio.run(main_async(args.to, args.lang))


if __name__ == "__main__":
    main()