---
id: task-300
title: >-
  Make the free trial a single 30-day quota window instead of resetting on the
  1st of the month
status: Done
assignee: []
created_date: '2026-08-19 20:41'
updated_date: '2026-08-19 21:40'
labels:
  - backend
  - pricing
  - quota
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 30-day free trial grants twice its allowance and announces the wrong date. Both come from the same line: for a user without a subscription, `get_entitlement_snapshot` (`media_summarizer/core/services/quota_enforcer.py`) falls back to the calendar month — `period_key = now.strftime("%Y-%m")` and `period_end = _next_month_start(now)`.

Two consequences, observed on a real account created on 2026-08-19 on dev:

- **Double allowance.** The counter row is keyed on the calendar month, so an account created on 19 August gets 300 minutes for the 12 remaining days of August, then a fresh 300 on 1 September for the 18 trial days that follow. A 30-day trial hands out 600 minutes. The owner's decision: **one trial, one allowance** — `free_trial.minutes_per_month` (300) covers the whole trial window, and nothing refills inside it.
- **Wrong date shown.** `period_end` is exposed as `resets_at` by `GET /api/v1/entitlements/status` (`media_summarizer/api/endpoints/entitlements.py`) and is the only date the app has. During a trial it points at the 1st of next month, which is neither when the trial ends (2026-09-18 for that account) nor a date on which anything meaningful happens once the allowance stops refilling. The trial's real end date is currently computed nowhere and exposed nowhere: it is implicit in `created_at + duration_days` inside `_is_free_trial_active`.

## Target model

A trial is a billing period like a subscription period, just one that happens once and does not renew: it opens at `user.created_at`, closes at `created_at + free_trial.duration_days`, holds one counter row, and `period_end` is its close. That makes it symmetric with the subscription branch, which already keys its counter on its own window (`sub:<YYYY-MM-DD>`) precisely so the allowance empties on the anniversary rather than on the 1st.

Keep the endpoint's existing contract of **one date**: `resets_at` already means "the end of the period the gauge describes", and for a trial that end is the trial's end. Do not add a second date field — the docstring at `entitlements.py:87` explains why, and the app has exactly one place to render it.

The eligibility test and the announced date must be the same boundary. Today `_is_free_trial_active` uses `account_age_days <= duration_days`, which grants a 31st day; whatever `period_end` says, access must stop there and not a day later.

## Not in scope

- **No compatibility path.** Nothing is deployed and there are no users (see `AGENTS.md`, "Nothing is deployed yet"): do not read the old `YYYY-MM` key as a fallback for trial users, do not migrate existing rows, do not dual-write. The owner's own dev counters being orphaned is expected and fine.
- Provider pool counters (`PROVIDER_POOL_USER_ID`) stay on the calendar month — they are platform-wide, not per-user, and `_current_month()` in `media_summarizer/utils/quota_usage_db.py` is theirs.
- Subscription periods are already correct; do not touch that branch beyond what symmetry requires.
- All mobile-facing copy and the trial countdown UI belong to the mobile task that depends on this one. This task ships the truthful state; nothing else renders it yet.

## Owner notes (not acceptance criteria)

- The end-to-end proof is the owner's own account on dev after the next deploy: the Account tab must show 18 September, and the gauge must not jump back to 300 minutes on 1 September. The deploy happens on push to `main`, after the implementer is gone.
- Figures live in `DEFAULT_PRICING_CONFIG` (`media_summarizer/core/services/pricing_config_service.py`, `free_trial`: 30 days, tier `mix`, 300 min, 180 min per item) and are editable at runtime through `PUT /api/pricing/admin`. Read them, never hardcode them.
- `task-299` rewrites the paywall and states the trial terms there. It reads `is_free_trial` / `subscription_status` from this same endpoint, so this task lands first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A user inside the free trial resolves to one single consumption window: the period_key returned by get_entitlement_snapshot / resolve_period_key is derived from the trial window and is byte-identical on the day the account is created and on any later day of the trial, including after a calendar-month boundary is crossed
- [x] #2 The period_end of a free-trial snapshot is the instant the trial closes, computed from the user's created_at plus free_trial.duration_days read from the pricing config, and no longer the first instant of the next calendar month
- [x] #3 _is_free_trial_active and period_end agree on the same boundary: an account is entitled while now is before that instant and not entitled at or after it, with no extra day granted by a day-count comparison
- [x] #4 GET /api/v1/entitlements/status returns that trial-close instant as resets_at when is_free_trial is true, and the response gains no second date field
- [x] #5 The trial period_key format is documented next to the sub: format in the module header of media_summarizer/utils/quota_usage_db.py, and the get_entitlement_snapshot docstring no longer states that users without a subscription fall back to the calendar month
- [x] #6 free_trial.duration_days and free_trial.minutes_per_month are still read from the pricing config at request time, so raising duration_days through PUT /api/pricing/admin moves the trial window with no code change and no hardcoded 30 anywhere in the resolution path
- [x] #7 No fallback read of the old YYYY-MM counter key survives for trial users, no existing counter row is migrated, and the provider-pool counters keyed by _current_month() are unchanged
- [x] #8 ruff check . and mypy media_summarizer are clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Une fenêtre, lue une fois, par deux consommateurs

Le correctif tient dans un helper : `_free_trial_window(user_id, config)` rend le couple
`(ouverture, fermeture)` du trial — `user.created_at` et `created_at + duration_days` — ou
`None` quand il n'y a pas de trial (désactivé dans la config, ou utilisateur introuvable).
C'est la seule source de la date : `_is_free_trial_active` et `period_end` la lisent tous
les deux, donc le test qui autorise un import et la date que l'app annonce ne peuvent plus
diverger. C'était exactement la faille d'origine — l'échéance était implicite dans un
calcul d'âge de compte, la date affichée venait d'un calcul sans rapport.

`_is_free_trial_active` change de forme : de `async (user_id) -> bool` elle devient un
prédicat pur `(window, now) -> bool`. Le snapshot ne lit donc l'utilisateur qu'une fois
au lieu de deux, et la fonction ne peut plus, par construction, appliquer une règle
différente de celle qui a produit la fenêtre. Son type de retour est un
`TypeGuard[TrialWindow]` : mypy sait que la branche `elif` a une fenêtre non nulle, sans
`assert` de confort.

La comparaison passe de `account_age_days <= duration_days` à `now < window[1]`. L'ancienne
forme accordait un 31e jour (le jour 30 satisfait `<=`), et travaillait à la journée alors
que la fenêtre a un instant précis. Compte du 2026-08-19 21:34 → fermeture le
2026-09-18 21:34 : la dernière minute avant est autorisée, l'instant lui-même ne l'est pas.

### La clé du compteur est datée de l'ouverture, pas de la fermeture

`trial:<YYYY-MM-DD de created_at>`, à côté du `sub:<YYYY-MM-DD de period_end>` des
abonnements. La dissymétrie est voulue et documentée aux deux endroits (`_trial_period_key`,
en-tête de `quota_usage_db.py`) : un abonnement se renouvelle, et re-keyer sur la fin est
précisément ce qui lui rend son allocation ; un trial ne se renouvelle jamais. Keyer un
trial sur sa fermeture aurait rendu la clé sensible à `duration_days` — l'owner allongeant
le trial de 30 à 45 jours via `PUT /api/pricing/admin` aurait déplacé la clé et redonné
300 minutes neuves, soit le bug corrigé ici sous une autre forme. Keyé sur l'ouverture, un
allongement déplace l'échéance et rien d'autre.

La clé ne dépend d'aucun `now` : elle est identique le jour de la création et n'importe
quel jour suivant, frontière de mois traversée ou non.

### Ce qui n'a pas bougé

Aucune lecture de repli sur l'ancienne clé `YYYY-MM` pour un utilisateur en trial, aucune
migration de ligne existante : les compteurs de dev de l'owner sont orphelins, ce qui est
le résultat attendu (`AGENTS.md`, « Nothing is deployed yet »). Les pools fournisseurs
(`PROVIDER_POOL_USER_ID`) gardent `_current_month()` — ils suivent des cycles de
facturation Apify/LlamaParse, pas la fenêtre d'un utilisateur. La branche abonnement n'est
pas touchée. `GET /api/v1/entitlements/status` garde ses champs à l'identique : `resets_at`
véhicule maintenant la fermeture du trial quand `is_free_trial` est vrai, aucun second
champ de date n'a été ajouté, et sa docstring dit désormais ce que la date signifie dans
les deux cas.

Les chiffres restent lus dans la config à chaque requête (`free_trial.duration_days`,
`free_trial.minutes_per_month`) : le seul `30` du chemin de résolution est le défaut de
`.get()` déjà présent avant cette tâche, jamais une valeur en dur.

### Vérifications

`ruff check .` et `mypy media_summarizer` (170 fichiers) passent. La frontière et la
stabilité de la clé ont été vérifiées en important les deux fonctions pures sur le compte
réel décrit par la tâche (créé le 2026-08-19) : clé `trial:2026-08-19` inchangée du jour
de création au 18 septembre, entitled jusqu'à 2026-09-18 21:33 inclus, plus au-delà, et
le 1er septembre ne produit aucune clé nouvelle donc aucun rechargement.

**Reste à l'owner** : la preuve de bout en bout est son propre compte sur dev après le
prochain déploiement (push sur `main`) — l'onglet Compte doit afficher le 18 septembre, et
la jauge ne doit pas revenir à 300 minutes le 1er septembre.
<!-- SECTION:NOTES:END -->
