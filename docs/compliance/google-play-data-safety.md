# Google Play Data Safety Declaration

**Media Summarizer**
**Last updated:** 2026-05-19

This document describes the Data Safety declarations required for Google Play Console submission. Answers map directly to the Data Safety form in Google Play Console.

---

## Overview Section

### Does your app collect or share any of the required user data types?

**Yes**

### Is all of the user data collected by your app encrypted in transit?

**Yes** - All network communication uses HTTPS (TLS 1.2+)

### Do you provide a way for users to request that their data is deleted?

**Yes** - Users can delete individual items in-app and request full account deletion

---

## Data Collected

### 1. Personal Info

#### Email address

| Field | Value |
|-------|-------|
| Collected | Yes |
| Shared | No |
| Ephemeral | No |
| Required | Yes |
| Purpose | App functionality, Account management |

---

### 2. App Activity

#### In-app search history

| Field | Value |
|-------|-------|
| Collected | No |
| Note | Search queries are processed client-side or ephemeral; not persisted on server |

#### Other user-generated content

| Field | Value |
|-------|-------|
| Collected | Yes |
| Shared | No |
| Ephemeral | No |
| Required | Yes |
| Purpose | App functionality |
| Description | URLs submitted for processing and AI-generated artifacts (summaries, notes, quizzes) |

---

### 3. App Info and Performance

#### Crash logs

| Field | Value |
|-------|-------|
| Collected | Yes |
| Shared | No |
| Ephemeral | No |
| Required | No (automatic) |
| Purpose | App functionality (debugging and stability) |

#### Diagnostics

| Field | Value |
|-------|-------|
| Collected | Yes |
| Shared | No |
| Ephemeral | No |
| Required | No (automatic) |
| Purpose | App functionality (performance monitoring) |

---

### 4. Device or Other IDs

#### Device or other IDs

| Field | Value |
|-------|-------|
| Collected | No |
| Note | We do not collect Android Advertising ID or other device identifiers |

---

## Data NOT Collected

The following categories are NOT collected:

- **Location** (approximate or precise)
- **Financial info** (purchase history, credit card, etc.)
- **Health and fitness**
- **Messages** (emails, SMS, other messages)
- **Photos and videos**
- **Audio files** (from device; we fetch audio from third-party URLs server-side)
- **Files and docs**
- **Calendar**
- **Contacts**
- **Web browsing** (we store only explicitly submitted URLs, not browsing history)

---

## Data Shared

**No data is shared with third parties** for purposes outside of providing the core Service.

Note on server-side processing: Our backend sends content to Deepgram (transcription) and OpenAI (AI generation) to provide core app functionality. Per Google's Data Safety guidance, server-side API calls to service providers acting as data processors on our behalf are disclosed as follows:

| Service Provider | Data Processed | Purpose | Retained by Provider |
|-----------------|----------------|---------|---------------------|
| Deepgram | Audio from submitted URLs | Transcription | No (deleted after processing) |
| OpenAI | Text content | AI artifact generation | No (API usage, not used for training) |

These are **not** considered "sharing" under Google Play Data Safety because these providers act as processors under our instructions and do not use the data for independent purposes.

---

## Security Practices

| Practice | Implemented |
|----------|-------------|
| Data encrypted in transit | Yes (TLS 1.2+) |
| Data encrypted at rest | Yes (AWS managed encryption) |
| Secure credential storage | Yes (Android Keystore via expo-secure-store) |
| Data deletion mechanism | Yes (in-app + account deletion) |
| Security review/audit | Planned before production launch |

---

## Data Deletion

### Can users request data deletion?

**Yes**

### How can users request deletion?

1. **In-app:** Users can delete individual media items and their associated artifacts
2. **Account deletion:** Available through account settings or by contacting support
3. **Email:** Users can email privacy@mediasummarizer.com to request full data deletion

### Deletion timeline

- Individual items: deleted immediately
- Full account deletion: all data permanently removed within 30 days

### What data may be retained after deletion?

- Aggregated, anonymized analytics data (cannot be linked back to the user)
- Data required to be retained by law (if applicable)

---

## Google Play Console Form Answers Reference

When completing the Data Safety form in Google Play Console:

1. **Does your app collect or share any of the required user data types?** -> Yes
2. **Is all of the user data collected by your app encrypted in transit?** -> Yes
3. **Do you provide a way for users to request that their data is deleted?** -> Yes
4. **Data types:**
   - Personal info > Email address: Collected, Not shared, Required, App functionality + Account management
   - App activity > Other user-generated content: Collected, Not shared, Required, App functionality
   - App info and performance > Crash logs: Collected, Not shared, Not required, Analytics
   - App info and performance > Diagnostics: Collected, Not shared, Not required, Analytics
5. **Privacy policy URL:** https://mediasummarizer.com/privacy

---

## Notes for Review

- The app uses Android intent filters to receive shared text/URLs from other apps. This is standard share-sheet functionality, not data collection from other apps.
- No Google Play Install Referrer or Advertising ID is used
- No ad SDKs are present
- The `android.permission.INTERNET` permission is used for API communication only
