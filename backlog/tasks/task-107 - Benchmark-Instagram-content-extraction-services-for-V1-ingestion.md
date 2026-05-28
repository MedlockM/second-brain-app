---
id: task-107
title: Benchmark Instagram content extraction services for V1 ingestion
status: To Do
assignee: []
created_date: '2026-05-28 14:17'
labels:
  - benchmark
  - ingestion
  - research
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'app supporte déjà l'ingestion Instagram via `getinsaver` (cf. task-31 et task-100), mais uniquement pour extraire l'audio/vidéo d'un Reel et le transcrire via Deepgram. Le scope ingestion Instagram doit s'élargir pour V1 :

- **Reels et vidéos** : récupération du fichier média (URL audio/vidéo téléchargeable) à transcrire par Deepgram. **Critère bloquant** — sans ça, la solution est disqualifiée.
- **Posts image-only** (carrousels, photos uniques) : récupération des images en haute résolution pour OCR / analyse visuelle.
- **Caption / texte du post** : récupération du texte rédigé par l'auteur.
- **Commentaires** : récupération de la liste des commentaires (bonus, à pondérer si certains providers le proposent).

L'objectif est de trouver **la meilleure solution possible** pour couvrir ces 4 dimensions de contenu Instagram, en re-questionnant le choix actuel (`getinsaver`) si une alternative est meilleure.

## Axes d'analyse imposés

Le benchmark doit comparer les candidats sur **au minimum** ces axes :

1. **Capacités de contenu** :
   - Reels / vidéos avec URL média téléchargeable utilisable par Deepgram (audio direct ou vidéo téléchargeable que l'on peut démuxer) — **critère bloquant**.
   - Posts images (carrousels et single image) en haute résolution.
   - Caption / texte.
   - Commentaires (avec pagination si applicable).
   - Stories / Highlights (informatif, pas bloquant).
2. **Pricing** :
   - Modèle de tarification (par requête, par crédit, abonnement mensuel, pay-as-you-go).
   - Coût unitaire estimé pour les 4 types de contenu.
   - Projection pour les volumes V1 (à demander au owner si besoin, sinon hypothèse documentée).
3. **Free tier** :
   - Existence et limites (req/jour, req/mois, fonctionnalités bridées ou complètes).
   - Pertinence pour le développement, le QA et le démarrage commercial.
4. **Réputation et fiabilité** :
   - Ancienneté du service, base d'utilisateurs, présence d'avis tiers (G2, Trustpilot, Reddit, GitHub issues).
   - Stabilité face aux changements Instagram (historique d'incidents, fréquence des breakages).
   - Conformité TOS / risque de blocage Meta.
   - Qualité du support et de la documentation.

## Candidats à étudier (non exhaustif, à compléter par l'agent research)

- `getinsaver` (incumbent, baseline à challenger)
- Apify (acteurs Instagram Scraper, Instagram Reel Scraper, Instagram API)
- Bright Data (Instagram Scraper API)
- ScrapingBee / ScraperAPI / SerpApi (si proposent un endpoint Instagram)
- RapidAPI marketplace (Instagram Bulk Profile Scraper, Instagram API, etc.)
- Phyllo, HikerAPI, Instaloader (lib open source self-hosted)
- yt-dlp pour le path Reels/vidéo (alternative open source à comparer en coût d'infra/maintenance)
- Tout autre acteur identifié pendant la recherche

## Livrable attendu

Un dossier `docs/research/task-XX-instagram-extraction-benchmark/` contenant un `README.md` avec front-matter `owner_decision: pending`, structuré ainsi :

- Tableau comparatif multi-providers couvrant les 4 axes ci-dessus.
- Verdict explicite sur le critère bloquant (URL média Reels exploitable par Deepgram) — **éliminer** tout candidat qui échoue ce critère.
- Recommandation finale unique (ou hybride : un provider pour les vidéos, un autre pour images/texte/commentaires si pertinent).
- Estimation de coût mensuel pour V1 (assumptions documentées).
- Plan de migration succinct si la recommandation diffère de `getinsaver`.
- Risques et plan B.

## Hors-scope

- Toute modification de code dans `media_summarizer/` : ce ticket est **research-only**.
- Le choix final est tranché par le owner (cf. `docs/BENCHMARK_OWNER_WORKFLOW.md`).

Acceptance criteria détaillés ci-dessous.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 README de benchmark publié sous docs/research/task-XX-instagram-extraction-benchmark/README.md avec front-matter owner_decision: pending
- [ ] #2 Tableau comparatif inclut au minimum getinsaver, Apify, Bright Data, RapidAPI marketplace, et yt-dlp self-hosted
- [ ] #3 Chaque candidat évalué sur les 4 axes : capacités (Reels/images/caption/commentaires), pricing, free tier, réputation
- [ ] #4 Le critère bloquant 'URL média Reels téléchargeable et exploitable par Deepgram' est tranché explicitement pour chaque candidat (pass/fail)
- [ ] #5 Tout candidat qui échoue le critère bloquant est explicitement éliminé du shortlist
- [ ] #6 Estimation de coût mensuel projetée pour les volumes V1 (avec hypothèses documentées si owner non consulté)
- [ ] #7 Recommandation finale unique (ou combinaison provider vidéo + provider images/texte) argumentée
- [ ] #8 Plan de migration depuis getinsaver fourni si la recommandation diffère de l'incumbent
- [ ] #9 Section 'risques et plan B' identifiant les principaux risques (TOS Meta, breakage, coût) avec mitigation
- [ ] #10 Aucune modification de code dans media_summarizer/ ou ailleurs hors du dossier docs/research/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode: initial** — benchmark produced from scratch.

Benchmark README published at `docs/research/task-107-instagram-extraction-benchmark/README.md` with `owner_decision: pending`.

**Recommendation awaits owner validation.**

Summary of findings:
- Evaluated 7 providers across all 4 required axes (content capabilities, pricing, free tier, reputation)
- Bright Data, HikerAPI, and RapidAPI marketplace eliminated due to failing the blocking criterion (no downloadable Reels video URL) or insufficient documentation to confirm it
- GetInSaver (incumbent) passes Reels extraction but cannot handle image posts, captions, or comments
- **Apify recommended as primary** (Reel Scraper + Post Scraper + Comment Scraper combination) covering all 4 content dimensions with proven downloadable video URLs
- GetInSaver retained as zero-cost Reels fallback
- Estimated V1 cost: $5-29/month on Apify depending on comment extraction needs
- Migration plan and risk mitigation documented
<!-- SECTION:NOTES:END -->
