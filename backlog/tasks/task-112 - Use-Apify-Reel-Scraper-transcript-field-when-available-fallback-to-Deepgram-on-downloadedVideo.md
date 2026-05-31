---
id: task-112
title: >-
  Use Apify Reel Scraper transcript field when available, fallback to Deepgram
  on downloadedVideo
status: Done
assignee: []
created_date: '2026-05-31 21:57'
labels:
  - ingestion
  - instagram
  - feature
  - cost-optimization
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'actor Apify `apify/instagram-reel-scraper` (configuré dans `.env` via `APIFY_INSTAGRAM_REEL_ACTOR_ID`) expose **deux champs utiles** dans son output :

- `transcript` — transcript du reel produit par Apify lui-même.
- `downloadedVideo` — MP4 hébergé par Apify (TTL ~3 jours, plus fiable que le CDN Instagram qui peut expirer ou être bloqué géographiquement).
- `videoUrl` — MP4 direct du CDN Instagram (fallback de second niveau).

Aujourd'hui, `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` retourne uniquement le `downloadedVideo` (ou `videoUrl` en fallback) comme `audio_url`, et l'orchestrator enfile vers Deepgram pour transcription. Le champ `transcript` retourné par Apify est ignoré, alors qu'il pourrait permettre de **bypasser entièrement Deepgram** sur les reels où il est disponible et de qualité acceptable.

## Bénéfice attendu

- **Coût** : économie de la facturation Deepgram (0,003 €/min) sur les reels où Apify fournit déjà le transcript. Apify Reel Scraper coûte $1/1000 reels (paid) ou $2,60/1000 (free) — facturation indépendante du fait qu'on utilise ou non le transcript intégré.
- **Latence** : suppression de l'aller-retour Deepgram pour les reels avec transcript (gain ~15-30 s).
- **Robustesse** : fallback Deepgram via `downloadedVideo` (URL stable 3 jours hébergée par Apify) reste disponible si le transcript est absent, vide, ou trop court pour être exploitable.

## Scope d'implémentation

1. **Resolver** (`media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`) :
   - Pour les reels (path `_resolve_reel`), lire le champ `transcript` du résultat Apify.
   - Si présent et de longueur ≥ seuil minimum (ex. 20 caractères significatifs après strip), populer `ResolvedMedia.raw_text` avec le transcript et **ne pas** fournir `audio_url`.
   - Sinon, conserver le comportement actuel : populer `audio_url` avec `downloadedVideo` ou `videoUrl`.
   - Capturer dans la metadata d'extraction (`extraction_metadata`) le champ choisi : `transcript_source: "apify_native" | "deepgram_pending" | "deepgram_pending_cdn_fallback"`.

2. **Orchestrator** (`media_summarizer/core/media_ingestion/adapters/orchestrators.py`) :
   - Le path `raw_text` pour `MediaFamily.SOCIAL_VIDEO` doit être géré : si `resolved.raw_text` est présent, upload immédiat S3 + mark `transcribing` puis `completed` (cohérent avec le path WhatsApp text déjà câblé pour `MediaFamily.TEXT`).
   - Le path `audio_url` pour `MediaFamily.SOCIAL_VIDEO` reste inchangé (enqueue Deepgram).
   - Vérifier que le minutes hold se finalise correctement dans le path `raw_text` (durée audio probablement disponible via metadata Apify pour estimer les minutes).

3. **Configuration** :
   - Ajouter une env var `INSTAGRAM_TRANSCRIPT_MIN_LENGTH` (défaut 20) pour ne pas accepter un transcript trop court / vide.
   - Ajouter une env var feature flag `INSTAGRAM_USE_APIFY_TRANSCRIPT` (défaut `true`) pour pouvoir désactiver rapidement si problème de qualité observé en prod.

4. **Tests unitaires** (`media_summarizer/tests/test_instagram_apify_resolver.py`) :
   - Reel avec `transcript` long → `ResolvedMedia.raw_text` populé, `audio_url` à `None`.
   - Reel avec `transcript` vide / absent → fallback `audio_url=downloadedVideo`.
   - Reel avec `transcript` trop court (sous seuil) → fallback `audio_url=downloadedVideo`.
   - Reel sans `downloadedVideo` mais avec `videoUrl` → fallback CDN.
   - Feature flag désactivé → `transcript` ignoré même si présent.

5. **Logging** : ajouter un log structuré `instagram.reel.transcript_source` indiquant la voie choisie pour chaque reel résolu.

## Hors-scope

- Évaluer/comparer la qualité du transcript Apify vs Deepgram : ce ticket se contente de l'utiliser quand il est de longueur suffisante. Une éventuelle comparaison qualité/échantillonnage est un follow-up séparé.
- Étendre la logique aux Posts vidéo (carrousels avec une vidéo) : l'actor `apify/instagram-post-scraper` n'expose pas de champ `transcript` selon la doc. Reste sur Deepgram pour ces cas.
- Réécrire les autres connecteurs (TikTok / YouTube) — `apify/instagram-reel-scraper` est le seul à proposer ce champ en V1.

## Vérification

- Soumettre un reel Instagram dont le transcript Apify est non vide → job complet sans appel Deepgram, transcript persisté en S3, log `transcript_source=apify_native`.
- Soumettre un reel Instagram sans transcript Apify → job complet via Deepgram sur `downloadedVideo`, log `transcript_source=deepgram_pending`.
- Soumettre un reel avec `transcript` artificiellement vide (mock) → fallback Deepgram observable.
- Désactiver le feature flag (`INSTAGRAM_USE_APIFY_TRANSCRIPT=false`) → tous les reels passent par Deepgram comme avant.

## Contexte fichiers utiles

- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:118-145` — sélection actuelle de `downloadedVideo` / `videoUrl`.
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:219-238` — classe `InstagramApifyResolver` + injection des actor IDs.
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:238-316` — paths `raw_text` (déjà câblé pour `MediaFamily.TEXT` via WhatsApp) et `audio_url` à étendre pour `MediaFamily.SOCIAL_VIDEO`.
- `media_summarizer/core/media_ingestion/domain.py` — `ResolvedMedia.raw_text` déjà existant.
- `media_summarizer/tests/test_instagram_apify_resolver.py` — tests existants à étendre.
- Doc Apify Reel Scraper : https://apify.com/apify/instagram-reel-scraper
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le resolver Instagram Apify lit le champ transcript du retour de l'actor instagram-reel-scraper et populate ResolvedMedia.raw_text quand il est présent et au-dessus d'un seuil minimum de longueur
- [ ] #2 Quand le transcript Apify est absent, vide, ou sous le seuil, le resolver tombe en fallback sur audio_url = downloadedVideo (ou videoUrl si downloadedVideo absent), comportement actuel préservé
- [ ] #3 L'orchestrator gère le path raw_text pour MediaFamily.SOCIAL_VIDEO : upload S3 immédiat + mark completed sans appel Deepgram, cohérent avec le path existant pour MediaFamily.TEXT
- [ ] #4 Le path audio_url existant pour MediaFamily.SOCIAL_VIDEO reste inchangé (enqueue Deepgram via downloadedVideo)
- [ ] #5 Une env var INSTAGRAM_TRANSCRIPT_MIN_LENGTH (défaut 20) contrôle le seuil de longueur minimum du transcript
- [ ] #6 Une env var feature flag INSTAGRAM_USE_APIFY_TRANSCRIPT (défaut true) permet de désactiver l'usage du transcript Apify et de tout faire passer par Deepgram
- [ ] #7 Tests unitaires couvrent : transcript long valide / transcript vide / transcript sous seuil / pas de downloadedVideo / feature flag désactivé
- [ ] #8 Un log structuré instagram.reel.transcript_source indique la voie choisie (apify_native / deepgram_pending / deepgram_pending_cdn_fallback) pour chaque reel résolu
- [ ] #9 Le minutes hold est correctement finalisé dans le path raw_text (durée estimée via metadata Apify)
- [ ] #10 Les paths Image-only Post + Comments restent inchangés (pas de transcript exposé par ces actors)
- [ ] #11 .env.example documente les deux nouvelles env vars (INSTAGRAM_TRANSCRIPT_MIN_LENGTH, INSTAGRAM_USE_APIFY_TRANSCRIPT)
<!-- AC:END -->
