# Maestro E2E

> **Automatic CI is mothballed since 2026-08-13.** The workflow no longer runs
> on `push` or on `pull_request`: the app UI is being redesigned, every flow
> asserts on screen copy and testIDs, so the suite would be rewritten at each
> design iteration. Nothing was deleted — the seven flows, the runner scripts,
> the GitHub secrets and the AWS dev fixture all stay provisioned, and
> `workflow_dispatch` still works (see [Running a run](#running-a-run)).
> Flow-by-flow state at the time of the freeze and the reactivation plan:
> `docs/V1_LAUNCH_PLAN.md`, Phase 7, section « Maestro E2E CI — en sommeil
> depuis le 2026-08-13 ».

The suite covers application-owned UI. Native sheets outside the app process
(Apple/Google authentication and real OS share sheets) stay in tasks 164/165.
No physical Android device is required for this suite: GitHub Actions builds a
self-contained test APK and runs it on an Android emulator.

## CI configuration

Configure these GitHub Actions secrets before running the workflow:

- `E2E_TEST_USER_EMAIL`: existing account with indexed media.
- `E2E_TEST_USER_PASSWORD`: password for that account; it is also used for the
  unique registration created by flow 01.
- `E2E_SEARCH_TEST_TERM`: term present in at least one indexed transcript owned
  by the test account.
- `E2E_REVENUECAT_TEST_KEY`: public RevenueCat Test Store SDK key used only by
  CI development builds on both platforms.
- `E2E_API_BASE_URL` (optional): defaults to the current AWS dev API Gateway.

The workflow passes a unique `MAESTRO_RUN_ID` based on the GitHub run and
attempt, so flow 01 can create an idempotent email address.

## Rotating `E2E_TEST_USER_PASSWORD`

The flows type this password into a text field, so a leak is a real account
takeover on dev — do the rotation whenever a dump, a log, or an artifact may
have carried it. Four steps, none of which can be skipped:

1. `gh secret set E2E_TEST_USER_PASSWORD -R <repo>` with a fresh random value.
   Keep it hex: the value is typed by `inputText`, and characters a soft
   keyboard may transform cost a red suite for no added entropy.
2. Replace `password_hash` on the test account with a bcrypt hash of the new
   value, in **both** `users-dev` and the unsuffixed `users` (task-237 left the
   historical tables in place). Guard the write with a condition on the old
   hash so a concurrent change is not silently overwritten.
3. Revoke every refresh token of that account in `auth_tokens-dev` and
   `auth_tokens` (`user-index` GSI, set `is_active = false` and `used_at`).
   Changing the password does **not** invalidate them: `/auth/refresh` only
   checks `is_active`, `used_at` and expiry, so a 30-day session minted with the
   leaked password would otherwise survive the rotation.
4. Delete the `*-e2e-passed-*` caches before the verification run, keeping the
   build caches. Otherwise `01_login` is reported as `<skipped>` on the strength
   of the previous run and the new credential is never actually exercised.

## Execution model

- No automatic trigger: the `push` and `pull_request` blocks are commented out
  in `.github/workflows/mobile-e2e-maestro.yml` since 2026-08-13. Restoring them
  means removing the comment markers, nothing else.
- `workflow_dispatch` can run Android, iOS, or both, and is the only entry point
  until the UI is frozen.
- iOS stays manual regardless, because macOS runner minutes are rationed.
- Release-configuration test binaries embed the JavaScript bundle and do not
  depend on a Metro process in CI.
- Production builds must use their platform-specific `appl_` / `goog_` keys;
  the `test_` key must never be submitted to either store.
- Maestro's exit code is never suppressed; a red flow makes the job red.

## Running a run

Every run is explicit while the CI is mothballed:

- **From the UI**: Actions > "Mobile E2E Tests (Maestro)" > **Run workflow**,
  then pick `platform` (`android`, `ios`, `both`) and optionally a `flow_filter`
  — a single flow name such as `06_search`, or `suites/tasks_168_170` for the
  three flows known green (`01_login`, `06_search`, `07_paywall`).
- **From a terminal**:
  ```bash
  gh workflow run mobile-e2e-maestro.yml \
    -f platform=android -f flow_filter=suites/tasks_168_170
  ```
- **Locally**, against a booted emulator or simulator with the app installed:
  ```bash
  cd mobile && maestro test .maestro/06_search.yaml
  ```

Reports, hierarchy dumps, and Maestro logs are uploaded by the workflow as
artifacts. Flows `03_inbox_visibility`, `04_media_detail_progression` and
`05_artifact_trigger_action` are known red on their first assertion — do not
include them in a dispatch expecting green.
