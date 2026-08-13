---
id: task-255
title: Purge the owner's login email from the tracked files and keep it out
status: To Do
assignee: []
created_date: '2026-08-13 15:22'
labels:
  - cleanup
  - compliance
  - security
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner's login email — the address behind the EAS, Google Cloud and AWS accounts — appears in clear text 12 times across 6 tracked files. `AGENTS.md` bans exactly this, and puts it first in the list: a login email is half of a password reset on the account that runs production, and unlike an API key it is not rotatable. It is the owner's billing identity.

Found on 2026-08-13 while auditing an unrelated diff. The value is the address in `git config user.email`, so it is easy to grep for without writing it down again: `git grep -n "$(git config user.email)"`.

**Where it is.** Two tracked files under `tests/` and `scripts/`-adjacent code, one research README, and four task files:

| File | Occurrences | Nature |
|---|---|---|
| `tests/unit/test_purge_e2e_accounts.py` | 2 | assertions `test_real_account_is_never_purgeable` and a `select_accounts` fixture row |
| `docs/research/task-218-durable-media-library-persistence/README.md` | 2 | named regression case |
| `backlog/tasks/task-241 - Backfill-user_media-...` | 3 | description, AC #10, implementation notes |
| `backlog/tasks/task-220 - Migrate-media-library-...` | 2 | AC #11 and the exit-gate paragraph |
| `backlog/tasks/task-246 - Purge-the-orphaned-E2E-accounts-...` | 2 | implementation notes |
| `backlog/tasks/task-239 - Freeze-the-media-library-data-loss-...` | 1 | a row count table |

**What this task is NOT.** It is not a history rewrite. All six files are already on `origin/main`, so the address is already public and a `filter-repo` would not unpublish it — it would only break every clone and every existing commit reference for no security gain. The realistic goal is: stop the bleeding, so that new work does not add occurrence 13, and remove the value from the places where it serves no purpose. If the owner later decides the history matters, that is a separate decision with its own trade-offs.

**The one non-trivial part.** `tests/unit/test_purge_e2e_accounts.py` is not documentation: it is the regression suite of `scripts/purge_e2e_accounts.py`, where a wrong `True` deletes a real account and all its data. The two occurrences are load-bearing — they assert that a real, non-`@test.local` address is never purgeable. So do not just delete those lines: that would silently drop the safety property they encode.

Good news, and it should be verified before changing anything: `scripts/purge_e2e_accounts.py` itself does **not** contain the address. Its protection is structural — `is_purgeable` requires the email to end in `@test.local` and to start with a known throwaway prefix, and `PROTECTED_EMAILS` only holds the permanent Maestro account. Nothing in the production path needs the owner's address. The test can therefore assert the same property with any realistic non-`@test.local` address (`a.real.person@example.com` is enough, and `example.com` is reserved by RFC 2606 for exactly this). Keep the test name and intent; change only the literal.

For the research README and the four task files, the address is used as a human label for "the owner's account". Replace it with something that identifies the account without being a credential. The user id is already written in those files (`4cd1abcb-…` in task-239 and the task-218 README) and, per `AGENTS.md`, a resource identifier is not a secret — so "the owner's account (`4cd1abcb-…`)" carries the full meaning with nothing sensitive. Do not invent a new alias that nobody can resolve.

**Note to the owner — not an AC.** Two things are yours, not the implementer's. First, deciding whether the already-published history warrants any action beyond this task (the recommendation is no). Second: the same audit turned up a live AWS access key in `~/.aws/credentials`; it is outside the repo, absent from the tracked files and absent from the git history, so it is not this task's business — but a key that has been pasted into a terminal is worth rotating on its own schedule.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git grep for the address returned by `git config user.email` finds zero occurrences in tracked files, across code, docs and backlog tasks
- [ ] #2 tests/unit/test_purge_e2e_accounts.py still asserts that a realistic non-@test.local address is never purgeable, and that a real address in a select_accounts population lands in to_keep — same test names, same intent, only the literal replaced by a reserved-domain address
- [ ] #3 scripts/purge_e2e_accounts.py is left unchanged, and it is stated in the Implementation Notes that its protection never relied on the owner's address but on the @test.local domain plus the prefix list
- [ ] #4 In the research README and the four task files, each removed mention is replaced by a formulation that still identifies the owner's account — the user id already present in those files is acceptable, an unresolvable alias is not
- [ ] #5 ruff and mypy stay clean on the touched Python file
- [ ] #6 AGENTS.md's ban is unchanged and no new occurrence is introduced by this task's own notes or commit message
<!-- AC:END -->
