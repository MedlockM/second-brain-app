---
id: task-349
title: 'Surface a failed EAS build as a GitHub issue, since --no-wait hides it today'
status: To Do
assignee: []
created_date: '2026-09-03 12:57'
updated_date: '2026-09-03 13:08'
labels:
  - mobile
  - ci
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision, 2026-09-03: **option A — a scheduled workflow polls EAS and surfaces a failed
build itself**, rather than a webhook receiver or a paid monitor. Nothing about the
mobile pipeline detects a failed build today.

Refined the same day after checking community practice: **a detected build failure opens a
GitHub issue and leaves the run green; only a broken check turns the run red.** Reasoning
under "Why the run does not fail" below — that section is the point of this task, do not
collapse the two cases back into one `exit 1`.

## The gap, measured

`mobile-ota-or-build.yml` starts the native build with `--no-wait`, deliberately: the
Free plan's low-priority queue served jobs after 3 h+ on 2026-09-02, and EAS keeps a
queued job for 30 days, so holding a GitHub job open proves nothing. The consequence is
that the workflow reports **success the moment the build is scheduled**. On its first
real run (2026-09-03, run `33750484244`) it went green in **1 m 18 s** while the Android
build was still `IN_QUEUE` and the iOS one `IN_PROGRESS`.

A build that errors twenty minutes later is therefore invisible:

- no job is alive to fail;
- `mobile-ota-or-build.yml` has no `notify-failure` job. Only
  `mobile-build-distribute.yml` has one, and it fires for tag-triggered runs — the path
  blocked today by the `production` profile's DNS;
- the Slack branch described in `mobile/MOBILE_CI_CD.md` § "Automatic Notifications" is
  inert: `SLACK_WEBHOOK_URL` is not among the repository's 7 secrets (`gh secret list`,
  2026-09-03).

The EAS webhook (`eas webhook:create --event BUILD|SUBMIT`) was considered and rejected
for now: it needs a public HTTPS receiver, and Expo POSTs HMAC-SHA1-signed JSON
(`expo-signature`) that no Slack or Discord webhook accepts as-is. Revisit it only if
submission failures become a real concern.

## Why the run does not fail on a detected build failure

Two reasons, both about this exact shape of workflow — a scheduled check on a system
outside the repository.

1. **A red run is an ambiguous signal here, and the mail carries nothing else.** "An EAS
   build errored" and "the check could not run" would produce the same conclusion and the
   same mail subject. GitHub's failure mail carries only the run title, so a
   `$GITHUB_STEP_SUMMARY` that distinguishes them is invisible at the moment of reading.
   Failing the run is the right signal for the second case only: there, the pipeline
   really is broken.
2. **An issue is the deduplication, for free.** Alerting once per failed build otherwise
   needs a hand-rolled state machine (anchor on the previous run's timestamp, and hope no
   run is skipped). GitHub's scheduler drifts 30-60 min under load and drops runs
   outright, which breaks a timestamp anchor; an issue keyed on the build id does not
   care. `gh issue list --search <build-id>` is the whole mechanism.

This follows the reference implementation of the pattern: Upptime (17 152 stars) polls
every 5 minutes and, when a monitored site is **down**, its `Uptime CI` run stays
**green** — the incident is a GitHub issue opened and closed by the action. Red is
reserved for a broken checker. epiforecasts' "Dealing with flaky GitHub Actions"
recommends the same for cron workflows, because GitHub's failure mail reaches exactly one
person: per GitHub's own docs, "Notifications for scheduled workflows are sent to the user
who initially created the workflow", moving to whoever last edited the **cron syntax**, or
to whoever re-enabled the workflow after it was disabled. Community discussion 43415
(98 upvotes, 65 comments, unresolved) is entirely about that recipient being unfixable.

It is also already this repository's convention: `mobile-build-distribute.yml:357`
`notify-failure` opens an issue with `permissions: issues: write`.

Note the asymmetry with Upptime worth not copying: an errored build never becomes
un-errored, so there is no "resolved" transition to detect and nothing to auto-close. One
issue per failed build id, the owner closes it.

## What to build

One new workflow — `.github/workflows/mobile-build-watch.yml` is a suggested name.

- `on: schedule` plus `workflow_dispatch`, and no other trigger. The manual trigger is
  not decoration: a `schedule` trigger only ever runs on the default branch, so it is
  the owner's only way to exercise the file once it is merged.
- Pick a cron period between 30 and 60 minutes and put the reasoning in a comment.
  Actions minutes are free on this public repo, so the tick costs nothing. Add
  `timeout-minutes` so a hung run cannot sit there reporting nothing.
- Same conventions as the three existing mobile workflows: `NODE_VERSION: "22"`,
  `EAS_CLI_VERSION: "22.0.0"` pinned (never bare `eas-cli` — the owner's machine runs
  22.0.0 while 23.2.0 is published), `EXPO_TOKEN` from the repository secret.
- The query is `eas build:list --platform all --status errored --json --non-interactive`
  with a small `--limit`. `--status` accepts
  `new|in-queue|in-progress|pending-cancel|errored|finished|canceled`; `errored` is the
  one that matters, `canceled` is usually a human act.
- For each errored build not already reported, `gh issue create`. Title carries platform,
  `appVersion (appBuildVersion)` and the build id; body carries the EAS build page URL,
  `gitCommitHash`, `gitCommitMessage`, `buildProfile`, and an explicit `@MedlockM`
  mention. The mention matters: whether the owner watches their own repository could not
  be verified (the local `gh` token lacks the `notifications` scope), and a mention
  notifies regardless. `build:list --json` carries **no** URL field — its keys are `app
  appBuildVersion appIdentifier appVersion artifacts buildProfile completedAt createdAt
  distribution expirationDate fingerprint gitCommitHash gitCommitMessage id
  initiatingActor isForIosSimulator logFiles metrics platform priority sdkVersion status
  updatedAt` — so the build page URL is constructed from the id.
- A failure to *report* is a broken check, so it belongs on the red path: a GitHub API
  hiccup must neither masquerade as a build failure nor swallow one silently.
- Builds only. Submissions are out of scope: no read-only CLI command exists for one
  (`eas submission:view` does not exist, and `eas submit --latest` *creates* another
  submission), so covering them means the Expo GraphQL API or the rejected webhook.
  Record the gap in the doc instead of half-closing it.

## Owner notes — not acceptance criteria

- **Check this first, it may make the task unnecessary.** expo.dev may already mail you
  on a failed build (avatar → Settings, look for a notifications section). The public
  docs do not say, and both candidate URLs 404 — it could not be confirmed from here. If
  that mail exists and suffices, close this task.
- After it merges and `main` is pushed, run `gh workflow run mobile-build-watch.yml`
  once. Nothing before the merge exercises a `schedule` trigger.
- Do not manufacture a failed build to see the issue appear — that spends build quota.
  The next genuine failure will do.
- One failure mode neither an issue nor a red run covers: the watcher silently stops.
  GitHub disables scheduled workflows after **60 days without repository activity**, and
  mails a warning first. The usual answer is an external dead-man's-switch; **the owner
  has ruled that out** (2026-09-03) — solo on the project, watching the inbox is the
  monitoring. Do not scope a heartbeat, a dead-man's-switch or a third-party cron monitor
  for this, now or later.
- The red path is what reaches you by mail, so keep Actions mail on: github.com → avatar
  top right → **Settings** → **Notifications** → section **Actions** → tick **Email**.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new workflow file exists whose only triggers are schedule and workflow_dispatch, and which names no push, pull_request or tag trigger
- [ ] #2 It pins EAS_CLI_VERSION 22.0.0 and NODE_VERSION 22 exactly as mobile-ota-or-build.yml, mobile-build-distribute.yml and mobile-store-promote.yml do, and authenticates with secrets.EXPO_TOKEN
- [ ] #3 The eas build:list query the workflow runs, executed verbatim from the worktree against the real EAS project, returns a parseable JSON array; the command and its output are pasted into the Implementation Notes
- [ ] #4 A comment at the top of the file states the split it implements -- a detected build failure opens an issue and leaves the run green, only a broken check fails the run -- and why, so a later reader does not collapse the two into one exit 1
- [ ] #5 On finding an errored build the workflow opens a GitHub issue via gh issue create and the job does NOT fail for that case; the permissions block grants exactly contents: read and issues: write
- [ ] #6 Deduplication is keyed on the EAS build id: the workflow searches existing issues (open and closed) for that id and skips creation when one is found; the search command and its real output are pasted into the Implementation Notes
- [ ] #7 The issue title carries platform, appVersion (appBuildVersion) and the build id; the body carries an EAS build page URL constructed from the id, gitCommitHash, gitCommitMessage, buildProfile, and an explicit @MedlockM mention
- [ ] #8 A failure of the eas query, of gh, or of the issue creation itself fails the run with a step summary saying the check could not run; this is the only path that turns the run red, and the two paths are distinguishable in the log
- [ ] #9 The cron period is between 30 and 60 minutes with a comment stating the reasoning, and the job sets timeout-minutes
- [ ] #10 The YAML parses and the resulting job list is pasted into the Implementation Notes (actionlint is not installed on this machine, so parseability is the bar)
- [ ] #11 mobile/MOBILE_CI_CD.md section 'Pinning the EAS CLI' lists the new workflow among those pinning EAS_CLI_VERSION

- [ ] #12 mobile/MOBILE_CI_CD.md section 'Automatic Notifications' states that mobile-ota-or-build.yml uses --no-wait and detects nothing by itself, that the Slack branch cannot fire while SLACK_WEBHOOK_URL is unset, what the new workflow covers and how it signals (issue for a build failure, red run for a broken check), and that submission failures stay uncovered and why
- [ ] #13 No existing workflow is modified: mobile-ota-or-build.yml keeps --no-wait and git diff lists no other file under .github/workflows/
<!-- AC:END -->
