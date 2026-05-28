---
id: task-108
title: Implement Instagram full-content ingestion per validated benchmark (task-107)
status: To Do
assignee: []
created_date: '2026-05-28 14:18'
updated_date: '2026-05-28 16:41'
labels:
  - ingestion
  - instagram
dependencies:
  - task-107
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le connecteur Instagram actuel (cf. task-31, task-100) n'extrait que l'audio des Reels via `getinsaver` pour Deepgram. Suite au benchmark task-107 et à la décision owner du 2026-05-28, on **remplace intégralement** `getinsaver` par Apify et on étend le scope d'ingestion Instagram pour couvrir tous les types de contenu pertinents pour V1 :

- **Reels et vidéos** → Apify Instagram Reel Scraper → URL média (`downloadedVideo` ou `videoUrl`) → Deepgram.
- **Posts images** (carrousels et single image) → Apify Instagram Post Scraper → URLs haute résolution (`displayUrl`, `images`, `childPosts`) → pipeline visuel/OCR.
- **Caption / texte** → champ `caption` retourné par les scrapers Apify → indexation et exploitation comme contenu textuel.
- **Commentaires** → Apify Instagram Comment Scraper → persistence avec pagination.

## Référence d'architecture

**Avant toute implémentation**, lire `docs/research/task-107-instagram-extraction-benchmark/README.md` et appliquer **strictement** la décision du owner consignée dans la section `Owner Validation` du front-matter.

Décision retenue (résumé) : Apify devient le **provider unique** pour Instagram en V1. **`getinsaver` est intégralement retiré** (code adapter, env vars `GETINSAVER_*`, mentions doc) — **pas de fallback conservé**. L'archi hexagonale permettra de réintroduire un adapter fallback plus tard si nécessaire ; ce n'est pas le scope de V1.

## Scope d'implémentation

1. Créer un nouvel adapter Apify (`InstagramApifyResolver` ou équivalent) qui orchestre les 3 acteurs Apify (Reel Scraper, Post Scraper, Comment Scraper) selon le type de contenu détecté (reel / post / carousel / igtv).
2. Câbler l'orchestrator pour dispatcher : Reels → Deepgram (path existant), images → pipeline visuel/OCR (nouveau dispatch), caption → persistence textuelle, commentaires → persistence.
3. Retirer intégralement l'adapter `getinsaver` : code dans `media_summarizer/core/media_ingestion/adapters/resolvers.py`, références dans `api/endpoints/media.py`, env vars `GETINSAVER_*` dans `.env.example`, mentions dans la doc (`docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`, `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`, `docs/V1_LAUNCH_PLAN.md`, `docs/LOGGING_SYSTEM.md`, `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`), champ scrub list logging (`getinsaver_api_key`).
4. Ajouter les nouvelles env vars Apify (token, IDs des actors, timeouts) dans `.env.example` et la doc runtime.
5. Tests unitaires couvrant chaque path de dispatch (reel, image-only post, carousel, caption, comments) et la résolution provider Apify.
6. Mise à jour des docs ingestion pour refléter le nouveau scope Instagram et le retrait de `getinsaver`.

## Hors-scope

- Ré-introduire un fallback Reels (la décision owner exclut explicitement de garder `getinsaver`).
- Re-débattre du choix de provider : la décision est figée dans le README validé.
- Étendre à d'autres réseaux sociaux (TikTok, X) : ce ticket est Instagram only.

## Validation

- Soumission d'une URL Reel → résolution Apify → transcription Deepgram → completed.
- Soumission d'une URL post image (single + carrousel) → ingestion image complète → pipeline visuel/OCR → completed.
- Soumission d'une URL post avec caption → caption persistée et exploitable côté search/artifacts.
- Soumission d'un post → commentaires récupérés et persistés.
- `grep -ri "getinsaver" media_summarizer/ docs/ .env.example` ne renvoie plus aucun résultat (sauf éventuellement dans `docs/research/task-107-instagram-extraction-benchmark/` qui est historique).

Acceptance criteria détaillés ci-dessous.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'implementation suit strictement la décision documentée dans docs/research/task-107-instagram-extraction-benchmark/README.md (section Owner Validation) : Apify provider unique, getinsaver retiré sans fallback
- [ ] #2 Un nouvel adapter Apify est créé et orchestre les 3 acteurs (Reel Scraper, Post Scraper, Comment Scraper) selon le type de contenu détecté
- [ ] #3 Le path Reels/vidéo fournit une transcription Deepgram fonctionnelle de bout en bout (pending → completed) via Apify
- [ ] #4 Les posts image-only (single + carrousel) sont ingestionnés avec récupération haute résolution et traités par le pipeline visuel/OCR pertinent
- [ ] #5 La caption/texte du post est extraite et persistée de manière exploitable par le pipeline d'artifacts et de recherche
- [ ] #6 Les commentaires sont récupérés via Apify Comment Scraper et persistés avec pagination
- [ ] #7 L'adapter getinsaver est intégralement retiré du code (resolvers.py, api/endpoints/media.py, scrub list logging) sans laisser de stub ni de mention conditionnelle
- [ ] #8 Les env vars GETINSAVER_* sont supprimées de .env.example et toutes les docs (MEDIA_INGESTION_CORE_ARCHITECTURE, MOBILE_APP_IMPLEMENTATION_PLAN, V1_LAUNCH_PLAN, LOGGING_SYSTEM, ADR social-video)
- [ ] #9 Les nouvelles env vars Apify (token, actor IDs, timeouts) sont propagées dans .env.example et la doc runtime
- [ ] #10 Tests unitaires couvrent chaque path de dispatch (reel, image-only, carousel, caption, comments) et la résolution Apify

- [ ] #11 Documentation ingestion (docs/ARCHITECTURE ou équivalent) mise à jour pour refléter le nouveau scope Instagram et le retrait de getinsaver
- [ ] #12 Les paths X et TikTok existants restent inchangés et fonctionnels
- [ ] #13 grep -ri 'getinsaver' media_summarizer/ docs/ .env.example ne renvoie plus aucun résultat hors du dossier docs/research/task-107-instagram-extraction-benchmark/
<!-- AC:END -->
