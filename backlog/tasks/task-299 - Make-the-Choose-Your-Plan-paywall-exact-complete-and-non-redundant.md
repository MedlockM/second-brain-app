---
id: task-299
title: 'Make the Choose Your Plan paywall exact, complete and non-redundant'
status: Done
assignee: []
created_date: '2026-08-19 20:24'
updated_date: '2026-08-19 22:12'
labels:
  - mobile
  - ui
  - paywall
  - copy
  - phase-6
dependencies:
  - task-300
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The paywall (`mobile/app/paywall.tsx`, title "Choose Your Plan") is the last screen a user reads before paying, and today it states things the backend does not do, omits two facts that change which tier someone should buy, and says "reading is unlimited" five times. It has to become exactly true, complete, and say each thing once.

Source of truth for every figure below: `DEFAULT_PRICING_CONFIG` in `media_summarizer/core/services/pricing_config_service.py` (seeded into DynamoDB, editable at runtime through `PUT /api/pricing/admin`) and the conversions in `media_summarizer/core/services/quota_enforcer.py`. Both implement the validated consumption model of `docs/research/task-287-consumption-model/README.md` (`owner_decision: ok`). Where the screen and that config disagree, the config is right and the screen is wrong.

## 1. What the screen says that is false

- **"Unlimited articles, web pages and documents"** (all three cards) — documents are metered. `quota_enforcer.minutes_for_document_pages()` charges one minute per five pages (`unit_conversion.document_pages_per_minute: 5`). The card contradicts the legend printed a few lines below it ("a PDF counts a minute per five pages").
- **"Unlimited flashcards, notes and summaries"** (all three cards) — only generations over a *single item* are free. `quota_enforcer.minutes_for_collection_sources()` charges one minute per five sources for a generation over a collection, and nothing on the paywall mentions that a metered unit exists there at all.
- **"articles, web pages and short clips are free"** (`MINUTES_LEGEND`) — "short clips" is not a category the backend has. TikToks and Instagram photo posts are free whatever their length; a Reel, a short YouTube video without bought captions, or a 40-second voice note are charged their real duration rounded up to at least one minute (`minutes_for_seconds`). As written, the sentence promises free where we bill.
- **The header comment of `paywall.tsx`** asserts "Minutes are the only thing a plan limits" and "the three tiers have exactly the same features". Both are false — see item 2 — and the comment is what will keep the copy wrong after the next edit.

## 2. What the screen omits, and that changes the purchase decision

- **The longest single import differs per tier**: `max_minutes_per_item` is **60 min on Reader, 180 min on Mix, 240 min on Audio-Heavy**. Over it, the submission is refused with `item_too_long` and there is no workaround — "Split it into shorter parts" (`quota_enforcer._item_too_long_message`). Someone who buys Reader for two-hour podcasts cannot process a single one, and learns it only after paying.
- **A 30-day free trial is already live**: `free_trial` is `enabled: True`, 30 days, on the **Mix** tier with **300 min** and a 180-min per-import ceiling, granted by account age (`quota_enforcer._is_free_trial_active` — every account younger than 30 days has it, no purchase involved). The paywall never mentions it, so a user in their trial window sees three "Subscribe" buttons and no indication that they already hold Mix-level access, or when it stops. `GET /api/v1/entitlements/status` already reports `is_free_trial` and `subscription_status: "free_trial"`, so this can be stated from real state rather than as a static line that would be wrong for everyone past day 30. Note for whoever writes the copy: per `task-261`, there is deliberately **no App Store introductory offer** — the trial is server-side only, so the wording must not read as a store trial attached to a purchase.

## 3. What the screen repeats

- The allowance is printed twice per card: `tier.minutes` ("300 min (5 h)") then the first bullet ("5 hours of audio and video a month").
- Six of the nine bullets are byte-identical across the three cards, so they triple the reading length while carrying zero information about the choice being made.
- "Reading is unlimited" is stated in the subtitle, in a bullet on each of the three cards, and again in the legend — five times on one screen, plus a sixth on the Account tab.
- The subtitle quantifies Mix and Audio-Heavy and ignores Reader, which repeats two card values and makes the third tier look like an afterthought.

## 4. The same numbers are written three times in the repo

`pricing_config_service.DEFAULT_PRICING_CONFIG` (authoritative), `OFFERINGS_CONFIG` + `MINUTES_LEGEND` in `media_summarizer/api/endpoints/entitlements.py` (a hardcoded second copy, sent to the app as `offerings_config` / `minutes_legend` when the caller has no plan), and `TIER_INFO` + `MINUTES_LEGEND` in `mobile/app/paywall.tsx` (a third). The mobile app declares the payload in `mobile/src/contexts/PurchasesContext.tsx` and never reads it, and `GET /api/pricing` — public, already returning `minutes_per_month`, `max_minutes_per_item` and `free_trial` — is called by nobody. Three copies of one fact is how the screen got stale, and fixing the wording without collapsing them just resets the clock.

Nothing is deployed and there are no users: delete the copies that lose, do not keep them as fallbacks. Pick one runtime source the app reads and one place the strings live; the implementer chooses which, and states the choice in the code.

## 5. Do not break

- Store-mandated legal text (charge on confirmation, auto-renewal, 24-hour cancellation window) and **Restore Purchases** must stay. Say the renewal terms once.
- Prices on screen must keep coming from the store package (`pkg.product.priceString`) when offerings are loaded, so a localized store price is never overwritten by a hardcoded "3 EUR/mo". If a pre-load fallback remains, it must not be a second hardcoded price list.
- `mobile/.maestro/07_paywall.yaml` asserts the texts `Choose Your Plan`, `Reader`, `Mix`, `Audio-Heavy`, the absence of `Unavailable`, and the ids `paywall-screen` / `paywall-close-button`. Keep them or update the flow in the same change.
- Concision is a constraint, not a bonus: the two facts added in item 2 must be paid for by the deduplication of item 3, not stacked on top of it.

## Owner notes (not acceptance criteria)

- The visual result can only be judged on a device or simulator; the agent cannot run one. Attach the final copy for each card in the implementation notes so it can be read without building.
- The wording is what App Review reads on the subscription screen. Once this lands, re-check `docs/store-listing/app-store-connect.md` for the same claims before submitting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No claim on the paywall contradicts pricing_config_service.DEFAULT_PRICING_CONFIG or the quota_enforcer conversions: nothing that debits minutes (documents at one minute per five pages, collection-level generations at one minute per five sources, any transcribed audio or video) is described as unlimited or free anywhere on the screen
- [x] #2 The paths presented as costing nothing are exactly the ones that debit zero minutes in quota_enforcer (articles, web pages, TikToks, Instagram photo posts, single-item generations) and the copy no longer uses the category 'short clips', which does not exist in the backend
- [x] #3 Each tier communicates its own longest single import with the value from its tier config (60 min on Reader, 180 min on Mix, 240 min on Audio-Heavy) and says that going over it is a refusal, not an upgrade prompt
- [x] #4 The 30-day Mix free trial is communicated from the live entitlement state returned by GET /api/v1/entitlements/status (is_free_trial / subscription_status) so the screen is true both inside and outside the trial window, and the wording does not present it as a store introductory offer
- [x] #5 Every fact appears once on the screen: no card prints its allowance twice, no line is identical across two tier cards, the subtitle no longer restates a value already on a card, and 'reading is unlimited' is stated exactly once
- [x] #6 The tier facts (name, monthly allowance, per-import ceiling, trial terms) reach the screen from one runtime source that the app reads, and the now-redundant copies are deleted rather than kept as fallbacks — a repo-wide grep for the figures 60, 300, 720, 180, 240 and for the prices 3/5/9 finds each tier's numbers in one authoritative place only
- [x] #7 Prices displayed come from the store package priceString when offerings are loaded, and no second hardcoded EUR price list survives in mobile/
- [x] #8 The store-mandated renewal and charge disclosure is present once, and the Restore Purchases action is still on the screen
- [x] #9 The Account tab hint in mobile/src/components/SubscriptionStatusCard.tsx and the refusal messages in quota_enforcer state the same rules in the same words as the new paywall copy, with no claim on one surface that the other contradicts
- [x] #10 The total user-visible character count of the paywall copy does not exceed today's, and the implementation notes record the before/after figures
- [x] #11 mobile/.maestro/07_paywall.yaml still matches the screen (texts Choose Your Plan, Reader, Mix, Audio-Heavy, absence of Unavailable, ids paywall-screen and paywall-close-button) or is updated in the same change
- [x] #12 cd mobile && npm run typecheck && npm run lint are clean, and if any Python file was touched, ruff check . and mypy media_summarizer are clean too
- [x] #13 The header comment of mobile/app/paywall.tsx no longer claims the three tiers have identical features and records where the plan figures now come from
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Une seule source runtime : `GET /api/pricing`

Les trois copies des mêmes chiffres sont réduites à une. `OFFERINGS_CONFIG` et
`MINUTES_LEGEND` sont supprimés d'`entitlements.py`, avec les champs
`offerings_config` / `minutes_legend` de la réponse et le type que
`PurchasesContext.tsx` déclarait sans jamais le lire. `TIER_INFO` et sa légende
disparaissent de `paywall.tsx`. Restent : `DEFAULT_PRICING_CONFIG` (autoritaire)
et `GET /api/pricing`, qui la sert.

Le partage des rôles entre les deux endpoints devient net et est écrit dans les
deux docstrings : `/api/v1/entitlements/status` ne décrit que **l'état de
l'appelant** (son plan, sa jauge, sa date), `/api/pricing` ne décrit que **l'offre**
(tiers, plafonds, trial, conversions). Le paywall lit les deux, chacun pour ce
qu'il sait.

`/api/pricing` gagne `unit_conversion` (`captions_minutes`,
`document_pages_per_minute`, `collection_sources_per_minute`) : la légende des
minutes est désormais *calculée* à partir des mêmes valeurs que `quota_enforcer`
convertit, au lieu d'être une phrase écrite deux fois qui pouvait dériver.
`min_minutes_per_transcription` reste interne — l'arrondi plancher n'est pas une
promesse faite à l'écran, et exposer un champ que personne ne lit était la
mécanique même du bug. Même raison pour `description` / `description_fr`,
supprimés du payload public **et** de `DEFAULT_PRICING_CONFIG` : ils ne faisaient
que reformuler `minutes_per_month` en prose, personne ne les lisait, et la ligne
d'allocation est maintenant dérivée du nombre. (Les tables `pricing_config-dev`
déjà peuplées gardent ces attributs — `_merge_defaults` ne supprime rien — mais
plus rien ne les lit.)

Côté app, `src/services/pricingService.ts` (fetch public, sans session : une
grille tarifaire n'est pas une donnée utilisateur) et `src/lib/planCopy.ts`, où
vivent **toutes** les phrases et **aucun** chiffre. Le paywall n'est plus qu'un
rendu. Si `/api/pricing` ne répond pas, l'écran affiche une erreur et un bouton
« Try again » : pas de cartes plutôt que des cartes fausses — décrire un plan
avec des nombres compilés dans le build est exactement la dérive qu'on supprime.

### Ce que l'écran dit maintenant (copie finale, lisible sans build)

Titre `Choose Your Plan`, sous-titre `Plans differ only by how much we transcribe for you.`

Ligne d'essai (visible **uniquement** si `is_free_trial` est vrai ; date = `resets_at`) :
`Your 30-day free trial is running: Mix access until 18 Sep, at no charge and nothing to cancel.`

| Carte | Prix | Ligne 1 | Ligne 2 | Bouton |
|---|---|---|---|---|
| Reader | store `priceString` (repli `3 EUR/mo`) | `1 h of audio and video a month` | `1 h max per import` | Subscribe |
| Mix *(mis en avant)* | store `priceString` (repli `5 EUR/mo`) | `5 h of audio and video a month` | `3 h max per import` | Subscribe |
| Audio-Heavy | store `priceString` (repli `9 EUR/mo`) | `12 h of audio and video a month` | `4 h max per import` | Subscribe |

Légende, une fois, sous les cartes :

> Minutes cover audio and video we transcribe. Reading your library is unlimited.
> Audio and video count their real length, a video with bought subtitles 1 min, a
> PDF 1 min per 5 pages, a whole-collection generation 1 min per 5 sources.
> Articles, web pages, TikToks, Instagram photo posts and single-item generations
> count nothing. Past a plan's per-import maximum an import is refused, not
> billed: split it into shorter parts.

Puis `Restore Purchases` et le texte légal, inchangés.

Trois décisions de rédaction qui méritent d'être dites :

- **« Reading *your library* is unlimited »**, pas « reading is unlimited ». Consulter
  ce qui est déjà enregistré est gratuit pour tout média ; c'est l'*import* d'un
  PDF qui débite. La forme non qualifiée aurait contredit la phrase suivante.
- **Le badge « Most Popular » est supprimé.** Rien n'a jamais été vendu : c'était
  un claim invérifiable sur un écran dont la tâche est d'être exact. La mise en
  avant visuelle reste, mais elle est maintenant dérivée de `free_trial.tier` —
  la carte encadrée est celle du niveau que l'essai accorde.
- **Le plafond par import est chiffré sur chaque carte, et la règle de refus dite
  une seule fois** dans la légende. La répéter par carte aurait violé « aucune
  ligne identique entre deux cartes ».

### Cohérence entre surfaces

Le hint de l'onglet Compte n'est plus une chaîne recopiée : il *importe*
`MINUTES_RULE`, la première phrase de la légende du paywall. Les deux écrans
expliquent le compteur avec les mêmes mots, ou pas du tout.

`_NO_PLAN_MESSAGE` disait « Subscribe to keep saving **audio and video** to your
library » alors que `evaluate_submission` refuse **tout** import sans plan, un
article compris : il promettait un palier gratuit qui n'a jamais existé.
Corrigé en « Subscribe to keep saving to your library ». `_item_too_long_message`
n'a pas bougé — il partageait déjà « split it into shorter parts » et
`formatMinutes` en TS est le miroir de `format_minutes` en Python, donc « 3 h »
sur la carte et « 3 h » dans le refus s'écrivent pareil.

`docs/store-listing/app-store-connect.md` (note owner) : les trois descriptions
produit étaient fausses — Audio-Heavy annonçait encore l'allocation d'avant
task-287, Mix et Audio-Heavy étaient formulées comme cumulatives (« Reader plus… »)
alors qu'une allocation est un total, et Reader citait documents et captions sans
dire qu'ils débitent. Remplacées par les lignes d'allocation du paywall, mot pour
mot.

### Vérifications

- `cd mobile && npm run typecheck` : clean. `npm run lint` : 0 erreur, 6 warnings
  tous préexistants (`no-explicit-any` dans les `catch` du paywall et de
  `purchaseService`, `no-unused-vars` dans `(tabs)/_layout.tsx` et `digest.tsx`).
- `ruff check .` et `mypy media_summarizer` (170 fichiers) : clean.
- **Caractères visibles : 1123 avant → 1117 après**, ligne d'essai comprise (pire
  cas) ; 1020 hors fenêtre d'essai. Compté chaîne par chaîne, chacune vérifiée
  présente dans le source, légende et cartes rendues en exécutant réellement
  `planCopy.ts` compilé sur le payload que `/api/pricing` produit à partir de
  `DEFAULT_PRICING_CONFIG`.
- Grep repo-wide : plus aucun 60/300/720/180/240 ni prix 3/5/9 lié à un tier dans
  `mobile/` — les seuls « 60 » restants y sont des conversions minutes↔heures. Les
  valeurs des tiers n'existent plus qu'en un endroit,
  `pricing_config_service.DEFAULT_PRICING_CONFIG`.
- `mobile/.maestro/07_paywall.yaml` est inchangé et matche toujours : `Choose Your
  Plan` est en dur dans le header, `Reader` / `Mix` / `Audio-Heavy` arrivent de
  `/api/pricing` avec ces noms exacts, `Unavailable` n'apparaît toujours que si un
  package du store manque, et les ids `paywall-screen` / `paywall-close-button`
  n'ont pas bougé.

### AC #5, une nuance assumée

« Aucune ligne identique entre deux cartes » : les trois boutons portent toujours
`Subscribe`. C'est un libellé d'action, pas un fait sur le plan — trois verbes
différents pour la même action seraient une régression. Les six bullets
identiques que visait l'AC ont disparu.

### Reste à l'owner

- **Le rendu visuel ne peut être jugé que sur appareil** : la ligne d'essai en
  encadré, deux lignes par carte au lieu de trois puces, et la légende à quatre
  phrases changent l'équilibre de l'écran.
- **Le paywall dépend maintenant d'un `/api/pricing` déployé avec
  `unit_conversion`.** Avant le push sur `main`, une app buildée en local qui
  parle au `-dev` actuel affichera la légende sans la phrase des conversions (les
  champs absents sont omis, pas de crash), mais les cartes seront correctes.
  Après déploiement, vérifier que `GET /api/pricing` renvoie bien `unit_conversion`
  et n'a plus de `description`.
- **Capture pour App Review** : la refaire après ce changement, l'ancienne montre
  les bullets supprimées.
<!-- SECTION:NOTES:END -->
