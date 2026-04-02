# Benchmark des coûts unitaires et proposition de pricing V1

> **Date** : 2 avril 2026
> **Contexte** : App "second brain" média -- l'utilisateur partage une URL (podcast, article, vidéo YouTube, PDF, etc.) et l'app génère des artefacts (transcription, résumé court, résumé détaillé, flashcards).
> **Contrainte prix** : maximum 9 €/mois

---

## Table des matières

1. [Coûts unitaires des services](#1-coûts-unitaires-des-services)
   - [1.1 Transcription audio (Speech-to-Text)](#11-transcription-audio-speech-to-text)
   - [1.2 LLM pour génération d'artefacts](#12-llm-pour-génération-dartefacts)
   - [1.3 OCR (images et PDF scannés)](#13-ocr-images-et-pdf-scannés)
   - [1.4 Stockage et base de données](#14-stockage-et-base-de-données)
   - [1.5 File de messages (SQS)](#15-file-de-messages-sqs)
   - [1.6 Compute (serveurs)](#16-compute-serveurs)
2. [Estimation du coût par artefact](#2-estimation-du-coût-par-artefact)
3. [Personas et profils d'utilisation](#3-personas-et-profils-dutilisation)
4. [Coût mensuel par persona](#4-coût-mensuel-par-persona)
5. [Analyse de la concurrence](#5-analyse-de-la-concurrence)
6. [Options de pricing proposées](#6-options-de-pricing-proposées)
7. [Recommandation finale](#7-recommandation-finale)

---

## 1. Coûts unitaires des services

### 1.1 Transcription audio (Speech-to-Text)

| Service | Modèle | Prix/minute | Prix/heure | Notes |
|---------|--------|-------------|------------|-------|
| **Deepgram** | Nova-3 (multilingue) | $0,0092 | $0,552 | Facturation à la seconde, pas d'arrondi |
| **Deepgram** | Nova-2 | $0,0058 | $0,348 | Modèle précédent, encore disponible |
| **Deepgram** | Nova-3 (Growth plan) | $0,0078 | $0,468 | À partir de $4K/an prépayé |
| **AssemblyAI** | Universal-3 Pro | -- | $0,21 | Modèle phare, facturation à l'heure |
| **AssemblyAI** | Universal-2 | -- | $0,15 | Modèle précédent |
| **OpenAI** | Whisper-1 | ~$0,006 | ~$0,36 | $0,006/min estimé (basé sur $0,10/seconde pour l'embedding audio) |

**Sources** :
- [Deepgram Pricing](https://deepgram.com/pricing) (consulté le 02/04/2026)
- [AssemblyAI Pricing](https://www.assemblyai.com/pricing) (consulté le 02/04/2026)
- [OpenAI Whisper pricing](https://docsbot.ai/tools/gpt-openai-api-pricing-calculator) (consulté le 02/04/2026)

**Choix recommandé** : **Deepgram Nova-3 multilingue** à $0,0092/min. C'est le meilleur rapport qualité/prix pour du multilingue (français + anglais). La facturation à la seconde est un avantage pour les podcasts de durée variable. Le free tier de $200 (≈ 21 700 minutes) permet de démarrer sans coût initial.

### 1.2 LLM pour génération d'artefacts

#### Prix par million de tokens (MTok) -- Avril 2026

| Fournisseur | Modèle | Input $/MTok | Output $/MTok | Qualité | Cas d'usage recommandé |
|-------------|--------|-------------|--------------|---------|----------------------|
| **OpenAI** | GPT-4.1 nano | $0,10 | $0,40 | Bonne | Résumé court, flashcards simples |
| **OpenAI** | GPT-4.1 mini | $0,40 | $1,60 | Très bonne | Résumé détaillé, flashcards complexes |
| **OpenAI** | GPT-4.1 | $2,00 | $8,00 | Excellente | Tâches complexes de synthèse |
| **OpenAI** | GPT-4o mini | $0,15 | $0,60 | Bonne | Alternative économique |
| **OpenAI** | GPT-4o | $2,50 | $10,00 | Excellente | Tâches premium |
| **OpenAI** | o4-mini | $1,10 | $4,40 | Très bonne (reasoning) | Raisonnement avancé |
| **Anthropic** | Claude Haiku 4.5 | $1,00 | $5,00 | Très bonne | Bon généraliste rapide |
| **Anthropic** | Claude Sonnet 4.6 | $3,00 | $15,00 | Excellente | Tâches complexes |
| **Anthropic** | Claude Opus 4.6 | $5,00 | $25,00 | Supérieure | Top qualité, coûteux |
| **Google** | Gemini 2.5 Flash | $0,30 | $2,50 | Très bonne | Excellent rapport qualité/prix |
| **Google** | Gemini 2.5 Pro | $1,25 | $10,00 | Excellente | Tâches complexes |
| **Google** | Gemini 3 Flash Preview | $0,50 | $3,00 | Très bonne | Dernière génération |
| **Google** | Gemini 3.1 Flash-Lite | $0,25 | $1,50 | Bonne | Le plus économique chez Google |
| **Mistral** | Mistral Small 3 | $0,10 | $0,30 | Correcte | Ultra économique |
| **Mistral** | Mistral Medium (latest) | $0,40 | $2,00 | Bonne | Bon rapport qualité/prix |
| **Mistral** | Mistral Large (latest) | $2,00 | $6,00 | Très bonne | Tâches complexes |
| **Mistral** | Codestral | $1,00 | $3,00 | Bonne (code) | Spécialisé code |

**Sources** :
- [Anthropic Models Documentation](https://platform.claude.com/docs/en/docs/about-claude/models) (consulté le 02/04/2026)
- [OpenAI Pricing via DocsBot](https://docsbot.ai/tools/gpt-openai-api-pricing-calculator) (consulté le 02/04/2026)
- [Google AI Pricing](https://ai.google.dev/pricing) (consulté le 02/04/2026)
- [Mistral Models via tokencost](https://github.com/AgentOps-AI/tokencost/blob/main/tokencost/model_prices.json) (consulté le 02/04/2026)

**Stratégie recommandée** : Utiliser un **modèle économique pour les tâches simples** (résumé court, flashcards) et un **modèle plus puissant pour les tâches complexes** (résumé détaillé). Candidats optimaux :

- **Résumé court + flashcards** : GPT-4.1 nano ($0,10/$0,40) ou Gemini 2.5 Flash ($0,30/$2,50) ou Mistral Small 3 ($0,10/$0,30)
- **Résumé détaillé** : GPT-4.1 mini ($0,40/$1,60) ou Gemini 2.5 Flash ($0,30/$2,50)

### 1.3 OCR (images et PDF scannés)

| Service | Prix/1000 pages | Prix/page | Free tier |
|---------|----------------|-----------|-----------|
| **Google Cloud Vision** (Text Detection) | $1,50 | $0,0015 | 1 000 unités/mois gratuites |
| **Google Document AI** (Enterprise OCR) | $1,50 | $0,0015 | Pas de free tier dédié |
| **LLM Vision** (GPT-4o / Gemini) | Variable | ~$0,01-0,05 | Inclus dans le coût LLM |

**Sources** :
- [Google Cloud Vision Pricing](https://cloud.google.com/vision/pricing) (consulté le 02/04/2026)
- [Google Document AI Pricing](https://cloud.google.com/document-ai/pricing) (consulté le 02/04/2026)

**Choix recommandé** : **Google Cloud Vision OCR** à $0,0015/page. Le free tier de 1000 unités/mois couvre largement un usage modéré. Pour les PDFs complexes, une approche hybride avec le modèle vision d'un LLM peut être envisagée.

### 1.4 Stockage et base de données

#### AWS S3 (stockage fichiers)

| Ressource | Prix | Notes |
|-----------|------|-------|
| S3 Standard stockage | ~$0,023/GB/mois | us-east-1 |
| PUT/COPY/POST/LIST requests | $0,005/1000 requêtes | |
| GET/SELECT requests | $0,0004/1000 requêtes | |
| Free tier | 5 GB + 2000 PUT + 20 000 GET/mois | 12 premiers mois |

#### AWS DynamoDB (base de données)

| Ressource | Prix (on-demand) | Notes |
|-----------|-----------------|-------|
| Écriture (WRU) | ~$1,25/million | us-east-1 |
| Lecture (RRU) | ~$0,25/million | us-east-1 |
| Stockage | ~$0,25/GB/mois | |
| Free tier | 25 GB + 25 WRU + 25 RRU/s | Permanent |

**Sources** :
- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/) (consulté le 02/04/2026)
- [AWS DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/on-demand/) (consulté le 02/04/2026)

> Note : Les prix exacts pour eu-west-1 sont légèrement supérieurs (~5-10%) mais dans le même ordre de grandeur. Les valeurs ci-dessus sont des estimations basées sur la documentation AWS et les prix standards connus.

### 1.5 File de messages (SQS)

| Ressource | Prix | Notes |
|-----------|------|-------|
| Standard Queue | ~$0,40/million de requêtes | us-east-1 |
| FIFO Queue | ~$0,50/million de requêtes | us-east-1 |
| Free tier | 1 million requêtes/mois | Permanent |

**Source** : [AWS SQS Pricing](https://aws.amazon.com/sqs/pricing/) (consulté le 02/04/2026)

### 1.6 Compute (serveurs)

#### Option 1 : AWS Fargate (ECS)

| Ressource | Prix | Équivalent mensuel (24/7) |
|-----------|------|--------------------------|
| vCPU | $0,04048/heure | ~$29,15/mois |
| Mémoire | $0,004445/GB/heure | ~$3,20/mois par GB |
| ARM (Graviton) vCPU | $0,03238/heure | ~$23,31/mois |
| ARM Mémoire | $0,00356/GB/heure | ~$2,56/mois par GB |

Config minimale API (0.25 vCPU, 0.5 GB) : ~$8,90/mois (x86) ou ~$7,10/mois (ARM)

**Source** : [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/) (consulté le 02/04/2026)

#### Option 2 : Railway

| Ressource | Prix |
|-----------|------|
| vCPU | $0,0278/heure (~$20/mois) |
| Mémoire | $0,0139/GB/heure (~$10/mois par GB) |
| Plan Hobby | $5/mois (inclus $5 de crédit) |
| Plan Pro | $20/mois (inclus $20 de crédit) |
| Free trial | $5 de crédit sur 30 jours |

**Source** : [Railway Pricing](https://railway.com/pricing) (consulté le 02/04/2026)

#### Option 3 : Fly.io

| Ressource | Prix |
|-----------|------|
| shared-cpu-1x, 256MB | $0,0028/heure (~$2/mois) |
| performance-1x, 2GB | $0,0447/heure (~$32/mois) |
| RAM additionnel | ~$5/mois par GB |

**Source** : [Fly.io Pricing](https://fly.io/docs/about/pricing/) (consulté le 02/04/2026)

---

## 2. Estimation du coût par artefact

### Hypothèses de tokenisation

Pour un podcast de 60 minutes :
- Transcription brute : ~15 000 mots ≈ **20 000 tokens**
- Résumé court (output) : ~300 mots ≈ **400 tokens**
- Résumé détaillé (output) : ~2 000 mots ≈ **2 700 tokens**
- Flashcards x10 (output) : ~1 000 mots ≈ **1 300 tokens**

Pour un article web (~2 000 mots) :
- Texte extrait : ~2 000 mots ≈ **2 700 tokens**
- Résumé court (output) : ~200 mots ≈ **270 tokens**
- Résumé détaillé (output) : ~1 000 mots ≈ **1 350 tokens**
- Flashcards x5 (output) : ~500 mots ≈ **670 tokens**

Pour une vidéo YouTube de 15 minutes :
- Transcription : ~3 750 mots ≈ **5 000 tokens**
- Résumé court (output) : ~200 mots ≈ **270 tokens**
- Résumé détaillé (output) : ~1 000 mots ≈ **1 350 tokens**
- Flashcards x5 (output) : ~500 mots ≈ **670 tokens**

Pour un PDF scanné de 10 pages :
- OCR : 10 pages
- Texte extrait : ~5 000 mots ≈ **6 700 tokens**
- Artefacts LLM : similaires au podcast court

### Coût par média complet (tous artefacts)

Avec **GPT-4.1 nano** (résumé court + flashcards) + **GPT-4.1 mini** (résumé détaillé) :

#### Podcast 60 min

| Étape | Calcul | Coût |
|-------|--------|------|
| Transcription (Deepgram Nova-3 multilingue) | 60 min × $0,0092 | $0,552 |
| Résumé court (GPT-4.1 nano) | Input: 20K tok × $0,10/MTok + Output: 400 tok × $0,40/MTok | $0,002 + $0,0002 = $0,0022 |
| Résumé détaillé (GPT-4.1 mini) | Input: 20K tok × $0,40/MTok + Output: 2,7K tok × $1,60/MTok | $0,008 + $0,0043 = $0,0123 |
| Flashcards (GPT-4.1 nano) | Input: 20K tok × $0,10/MTok + Output: 1,3K tok × $0,40/MTok | $0,002 + $0,0005 = $0,0025 |
| **Total** | | **$0,569** |

#### Article web (2 000 mots)

| Étape | Calcul | Coût |
|-------|--------|------|
| Extraction texte | Scraping (gratuit) | $0,000 |
| Résumé court (GPT-4.1 nano) | Input: 2,7K × $0,10/MTok + Output: 270 × $0,40/MTok | $0,0003 + $0,0001 = $0,0004 |
| Résumé détaillé (GPT-4.1 mini) | Input: 2,7K × $0,40/MTok + Output: 1,35K × $1,60/MTok | $0,0011 + $0,0022 = $0,0033 |
| Flashcards (GPT-4.1 nano) | Input: 2,7K × $0,10/MTok + Output: 670 × $0,40/MTok | $0,0003 + $0,0003 = $0,0006 |
| **Total** | | **$0,004** |

#### Vidéo YouTube 15 min

| Étape | Calcul | Coût |
|-------|--------|------|
| Transcription (Deepgram Nova-3) | 15 min × $0,0092 | $0,138 |
| Résumé court (GPT-4.1 nano) | Input: 5K × $0,10/MTok + Output: 270 × $0,40/MTok | $0,0005 + $0,0001 = $0,0006 |
| Résumé détaillé (GPT-4.1 mini) | Input: 5K × $0,40/MTok + Output: 1,35K × $1,60/MTok | $0,002 + $0,0022 = $0,0042 |
| Flashcards (GPT-4.1 nano) | Input: 5K × $0,10/MTok + Output: 670 × $0,40/MTok | $0,0005 + $0,0003 = $0,0008 |
| **Total** | | **$0,143** |

#### PDF scanné 10 pages

| Étape | Calcul | Coût |
|-------|--------|------|
| OCR (Google Vision) | 10 pages × $0,0015 | $0,015 |
| Résumé court (GPT-4.1 nano) | Input: 6,7K × $0,10/MTok + Output: 270 × $0,40/MTok | $0,0007 + $0,0001 = $0,0008 |
| Résumé détaillé (GPT-4.1 mini) | Input: 6,7K × $0,40/MTok + Output: 1,35K × $1,60/MTok | $0,0027 + $0,0022 = $0,0049 |
| Flashcards (GPT-4.1 nano) | Input: 6,7K × $0,10/MTok + Output: 670 × $0,40/MTok | $0,0007 + $0,0003 = $0,001 |
| **Total** | | **$0,022** |

### Résumé des coûts par type de média

| Type de média | Coût moyen par média |
|--------------|---------------------|
| Podcast 60 min | $0,57 |
| Podcast 30 min | $0,29 |
| Vidéo YouTube 15 min | $0,14 |
| Article web | $0,004 |
| PDF scanné 10 pages | $0,02 |
| Tweet / post LinkedIn | ~$0,001 |

> **Observation clé** : Le coût est très fortement dominé par la **transcription audio**. Les coûts LLM sont négligeables en comparaison. Le contenu textuel (articles, tweets) coûte quasi rien.

---

## 3. Personas et profils d'utilisation

### Persona 1 : Étudiant ("Léa")

- **Profil** : Étudiante en master, utilise l'app pour organiser ses cours et ses lectures
- **Utilisation mensuelle** :
  - 4 podcasts éducatifs (~45 min chacun)
  - 8 vidéos YouTube (~15 min chacune)
  - 15 articles web
  - 5 PDFs (cours, slides)
- **Volume audio** : ~180 min de podcasts + ~120 min de vidéos = **300 min audio/mois**
- **Total médias** : ~32 médias/mois

### Persona 2 : Professionnel en veille ("Thomas")

- **Profil** : Product manager, fait de la veille technologique et business
- **Utilisation mensuelle** :
  - 8 podcasts (~60 min chacun)
  - 5 vidéos YouTube (~20 min chacune)
  - 25 articles web
  - 3 PDFs (rapports)
- **Volume audio** : ~480 min de podcasts + ~100 min de vidéos = **580 min audio/mois**
- **Total médias** : ~41 médias/mois

### Persona 3 : Power User ("Sofia")

- **Profil** : Entrepreneuse, consommatrice compulsive de contenus, veille sur 5+ domaines
- **Utilisation mensuelle** :
  - 20 podcasts (~60 min chacun)
  - 15 vidéos YouTube (~20 min chacune)
  - 50 articles web
  - 10 PDFs
  - 20 tweets/posts LinkedIn
- **Volume audio** : ~1 200 min de podcasts + ~300 min de vidéos = **1 500 min audio/mois**
- **Total médias** : ~115 médias/mois

---

## 4. Coût mensuel par persona

### Détail du calcul

#### Léa (Étudiante)

| Poste | Calcul | Coût |
|-------|--------|------|
| Transcription podcasts | 180 min × $0,0092 | $1,66 |
| Transcription vidéos | 120 min × $0,0092 | $1,10 |
| LLM (résumés + flashcards) pour audio | 12 médias audio × ~$0,017 | $0,20 |
| LLM articles | 15 × $0,004 | $0,06 |
| LLM PDFs | 5 × $0,007 (5 pages moy.) | $0,04 |
| OCR PDFs | 25 pages × $0,0015 | $0,04 |
| **Total variable** | | **$3,10** |

#### Thomas (Professionnel veille)

| Poste | Calcul | Coût |
|-------|--------|------|
| Transcription podcasts | 480 min × $0,0092 | $4,42 |
| Transcription vidéos | 100 min × $0,0092 | $0,92 |
| LLM audio | 13 médias × ~$0,017 | $0,22 |
| LLM articles | 25 × $0,004 | $0,10 |
| LLM PDFs | 3 × $0,007 | $0,02 |
| OCR PDFs | 15 pages × $0,0015 | $0,02 |
| **Total variable** | | **$5,70** |

#### Sofia (Power User)

| Poste | Calcul | Coût |
|-------|--------|------|
| Transcription podcasts | 1 200 min × $0,0092 | $11,04 |
| Transcription vidéos | 300 min × $0,0092 | $2,76 |
| LLM audio | 35 médias × ~$0,017 | $0,60 |
| LLM articles | 50 × $0,004 | $0,20 |
| LLM PDFs | 10 × $0,007 | $0,07 |
| LLM tweets/LinkedIn | 20 × $0,001 | $0,02 |
| OCR PDFs | 50 pages × $0,0015 | $0,08 |
| **Total variable** | | **$14,77** |

### Coûts fixes (infrastructure)

| Poste | Estimation mensuelle | Notes |
|-------|---------------------|-------|
| Compute (API + workers) | $10-30 | 1 service API + workers async, mutualisé |
| DynamoDB | $1-5 | On-demand, dépend du nombre d'utilisateurs |
| S3 | $0,50-2 | Stockage transcripts et métadonnées |
| SQS | ~$0 | Couvert par le free tier pour longtemps |
| **Total fixe** | **$12-37/mois** | Pour les premiers 100-500 utilisateurs |

**Coût fixe par utilisateur** (amorti sur N utilisateurs) :

| Nb utilisateurs | Coût fixe/user/mois |
|-----------------|-------------------|
| 50 | $0,24-0,74 |
| 100 | $0,12-0,37 |
| 500 | $0,02-0,07 |
| 1 000 | $0,01-0,04 |

> Les coûts fixes deviennent négligeables dès ~100 utilisateurs. Le coût est **dominé par les coûts variables** (transcription + LLM).

### Récapitulatif des coûts par persona

| Persona | Coût variable | Coût fixe (100 users) | **Coût total** |
|---------|--------------|----------------------|----------------|
| Léa (étudiante) | $3,10 | ~$0,25 | **~$3,35** |
| Thomas (pro veille) | $5,70 | ~$0,25 | **~$5,95** |
| Sofia (power user) | $14,77 | ~$0,25 | **~$15,02** |

---

## 5. Analyse de la concurrence

### Concurrents directs et adjacents

| Produit | Prix | Modèle | Positionnement |
|---------|------|--------|---------------|
| **Readwise Reader** | $12,99/mois ($9,99/mois annuel) | Abonnement unique | Read-it-later + highlights + export Notion/Obsidian |
| **Readwise Lite** | $6,99/mois ($5,59/mois annuel) | Abonnement unique | Highlights uniquement, sans Reader |
| **Snipd** | $6,99/mois | Freemium | Podcasts uniquement, 2 épisodes IA/semaine en free |
| **Recall AI** | $7/mois (free tier limité) | Freemium | Second brain, résumés + knowledge graph |
| **Castmagic** | $29/mois ($21 annuel) | Abonnement | Podcasts, 5h transcription/mois au tier bas |
| **Shortform** | $24/mois ($16,42 annuel) | Abonnement | Résumés de livres uniquement, pas d'import perso |
| **Google NotebookLM** | Gratuit (Plus via Google One AI Premium ~$20/mois) | Freemium | Upload de docs, génération de podcasts IA |
| **Perplexity Pro** | ~$20/mois | Abonnement | Moteur de recherche IA, pas de second brain |

**Sources** :
- [Readwise Pricing](https://readwise.io/pricing) (consulté le 02/04/2026)
- [Snipd Pricing](https://www.snipd.com/pricing) (consulté le 02/04/2026)
- [Recall AI Pricing](https://www.getrecall.ai/pricing) (consulté le 02/04/2026)
- [Castmagic Pricing](https://www.castmagic.io/pricing) (consulté le 02/04/2026)
- [Shortform Pricing](https://www.shortform.com/pricing) (consulté le 02/04/2026)

### Positionnement prix du marché

- **Entrée de gamme** (free / <$7/mois) : Snipd free, Recall Lite, Readwise Lite
- **Milieu de gamme** ($7-13/mois) : Snipd Premium, Recall Plus, Readwise Full
- **Haut de gamme** (>$15/mois) : Castmagic, Shortform, NotebookLM Plus, Perplexity Pro

Notre contrainte de **9 €/mois maximum** nous positionne dans le **milieu de gamme**, au-dessus de Snipd/Recall mais en-dessous de Readwise Full.

### Différenciateurs de notre app

- **Multi-média universel** : podcasts + vidéos + articles + PDFs + tweets + LinkedIn (vs. Snipd = podcasts only, Readwise = texte surtout)
- **Artefacts structurés** : transcription + résumé court + résumé détaillé + flashcards avec spaced repetition
- **Organisation à la Raindrop.io** : dossiers imbriqués + tags
- **Digest in-app** : daily + weekly

---

## 6. Options de pricing proposées

### Option A : Abonnement unique à 7,99 €/mois

| | Détails |
|---|---------|
| **Prix** | 7,99 €/mois (≈ $8,70) |
| **Essai** | 1 mois gratuit |
| **Limites** | Aucune limite artificielle, usage "raisonnable" |
| **Fair use** | 800 min audio/mois (~13h), 100 médias texte/mois |

**Avantages** :
- Simple à comprendre, pas de friction
- Couvre le profil étudiant ($3,35) et pro ($5,95) avec marge confortable
- Le mois gratuit permet de tester sans engagement
- Aligné avec le prix de Recall ($7/mois) et Snipd ($6,99/mois)

**Inconvénients** :
- Le power user ($15,02 de coût) n'est pas rentable
- Pas de revenus du free tier pour l'acquisition
- Risque d'abus sans limite dure

**Marge estimée** :
- Étudiant : 7,99 € - 3,35 $ ≈ +$5,35 (63% de marge)
- Pro veille : 7,99 € - 5,95 $ ≈ +$2,75 (32% de marge)
- Power user : 7,99 € - 15,02 $ = **-$6,32** (perte)

---

### Option B : Freemium + Premium à 8,99 €/mois

| Tier | Prix | Limites |
|------|------|---------|
| **Free** | 0 € | 5 médias/mois, résumé court seulement, pas de flashcards, pas de digest |
| **Premium** | 8,99 €/mois (≈ $9,80) | 60 médias/mois, 600 min audio/mois, tous artefacts, digest, spaced repetition |

**Avantages** :
- Free tier pour l'acquisition et la viralité (partage d'un résumé = publicité)
- Le Premium couvre étudiant et pro avec bonne marge
- Le plafond de 600 min audio protège contre les power users extrêmes
- Ancrage psychologique : le free tier rend le premium désirable

**Inconvénients** :
- Plus complexe à communiquer
- Le free tier a un coût serveur même sans revenus
- 600 min audio peut frustrer le pro actif (Thomas est à 580 min)

**Marge estimée** :
- Free user (5 médias) : coût ~$0,30 → perte acceptable pour acquisition
- Étudiant : 8,99 € - $3,35 ≈ +$6,45 (66% de marge)
- Pro veille : 8,99 € - $5,70 ≈ +$4,10 (42% de marge)
- Power user (plafonné) : 8,99 € - $7,50 ≈ +$2,30 (24% de marge, grâce au plafond)

---

### Option C : Deux tiers payants + Free

| Tier | Prix | Limites |
|------|------|---------|
| **Free** | 0 € | 3 médias/mois, résumé court seulement |
| **Standard** | 4,99 €/mois (≈ $5,45) | 30 médias/mois, 300 min audio/mois, tous artefacts |
| **Pro** | 8,99 €/mois (≈ $9,80) | 100 médias/mois, 1 000 min audio/mois, tous artefacts, priorité de traitement |

**Avantages** :
- Point d'entrée bas pour l'étudiant ($4,99 = très compétitif)
- Le tier Pro capture les professionnels avec une marge correcte
- Le free tier sert l'acquisition
- Upsell naturel : Free → Standard → Pro

**Inconvénients** :
- Complexité : 3 tiers à gérer (backend, frontend, support)
- Le Standard à $4,99 a une marge serrée si l'étudiant consomme beaucoup d'audio
- Le Pro à $8,99 ne couvre toujours pas le power user extrême

**Marge estimée** :
- Free user : coût ~$0,15 → perte minime
- Étudiant (Standard) : 4,99 € - $3,10 ≈ +$2,35 (43% de marge)
- Pro veille (Pro) : 8,99 € - $5,70 ≈ +$4,10 (42% de marge)
- Power user (Pro, plafonné à 1000 min) : 8,99 € - $11,50 ≈ **-$1,70** (perte réduite)

---

### Option D : Abonnement unique + crédits audio

| | Détails |
|---|---------|
| **Prix de base** | 5,99 €/mois (≈ $6,53) |
| **Inclus** | Médias texte illimités + 300 min audio/mois + tous artefacts |
| **Pack audio additionnel** | 2,99 € pour 300 min supplémentaires |
| **Essai** | 1 mois gratuit |

**Avantages** :
- Prix de base très attractif car les articles/tweets coûtent quasi rien
- Les gros consommateurs audio paient proportionnellement
- Pas de "tiers" multiples mais un mécanisme de pack simple
- Aligne le coût sur la consommation réelle

**Inconvénients** :
- Le mécanisme de "pack" peut paraître limitatif
- Mauvaise UX si l'utilisateur doit surveiller ses minutes
- Complexité technique pour gérer les crédits

**Marge estimée** :
- Étudiant (300 min suffisent) : 5,99 € - $3,10 ≈ +$3,43 (53% de marge)
- Pro veille (1 pack extra) : 8,98 € - $5,70 ≈ +$4,09 (42% de marge)
- Power user (4 packs extra) : 17,95 € - $14,77 ≈ +$4,77 (24% de marge)

---

## 7. Recommandation finale

### Choix recommandé : Option B -- Freemium + Premium à 8,99 €/mois

**Raisons** :

1. **Simplicité** : Un seul tier payant à communiquer, pas de confusion entre Standard et Pro
2. **Acquisition** : Le free tier (5 médias/mois) permet le bouche-à-oreille et réduit la friction d'adoption. Un utilisateur qui partage 5 articles peut voir la valeur avant de payer.
3. **Marge saine** : 42-66% de marge sur les profils étudiant et pro, qui représentent la grande majorité des utilisateurs
4. **Protection contre l'abus** : Le plafond de 600 min audio/mois et 60 médias/mois protège contre les power users extrêmes tout en étant généreux pour 90% des utilisateurs
5. **Alignement marché** : Le prix de 8,99 € se situe entre Snipd ($6,99) et Readwise ($12,99), ce qui est cohérent vu que notre app offre plus que Snipd (multi-média) mais un scope différent de Readwise (pas d'export Notion)
6. **Respect de la contrainte** : 8,99 € < 9 € max

### Ajustements recommandés

- **Plafond audio** : Fixer à 600 min/mois (10h), suffisant pour Thomas (580 min) avec une petite marge. Si dépassement fréquent, envisager un upgrade payant à la demande.
- **Annuel** : Proposer -20% en annuel → 7,19 €/mois (86,28 €/an) pour verrouiller les utilisateurs et améliorer le cash flow
- **Modèles LLM** : Démarrer avec GPT-4.1 nano pour les résumés courts + flashcards, et GPT-4.1 mini pour les résumés détaillés. Tester Gemini 2.5 Flash comme alternative si la qualité est équivalente (potentiellement meilleur rapport qualité/prix à $0,30/$2,50).
- **Monitoring** : Mettre en place un suivi du coût par utilisateur dès le lancement pour détecter les outliers et ajuster les plafonds si nécessaire

### Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Power users non rentables | Perte financière | Plafond de 600 min audio + monitoring |
| Free tier abusé (bots, scraping) | Coût serveur | Rate limiting, vérification email, CAPTCHA |
| Hausse des prix API (LLM, Deepgram) | Réduction des marges | Multi-provider, possibilité de switcher |
| Taux de conversion free → paid trop bas | Revenus insuffisants | Optimiser l'onboarding, montrer la valeur dès le 1er média |
| Concurrence agressive (Readwise baisse ses prix) | Pression sur le prix | Différenciation par les features (spaced rep, digest, multi-média) |

### Prochaines étapes

1. **Benchmark qualité LLM** : Tester GPT-4.1 nano vs Gemini 2.5 Flash vs Mistral Small 3 sur la qualité des résumés et flashcards
2. **Prototype de facturation** : Implémenter le compteur de médias et de minutes audio
3. **Intégration Stripe** : Configurer les plans Free et Premium
4. **Dashboard coûts** : Mettre en place le suivi des coûts par utilisateur (coût Deepgram + coût LLM par média)

---

## Annexe : Tableau récapitulatif des prix unitaires

| Service | Fournisseur | Prix unitaire | Unité |
|---------|-------------|---------------|-------|
| Transcription audio | Deepgram Nova-3 (multilingue) | $0,0092 | par minute |
| LLM (économique) | GPT-4.1 nano | $0,10 / $0,40 | par MTok (in/out) |
| LLM (standard) | GPT-4.1 mini | $0,40 / $1,60 | par MTok (in/out) |
| LLM (premium) | Gemini 2.5 Flash | $0,30 / $2,50 | par MTok (in/out) |
| OCR | Google Cloud Vision | $0,0015 | par page |
| Stockage S3 | AWS | ~$0,023 | par GB/mois |
| DynamoDB écriture | AWS | ~$1,25 | par million WRU |
| DynamoDB lecture | AWS | ~$0,25 | par million RRU |
| SQS | AWS | ~$0,40 | par million requêtes |
| Compute (Fargate) | AWS | $0,04048 vCPU/h + $0,00445 GB/h | par heure |
| Compute (Railway) | Railway | $0,0278 vCPU/h | par heure |
