# Bug Reports — Internal Process

## Overview

Bug reports submitted through the mobile app's "Report a Bug" feature are persisted to the `bug_reports` DynamoDB table and trigger an alert email when received.

## Where reports go

| Step | System | Details |
|------|--------|---------|
| Persistence | DynamoDB `bug_reports` table | Permanent record with ticket ID |
| Real-time alert | SNS email notification | Subject, description, platform, version, and media context (if report is about a specific item) |
| Attachments | S3 `media-summarizer-bug-reports-*` bucket | Presigned PUT URL upload, server-side validation |

## Who responds

During V1 soft-launch, the owner receives alert emails when reports arrive and triages directly by reading the `bug_reports` DynamoDB table via AWS Console or CLI.
Future: dedicated dashboard or Linear integration.

## SLA targets (soft-launch)

| Priority | Acknowledgement | Resolution |
|----------|----------------|------------|
| Critical (app crash, data loss) | < 4 hours | < 24 hours |
| High (blocking workflow) | < 12 hours | < 3 days |
| Medium (inconvenience) | < 24 hours | < 7 days |
| Low (cosmetic, edge case) | < 48 hours | Best effort |

These are aspirational targets for the soft-launch phase, not contractual commitments.

## Data retention / GDPR

- **Bug report records** (DynamoDB): retained indefinitely until user requests deletion.
- **Attachments** (S3): automatically purged 90 days after upload via S3 lifecycle rule.
  - If the bug is resolved before 90 days, the attachment is still retained until the lifecycle triggers.
  - If the user requests data deletion under GDPR Article 17, the attachment and report are deleted immediately.
- **Alert emails**: stored in the owner's inbox per normal email retention policies.

## How to triage (for the owner)

1. An alert email arrives notifying of a new report.
2. Read the report from the DynamoDB `bug_reports` table:
   ```bash
   aws dynamodb get-item --region eu-west-3 \
     --table-name bug_reports-dev \
     --key '{"id": {"S": "<report_id>"}}'
   ```
3. Read the subject and description. Check the attachment key if present (access via AWS Console or CLI).
4. Assign a priority mentally (Critical/High/Medium/Low).
5. Reproduce if possible on a test device.
6. Fix or create a backlog task for later.
7. Update the `status` field in DynamoDB if you want to track resolution:
   - `open` (default) -> `in_progress` -> `resolved` or `closed`

## Rate limits

- 5 bug reports per hour per user.
- Maximum 1 attachment per report, max 50 MB.
- Allowed types: jpg, jpeg, png, heic, mp4, mov, pdf, zip.

## Antivirus / security

V1 decision: **no antivirus scanning on uploaded attachments**. This is conscious tech debt.
- Attachments are in a private bucket with no public access.
- Only the owner/team accesses them via signed URLs or AWS Console.
- Risk is low during soft-launch (authenticated users only, known user base).
- Follow-up: implement ClamAV Lambda trigger when user base grows beyond ~100 active users.
