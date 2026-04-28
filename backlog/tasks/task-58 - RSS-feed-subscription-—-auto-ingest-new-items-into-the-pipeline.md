---
id: task-58
title: RSS feed subscription — auto-ingest new items into the pipeline
status: To Do
assignee: []
created_date: '2026-03-18 16:13'
updated_date: '2026-03-29 21:19'
labels:
  - ingestion
  - second-brain
  - subscription
  - post-v1
dependencies:
  - task-10
  - task-29
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Un flux RSS n'est pas une source de contenu directe : c'est un fichier XML qui contient une liste de liens vers du contenu (articles, épisodes audio, etc.). L'ingestion d'un RSS n'est donc pas un nouveau worker de contenu, mais une feature de **souscription + découverte** qui se greffe sur les workers existants.

## Comportement attendu

1. L'utilisateur soumet un URL de flux RSS (ex: `https://blog.exemple.com/feed`, un Substack, un blog Ghost, Medium…)
2. Le système parse le flux et extrait les items (titre, lien, date de publication)
3. Chaque item est soumis comme une URL ordinaire dans le pipeline existant :
   - Item avec `<enclosure>` audio → `download_worker` (podcast)
   - Item avec `<link>` article → `article_extraction_worker`
4. Le système poll le flux périodiquement et ne réingère que les **nouveaux items** (déduplication par URL/guid)
5. L'utilisateur peut gérer ses flux abonnés (liste, pause, suppression)

## Architecture

- **Modèle** : `UserRssFeed` (user_id, feed_url, feed_title, last_polled_at, status, item_guids_seen[])
- **Scheduler** : cron ou SQS delayed message pour le polling périodique (ex: toutes les heures)
- **Resolver** : `RssFeedResolver` qui parse le XML et route chaque item vers le bon worker via le pipeline canonique `ingest-url`
- **Déduplication** : via `media_key` existant (idempotence déjà en place) + tracking des guids vus
- **API** :
  - `POST /api/feeds` — souscrire à un flux
  - `GET /api/feeds` — lister ses flux
  - `DELETE /api/feeds/{feed_id}` — se désabonner
- **Frontend** : section "Mes flux" dans les settings ou dashboard

## Librairie suggérée

`feedparser` (Python) pour le parsing RSS/Atom — mature, zéro dépendance lourde.

## Cas couverts automatiquement

- Substack (chaque Substack a un `/feed` RSS public)
- Medium
- Ghost blogs
- WordPress
- Podcasts RSS (format Apple Podcasts)
- Tout blog avec flux RSS/Atom
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'utilisateur peut soumettre un URL de flux RSS et recevoir la liste des items détectés
- [ ] #2 Chaque item est ingéré via le pipeline canonique existant (article ou audio selon le type)
- [ ] #3 Les items déjà ingérés ne sont pas re-soumis (déduplication par media_key ou guid)
- [ ] #4 Le flux est pollé automatiquement à intervalle régulier (cron/scheduler)
- [ ] #5 L'utilisateur peut lister, mettre en pause et supprimer ses flux abonnés
- [ ] #6 Fonctionne avec Substack, Medium, Ghost et tout flux RSS/Atom standard
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-03-29 : confirmé hors scope V1. Feature post-lancement.
<!-- SECTION:NOTES:END -->
