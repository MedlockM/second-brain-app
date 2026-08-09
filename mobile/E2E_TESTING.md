# Mobile E2E Testing Strategy

## Overview

This document describes the automated end-to-end testing strategy for the Media Summarizer mobile app. The primary framework is **Maestro**, with a targeted **Appium fallback** for iOS share-extension gaps.

Reference ADR: `docs/ADR/mobile-e2e-test-strategy-maestro-first.md`

## Architecture

```
mobile/.maestro/
  config.yaml              # Global configuration (appId, env vars)
  utils/
    login.yaml             # Reusable login sub-flow
  01_login.yaml            # Auth flow verification
  02_share_intake.yaml     # Share intent simulation + confirmation
  03_inbox_visibility.yaml # Inbox item display + states
  04_media_detail_progression.yaml  # Detail screen + transcript status
  05_artifact_trigger_action.yaml   # AI artifact generation trigger
  06_search.yaml           # Algolia lexical search against seeded data
  07_paywall.yaml          # RevenueCat offering and tier visibility
```

## Prerequisites

### Local Development

1. Install Maestro CLI:
   ```bash
   curl -Ls "https://get.maestro.mobile.dev" | bash
   ```

2. Verify installation:
   ```bash
   maestro --version
   ```

3. Have either:
   - An Android emulator running (API 33+), or
   - An iOS Simulator booted (iPhone 15+)

4. Install the app on the device/emulator:
   ```bash
   cd mobile
   npx expo run:android   # Android
   npx expo run:ios       # iOS
   ```

### CI Environment

CI uses GitHub Actions with:
- **Android**: `reactivecircus/android-emulator-runner` on `ubuntu-latest`
- **iOS**: macOS 14 runner with Xcode and iOS Simulator

Required GitHub secrets:
- `E2E_TEST_USER_EMAIL` - Test account with an indexed media item
- `E2E_TEST_USER_PASSWORD` - Test account password, also used by the registration flow
- `E2E_SEARCH_TEST_TERM` - Term present in that account's indexed transcript
- `E2E_REVENUECAT_TEST_KEY` - RevenueCat Test Store public SDK key for both CI platforms
- `E2E_API_BASE_URL` - Optional API override; defaults to the AWS dev endpoint

## Running Tests

### Run All Flows Locally

```bash
cd mobile
maestro test .maestro/
```

### Run a Specific Flow

```bash
maestro test .maestro/02_share_intake.yaml
```

### Run with Custom Environment Variables

```bash
maestro test .maestro/ \
  --env=TEST_USER_EMAIL="your-test@example.com" \
  --env=TEST_USER_PASSWORD="YourPassword123" \
  --env=SHARE_TEST_URL="https://example.com/article"
```

### Run in CI (Manual Dispatch)

Trigger via GitHub Actions > "Mobile E2E Tests (Maestro)" > Run workflow:
- Select platform: `android`, `ios`, or `both`
- Optionally filter to a specific flow file name

## Critical Flows Covered

| # | Flow | What It Tests | Platforms |
|---|------|---------------|-----------|
| 01 | Login | Authentication, navigation to inbox | Android, iOS |
| 02 | Share Intake | Deep link share simulation, confirmation screen, Save action | Android (full), iOS (partial) |
| 03 | Inbox Visibility | Items display after share, processing states, pull-to-refresh | Android, iOS |
| 04 | Media Detail Progression | Detail screen load, transcript status, AI Artifacts section | Android, iOS |
| 05 | Artifact Trigger | Generate button, queued/generating states, completion | Android, iOS |
| 06 | Search | Seeded Algolia result opens its media detail | Android, iOS |
| 07 | Paywall | Three RevenueCat tiers load; no purchase is triggered | Android, iOS |

## Share Intent Testing Approach

### Android (Fully Automated)

On Android, share intents are simulated via deep links using the app's custom URL scheme:
```
media-summarizer://share?url=<encoded-url>&sourceApp=android-share-intent
```

This triggers the same code path as a real Android Share Intent because the `useShareIntent` hook processes URLs received via `Linking.getInitialURL()` and the `url` event listener.

### iOS (Partial Automation + Fallback)

The iOS share extension (`ShareMedia`) is a separate native extension process. Maestro can:
- Test the in-app share confirmation screen via deep links
- Test the full inbox/detail/artifact flows after a share

Maestro **cannot** reliably:
- Trigger the native iOS share sheet from a third-party app
- Interact with the share extension UI rendered in a separate process

This gap is addressed by the Appium fallback strategy below.

## Appium Fallback Strategy (iOS Share Extension)

### When to Use Appium

Use targeted Appium tests **only** for the following scenario:
1. Validating that the iOS share extension appears in the system share sheet
2. Validating that tapping the extension opens the correct UI
3. Validating data transfer from the extension to the main app via App Groups

### When NOT to Use Appium

Do not migrate the following to Appium:
- Login/auth flows (covered by Maestro)
- Inbox/detail/artifact flows (covered by Maestro)
- Any flow that does not require native share sheet interaction

### Appium Setup (If Needed)

If the iOS share extension gap becomes a release blocker, implement targeted Appium coverage as follows:

1. Create `mobile/e2e-appium/` directory with:
   ```
   e2e-appium/
     config/
       wdio.ios.conf.ts      # WebdriverIO + Appium config
     specs/
       ios-share-extension.spec.ts  # Share extension specific test
     package.json
   ```

2. The Appium test should:
   - Open Safari with a test URL
   - Tap the iOS share button
   - Find and tap "Media Summarizer" in the share sheet
   - Verify the share extension UI renders
   - Verify the URL is passed to the main app

3. Run Appium tests separately from Maestro in CI:
   ```yaml
   # Only on macOS runner, only for iOS
   - name: Run Appium iOS share extension test
     run: npx wdio run e2e-appium/config/wdio.ios.conf.ts
   ```

### Decision Criteria

Escalate to Appium if **all** of the following are true:
- A release is blocked specifically by uncertainty about iOS share extension behavior
- The manual E2E matrix (task-41) has identified a regression in share extension
- The regression cannot be caught by Maestro's deep-link-based share simulation

## Failure Triage Guidance

### Understanding Test Results

Maestro produces JUnit XML reports and screenshots/video on failure. In CI, these are uploaded as artifacts.

### Triage Decision Tree

```
Test failed
  |
  +-- Is it a flaky failure? (passes on retry)
  |     |
  |     +-- YES: Tag as flake, check for timing issues
  |     |         - Increase timeout in the assertion
  |     |         - Add explicit wait before the assertion
  |     |         - Consider if backend latency caused it
  |     |
  |     +-- NO: Investigate root cause
  |
  +-- Is it an infrastructure failure? (emulator crash, build failure)
  |     |
  |     +-- YES: Not a product bug. Retry the CI job.
  |     |         Check: AVD cache hit, Maestro version, build output
  |     |
  |     +-- NO: Likely a product regression
  |
  +-- Is it a product regression?
        |
        +-- Which flow failed?
              |
              +-- 01_login: Auth service or login screen broken
              +-- 02_share_intake: Share intent handling or confirmation screen
              +-- 03_inbox_visibility: Inbox rendering or polling logic
              +-- 04_media_detail: Detail screen or transcript display
              +-- 05_artifact_trigger: Artifact API or generation UI
```

### Flake Mitigation

Known sources of flakiness in mobile E2E:
1. **Network latency**: Backend API calls may be slow in CI. Use generous timeouts (10-30s) for assertions that depend on API responses.
2. **Animation timing**: React Native animations may delay element visibility. Use `extendedWaitUntil` with appropriate timeouts.
3. **Emulator startup**: Cold-start emulators are slower. The CI workflow caches AVD snapshots.
4. **State pollution**: Each flow uses `clearState: true` on launch to avoid cross-test contamination.

### Release-Readiness Criteria

A release is considered E2E-ready when:

| Criterion | Required |
|-----------|----------|
| All 5 Maestro flows pass on Android | Yes |
| All 5 Maestro flows pass on iOS (where applicable) | Yes |
| No new flakes introduced in the last 3 runs | Yes |
| iOS share extension manual validation (task-41 matrix) passes | Yes |
| Appium share extension test passes (if implemented) | Only if activated |

### Reporting

After each CI run:
1. Check the GitHub Actions summary for pass/fail status
2. If failed, download the `maestro-*-screenshots` artifact for visual context
3. Review the JUnit XML for specific assertion failures
4. Cross-reference with recent code changes to identify the regression source

## Maintenance

### Adding a New Flow

1. Create a new YAML file in `mobile/.maestro/` with sequential numbering
2. Add appropriate tags in the flow header
3. Reference reusable sub-flows from `utils/` where possible
4. Test locally before committing: `maestro test .maestro/<new-flow>.yaml`

### Updating Environment Variables

- **Local**: Override via `--env` flag or edit `config.yaml`
- **CI**: Update GitHub Actions secrets or workflow env vars

### Maestro Version Updates

The workflow pins a Maestro version via `MAESTRO_VERSION` env var. To update:
1. Test the new version locally
2. Update the env var in `.github/workflows/mobile-e2e-maestro.yml`
3. Verify CI passes with the new version
