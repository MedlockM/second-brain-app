#!/usr/bin/env python3
"""
Reproducible multi-instance verification for PodcastIndex global limiter.

This script does not call PodcastIndex. It validates the slot scheduler itself by
running multiple OS processes that concurrently request limiter slots.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from concurrent.futures import ProcessPoolExecutor


def _run_worker(iterations: int) -> list[float]:
    async def _run() -> list[float]:
        from media_summarizer.utils.podcastindex_limiter import acquire_podcastindex_slot

        timestamps: list[float] = []
        for _ in range(iterations):
            await acquire_podcastindex_slot()
            timestamps.append(time.time())
        return timestamps

    return asyncio.run(_run())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4, help="Process count")
    parser.add_argument(
        "--iterations", type=int, default=5, help="Limiter acquisitions per process"
    )
    parser.add_argument(
        "--min-gap-ms",
        type=int,
        default=900,
        help="Minimum expected global gap between consecutive slots (tolerance).",
    )
    args = parser.parse_args()

    redis_url = os.getenv("PODCASTINDEX_LIMITER_REDIS_URL", "").strip()
    if not redis_url:
        print("PODCASTINDEX_LIMITER_REDIS_URL is not set. Aborting.")
        return 2

    all_timestamps: list[float] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(_run_worker, args.iterations) for _ in range(args.workers)]
        for future in futures:
            all_timestamps.extend(future.result())

    all_timestamps.sort()
    if len(all_timestamps) < 2:
        print("Not enough timestamps to validate limiter behavior.")
        return 2

    gaps_ms = [
        int((all_timestamps[i + 1] - all_timestamps[i]) * 1000)
        for i in range(len(all_timestamps) - 1)
    ]
    min_gap = min(gaps_ms)
    max_gap = max(gaps_ms)
    avg_gap = int(sum(gaps_ms) / len(gaps_ms))

    print(
        f"Collected {len(all_timestamps)} slots "
        f"(workers={args.workers}, iterations={args.iterations})."
    )
    print(f"Gap stats (ms): min={min_gap}, avg={avg_gap}, max={max_gap}")

    if min_gap < args.min_gap_ms:
        print(
            f"FAILED: min gap {min_gap}ms is below threshold {args.min_gap_ms}ms."
        )
        return 1

    print("OK: global limiter gap is within expected bounds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

