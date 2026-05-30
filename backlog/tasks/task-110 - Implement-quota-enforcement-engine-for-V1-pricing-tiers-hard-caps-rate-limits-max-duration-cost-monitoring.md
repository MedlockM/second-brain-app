---
id: task-110
title: >-
  Implement quota enforcement engine for V1 pricing tiers (hard caps + rate
  limits + max duration + cost monitoring)
status: To Do
assignee: []
created_date: '2026-05-29 08:55'
labels:
  - billing
  - pricing
  - v1
  - feature
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le benchmark `docs/research/task-65-pricing-v1-benchmark/README.md` (`owner_decision: ok`) a défini les quotas par type de média pour V1, et task-86 a câblé la **configuration** de ces quotas dans la table DynamoDB `pricing_config` + endpoints `/api/pricing`. **Mais le moteur d'enforcement n'a jamais été implémenté** : task-35 (Media Processing Quotas) qui devait s'en charger a été archivée (`owner_decision: abandoned`), et task-86 s'est limitée à exposer la config.

Audit du code (2026-05-29) :
- ✅ `pricing_config_service.py` contient les bons chiffres (hard_caps, rate_limits, cost_monitoring, max_audio_per_import).
- ✅ `pricing.py` (`GET /api/pricing`) renvoie la config au mobile.
- ❌ **Aucun consumer côté backend** : `grep -rE "hard_caps|hard_block_eur|max_audio_per_import" media_summarizer/` ne retourne que la définition + l'exposition publique. Aucun check à la soumission.
- ❌ Le seul guard actuel est `media_submission.py:54-66` qui compare `minutes_required` à `get_total_available_minutes()` — donc **uniquement** la balance audio. Aucun cap par type, aucun rate limit per-tier, aucun max duration par import, aucun cost monitoring.

## Conséquences (risques V1)

- Tier **text_only** : aucun blocage structurel d'une submission audio si le user a des minutes flottantes (bug webhook RevenueCat ou crédit free trial).
- Tier **mix / audio_heavy** : un user peut soumettre un podcast 4h, dépasser 500 articles/mois, importer 100 PDFs/jour — pas de plafond.
- **Cost runaway** : un user en burst peut faire exploser les coûts Deepgram/LLM avant qu'on s'en aperçoive (warning_eur / hard_block_eur ne sont consommés par personne).

## Décision retenue (task-65, à appliquer telle quelle)

Recopiée de `pricing_config_service.py:DEFAULT_PRICING_CONFIG` (source de vérité runtime) :

**Hard caps mensuels par tier** :
- text_only : 0 audio_min, 500 articles, 100 documents, 100 youtube, max_audio_duration_minutes = 0
- mix : 300 audio_min, 500 articles, 100 documents, 100 youtube, max_audio_duration_minutes = 180
- audio_heavy : 900 audio_min, 1500 articles, 300 documents, 200 youtube, max_audio_duration_minutes = 180

**Rate limits journaliers par tier** :
- text_only : 0 audio/j, 30 text/j, 10 doc/j (5 text/min, 15 api/min)
- mix : 10 audio/j (max 60 min/import), 30 text/j, 10 doc/j (5 text/min, 30 api/min)
- audio_heavy : 20 audio/j (max 90 min/import), 100 text/j, 30 doc/j (10 text/min, 60 api/min)

**Cost monitoring par tier** (warning / hard_block / action) :
- text_only : 2.5 € / 3.5 € / `throttle_5_imports_per_day`
- mix : 4.0 € / 6.0 € / `throttle_1_audio_per_hour`
- audio_heavy : 7.0 € / 10.0 € / `throttle_and_contact_owner`

**Free trial** : 30 jours sur tier Mix avec hard cap 300 min + 300 articles + 50 docs, cost monitoring warning 3.0 € / hard_block 5.0 €.

## Scope d'implémentation

1. **Compteurs d'usage mensuel par type** :
   - Nouvelle table DynamoDB `user_usage_monthly` (PK : `user_id`, SK : `period_yyyymm` ou similaire ; attributs : `audio_minutes_used`, `articles_count`, `documents_count`, `youtube_count`, `cost_eur_estimated`, `last_updated`).
   - Incrément atomique à chaque soumission validée (utilisation de `UpdateItem` avec `ADD`).
   - Reset implicite à chaque nouveau mois (clé de partition par mois).

2. **Service `quota_enforcer`** (nouveau, dans `media_summarizer/core/services/`) :
   - `async def check_submission_allowed(user_id, media_type, duration_seconds=0) -> QuotaCheckResult` qui lit le tier du user (depuis `entitlements` / `subscription`), récupère les hard_caps + rate_limits + max_audio_per_import depuis `pricing_config_service`, vérifie le compteur mensuel courant, vérifie le compteur journalier (à stocker aussi, ex: `user_usage_daily`), et renvoie soit `allowed` soit un code d'erreur user-facing stable (`tier_quota_exceeded`, `daily_rate_limit`, `audio_too_long`, `cost_hard_block`).
   - `async def record_submission(user_id, media_type, duration_seconds, estimated_cost_eur)` à appeler après l'enqueue pour incrémenter les compteurs.

3. **Wiring à la soumission** :
   - Dans `media_submission.py:submit_media_for_user`, **avant** `allocate_hold_for_job`, appeler `quota_enforcer.check_submission_allowed`. Si refusé, renvoyer un code stable cohérent avec `user_facing_errors.py` (ajouter les nouveaux codes au registry).
   - Wiring équivalent dans `api/endpoints/media.py` (path d'upload de fichier) et `api/endpoints/podcasts.py` (path search-then-submit) — chaque entrée d'ingestion doit passer par le check.
   - Mapping `media_type` à dériver de `MediaFamily` ou `resolver_key` (audio_minute → podcasts + audio personnel + WhatsApp ; articles → ARTICLE ; documents → DOCUMENT ; youtube → YouTube ; social_video courts comptés selon ce que le benchmark dit — à vérifier).

4. **Cost monitoring** :
   - Estimer le coût d'une submission (utiliser les `cost_per_minute_eur` / `cost_per_article` si déjà dans pricing_config, sinon les ajouter en config).
   - Cumul dans le compteur mensuel `cost_eur_estimated`.
   - Lorsque `>= warning_eur` : log structuré `quota.cost_warning` (alerte CloudWatch côté infra, pas dans ce ticket).
   - Lorsque `>= hard_block_eur` : appliquer l'`action` du tier (throttle ou contact_owner) et bloquer la submission avec code `cost_hard_block`.

5. **Free trial** :
   - Lecture du flag `free_trial.enabled` + `duration_days` + `tier` + `hard_caps` + `cost_monitoring` depuis `pricing_config_service`.
   - Override les hard_caps standards du tier Mix par ceux du free_trial pendant la durée du trial.

6. **Tests** :
   - Tests unitaires sur `quota_enforcer` couvrant chaque rule (hard_cap atteint, rate_limit journalier, max_audio_per_import dépassé, tier text_only refuse audio, hard_block coût, free trial caps).
   - Tests d'intégration sur `media_submission.py` vérifiant le refus avec code stable.

7. **Documentation** :
   - Mettre à jour `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` avec la mention du check de quota dans le flow.
   - Mettre à jour `.env.example` si de nouvelles env vars apparaissent (table name).

## Hors-scope

- Re-débattre les chiffres des quotas — la décision task-65 est figée, aucune modification de `pricing_config_service.py:DEFAULT_PRICING_CONFIG` n'est attendue.
- L'UI mobile : ce ticket implémente le backend. Le mobile lit déjà les hard_caps via `GET /api/pricing` pour les afficher ; aucun changement de contrat API n'est nécessaire côté mobile (juste de nouveaux codes d'erreur `4xx` à gérer côté mobile dans un ticket follow-up si besoin).
- Création d'alarmes CloudWatch : laissé à la prochaine itération infra.

## Vérification

- Tier text_only : soumission d'un podcast → `403 tier_quota_exceeded` (audio_minutes = 0).
- Tier mix : soumission d'un podcast 4h (240 min) → `403 audio_too_long` (max 180 min/import).
- Tier mix : 11ᵉ podcast dans la même journée → `429 daily_rate_limit`.
- Tier audio_heavy : 1501ᵉ article dans le mois → `403 tier_quota_exceeded`.
- Free trial actif : caps overridés à `{300, 300, 50}` ; jour 31 → caps standards Mix reprennent.
- Cost monitoring : un user qui dépasse `hard_block_eur` est bloqué jusqu'au mois suivant.

## Contexte fichiers utiles

- `media_summarizer/core/services/pricing_config_service.py` — config en lecture (TTL 5 min).
- `media_summarizer/core/services/media_submission.py:54-66` — endroit naturel pour le hook.
- `media_summarizer/api/endpoints/media.py:301, 435` — autres entrées d'ingestion à wirer.
- `media_summarizer/api/endpoints/podcasts.py:207` — entrée podcast.
- `media_summarizer/utils/user_facing_errors.py` — registry des codes d'erreur stables à étendre.
- `docs/research/task-65-pricing-v1-benchmark/README.md` — décision validée (lecture de référence).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une table DynamoDB user_usage_monthly (et user_usage_daily si nécessaire) est provisionnée via Terraform et incrémentée atomiquement à chaque submission validée
- [ ] #2 Un service quota_enforcer expose check_submission_allowed et record_submission, lus par toutes les entrées d'ingestion (media_submission.py, api/endpoints/media.py, api/endpoints/podcasts.py)
- [ ] #3 Les hard caps mensuels par tier (audio_minutes, articles, documents, youtube) sont effectivement bloquants à la submission avec code d'erreur user-facing stable
- [ ] #4 Les rate limits journaliers per-tier (audio_imports_per_day, text_imports_per_day, document_imports_per_day, *_per_minute) sont effectivement appliqués avec code 429
- [ ] #5 max_audio_duration_minutes (180 min global) et max_audio_per_import_minutes (60/90 min selon tier) sont appliqués et refusent les imports trop longs
- [ ] #6 Le tier text_only refuse structurellement toute submission audio (audio_minutes = 0), indépendamment du solde minutes du user
- [ ] #7 Cost monitoring : warning_eur logé en structured logging, hard_block_eur bloque les submissions du mois en cours avec code stable cost_hard_block
- [ ] #8 Free trial : pendant les 30 premiers jours sur tier Mix, les hard_caps du free_trial overrident ceux du tier mix standard
- [ ] #9 Tests unitaires couvrent chaque règle (hard cap, rate limit, max duration, tier audio gating, cost block, free trial)
- [ ] #10 user_facing_errors.py est étendu avec les nouveaux codes (tier_quota_exceeded, daily_rate_limit, audio_too_long, cost_hard_block)
- [ ] #11 Aucune modification de pricing_config_service.py:DEFAULT_PRICING_CONFIG (les chiffres restent ceux validés en task-65)
- [ ] #12 docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md mentionne le check quota dans le flow de submission
<!-- AC:END -->
