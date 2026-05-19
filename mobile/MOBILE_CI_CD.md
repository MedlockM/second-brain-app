# Mobile CI/CD: Build, Sign & Distribute

This document describes the mobile build and distribution pipeline for Media Summarizer.

## Overview

The pipeline uses **EAS Build** (Expo Application Services) for cloud-based native builds
and **EAS Submit** for publishing to TestFlight (iOS) and Google Play Internal Testing (Android).

```
Push to main (mobile/**) or tag mobile-v*
    |
    v
GitHub Actions (.github/workflows/mobile-build-distribute.yml)
    |
    +-- iOS: EAS Build -> EAS Submit -> TestFlight (internal)
    |
    +-- Android: EAS Build -> EAS Submit -> Google Play (internal track)
    |
    +-- On failure: Slack notification + GitHub Issue
```

## Required Secrets & Variables

Configure these in GitHub repository Settings > Secrets and variables > Actions:

### Secrets (required)

| Secret | Description | How to obtain |
|--------|-------------|---------------|
| `EXPO_TOKEN` | Expo access token for EAS CLI authentication | [expo.dev/accounts/tokens](https://expo.dev/accounts/[account]/settings/access-tokens) - Create a Robot token |
| `APPLE_ID` | Apple ID email used for App Store Connect | Your Apple Developer account email |
| `ASC_APP_ID` | App Store Connect App ID (numeric) | App Store Connect > App > General > App Information > Apple ID |
| `APPLE_TEAM_ID` | Apple Developer Team ID | [developer.apple.com/account](https://developer.apple.com/account) > Membership > Team ID |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY` | Full JSON content of Google Play service account key | Google Cloud Console > IAM > Service Accounts (see below) |

### Variables (optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for failure notifications | (none - Slack alerts disabled if unset) |

## Initial Setup

### 1. Expo / EAS Setup

```bash
cd mobile

# Install EAS CLI
npm install -g eas-cli

# Log in to Expo
eas login

# Link the project (first time only)
eas init --id <your-expo-project-id>

# Configure credentials (interactive - follow prompts)
eas credentials
```

### 2. iOS Signing (Apple)

EAS manages iOS signing automatically via its credentials service. On first build:

1. EAS will prompt you to log in with your Apple ID
2. It creates/manages Distribution Certificates and Provisioning Profiles automatically
3. For CI, credentials are stored in EAS servers (not in your repo)

To use your own certificates instead:
```bash
eas credentials --platform ios
# Choose "Manage credentials" > "Set up manually"
```

### 3. Android Signing (Google Play)

#### Keystore (managed by EAS)
EAS generates and manages the upload keystore automatically. To use your own:
```bash
eas credentials --platform android
# Choose "Manage credentials" > "Set up manually" > upload your .jks
```

#### Google Play Service Account Key
1. Go to Google Cloud Console > APIs & Services > Credentials
2. Create a Service Account with "Service Account User" role
3. Grant it access in Google Play Console:
   - Google Play Console > Setup > API access
   - Link the service account
   - Grant "Release manager" permission for your app
4. Create a JSON key for the service account
5. Copy the entire JSON content into the `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY` secret

### 4. App Store Connect Setup

1. Create the app in App Store Connect (bundle ID: `com.mediasummarizer.app`)
2. Enable TestFlight for the app
3. Add internal testers in TestFlight > Internal Testing > Add group
4. Note the numeric App ID for `ASC_APP_ID`

### 5. Google Play Console Setup

1. Create the app in Google Play Console (package: `com.mediasummarizer.app`)
2. Complete the app content declarations
3. Create an Internal Testing track
4. Add internal testers (email list or Google Group)

## Reproducing Builds Locally

### Build locally with EAS

```bash
cd mobile

# Preview/internal build (faster, for testing)
eas build --platform ios --profile preview --local
eas build --platform android --profile preview --local

# Production build
eas build --platform ios --profile production --local
eas build --platform android --profile production --local
```

Note: Local iOS builds require macOS with Xcode installed.

### Submit locally

```bash
# Submit last successful build
eas submit --platform ios --profile production --latest
eas submit --platform android --profile production --latest

# Submit a specific build by ID
eas submit --platform ios --profile production --id <build-id>
```

## Build Profiles

| Profile | Purpose | iOS Output | Android Output |
|---------|---------|-----------|----------------|
| `development` | Local dev with dev client | Simulator build | Debug APK |
| `preview` | Internal testing (ad-hoc) | IPA (internal) | APK (shareable) |
| `production` | Store submission | IPA (App Store) | AAB (Play Store) |

## Workflow Triggers

The pipeline runs automatically when:
- Code is pushed to `main` with changes in `mobile/`
- A tag matching `mobile-v*` is created (e.g., `mobile-v1.0.0`)
- Manually triggered via GitHub Actions UI (workflow_dispatch)

### Manual Trigger Options

| Input | Options | Default |
|-------|---------|---------|
| Platform | ios, android, all | all |
| Profile | preview, production | production |
| Submit | true, false | true |

## Observability & Failure Handling

### Automatic Notifications

When a build or submission fails:
1. **GitHub Step Summary** - Detailed failure info in the workflow run
2. **Slack notification** - Posted to configured webhook (if `SLACK_WEBHOOK_URL` is set)
3. **GitHub Issue** - Auto-created for push-triggered failures (labeled `bug` + `ci/cd`)

### Monitoring Build Status

```bash
# List recent builds
eas build:list --platform all --limit 10

# View specific build
eas build:view <build-id>

# View submission status
eas submit --platform ios --latest --json
```

### EAS Build Dashboard

Visit [expo.dev](https://expo.dev) > Your project > Builds for a web-based view of
all builds, logs, and artifacts.

## Troubleshooting

### iOS: "No matching provisioning profile"

```bash
# Regenerate credentials
eas credentials --platform ios
# Select: Remove existing > Set up new
```

### iOS: "App version already exists in TestFlight"

The `autoIncrement: true` in `eas.json` handles this automatically. If it still occurs:
```bash
# Check current version
eas build:version:get --platform ios

# Set a specific version
eas build:version:set --platform ios --build-number 42
```

### Android: "Upload failed - version code already used"

```bash
# Check current version
eas build:version:get --platform android

# Set a specific version
eas build:version:set --platform android --version-code 42
```

### Android: "Service account key invalid"

1. Verify the JSON key is complete (not truncated) in the GitHub secret
2. Verify the service account has "Release manager" permission in Play Console
3. Verify the API access is enabled: Play Console > Setup > API access

### EAS Build: "Queue timeout"

Free EAS plans have limited concurrent builds. Options:
- Wait and retry (builds are queued)
- Upgrade to EAS Production plan for priority queue
- Use `--local` flag for local builds

### Generic: "EXPO_TOKEN invalid"

1. Verify the token exists and is not expired at expo.dev
2. Create a new Robot token if needed
3. Update the `EXPO_TOKEN` secret in GitHub

## Version Management

Version numbers are managed via EAS remote version source (`appVersionSource: "remote"` in eas.json):

- `autoIncrement: true` on production profile bumps build number automatically
- App version (semver) is set in `app.config.ts` (`version` field)
- To release a new marketing version, update `version` in `app.config.ts`

## Security Notes

- iOS signing credentials are stored in EAS servers (encrypted at rest)
- Android keystore is stored in EAS servers (encrypted at rest)
- The Google Play service account key is written to disk only during the CI job and cleaned up immediately after
- Never commit signing credentials to the repository
- `google-services-key.json` is in `.gitignore`
