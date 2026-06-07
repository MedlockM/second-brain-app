# Pre-Review QA Checklist

Run this checklist before every store submission. All items must pass before submitting for review.

## 1. Metadata Consistency

### App Name and Identity

- [ ] App name is identical across both stores ("Media Summarizer")
- [ ] Bundle ID / Package Name matches app.config.ts (`com.secondbrainlabs.core`)
- [ ] Version number in store listing matches the build being submitted
- [ ] Category selections are correct (Productivity primary, Education secondary for iOS)

### Description Accuracy

- [ ] All features mentioned in descriptions are actually functional in the submitted build
- [ ] No mention of features planned but not yet implemented
- [ ] Pricing claims match actual in-app behavior (free tier for text, paid for audio)
- [ ] Supported platform list (Spotify, YouTube, TikTok, etc.) matches implemented connectors
- [ ] No claims of "offline" functionality unless actually implemented in this build
- [ ] "Share from any app" claim is accurate for the platforms tested

### Keywords and Discoverability

- [ ] iOS keywords fit within 100 character limit (count verified)
- [ ] No competitor brand names in keywords (grounds for rejection)
- [ ] Keywords reflect actual app functionality
- [ ] Short description (Google Play) is under 80 characters
- [ ] Promotional text (iOS) is under 170 characters

## 2. Screenshot Accuracy

### Content Matches Current UI

- [ ] All screenshots taken from the exact build version being submitted
- [ ] UI elements in screenshots match the live app (no outdated layouts)
- [ ] Status bar shows realistic time, battery, signal (not debug indicators)
- [ ] No debug banners, developer tools, or placeholder text visible
- [ ] No "lorem ipsum" or obviously fake content

### Technical Requirements

- [ ] iOS screenshots provided for all required device sizes (6.7", 6.5", 5.5")
- [ ] Android screenshots provided at minimum 1080x1920 resolution
- [ ] Minimum screenshot count met (3 for iOS, 2 for Android)
- [ ] No screenshots exceed maximum file size (8 MB for Google Play)
- [ ] Screenshots are in correct orientation (portrait for phone)

### Visual Quality

- [ ] Captions are legible and free of typos
- [ ] Consistent visual style across all screenshots
- [ ] No cropped or stretched content
- [ ] Brand colors are consistent with the live app

## 3. Compliance Cross-Reference

### Privacy and Data Safety

- [ ] Privacy Policy URL is live and accessible (not 404)
- [ ] Privacy Policy content matches the data collection declared in store listings
- [ ] iOS App Privacy declarations match actual data collection
- [ ] Google Play Data Safety section matches actual data collection
- [ ] Account deletion mechanism described and functional
- [ ] Support URL is live and accessible

### Content Declarations

- [ ] iOS age rating answers are accurate (no unrestricted web access in-app)
- [ ] Google Play content rating questionnaire answers are accurate
- [ ] No "Made for Kids" declaration (app is not COPPA-targeted)
- [ ] Third-party service disclosures are accurate (Deepgram for transcription, LLM for generation)

### Platform-Specific Compliance

- [ ] iOS: Share Extension permission strings are clear and accurate (NSExtensionActivationRules)
- [ ] iOS: App Groups entitlement is properly configured
- [ ] Android: Intent filter declarations match actual share capability
- [ ] Android: No unnecessary permissions requested in manifest

## 4. Build Verification

### Pre-Submission Build Check

- [ ] Production build completes without errors (EAS Build success)
- [ ] App launches successfully on a fresh install (no migration crashes)
- [ ] Authentication flow works end-to-end (signup, login, token refresh)
- [ ] Share extension activates from at least 3 different source apps
- [ ] At least one full flow works: share URL -> see in inbox -> view transcript -> generate summary
- [ ] App does not crash on device rotation or backgrounding
- [ ] No ANR (Application Not Responding) on Android during normal use

### Version and Signing

- [ ] Build is signed with production credentials (not development)
- [ ] Version code/build number is higher than any previously submitted build
- [ ] app.config.ts version matches What's New / Release Notes version

## 5. Localization Readiness

### V1 Scope (English Only)

- [ ] All user-facing text in the app is in English
- [ ] Store listing is provided in English (United States) as the default language
- [ ] No untranslated strings or placeholder keys visible in the UI
- [ ] Date/time formatting works correctly for English locales
- [ ] No hardcoded locale-specific content that would break in other regions

### Future Localization Prep

- [ ] Store metadata structure supports adding additional languages later
- [ ] No text baked into screenshot images (or easily re-creatable per locale)

## 6. Common Rejection Prevention

### Apple-Specific Rejection Risks

- [ ] App does not mention "beta" or "test" in public-facing copy
- [ ] No references to other mobile platforms ("also on Android") in iOS listing
- [ ] Share Extension has clear purpose and works reliably
- [ ] Login is required but app purpose is clear before login (description explains value)
- [ ] Demo/test account credentials prepared for review team
- [ ] No broken links in the app (support URL, privacy URL, marketing URL)

### Google-Specific Rejection Risks

- [ ] Data Safety declarations are complete (no "Information not available")
- [ ] App does not request permissions not used (no unused permission warnings)
- [ ] Feature graphic does not contain misleading content
- [ ] Short description does not contain special characters or excessive capitalization
- [ ] No "free" claims if the app has paid features (use "freemium" framing carefully)

## Sign-Off

| Check | Reviewer | Date | Status |
|-------|----------|------|--------|
| Metadata Consistency | | | |
| Screenshot Accuracy | | | |
| Compliance Cross-Reference | | | |
| Build Verification | | | |
| Localization Readiness | | | |
| Rejection Prevention | | | |

**Final approval**: All sections must be checked by at least one reviewer before submission.
