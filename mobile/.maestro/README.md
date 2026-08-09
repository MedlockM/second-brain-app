# Maestro E2E

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

## Execution model

- Pull requests and pushes touching `mobile/**` run Android on an emulator.
- `workflow_dispatch` can run Android, iOS, or both.
- iOS stays manual because macOS runner minutes are rationed.
- Release-configuration test binaries embed the JavaScript bundle and do not
  depend on a Metro process in CI.
- Production builds must use their platform-specific `appl_` / `goog_` keys;
  the `test_` key must never be submitted to either store.
- Maestro's exit code is never suppressed; a red flow makes the job red.

For a targeted manual run, select the workflow input `flow_filter` (for
example `06_search`). Reports, screenshots, videos, and Maestro logs are
uploaded by the workflow.
