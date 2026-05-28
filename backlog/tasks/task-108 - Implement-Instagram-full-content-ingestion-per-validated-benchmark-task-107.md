---
id: task-108
title: Implement Instagram full-content ingestion per validated benchmark (task-107)
status: To Do
assignee: []
created_date: '2026-05-28 14:18'
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

Le connecteur Instagram actuel (cf. task-31, task-100) n'extrait que l'audio des Reels via `getinsaver` pour Deepgram. Il faut élargir l'ingestion Instagram pour couvrir tous les types de contenu pertinents pour V1 :

- Reels et vidéos → URL média transcrite par Deepgram (déjà en place, à conserver ou migrer selon la recommandation).
- Posts images (carrousels et single image) → récupération haute résolution + OCR / analyse visuelle.
- Caption / texte du post → indexation et exploitation comme contenu textuel.
- Commentaires → si la solution choisie le permet.

## Référence d'architecture

**Avant toute implémentation**, lire `docs/research/task-107-instagram-extraction-benchmark/README.md` et appliquer **strictement** la décision du owner consignée dans la section `Owner Validation` du front-matter (`Decision`, `Validated at`).

Si la décision référence des fichiers `complement-response-*.md` dans le même dossier, les lire aussi pour comprendre les nuances retenues. La main `README.md` reste la source de vérité — les recommandations initiales de l'agent research peuvent avoir été infléchies par le owner.

## Scope d'implémentation (à dériver de la décision)

Selon la décision du owner, ce ticket peut couvrir tout ou partie de :

1. Migration ou conservation du provider Reels/vidéo actuel (`getinsaver` ou remplaçant).
2. Ajout d'un path Instagram-image dans le pipeline d'ingestion (orchestrator dispatch + worker dédié si nécessaire).
3. Ajout de l'extraction caption / texte avec persistence dans le modèle media adéquat.
4. Ajout de l'extraction commentaires si la décision le retient (sinon documenter pourquoi c'est exclu).
5. Mise à jour des configurations runtime (env vars, secrets) et des docs ingestion.
6. Tests unitaires couvrant les nouveaux paths de dispatch et la résolution provider.

## Hors-scope

- Re-débattre du choix de provider : la décision est figée dans le README validé.
- Étendre à d'autres réseaux sociaux (TikTok, X) : ce ticket est Instagram only.

## Validation

- Soumission d'une URL Reel → transcription Deepgram → completed (path existant maintenu ou amélioré).
- Soumission d'une URL post image → ingestion image complète (OCR ou analyse selon décision) → completed.
- Soumission d'une URL post avec caption → caption persistée et exploitable côté search/artifacts.
- Si commentaires retenus : soumission d'un post → commentaires récupérés et persistés.

Acceptance criteria détaillés ci-dessous.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'implementation suit strictement la décision documentée dans docs/research/task-107-instagram-extraction-benchmark/README.md (section Owner Validation)
- [ ] #2 Le path Reels/vidéo continue de fournir une transcription Deepgram fonctionnelle de bout en bout (pending → completed)
- [ ] #3 Les posts image-only (single + carrousel) sont ingestionnés avec récupération haute résolution et traités par le pipeline visuel/OCR pertinent
- [ ] #4 La caption/texte du post est extraite et persistée de manière exploitable par le pipeline d'artifacts et de recherche
- [ ] #5 Si la décision retient les commentaires : ils sont récupérés et persistés ; sinon une note explique l'exclusion
- [ ] #6 Les nouvelles dépendances de configuration (env vars, secrets) sont propagées dans .env.example et la doc runtime
- [ ] #7 Tests unitaires couvrent chaque nouveau path de dispatch dans l'orchestrator et chaque nouvelle résolution provider
- [ ] #8 Documentation ingestion (docs/ARCHITECTURE ou équivalent) mise à jour pour refléter le nouveau scope Instagram
- [ ] #9 Les paths X et TikTok existants restent inchangés et fonctionnels
- [ ] #10 Si migration depuis getinsaver : ancien code retiré ou marqué déprécié selon le plan de migration du README
<!-- AC:END -->
