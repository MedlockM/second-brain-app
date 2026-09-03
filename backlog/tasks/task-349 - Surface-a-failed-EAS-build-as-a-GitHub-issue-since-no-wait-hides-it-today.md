---
id: task-349
title: 'Surface a failed EAS build as a GitHub issue, since --no-wait hides it today'
status: To Do
assignee: []
created_date: '2026-09-03 12:57'
updated_date: '2026-09-03 15:45'
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
- [x] #1 A new workflow file exists whose only triggers are schedule and workflow_dispatch, and which names no push, pull_request or tag trigger
- [x] #2 It pins EAS_CLI_VERSION 22.0.0 and NODE_VERSION 22 exactly as mobile-ota-or-build.yml, mobile-build-distribute.yml and mobile-store-promote.yml do, and authenticates with secrets.EXPO_TOKEN
- [x] #3 The eas build:list query the workflow runs, executed verbatim from the worktree against the real EAS project, returns a parseable JSON array; the command and its output are pasted into the Implementation Notes
- [x] #4 A comment at the top of the file states the split it implements -- a detected build failure opens an issue and leaves the run green, only a broken check fails the run -- and why, so a later reader does not collapse the two into one exit 1
- [x] #5 On finding an errored build the workflow opens a GitHub issue via gh issue create and the job does NOT fail for that case; the permissions block grants exactly contents: read and issues: write
- [x] #6 Deduplication is keyed on the EAS build id: the workflow searches existing issues (open and closed) for that id and skips creation when one is found; the search command and its real output are pasted into the Implementation Notes
- [x] #7 The issue title carries platform, appVersion (appBuildVersion) and the build id; the body carries an EAS build page URL constructed from the id, gitCommitHash, gitCommitMessage, buildProfile, and an explicit @MedlockM mention
- [x] #8 A failure of the eas query, of gh, or of the issue creation itself fails the run with a step summary saying the check could not run; this is the only path that turns the run red, and the two paths are distinguishable in the log
- [x] #9 The cron period is between 30 and 60 minutes with a comment stating the reasoning, and the job sets timeout-minutes
- [x] #10 The YAML parses and the resulting job list is pasted into the Implementation Notes (actionlint is not installed on this machine, so parseability is the bar)
- [x] #11 mobile/MOBILE_CI_CD.md section 'Pinning the EAS CLI' lists the new workflow among those pinning EAS_CLI_VERSION

- [x] #12 mobile/MOBILE_CI_CD.md section 'Automatic Notifications' states that mobile-ota-or-build.yml uses --no-wait and detects nothing by itself, that the Slack branch cannot fire while SLACK_WEBHOOK_URL is unset, what the new workflow covers and how it signals (issue for a build failure, red run for a broken check), and that submission failures stay uncovered and why
- [x] #13 No existing workflow is modified: mobile-ota-or-build.yml keeps --no-wait and git diff lists no other file under .github/workflows/
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
### What shipped

One new file, `.github/workflows/mobile-build-watch.yml`, plus two sections of
`mobile/MOBILE_CI_CD.md`. No existing workflow touched.

`git diff --name-only` (staged + worktree, before commit):

```
.github/workflows/mobile-build-watch.yml   (new)
mobile/MOBILE_CI_CD.md
backlog/tasks/task-349 - ...md
```

Nothing else under `.github/workflows/`; `mobile-ota-or-build.yml` keeps
`--no-wait`.

### AC #3 — the query, run verbatim against the real EAS project

The workflow's query needs `mobile/node_modules` to exist, because
`eas build:list` evaluates `mobile/app.config.ts` to resolve the project id and
that file imports `expo/config`. In a fresh worktree it therefore fails *before*
reaching the API:

```
$ cd mobile && eas build:list --platform all --status errored --limit 5 --json --non-interactive
Error reading Expo config at .../mobile/app.config.ts:
Cannot find module 'expo/config'
    Error: build:list command failed.
```

That is why the workflow keeps a `npm ci` step even though it builds nothing —
the step carries a comment saying so. With `node_modules` available (symlinked in
from the primary checkout for the duration of this check, then removed), the same
command returns a parseable array:

```
$ cd mobile && eas build:list --platform all --status errored --limit 5 --json --non-interactive > /tmp/errored.json
$ jq 'length' /tmp/errored.json
2
$ jq -r 'type' /tmp/errored.json
array
$ jq -r '.[] | [.id, .platform, .status, .appVersion, .appBuildVersion, .buildProfile] | @tsv' /tmp/errored.json
770c4409-a506-49e1-b9a9-649404f72b9b	ANDROID	ERRORED	1.0.0	3	internal
4b7bd950-335c-4a60-be3c-4f95bce8808a	ANDROID	ERRORED	1.0.0	2	internal
```

The raw array is not pasted whole because each row embeds a full
`gitCommitMessage` (a 30-line commit body); the projections above are the same
call, and `jq 'length'` is itself the parse check the workflow uses.

Three facts read out of that payload, none of them guessable:

- **`--status` is lowercase on the flag, uppercase in the output.** The flag takes
  `errored`; the rows come back `"status": "ERRORED"`, `"platform": "ANDROID"`.
- **`--limit` defaults to 10 and is capped at 50** (`build:list --help`, 22.0.0).
  The workflow uses 20.
- **An errored build carries an extra `error` object the task's key list did not
  have** (that list came from a finished build):
  `{"errorCode":"EAS_BUILD_UNKNOWN_GRADLE_ERROR","message":"Gradle build failed with unknown error. See logs for the \"Run gradlew\" phase for more information."}`.
  It is now in the issue body — it is the single most useful field for triage.

`build:list --json` really carries no URL, confirmed. The build page is composed
from the id plus `app.ownerAccount.name` and `app.slug` on the same row, and the
result resolves:

```
$ curl -s -o /dev/null -w "%{http_code}\n" -I "https://expo.dev/accounts/second-brain-labs/projects/media-summarizer/builds/770c4409-a506-49e1-b9a9-649404f72b9b"
200
```

### AC #6 — deduplication, and the one thing that could not be proven

Primary lookup, run verbatim for both real build ids:

```
$ gh issue list --repo MedlockM/second-brain-app --state all --search "770c4409-a506-49e1-b9a9-649404f72b9b" --limit 50 --json title
[]
$ gh issue list --repo MedlockM/second-brain-app --state all --search "4b7bd950-335c-4a60-be3c-4f95bce8808a" --limit 50 --json title
[]
```

`[]` is the honest and the expected answer — **the repository has zero issues,
open or closed** (`gh issue list --state all --limit 5 --json ...` → `[]`), so a
*positive* match cannot be demonstrated without creating an issue, which nothing
here justifies. What that leaves unverified is narrow but real: whether GitHub's
issue-search tokenizer matches a hyphenated UUID. A false negative there would
open a duplicate issue on every tick.

So the workflow does not rely on it alone. It also fetches, once per run, the
titles of the 100 most recent issues from the plain list endpoint — no search
index involved — and matches the id locally:

```
$ gh issue list --repo MedlockM/second-brain-app --state all --limit 100 --json title
[]
```

Both lookups then filter with `select(.title | contains($id))`, which is what
makes either one exact: the search API is free to return fuzzy hits and they must
not count as "already reported". A build is skipped if *either* lookup matches.

### AC #10 — YAML parses, and the job it yields

```
$ python3 -c "import yaml, json; d = yaml.safe_load(open('.github/workflows/mobile-build-watch.yml')); ..."
top-level keys: ['name', True, 'concurrency', 'env', 'jobs']
triggers: {"schedule": [{"cron": "17,47 * * * *"}], "workflow_dispatch": null}
jobs: ['watch-errored-builds']
 job watch-errored-builds | permissions: {'contents': 'read', 'issues': 'write'} | timeout-minutes: 10
  steps: ['Require EXPO_TOKEN', 'Checkout code', 'Set up Node.js', 'Install dependencies',
          'Install EAS CLI ${{ env.EAS_CLI_VERSION }}', 'List errored builds',
          'Open an issue per unreported errored build', 'Say that the check could not run']
env: ['NODE_VERSION', 'EAS_CLI_VERSION', 'EXPO_TOKEN', 'QUERY_LIMIT', 'REPORT_WINDOW_HOURS']
```

(`on` reads back as the key `True` because PyYAML applies YAML 1.1 booleans;
GitHub does not. Every existing workflow in this repo parses the same way.)
Each `run:` block was extracted from the parsed YAML and checked with `bash -n` —
all four are syntactically valid.

### The green path and the red path, both exercised locally

The reporting step was extracted from the YAML and run against the real
`build:list` payload and the real `gh` API, with only `gh issue create` stubbed
out (creating throwaway issues in a public repo is not worth it).

Green path, reporting window widened so the two historical failures fall inside
it — real fields, real dedup calls, real body:

```
$ RUNNER_TEMP=... REPO=MedlockM/second-brain-app REPORT_WINDOW_HOURS=200 bash step6-dryrun.sh; echo exit=$?
DRY RUN would run: gh issue create --title "EAS build errored: ANDROID 1.0.0 (3) — 770c4409-a506-49e1-b9a9-649404f72b9b" ...
| Build page | https://expo.dev/accounts/second-brain-labs/projects/media-summarizer/builds/770c4409-... |
| Build profile | `internal` |
| Error code | `EAS_BUILD_UNKNOWN_GRADLE_ERROR` |
| Commit | `30cf62ce99fe0c8cfbc28183bb43ed875bac6af2` |
| Commit subject | fix(artifacts): size the triage bullets to the card, drop the audience line |
::notice title=EAS build errored::ANDROID 1.0.0 (3) build 770c4409-... errored (EAS_BUILD_UNKNOWN_GRADLE_ERROR). ...
Done. created=2 already_reported=0 outside_window=0
exit=0
```

`exit=0` is the AC #5 point: finding and reporting a failed build does not fail
the job.

Red path, same script pointed at a repository that does not exist so that `gh`
fails the way an API hiccup would:

```
$ REPO=MedlockM/this-repo-does-not-exist-349 bash step6-dryrun.sh; echo exit=$?
GraphQL: Could not resolve to a Repository with the name '...'. (repository)
exit=1
```

Non-zero, and no issue was created — a reporting failure can neither masquerade
as a build failure nor swallow one. In the workflow that exit code fails the job
and the `if: failure()` step writes a summary headed
`## EAS build watch: THE CHECK COULD NOT RUN`, which explicitly says the run is
red because the watcher failed and that there is no issue to look for. In the log
the two paths differ by annotation: `::notice::` for a detected build failure,
`::error::` reserved for the broken check.

### Two design points the task did not spell out

**A 48 h reporting window (`REPORT_WINDOW_HOURS`).** Without it the first real run
would open two issues about the Android builds that errored on 2026-08-31 and
2026-09-01 — the same Gradle failure, on a commit the owner moved past days ago.
Measured at 2026-09-03T13:39Z those two rows are 68.7 h and 53.3 h old, so both
fall outside the window and the first run will open nothing. Run with the real
value:

```
Skipping 770c4409-... (ANDROID): errored 2026-09-01T08:19:31.507Z, outside the 48 h reporting window.
Skipping 4b7bd950-... (ANDROID): errored 2026-08-31T16:57:28.817Z, outside the 48 h reporting window.
Done. created=0 already_reported=0 outside_window=2
```

This is *not* the timestamp state machine the design rejects: the cutoff is
relative to *now*, never to the previous run, so a skipped or doubled tick
changes nothing. 48 h against a 30-minute period is 96 consecutive missed ticks
of slack, far past GitHub's 30-60 min drift. What it does accept is a watcher
stopped for two full days — the failure mode the owner has explicitly chosen to
cover by watching their inbox, with no dead-man's-switch.

**`concurrency: mobile-build-watch`, `cancel-in-progress: false`.** Two
overlapping runs could each see the same errored build before either had opened
its issue, and both would open one. Ticks are 30 min apart and a run takes about
a minute, so queueing costs nothing.

### Owner follow-up

1. `git push` `main`, then `gh workflow run mobile-build-watch.yml` once — nothing
   before the merge exercises a `schedule` trigger, and a scheduled workflow only
   ever runs on the default branch.
2. Expect a **green** run that opens **nothing**: the only two errored builds EAS
   still lists are both older than 48 h. Green with `created=0` is the check
   working, not the check missing something — the run summary lists every row it
   saw and why it skipped it.
3. Still worth the two minutes: check whether expo.dev already mails you on a
   failed build (avatar → Settings → notifications). If it does and it suffices,
   this workflow is redundant and can be deleted — it was written because that
   could not be confirmed from here.
4. Do not manufacture a failed build to watch the issue appear; that spends build
   quota. The next genuine failure will do.
<!-- SECTION:NOTES:END -->
