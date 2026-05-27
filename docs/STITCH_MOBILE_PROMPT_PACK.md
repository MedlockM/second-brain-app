# Stitch Prompt Pack - Media Summarizer Mobile Share-First

This document is the current source of truth for generating mobile UI concepts in Stitch.

It follows Stitch guidance:

- start in `App Mode`
- begin with a broad seed prompt
- iterate screen by screen
- make one major change at a time

Primary references:

- https://stitch.withgoogle.com/docs/learn/overview
- https://stitch.withgoogle.com/docs/learn/prompting
- https://stitch.withgoogle.com/docs/learn/device-types
- https://stitch.withgoogle.com/docs/learn/design-modes
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `docs/CANONICAL_MEDIA_API_CONTRACT.md`
- `docs/ADR/mobile-stack-share-first.md`
- `front/src/types/media.ts`

## Repository Truth To Preserve

Use these facts as non-negotiable when generating or reviewing Stitch output:

- Brand name: `Media Summarizer`
- Device type: mobile only, `App Mode`, iOS + Android considered
- Product shape: a mobile knowledge app that turns shared media links into transcripts, reusable AI artifacts, searchable personal knowledge, and a weekly in-app review digest
- Supported source families: podcast episode URLs, article URLs, YouTube URLs, short-form video URLs, direct audio links
- Product stance: transcript-first, not dashboard-first; multi-source, not newspaper-like
- App stack realism: React Native + Expo, Android Share Intent, iOS Share Extension
- UI copy: English only

Approved major product surfaces for design exploration:

- `Inbox`: where shared links arrive and processing is tracked
- `Search`: where users search their private knowledge base with direct keywords and semantically related phrases
- `Weekly Digest`: a once-per-week in-app newsletter surface that summarizes the media sent during the week
- `Account`: auth, preferences, notifications, reading settings, and help

Core flow:

1. user shares a URL from another app
2. app accepts, queues, or rejects it
3. app processes the media into a transcript
4. user can read the transcript and generate `summary`, `quiz`, or `notes` on demand
5. user can search across their submitted-media knowledge base using lexical or semantically related language
6. once per week, user receives an in-app weekly digest notification
7. opening the digest reveals concise but exhaustive summaries of the media submitted that week
8. under each digest summary, the user sees the CTA `Try a quick quiz about this media to see what stuck with you.`
9. tapping that CTA opens an interactive quiz about that media, generated from its transcript

Important product clarifications:

- Search is a first-class app surface, not a minor filter inside history
- Weekly digest is a first-class app surface, not an email workflow
- Past submitted media should remain browsable as an archive or library, but this can be integrated into the Search surface
- Weekly digest summaries are read in-app
- Weekly notification entry can be modeled as push notification, in-app notification center item, or both

Explicit exclusions:

- no billing or checkout screens
- no Spotify account-linking screens
- no newsletter email client UI
- no content delivered by email
- no desktop or tablet-first layouts

Locked public interfaces and states to reflect in UI semantics:

- `POST /api/media/ingest-url`
- `GET /api/media/{media_item_id}`
- `POST /api/media/{media_item_id}/artifacts`
- `GET /api/media/{media_item_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`

- `MediaItem.status`: `ingested | resolving | processing | ready_for_artifacts | failed | cancelled`
- `Transcript.status`: `pending | extracting | transcribing | ready | failed`
- `Artifact.status`: `queued | generating | ready | failed`
- `ProcessingJob.stage`: `pending | classifying | resolving | downloading | extracting | transcribing | ready_for_artifacts | completed | failed | cancelled`

Stable error conditions to support:

- `INVALID_URL`
- `UNSUPPORTED_URL`
- `SESSION_EXPIRED`
- `NOT_AUTHORIZED`
- `MEDIA_NOT_FOUND`
- `QUOTA_EXCEEDED`
- `INSUFFICIENT_MINUTES`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

Unfrozen product areas for design only:

- Search backend and ranking details are not yet frozen; do not expose technical model jargon
- Weekly digest backend contracts are not yet frozen; design the product surface and interaction flow, not speculative API naming

## Recommended Stitch Workflow

1. Create a new Stitch project in `App Mode`.
2. Paste `P01 - Seed Prompt` to generate the first concept.
3. Pick the strongest direction, then run `P02` to lock the visual system.
4. Refine one area at a time with `P03` to `P09`.
5. If a screen drifts, use the scoped edit template at the end of this file instead of regenerating everything.

## P01 - Seed Prompt

Use this first. It is intentionally broad enough to generate the entire app concept while making Search and Weekly Digest first-class product surfaces from the very start.

```text
Design an App Mode mobile UI concept for a product called "Media Summarizer".

This is a share-first iOS and Android app for turning personal media intake into a searchable knowledge base. A user shares a URL from another app into Media Summarizer, the app ingests and processes the media into a faithful transcript, the user can generate optional AI artifacts on demand, the user can search across their submitted-media knowledge base using direct keywords or semantically related language, and once per week the user receives an in-app digest that summarizes the media they sent that week.

Product context:
- Transcript-first experience, not dashboard-first
- Supported sources include podcast episode URLs, article URLs, YouTube URLs, short-form video URLs, and direct audio links
- Major product surfaces must include Inbox, Search, Weekly Digest, and Account
- Past submitted media can be represented as an archive or library, but Search must be a first-class surface, not a buried filter
- Media Detail is the central operational hub for processing status, transcript access, and artifact actions

Canonical API surfaces to reflect in existing UI state flows:
- POST /api/media/ingest-url
- GET /api/media/{media_item_id}
- POST /api/media/{media_item_id}/artifacts
- GET /api/media/{media_item_id}/artifacts
- GET /api/artifacts/{artifact_id}

Design direction:
- bold, modern, and content-forward
- premium, vibrant, contemporary, focused, trustworthy
- colorful in a refined, digital-native way
- avoid generic SaaS card grids and avoid playful or gamified styling
- create a memorable identity with strong composition and a signature motif rooted in multi-source media convergence
- reading screens must stay calm, highly legible, and low-noise
- avoid newspaper, editorial archive, or print-media aesthetics — the product is inherently digital and multi-format

Creative concept:
- use a "modern multi-source media hub" feel rather than a startup dashboard or newspaper archive feel
- the app handles content from podcasts, YouTube, articles, TikTok, Instagram reels, LinkedIn posts, and X threads — the design must reflect this diversity
- introduce source-type visual signatures: subtle iconography, color-coded chips, or format indicators that let users recognize content origin at a glance
- use a signature motif based on media convergence: for example, a stream/flow pattern, layered content cards with source badges, or a rhythm suggesting different media types merging into one knowledge surface
- give the app a strong rhythm through typography, spacing, section dividers, and navigation treatment
- keep long-form reading views clean and focused
- let the shell feel vibrant, polished, and visually alive without becoming busy

Visual system:
- clean, neutral base surfaces with contemporary depth (subtle layering, soft elevation, not paper textures)
- bold, modern sans-serif or geometric typography for headings, highly legible text for body and controls
- a vibrant, harmonious palette with 3 to 5 accent hues that feel digital and alive, such as electric teal, warm coral, bright amber, deep indigo, or vivid green
- gradient accents used sparingly and with sophistication on shell, navigation, and key action surfaces
- micro-animations and transitions that feel fluid and app-native
- keep gradients and color accents away from dense reading text blocks
- no purple-gradient startup aesthetic
- no newspaper, paper textures, ink metaphors, index tabs, annotation rails, or archival dividers

Required screens and states:
- Auth Entry
- Share Intake Confirmation
- Inbox Empty
- Inbox List
- Offline Queue and Sync States
- Search Home
- Search Results
- Search Empty / No Results / Refine Query states
- Weekly notification entry
- Weekly Digest overview
- Weekly Digest item list with concise but exhaustive summary cards
- Digest-driven interactive quiz entry
- Media Detail while ingesting or processing
- Media Detail when transcript is ready for artifacts
- Media Detail failed or cancelled
- Transcript Full View
- Artifact Action Cards
- Artifact Detail Views for summary, quiz, and notes
- Account

Required product behaviors to visualize:
- share-first ingestion and processing
- lexical search with direct keyword matching
- semantic search with semantically related query behavior across the user's own media knowledge base
- weekly in-app digest review flow
- under every digest summary card, show this exact CTA: "Try a quick quiz about this media to see what stuck with you."
- tapping that CTA opens an interactive quiz about the related media

Required product states to visualize:
- media states: ingested, resolving, processing, ready_for_artifacts, failed, cancelled
- transcript states: pending, extracting, transcribing, ready, failed
- artifact states: queued, generating, ready, failed
- processing stages: pending, classifying, resolving, downloading, extracting, transcribing, ready_for_artifacts, completed, failed, cancelled

Required error states to support:
- INVALID_URL
- UNSUPPORTED_URL
- SESSION_EXPIRED
- NOT_AUTHORIZED
- MEDIA_NOT_FOUND
- QUOTA_EXCEEDED
- INSUFFICIENT_MINUTES
- RATE_LIMITED
- INTERNAL_ERROR

Search UX guidance:
- search should feel like querying a private knowledge hub built from transcripts and related artifacts across all media sources
- support both exact term intent and semantically related intent
- results should feel relevant without exposing technical ranking jargon
- allow highlighting of matching snippets, surfaced concepts, or related-media groupings

Weekly Digest guidance:
- this is not email
- the weekly digest is consumed directly inside the app
- the user should receive a once-per-week notification that deep-links into the digest
- digest cards should feel polished, modern, and readable
- each digest card should summarize one media item from the user's week in a concise but exhaustive way

Reading experience:
- transcript and digest/article-like reading views should feel like a modern e-reader
- include a reader mode with reduced chrome, strong typography, stable scrolling, and reading controls

Constraints:
- mobile only, no desktop layouts
- English copy only
- one-handed usability for primary actions
- touch targets at least 44px
- no horizontal clipping on 320 to 430px widths
- no billing screens
- no Spotify linking
- no email newsletter UI
- no content email flows

Output:
- create a complete mobile concept with reusable components and critical loading, offline, retry, error, and success variants
- label the main screens clearly
- show a component system and the most important state variants
```

## P02 - Visual System And Identity

Use this after the seed if the structure is promising but the visual language is too generic.

```text
Edit scope: overall visual system, app shell, main navigation, auth screen, inbox shell, search shell, weekly digest shell

Keep fixed:
- Media Summarizer brand name
- App Mode mobile layout
- first-class surfaces for Inbox, Search, Weekly Digest, and Account
- transcript-first product positioning
- English copy only
- no billing, no Spotify linking, no email newsletter UI

Change request:
- Replace any generic startup look or newspaper/archive aesthetic with a bold, modern, digital-native visual system
- Use clean, neutral base surfaces with contemporary depth (layering, soft elevation) instead of paper textures or ink metaphors
- Make the app feel vibrant and alive through a harmonious palette of 3 to 5 accent hues (e.g., electric teal, warm coral, bright amber, deep indigo, vivid green) with sophisticated gradient accents on shell and navigation
- Use bold, modern sans-serif or geometric typography for headings, with highly legible body text
- Introduce source-type visual signatures: color-coded chips, subtle platform iconography, or format indicators so users can instantly tell whether content came from a podcast, YouTube, article, or social post
- Use a signature motif based on media convergence — for example a stream/flow pattern, layered content cards with source badges, or a visual rhythm suggesting multiple media types merging into one surface
- Make navigation, chips, cards, and section dividers feel authored and memorable rather than template-like
- Include fluid micro-animations and transitions that feel app-native
- Keep transcript, digest, and artifact reading views calmer and more focused than the shell, with reduced chrome and stronger reading comfort
- Remove any paper textures, ink metaphors, index tabs, annotation rails, or archival dividers from the current design

Do not regenerate unrelated screens.
```

## P03 - Share Intake, Inbox, And Offline Queue

Use this to refine the intake and early lifecycle experience.

```text
Edit scope: Share Intake Confirmation, Inbox Empty, Inbox List, Offline Queue and Sync States

Keep fixed:
- current visual identity
- App Mode mobile behavior
- first-class surfaces for Search and Weekly Digest remain visible in the app shell
- share-first product flow

Change request:
- Refine the share entry flow so it feels immediate, native, and confidence-building on both iOS and Android
- The share confirmation screen must clearly show the received host or URL identity, a fast validation signal, and four outcomes: accepted, invalid_url, unsupported_url, queued_offline
- In Inbox List, each media row must show source platform, title or URL snippet, media status, transcript status, and last updated
- Create a clear distinction between items that are only queued locally and items already being processed by the server
- Design offline queue states for queued, syncing, synced, and failed with bounded retry messaging that avoids duplicate anxiety
- Make Inbox Empty feel helpful and product-specific, with a compact explanation of how sharing into the app works
- Keep all primary actions one-handed and thumb-friendly

Do not change search, digest, or reader screens.
```

## P04 - Search, Library, And Results

Use this to make search a major surface instead of a secondary filter.

```text
Edit scope: Search Home, Search Results, Search Empty, Search No Results, archive or library browse states

Keep fixed:
- current visual identity
- App Mode mobile behavior
- search is a first-class surface
- no explicit backend technology claims

Change request:
- Design a powerful but calm Search surface for the user's private media knowledge base
- The user must be able to search by direct keywords and by semantically related language
- Make Search Home feel useful before query entry, with recent queries, suggested concepts, saved themes, or recent media clusters
- Search Results should feel like a knowledge retrieval experience across transcripts and related artifacts, not a generic file finder
- Communicate why results feel relevant using human-readable cues like matched phrase, related concept, transcript passage, or summary match, without exposing ranking jargon
- Include filters or scopes if useful, such as media type, source platform, date range, or artifact availability
- Include empty, no-result, and refine-query states that guide the user clearly
- Keep the archive or history browse state integrated into the search surface so the product still supports retrospective browsing

Do not redesign Inbox or Weekly Digest in this pass.
```

## P05 - Weekly Notification And Weekly Digest

Use this to make the in-app newsletter a major reading and retention surface.

```text
Edit scope: weekly notification entry, Weekly Digest overview, digest list, digest cards, digest empty states

Keep fixed:
- current visual identity
- weekly digest is in-app only, not email
- digest content is based on media the user submitted during the week

Change request:
- Design a once-per-week notification entry that deep-links into the Weekly Digest
- The Weekly Digest must feel like a premium editorial review of the user's week, not like a push-notification inbox
- The digest should present a list of media items from that week, each with a concise but exhaustive summary
- Each digest summary card must include this exact CTA text: "Try a quick quiz about this media to see what stuck with you."
- Make the digest easy to scan, but comfortable to read at length
- Include edge states for no eligible media this week, a very long week with many media items, and partial artifact availability
- The digest should feel reusable and revisitable later, not ephemeral like a toast

Do not redesign Search or Media Detail in this pass.
```

## P06 - Media Detail States

Use this to lock the operational heart of the product.

```text
Edit scope: Media Detail screens for in-progress, ready_for_artifacts, failed, and cancelled states

Keep fixed:
- current visual system
- transcript-first behavior
- on-demand artifacts only
- Search and Weekly Digest remain first-class surfaces elsewhere in the app

Change request:
- Make Media Detail the clear operational hub of the product
- For in-progress states, show a strong progress module with stage, percentage, timestamps, and next expectation
- Reflect these processing stages in a readable, mobile-native way: pending, classifying, resolving, downloading, extracting, transcribing, ready_for_artifacts, completed, failed, cancelled
- When transcript is ready, present a compact transcript summary card with source, language, and duration metadata
- Create a distinct action zone for Generate Summary, Generate Quiz, and Generate Notes, with each action clearly independent
- For failed and cancelled states, show safe recovery paths for MEDIA_NOT_FOUND, NOT_AUTHORIZED, INTERNAL_ERROR, and generic retryable failures
- Ensure retry, cancel, refresh, and passive polling states feel coherent and not cluttered

Do not redesign Search, Digest, or Account in this pass.
```

## P07 - Transcript Full View And Reader Mode

Use this when the transcript reading surface needs to become exceptional rather than merely functional.

```text
Edit scope: Transcript Full View and Reader Mode

Keep fixed:
- current visual identity
- existing information architecture
- transcript-first positioning

Change request:
- Turn the transcript screen into a true long-form reading surface with e-reader quality comfort
- Create two related modes: a standard transcript view and a more immersive Reader Mode
- Include search within transcript, segment jump behavior, copy excerpt action, and a clear resume-reading affordance
- Reader Mode must minimize chrome and include controls for font size, line height, and reading margins
- Include theme presets named Light, Warm, and Night
- Preserve reading progress and make the view feel stable, quiet, and high-focus
- Keep the screen original and modern, but never at the expense of readability or accessibility

Do not change Search or Weekly Digest layouts.
```

## P08 - Artifact Actions, Interactive Quiz, And Artifact Details

Use this to refine the AI artifact layer, including quiz entry from the weekly digest.

```text
Edit scope: Artifact action cards, artifact state variants, interactive quiz screen, artifact detail screens for summary, quiz, and notes

Keep fixed:
- current visual identity
- Media Detail structure
- digest card CTA text remains exact
- no automatic artifact generation

Change request:
- Make artifact actions feel clear, premium, and non-blocking
- Each artifact type must support idle, queued, generating, ready, and failed states independently
- Design summary, quiz, and notes cards so one artifact can fail without making the others feel broken
- The interactive quiz surface must work both as a destination from Media Detail and as the destination opened from a Weekly Digest CTA
- If a digest-triggered quiz is not ready yet, show a graceful queued or generating state before the interactive quiz opens
- Summary detail should emphasize main topics, key points, notable quotes, and conclusion
- Quiz detail should emphasize question cards, answer reveal interactions, progress through questions, and clear feedback after each answer
- Notes detail should emphasize objectives, concepts, key points, action items, and glossary
- Artifact detail reading surfaces should inherit the calm, high-legibility reading quality of the transcript experience

Do not redesign Search or Inbox in this pass.
```

## P09 - Account, Notifications, And Preferences

Use this once the main creation, search, and weekly-digest flows are stable.

```text
Edit scope: Account, preferences, notification settings, help, sign-out

Keep fixed:
- current visual identity
- no billing or checkout surfaces
- weekly digest stays in-app, not email

Change request:
- Account should cover session restore, session expired re-auth path, reading preferences, share help, weekly notification preferences, and sign out
- Include controls or messaging for weekly digest notifications without turning the screen into a system settings clone
- If quota or minutes are exhausted, show informative blocking states only, without any pricing or purchase flow
- Keep the Account area useful and product-specific, not a generic settings dump

Do not change Search, Digest, or Reader layouts.
```

## Scoped Edit Template

Use this for any later iteration that should stay narrow and predictable.

```text
Edit scope: [screen IDs or named screens/components]

Keep fixed:
- [elements, layout logic, or brand decisions that must remain unchanged]

Change request:
- [one focused change]
- [optional second focused change]

Do not regenerate unrelated screens.
```

## Validation Checklist For Stitch Output

Use this checklist after each generation pass.

### Device And Layout

- Project is generated in `App Mode`
- Layout feels natively mobile, not like compressed web
- No horizontal clipping on `320-360` or `390-430` widths
- Primary actions stay reachable one-handed
- Touch targets look at least `44px`

### Screen Coverage

- Auth
- Share Intake Confirmation
- Inbox Empty
- Inbox List
- Offline Queue
- Search Home
- Search Results
- Search Empty / No Results
- Weekly notification entry
- Weekly Digest overview
- Weekly Digest summary list
- Digest-driven interactive quiz entry
- Media Detail in progress
- Media Detail ready
- Media Detail failed or cancelled
- Transcript Full View
- Reader Mode
- Artifact action states
- Summary detail
- Quiz detail
- Notes detail
- Account

### State Coverage

- Media states: `ingested`, `resolving`, `processing`, `ready_for_artifacts`, `failed`, `cancelled`
- Transcript states: `pending`, `extracting`, `transcribing`, `ready`, `failed`
- Artifact states: `queued`, `generating`, `ready`, `failed`
- Local queue states: `queued`, `syncing`, `synced`, `failed`
- Digest quiz CTA states: available, queued, generating, ready, failed

### Product Correctness

- Inbox, Search, Weekly Digest, and Account feel like first-class surfaces
- Media Detail is the hub for transcript and artifact actions
- Transcript comes before artifact generation
- Artifact actions are on demand and independent
- Output supports podcast, article, YouTube, short video, and direct audio use cases
- Search visibly supports direct keyword queries and semantically related query behavior across the user's own media knowledge base
- Weekly notification opens an in-app digest, not an email flow
- Each digest card includes the exact CTA text `Try a quick quiz about this media to see what stuck with you.`
- That CTA clearly leads to an interactive quiz about the related media

### Error And Recovery

- `INVALID_URL`
- `UNSUPPORTED_URL`
- `SESSION_EXPIRED`
- `NOT_AUTHORIZED`
- `MEDIA_NOT_FOUND`
- `QUOTA_EXCEEDED`
- `INSUFFICIENT_MINUTES`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

- Each blocking state offers one clear next action
- Error copy stays user-safe and does not expose internals

### Exclusions

- No billing or checkout screens
- No Spotify linking or playlist sync
- No email-delivered digest or content UI
- No desktop-only navigation or wide data tables

### Visual Direction

- Feels more original than the current web app
- Does not default back to blue-purple startup gradients
- Does not look like a newspaper, editorial archive, or print-media product
- Feels modern, vibrant, digital-native, and contemporary at the shell level
- Uses a harmonious multi-accent palette with sophisticated gradient accents on shell and navigation
- Source-type visual signatures are visible (platform icons, color-coded chips, format indicators)
- Multi-source media convergence motif is present without being noisy
- Reading surfaces remain calmer and more focused than shell or navigation surfaces
- Signature motif is visible but does not reduce readability
