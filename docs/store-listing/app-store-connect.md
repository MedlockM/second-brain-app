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

**These strings no longer say "transcription", and neither does the app**
(`task-377`, following `docs/research/task-376-subscription-screen-redesign/README.md`
§4.3). The purchase sheet and Settings → Subscriptions are the two places a buyer
reads a subscription Description, so a word retired from the app's own screens
cannot survive here — it would be the only place the buyer meets it.

| Locale | Reader | Mix | Audio-Heavy |
|---|---|---|---|
| en | Unlimited articles + 1 h turned into text. | Unlimited articles + 5 h turned into text. | Unlimited articles + 12 h turned into text. |
| fr | Articles illimités + 1 h mise en texte. | Articles illimités + 5 h mises en texte. | Articles illimités + 12 h mises en texte. |
| es | Artículos ilimitados + 1 h en texto. | Artículos ilimitados + 5 h en texto. | Artículos ilimitados + 12 h en texto. |
| de | Unbegrenzte Artikel + 1 Std. als Text. | Unbegrenzte Artikel + 5 Std. als Text. | Unbegrenzte Artikel + 12 Std. als Text. |
| it | Articoli illimitati + 1 h in testo. | Articoli illimitati + 5 h in testo. | Articoli illimitati + 12 h in testo. |
| pt | Artigos ilimitados + 1 h em texto. | Artigos ilimitados + 5 h em texto. | Artigos ilimitados + 12 h em texto. |
| nl | Onbeperkte artikelen + 1 u als tekst. | Onbeperkte artikelen + 5 u als tekst. | Onbeperkte artikelen + 12 u als tekst. |
| ja | 記事は無制限、1 時間をテキスト化。 | 記事は無制限、5 時間をテキスト化。 | 記事は無制限、12 時間をテキスト化。 |
| zh | 文章不限量，1 小时转成文字。 | 文章不限量，5 小时转成文字。 | 文章不限量，12 小时转成文字。 |
| ar | مقالات بلا حدود + ساعة واحدة نصًا. | مقالات بلا حدود + 5 ساعات نصًا. | مقالات بلا حدود + 12 ساعة نصًا. |
| hi | असीमित लेख + 1 घंटा टेक्स्ट में। | असीमित लेख + 5 घंटे टेक्स्ट में। | असीमित लेख + 12 घंटे टेक्स्ट में। |

The hour unit is lifted from `duration.hours` in the matching locale file — hence
`Std.` in German, `u` in Dutch, and the Arabic form shifting across 1, 5 and 12 the
way the app does it. The *verb* half ("turned into text", « mises en texte »,
`テキスト化`) is the one part not already in a catalogue, because the app no longer
needs to name the operation anywhere: it is proposed by the benchmark and **still
wants one native reader per language before it is pasted into the console** — the
owner's second follow-up in README §11.

**Thirteen App Store entries, not eleven.** Apple has no generic Spanish or
Portuguese: take `Spanish (Spain)` *and* `Spanish (Mexico)`, `Portuguese (Brazil)`
*and* `Portuguese (Portugal)`, same string in each pair, or the Latin American
storefronts fall back to English.

**Every line now clears 45 characters with room to spare** — the longest is English
at 43, and Spanish drops from exactly 45 to 37, so the 40-character Spanish fallback
this table used to carry is no longer needed. Lengths counted in Unicode characters;
the form's own acceptance is still the only verdict that counts.

### What the app says, and where each half of the Description comes from

`pricing_config_service.DEFAULT_PRICING_CONFIG` (`unit_conversion`) settles what a
minute buys, and after `task-377` the paywall states it in a table rather than in
prose, one row per regime the enforcer applies:

| Row on the paywall | Debit | Config key |
|---|---|---|
| Articles, web pages, X posts | free | — (no provider fee) |
| A YouTube video, whatever its length | 1 min flat | `captions_minutes` |
| A podcast that publishes its own text | free | Podcasting 2.0 `<podcast:transcript>` |
| Audio, video, reels, voice notes | real length | — |
| A document or a photo of a page | 1 min per 5 pages | `document_pages_per_minute` |
| Generating across a whole folder | 1 min per 5 items | `folder_sources_per_minute` |

So the Description's two halves map cleanly onto two things the app itself says:

- `Unlimited articles` ← the free row above, plus `plan.minutesRule` under the
  Account tab's usage gauge: « Minutes cover the audio and video you send. Articles
  and web pages cost none, and reading your library is unlimited. » "Cover", not
  "only cover" — documents and folder-wide generations debit minutes too.
- `{N} h turned into text` ← `plan.card.allowance`, which is now **`"{duration} per
  month"`**: the quantity and nothing else. The card carries the amount, the cost
  table right below it says what the amount buys. Naming the operation on the card
  ("of transcription") was jargon in eleven languages and false for half the
  debits, since a PDF read for its text is not transcribed and is billed all the
  same.

The store line still has to name the operation once, because a purchase sheet has no
table under it — hence "turned into text", which is true of every metered path.

**The app never authors a figure.** Allowances, ceilings and the three conversions
arrive from `GET /api/pricing`. If one moves in `DEFAULT_PRICING_CONFIG`, the screen
follows with no build and **these thirteen store strings do not** — re-derive them
from the config by hand.

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
submitting an app version for review, provide required metadata **and** choose the
build for the version. »

**The build half is done.** EAS build `790af106-040c-4798-9599-68ad5b6f0770`
(`distribution: store`, 1.0.0 build 2, commit `ca9cadb`) finished 2026-09-01 and EAS
Submit pushed it to ASC App ID `6778072060` on 2026-09-02, status `finished` — it went
out to a TestFlight beta tester who installed it. TestFlight needs no review, which is
why that worked while the submission is stuck: a build in TestFlight is not a version
added to a submission.

**The metadata half is not**, and the hard blocker is the URLs below. So the order is:
subscriptions left in `Prepare for Submission` → API key in RevenueCat → sandbox
purchase on the TestFlight build → 1.0 metadata and hosted URLs → `Add for Review` on
the version → **one** submission carrying the version *and* the four items.

Nothing before that submission depends on it: RevenueCat imports through the App
Store Connect API key, and sandbox resolution needs the products to exist, not to be
approved.

### The prices shown in TestFlight are not trustworthy

Observed 2026-09-02 on build 1.0.0 (2): the paywall resolved the three subscriptions
and printed `$3.00/mo` and `$4.00/mo` — US dollars, on a French device, for products
whose base prices are set in euros. **Nothing is broken.** RevenueCat documents it:

> In sandbox, StoreKit Test, and TestFlight environments … prices will often not
> reflect the actual prices set in App Store Connect. […] Paywalls or
> `getOfferings()` may return prices in USD when testing through TestFlight, even if
> the tester's storefront is set to another country. […] StoreKit product metadata can
> return prices in USD even when the purchase itself uses the correct local storefront.
> […] RevenueCat passes through the product metadata provided by StoreKit as-is. […]
> Apple's purchase sheet may still show the correct local currency, and purchases can
> complete successfully. This is a known quirk of Apple's TestFlight and sandbox
> environments.

The app is doing the right thing, deliberately: the tier card in
`mobile/app/paywall.tsx` prints `pkg.product.priceString` and
`pkg.product.currencyCode` straight from the SDK, and `formatCurrency` in
`mobile/src/lib/planCopy.ts` says why — money is « only ever fed amounts *derived
from the store package* …, never from the pricing config: the config holds one EUR
figure while the store bills whatever the user's storefront charges ». So there is no
currency to fix in the code, and RevenueCat's own checklist agrees: « Your paywall
isn't hardcoding a specific currency. »

**What to check instead**: « The purchase sheet shows the expected local currency » —
Apple's own sheet, the one that appears after the purchase button. That is the value a
real customer pays. The card above it is metadata, and in TestFlight it lies.

Two figures worth reading anyway, because they *corroborate* the euro bases rather
than contradict them: Apple « provides comparable prices for all 175 App Store
countries and regions, **taking into account taxes and foreign exchange rates** ».
French prices include ~20 % VAT, US prices exclude sales tax, so the converted US
number lands *below* a naive rate conversion — 5 € incl. VAT is ≈ 4.17 € net, hence
$4.00, and 3 € is ≈ 2.50 € net, hence $3.00. Audio-Heavy should sit near $8.

To confirm the euro row directly, Apple's path is: « In Apps, select the app … In the
sidebar, click Subscriptions … Click the subscription group name … Click the
subscription reference name … Scroll down to the Subscription Prices section », then
**View all Subscription Pricing** for the per-territory table (`Export as CSV` there
too). Setting a starting price is `Add Subscription Price` → « Choose a country or
region and price » (the base) → Apple's conversion table, where « If you want to set
different prices for specific storefronts, make the changes ». Required role: Account
Holder, Admin or App Manager. And the same one-hour lag applies here: « It may take up
to 1 hour for changes you make to product metadata to appear in the sandbox
environment. »

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
2. Media Summarizer turns audio, video, documents, and photos into text automatically
3. Generate summaries, notes, and flashcards on demand
4. Review, search, and organize your growing media library

KEY FEATURES

- Universal Share Extension: Share links directly from any app on your phone. No copy-pasting needed.

- Everything Comes Back as Text: Podcasts, YouTube videos, reels, voice notes, PDFs, Office documents, and photos of a page all come back as text you can read, search, and keep.

- Smart Summaries: Get both quick overviews (summary short) and comprehensive breakdowns (summary detailed) of any content.

- Structured Notes: AI-generated notes that capture the key points, arguments, and takeaways in an organized format.

- Flashcards for Retention: Automatically generated question-and-answer flashcards help you remember what matters most.

- Full Text Extraction: Articles and web pages are cleanly extracted - no ads, no clutter, just the content.

- Search Your Library: Find any media by title, source, or content. Your personal knowledge base grows with every share.

- Multi-Platform Support: Works with YouTube, TikTok, Instagram, podcasts (Spotify, Apple Podcasts, Deezer, RSS), X, WhatsApp, articles, and any web page.

SUPPORTED CONTENT TYPES

- YouTube videos
- TikTok videos
- Instagram reels
- Podcast episodes from Spotify, Apple Podcasts, Deezer, or any RSS feed
- X posts
- WhatsApp messages and voice notes
- Web articles, blog posts, and any web page
- Any direct audio link
- Documents: PDF, DOCX, PPTX, XLSX
- Photos and screenshots: JPG, PNG, HEIF, TIFF, BMP
- Audio files: MP3, M4A, AAC, OGG, WAV, FLAC, OPUS

PRICING

Media Summarizer is a subscription, with three monthly plans. Every plan does everything; they differ only in how much you send. Articles, web pages, and X posts cost nothing against your monthly time, and reading your library is always unlimited.

Perfect for students, researchers, lifelong learners, and anyone who consumes more content than they can remember.

Start building your second brain today.
```

## Keywords (max 100 chars, comma-separated)

```
podcast,summarizer,transcription,notes,flashcards,AI,knowledge,second brain,articles,learning
```

`transcription` stays here on purpose. Keywords are **never displayed** — they only
match searches — so retiring the word from every customer-visible surface
(`task-377`) does not mean giving up the people who type it into the search field.

## Promotional Text (max 170 chars)

```
Turn podcasts, videos, and articles into summaries, notes, and flashcards. Share any link and build your personal knowledge base with AI.
```

## What's New (v1.0)

```
Welcome to Media Summarizer! In this first release:

- Share links from any app to start building your media library
- Podcasts, YouTube, TikTok, Instagram, WhatsApp, documents, and photos all come back as text
- Generate short and detailed summaries on demand
- Create structured notes from any content
- Auto-generated flashcards for active recall
- Search across your entire media library
- Clean article extraction without ads or clutter
```

## URLs

**None of these work, and this is what blocks the 1.0 submission.** Checked
2026-09-02:

| Field | Value in this table | Reality |
|-------|--------------------|---------|
| Support URL | https://mediasummarizer.com/support | `mediasummarizer.com` **has no DNS record at all** |
| Marketing URL | https://mediasummarizer.com | same — the domain does not resolve |
| Privacy Policy URL | https://mediasummarizer.com/privacy | same |
| — | https://secondbrainlabs.com/privacy | resolves, answers **404** |
| — | https://secondbrainlabs.com/terms | resolves, answers **404** |

Support URL is a required version property and Privacy Policy URL a required App
Privacy property, so `Add for Review` cannot be satisfied until two pages are actually
served. The texts already exist in the repo — `docs/compliance/privacy-policy.md` and
`terms-of-service.md` — they are simply not hosted anywhere, and the app has no in-app
links to them either (`V1_LAUNCH_PLAN.md` Phase 10). Whatever domain ends up serving
them has to match the marketing name settled by `task-186`, so decide the name first
and host once.

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
