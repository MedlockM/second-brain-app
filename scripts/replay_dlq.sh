#!/usr/bin/env bash
# replay_dlq.sh — Replay messages from a Dead Letter Queue back to its source queue.
#
# Uses the SQS StartMessageMoveTask API (available since 2023-06-27) to atomically
# move all messages from the DLQ back to the original source queue for reprocessing.
#
# Prerequisites:
#   - AWS CLI v2 (>= 2.12.0 for start-message-move-task support)
#   - Appropriate IAM permissions (sqs:StartMessageMoveTask, sqs:GetQueueAttributes)
#   - AWS_PROFILE or credentials configured
#
# Usage:
#   ./scripts/replay_dlq.sh <dlq-name>
#
# Example:
#   ./scripts/replay_dlq.sh summarization-dlq
#   ./scripts/replay_dlq.sh podcastindex-resolution-dlq
#
# See also: infrastructure/observability/runbooks/pipeline-alerts.md

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AWS_REGION="${AWS_REGION:-eu-west-1}"
POLL_INTERVAL_SECONDS=5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "[$(date '+%H:%M:%S')] $*"
}

usage() {
  echo "Usage: $0 <dlq-name>"
  echo ""
  echo "Replays all messages from the specified DLQ back to its source queue."
  echo ""
  echo "Available DLQs:"
  echo "  podcastindex-resolution-dlq"
  echo "  article-extraction-dlq"
  echo "  x-ingestion-dlq"
  echo "  youtube-ingestion-dlq"
  echo "  instagram-ingestion-dlq"
  echo "  tiktok-ingestion-dlq"
  echo "  deepgram-transcription-dlq"
  echo "  summarization-dlq"
  echo "  document-parsing-dlq"
  echo "  search-indexing-dlq"
  echo "  rss-feed-poll-dlq"
  echo "  episode-completed-events-dlq"
  echo "  flashcards-dlq"
  echo "  notes-dlq"
  echo "  quiz-dlq"
  echo ""
  echo "Environment variables:"
  echo "  AWS_REGION   AWS region (default: eu-west-1)"
  echo "  AWS_PROFILE  AWS profile to use (optional)"
  exit 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if [[ $# -lt 1 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  usage
fi

DLQ_NAME="$1"

# Validate the DLQ name ends with -dlq
if [[ ! "$DLQ_NAME" =~ -dlq$ ]]; then
  die "Queue name '$DLQ_NAME' does not look like a DLQ (must end with -dlq)."
fi

# Get the DLQ URL
info "Looking up DLQ: $DLQ_NAME ..."
DLQ_URL=$(aws sqs get-queue-url \
  --queue-name "$DLQ_NAME" \
  --region "$AWS_REGION" \
  --output text --query 'QueueUrl' 2>/dev/null) \
  || die "Could not find queue '$DLQ_NAME' in region $AWS_REGION. Check the name and your AWS credentials."

# Get DLQ ARN and message count
info "Fetching DLQ attributes ..."
DLQ_ATTRS=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn ApproximateNumberOfMessages RedriveAllowPolicy \
  --region "$AWS_REGION" \
  --output json)

DLQ_ARN=$(echo "$DLQ_ATTRS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Attributes']['QueueArn'])")
MSG_COUNT=$(echo "$DLQ_ATTRS" | python3 -c "import sys,json; print(json.load(sys.stdin)['Attributes']['ApproximateNumberOfMessages'])")

if [[ "$MSG_COUNT" -eq 0 ]]; then
  die "DLQ '$DLQ_NAME' is empty (0 messages). Nothing to replay."
fi

info "Found $MSG_COUNT message(s) in $DLQ_NAME."

# Determine the source queue by inspecting the DLQ's redrive allow policy,
# or by convention (strip -dlq suffix, add -queue suffix).
# The start-message-move-task API moves to the original source automatically
# when no DestinationArn is specified.

info "Starting message move task (DLQ -> source queue) ..."
MOVE_RESULT=$(aws sqs start-message-move-task \
  --source-arn "$DLQ_ARN" \
  --region "$AWS_REGION" \
  --output json) \
  || die "start-message-move-task failed. Ensure your AWS CLI is >= 2.12.0 and you have sqs:StartMessageMoveTask permission."

TASK_HANDLE=$(echo "$MOVE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['TaskHandle'])")

info "Move task started. TaskHandle: $TASK_HANDLE"
info "Polling for completion ..."

# Poll until the move task finishes
while true; do
  sleep "$POLL_INTERVAL_SECONDS"

  TASK_STATUS=$(aws sqs list-message-move-tasks \
    --source-arn "$DLQ_ARN" \
    --region "$AWS_REGION" \
    --output json)

  # Find our task in the results
  STATUS=$(echo "$TASK_STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for task in data.get('Results', []):
    if task.get('TaskHandle') == '$TASK_HANDLE':
        print(task.get('Status', 'UNKNOWN'))
        break
else:
    print('NOT_FOUND')
")

  MOVED=$(echo "$TASK_STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for task in data.get('Results', []):
    if task.get('TaskHandle') == '$TASK_HANDLE':
        print(task.get('ApproximateNumberOfMessagesMoved', 0))
        break
else:
    print(0)
" 2>/dev/null || echo "?")

  case "$STATUS" in
    RUNNING)
      info "  Status: RUNNING | Messages moved so far: $MOVED"
      ;;
    COMPLETED)
      info "Move task COMPLETED. Total messages moved: $MOVED"
      break
      ;;
    CANCELLING|CANCELLED)
      die "Move task was cancelled."
      ;;
    FAILED)
      die "Move task FAILED. Check CloudTrail or SQS console for details."
      ;;
    NOT_FOUND)
      die "Could not find task in list-message-move-tasks results."
      ;;
    *)
      info "  Status: $STATUS | Messages moved so far: $MOVED"
      ;;
  esac
done

info "Done. All messages from '$DLQ_NAME' have been replayed to the source queue."
info "Monitor the source queue and worker Lambda for successful processing."
