# Production Release Runbook

This document covers the end-to-end process for publishing Media Summarizer to the
iOS App Store and Google Play Store, including hotfix procedures and rollback strategies.

## Table of Contents

1. [Release Overview](#release-overview)
2. [Version Numbering Strategy](#version-numbering-strategy)
3. [Pre-Release Checklist](#pre-release-checklist)
4. [Production Release Process](#production-release-process)
5. [Post-Release Verification](#post-release-verification)
6. [Hotfix Release Process](#hotfix-release-process)
7. [Rollback Strategy](#rollback-strategy)
8. [Operational Ownership and Escalation](#operational-ownership-and-escalation)
9. [Release Status Tracking](#release-status-tracking)
10. [Communication Templates](#communication-templates)

---

## Release Overview

> **This runbook cannot be executed today, and a `mobile-v*` tag push fails on
> purpose.** Every step below builds the `production` profile, whose
> `EXPO_PUBLIC_API_BASE_URL` host has no DNS record and no zone delegated to it,
> and there is no production API behind that host either. Since 2026-09-03 both CI
> build jobs run `scripts/mobile_release_check.sh <profile>` before `eas build` and
> fail the run in seconds. The reason, the guard and the two conditions that
> unblock this path are in `mobile/MOBILE_CI_CD.md`, section *Why a `mobile-v*` tag
> push is blocked today*. Until then, ship through the `internal` profile
> (TestFlight + Play internal track), not through this runbook.

Media Summarizer uses **EAS Build** and **EAS Submit** for production releases. The
pipeline supports two paths:

- **Standard release**: feature work merged to `main`, tagged, built, and promoted
  through testing tracks before going live.
- **Hotfix release**: critical bugfix on a dedicated branch, expedited build, and
  fast-tracked review submission.

```
feature branch --> main --> tag mobile-v<X.Y.Z>
                              |
                    CI: EAS Build (production profile)
                              |
                    CI: EAS Submit (internal testing)
                              |
                    Manual: Promote to production
                              |
                    App Store / Google Play: Review
                              |
                    Live on stores
```

---

## Version Numbering Strategy

### Semantic Versioning

The app follows **semver** (`MAJOR.MINOR.PATCH`):

| Component | When to bump | Example |
|-----------|-------------|---------|
| MAJOR | Breaking changes, full redesigns | 1.0.0 -> 2.0.0 |
| MINOR | New features, non-breaking additions | 1.0.0 -> 1.1.0 |
| PATCH | Bug fixes, minor improvements | 1.0.0 -> 1.0.1 |

### Where Version Lives

- **Marketing version** (what users see): `version` field in `mobile/app.config.ts`
- **Build number** (internal, auto-incremented): managed by EAS via `autoIncrement: true`
  in `mobile/eas.json`. Each platform increments independently.

### Tagging Convention

Production releases are triggered by git tags:

```
mobile-v1.0.0    # Initial release
mobile-v1.0.1    # Patch (hotfix)
mobile-v1.1.0    # Minor feature release
```

### Build Number Management

```bash
# Check current build numbers
eas build:version:get --platform ios
eas build:version:get --platform android

# Manually set if needed (e.g., after a rollback)
eas build:version:set --platform ios --build-number <N>
eas build:version:set --platform android --version-code <N>
```

---

## Pre-Release Checklist

Complete every item before creating a production tag.

### Code Quality

- [ ] All PRs merged to `main` for this release
- [ ] No critical bugs in the issue tracker
- [ ] TypeScript type-check passes: `cd mobile && npm run typecheck`
- [ ] Linting passes: `cd mobile && npm run lint`

### Automated Testing

- [ ] Maestro E2E flows pass on Android (all 5 critical flows)
- [ ] Maestro E2E flows pass on iOS (all applicable flows)
- [ ] No new flakes in the last 3 CI runs
- [ ] Integration tests pass (backend)

### Manual Validation

- [ ] Manual test checklist completed (`mobile/MANUAL_TEST_CHECKLIST.md`)
- [ ] iOS share extension tested on physical device
- [ ] Android share intent tested on physical device
- [ ] Fresh install flow verified (new user sign-up)
- [ ] Upgrade flow verified (existing user data preserved)

### Store Compliance

- [ ] Privacy policy up to date (`docs/compliance/privacy-policy.md`)
- [ ] Terms of service current (`docs/compliance/terms-of-service.md`)
- [ ] Apple app privacy declarations accurate (`docs/compliance/apple-app-privacy.md`)
- [ ] Google Play data safety section current (`docs/compliance/google-play-data-safety.md`)
- [ ] App Store screenshots current (`docs/store-listing/app-store-connect.md`)
- [ ] Google Play listing metadata current (`docs/store-listing/google-play-store.md`)

### Version Bump

- [ ] `version` field updated in `mobile/app.config.ts`
- [ ] "What's New" text updated for this version (both stores)
- [ ] Changes committed and pushed to `main`

---

## Production Release Process

### Step 1: Create the Release Tag

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Verify the version in app.config.ts matches your intended release
grep "version:" mobile/app.config.ts

# Create and push the tag
git tag mobile-v1.0.0
git push origin mobile-v1.0.0
```

This triggers the `mobile-build-distribute.yml` workflow automatically.

### Step 2: Monitor CI Build

1. Go to GitHub Actions > "Mobile Build & Distribute" workflow
2. Verify both iOS and Android builds complete successfully
3. Verify both submissions to internal testing tracks succeed
4. If build fails, see `mobile/MOBILE_CI_CD.md` troubleshooting section

```bash
# Or check via CLI
eas build:list --platform all --limit 5
```

### Step 3: Internal Testing Validation

After CI submits to testing tracks:

**iOS (TestFlight)**:
1. Open TestFlight app on test devices
2. Install the new build
3. Run through critical flows manually
4. Confirm no crashes or regressions

**Android (Internal Testing)**:
1. Open Play Store opt-in link for internal testers
2. Install the new build
3. Run through critical flows manually
4. Confirm no crashes or regressions

Allow 24-48 hours of internal testing before promoting.

### Step 4: Promote to Production (iOS)

1. Log in to [App Store Connect](https://appstoreconnect.apple.com)
2. Navigate to: My Apps > Media Summarizer > App Store
3. Click the "+" button to create a new version (if not auto-created)
4. Select the build from TestFlight
5. Update "What's New" text for this version
6. Verify screenshots and metadata are current
7. Set release type:
   - **Manual release**: Click "Submit for Review" then manually release after approval
   - **Automatic release**: App goes live immediately after approval
   - **Scheduled release**: Set a date (useful for coordinated launches)
8. Click "Submit for Review"

Expected timeline: Apple review typically takes 24-48 hours (can be faster for updates).

### Step 5: Promote to Production (Android)

1. Log in to [Google Play Console](https://play.google.com/console)
2. Navigate to: Media Summarizer > Release > Production
3. Click "Create new release"
4. Add the build from Internal Testing (or upload the AAB directly)
5. Update release notes
6. Choose rollout percentage:
   - **Staged rollout** (recommended): Start at 10-20%, increase over days
   - **Full rollout**: 100% immediately
7. Click "Review release" then "Start rollout to Production"

Expected timeline: Google review typically takes a few hours to 7 days (first release
takes longer).

### Step 6: Staged Rollout Management (Android)

Google Play supports staged rollouts. Recommended progression:

| Day | Rollout % | Action |
|-----|-----------|--------|
| Day 0 | 10% | Initial rollout, monitor crash rate |
| Day 1 | 25% | If stable, increase |
| Day 3 | 50% | Continue monitoring |
| Day 5 | 100% | Full rollout if no issues |

To increase rollout percentage:
1. Play Console > Release > Production > current release
2. Click "Increase rollout"
3. Set new percentage
4. Click "Update"

### Step 7: Record Release Outcome

Update the release log (see [Release Status Tracking](#release-status-tracking)).

---

## Post-Release Verification

After the app is live on stores:

- [ ] Download from App Store and verify (different Apple ID from developer)
- [ ] Download from Google Play and verify
- [ ] Check crash reporting dashboards (EAS, App Store Connect, Play Console)
- [ ] Monitor user reviews for the first 48 hours
- [ ] Verify backend API handles the new client version correctly
- [ ] Confirm deep links and share extension work on production builds

---

## Hotfix Release Process

For critical bugs that require an expedited release.

### Decision Criteria

Trigger a hotfix when:
- App crashes on launch for a significant user segment
- Data loss or corruption occurs
- Security vulnerability is discovered
- Core functionality (share intake, login) is completely broken

### Hotfix Procedure

#### 1. Create Hotfix Branch

```bash
git checkout main
git pull origin main
git checkout -b hotfix/v1.0.1
```

#### 2. Apply the Fix

- Keep changes minimal -- fix only the critical issue
- No feature work in hotfix branches
- Add a regression test if feasible

#### 3. Test the Fix

```bash
cd mobile
npm run typecheck
npm run lint

# Run Maestro on the affected flow
maestro test .maestro/<relevant-flow>.yaml
```

#### 4. Merge and Tag

```bash
git checkout main
git merge hotfix/v1.0.1
git push origin main

# Bump patch version in app.config.ts
# Commit the version bump

git tag mobile-v1.0.1
git push origin mobile-v1.0.1
```

#### 5. Expedited Review (iOS)

Apple offers expedited review for critical fixes:
1. Submit the new build normally via App Store Connect
2. Go to [Apple Expedited Review Request](https://developer.apple.com/contact/app-store/?topic=expedite)
3. Fill in the form explaining the critical issue
4. Expected turnaround: 24 hours or less

#### 6. Expedited Release (Android)

Google Play does not have a formal expedited review process, but:
1. Submit with 100% rollout (skip staged rollout for critical fixes)
2. Android reviews are typically faster (hours to 1-2 days)
3. Use "Managed publishing" if you need to control exact release timing

#### 7. Communication

Send a hotfix notification using the template in [Communication Templates](#communication-templates).

---

## Rollback Strategy

### Important: Native App Rollback Limitations

Unlike web applications, mobile app rollbacks have fundamental constraints:
- You cannot forcibly remove an installed version from user devices
- Store reviewers do not always allow version number decreases
- Users may have auto-update disabled

### iOS Rollback Options

#### Option A: Remove from Sale (Emergency)

Stops new downloads immediately but existing installs remain:
1. App Store Connect > Pricing and Availability
2. Click "Remove from Sale"
3. The app becomes unavailable for new downloads within hours

#### Option B: Submit a Revert Build

Build and submit a new version that contains the previous code:
```bash
# Check out the last known good version
git checkout mobile-v1.0.0

# Create a new tag with bumped version
# (must be higher than current to pass store validation)
# Edit app.config.ts to set version: "1.0.2"
git tag mobile-v1.0.2
git push origin mobile-v1.0.2
```

Submit this build through the normal review process (or request expedited review).

#### Option C: Phased Release Pause (iOS)

If you are using phased release (automatic staged rollout over 7 days):
1. App Store Connect > App Store > your version
2. Click "Pause Phased Release"
3. This stops the rollout at its current percentage
4. You have 30 days to resume or release a new version

### Android Rollback Options

#### Option A: Halt Staged Rollout

If using staged rollout:
1. Play Console > Release > Production
2. Click "Halt rollout"
3. Users who already received the update keep it
4. New users and remaining users stay on the previous version

#### Option B: Submit a Revert Build

Same as iOS -- build and submit a new version with the old code:
```bash
git checkout mobile-v1.0.0

# Bump version code (must be higher)
# EAS autoIncrement handles this if you just rebuild
eas build --platform android --profile production
eas submit --platform android --profile production --latest
```

#### Option C: Full Rollout of Previous Version

1. Play Console > Release > Production
2. If the previous release is still in the release history, you can promote it again
3. Create a new release pointing to the old AAB artifact

### Rollback Decision Matrix

| Severity | iOS Action | Android Action |
|----------|-----------|---------------|
| Critical (crash on launch) | Remove from sale + expedited revert build | Halt rollout + immediate revert build |
| High (core feature broken) | Pause phased release + revert build | Halt staged rollout + revert build |
| Medium (non-blocking bug) | Submit fix as next patch version | Submit fix and push to staged rollout |
| Low (cosmetic) | Include fix in next scheduled release | Include fix in next scheduled release |

---

## Operational Ownership and Escalation

### Roles

| Role | Responsibility | Person |
|------|---------------|--------|
| Release Owner | Decides when to release, approves promotion to production | Project Owner |
| Build Engineer | Triggers builds, monitors CI, troubleshoots failures | Project Owner |
| On-Call | Monitors post-release health, initiates hotfix/rollback | Project Owner |

Note: As a solo-dev project, all roles are currently held by the project owner.
As the team grows, these responsibilities should be separated.

### Escalation Paths

```
Issue Detected
     |
     v
Check severity (see Rollback Decision Matrix)
     |
     +-- Low/Medium --> File issue, fix in next release
     |
     +-- High/Critical --> Initiate hotfix procedure
                            |
                            v
                    Can the fix be deployed in < 4 hours?
                            |
                            +-- YES --> Hotfix branch + expedited review
                            |
                            +-- NO --> Rollback + communicate to users
```

### Response Time Targets

| Severity | Detection to Triage | Triage to Action | Fix/Rollback Deployed |
|----------|--------------------|-----------------|-----------------------|
| Critical | < 1 hour | < 30 minutes | < 6 hours (+ store review) |
| High | < 4 hours | < 2 hours | < 24 hours |
| Medium | < 24 hours | < 8 hours | Next scheduled release |
| Low | Best effort | Best effort | Next scheduled release |

### Monitoring Channels

- **Crash reports**: EAS dashboard, App Store Connect Crashes, Play Console ANRs and Crashes
- **User feedback**: App Store reviews, Google Play reviews, support email
- **Backend health**: Server logs, API error rates, Deepgram transcription success rate
- **CI status**: GitHub Actions notifications, Slack webhook (if configured)

---

## Release Status Tracking

### Release Log

Maintain a release log at `docs/RELEASE_LOG.md` with the following format for each release:

```markdown
## v1.0.0 - YYYY-MM-DD

**Status**: Live / In Review / Rolled Back / Halted
**Tag**: mobile-v1.0.0
**Build IDs**: iOS: <eas-build-id> | Android: <eas-build-id>

### Timeline
- YYYY-MM-DD HH:MM - Tag created, CI triggered
- YYYY-MM-DD HH:MM - Builds completed
- YYYY-MM-DD HH:MM - Internal testing started
- YYYY-MM-DD HH:MM - Promoted to production review
- YYYY-MM-DD HH:MM - iOS approved, live on App Store
- YYYY-MM-DD HH:MM - Android approved, staged rollout at 10%
- YYYY-MM-DD HH:MM - Android full rollout (100%)

### Changes
- Feature A
- Bug fix B

### Issues Found
- None / description of post-release issues
```

### Status Definitions

| Status | Meaning |
|--------|---------|
| Building | CI is producing artifacts |
| Internal Testing | Build submitted to TestFlight/Internal track |
| In Review | Submitted to store for review |
| Approved | Review passed, pending release |
| Live | Available on stores |
| Staged Rollout (X%) | Android gradual rollout in progress |
| Halted | Staged rollout paused due to issues |
| Rolled Back | Revert version submitted/live |
| Rejected | Store review rejected (action needed) |

---

## Communication Templates

### Release Announcement (Internal)

```
Subject: [Release] Media Summarizer v<X.Y.Z> submitted to stores

Summary: Version <X.Y.Z> has been submitted to the App Store and Google Play
for review.

Key Changes:
- <Change 1>
- <Change 2>

Expected availability: <date range based on typical review times>

Build IDs:
- iOS: <build-id>
- Android: <build-id>

Status tracking: docs/RELEASE_LOG.md
```

### Release Live Notification

```
Subject: [Live] Media Summarizer v<X.Y.Z> is now available

Version <X.Y.Z> is now live on:
- [ ] App Store (iOS)
- [ ] Google Play (Android)

All monitoring channels are green. No action required.
```

### Hotfix Notification

```
Subject: [HOTFIX] Media Summarizer v<X.Y.Z> - <brief description>

A critical issue has been identified:
- Issue: <description>
- Impact: <who/what is affected>
- Severity: Critical / High

Action taken:
- Hotfix branch created: hotfix/v<X.Y.Z>
- Fix: <brief description of the fix>
- ETA for store availability: <estimate>

Current mitigation:
- <any temporary workaround or rollback action taken>
```

### Rollback Notification

```
Subject: [ROLLBACK] Media Summarizer v<X.Y.Z> rolled back

A rollback has been initiated:
- Affected version: v<X.Y.Z>
- Reason: <description>
- Action: <halted rollout / removed from sale / revert build submitted>

Next steps:
- <Investigation timeline>
- <Expected fix timeline>

Users on the affected version: <impact assessment>
```

### Store Review Rejection Response

```
Subject: [Action Required] App Store/Play Store review rejected v<X.Y.Z>

Our submission was rejected:
- Store: <iOS / Android>
- Reason: <rejection reason from reviewer>
- Guidelines cited: <specific guideline numbers>

Plan:
- <What needs to change>
- <Timeline for resubmission>
```

---

## Appendix: Quick Reference Commands

```bash
# Build production
eas build --platform all --profile production

# Submit to stores
eas submit --platform ios --profile production --latest
eas submit --platform android --profile production --latest

# Check build status
eas build:list --platform all --limit 5

# Check version numbers
eas build:version:get --platform ios
eas build:version:get --platform android

# Set version (after rollback)
eas build:version:set --platform ios --build-number <N>
eas build:version:set --platform android --version-code <N>

# Local production build (iOS needs macOS)
eas build --platform ios --profile production --local
eas build --platform android --profile production --local
```
