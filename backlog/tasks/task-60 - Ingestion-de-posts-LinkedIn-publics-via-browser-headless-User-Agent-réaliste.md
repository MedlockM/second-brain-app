---
id: task-60
title: Ingestion de posts LinkedIn publics via browser headless / User-Agent réaliste
status: Done
assignee: []
created_date: '2026-03-19 10:37'
updated_date: '2026-04-28 12:00'
labels:
  - ingestion
  - linkedin
  - benchmark
  - v1
dependencies:
  - task-20
  - task-21
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Ingestion de posts LinkedIn publics (texte uniquement). Images embeddées dans le rendu mais pas analysées. Avant l'implémentation, un **benchmark exhaustif des approches** est requis.

## Étape 1 : Benchmark (recherche internet requise)
Comparer de manière exhaustive les approches pour récupérer le contenu textuel d'un post LinkedIn public :
- Playwright headless browser
- User-Agent réaliste + headers HTTP
- APIs tierces (Proxycurl, PhantomBuster, RapidAPI LinkedIn scrapers, etc.)
- Librairies Python spécialisées (linkedin-api, linkedin-scraper, etc.)
- Extension navigateur / copier-coller comme fallback UX
- API officielle LinkedIn (limites connues)

Pour chaque approche : robustesse, coût, maintenance, risques ToS, qualité du texte extrait.

## Étape 2 : Implémentation
- Resolver : `LinkedInPostResolver` — détecte les URLs `linkedin.com/feed/update/` ou `linkedin.com/posts/`
- Worker dédié ou réutilisation article_extraction_worker avec adapter LinkedIn
- Texte uniquement (pas d'extraction vidéo/image/PDF)
- Déduplication via `media_key` existant

## Risques
- ToS LinkedIn interdit le scraping
- Structure HTML fréquemment mise à jour
- Posts derrière login wall non accessibles
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Benchmark exhaustif des approches documenté avec recommandation argumentée
- [ ] #2 URLs linkedin.com/feed/update/ et linkedin.com/posts/ détectées et routées
- [ ] #3 Texte du post extrait correctement pour les posts publics
- [ ] #4 Erreurs gérées avec message clair (post privé, login wall, structure changée)

- [ ] #5 Solution documentée avec ses limites ToS
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-23: Phase benchmark (AC#1) complétée par agent-task-60. Documents créés: docs/research/task-60/BENCHMARK_UPDATE_2026-04-23.md et README.md. Recommandation: Fallback UX (copier-coller manuel) pour V1 - zéro risque ToS. L'implémentation (AC#2-5) reste à faire. Commit direct sur second-brain-project.

Dispatch 2026-04-28: Implémentation AC#2-5 complétée par agent-task-60. Créé core/resolvers/linkedin.py (LinkedInResolver avec URL validation, error enums, content hashing), tests/unit/core/resolvers/test_linkedin.py (34 unit tests), docs/research/task-60/LINKEDIN_INTEGRATION.md. Modifié api/endpoints/media.py (détection LinkedIn dans _detect_platform, POST /api/media/ingest-shared-content). Merged dans second-brain-project (conflit résolu dans media.py imports).
<!-- SECTION:NOTES:END -->
