#!/usr/bin/env python3
"""
Render locally the Jinja quiz email templates (AMP, interactive HTML, fallback HTML, text)
into an output directory, using a synthetic context.

Usage:
  uv run python scripts/render_quiz_templates_demo.py --lang FR --out rendered_emails
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

try:
    from media_summarizer.utils.mime_builder import build_multipart_amp_email
except Exception:
    # Optional: allow running even if import path changes
    build_multipart_amp_email = None  # type: ignore


def demo_context(language: str) -> Dict[str, Any]:
    quiz = {
        "id": "demo-quiz",
        "episode_id": None,
        "language": language,
        "questions": [
            {
                "id": "q1",
                "prompt": (
                    "Quelle est la capitale de la France ?"
                    if language.upper() == "FR"
                    else "What is the capital of France?"
                ),
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
                "prompt": (
                    "Sélectionnez les langages typiquement utilisés côté frontend"
                    if language.upper() == "FR"
                    else "Select languages typically used on the frontend"
                ),
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
        "key_points": ["Email AMP + HTML interactif", "Fallback universel"],
        "notable_quotes": [],
        "conclusion": "Fin de la démo" if language.upper() == "FR" else "End of demo",
    }

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
        "primary_start": "#2563eb",
        "primary_end": "#9333ea",
        "bg_from": "#eff6ff",
        "bg_to": "#faf5ff",
        "text": "#111827",
        "muted": "#6b7280",
        "border": "#e5e7eb",
        "correct_bg": "#dcfce7",
        "correct_text": "#166534",
        "incorrect_bg": "#fee2e2",
        "incorrect_text": "#991b1b",
        "button_text": "#ffffff",
    }

    return {
        "podcast_title": "Demo Podcast",
        "episode_title": "Episode de démonstration" if language.upper() == "FR" else "Demo Episode",
        "quiz": quiz,
        "summary": summary,
        "ui_strings": ui_strings,
        "brand": brand,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default=os.environ.get("DEFAULT_QUIZ_LANGUAGE", "EN"))
    parser.add_argument("--out", default="rendered_emails")
    args = parser.parse_args()

    templates_dir = Path(__file__).resolve().parents[1] / "media_summarizer" / "email_templates" / "quiz"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    ctx = demo_context(args.lang)

    # Render files
    amp_html = env.get_template("quiz_amp.html.j2").render(**ctx)
    (out_dir / "quiz_amp.html").write_text(amp_html, encoding="utf-8")

    interactive_html = env.get_template("quiz_interactive.html.j2").render(**ctx)
    (out_dir / "quiz_interactive.html").write_text(interactive_html, encoding="utf-8")

    fallback_html = env.get_template("quiz_fallback.html.j2").render(**ctx)
    (out_dir / "quiz_fallback.html").write_text(fallback_html, encoding="utf-8")

    text_part = env.get_template("quiz.txt.j2").render(**ctx)
    (out_dir / "quiz.txt").write_text(text_part, encoding="utf-8")

    # Optional: build combined MIME .eml for inspection
    if build_multipart_amp_email:
        raw = build_multipart_amp_email(
            subject="Your podcast summary is ready",
            from_addr=os.environ.get("FROM_EMAIL", "noreply@example.com"),
            to_addr="you@example.com",
            text_part=text_part,
            amp_part=amp_html,
            html_part=interactive_html,
        )
        (out_dir / "quiz_email.eml").write_text(raw, encoding="utf-8")

    print(f"Rendered templates to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()