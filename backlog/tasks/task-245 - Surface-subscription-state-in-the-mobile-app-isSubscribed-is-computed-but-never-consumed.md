---
id: task-245
title: >-
  Surface subscription state in the mobile app (isSubscribed is computed but
  never consumed)
status: To Do
assignee: []
created_date: '2026-08-11 16:24'
updated_date: '2026-08-12 17:30'
labels:
  - mobile
  - billing
  - feature
  - phase-6
dependencies:
  - task-244
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

`mobile/src/contexts/PurchasesContext.tsx` calcule `isSubscribed` et expose `entitlementStatus` (tier, minutes restantes, fin de période) depuis `GET /api/v1/entitlements/status`. Audit du code (2026-08-11) : **aucun écran ne consomme ces valeurs**. Le seul appelant de `usePurchases()` est `paywall.tsx`, et seulement pour `refreshEntitlements`.

L'utilisateur n'a donc aujourd'hui **aucun moyen de voir** son tier, ses minutes restantes ou la date de fin de période, alors que le backend fournit tout.

## À clarifier avec l'owner avant implémentation

Le vrai « gating » (restreindre des fonctionnalités selon le tier) est déjà assuré **côté backend** par `quota_enforcer.py` (task-110, Done), qui est la seule place où il est fiable — un gating purement client serait contournable. La question ouverte est donc :

- Faut-il seulement **afficher** l'état (tier + minutes restantes dans Account, éventuellement un indicateur d'approche de limite) ?
- Ou aussi **désactiver côté client** certaines actions par anticipation (griser l'import audio quand le solde est épuisé), pour éviter un aller-retour réseau soldé par une erreur ?

Trancher ce point avant de coder : la première option est un affichage, la seconde duplique une règle métier côté client et doit rester cosmétique.

## Scope indicatif (à confirmer selon la réponse ci-dessus)

1. Afficher dans l'onglet Account le tier courant, les minutes restantes et la fin de période à partir de `entitlementStatus`.
2. Gérer les états `null` / chargement / erreur réseau sans casser l'écran (l'endpoint peut échouer : `PurchasesContext.tsx` logge déjà l'erreur et laisse `entitlementStatus` à `null`).
3. Optionnel selon décision : indication anticipée quand le solde est proche de zéro, complémentaire au refus backend traité par task-244.

## Hors scope

- Les points d'entrée du paywall (task-244).
- Toute règle d'enforcement côté client qui remplacerait `quota_enforcer.py`.

## Références

- `mobile/src/contexts/PurchasesContext.tsx` (`isSubscribed`, `entitlementStatus`, `refreshEntitlements`)
- `media_summarizer/api/endpoints/entitlements.py`
- `media_summarizer/core/services/quota_enforcer.py`, task-110 (enforcement backend, Done)
- task-244 (points d'entrée paywall + traitement des refus de quota)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The owner has confirmed whether the scope is display-only or also includes client-side pre-emptive disabling, and the task description records the answer
- [x] #2 The Account tab shows the current tier, remaining minutes, and period end from entitlementStatus
- [x] #3 A null or failed entitlements response leaves the Account tab usable, with no crash and no misleading 'free tier' claim
- [x] #4 usePurchases is consumed by at least one screen other than paywall.tsx
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Scope question still open — implemented display-only

The question recorded in the description (display-only vs. also disabling actions client-side before the network round-trip) **was not answered by the owner**, and nothing here should be read as an answer. This run implemented **option 1 only, display**, which is the conservative reading: option 2 duplicates a business rule that only `quota_enforcer.py` can enforce reliably, and the description itself flags it as having to stay cosmetic. AC #1 is therefore left unchecked.

If the owner later picks the pre-emptive-disabling variant, what remains to do is scoped and small:

- `entitlementStatus.minutes_remaining` is already in the Account tab through `usePurchases()`; the same hook is available anywhere under `PurchasesProvider`, so the audio-import affordances (`share-confirmation.tsx`, the audio branch of `sharedContentService`) can read it without new plumbing.
- The decision to make would be *which* affordance is greyed out and on what predicate (balance strictly zero? a threshold? `is_active === false`?), plus what happens when the entitlement is `null` — greying out on an unknown state would lock out a paying user on a transient network error, so an unknown state must stay permissive.
- The backend refusal path is already handled end-to-end by task-244 (`X-Quota-Error-Code` → quota-aware error state → paywall), so pre-emptive disabling would be a pure UX shortcut on top of a working refusal, never a replacement for it.
- Item 3 of the indicative scope (early "balance near zero" indicator) belongs to that same decision and was deliberately **not** implemented: no warning colour, no threshold, no near-limit copy. The card shows the number the backend returns and nothing more.

## What was implemented (2026-08-12)

### `mobile/src/lib/subscriptionDisplay.ts` (new)

Pure display helpers over `EntitlementStatus`, no gating logic:

- `getTierLabel()` — `S`/`M`/`L` → `Reader`/`Mix`/`Audio-Heavy`, mirroring the `display_name` values of `OFFERINGS_CONFIG` in `media_summarizer/api/endpoints/entitlements.py`. Returns `null` for an unknown tier instead of crashing on the index, so a tier added backend-side degrades to a generic label.
- `formatPeriodEnd()` — `"Sep 12"`, with the year appended only when it is not the current one. Returns `null` for a missing **or unparseable** date, so the screen renders an explicit unknown rather than `"Invalid Date"`.
- `getPeriodEndLabel()` — `RENEWS` / `ENDS` / `PERIOD ENDS` from `auto_renew_status`. `auto_renew_status` is nullable and a null renewal intent stays neutral: the app does not promise a renewal it cannot confirm.
- `getStatusNote()` — `grace_period` → "Payment issue", `canceled` → "Cancelled". These are the only two statuses the endpoint reports as still active besides `active`.
- `includesAudioMinutes()` — Reader carries no audio allowance at all, so its `minutes_remaining: 0` describes the plan, not an exhausted balance, and gets a one-line clarification instead of reading as "you ran out".

`TIER_LABELS` moved here out of `account.tsx`, where task-244 had inlined it.

### `mobile/src/components/SubscriptionStatusCard.tsx` (new)

A read-only "YOUR PLAN" card with four distinct states — the distinction between the last two is the whole point of AC #3:

1. **Loading** — spinner, only on first load. Guarded on `entitlement === null && isLoading`, so the focus refresh below never flickers the figures back to a placeholder.
2. **Unavailable** (`entitlement === null`, not loading) — `cloud-offline-outline`, "Plan status unavailable", "We could not load your subscription details. Your plan itself is unaffected.", plus a Retry button wired to `refreshEntitlements`. It is deliberately **not** rendered as "no plan" or "free tier": a failed request means the plan is *unknown*, and claiming otherwise is exactly what AC #3 forbids. `PurchasesContext` swallows the error and leaves `entitlementStatus` at `null`, so this branch is the only signal the user gets that the fetch failed.
3. **No active plan** (`is_active === false`) — that one is authoritative, the backend said it, so it is stated plainly.
4. **Active** — tier name, an attention chip for `grace_period`/`canceled`, and two metric tiles on `surfaceContainerLow`: audio minutes left this month, and the renewal/expiry date.

Amber Clarity tokens only (`Colors`, `Typography`, `Spacing`, `BorderRadius`, `Shadows.soft`, `TouchTarget.minimum` on Retry), no 1px sectioning lines — the tiles are tonal shifts. `Shadows.soft` matches the two sibling cards already on this screen. Metric tiles expose an `accessibilityLabel` written for a screen reader ("240 audio minutes left this month") rather than the uppercase on-screen label.

### `mobile/app/(tabs)/account.tsx`

- Mounts the card between the profile block and the paywall CTA, fed by `entitlementStatus`, `isLoading` and `refreshEntitlements` from `usePurchases()`.
- `useFocusEffect` refreshes entitlements when the tab gains focus, like `inbox.tsx` and `search.tsx` do. The remaining balance moves on every audio import, and the provider otherwise only fetches it at sign-in, so without this the figure shown is the one from the start of the session. It also picks up a purchase made on the paywall.
- CTA copy adjusted, for two reasons. The subtitle no longer repeats the tier (the card states it right above), and when the state is **unknown** — `entitlementStatus === null` and RevenueCat has nothing either — the CTA now reads "View plans" / "See what each subscription includes" instead of "Upgrade". "Upgrade" asserts we know the user is not subscribed, which on a failed fetch we do not. The subscribed and confirmed-unsubscribed wordings from task-244 are unchanged, and the `account-upgrade-button` test id is untouched, so `07_paywall.yaml` and `sign_out.yaml` (both address it by id) are unaffected.

## Verification

- `cd mobile && npm run typecheck` — clean.
- `cd mobile && npm run lint` — 0 errors, 10 warnings, all pre-existing and none in the three files touched (`npx eslint` on those three files alone: silent).
- No automated tests added, per the project rule for this agent. No Maestro assertion was added on the new card for the same reason; the existing flows still traverse the Account tab and both `scrollUntilVisible` targets (`account-upgrade-button`, `account-sign-out-button`) keep working with one more card above the menu, since the body has been a `ScrollView` since task-244.
- **Not verified on a device or simulator** (none available in the agent sandbox): the four card states were reasoned through statically, not rendered. Worth a look on first run: the two metric tiles side by side on a narrow screen (`AUDIO MIN LEFT` is the longest label, and wraps to two lines if it has to), and the unavailable state, which is easiest to trigger by killing the API host.
<!-- SECTION:NOTES:END -->
