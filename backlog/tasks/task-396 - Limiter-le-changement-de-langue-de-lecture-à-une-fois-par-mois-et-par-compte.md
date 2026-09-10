---
id: task-396
title: Limiter le changement de langue de lecture à une fois par mois et par compte
status: Done
assignee: []
created_date: '2026-09-10 12:37'
updated_date: '2026-09-10 15:10'
labels:
  - backend
  - mobile
  - cost
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Changer de langue de lecture engage un coût fournisseur réel : traduction du texte complet de chaque média ouvert, puis traduction de ses artefacts. Ce coût est maîtrisé par média (la traduction est persistée et ne se relance pas), mais rien ne limite la **fréquence** à laquelle un compte peut changer de langue, et chaque changement rouvre la porte à une nouvelle vague de traductions sur toute la bibliothèque au fil des ouvertures.

## Décision du propriétaire

**Un changement de langue de lecture par mois et par compte.** Garde-fou de coût, pas une fonctionnalité produit.

## Périmètre

Le refus doit être lisible côté application : l'utilisateur comprend qu'il a déjà changé de langue récemment et à partir de quand il pourra le refaire. Le message passe par les 11 catalogues i18n existants, comme toute autre chaîne de l'application.

À la charge de l'implémenteur de vérifier si la langue de lecture est modifiable ailleurs que sur l'écran de réglages (par exemple à l'inscription ou lors d'un choix initial) et de ne pas appliquer la limite là où elle empêcherait un premier réglage.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après déploiement : changer de langue, puis tenter un second changement immédiatement et lire le refus dans l'application.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un second changement de langue de lecture dans le mois qui suit le précédent est refusé côté backend, indépendamment du client qui le demande.
- [x] #2 Le refus est présenté dans l'application avec la date à partir de laquelle un nouveau changement est possible, via les 11 catalogues i18n existants.
- [x] #3 Le premier réglage de la langue de lecture d'un compte n'est pas soumis à la limite.
- [x] #4 ruff et mypy passent sans erreur sur les modules touchés.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Delivered

**Where the limit lives.** `PATCH /api/auth/me` is the *only* write path of
`reading_language` in the whole codebase (`grep` over `media_summarizer/` and
`scripts/`: every other occurrence reads it), so the guard-rail sits there and
holds for any client, including one that never opens the app's settings screen.
`User.reading_language_changed_at` is the new stored column, and
`User.reading_language_change_available_at()` the one place the rule is applied:
it returns the instant the guard lifts, or `None` when a change is possible now.

**One rolling month, not the calendar one.** `READING_LANGUAGE_CHANGE_INTERVAL =
timedelta(days=30)` in `core/models/user.py`. A calendar rule would let a change
on 31 January and another on 1 February through — a day apart, two full waves of
translation — which is exactly the burst the guard exists to prevent.

**The first setting is not a change (AC #3).** The clock starts only when one
language *replaces* another. Picking a language at onboarding (`mobile/app/
onboarding/language.tsx`, the other caller of `updateReadingLanguage`) writes the
preference with no timestamp, so the account is not locked out of the very setting
it just discovered — a reader who mis-picks during onboarding can still correct it,
and *that* correction starts the month. Re-sending the language already stored is
not a change either: it neither spends the allowance nor gets refused, which
matters because the settings screen's Save does exactly that.

**The refusal follows the task-359 convention.** 429 with
`{"detail": {"error_code": "reading_language_change_too_soon", "available_at":
"<ISO 8601>"}}` — a stable code and a date, never a sentence the server could not
have worded in the reader's interface language. `mobile/src/lib/httpError.ts`
already lifts a typed `detail` into `error.code` + `error.details`, so no transport
change was needed. `mobile/src/lib/readingLanguageRefusal.ts` turns the pair into
copy, the way `artifactRefusal.ts` and `quotaError.ts` do for their own refusals,
and `getFriendlyErrorMessage` maps the code to the dateless sentence as the
fallback for any caller that does not go through it (that table maps a code to a
key and cannot interpolate a date).

**Two catalogue keys, not three.** `readingLanguage.changeLimit` ("once a month,
next change on {date}") is true both *before* an attempt and *as* a refusal, so
the pre-emptive notice on the settings screen and the error after a save share it.
`readingLanguage.changeLimitNoDate` is the shorter true sentence for a refusal
that reaches the app without its date. Both landed in the `readingLanguage.*`
block of the 11 catalogues rather than the `error.*` block, to stay clear of
task-397's sweep over error copy.

**The screen says it before it refuses.** `AuthUser` now carries
`reading_language_change_available_at` (computed in `from_user`, the single
projection point, so all five session endpoints serve it). `UserPreferencesContext`
exposes it and refreshes it from the PATCH response, so the lock appears the
instant a change succeeds instead of waiting for the next sign-in.
`mobile/app/settings/reading-language.tsx` renders the date in a tonal notice
(`surfaceContainerLow`, same as the disclaimer above it — a fact about the
setting, not an alarm) and disables Save. The refusal path stays wired all the
same: the date comes from the profile the session was opened with, and a second
device may have spent the change since. No new colour, spacing or type value —
notice styling reuses the disclaimer's tokens.

## Deliberately not done

**No conditional write against the race.** Two PATCHes landing in the same
instant from two devices both read "available" and both stamp the clock, so one
extra change can slip through. Making that impossible means a DynamoDB
`ConditionExpression` on the user row, where `database_async.update_user` is a
whole-item `put_item`. The guard-rail bounds a monthly cost, and the worst case is
one extra change per genuine race; the plumbing is not worth it.

**No test, per the delivery rules.** The model round-trip and the two date
branches were exercised once in a throwaway interpreter call (locked → date,
31 days old → `None`, never set → no DynamoDB attribute written), not committed.

## Checks

- `ruff check` and `mypy` clean on `core/models/user.py`, `core/models/auth.py`,
  `api/endpoints/auth.py` (AC #4).
- `tsc --noEmit` clean over `mobile/`; `eslint app src` reports only the
  pre-existing `no-explicit-any` warning in `src/services/purchaseService.ts`.

## Owner follow-up

Deploy-gated, so out of reach from the worktree: after this merges and `main` is
pushed, change the reading language on the app, then attempt a second change and
read the refusal (Settings → Reading Language shows the date and greys Save; the
429 body carries `available_at`). Any account whose language was set before this
ships has no `reading_language_changed_at`, so its next change is free and starts
the month — which is the intended behaviour, not a gap.
<!-- SECTION:NOTES:END -->
