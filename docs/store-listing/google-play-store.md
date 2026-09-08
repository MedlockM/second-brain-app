# Google Play Store Metadata

## App Identity

| Field | Value |
|-------|-------|
| App Name (max 30) | Media Summarizer |
| Package Name | com.secondbrainlabs.core |
| Category | Productivity |
| Content Rating | Everyone |

## Subscriptions

The three subscriptions and their monthly base plans **already exist** in Play
Console (created 2026-09-01, imported into RevenueCat — full mapping in
`docs/REVENUECAT_ENTITLEMENTS.md`). What was never written is the customer-facing
copy of the `Edit subscription details` block, which is what this section holds.

| Level | Subscription ID | Base plan | Store identifier | Price (EUR, VAT incl.) |
|---|---|---|---|---|
| lowest | `text_only_monthly` | `monthly` | `text_only_monthly:monthly` | 3.00 |
| middle | `mix_monthly` | `monthly` | `mix_monthly:monthly` | 5.00 |
| highest | `audio_heavy_monthly` | `monthly` | `audio_heavy_monthly:monthly` | 9.00 |

The Play IDs are the bare tier names, not the reverse-DNS iOS ones: Play caps a
product ID at 40 characters and `com.secondbrainlabs.core.text_only_monthly` is 42.
Nothing in the code reads a store product identifier, so the two stores carrying
different ones costs nothing.

### Exact console path

Relevant fields, in the order the form presents them (Play Console UI as of
2026-09-07):

1. **Monetize with Play → Products → Subscriptions**.
2. The **right arrow** next to an existing subscription (`Create subscription` is
   for a new one, which is not needed — all three exist).
3. **Edit subscription details**.
4. **Name** — « A short name for your subscription of up to 55 characters. Users
   will see this in emails and the subscription center. » **The only
   customer-visible field in this block.**
5. **Description** — « This is for your own internal use; it is not shown to users
   on Google Play. » No vocabulary stake at all; use the reference name.
6. **Benefits** — **+ Add benefit**, up to **4**, **40 characters each**, and Play
   forbids mentioning a price or a free trial in them. This is where the app's
   lexicon has to match.
7. **Save changes**. Prices live under the base plan, never in this block.

### Name (≤ 55 characters, customer-visible)

| Subscription | Name | Length |
|---|---|---|
| `text_only_monthly` | Media Summarizer Reader | 23 |
| `mix_monthly` | Media Summarizer Mix | 20 |
| `audio_heavy_monthly` | Media Summarizer Audio-Heavy | 28 |

The tier word (`Reader`, `Mix`, `Audio-Heavy`) is a product name and is never
translated — same rule as the App Store Display Name. The `Media Summarizer` prefix
is the app-name placeholder `task-186` exists to settle; if that task renames the
app, these three Names change with it. They are editable at any time, unlike the
product IDs.

### Benefits (≤ 4 per subscription, 40 characters each)

Same order for the three subscriptions, only the first line differs. The figure in
the first benefit comes from `minutes_per_month` in
`media_summarizer/core/services/pricing_config_service.py` (60 / 300 / 720) — Play
Benefits are static store text, so **if that config moves, these three lines have to
be re-typed by hand**. Nothing else here carries a figure.

| # | Reader | Mix | Audio-Heavy |
|---|---|---|---|
| 1 | 1 h turned into text every month | 5 h turned into text every month | 12 h turned into text every month |
| 2 | Unlimited articles and web pages | Unlimited articles and web pages | Unlimited articles and web pages |
| 3 | Summaries, notes, flashcards, quizzes | Summaries, notes, flashcards, quizzes | Summaries, notes, flashcards, quizzes |
| 4 | Search everything, file it in folders | Search everything, file it in folders | Search everything, file it in folders |

Longest line is 37 characters (benefits 3 and 4), so all twelve clear the 40-character
cap. None names a price and none mentions the free month — which is granted
**server-side by account age** (`free_trial` in `pricing_config_service.py`), not by a
Play introductory offer, so there is nothing to advertise here even if Play allowed
it. Adding one would hand out a second free month, billed as a real period.

The wording is deliberately the same lexicon the app itself uses after `task-377`:
"turned into text" rather than "transcription" (jargon in eleven languages, and false
for a PDF that is read rather than transcribed and billed all the same), and "folders"
because that is the word the app's own folder picker uses in all eleven locales.

## Short Description (max 80 chars)

```
Turn podcasts, videos & articles into AI summaries, notes, and flashcards.
```

## Full Description (max 4000 chars)

```
Media Summarizer turns everything you read, watch, and listen to into organized knowledge you can actually use.

Share any link from your favorite apps and get AI-powered summaries, detailed notes, and flashcards in seconds. Podcasts, YouTube videos, articles, TikTok, Instagram, and more - all captured and transformed into your personal knowledge base.

HOW IT WORKS

1. Share a link from any app (Chrome, YouTube, Instagram, TikTok, WhatsApp, podcast apps, and more)
2. Media Summarizer turns audio, video, documents, and photos into text automatically
3. Generate summaries, notes, and flashcards on demand
4. Review, search, and organize your growing media library

KEY FEATURES

Universal Share: Share links directly from any app on your phone via Android's Share menu. No copy-pasting needed.

Everything Comes Back as Text: Podcasts, YouTube videos, reels, voice notes, PDFs, Office documents, and photos of a page all come back as text you can read, search, and keep.

Smart Summaries: Get both quick overviews and comprehensive breakdowns of any content.

Structured Notes: AI-generated notes that capture the key points, arguments, and takeaways in an organized format.

Flashcards for Retention: Automatically generated question-and-answer flashcards help you remember what matters most.

Full Text Extraction: Articles and web pages are cleanly extracted - no ads, no clutter, just the content.

Search Your Library: Find any media by title, source, or content. Your personal knowledge base grows with every share.

Multi-Platform Support: Works with YouTube, TikTok, Instagram, podcasts (Spotify, Apple Podcasts, Deezer, RSS), X, WhatsApp, articles, and any web page.

SUPPORTED CONTENT TYPES

- YouTube videos
- TikTok videos
- Instagram reels
- Podcast episodes from Spotify, Apple Podcasts, Deezer, or any RSS feed
- X posts
- WhatsApp voice notes
- Notes from your notes app: Apple Notes, Google Keep, Samsung Notes
- Web articles, blog posts, and any web page
- Any direct audio link
- Documents: PDF, DOCX, PPTX, XLSX
- Text files: TXT, MD, RTF
- Photos and screenshots: JPG, PNG, HEIF, TIFF, BMP
- Audio files: MP3, M4A, AAC, OGG, WAV, FLAC, OPUS

PRICING

Media Summarizer is a subscription, with three monthly plans. Every plan does everything; they differ only in how much you send. Articles, web pages, and X posts cost nothing against your monthly time, and reading your library is always unlimited.

Perfect for students, researchers, lifelong learners, and anyone who consumes more content than they can remember.

Start building your second brain today.
```

## Content Rating Questionnaire

| Question | Answer |
|----------|--------|
| Violence | No |
| Sexual Content | No |
| Language | No |
| Controlled Substances | No |
| Gambling | No |
| User-Generated Content | No (app processes third-party URLs but does not host UGC for sharing between users) |
| Ads | No |
| Interactive Elements | Users interact (shares content) |
| Target Audience | General / 18+ (not designed for children) |

**Resulting Rating**: Everyone (ESRB) / PEGI 3

## Data Safety Section

### Data Collection

| Data Type | Collected | Shared | Purpose |
|-----------|-----------|--------|---------|
| Personal info (email) | Yes | No | Account management, authentication |
| App activity (shared URLs, viewing history) | Yes | No | App functionality |
| App info and performance (crash logs, diagnostics) | Yes | No | Analytics, debugging |
| Device or other IDs | Yes | No | Analytics, fraud prevention |

### Security Practices

| Practice | Status |
|----------|--------|
| Data encrypted in transit | Yes (HTTPS/TLS) |
| Data can be deleted by user | Yes (account deletion request) |
| Committed to Play Families Policy | No (not a children's app) |
| Independent security review | No |

### Data Deletion

Users can request account and data deletion via:
- In-app: Settings > Account > Delete Account
- Email: support@mediasummarizer.com

## Contact Details

| Field | Value |
|-------|-------|
| Developer Name | Media Summarizer |
| Email | support@mediasummarizer.com |
| Website | https://mediasummarizer.com |
| Privacy Policy | https://mediasummarizer.com/privacy |

## Store Listing Contact

| Field | Value |
|-------|-------|
| Phone (optional) | -- |
| Address (optional) | -- |

## Tags (max 5)

1. Productivity
2. Education
3. Notes
4. Podcast
5. AI
