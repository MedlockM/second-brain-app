# App Store Connect Metadata

## App Identity

| Field | Value |
|-------|-------|
| App Name | Media Summarizer |
| Subtitle | Your Second Brain for Media |
| Bundle ID | com.secondbrainlabs.core |
| SKU | com-secondbrainlabs-core-v1 |
| Primary Category | Productivity |
| Secondary Category | Education |

## Subscriptions (In-App Purchases)

Values to paste into **App Store Connect → Apps → Subscriptions**. The product
identifiers are frozen (`docs/research/task-65-pricing-v1-benchmark/README.md`)
and a product ID cannot be renamed once created — copy them exactly. The
RevenueCat side is already wired to these identifiers (`task-261`, layout in
`docs/REVENUECAT_ENTITLEMENTS.md`), so a typo here means a product RevenueCat
never resolves.

### Subscription group

One group for the three plans — that is what makes upgrade/downgrade a switch
inside a group instead of two concurrent subscriptions.

| Field | Value |
|-------|-------|
| Reference Name (internal) | Media Summarizer Plans |
| Localized Display Name (en-US, ≤ 30 chars) | Media Summarizer Plans |

The group display name is customer-visible (iOS Settings → Subscriptions), so if
`task-186` settles on a different marketing name, edit it. Names are editable at
any time; the product identifiers below are not.

### The three monthly subscriptions

| Level | Reference Name | Product ID | Duration | Price (EUR, VAT incl.) |
|-------|----------------|------------|----------|------------------------|
| 3 (lowest) | Reader Monthly | `com.secondbrainlabs.core.text_only_monthly` | 1 month | 3.00 |
| 2 | Mix Monthly | `com.secondbrainlabs.core.mix_monthly` | 1 month | 5.00 |
| 1 (highest) | Audio Heavy Monthly | `com.secondbrainlabs.core.audio_heavy_monthly` | 1 month | 9.00 |

Levels matter: with Audio-Heavy at level 1, moving Reader → Mix → Audio-Heavy is
an immediate upgrade with proration, and the reverse is a downgrade deferred to
the next renewal. Set the price on the France storefront and let Apple convert
the other territories.

### Localizations (en-US)

Display Name is capped at 30 characters, Description at 45.

| Product | Display Name | Description |
|---------|--------------|-------------|
| `…text_only_monthly` | Reader | 1 h of audio and video a month. |
| `…mix_monthly` | Mix | 5 h of audio and video a month. |
| `…audio_heavy_monthly` | Audio-Heavy | 12 h of audio and video a month. |

These are the allowance lines the paywall builds from `minutes_per_month`
(task-299), word for word, so App Review reads the same claim on the store sheet
and on the screen. They replaced three wrong ones: Audio-Heavy still advertised
the allowance it had *before* task-287 cut it, and Mix and Audio-Heavy were
phrased as cumulative (*Reader plus…*, *Mix plus…*) when each tier's allowance
is a total, not an addition. Reader's named documents and captions — both of
which debit minutes — and said nothing about the transcription it includes. The
figures themselves live only in `pricing_config_service.DEFAULT_PRICING_CONFIG`:
if one moves, re-derive these three lines from it.

### Do NOT add an introductory offer

The 30-day free month on the Mix tier is granted **server-side** by account age
(`free_trial` in `media_summarizer/core/services/pricing_config_service.py`, read
by `quota_enforcer._is_free_trial_active`). An App Store introductory offer would
stack on top of it and hand out a second free month, this one billed as a real
subscription period.

### Review screenshot

Each subscription needs one, or it stays `Missing Metadata` and RevenueCat cannot
import it. Minimum 640 × 920 px. A capture of the paywall
(`mobile/app/paywall.tsx`, reachable from the Account tab) showing the three tier
cards satisfies it for all three — Apple only needs to see where the purchase is
offered.

## Description (max 4000 chars)

```
Media Summarizer turns everything you read, watch, and listen to into organized knowledge you can actually use.

Share any link from your favorite apps and get AI-powered summaries, detailed notes, and flashcards in seconds. Podcasts, YouTube videos, articles, TikTok, Instagram, and more - all captured and transformed into your personal knowledge base.

HOW IT WORKS

1. Share a link from any app (Chrome, YouTube, Instagram, TikTok, WhatsApp, podcast apps, and more)
2. Media Summarizer transcribes audio content and extracts text automatically
3. Generate summaries, notes, and flashcards on demand
4. Review, search, and organize your growing media library

KEY FEATURES

- Universal Share Extension: Share links directly from any app on your phone. No copy-pasting needed.

- AI-Powered Transcription: Podcasts, YouTube videos, and social media clips are transcribed with high accuracy using advanced speech recognition.

- Smart Summaries: Get both quick overviews (summary short) and comprehensive breakdowns (summary detailed) of any content.

- Structured Notes: AI-generated notes that capture the key points, arguments, and takeaways in an organized format.

- Flashcards for Retention: Automatically generated question-and-answer flashcards help you remember what matters most.

- Full Text Extraction: Articles and web pages are cleanly extracted - no ads, no clutter, just the content.

- Search Your Library: Find any media by title, source, or content. Your personal knowledge base grows with every share.

- Multi-Platform Support: Works with podcasts (Spotify, Apple Podcasts, Deezer, RSS), YouTube, articles, Instagram, TikTok, and X (Twitter).

SUPPORTED CONTENT TYPES

- Podcasts from any platform
- YouTube videos
- Web articles and blog posts
- TikTok videos
- Instagram posts and reels
- X (Twitter) posts
- Direct RSS feeds

PRICING

Media Summarizer offers a free tier for text-based content (articles, web pages). Audio and video transcription is available on paid plans with generous monthly quotas.

Perfect for students, researchers, lifelong learners, and anyone who consumes more content than they can remember.

Start building your second brain today.
```

## Keywords (max 100 chars, comma-separated)

```
podcast,summarizer,transcription,notes,flashcards,AI,knowledge,second brain,articles,learning
```

## Promotional Text (max 170 chars)

```
Turn podcasts, videos, and articles into summaries, notes, and flashcards. Share any link and build your personal knowledge base with AI.
```

## What's New (v1.0)

```
Welcome to Media Summarizer! In this first release:

- Share links from any app to start building your media library
- AI transcription for podcasts, YouTube, TikTok, Instagram, and more
- Generate short and detailed summaries on demand
- Create structured notes from any content
- Auto-generated flashcards for active recall
- Search across your entire media library
- Clean article extraction without ads or clutter
```

## URLs

| Field | Value |
|-------|-------|
| Support URL | https://mediasummarizer.com/support |
| Marketing URL | https://mediasummarizer.com |
| Privacy Policy URL | https://mediasummarizer.com/privacy |

## Age Rating

- Unrestricted Web Access: No
- Made for Kids: No
- Age Rating: 4+ (no objectionable content generated by the app itself; user-shared content is third-party)

## App Privacy (Data Collection)

| Data Type | Collected | Linked to User | Tracking |
|-----------|-----------|----------------|----------|
| Email Address | Yes | Yes | No |
| User Content (shared URLs) | Yes | Yes | No |
| Identifiers (user ID) | Yes | Yes | No |
| Usage Data | Yes | Yes | No |
| Diagnostics (crash logs) | Yes | No | No |

Purpose: App Functionality, Analytics

## Review Notes for Apple

```
Media Summarizer requires an account to use. A test account will be provided in the review submission.

The app uses a Share Extension to receive URLs from other apps. To test:
1. Open Safari and navigate to any article or YouTube video
2. Tap the Share button
3. Select "Media Summarizer" from the share sheet
4. The link appears in the app's inbox and processing begins

Audio transcription uses Deepgram (third-party speech-to-text service).
AI summaries and notes are generated using large language models via our backend API.
No content is generated on-device.
```
