---
id: task-59
title: Ingestion de posts X (Twitter) via API v2
status: Done
assignee: []
created_date: '2026-03-19 10:37'
updated_date: '2026-03-20 21:47'
labels:
  - ingestion
  - second-brain
  - twitter
  - api
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'article_extraction_worker existant ne peut pas traiter les URLs X/Twitter car la page est une SPA React. Le support est maintenant assuré via l'API X v2 en mode lookup simple, sans reconstruction de thread dans cette itération.

## Comportement livré

1. L'utilisateur soumet une URL X/Twitter de post public (ex: `https://x.com/user/status/123456`).
2. Le système canonicalise l'URL vers une forme stable par ID, déduplique `x.com` et `twitter.com`, puis route vers un resolver dédié.
3. Un worker dédié `x_ingestion_worker.py` appelle `GET /2/tweets/:id` pour récupérer le contenu complet du post.
4. Le texte complet est uploadé dans S3 comme transcript (`{job_id}.txt`).
5. Le média reste modélisé comme `media_type=article` avec `source_platform=x` pour permettre le filtrage/triage aval par source.
6. Le pipeline s'arrête au statut transcript-ready / ready-for-artifacts, sans génération automatique de résumé.

## Architecture

- **Resolver** : `XPostResolver` — extrait `tweet_id` depuis l'URL canonique et produit `media_type=article`, `source_platform=x`.
- **Worker** : `x_ingestion_worker.py` — appelle l'API X v2, choisit `note_tweet.text` quand présent, puis upload le transcript texte vers S3.
- **Auth** : Bearer Token app-only — pas besoin d'OAuth utilisateur X pour les posts publics.
- **Endpoint API v2 utilisé** : `GET /2/tweets/:id`
- **Librairie HTTP** : `httpx` pour rester aligné avec le codebase.

## Gestion d'erreurs

- `404` : post supprimé ou introuvable
- `401` / `403` : auth/provider invalide ou contenu inaccessible
- `402` : crédits X épuisés (`CreditsDepleted`)
- `429` : rate limiting
- `5xx` / timeouts : erreurs temporaires retryables
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Une URL x.com/twitter.com de post public est détectée, canonicalisée et routée vers le worker X dédié
- [x] #2 Le texte complet du post est récupéré via `GET /2/tweets/:id`, en privilégiant `note_tweet.text` quand présent
- [x] #3 Le transcript texte est uploadé dans S3 et le média atteint le pipeline transcript-ready existant
- [x] #4 Le média est exposé comme `media_type=article` et `source_platform=x` pour le filtrage aval
- [x] #5 Les erreurs API X (`404`, `401`/`403`, `402 CreditsDepleted`, `429`, `5xx`) sont gérées proprement
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémenté le support X/Twitter lookup simple sans thread: ajout de `source_platform=x` aux contrats backend/front, canonicalisation stable `x.com/i/status/<tweet_id>`, classification dédiée `x.default`, resolver `XPostResolver`, branche orchestrateur et queue `x-ingestion-queue`, puis worker `x_ingestion_worker.py` basé sur `httpx` et l'API X v2 `GET /2/tweets/:id`.

Le worker choisit `note_tweet.text` quand présent, met à jour `podcast_title` / `episode_title`, persiste `transcription_metadata` avec `provider=x_api_lookup`, écrit `extraction_metadata` détaillé (`tweet_id`, auteur, metrics, etc.), et publie les événements `episode_completion_status` comme les autres contenus textuels.

Mises à jour infra effectuées dans Docker Compose, Terraform localstack/scaling/monitoring et scaling controller pour la nouvelle queue/worker X.

Vérifications ciblées effectuées:
- AST parse OK sur les fichiers Python modifiés
- canonicalisation validée sur `x.com`, `twitter.com` et `x.com/i/web/status/...` vers `https://x.com/i/status/<id>`
- lookup réel validé sur le post `https://x.com/0x_Discover/status/2034979291474092526` avec réponse `HTTP 200`, `note_tweet` présent et 1 utilisateur dans `includes.users`

Aucun test automatisé additionnel n'a été ajouté dans cette tâche, conformément aux règles du projet.
<!-- SECTION:NOTES:END -->
