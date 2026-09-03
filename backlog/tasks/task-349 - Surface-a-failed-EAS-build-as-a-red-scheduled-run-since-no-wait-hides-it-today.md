---
id: task-349
title: >-
  Surface a failed EAS build as a red scheduled run, since --no-wait hides it
  today
status: To Do
assignee: []
created_date: '2026-09-03 12:57'
labels:
  - mobile
  - ci
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision, 2026-09-03: **option A — poll EAS from a scheduled workflow and let a red
GitHub Actions run be the notification.** That is the channel that already delivers a
failed `Main Branch Checks` by mail, so it needs no new service, no new secret and no
receiver.

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

## What to build

One new workflow — `.github/workflows/mobile-build-watch.yml` is a suggested name.

- `on: schedule` plus `workflow_dispatch`, and no other trigger. The manual trigger is
  not decoration: a `schedule` trigger only ever runs on the default branch, so it is
  the owner's only way to exercise the file once it is merged.
- Pick a cron period between 30 and 60 minutes and put the reasoning in a comment.
  Actions minutes are free on this public repo, so the tick costs nothing; the real
  constraint is that GitHub's shared scheduler delays cron under load, which the dedup
  below has to tolerate. Worth a comment too: GitHub disables scheduled workflows after
  60 days without repository activity.
- Same conventions as the three existing mobile workflows: `NODE_VERSION: "22"`,
  `EAS_CLI_VERSION: "22.0.0"` pinned (never bare `eas-cli` — the owner's machine runs
  22.0.0 while 23.2.0 is published), `EXPO_TOKEN` from the repository secret.
- The query is `eas build:list --platform all --status errored --json --non-interactive`
  with a small `--limit`. `--status` accepts
  `new|in-queue|in-progress|pending-cancel|errored|finished|canceled`; `errored` is the
  one that matters, `canceled` is usually a human act.
- **Alert at most once per failed build.** A red run on every tick for as long as the
  failure stays recent trains the owner to ignore the channel, which defeats the task.
  Suggested stateless mechanism: anchor on the previous **completed** run of this same
  workflow (`gh run list --workflow <file> --status completed --limit 1 --json
  createdAt`) and consider only builds whose `completedAt` is later than that anchor.
  Anchoring on the last *successful* run instead re-alerts every cycle, since the run
  that alerted was itself a failure. Fall back to a bounded window when no previous run
  exists. Another mechanism is fine if the comment justifies it; no dedup is not.
- The failing step writes to `$GITHUB_STEP_SUMMARY` what broke: platform,
  `appVersion (appBuildVersion)`, build id, a link to the EAS build page, `gitCommitHash`
  and `gitCommitMessage`. The mail GitHub sends carries only the run title, so the
  summary is where the owner will actually look. Note that `build:list --json` carries
  **no** URL field (its keys are `app appBuildVersion appIdentifier appVersion artifacts
  buildProfile completedAt createdAt distribution expirationDate fingerprint
  gitCommitHash gitCommitMessage id initiatingActor isForIosSimulator logFiles metrics
  platform priority sdkVersion status updatedAt`) — the build page URL is built from the
  id.
- **Distinguish a found failure from a broken check.** If `eas build:list` itself fails
  — revoked token, network, CLI drift — the run must still go red, but with a summary
  saying the check could not run rather than one that reads like a build failure.
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
- Do not manufacture a failed build to see it go red — that spends build quota. The next
  genuine failure will do.
- Make sure the mail reaches you: github.com → avatar top right → **Settings** →
  **Notifications** → section **Actions** → tick **Email**, and "Only notify for failed
  workflows" if you do not want the green ones. For a `schedule` run GitHub notifies the
  user who last modified the workflow file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new workflow file exists whose only triggers are schedule and workflow_dispatch, and which names no push, pull_request or tag trigger
- [ ] #2 It pins EAS_CLI_VERSION 22.0.0 and NODE_VERSION 22 exactly as mobile-ota-or-build.yml, mobile-build-distribute.yml and mobile-store-promote.yml do, and authenticates with secrets.EXPO_TOKEN
- [ ] #3 The eas build:list query the workflow runs, executed verbatim from the worktree against the real EAS project, returns a parseable JSON array; the command and its output are pasted into the Implementation Notes
- [ ] #4 The workflow alerts at most once per failed build: the mechanism is implemented, a comment states why it anchors where it does, and the Implementation Notes show the anchor query run against the real repository together with the comparison it feeds
- [ ] #5 On a detected failure the step summary names platform, appVersion (appBuildVersion), build id, a URL to the EAS build page built from that id, and the git commit hash and message
- [ ] #6 A failure of the eas query itself also fails the run, with a step summary saying the check could not run rather than one that reads like a build failure; the two paths are distinguishable in the log
- [ ] #7 The cron period is between 30 and 60 minutes and a comment states the reasoning, including that Actions minutes are free on this public repo and that GitHub delays cron under load
- [ ] #8 The YAML parses and the resulting job list is pasted into the Implementation Notes (actionlint is not installed on this machine, so parseability is the bar)
- [ ] #9 mobile/MOBILE_CI_CD.md section 'Pinning the EAS CLI' lists the new workflow among those pinning EAS_CLI_VERSION
- [ ] #10 mobile/MOBILE_CI_CD.md section 'Automatic Notifications' states that mobile-ota-or-build.yml uses --no-wait and detects nothing by itself, that the Slack branch cannot fire while SLACK_WEBHOOK_URL is unset, what the new workflow covers, and that submission failures stay uncovered and why
- [ ] #11 No existing workflow is modified: mobile-ota-or-build.yml keeps --no-wait and git diff lists no other file under .github/workflows/
<!-- AC:END -->
