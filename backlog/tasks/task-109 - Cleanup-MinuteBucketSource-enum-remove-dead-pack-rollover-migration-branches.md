---
id: task-109
title: 'Cleanup MinuteBucketSource enum: remove dead pack/rollover/migration branches'
status: To Do
assignee: []
created_date: '2026-05-29 08:46'
labels:
  - cleanup
  - billing
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le système de quota minutes (`media_summarizer/core/services/minute_pool.py`) a une enum `MinuteBucketSource` avec 4 valeurs : `subscription`, `pack`, `rollover`, `migration`. **Seul `subscription` est effectivement produit en prod** par le webhook RevenueCat (`api/endpoints/revenucat_webhook.py:204, 270, 386`). Les 3 autres valeurs sont uniquement lues / triées mais jamais créées — c'est du résiduel d'un ancien design (cf. commentaire `# as per PAYMENT_SYSTEM_V2.md line 24` dans `minute_pool.py:91`) qui n'a pas été nettoyé lors de la migration vers le pricing V1 validé en task-65.

Le pricing V1 retenu (cf. `docs/research/task-65-pricing-v1-benchmark/README.md`, `owner_decision: ok`) ne mentionne ni rollover ni packs — modèle strictement « tier mensuel → minutes mensuelles → reset à la fin de la période ».

## Conséquences actuelles

- `finalize_usage()` trie les buckets par priorité `rollover → subscription → packs` mais 2 branches sur 3 sont mortes en pratique.
- L'endpoint `GET /api/entitlements/status` retourne un breakdown `{subscription, pack, rollover, migration}` dont 3 des 4 compteurs valent toujours 0.
- Le commentaire `# Used for TTL (packs, rollover)` sur `expires_at` dans `MinuteBucket` est maintenant trompeur.
- Pollue la lecture du code pour les humains et les agents.

## Scope

1. Réduire l'enum `MinuteBucketSource` à `subscription` uniquement (ou supprimer l'enum si elle ne sert plus à rien).
2. Simplifier `finalize_usage()` : un tri unique sur `period_end` (ou `created_at` à défaut) suffit pour départager les buckets `subscription` qui co-existeraient en cas de chevauchement de périodes.
3. Simplifier le breakdown `entitlements.py:106` : retourner `{subscription: <int>}` ou supprimer le breakdown si la valeur unique remplace la table de comptage.
4. Nettoyer les commentaires obsolètes dans `billing.py` et `minute_pool.py` (mentions `PAYMENT_SYSTEM_V2.md`, `(packs, rollover)` sur `expires_at`).
5. Vérifier qu'il n'existe pas un fichier `docs/PAYMENT_SYSTEM_V2.md` à supprimer ou archiver.
6. Mettre à jour les tests qui consommeraient les valeurs supprimées.

## Hors-scope

- Pas de migration de données : la table DynamoDB `minute_buckets` ne contient en pratique que des lignes `subscription` (rien à backfill).
- Pas de modification du contrat de réponse de `/api/entitlements/status` autre que l'aplatissement du breakdown — si le mobile lit un champ spécifique, le garder (vérifier dans `mobile/`).

## Vérification

- `grep -rE "MinuteBucketSource\.(pack|rollover|migration)" media_summarizer/` ne renvoie plus aucun résultat.
- `pytest media_summarizer/tests/` reste vert.
- L'endpoint `/api/entitlements/status` retourne un breakdown cohérent avec le nouveau modèle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'enum MinuteBucketSource est réduite à subscription (ou supprimée) et plus aucune référence pack/rollover/migration n'existe dans media_summarizer/
- [ ] #2 finalize_usage() est simplifiée à un tri unique sur period_end (ou created_at) sur les buckets subscription
- [ ] #3 Le breakdown retourné par /api/entitlements/status ne contient plus pack/rollover/migration (cohabitation avec mobile vérifiée)
- [ ] #4 Les commentaires obsolètes mentionnant PAYMENT_SYSTEM_V2.md ou packs/rollover sont retirés ou corrigés
- [ ] #5 Le fichier docs/PAYMENT_SYSTEM_V2.md s'il existe encore est supprimé ou archivé explicitement
- [ ] #6 Les tests existants couvrant minute_pool restent verts après simplification
- [ ] #7 Aucune régression sur le path nominal allocate_hold_for_job → finalize_usage → update bucket
<!-- AC:END -->
