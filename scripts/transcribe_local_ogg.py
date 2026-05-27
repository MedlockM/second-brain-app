#!/usr/bin/env python3
"""
Transcribe local .ogg files using Whisper and write .txt next to each file.
"""
import argparse
import asyncio
import os
from pathlib import Path
import sys
from typing import Iterable

import whisper

from media_summarizer.core.utils.whisper_async import AsyncWhisperWrapper


def iter_audio_files(root: Path, pattern: str) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    yield from sorted(root.glob(pattern))


async def transcribe_files(
    files: Iterable[Path],
    model_size: str,
    output_dir: Path | None,
) -> int:
    model = whisper.load_model(model_size)
    wrapper = AsyncWhisperWrapper(model)

    processed = 0
    for audio_path in files:
        result = await wrapper.transcribe(str(audio_path))
        text = result.get("text", "")
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"{audio_path.stem}.txt"
        else:
            out_path = audio_path.with_suffix(".txt")
        out_path.write_text(text, encoding="utf-8")
        print(f"{audio_path} -> {out_path}")
        processed += 1

    return processed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe .ogg files in a directory using Whisper."
    )
    parser.add_argument(
        "path",
        help="File or directory containing .ogg files",
    )
    parser.add_argument(
        "--pattern",
        default="*.ogg",
        help="Glob pattern when path is a directory (default: *.ogg)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Whisper model size (default: env WHISPER_MODEL_SIZE or 'large')",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for .txt files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser().resolve()
    pattern = args.pattern
    model_size = args.model or os.environ.get("WHISPER_MODEL_SIZE", "large")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    files = list(iter_audio_files(root, pattern))
    if not files:
        print(f"No files found at {root} with pattern {pattern}")
        return 1

    processed = asyncio.run(transcribe_files(files, model_size, output_dir))
    print(f"Processed {processed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
