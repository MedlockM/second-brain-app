# Manual E2E Validation Matrix - Share-First Mobile Flows

## Purpose

This document defines the manual end-to-end validation matrix for the mobile app's share-first flows. It serves as a release readiness gate, verifying that share intake, processing, inbox display, media detail, and artifact generation work correctly across platforms, source apps, and network conditions.

**Related ADR:** `docs/ADR/mobile-e2e-test-strategy-maestro-first.md`

---

## 1. Device and Platform Matrix

| # | Device Class | Platform | OS Version | Notes |
|---|---|---|---|---|
| D1 | iPhone (recent) | iOS 17+ | Latest stable | Primary iPhone target |
| D2 | iPhone (older) | iOS 16 | - | Minimum supported version |
| D3 | Android flagship | Android 14+ | Latest stable | Primary Android target |
| D4 | Android mid-range | Android 12-13 | - | Lower-end performance |
| D5 | Android (older) | Android 11 | - | Minimum supported version |

---

## 2. Source App Matrix

Each source app below represents a distinct share mechanism. Test each on at least one iOS and one Android device.

| # | Source App | Platform | Share Mechanism | Expected Media Type | Expected Source Platform |
|---|---|---|---|---|---|
| S1 | Safari | iOS | Share Sheet | article | web |
| S2 | Chrome | iOS / Android | Share Sheet / Intent | article | web |
| S3 | YouTube App | iOS / Android | Share Sheet / Intent | youtube_video | youtube |
| S4 | Spotify | iOS / Android | Share Sheet / Intent | podcast_episode | spotify |
| S5 | Apple Podcasts | iOS | Share Sheet | podcast_episode | apple_podcasts |
| S6 | X (Twitter) | iOS / Android | Share Sheet / Intent | short_video / article | x |
| S7 | Instagram | iOS / Android | Share Sheet / Intent | short_video | instagram |
| S8 | TikTok | iOS / Android | Share Sheet / Intent | short_video | tiktok |
| S9 | WhatsApp | iOS / Android | Share Sheet / Intent | article / audio_file | whatsapp |
| S10 | Pocket Casts / Overcast | iOS / Android | Share Sheet / Intent | podcast_episode | rss / podcast_index |
| S11 | Notes / Clipboard (manual paste) | iOS / Android | Direct URL input | unknown | direct_url |
| S12 | Deezer | iOS / Android | Share Sheet / Intent | podcast_episode | deezer |

---

## 3. Network Condition Scenarios

| # | Condition | How to Simulate | Description |
|---|---|---|---|
| N1 | Normal (WiFi) | Standard WiFi connection | Baseline happy-path |
| N2 | Normal (LTE/5G) | Mobile data, good signal | Standard cellular |
| N3 | Degraded (slow) | Network Link Conditioner: 3G profile (iOS) / Android emulator throttle | High latency, low bandwidth |
| N4 | Degraded (lossy) | Network Link Conditioner: 100% Loss for 3s, then resume | Intermittent packet loss |
| N5 | Offline-to-Online | Airplane mode ON, perform action, then Airplane mode OFF | Queued action recovery |
| N6 | Offline (pure) | Airplane mode ON, no recovery during test | Verify error handling and retry UI |
| N7 | Timeout | Network Link Conditioner: Very Slow (>30s RTT) | Request timeout behavior |

---

## 4. Test Scenarios

### 4.1 Share Intake Flow (Share Confirmation Screen)

Tests the path from external app share intent through URL validation to the confirmation screen.

| ID | Scenario | Steps | Expected Result | Pass/Fail Criteria |
|---|---|---|---|---|
| SI-01 | Valid URL share from external app | 1. Open source app 2. Find shareable content 3. Tap Share, select our app | Share confirmation screen opens with URL pre-filled | URL displayed correctly, no validation error |
| SI-02 | URL with surrounding text | Share text containing "Check this out https://example.com/article cool" | URL extracted, confirmation screen shows cleaned URL | Only URL appears in preview, surrounding text stripped |
| SI-03 | Bare domain share | Share "example.com/article" | Scheme auto-prepended, shows https://example.com/article | Valid URL detected and shown |
| SI-04 | Invalid/empty share payload | Share empty text or non-URL text | Validation error displayed: "No link found in the shared content" | Error banner visible, Save button disabled |
| SI-05 | Unsupported scheme (ftp://) | Share "ftp://files.example.com/doc" | Validation error: "No link found in the shared content" | Error shown, cannot submit |
| SI-06 | Save button submits | From SI-01, tap Save | Spinner on Save button, then success checkmark animation, auto-dismiss after 1.5s | Smooth transition, navigates to inbox |
| SI-07 | Close button (X) dismissal | From SI-01, tap X before saving | Returns to inbox, no submission made | No item added to inbox |
| SI-08 | Duplicate URL submission | Share same URL that was already ingested | Success response with `deduplicated: true` | User sees success (no error), item appears in inbox |
| SI-09 | Session expired during submit | Token expired, tap Save | Error: "Your session has expired. Please sign in again." | Error banner with message, Retry visible |
| SI-10 | Rate limited during submit | Submit many URLs rapidly | Error: "Too many requests. Please wait a moment and try again." | Error banner, Retry button functional |

### 4.2 Inbox Screen (Processing States and Polling)

Tests the inbox display with live polling, processing state badges, and pull-to-refresh.

| ID | Scenario | Steps | Expected Result | Pass/Fail Criteria |
|---|---|---|---|---|
| IN-01 | Empty inbox | New user, no shared items | Empty state: share icon, "Your shared media will appear here." message | Empty state renders correctly |
| IN-02 | Optimistic UI after share | Share URL, return to inbox immediately | Item shows in "SUBMITTING" section with spinner | Local item visible before backend confirms |
| IN-03 | Item transitions to backend list | Wait 1-2s after share | Item moves from "SUBMITTING" to "READY FOR REVIEW" section | Smooth transition, no duplicate |
| IN-04 | Processing state: pending | Item just submitted | Badge: "Pending" with spinner | Correct label and color |
| IN-05 | Processing state: classifying | Backend classifies media type | Badge: "Classifying" with spinner | Status updates via polling |
| IN-06 | Processing state: resolving | Backend resolves metadata | Badge: "Resolving" with spinner | Status updates via polling |
| IN-07 | Processing state: downloading | Backend downloads audio | Badge: "Downloading" with spinner | Status updates via polling |
| IN-08 | Processing state: extracting | Backend extracts content | Badge: "Extracting" with spinner | Status updates via polling |
| IN-09 | Processing state: transcribing | Backend transcribes audio | Badge: "Transcribing" with spinner | Status updates via polling |
| IN-10 | Processing state: ready_for_artifacts | Transcript complete | Badge: "Generating summary" with spinner | Correct label |
| IN-11 | Processing state: completed | All processing done | No processing badge shown (terminal) | Item appears without status badge |
| IN-12 | Processing state: failed | Backend reports failure | Badge: "Failed" with error container color | Error state visually distinct |
| IN-13 | Processing state: cancelled | Job cancelled | Badge: "Cancelled" with error container color | Terminal state, no spinner |
| IN-14 | Polling active for non-terminal | Items in pending/downloading/etc. | Network requests every 5s | Verify via dev tools or network monitor |
| IN-15 | Polling stops for terminal items | All items completed/failed/cancelled | No further network requests after terminal | No unnecessary requests |
| IN-16 | Pull-to-refresh | Pull down on list | Refresh indicator, list updates | Data refreshes, indicator dismisses |
| IN-17 | Media type badge: podcast | Share podcast URL | Badge shows "PODCAST" with headset icon | Correct icon and label |
| IN-18 | Media type badge: article | Share article URL | Badge shows "ARTICLE" with document icon | Correct icon and label |
| IN-19 | Media type badge: youtube video | Share YouTube URL | Badge shows "VIDEO" with play icon | Correct icon and label |
| IN-20 | Media type badge: short video | Share TikTok/Instagram URL | Badge shows "SHORT" with play icon | Correct icon and label |
| IN-21 | Media type badge: audio file | Share direct audio file | Badge shows "AUDIO" with music icon | Correct icon and label |
| IN-22 | Daily Digest button | Tap Daily Digest button | Navigates to digest screen | Correct navigation, count badge if items ready |
| IN-23 | Item tap navigates to detail | Tap any media item card | Navigates to media detail screen for that item | Correct ID passed, detail loads |
| IN-24 | Error state with retry | Force network error during fetch | Error screen: "Unable to load your inbox...", Retry button | Error message displayed, Retry reloads |
| IN-25 | App background/foreground | Put app in background 30s, return | Data refreshes on foreground return, polling resumes if needed | No stale data shown |
| IN-26 | Failed local submission | Network error during share save | "SUBMITTING" card shows error state, "Failed" badge, error message | Error clearly visible on the card |
| IN-27 | Greeting changes by time | Check morning/afternoon/evening | "Good Morning/Afternoon/Evening, [name]" | Correct time-of-day greeting |
| IN-28 | Relative time display | Items from just now, 5m, 2h, 1d, 5d ago | Shows "Just now", "5m ago", "2h ago", "Yesterday", "5d ago" | Correct relative formatting |

### 4.3 Media Detail Screen

Tests the media detail view with metadata, transcript status, and artifact actions.

| ID | Scenario | Steps | Expected Result | Pass/Fail Criteria |
|---|---|---|---|---|
| MD-01 | Load completed media | Tap item with status=completed | Title, domain, date, duration shown | All metadata renders |
| MD-02 | Load processing media | Tap item still processing | Title and metadata shown, artifacts section shows "Processing..." | Correct waiting state |
| MD-03 | Back navigation | Tap back arrow | Returns to inbox | Correct navigation |
| MD-04 | Transcript: pending | Item with transcript.status=pending | "Transcript processing will start soon." | Correct message, no spinner crash |
| MD-05 | Transcript: extracting | Item with transcript.status=extracting | "Extracting audio content..." with spinner | Processing indicator shown |
| MD-06 | Transcript: transcribing | Item with transcript.status=transcribing | "Transcribing audio to text..." with spinner | Processing indicator shown |
| MD-07 | Transcript: ready | Item with transcript.status=ready | "Transcript is ready." with checkmark | Green checkmark icon |
| MD-08 | Transcript: failed | Item with transcript.status=failed | "Transcript processing failed." with error icon | Red error icon, red text |
| MD-09 | Transcript metadata | Item with language, duration, segments | Shows language badge, duration, segment count | All metadata chips visible |
| MD-10 | No transcript | Item where transcript is null | "No transcript available yet." | Graceful empty state |
| MD-11 | Artifact toggle expand | Tap "AI Artifacts" section | Artifact rows expand with animation | Smooth LayoutAnimation |
| MD-12 | Artifact toggle collapse | Tap expanded "AI Artifacts" | Rows collapse | Smooth animation |
| MD-13 | Generate Summary | Tap "Generate" on Summary row (media ready) | Optimistic "Queued" state, then polling starts | Button changes to spinner |
| MD-14 | Generate Quiz | Tap "Generate" on Flashcards row | Optimistic "Queued", polling for status | Button changes to spinner |
| MD-15 | Generate Notes | Tap "Generate" on Learning Notes row | Optimistic "Queued", polling for status | Button changes to spinner |
| MD-16 | Artifact: queued state | After generate, before backend starts | Shows "Queued" with spinner | Correct intermediate state |
| MD-17 | Artifact: generating state | Backend processing artifact | Shows "Generating..." with spinner | Polling updates status |
| MD-18 | Artifact: ready state | Artifact generation complete | Shows "Ready" with green checkmark | Terminal state, no spinner |
| MD-19 | Artifact: failed state | Artifact generation failed | Shows "Failed" with Retry button | Retry button functional |
| MD-20 | Artifact retry after failure | Tap Retry on failed artifact | Re-triggers generation, returns to Queued | New generation request sent |
| MD-21 | Generate disabled when processing | Media item not yet ready_for_artifacts | "Processing..." text instead of Generate button | Button not shown |
| MD-22 | Polling stops when done | All artifacts in terminal state | No further /api/media/:id requests | Network traffic ceases |
| MD-23 | Error loading media detail | Network error on GET /api/media/:id | Error icon, message, Retry button | Error state renders, Retry works |
| MD-24 | MEDIA_NOT_FOUND error | 404 on media detail | "This media item was not found or is no longer available." | Correct friendly message |

### 4.4 Error Handling (Canonical Error Codes)

Tests that each canonical error code displays the expected user-friendly message.

| ID | Error Code | Trigger Method | Expected Friendly Message | Pass/Fail Criteria |
|---|---|---|---|---|
| EH-01 | INVALID_URL | Share malformed URL, submit | "This link is invalid. Please try another URL." | Exact message match |
| EH-02 | UNSUPPORTED_URL | Share URL from unsupported platform | "This link is not supported yet. Please try another source." | Exact message match |
| EH-03 | SESSION_EXPIRED | Let token expire, perform action | "Your session has expired. Please sign in again." | Redirects to login or shows message |
| EH-04 | NOT_AUTHORIZED | Access another user's resource | "You don't have permission to perform this action." | Exact message match |
| EH-05 | MEDIA_NOT_FOUND | Navigate to deleted media item | "This media item was not found or is no longer available." | Exact message match |
| EH-06 | ARTIFACT_NOT_FOUND | Access deleted artifact | "This artifact was not found or is no longer available." | Exact message match |
| EH-07 | RATE_LIMITED | Rapid-fire multiple requests | "Too many requests. Please wait a moment and try again." | Exact message match |
| EH-08 | PAYMENT_REQUIRED | User with depleted quota | "You need more minutes or credits to continue." | Exact message match |
| EH-09 | QUOTA_EXCEEDED | User over plan limit | "Your quota has been exceeded. Please upgrade your plan or wait for the next period." | Exact message match |
| EH-10 | INSUFFICIENT_MINUTES | Not enough minutes for operation | "You need more minutes or credits to continue." | Exact message match |
| EH-11 | INTERNAL_ERROR | Backend 500 | "Error" (generic critical) | No technical details leaked |
| EH-12 | BAD_REQUEST | Invalid request body | "Please check your input and try again." | Exact message match |
| EH-13 | CONFLICT | Duplicate conflicting action | "This action conflicts with existing data. Please refresh and try again." | Exact message match |
| EH-14 | VALIDATION_ERROR | Missing required field | "Please fill in all required fields." | Exact message match |
| EH-15 | Network disconnected | Airplane mode during request | "Network error. Please check your connection and try again." | Exact message match |
| EH-16 | Request timeout | Very slow network | "Request timed out. Please try again." | Exact message match |

### 4.5 Network Condition Cross-Scenarios

Tests that share-first flows behave correctly under degraded and offline network conditions.

| ID | Network Condition | Action | Expected Behavior | Pass/Fail Criteria |
|---|---|---|---|---|
| NC-01 | Degraded (N3) | Share URL and submit | Spinner visible longer, eventually succeeds or times out gracefully | No crash, eventual resolution |
| NC-02 | Degraded (N3) | Inbox polling | Polling continues at 5s intervals, UI remains responsive | No frozen UI or ANR |
| NC-03 | Degraded (N4, lossy) | Share URL and submit | May fail once, retry succeeds | Error message + Retry functional |
| NC-04 | Offline (N6) | Open app, view inbox | Cached empty state or error: "Network error..." | Graceful degradation |
| NC-05 | Offline (N6) | Share URL and submit | Immediate error: "Network error. Please check your connection and try again." | Fast failure, no hang |
| NC-06 | Offline-to-Online (N5) | Share URL offline, wait, go online | Submission fails, user taps Retry after connectivity restored, succeeds | Retry works after connectivity |
| NC-07 | Offline-to-Online (N5) | Inbox screen open, go offline 10s, come back | Polling fails silently during offline, resumes on foreground | No error flash during silent polling |
| NC-08 | Timeout (N7) | Generate artifact | "Request timed out. Please try again." after timeout period | Timeout handled gracefully |
| NC-09 | Normal then disconnect | Mid-polling, lose connectivity | Polling fails silently, no error shown (silent mode) | No jarring error mid-session |
| NC-10 | Reconnect after background | Put in background, lose wifi, reconnect, foreground | Refresh on foreground, data loads | Fresh data on return |

### 4.6 Deduplication and Edge Cases

| ID | Scenario | Steps | Expected Result | Pass/Fail Criteria |
|---|---|---|---|---|
| DE-01 | Same URL shared twice (sequential) | Share URL, wait for success, share same URL again | Second share returns `deduplicated: true`, no error shown | User sees success both times |
| DE-02 | Same URL shared twice (rapid) | Share URL, immediately share same URL before first completes | Idempotency key prevents double ingestion | No duplicate items in inbox |
| DE-03 | URL with different casing | Share "https://Example.COM/Path" vs "https://example.com/path" | Backend normalizes, single item | Only one item in inbox |
| DE-04 | URL with tracking params | Share "https://example.com/article?utm_source=twitter" | Backend normalizes URL | Treated correctly (platform decides) |
| DE-05 | Very long URL | Share URL > 2000 characters | Either accepts or shows validation error | No crash or truncation |
| DE-06 | Unicode in URL | Share URL with encoded unicode characters | Handled correctly | No parsing error |
| DE-07 | Multiple URLs in shared text | Share "Check https://a.com and https://b.com" | First URL extracted and submitted | Only one URL processed |

---

## 5. Execution Instructions

### Prerequisites

1. **Devices**: At minimum, one iOS device (physical) and one Android device (physical or emulator with intent support)
2. **Backend**: Staging environment with test accounts provisioned
3. **Build**: Internal distribution build (TestFlight / APK internal track) matching current `second-brain-project` branch
4. **Accounts**: Test user accounts with valid auth tokens and quota
5. **Network tools**:
   - iOS: Settings > Developer > Network Link Conditioner
   - Android: `adb shell settings put global http_proxy` or emulator throttle settings
6. **Source apps installed**: At minimum YouTube, Chrome/Safari, Spotify, X (Twitter), WhatsApp

### Execution Steps

1. Record the **build version**, **device model**, and **OS version** in the results template.
2. Execute each test scenario row by row.
3. For each test, record: Pass / Fail / Blocked / Skipped.
4. For failures and blocking issues, capture:
   - Screenshot or screen recording
   - Steps to reproduce (if different from documented)
   - Error message shown (exact text)
   - Network request/response if relevant (from proxy or dev tools)
5. Re-test any **Blocked** issues after fixes are applied.
6. All **Critical Path** scenarios (SI-01 through SI-06, IN-01 through IN-16, MD-01 through MD-03, MD-13, MD-18) must pass for release.

### Priority Classification

- **P0 (Release Blocker)**: Share intake fails, inbox does not display items, crash on any screen
- **P1 (Must Fix Before Release)**: Processing status not updating, artifacts cannot be generated, error messages incorrect
- **P2 (Can Ship With Known Issue)**: Minor UI glitch, edge case deduplication issue, styling on specific device
- **P3 (Backlog)**: Enhancement ideas discovered during testing

---

## 6. Results Template

Copy and fill for each test run.

### Run Metadata

| Field | Value |
|---|---|
| Tester | |
| Date | |
| Build Version | |
| Backend Environment | |
| iOS Device | |
| iOS OS Version | |
| Android Device | |
| Android OS Version | |

### Results Summary

| Category | Total | Pass | Fail | Blocked | Skipped |
|---|---|---|---|---|---|
| Share Intake (SI) | 10 | | | | |
| Inbox (IN) | 28 | | | | |
| Media Detail (MD) | 24 | | | | |
| Error Handling (EH) | 16 | | | | |
| Network Conditions (NC) | 10 | | | | |
| Deduplication (DE) | 7 | | | | |
| **TOTAL** | **95** | | | | |

### Detailed Results

Use this template for each scenario:

```
| ID | Platform | Result | Notes |
|---|---|---|---|
| SI-01 | iOS | | |
| SI-01 | Android | | |
| ... | ... | ... | ... |
```

### Blocking Issues Log

| # | Scenario ID | Platform | Severity | Description | Steps to Reproduce | Screenshot |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |

---

## 7. Release Readiness Gate Criteria

The following must be satisfied before approving release:

1. **All P0 scenarios pass** on at least one iOS and one Android device
2. **All P1 scenarios pass** or have documented workaround with tracking issue
3. **No regressions** from previous test run (if applicable)
4. **Network resilience** validated: NC-01, NC-04, NC-05, NC-06 pass on both platforms
5. **Error messages** match canonical expectations (EH-01 through EH-16)
6. **Polling behavior** verified: starts for active items, stops for terminal items (IN-14, IN-15)
7. **Source app coverage**: At least 5 distinct source apps tested on each platform (mix of S1-S12)

### Sign-off

| Role | Name | Date | Status |
|---|---|---|---|
| QA Lead | | | Approved / Rejected |
| Product Owner | | | Approved / Rejected |

---

## 8. Canonical Status Reference

For quick reference during testing, these are the statuses defined in `mobile/src/types/media.ts`:

### MediaItemStatus
`ingested` | `resolving` | `processing` | `ready_for_artifacts` | `failed` | `cancelled`

### ProcessingJobLifecycleStatus
`pending` | `classifying` | `resolving` | `downloading` | `extracting` | `transcribing` | `ready_for_artifacts` | `completed` | `failed` | `cancelled`

### TranscriptStatus
`pending` | `extracting` | `transcribing` | `ready` | `failed`

### ArtifactStatus
`queued` | `generating` | `ready` | `failed`

### ArtifactType
`summary` | `quiz` | `notes`

### CanonicalErrorCode
`BAD_REQUEST` | `INVALID_URL` | `UNSUPPORTED_URL` | `SESSION_EXPIRED` | `NOT_AUTHORIZED` | `NOT_FOUND` | `MEDIA_NOT_FOUND` | `ARTIFACT_NOT_FOUND` | `CONFLICT` | `VALIDATION_ERROR` | `RATE_LIMITED` | `PAYMENT_REQUIRED` | `QUOTA_EXCEEDED` | `INSUFFICIENT_MINUTES` | `INTERNAL_ERROR`

### SourcePlatform
`spotify` | `apple_podcasts` | `deezer` | `rss` | `podcast_index` | `youtube` | `instagram` | `tiktok` | `x` | `whatsapp` | `web` | `direct_url` | `unknown`

### MediaType
`podcast_episode` | `article` | `youtube_video` | `short_video` | `audio_file` | `shared_text` | `unknown`
