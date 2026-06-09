# Bug Reports — Internal Process

## Overview

Bug reports submitted through the mobile app's "Report a Bug" feature are:
1. Persisted to the `bug_reports` DynamoDB table
2. Routed in real-time to the triage Discord channel via webhook

## Where reports go

| Step | System | Details |
|------|--------|---------|
| Persistence | DynamoDB `bug_reports` table | Permanent record with ticket ID |
| Real-time alert | Discord webhook | Embed with subject, description, platform, version |
| Attachments | S3 `media-summarizer-bug-reports-*` bucket | Presigned PUT URL upload, server-side validation |

## Who responds

During V1 soft-launch, the owner triages directly from the Discord `#bug-reports` channel.
Future: dedicated dashboard or Linear integration.

## SLA targets (soft-launch)

| Priority | Acknowledgement | Resolution |
|----------|----------------|------------|
| Critical (app crash, data loss) | < 4 hours | < 24 hours |
| High (blocking workflow) | < 12 hours | < 3 days |
| Medium (inconvenience) | < 24 hours | < 7 days |
| Low (cosmetic, edge case) | < 48 hours | Best effort |

These are aspirational targets for the soft-launch phase, not contractual commitments.

## Data retention / RGPD

- **Bug report records** (DynamoDB): retained indefinitely until user requests deletion.
- **Attachments** (S3): automatically purged 90 days after upload via S3 lifecycle rule.
  - If the bug is resolved before 90 days, the attachment is still retained until the lifecycle triggers.
  - If the user requests data deletion under GDPR Article 17, the attachment and report are deleted immediately.
- **Discord messages**: not automatically purged. The owner manually deletes if requested.

## How to triage (for the owner)

1. A new embed appears in the Discord `#bug-reports` channel.
2. Read the subject and description. Check the attachment key if present (access via AWS Console or CLI).
3. Assign a priority mentally (Critical/High/Medium/Low).
4. Reproduce if possible on a test device.
5. Fix or create a backlog task for later.
6. Update the `status` field in DynamoDB if you want to track resolution:
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
