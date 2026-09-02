---
id: task-337
title: >-
  Align the paywall allowance copy with the App Store wording across the eleven
  locales
status: To Do
assignee: []
created_date: '2026-09-02 14:27'
labels:
  - phase-6
  - mobile
  - i18n
  - paywall
  - release
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The App Store subscription descriptions were rewritten on 2026-09-02 (`docs/store-listing/app-store-connect.md`, § "Localizations — all eleven locales") because the wording taken from the app was misleading. The app still carries the old wording, so the store sheet and the paywall card now disagree. This task closes that gap in the app.

## What is wrong with `plan.card.allowance`

The card's dominant line is `"{duration} of audio and video"` (`mobile/src/i18n/en.ts:229`, and the same key in the ten other locale files). Checked against `DEFAULT_PRICING_CONFIG.unit_conversion` in `media_summarizer/core/services/pricing_config_service.py`, it is wrong in both directions:

- **It hides what is free and unlimited.** `plan.legend.free`, verbatim: « Articles, web pages, TikToks and Instagram photo posts cost nothing at all: they are not transcribed. » A reader of the card concludes the app is an audio/video product, and that a 3 EUR plan buys them one hour of *use* a month.
- **It omits what else spends the budget.** A PDF, an Office document or a photo read for its text costs 1 min per 5 pages (`document_pages_per_minute`); a video whose captions can be bought costs 1 min flat (`captions_minutes`); a generation over a whole collection costs 1 min per 5 items (`collection_sources_per_minute`).

Both facts are already stated correctly in the app — but only inside `buildMinutesLegend`, which `buildPlanIncludes` places in the `minutes` section, i.e. **behind the `Show details` disclosure** (`mobile/app/paywall.tsx:515`). Nothing above the fold contradicts the card. The four highlight lines list articles and PDFs as *sources* (`plan.highlight.capture`) without saying they cost no minutes.

## The wording the store now uses

`Unlimited articles + {N} h of transcription.` — chosen by the owner because it carries both halves inside Apple's 45-character description limit. The eleven translations are already written and length-checked in `docs/store-listing/app-store-connect.md`; every term is lifted from the matching locale file (`transcription` / `Transkription` / `文字起こし` / `تحويل إلى نص`, and the hour unit from `duration.hours`), not translated afresh.

## Do not paste the store string into the card

The card line is not a store description and the constraint is different. `planCopy.ts:134` states it: « "a month" is carried by the price column ("per month"), not repeated here: this line has to survive at 20px next to a price on a 375pt screen. » `Unlimited articles + 12 h of transcription.` is roughly twice the length of `12 h of audio and video` and will wrap or shrink on a 375pt card, in German and Dutch worst of all.

So the deliverable is the *claim*, not the sentence: the card must stop implying audio/video is all the app does, and stop implying the allowance meters everything. Whether that lands as a shorter `plan.card.allowance` plus a new sibling line, as a change to one of the four highlights, or as pulling one legend sentence above the disclosure, is the implementer's call — argue it in the notes. Two rules from the file header hold either way: **no figure is authored** in `planCopy.ts` (every number arrives from `GET /api/pricing`), and a rule stated on the paywall may not contradict the Account tab, which reads the same module.

## Scope

- The eleven locale files in `mobile/src/i18n/` (`en`, `fr`, `es`, `de`, `it`, `pt`, `nl`, `ja`, `zh`, `ar`, `hi`) stay in step: a key added or removed in `en.ts` exists in all eleven. `mobile/src/i18n/catalogs.ts` and `pseudo.ts` are generated or derived — check how before editing either.
- Tier names are never translated (`mobile/src/i18n/fr.ts:8`).
- `docs/store-listing/app-store-connect.md` § "Why not \"N h of audio and video a month\"" ends on « Aligning the app is outstanding work » — replace that paragraph with what the app actually says once this lands, so the two stay comparable.

## Owner note — not an acceptance criterion

The card layout can only be judged on a device or a simulator, which no agent has. Leave a note in the implementation notes saying which locale is the tightest fit and what to look at, so the owner can check it on the next build. Do not write an AC about rendering, and do not touch `mobile/.maestro/` — the paywall flow asserts on `testID`s, not on copy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/src/i18n/en.ts no longer claims the monthly allowance covers 'audio and video' alone: the paywall card copy states both that articles and web pages cost no minutes and that transcription is what the allowance meters
- [ ] #2 The same change is applied to the ten other locale files (fr, es, de, it, ja, zh, pt, nl, ar, hi) with no key present in one file and missing from another, verifiable by comparing the key sets
- [ ] #3 No figure is hardcoded in mobile/src/lib/planCopy.ts or in any locale file: allowances, page-per-minute and item-per-minute conversions still arrive from GET /api/pricing through the existing interpolation placeholders
- [ ] #4 The sentences of buildMinutesLegend still match media_summarizer/core/services/pricing_config_service.py DEFAULT_PRICING_CONFIG unit_conversion: audio and video at real length, bought captions 1 min flat, documents and photos 1 min per 5 pages, collection-wide generation 1 min per 5 items, articles and web pages and TikToks and Instagram photo posts free
- [ ] #5 docs/store-listing/app-store-connect.md records what the app now says instead of stating that the alignment is outstanding
- [ ] #6 cd mobile && npx tsc --noEmit is clean, and npx eslint . reports no new error
<!-- AC:END -->
