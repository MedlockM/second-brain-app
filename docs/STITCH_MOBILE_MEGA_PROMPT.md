Design a complete App Mode mobile UI system for an app called "Media Summarizer".

You are designing for iOS and Android.

MISSION
Create a distinctive, production-grade mobile app concept for a share-first knowledge product.
This app helps users turn the media they send into a private, searchable knowledge base and a weekly in-app review habit.

CORE PRODUCT TRUTH
- A user shares a URL from another app into Media Summarizer.
- The app ingests and processes the media into a faithful transcript.
- The user can then generate optional AI artifacts on demand: summary, quiz, notes.
- The user can search across their own submitted-media knowledge base using:
  - exact keywords
  - semantically related words and phrases
- Once per week, the user receives an in-app weekly digest notification.
- Opening that notification reveals a weekly digest inside the app, not in email.
- The digest contains one concise but exhaustive summary card per media item sent that week.
- Under each digest summary card, include this exact CTA:
  "Try a quick quiz about this media to see what stuck with you."
- Tapping that CTA opens an interactive quiz about that media, generated from its transcript.

PRODUCT POSITIONING
- This is a transcript-first product, not a dashboard-first product.
- It should feel like a modern personal knowledge hub that naturally handles media from many different platforms and formats.
- The app must feel premium, vibrant, contemporary, original, and highly readable.
- Avoid playful, gamified, or generic SaaS styling.
- Avoid newspaper, editorial archive, or print-media aesthetics — the product is inherently digital and multi-format.

PRIMARY INFORMATION ARCHITECTURE
Use these 4 first-class navigation destinations:
- Inbox
- Search
- Weekly Digest
- Account

Additional structural rule:
- Media Detail is the central operational hub for processing status, transcript access, and artifact actions.
- Past submitted media can be browsed as an archive or library, but Search must remain a first-class surface, not just a small filter inside another screen.

SUPPORTED CONTENT SOURCES
- podcast episode URLs
- article URLs
- YouTube URLs
- short-form video URLs
- direct audio links

TECH CONTEXT FOR UX REALISM
- Mobile target stack: React Native + Expo
- Android entrypoint: Share Intent
- iOS entrypoint: Share Extension
- Existing canonical API surfaces to reflect in states:
  - POST /api/media/ingest-url
  - GET /api/media/{media_item_id}
  - POST /api/media/{media_item_id}/artifacts
  - GET /api/media/{media_item_id}/artifacts
  - GET /api/artifacts/{artifact_id}
- Search backend and weekly digest backend are not fully frozen yet, so do not expose technical backend jargon or speculative API details for those surfaces.

CANONICAL STATUS MODELS TO VISUALIZE
MediaItem.status:
- ingested
- resolving
- processing
- ready_for_artifacts
- failed
- cancelled

Transcript.status:
- pending
- extracting
- transcribing
- ready
- failed

Artifact.status:
- queued
- generating
- ready
- failed

Processing lifecycle stages:
- pending
- classifying
- resolving
- downloading
- extracting
- transcribing
- ready_for_artifacts
- completed
- failed
- cancelled

CANONICAL ERROR STATES TO SUPPORT
- INVALID_URL
- UNSUPPORTED_URL
- SESSION_EXPIRED
- NOT_AUTHORIZED
- MEDIA_NOT_FOUND
- QUOTA_EXCEEDED
- INSUFFICIENT_MINUTES
- RATE_LIMITED
- INTERNAL_ERROR

DESIGN DIRECTION
- bold, modern, and content-forward
- premium, vibrant, contemporary, focused, trustworthy
- colorful in a refined, digital-native way
- highly legible
- low visual noise on reading surfaces, more expressive on navigation and shell
- original and memorable
- not startup-gradient SaaS
- not playful or gamified
- not over-decorated
- not newspaper, not editorial archive, not print-media aesthetic

CREATIVE DIRECTION
Create a concept that feels like a modern multi-source media hub — a digital knowledge stream, not a paper archive.
The app handles content from podcasts, YouTube, articles, TikTok, Instagram reels, LinkedIn posts, and X threads.
The design must reflect this multi-format, multi-platform reality with a unified but source-aware visual language.

Use:
- clean, neutral base surfaces with contemporary depth (subtle layering, soft elevation, not paper textures)
- bold, modern sans-serif or geometric typography for headings
- highly legible body typography for reading and controls
- a vibrant, harmonious palette with 3 to 5 accent hues that feel digital and alive, such as electric teal, warm coral, bright amber, deep indigo, or vivid green
- source-type visual signatures: subtle iconography, color-coded chips, or format indicators that let users instantly recognize whether content came from a podcast, video, article, or social post
- a signature motif based on media convergence: for example, a stream/flow pattern, layered content cards with source badges, or a visual rhythm that suggests different media types merging into one knowledge surface
- gradient accents used sparingly and with sophistication on shell, navigation, and key action surfaces
- micro-animations and transitions that feel fluid and app-native
- calm, distraction-free reading surfaces that contrast with the more expressive shell and navigation

Avoid:
- newspaper or print-media aesthetics (no paper textures, no ink metaphors, no annotation rails, no index tabs, no archival dividers)
- purple SaaS gradients
- repetitive generic card grids everywhere
- heavy glassmorphism
- noisy dashboards
- visual gimmicks that hurt reading comfort
- bright shimmer directly behind dense reading text
- design that visually favors one source type over others

READING EXPERIENCE
Transcript, digest, and artifact reading surfaces should feel like a modern digital reader — clean and focused, not paper-like.
Include:
- immersive reading layout
- reduced chrome
- strong typography hierarchy
- smooth stable scrolling
- reading controls
- persistent reading position
- distraction-free mode feel
- theme presets such as Light, Warm, and Night

SEARCH EXPERIENCE
Search is a major component of the app.
Design it as a private knowledge retrieval experience across the user’s submitted media.
It must support:
- lexical keyword search
- semantically related search intent
- useful empty states
- no-result states
- refine-query states
- result explanations that feel human-readable, such as:
  - matching phrase
  - related concept
  - transcript snippet
  - summary match
Do not expose technical search jargon such as embeddings, vector ranking, hybrid retrieval, or index internals.

WEEKLY DIGEST EXPERIENCE
Weekly Digest is a major component of the app.
It is an in-app newsletter-like review surface, not an email screen.
It must include:
- a once-per-week notification entry
- a digest overview
- a list of media items submitted during the week
- one digest card per media item
- a concise but exhaustive summary on each card
- the exact CTA under each card:
  "Try a quick quiz about this media to see what stuck with you."
- interactive quiz opening flow from that CTA
- good behavior if the quiz is not ready yet:
  - queued
  - generating
  - ready
  - failed

NON-NEGOTIABLE CONSTRAINTS
- mobile only
- App Mode framing
- English UI copy only
- one-handed usability for primary actions
- touch targets >= 44px
- avoid horizontal overflow on 320–430px widths
- iOS and Android behavior both considered
- no billing or checkout screens
- no Spotify linking or playlist sync screens
- no email newsletter client UI
- no content delivered by email
- no desktop/web layouts
- no fake admin dashboard patterns

REQUIRED SCREEN INVENTORY

S01 - Auth Entry
- sign in
- create account
- session restore state
- session expired re-auth state
- inline recovery-friendly errors

S02 - Share Intake Confirmation
- appears right after share from another app
- shows received URL identity or host
- states:
  - accepted
  - invalid_url
  - unsupported_url
  - queued_offline

S03 - Inbox Empty
- explain how share-first ingestion works
- make it specific to the product
- include helpful next action

S04 - Inbox List
- chronological list of submitted media
- each row shows:
  - source platform
  - title or URL snippet
  - media status
  - transcript status
  - last updated

S05 - Offline Queue
- queued
- syncing
- synced
- failed
- bounded retry
- duplicate-safe messaging

S06 - Search Home
- large search entry point
- recent searches
- suggested concepts
- archive/library affordance
- feels like a private knowledge hub, not a generic search page

S07 - Search Results
- supports both exact keywords and semantically related query behavior
- results can include:
  - transcript snippets
  - related concepts
  - matched summaries
  - grouped media items
- filters or scopes can include:
  - media type
  - source platform
  - date range
  - artifact availability

S08 - Search Empty / No Results / Refine Query
- helpful guidance
- no dead ends
- visually clear distinctions between:
  - no query yet
  - no results
  - broad results needing refinement

S09 - Weekly Notification Entry
- once-per-week notification or notification-center item
- clearly deep-links into Weekly Digest
- feels product-native, not like an email preview

S10 - Weekly Digest Overview
- premium weekly review surface with modern editorial feel
- clear date range or weekly framing
- digest is revisitable inside the app

S11 - Weekly Digest Item List
- one card per media item submitted during the week
- each card contains a concise but exhaustive summary
- under each card include this exact CTA:
  "Try a quick quiz about this media to see what stuck with you."

S12 - Digest Quiz Entry State
- show what happens when user taps the digest CTA
- support:
  - quiz ready
  - quiz queued
  - quiz generating
  - quiz failed

S13 - Media Detail In Progress
- operational hub
- stage label
- progress indicator
- timestamp updates
- pending transcript section
- retry/cancel/refresh actions where appropriate

S14 - Media Detail Ready For Artifacts
- transcript summary card
- source
- language
- duration
- action area:
  - Generate Summary
  - Generate Quiz
  - Generate Notes
- per-artifact independent states

S15 - Media Detail Failed / Cancelled
- safe error guidance
- recovery actions
- support MEDIA_NOT_FOUND, NOT_AUTHORIZED, INTERNAL_ERROR

S16 - Transcript Full View
- reading-optimized transcript
- search inside transcript
- segment jump behavior
- excerpt copy/share action

S17 - Reader Mode
- immersive
- reduced chrome
- reading controls
- Light / Warm / Night
- stable reading progress

S18 - Artifact Cards
- summary
- quiz
- notes
- states:
  - idle
  - queued
  - generating
  - ready
  - failed

S19 - Summary Detail
- main topics
- key points
- notable quotes
- conclusion

S20 - Interactive Quiz Detail
- question cards
- answer reveal
- progress through quiz
- strong mobile-native interaction model
- should work both from Media Detail and from Weekly Digest CTA

S21 - Notes Detail
- objectives
- concepts
- key points
- action items
- glossary

S22 - Account
- session restore
- sign out
- reading preferences
- weekly digest notification preferences
- help for sharing into the app
- safe blocking states for exhausted minutes/quota without billing UI

STATE MAPPING REQUIREMENT
Provide a clear visual mapping between:
- API status values
- user-facing labels
- available CTAs
- retry behaviors
- terminal states

At minimum map:
Media:
- ingested -> Received
- resolving -> Resolving source
- processing -> Processing
- ready_for_artifacts -> Ready
- failed -> Failed
- cancelled -> Cancelled

Transcript:
- pending -> Waiting
- extracting -> Extracting content
- transcribing -> Transcribing
- ready -> Ready
- failed -> Failed

Artifact:
- queued -> Queued
- generating -> Generating
- ready -> Ready
- failed -> Failed

COMPONENT SYSTEM REQUIRED
Create reusable components for:
- app shell
- bottom navigation
- top contextual header
- status chip
- queue item row
- media list row
- search result row
- digest summary card
- digest CTA row
- progress module
- transcript preview card
- artifact action card
- inline error block
- empty state block
- retry button group
- notification entry card

OUTPUT EXPECTED
- complete mobile screen set
- iOS and Android-aware patterns
- reusable component library
- loading, offline, retry, success, and error variants
- strong visual concept rationale
- strong reading experience rationale
- clear search UX rationale
- clear weekly digest rationale

Make the app feel like a modern, vibrant knowledge companion for people who consume media across many platforms — podcasts, YouTube, articles, social posts — and want to capture, revisit, search, and review it every week.