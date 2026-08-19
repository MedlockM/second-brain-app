---
id: task-301
title: 'Tell the user they are in a free trial: Account tab date and Inbox countdown'
status: Done
assignee: []
created_date: '2026-08-19 20:42'
updated_date: '2026-08-19 23:22'
labels:
  - mobile
  - ui
  - copy
  - phase-6
dependencies:
  - task-300
  - task-299
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app never tells a user they are in a free trial. `is_free_trial` is returned by `GET /api/v1/entitlements/status`, declared in `EntitlementStatus` (`mobile/src/contexts/PurchasesContext.tsx:37`) and read by nothing — a repo-wide grep finds no other use in `mobile/`. Consequences an owner hit on a fresh account created on 2026-08-19:

- The Account tab renders a trial exactly like a paid plan. `subscription_tier` is null during a trial, so `getTierLabel` returns null and `SubscriptionStatusCard.tsx` falls back to the heading **"Active plan"**. Nothing on the screen contains the word trial.
- The date next to it is labelled **"PERIOD ENDS"** — `getResetDateLabel` (`mobile/src/lib/subscriptionDisplay.ts`) returns that when `auto_renew_status` is null, which is always the case during a trial. It is the most ambiguous of its three labels and reads as "your access stops here", which is what the owner concluded. Combined with `task-300`, the date it points at *is* now the trial's end — so the fix is to say so, not to hide it.
- `MinutesWarningBanner.tsx` says "You've used X% of this month's minutes. They reset on <date>." During a trial, after `task-300`, those minutes do not reset at all: the trial ends. The sentence is false on that surface too.

## What to build

**Account tab.** During a trial the card identifies itself as a trial and labels the date as the trial's end rather than a period boundary or a refill. The tier it grants (`mix` → the Mix allowance) is worth stating since it is what the gauge above is measuring, but the heading must not read as a purchased plan.

**Inbox.** A small centred notice at the top of the Inbox, shown only while the trial is running, reading the remaining days — the owner's wording: `Free Trial - X days left`. Placement is the existing `ListHeader` in `mobile/app/(tabs)/inbox.tsx`, which already hosts `MinutesWarningBanner`; both must be able to appear without fighting for the same slot.

The countdown derives from `resets_at`, which after `task-300` is the trial's closing instant. The app does not know `created_at` and must not try to reconstruct the trial length: one date in, one countdown out. Decide and state in the code what the last day says — a notice reading "0 days left" while the user still has access is a bug, and so is "1 day left" for eleven more hours if the copy implies a full day.

## Constraints

- **The client decides nothing about entitlement.** Whether a trial is running is `is_free_trial` from the backend, never a date comparison the app makes to guess it; the existing header comment in `subscriptionDisplay.ts` is the rule. The countdown is presentation of a backend date, which is allowed; eligibility is not.
- Render nothing rather than guess: no notice while `entitlementStatus` is null, still loading, or errored, and none once `is_free_trial` is false (subscribed, or trial over).
- Timezone: `formatResetDate` formats in device-local time with no explicit zone, which is why a `2026-09-01T00:00Z` boundary displayed as "Aug 31" started this. A date the backend sends as an instant and the countdown derived from it must not disagree by a day on the same screen.
- `task-299` rewrites the paywall copy, including how the trial is worded there, and also touches `SubscriptionStatusCard.tsx` (its AC #9). This task runs after it and matches its vocabulary — the trial must not be called one thing on the paywall and another on Account.
- Give the Inbox notice a `testID` in the style of the neighbouring ones (`minutes-warning-banner`, `account-plan-*`) so a Maestro flow can assert it later.

## Owner notes (not acceptance criteria)

- The visual result — a *small centred* card, not a full-width banner — can only be judged on a simulator, which the implementer cannot run. Put the final copy and the component's style block in the implementation notes so it can be read without building.
- Worth checking on the owner's dev account after deploy: created 2026-08-19, so the Account tab should read 18 September and the Inbox should count down to it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Account tab card identifies a running trial as a trial instead of falling back to the 'Active plan' heading, and is_free_trial from the entitlement payload is what drives it — the field is no longer declared-but-unused in mobile/
- [x] #2 The date shown on the Account tab during a trial is labelled as the end of the free trial, and getResetDateLabel no longer returns 'PERIOD ENDS' for a trial
- [x] #3 A centred notice at the top of the Inbox shows 'Free Trial - X days left' while the trial runs, with X derived from the entitlement payload's resets_at and never from a locally reconstructed trial length
- [x] #4 The remaining-days figure is never negative or zero while access is still granted, the last day of the trial reads as a true statement, and the rounding rule is stated in the component
- [x] #5 The Inbox notice renders nothing when the entitlement status is missing, loading or errored, and disappears as soon as is_free_trial is false — a subscriber and a user past their trial both see no notice
- [x] #6 The Inbox notice and MinutesWarningBanner can both be present without overlapping or displacing each other, and the existing greeting, digest button and section header of ListHeader are unchanged
- [x] #7 MinutesWarningBanner no longer tells a trial user that this month's minutes 'reset on' a date, since a trial allowance does not refill
- [x] #8 No entitlement decision is taken client-side: the app still reads tier, allowance and trial state from the backend payload and computes only display strings from them
- [x] #9 The Inbox notice carries a testID consistent with the existing ones so it is assertable from Maestro
- [x] #10 cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Une date, deux surfaces, une seule conversion

Le compte à rebours et la date affichée viennent du même `resets_at` et passent par la
même projection : `getDaysUntil(iso, now)` (`mobile/src/lib/subscriptionDisplay.ts`) compte
des **frontières de minuit locales**, pas des tranches de 24 h. `formatResetDate` formate
déjà en heure locale ; compter en millisecondes écoulées puis arrondir aurait pu donner
« 2 days left » sous une date affichée à J+1 aux abords de minuit — exactement le genre de
désaccord d'un jour qui a lancé la tâche (`2026-09-01T00:00Z` rendu « Aug 31 »). Deux
projections identiques ne peuvent pas diverger.

`Math.round` sur la différence de minuits, pas `floor` : un passage à l'heure d'été rend
une journée de 23 ou 25 h, et l'arrondi absorbe le décalage. Résultat clampé à 0 pour ne
jamais rendre de négatif si le payload est en retard sur l'horloge.

### La règle d'arrondi, et le seul jour qu'elle ne peut pas énoncer

`getDaysUntil` rend 0 quand la fermeture tombe aujourd'hui, 1 quand elle tombe demain.
Le wording de l'owner, `Free Trial - X days left`, est donc rendu tel quel à partir de 2, et
le dernier jour dit **`Free Trial - last day`** : « 0 days left » serait faux tant que
l'accès est accordé, et « 1 day left » le serait tout autant pour les onze dernières heures.
`last day` est vrai pendant toute cette journée-là, quelle que soit l'heure de fermeture.
La règle est écrite dans le composant, à côté du code qui l'applique.

Troisième cas : `resets_at` est nullable. Le backend dit que le trial tourne, la notice
reste donc affichée — mais réduite à `Free Trial`, sans compteur qu'il faudrait inventer.

### Ce que le client décide : rien

`is_free_trial` du backend est la seule chose qui allume la notice ; aucune comparaison de
dates ne sert à deviner l'état. Une seule garde suffit : `!entitlementStatus?.is_free_trial`
couvre payload absent, en cours de chargement, en erreur, abonné et trial terminé — les
cinq cas rendent `null`. Le compte à rebours n'est que la mise en forme d'une date que le
serveur envoie, ce que la contrainte autorise explicitement.

### Onglet Account

`getResetDateLabel` teste `is_free_trial` en premier et rend `FREE TRIAL ENDS` : pendant un
trial `auto_renew_status` est toujours `null`, donc l'ancienne cascade tombait
systématiquement sur `PERIOD ENDS`, le plus ambigu de ses trois libellés. Le titre de la
carte devient `Free trial` au lieu de retomber sur `Active plan` (le `subscription_tier`
étant `null`, `getTierLabel` ne pouvait rien rendre).

Le tier accordé par le trial n'est pas dans le payload d'entitlement — il vit dans la config
pricing. `account.tsx` va donc le chercher sur `GET /api/pricing`, **uniquement** quand
`is_free_trial` est vrai (un abonné a déjà son tier dans le payload), et en silence si
l'appel échoue : la carte nomme le trial avec ou sans lui. Il est rendu dans la puce déjà
présente à droite du titre — libre pendant un trial, puisque `getStatusNote("free_trial")`
rend `null`. Le nom n'est jamais promu en titre : « Mix » seul se lirait comme un plan
acheté. Le nom est filtré par `isFreeTrial` au moment d'être passé en prop plutôt que remis
à zéro dans l'effet (le lint interdit un `setState` synchrone dans un effet), donc un trial
qui se termine ne peut pas laisser sa puce derrière lui.

### `MinutesWarningBanner`

La phrase « They reset on <date> » était fausse pour un trial depuis task-300 : l'allocation
ne se recharge pas, elle se termine. La bannière a maintenant deux formulations, choisies
sur `is_free_trial` — « of your free trial minutes … They do not refill — your trial ends on
<date>. » contre la formulation mensuelle inchangée pour les abonnés.

### Copie finale et style, pour lecture sans build

Notice Inbox (`mobile/src/components/FreeTrialNotice.tsx`, testID `free-trial-notice`) :

- `Free Trial - 29 days left` / `Free Trial - 1 day left` / `Free Trial - last day` / `Free Trial`
- une pastille qui se dimensionne à son texte, centrée par une ligne parente
  (`row: { alignItems: "center", marginTop: Spacing.md, paddingHorizontal: Spacing.md }`,
  `pill: { paddingVertical: Spacing.xs, paddingHorizontal: Spacing.md,
  borderRadius: BorderRadius.full, backgroundColor: Colors.highlight }`,
  `text: { ...Typography.small, fontWeight: "600", color: Colors.onHighlight }`).
  `Colors.highlight` / `onHighlight` du design system, jamais une couleur inventée.
- Volontairement une petite pastille et non une bannière pleine largeur : la bannière
  minutes juste en dessous est la pleine largeur, et les deux ne doivent pas se lire comme
  la même alerte. Elles s'empilent dans le `ListHeader` (notice puis bannière), chacune
  portant sa propre marge haute, donc un utilisateur en trial et à court de minutes voit
  les deux sans chevauchement. Salutation, bouton Daily Digest et en-tête de section sont
  inchangés.

Carte Account : titre `Free trial`, puce `Mix` (nom lu dans la config), métrique
`FREE TRIAL ENDS` / `18 sept.`, et le rappel `Minutes cover audio and video we transcribe.
Reading your library is unlimited. Trial minutes do not refill.` — le vocabulaire du
paywall de task-299 (`free trial`, nom du tier) est repris tel quel.

### Vérifications

`cd mobile && npm run typecheck && npm run lint` : typecheck muet, lint 0 erreur (6 warnings
préexistants, tous hors des fichiers touchés — `_layout.tsx`, `digest.tsx`, `paywall.tsx`,
`purchaseService.ts`).

La projection a été rejouée hors app sur le compte réel décrit par la tâche (créé le
2026-08-19 20:42Z, fermeture 2026-09-18 20:42Z, appareil en Europe/Paris) : le 2026-08-20
→ `Free Trial - 29 days left` sous une date affichée « 18 sept. » ; le 2026-09-17 22:00Z
(déjà le 18 en local) → `last day`, comme à 08:00Z et 20:41Z le 18 ; date nulle ou
illisible → `Free Trial`.

À vérifier par l'owner après déploiement : le rendu visuel de la pastille (petite, centrée)
ne se juge qu'au simulateur, et sur son compte de dev l'onglet Account doit afficher
« 18 septembre ».
<!-- SECTION:NOTES:END -->
