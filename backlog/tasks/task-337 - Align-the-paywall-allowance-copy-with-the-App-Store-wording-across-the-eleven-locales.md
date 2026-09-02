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
- [x] #1 mobile/src/i18n/en.ts no longer claims the monthly allowance covers 'audio and video' alone: the paywall card copy states both that articles and web pages cost no minutes and that transcription is what the allowance meters
- [x] #2 The same change is applied to the ten other locale files (fr, es, de, it, ja, zh, pt, nl, ar, hi) with no key present in one file and missing from another, verifiable by comparing the key sets
- [x] #3 No figure is hardcoded in mobile/src/lib/planCopy.ts or in any locale file: allowances, page-per-minute and item-per-minute conversions still arrive from GET /api/pricing through the existing interpolation placeholders
- [x] #4 The sentences of buildMinutesLegend still match media_summarizer/core/services/pricing_config_service.py DEFAULT_PRICING_CONFIG unit_conversion: audio and video at real length, bought captions 1 min flat, documents and photos 1 min per 5 pages, collection-wide generation 1 min per 5 items, articles and web pages and TikToks and Instagram photo posts free
- [x] #5 docs/store-listing/app-store-connect.md records what the app now says instead of stating that the alignment is outstanding
- [x] #6 cd mobile && npx tsc --noEmit is clean, and npx eslint . reports no new error
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

Two strings per locale, one new placement on the paywall, no new and no deleted key.

1. **`plan.card.allowance` → `"{duration} of transcription"`** (eleven locales). The
   half of the claim that *differs between the tiers*, in the word the screen already
   used two lines above it: `paywall.selectorLabel` is "Pick your monthly transcription
   time" and `paywall.subtitle` is "Every plan does all of it. Only the monthly
   transcription time changes." The card was the only place still saying "audio and
   video". It is also the store's own second half (`{N} h of transcription`).
2. **`plan.minutesRule` gained one clause**: « Minutes cover audio and video we
   transcribe. **Articles and web pages cost no minutes**, and reading your library is
   unlimited. » Rendered on the paywall directly under the card list (`testID
   paywall-minutes-rule`), and unchanged in its other home, the Account tab's hint
   under the usage gauge.
3. `minutesRule()` was **removed from `buildMinutesLegend`**, which now returns the
   conversion table only. It used to be the legend's first sentence, i.e. behind
   `See exactly what is included`; leaving it there as well would have printed the
   same sentence twice on one screen.

### Why this shape rather than a longer card line or a sibling line per card

- **The store string cannot go on the card**, as the task says — but the *reason* also
  rules out any per-card variant of it. "Unlimited articles" is identical on all three
  cards: printing it three times spends ~60pt of the most expensive vertical space on
  the screen to say one thing, and the module's own rule is that what does not vary by
  tier is stated once (that is why `buildPlanIncludes` sits under the cards at all).
  So the card keeps only what differs — the duration — and the shared half is one line
  under the list.
- **`plan.minutesRule` was already the right sentence**, three-quarters written and
  translated eleven times; it only lacked the free half. Reusing it buys two things a
  new key could not: the paywall and the Account tab cannot contradict each other about
  the meter (they read the same key, which is the constraint named in the task), and the
  free enumeration is not duplicated — the exhaustive list, TikToks and Instagram photo
  posts included, stays in `plan.legend.free` behind the disclosure. Short claim above,
  exhaustive list behind the disclosure is the pattern the screen already uses for the
  four highlights.
- **"Cover", never "only cover".** A PDF, an Office document or a photo costs 1 min per
  5 pages and a collection-wide generation 1 min per 5 items, so an exclusive form
  ("minutes only pay for transcription") would have been a second false rule. The line
  says what minutes cover and what costs nothing, and leaves the conversions to the
  legend — which is why `Articles and web pages cost no minutes` is phrased as a fact
  about those two source types and not as "everything else is free".
- **Below the cards, not above them.** The screen's stated priority is that a price is
  on screen without scrolling; the header already carries "Only the monthly
  transcription time changes", so the rule costs 0pt before the first price where above
  the cards it would have cost one to three lines in the wider locales.
- **`Colors.textMain`, not `textSubtle`**, at `Typography.small`: the line qualifies the
  dominant line of all three cards, and in the grey used for the legal block it reads
  as a footnote — which is how the app got here.

No figure was authored: the only interpolation on the card is `{duration}`, fed by
`formatMinutes(tier.minutes_per_month)` from `GET /api/pricing`, and the new clause
contains no number at all. Key sets were compared file by file after the change: the
ten Latin/CJK catalogues are identical to `en`, and `ar` differs only by its extra
plural categories, exactly as before.

### For the owner — the card and the line on a device

Nothing here can be judged from a worktree; two things to look at on the next build.

- **The card line got shorter in all eleven locales**, so it is the safer half:
  `12 h of transcription` (en) against `12 h of audio and video`, `12 Std.
  Transkription` against `12 Std. Audio und Video`, `12 u transcriptie` against
  `12 u audio en video`. The widest rendered card line is now Arabic
  (`12 ساعة من التحويل إلى نص`), which is the same width as the string it replaces.
- **The tightest fit is the new line, and the tightest locale is French.** At 160
  characters it is the longest of the eleven (en 123, es 150, de 145, hi 137, ja 122
  display columns, zh 78), i.e. about four lines of 13px text at 327pt of content
  width on a 375pt screen, sitting between the last plan card and the "Included in
  every plan" block. Check that it still reads as a note on the plans and not as a
  paragraph pushing the block off screen.
- **The same sentence in the Account tab during a free trial is the longest text run
  of the two screens**: `account.plan.minutesRuleTrial` appends "Les minutes d'essai
  ne se rechargent pas." to it, 202 characters in French, under the usage bar in
  `SubscriptionStatusCard`. Neither `Text` sets `numberOfLines`, so the risk is height,
  never truncation.
- Unrelated, spotted while editing: the paywall's tagline (`mobile/app/paywall.tsx`,
  under `styles.tagline`) is a hard-coded English literal that never goes through the
  catalogue, so it stays English in the other ten locales. Out of this task's scope,
  left alone.

### Not done

No automated test was added (project rule). AC #6 was verified by running `tsc
--noEmit` (clean) and `eslint` (0 errors; the 2 pre-existing warnings are in
`app/(tabs)/digest.tsx` and `src/services/purchaseService.ts`, untouched here) with
the repository checkout's `mobile/node_modules` symlinked into the worktree for the
run and removed afterwards — the worktree has no `node_modules` of its own.
`mobile/.maestro/` was not touched and contains no assertion on this copy.
<!-- SECTION:NOTES:END -->
