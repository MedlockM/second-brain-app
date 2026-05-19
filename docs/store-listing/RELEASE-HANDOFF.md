# Release Operations Handoff

Step-by-step guide for submitting Media Summarizer to the Apple App Store and Google Play Store.

## Prerequisites

Before starting the submission process, ensure:

- [ ] Production build passes all QA checks (see `QA-CHECKLIST.md`)
- [ ] All store listing metadata finalized (see `app-store-connect.md` and `google-play-store.md`)
- [ ] Screenshots captured and formatted (see `screenshot-specs.md`)
- [ ] Icon and graphic assets at final production quality (see `icon-and-graphics.md`)
- [ ] Privacy policy and terms of service published at their URLs
- [ ] CI/CD pipeline is green on the release branch
- [ ] Test account credentials available for review teams

## Asset File Locations and Naming

### Directory Structure

```
docs/store-listing/
  assets/
    icon-1024.png              # iOS App Store icon
    icon-512.png               # Google Play icon
    adaptive-fg.png            # Android adaptive icon foreground
    feature-graphic.png        # Google Play feature graphic (1024x500)
    screenshots/
      ios/
        6.7/
          01-share-flow.png
          02-inbox.png
          03-transcript.png
          04-summary.png
          05-flashcards.png
          06-search.png
        6.5/
          01-share-flow.png
          ...
        5.5/
          01-share-flow.png
          ...
      android/
        phone/
          01-share-flow.png
          02-inbox.png
          03-transcript.png
          04-summary.png
          05-flashcards.png
          06-search.png
        7-tablet/
          (optional)
        10-tablet/
          (optional)
```

### Naming Convention

- Screenshots: `{NN}-{screen-name}.png` (e.g., `01-share-flow.png`)
- Numbered in display order (stores show them sequentially)
- Use lowercase, hyphens for spaces, no special characters

## iOS Submission: App Store Connect

### Step 1: Trigger Production Build

```bash
cd mobile

# Option A: Via CI (recommended)
git tag mobile-v1.0.0
git push origin mobile-v1.0.0
# CI will build and submit to TestFlight automatically

# Option B: Manual
eas build --platform ios --profile production
eas submit --platform ios --profile production --latest
```

### Step 2: TestFlight Internal Validation

1. Wait for build to appear in TestFlight (usually 5-15 minutes after upload)
2. If "Missing Compliance" warning appears:
   - Go to TestFlight > the build > Manage > Export Compliance
   - Answer: "Does your app use encryption?" -> Yes (HTTPS/TLS)
   - "Is it exempt?" -> Yes (standard HTTPS only, no custom crypto)
3. Install on test device via TestFlight
4. Run through the critical path manually:
   - Sign up / Log in
   - Share a URL from Safari
   - Verify it appears in inbox
   - Wait for transcription
   - Generate a summary
5. Confirm no crashes in Expo/EAS dashboard

### Step 3: Submit for App Store Review

1. Open App Store Connect > Apps > Media Summarizer
2. Go to the current version (1.0)
3. Fill in all metadata:
   - Copy description from `app-store-connect.md`
   - Upload screenshots for each device class
   - Set keywords, promotional text, What's New
   - Set Support URL and Marketing URL
   - Upload app icon (1024x1024)
4. Under "App Review Information":
   - Provide demo account credentials
   - Add notes from the "Review Notes" section of `app-store-connect.md`
   - Set contact information for the review team
5. Under "Version Release":
   - Choose "Manually release this version" (recommended for first release)
6. Select the TestFlight build to submit
7. Click "Submit for Review"

### Step 4: Monitor Review

- Typical review time: 24-48 hours (can be longer for first submission)
- Monitor status in App Store Connect
- Be ready to respond to reviewer questions within 24 hours
- If rejected, see "Common Rejections" section below

## Android Submission: Google Play Console

### Step 1: Trigger Production Build

```bash
cd mobile

# Option A: Via CI (recommended)
git tag mobile-v1.0.0
git push origin mobile-v1.0.0
# CI will build and submit to internal track automatically

# Option B: Manual
eas build --platform android --profile production
eas submit --platform android --profile production --latest
```

### Step 2: Internal Testing Validation

1. Open Google Play Console > Media Summarizer > Testing > Internal testing
2. Verify the build appears (may take a few minutes)
3. Share the internal testing link with test devices
4. Install and test the critical path (same as iOS step 2.4)
5. Check for ANRs and crashes in Play Console > Quality > Android vitals

### Step 3: Complete Store Listing

1. Go to Google Play Console > Grow > Store presence > Main store listing
2. Fill in:
   - App name, short description, full description (from `google-play-store.md`)
   - Upload screenshots for phone (and tablet if available)
   - Upload feature graphic (1024x500)
   - Upload app icon (512x512)
3. Go to Policy > App content and complete:
   - Privacy policy URL
   - Data safety form (from `google-play-store.md` Data Safety section)
   - Content rating questionnaire
   - Target audience declaration
   - News app declaration: No
   - COVID-19 contact tracing: No
   - Data safety: fill from the table in `google-play-store.md`

### Step 4: Promote to Production

1. For first release, promote through tracks:
   - Internal testing (already done) -> Closed testing (optional) -> Production
2. Go to Release > Production > Create new release
3. Add the tested AAB from internal testing
4. Add release notes (What's New text)
5. Review release and roll out:
   - First release: Consider 20% staged rollout
   - Monitor crashes/ANRs for 24-48h before going to 100%
6. Click "Start rollout to Production"

### Step 5: Monitor Review

- Google review typically takes 1-7 days for new apps
- Monitor status in Play Console > Publishing overview
- Check for policy violation emails

## Review Timeline Expectations

| Platform | First Submission | Updates |
|----------|-----------------|---------|
| Apple App Store | 24-72 hours (first app may take longer) | 24-48 hours typically |
| Google Play | 1-7 days (new developer accounts take longer) | 1-3 days typically |

**Tips for faster reviews**:
- Submit early in the week (avoid Friday submissions)
- Provide clear review notes and test credentials
- Ensure all URLs are live and accessible
- Have no placeholder content in the listing

## Common Rejection Reasons and Mitigations

### Apple App Store

| Rejection Reason | Prevention |
|-----------------|------------|
| **Guideline 2.1 - App Completeness**: Placeholder content, broken features | Test every flow before submission; no "coming soon" features in the build |
| **Guideline 2.3 - Accurate Metadata**: Description doesn't match functionality | Cross-check description against QA checklist; remove any unreleased feature mentions |
| **Guideline 4.0 - Design**: Poor UI, non-standard navigation | Follow iOS Human Interface Guidelines; ensure native feel |
| **Guideline 5.1.1 - Data Collection**: Privacy mismatches | Ensure App Privacy declarations exactly match actual data collection |
| **Guideline 5.1.2 - Data Use**: Missing privacy policy | Verify privacy policy URL is live and covers all data types |
| **Login Required**: No way to evaluate without account | Always provide working demo credentials in review notes |
| **Guideline 2.5.1 - Performance**: Crashes during review | Test on same-generation device as reviewers typically use (current-gen iPhone) |

### Google Play Store

| Rejection Reason | Prevention |
|-----------------|------------|
| **Data Safety mismatch** | Data Safety form must exactly match actual data handling |
| **Missing privacy policy** | URL must be live, not password-protected, and relevant to the app |
| **Deceptive behavior** | No background data collection without disclosure |
| **Broken functionality** | Ensure servers are up during review period; test with fresh account |
| **Intellectual property** | No copyrighted content in screenshots or descriptions |
| **Repetitive content** | Avoid keyword stuffing in short/full descriptions |

### Recovery from Rejection

1. Read the rejection reason carefully (Apple provides specific guideline numbers)
2. Fix the cited issue in the next build or metadata update
3. Reply to the reviewer with a clear explanation of what changed
4. Re-submit (replies get prioritized in the review queue on Apple)
5. Document the rejection and fix in the release notes for future reference

## Post-Launch Monitoring

After approval and release:

- [ ] Verify the listing appears correctly in both stores (search by name)
- [ ] Install the production version from the store on a clean device
- [ ] Run through critical path one more time on the store-distributed build
- [ ] Monitor crash reports for the first 48 hours (Expo dashboard + store consoles)
- [ ] Monitor user reviews and respond to any issues within 24 hours
- [ ] Confirm analytics events are flowing (if analytics is configured)

## Hotfix Process

If a critical issue is found after release:

1. Create a hotfix branch from the release tag
2. Fix the issue with minimal changes
3. Bump the build number (not the version number unless necessary)
4. Build and submit using the same process above
5. For Apple: Request expedited review if the issue is a crasher
   - App Store Connect > the rejected build > "Contact Us" > "Request Expedited Review"
6. For Google: Use "Managed publishing" to control exactly when the fix goes live

## Rollback

If a rollback is needed (critical issue, no quick fix available):

### iOS
- Apple does not support true rollback. You must submit a new build.
- Option: Re-submit the previous known-good build with an incremented build number.

### Android
- Google Play Console > Release > Production > Release history
- Select a previous release > "Rollback" (halts staged rollout immediately)
- For full rollback: Promote the previous version's AAB as a new release
