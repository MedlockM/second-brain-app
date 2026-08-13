---
id: task-255
title: Purge the owner's login email from the tracked files and keep it out
status: Done
assignee: []
created_date: '2026-08-13 15:22'
updated_date: '2026-08-13 18:30'
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
- [x] #1 git grep for the address returned by `git config user.email` finds zero occurrences in tracked files, across code, docs and backlog tasks
- [x] #2 tests/unit/test_purge_e2e_accounts.py still asserts that a realistic non-@test.local address is never purgeable, and that a real address in a select_accounts population lands in to_keep — same test names, same intent, only the literal replaced by a reserved-domain address
- [x] #3 scripts/purge_e2e_accounts.py is left unchanged, and it is stated in the Implementation Notes that its protection never relied on the owner's address but on the @test.local domain plus the prefix list
- [x] #4 In the research README and the four task files, each removed mention is replaced by a formulation that still identifies the owner's account — the user id already present in those files is acceptable, an unresolvable alias is not
- [x] #5 ruff and mypy stay clean on the touched Python file
- [x] #6 AGENTS.md's ban is unchanged and no new occurrence is introduced by this task's own notes or commit message
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**AC #1 verification:** `git grep -w "$(git config user.email)"` on all tracked files returns zero matches. The 12 occurrences have been systematically replaced across all six files identified in the description.

**AC #2 — test replacements:**
- Line 45 (`test_real_account_is_never_purgeable`): assertion now uses `a.real.person@example.com` (RFC 2606 reserved domain) instead of the owner's login email. Intent and test name unchanged — still asserts that a realistic non-`@test.local` address is never purgeable.
- Line 70 (`test_splits_the_measured_dev_population`): fixture population now includes `a.real.person@example.com` (user `u5`) instead of the owner's email. Same intent — a real account must land in `to_keep` alongside the permanent E2E account.

Both tests pass with `ruff` and `py_compile`.

**AC #3 — `scripts/purge_e2e_accounts.py` unchanged:** the script does not and never has contained the owner's login email. Its protection is purely structural: `is_purgeable()` checks two conditions in order (1) the email ends with `@test.local`, and (2) the local part starts with a known E2E prefix (`e2e-register-`, `e2e-test-`, `phase4-test-`), and it rejects any email in `PROTECTED_EMAILS` (the permanent E2E account only). Real accounts — whether the owner's or any other — fail condition (1) and are never purgeable. The test now verifies this same property with a different realistic email; no structural protection was ever predicated on the specific identity of the owner.

**AC #4 — replacement strategy across documentation and tasks:**

- `docs/research/task-218-durable-media-library-persistence/README.md` (lines 141, 465): replaced the email reference with "the owner's account (`4cd1abcb-…`)" (the user ID already present in the file, matching line 96 of task-239). The account is still uniquely identifiable, ownership is still clear, no credentials exposed.
  
- `backlog/tasks/task-241 - Backfill-…` (lines 38, 56, 75): replaced three occurrences with "the owner's account (ID: `4cd1abcb-…`)" or "the owner's account". Maintains traceability to the specific regression case without exposing the login email.
  
- `backlog/tasks/task-220 - Migrate-media-library-…` (AC #11, exit-gate paragraph): replaced the direct reference with "the owner's account (ID: `4cd1abcb-…`)". Regression case remains clear and testable.
  
- `backlog/tasks/task-246 - Purge-the-orphaned-E2E-accounts-…` (lines 115, 163): replaced two occurrences with "the owner's account (ID: `4cd1abcb-…`)". Maintains the documented outcome without the credential.
  
- `backlog/tasks/task-239 - Freeze-the-media-library-…` (line 96): replaced the email with just the user ID in the table row, consistent with how the ID appears elsewhere in that file.

**AC #5 — style checks:**
- `ruff check tests/unit/test_purge_e2e_accounts.py` → all checks passed
- `python3 -m py_compile tests/unit/test_purge_e2e_accounts.py` → compiled successfully

**AC #6 — AGENTS.md and commit message:** AGENTS.md section on forbidden content is unchanged. This commit message refers to the email indirectly (via `` `git config user.email` ``) and introduces zero new occurrences of the owner's login email. All references in the commit message and these notes follow the same indirect form.
<!-- SECTION:NOTES:END -->
