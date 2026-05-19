# Apple App Privacy Disclosures

**Media Summarizer**
**Last updated:** 2026-05-19

This document describes the App Privacy disclosures required for the Apple App Store submission. These answers correspond to the App Privacy section in App Store Connect.

---

## Privacy Policy URL

`https://mediasummarizer.com/privacy` (must be publicly accessible before submission)

---

## Data Collection Declaration

**Does your app collect data?** Yes

---

## Data Types Collected

### 1. Contact Info

| Data Type | Collected | Linked to Identity | Used for Tracking |
|-----------|-----------|-------------------|-------------------|
| Email Address | Yes | Yes | No |

**Purpose:** App Functionality, Account Registration

---

### 2. User Content

| Data Type | Collected | Linked to Identity | Used for Tracking |
|-----------|-----------|-------------------|-------------------|
| Other User Content | Yes | Yes | No |

**Description:** URLs shared by the user for media processing, and AI-generated artifacts (summaries, notes, quizzes) derived from that content.

**Purpose:** App Functionality

---

### 3. Identifiers

| Data Type | Collected | Linked to Identity | Used for Tracking |
|-----------|-----------|-------------------|-------------------|
| User ID | Yes | Yes | No |

**Purpose:** App Functionality

---

### 4. Usage Data

| Data Type | Collected | Linked to Identity | Used for Tracking |
|-----------|-----------|-------------------|-------------------|
| Product Interaction | Yes | Yes | No |

**Description:** Screens visited, features used, session duration for product improvement.

**Purpose:** Analytics

---

### 5. Diagnostics

| Data Type | Collected | Linked to Identity | Used for Tracking |
|-----------|-----------|-------------------|-------------------|
| Crash Data | Yes | No | No |
| Performance Data | Yes | No | No |

**Purpose:** App Functionality (stability improvement)

---

## Data NOT Collected

The following data types are NOT collected by Media Summarizer:

- Health & Fitness
- Financial Info
- Location
- Sensitive Info
- Contacts
- Browsing History (we only store URLs explicitly submitted by the user, not browsing activity)
- Search History (in-app search queries are not persisted server-side)
- Purchases
- Photos or Videos (photo library permission exists but no photos are uploaded to our servers)
- Audio Data (audio is fetched from third-party URLs, not from the user's device microphone)
- Other Diagnostic Data

---

## Tracking Declaration

**Does your app track users?** No

We do not:

- Link user data with third-party data for advertising purposes
- Share user data with data brokers
- Use advertising identifiers (IDFA)
- Participate in cross-app tracking

The app does NOT use the AppTrackingTransparency framework because no tracking occurs.

---

## Third-Party SDKs / Services

| SDK/Service | Data Accessed | Purpose |
|-------------|---------------|---------|
| Expo | Device info, crash data | App framework, OTA updates |
| Deepgram (server-side only) | Audio content from URLs | Transcription |
| OpenAI (server-side only) | Text content | AI generation |

Note: Deepgram and OpenAI are called server-side only (from our backend), not from the app directly. They do not have SDKs embedded in the app binary.

---

## Data Linked to You (Summary for App Store Label)

The following data is collected and linked to your identity:

- Email Address
- User ID
- User Content (submitted URLs, generated artifacts)
- Product Interaction data

## Data Not Linked to You (Summary for App Store Label)

The following data may be collected but is not linked to your identity:

- Crash Data
- Performance Data

---

## App Store Connect Answers Reference

When filling out App Store Connect, answer as follows:

1. **Do you or your third-party partners collect data from this app?** -> Yes
2. **Privacy Policy URL** -> https://mediasummarizer.com/privacy
3. For each data type above, select the matching category and set:
   - **Linked to Identity**: as marked above
   - **Used for Tracking**: No (for all)
   - **Collection purpose**: as listed above

---

## Notes for Review

- No advertising SDKs are present in the app
- No third-party analytics SDKs that track across apps
- Authentication tokens are stored in iOS Keychain via expo-secure-store
- The share extension (ShareMedia) accesses the same App Group data but does not independently collect or transmit data; it passes URLs to the main app's processing pipeline
