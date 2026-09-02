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
| Reference Name (internal) | Second Brain Plans |
| Localized Display Name (en-US, ≤ 30 chars) | Second Brain Plans |

**Created in App Store Connect on 2026-09-02 as `Second Brain Plans`**, not the
`Media Summarizer Plans` this table used to hold. The rest of this file, and the app
itself, still say `Media Summarizer` — the placeholder `task-186` exists to replace
once a marketing name is decided. If `Second Brain` *is* that decision, `task-186`
has to land before the version metadata is written, because the App Store listing,
the screenshots and this group name all consume the final name (`V1_LAUNCH_PLAN.md`
Phase 10, sub-step 0).

The group display name is customer-visible (iOS Settings → Subscriptions). Names are
editable at any time — **except while an item sits in a submission**, see below. The
product identifiers are never editable.

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

### Localizations — all eleven locales

Display Name is capped at 30 characters, Description at 45. **At least one
localization is mandatory** — Apple, on the In-App Purchase reference: « You must
include these properties for at least one language. » Unlike the review screenshot,
these two strings are customer-visible: purchase sheet, and Settings →
Subscriptions.

There is no "adapt automatically" option. Apple serves the localization matching the
user's App Store language and falls back to the **app's primary language** (App
Information — keep it on `English (U.S.)`), so the set you provide *is* the reach.
The app declares eleven locales in `mobile/app.config.ts`, so all eleven are here.

**Display Name is the tier name, identical in every locale** — `Reader`, `Mix`,
`Audio-Heavy`. Product names are never translated (`mobile/src/i18n/fr.ts` header:
"Product names (Reader, Mix, Audio-Heavy)…").

| Locale | Reader | Mix | Audio-Heavy |
|---|---|---|---|
| en | Unlimited articles + 1 h of transcription. | Unlimited articles + 5 h of transcription. | Unlimited articles + 12 h of transcription. |
| fr | Articles illimités + 1 h de transcription. | Articles illimités + 5 h de transcription. | Articles illimités + 12 h de transcription. |
| es | Artículos ilimitados + 1 h de transcripción. | Artículos ilimitados + 5 h de transcripción. | Artículos ilimitados + 12 h de transcripción. |
| de | Unbegrenzte Artikel + 1 Std. Transkription. | Unbegrenzte Artikel + 5 Std. Transkription. | Unbegrenzte Artikel + 12 Std. Transkription. |
| it | Articoli illimitati + 1 h di trascrizione. | Articoli illimitati + 5 h di trascrizione. | Articoli illimitati + 12 h di trascrizione. |
| pt | Artigos ilimitados + 1 h de transcrição. | Artigos ilimitados + 5 h de transcrição. | Artigos ilimitados + 12 h de transcrição. |
| nl | Onbeperkte artikelen + 1 u transcriptie. | Onbeperkte artikelen + 5 u transcriptie. | Onbeperkte artikelen + 12 u transcriptie. |
| ja | 記事は無制限、文字起こし1 時間。 | 記事は無制限、文字起こし5 時間。 | 記事は無制限、文字起こし12 時間。 |
| zh | 文章不限量，转写1 小时。 | 文章不限量，转写5 小时。 | 文章不限量，转写12 小时。 |
| ar | مقالات بلا حدود + ساعة واحدة تحويل إلى نص. | مقالات بلا حدود + 5 ساعات تحويل إلى نص. | مقالات بلا حدود + 12 ساعة تحويل إلى نص. |
| hi | असीमित लेख + 1 घंटा ट्रांसक्रिप्शन। | असीमित लेख + 5 घंटे ट्रांसक्रिप्शन। | असीमित लेख + 12 घंटे ट्रांसक्रिप्शन। |

Every word is lifted from the matching locale file rather than translated afresh:
`transcription` / `Transkription` / `文字起こし` / `تحويل إلى نص` come from
`plan.legend.free` and `plan.highlight.read`, and the hour unit from
`duration.hours` — hence `Std.` in German, `u` in Dutch, and the Arabic plural
shifting between 1, 5 and 12 the way the app does it.

**Thirteen App Store entries, not eleven.** Apple has no generic Spanish or
Portuguese: take `Spanish (Spain)` *and* `Spanish (Mexico)`, `Portuguese (Brazil)`
*and* `Portuguese (Portugal)`, same string in each pair, or the Latin American
storefronts fall back to English.

**Spanish sits at exactly 45 characters** on the Audio-Heavy line. If App Store
Connect refuses it, the 40-character fallback is
`Artículos ilimitados + 12 h transcritas.`

### Why not "N h of audio and video a month"

That was the wording here until 2026-09-02, taken from the app's own
`plan.card.allowance`. It is wrong in both directions, and
`pricing_config_service.DEFAULT_PRICING_CONFIG` (`unit_conversion`) is what settles
it. **Metered**: audio and video at their real length; a video whose captions are
bought, 1 min flat; **a PDF, an Office document or a photo read for its text, 1 min
per 5 pages**; a generation over a whole collection, 1 min per 5 items. **Free and
unlimited** (`plan.legend.free`, verbatim): « Articles, web pages, TikToks and
Instagram photo posts cost nothing at all: they are not transcribed », plus
single-item generations and reading the library.

So the old line hid that articles, web pages, TikToks and Instagram photo posts cost
nothing, and omitted that documents and photos spend the same budget. The chosen
shape carries both halves in 45 characters. The figures live only in
`DEFAULT_PRICING_CONFIG`: if one moves, re-derive these lines from it.

**The app still carries the old wording.** `plan.card.allowance` is
`"{duration} of audio and video"` across the eleven locale files, so the paywall card
and this store sheet now disagree. `task-337` closes that gap — and deliberately does
not paste these 45-character strings onto the card, which has to hold at 20px next to
a price on a 375pt screen.

### Do NOT add an introductory offer

The 30-day free month on the Mix tier is granted **server-side** by account age
(`free_trial` in `media_summarizer/core/services/pricing_config_service.py`, read
by `quota_enforcer._is_free_trial_active`). An App Store introductory offer would
stack on top of it and hand out a second free month, this one billed as a real
subscription period.

### Review screenshot

**It gates the review submission and nothing else.** Verified against the App Store
Connect reference on 2026-09-02: `Missing Metadata` is not a status Apple uses any
more — the list is `Prepare for Submission`, `Ready for Review`, `Waiting for
Review`, `In Review`, `Accepted`, `Approved`, `Rejected`, `Developer Rejected`,
`Developer Removed from Sale`, `Removed from Sale` — and under `Prepare for
Submission` Apple only says « If your In-App Purchase is missing required metadata,
complete it before adding for review ». Neither the RevenueCat import nor StoreKit's
sandbox resolution depends on it. Apple states no dimension of its own ("any of the
screenshot specifications your app supports"); the 640 × 920 figure comes from
RevenueCat, which goes further and accepts a placeholder — « While testing, it's okay
to upload an empty 640 x 920 image here of whatever you want ».

A capture of the paywall (`mobile/app/paywall.tsx`, reachable from the Account tab)
satisfies it for all three — Apple only needs to see where the purchase is offered.
**It can be taken before the products exist**: the paywall renders the three tier
cards from `GET /api/pricing` whatever the store returns, switching off only the
prices, the selection and the purchase button. So take one now, upload it, let
StoreKit resolve the products (up to 1 h for metadata to reach the sandbox), then
retake it with real prices. The screenshot is **updatable but not removable** once
uploaded.

### The first subscription ships with the first app version

« Your first auto-renewable subscription must be submitted with a new app version.
Your first subscription group must also be submitted with a new app version and must
include an auto-renewable subscription in the same submission. » The three
subscriptions cannot be reviewed on their own — they go in the 1.0 submission.

Levels are ordered with **Edit Order** on the group page, « from the one that offers
the most (level 1) to the one that offers the least ».

### Do not put the subscriptions in a submission before 1.0 is ready

Observed on 2026-09-02: a draft submission holding the three subscriptions and the
group refuses to send — « Impossible de soumettre pour vérification. Pour soumettre
vos éléments pour vérification, ajoutez une version de l'app pour la plateforme
sélectionnée. » That is the rule above, enforced. Apple: « If your submission doesn't
include an app version … items will be reviewed together with the latest version of
the platform you specify » — and this app has no version yet, approved or otherwise,
so there is nothing to attach the items to.

**Adding them to a draft submission costs editability.** Status `Ready for Review`
means « Your In-App Purchase has been added to a submission, but you haven't sent the
submission to App Review yet. While your product is in this state, **you can edit only
the reference name, pricing, and availability** » — so the thirteen localizations, the
review screenshot and the duration all freeze, in a submission that cannot be sent.
The way out is **App Review → Submissions → the submission → Cancel Submission →
Confirm**, which returns the items to `Prepare for Submission`.

Adding a version is what unblocks it, and Apple gates that on two things: « Before
submitting an app version for review, provide required metadata and choose the build
for the version. » The build means a real EAS iOS production build uploaded to App
Store Connect; the metadata means the whole 1.0 listing, including a privacy-policy
URL that answers. Neither exists yet, so the correct order is: subscriptions created
and left in `Prepare for Submission` → API key in RevenueCat → sandbox purchase →
build → 1.0 metadata → **one** submission carrying the version *and* the four items.

Nothing before that submission depends on it: RevenueCat imports through the App
Store Connect API key, and sandbox resolution needs the products to exist, not to be
approved.

### TestFlight accelerates renewals

« Each subscription is renewed daily, up to 6 times within a 1-week period,
regardless of the subscription's duration. » A tester's monthly subscription fires a
`RENEWAL` a day for six days and then stops — which is how the webhook loop gets
exercised cheaply, and why a test subscription does not survive a week.

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
