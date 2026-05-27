import argparse
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tail LocalStack CloudWatch logs for a Lambda function."
    )
    parser.add_argument(
        "--function",
        required=True,
        help="Lambda function name (e.g., cleanup-job-archiver).",
    )
    parser.add_argument(
        "--since-minutes",
        type=int,
        default=10,
        help="Look back window in minutes (default: 10).",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        help="AWS/LocalStack endpoint URL (default: http://localhost:4566).",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1).",
    )
    return parser.parse_args()


def _format_ts(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.isoformat()


def main() -> int:
    args = _parse_args()
    start_time = datetime.now(timezone.utc) - timedelta(minutes=args.since_minutes)
    start_ms = int(start_time.timestamp() * 1000)

    logs = boto3.client(
        "logs",
        endpoint_url=args.endpoint_url,
        region_name=args.region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )

    log_group = f"/aws/lambda/{args.function}"

    try:
        streams_resp = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            descending=True,
            limit=5,
        )
    except ClientError as exc:
        print(f"Failed to describe log streams for {log_group}: {exc}")
        return 1

    streams = streams_resp.get("logStreams", [])
    if not streams:
        print(f"No log streams found for {log_group}.")
        return 0

    found = False
    for stream in streams:
        stream_name = stream.get("logStreamName")
        if not stream_name:
            continue
        try:
            events_resp = logs.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                startTime=start_ms,
                startFromHead=True,
            )
        except ClientError as exc:
            print(f"Failed to get log events for {stream_name}: {exc}")
            continue

        events = events_resp.get("events", [])
        if not events:
            continue

        found = True
        print(f"== {log_group} :: {stream_name} ==")
        for event in events:
            ts = _format_ts(event.get("timestamp", 0))
            message = event.get("message", "").rstrip()
            print(f"{ts} {message}")

    if not found:
        print(f"No log events for {log_group} in the last {args.since_minutes} minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
