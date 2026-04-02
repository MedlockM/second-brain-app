# Benchmark LLM pour la generation d'artefacts

**Date :** 2 avril 2026
**Auteur :** Recherche automatisee
**Statut :** Recherche complete

---

## 1. Contexte

L'application "second brain" genere quatre types d'artefacts a partir de transcriptions/extractions de contenu media :

| Artefact | Description | Tokens output estimes |
|----------|-------------|-----------------------|
| **summary_short** | Resume court, adapte format newsletter/digest | ~500 tokens |
| **summary_detailed** | Resume exhaustif, adapte apprentissage | ~2 000 tokens |
| **flashcards** | Questions/Reponses generees par IA (JSON structure) | ~1 500 tokens |
| **notes** | Notes structurees (non implemente, prevu V1) | ~1 000 tokens |

**Input typique :** Une transcription de podcast/video de 30-60 minutes represente environ 8 000 a 20 000 tokens. On retient **15 000 tokens en moyenne** pour les estimations de cout.

### Etat actuel du code

Le backend utilise actuellement :
- **Modele :** `gpt-4o-mini-2024-07-18` (configurable via `OPENAI_MODEL`)
- **API :** OpenAI Chat Completions (`/v1/chat/completions`)
- **Format de sortie :** JSON (main_topics, key_points, notable_quotes, conclusion)
- **Timeout :** 120s (summarization), 180s (quiz)
- **Retry :** 3 tentatives avec backoff exponentiel
- **max_completion_tokens :** 1 000 (summarization), illimite (quiz)

Le worker de summarization (`media_summarizer/workers/summarization/summarization_worker.py`) fait un appel direct a l'API OpenAI via `aiohttp`. Le worker quiz (`media_summarizer/workers/quiz/worker.py`) suit le meme pattern.

---

## 2. Criteres d'evaluation

| Critere | Poids | Description |
|---------|-------|-------------|
| **Qualite de generation** | 30% | Pertinence, coherence, fidelite au contenu source |
| **Cout par million de tokens** | 25% | Prix input + output combines |
| **Latence** | 15% | Temps de reponse (TTFT + generation) |
| **Fiabilite JSON** | 15% | Capacite a produire du JSON valide sans post-traitement |
| **Taille de contexte** | 10% | Capacite a traiter de longues transcriptions |
| **Multilinguisme** | 5% | Qualite en francais, anglais, espagnol, etc. |

---

## 3. Modeles evalues

### 3.1 OpenAI

| Modele | Input $/MTok | Output $/MTok | Contexte | Max output | Latence (TTFT) | Intelligence Index |
|--------|-------------|--------------|----------|------------|----------------|-------------------|
| **GPT-4o** | $2.50 | $10.00 | 128K | 16K | 0.92s | 17 |
| **GPT-4o-mini** | $0.15 | $0.60 | 128K | 16K | 4.64s | 13 |
| **GPT-4.1** | $2.00 | $8.00 | 1M | 32K | 1.07s | 26 |
| **GPT-4.1-mini** | $0.40 | $1.60 | 1M | 32K | ~1.5s | ~18 |
| **GPT-4.1-nano** | $0.10 | $0.40 | 1M | 32K | ~0.8s | ~10 |
| **o4-mini** | $1.10 | $4.40 | 200K | 100K | ~2s | ~30 |

**Notes :**
- GPT-4.1 offre un contexte de 1M tokens, ideal pour les tres longues transcriptions
- GPT-4o-mini reste le meilleur rapport qualite/prix dans la gamme OpenAI pour des taches de summarization
- GPT-4.1-nano est le modele le moins cher d'OpenAI avec un contexte de 1M
- o4-mini est un modele de raisonnement, surdimensionne pour la generation d'artefacts
- Tous les modeles OpenAI supportent le JSON mode natif (`response_format: { type: "json_object" }`)

**Sources :** [OpenRouter - GPT-4o](https://openrouter.ai/models/openai/gpt-4o), [OpenRouter - GPT-4.1](https://openrouter.ai/models/openai/gpt-4.1), [OpenRouter - GPT-4.1-mini](https://openrouter.ai/models/openai/gpt-4.1-mini), [OpenRouter - GPT-4.1-nano](https://openrouter.ai/models/openai/gpt-4.1-nano), [OpenRouter - GPT-4o-mini](https://openrouter.ai/models/openai/gpt-4o-mini)

### 3.2 Anthropic (Claude)

| Modele | Input $/MTok | Output $/MTok | Contexte | Max output | Latence (TTFT) | Intelligence Index |
|--------|-------------|--------------|----------|------------|----------------|-------------------|
| **Claude Opus 4.6** | $5.00 | $25.00 | 1M | 128K | ~3s | ~50 |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 1M | 64K | 2.02s | 44 |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K | 64K | 0.68s | 31 |

**Notes :**
- Claude Sonnet 4.6 et Opus 4.6 sont les modeles les plus recents (mars 2026)
- Claude Haiku 4.5 offre un excellent equilibre qualite/vitesse/prix
- Anthropic excelle en multilinguisme et en suivi d'instructions complexes
- L'API supporte le JSON mode via le prefixe `{"` dans la reponse assistante ou via tool use
- Claude Haiku 3.5 est obsolete (`claude-3-haiku-20240307`, retirement prevu avril 2026) -- remplace par Haiku 4.5

**Sources :** [Anthropic Models Documentation](https://platform.claude.com/docs/en/docs/about-claude/models), [Artificial Analysis Leaderboard](https://artificialanalysis.ai/leaderboards/models)

### 3.3 Google (Gemini)

| Modele | Input $/MTok | Output $/MTok | Contexte | Max output | Latence (TTFT) | Intelligence Index |
|--------|-------------|--------------|----------|------------|----------------|-------------------|
| **Gemini 2.5 Pro** | $1.25 | $10.00 | 1M | 65K | 29.61s | 30 |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | 1M | 65K | 0.55s | 21 |
| **Gemini 2.0 Flash** | $0.10 | $0.40 | 1M | 8K | ~0.4s | ~15 |

**Notes :**
- Gemini 2.5 Pro a un input tres economique ($1.25) mais un output cher ($10.00)
- Gemini 2.5 Flash est le champion de la vitesse (213 tokens/s) avec un prix agressif
- La latence TTFT de Gemini 2.5 Pro est tres elevee (29.6s) -- problematique en production
- L'API Gemini supporte `response_mime_type: "application/json"` pour le JSON mode
- Le tier gratuit de Gemini est genereux pour le prototypage (15 req/min)

**Sources :** [Google AI Pricing](https://ai.google.dev/pricing), [OpenRouter - Gemini 2.5 Pro](https://openrouter.ai/models/google/gemini-2.5-pro-preview)

### 3.4 Mistral

| Modele | Input $/MTok | Output $/MTok | Contexte | Max output | Latence (TTFT) | Intelligence Index |
|--------|-------------|--------------|----------|------------|----------------|-------------------|
| **Mistral Large 3** | $2.00 | $6.00 | 131K | ~32K | 1.48s | 15 |
| **Mistral Medium 3.1** | $0.40 | $2.00 | 131K | ~32K | ~1.5s | ~20 |
| **Mistral Small 3.2** | $0.05 | $0.08 | 32K | 16K | ~0.5s | ~12 |

**Notes :**
- Mistral Small est extremement bon marche ($0.05/$0.08) mais son contexte est limite a 32K
- Mistral Medium 3.1 offre un bon equilibre pour des taches de synthese
- Mistral Large est competitif en prix mais en retard sur l'intelligence comparee a GPT-4.1 ou Claude
- L'API Mistral supporte le JSON mode natif
- Mistral est un fournisseur europeen (donnees hebergees en UE), avantage RGPD

**Sources :** [OpenRouter - Mistral Large](https://openrouter.ai/models/mistralai/mistral-large-2411), [OpenRouter - Mistral Medium](https://openrouter.ai/models/mistralai/mistral-medium-3), [OpenRouter - Mistral Small](https://openrouter.ai/models/mistralai/mistral-small-24b-instruct-2501)

### 3.5 Open Source (via API tiers)

| Modele | Input $/MTok | Output $/MTok | Contexte | Max output | Latence (TTFT) | Intelligence Index |
|--------|-------------|--------------|----------|------------|----------------|-------------------|
| **Llama 4 Maverick** | $0.15 | $0.60 | 1M | 16K | ~0.7s | ~18 |
| **Llama 4 Scout** | $0.08 | $0.30 | 328K | 16K | 0.77s | 14 |
| **DeepSeek V3** | $0.20 | $0.77 | 164K | ~16K | 1.81s | 32 |
| **Qwen3 235B** | $0.455 | $1.82 | 131K | 8K | 5.69s | ~42 |

**Notes :**
- DeepSeek V3 offre un rapport qualite/prix exceptionnel (intelligence 32, prix ~$0.50/MTok moyen)
- Qwen3 235B a un score d'intelligence tres eleve (42) comparable a Claude Sonnet, pour un prix tres bas
- Llama 4 Maverick est tres economique avec un contexte de 1M tokens
- Les modeles open-source sont accessibles via des providers tiers (Together, Fireworks, DeepInfra, OpenRouter)
- La fiabilite JSON est generalement inferieure aux modeles proprietaires -- necessitent souvent du post-traitement
- Le self-hosting est possible mais non recommande pour un solo dev (complexite infra)

**Sources :** [OpenRouter - Llama 4 Maverick](https://openrouter.ai/models/meta-llama/llama-4-maverick), [OpenRouter - Llama 4 Scout](https://openrouter.ai/models/meta-llama/llama-4-scout), [OpenRouter - DeepSeek V3](https://openrouter.ai/models/deepseek/deepseek-chat-v3-0324), [OpenRouter - Qwen3](https://openrouter.ai/models/qwen/qwen3-235b-a22b), [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)

---

## 4. Comparaison par type d'artefact

### Hypotheses de calcul

- **Input moyen :** 15 000 tokens (transcription de ~45 min)
- **Prompt systeme :** ~500 tokens
- **Total input :** 15 500 tokens par appel

| Artefact | Output tokens | Exigence qualite | Exigence JSON | Exigence vitesse |
|----------|--------------|-------------------|---------------|------------------|
| summary_short | 500 | Moyenne | Non (texte) | Elevee (digest) |
| summary_detailed | 2 000 | Elevee | Oui (structure) | Moyenne |
| flashcards | 1 500 | Elevee | Critique (JSON strict) | Faible |
| notes | 1 000 | Moyenne-Elevee | Oui (structure) | Moyenne |

### 4.1 summary_short (~500 tokens output)

Cout par appel = (15 500 * input_price + 500 * output_price) / 1 000 000

| Modele | Cout/appel | Qualite | Vitesse | JSON fiable | Score global |
|--------|-----------|---------|---------|-------------|-------------|
| **GPT-4.1-nano** | $0.0018 | Correcte | Rapide | Oui | Bon |
| **Gemini 2.5 Flash** | $0.0059 | Bonne | Tres rapide | Oui | Tres bon |
| **GPT-4o-mini** | $0.0026 | Bonne | Moyenne | Oui | Tres bon |
| **Mistral Small** | $0.0008 | Acceptable | Rapide | Oui | Correct |
| **Llama 4 Scout** | $0.0014 | Acceptable | Rapide | Moyenne | Correct |
| **DeepSeek V3** | $0.0035 | Bonne | Moyenne | Moyenne | Bon |
| **GPT-4.1-mini** | $0.0070 | Bonne | Rapide | Oui | Bon |
| **Claude Haiku 4.5** | $0.0181 | Tres bonne | Rapide | Bonne | Bon |

**Recommandation summary_short : GPT-4o-mini** -- meilleur equilibre qualite/cout/fiabilite JSON pour un resume court. Alternative budget : GPT-4.1-nano. Alternative qualite : Gemini 2.5 Flash.

### 4.2 summary_detailed (~2 000 tokens output)

Cout par appel = (15 500 * input_price + 2 000 * output_price) / 1 000 000

| Modele | Cout/appel | Qualite | Vitesse | JSON fiable | Score global |
|--------|-----------|---------|---------|-------------|-------------|
| **GPT-4o-mini** | $0.0035 | Bonne | Moyenne | Oui | Tres bon |
| **GPT-4.1-nano** | $0.0024 | Correcte | Rapide | Oui | Bon |
| **Gemini 2.5 Flash** | $0.0097 | Bonne | Tres rapide | Oui | Tres bon |
| **DeepSeek V3** | $0.0046 | Tres bonne | Moyenne | Moyenne | Bon |
| **GPT-4.1-mini** | $0.0094 | Bonne | Rapide | Oui | Tres bon |
| **Claude Haiku 4.5** | $0.0255 | Tres bonne | Rapide | Bonne | Bon |
| **Qwen3 235B** | $0.0107 | Tres bonne | Lente | Moyenne | Correct |
| **GPT-4.1** | $0.0470 | Excellente | Rapide | Oui | Premium |

**Recommandation summary_detailed : GPT-4.1-mini** -- intelligence suffisante pour un resume detaille, JSON fiable natif, contexte de 1M tokens. Alternative budget : GPT-4o-mini. Alternative qualite : DeepSeek V3 (excellent rapport qualite/prix).

### 4.3 flashcards (~1 500 tokens output, JSON strict)

Cout par appel = (15 500 * input_price + 1 500 * output_price) / 1 000 000

| Modele | Cout/appel | Qualite | JSON fiable | Score global |
|--------|-----------|---------|-------------|-------------|
| **GPT-4o-mini** | $0.0032 | Bonne | Excellent | Tres bon |
| **GPT-4.1-mini** | $0.0086 | Bonne | Excellent | Tres bon |
| **GPT-4.1-nano** | $0.0022 | Correcte | Bon | Bon |
| **Gemini 2.5 Flash** | $0.0084 | Bonne | Bon | Bon |
| **Claude Haiku 4.5** | $0.0230 | Tres bonne | Bon | Bon |
| **DeepSeek V3** | $0.0043 | Bonne | Moyen | Correct |
| **Llama 4 Maverick** | $0.0032 | Correcte | Faible | Insuffisant |
| **Mistral Small** | $0.0009 | Acceptable | Moyen | Correct |

**Recommandation flashcards : GPT-4o-mini** -- la fiabilite JSON est critique pour les flashcards (schema strict avec id, prompt, choices, correct). GPT-4o-mini et GPT-4.1-mini offrent le JSON mode natif le plus fiable. Alternative : GPT-4.1-mini pour une meilleure qualite des questions.

### 4.4 notes (~1 000 tokens output)

Cout par appel = (15 500 * input_price + 1 000 * output_price) / 1 000 000

| Modele | Cout/appel | Qualite | JSON fiable | Score global |
|--------|-----------|---------|-------------|-------------|
| **GPT-4o-mini** | $0.0029 | Bonne | Oui | Tres bon |
| **GPT-4.1-nano** | $0.0020 | Correcte | Oui | Bon |
| **Gemini 2.5 Flash** | $0.0072 | Bonne | Oui | Bon |
| **GPT-4.1-mini** | $0.0078 | Bonne | Oui | Tres bon |
| **DeepSeek V3** | $0.0039 | Tres bonne | Moyenne | Bon |
| **Claude Haiku 4.5** | $0.0205 | Tres bonne | Bonne | Bon |
| **Mistral Medium 3.1** | $0.0082 | Bonne | Bonne | Bon |

**Recommandation notes : GPT-4o-mini** -- equilibre ideal pour des notes structurees. Alternative qualite : GPT-4.1-mini. Alternative budget : GPT-4.1-nano.

---

## 5. Tableau de synthese des recommandations

| Artefact | Recommandation principale | Cout/appel | Alternative budget | Alternative qualite |
|----------|--------------------------|-----------|-------------------|-------------------|
| **summary_short** | GPT-4o-mini | $0.0026 | GPT-4.1-nano ($0.0018) | Gemini 2.5 Flash ($0.0059) |
| **summary_detailed** | GPT-4.1-mini | $0.0094 | GPT-4o-mini ($0.0035) | DeepSeek V3 ($0.0046) |
| **flashcards** | GPT-4o-mini | $0.0032 | GPT-4.1-nano ($0.0022) | GPT-4.1-mini ($0.0086) |
| **notes** | GPT-4o-mini | $0.0029 | GPT-4.1-nano ($0.0020) | GPT-4.1-mini ($0.0078) |

### Justification des choix

1. **GPT-4o-mini comme choix par defaut** : C'est le modele deja en place dans le code. Il offre un excellent rapport qualite/prix, une fiabilite JSON native, et une compatibilite directe avec l'API OpenAI existante. Aucune migration technique n'est necessaire.

2. **GPT-4.1-mini pour summary_detailed** : Le resume detaille beneficie d'un modele plus intelligent (score 18 vs 13) pour mieux capturer les nuances. Le contexte de 1M tokens permet de traiter des transcriptions tres longues sans troncature. Le surcout est modeste ($0.0094 vs $0.0035).

3. **Fiabilite JSON determinante pour flashcards** : Les flashcards ont un schema JSON strict (id, prompt, multiple, choices avec correct, explanation). Les modeles OpenAI avec `response_format: { type: "json_object" }` garantissent un JSON valide. Les modeles open-source necessitent souvent du post-traitement couteux en complexite.

4. **GPT-4.1-nano comme alternative budget systematique** : A $0.10/$0.40 par MTok avec 1M de contexte, c'est le modele le plus economique capable de produire du JSON fiable. Qualite inferieure mais acceptable pour un tier gratuit.

---

## 6. Estimation du cout mensuel par persona

### Hypotheses

- **1 media traite = 4 appels LLM** (summary_short + summary_detailed + flashcards + notes)
- **Cout moyen par media** = $0.0026 + $0.0094 + $0.0032 + $0.0029 = **$0.0181** (recommandation principale)
- **Cout moyen par media (budget)** = $0.0018 + $0.0035 + $0.0022 + $0.0020 = **$0.0095** (alternatives budget)

### Profils utilisateur

| Persona | Medias/semaine | Medias/mois | Cout/mois (principal) | Cout/mois (budget) |
|---------|---------------|-------------|----------------------|-------------------|
| **Etudiant** | 10 | 43 | $0.78 | $0.41 |
| **Professionnel** | 20 | 87 | $1.57 | $0.83 |
| **Power user** | 40 | 173 | $3.13 | $1.64 |

### Cout en euros (taux 1 USD = 0.92 EUR)

| Persona | Medias/mois | Cout/mois (principal) | Cout/mois (budget) |
|---------|-------------|----------------------|-------------------|
| **Etudiant** | 43 | 0.72 EUR | 0.38 EUR |
| **Professionnel** | 87 | 1.44 EUR | 0.76 EUR |
| **Power user** | 173 | 2.88 EUR | 1.51 EUR |

### Analyse par rapport au pricing cible (max 9 EUR/mois)

Avec la recommandation principale, le cout LLM represente :
- **Etudiant :** 8% du prix max (0.72 EUR / 9 EUR)
- **Professionnel :** 16% du prix max
- **Power user :** 32% du prix max

La marge est confortable. Meme un power user en mode "principal" ne consomme que ~3 EUR de LLM, laissant ~6 EUR pour les autres couts (transcription, stockage, infra, marge).

### Scenario "tout GPT-4.1-nano" (tier gratuit)

| Persona | Medias/mois | Cout/mois |
|---------|-------------|-----------|
| **Etudiant** | 43 | 0.38 EUR |
| **Professionnel** | 87 | 0.76 EUR |
| **Power user** | 173 | 1.51 EUR |

Ce scenario permet d'offrir un tier gratuit limite (ex: 5 medias/semaine = ~0.20 EUR/mois) sans impact financier significatif.

---

## 7. Strategie d'implementation recommandee

### Phase 1 : Optimisation immediate (0 effort)

Conserver **GPT-4o-mini** pour tous les artefacts. C'est deja en place et le rapport qualite/prix est excellent. Ajouter `response_format: { type: "json_object" }` dans les appels API pour garantir le JSON valide (le code actuel fait du parsing JSON en fallback).

### Phase 2 : Differenciation par artefact (effort modere)

Introduire une variable de configuration par type d'artefact :

```
OPENAI_MODEL_SUMMARY_SHORT=gpt-4o-mini
OPENAI_MODEL_SUMMARY_DETAILED=gpt-4.1-mini
OPENAI_MODEL_FLASHCARDS=gpt-4o-mini
OPENAI_MODEL_NOTES=gpt-4o-mini
```

Cela permet de selectionner le modele optimal par artefact sans changer le fournisseur API.

### Phase 3 : Multi-provider (effort significatif)

Abstraire le client LLM pour supporter plusieurs fournisseurs (OpenAI, Anthropic, Google, etc.). Utile pour :
- Negocier les prix en jouant la concurrence
- Fallback automatique en cas de panne d'un fournisseur
- A/B testing de la qualite par modele

**Recommandation :** Ne pas investir dans Phase 3 avant d'avoir des utilisateurs reels. La difference de qualite entre les top modeles est faible pour des taches de summarization. Le lock-in sur OpenAI est acceptable a court terme.

### Consideration RGPD

Mistral (fournisseur francais, donnees en UE) peut etre interessant pour des raisons reglementaires. Cependant, les modeles Mistral sont en retrait en qualite par rapport a OpenAI et Anthropic. A reconsiderer si la reglementation l'exige.

---

## 8. Risques et limites

| Risque | Impact | Mitigation |
|--------|--------|------------|
| **Hausse des prix OpenAI** | Moyen | Phase 3 multi-provider, ou migration vers GPT-4.1-nano |
| **Baisse de qualite apres mise a jour modele** | Faible | Versionner le modele (ex: `gpt-4o-mini-2024-07-18`) |
| **Latence elevee en pic** | Moyen | Traitement asynchrone (deja en place via SQS) |
| **Transcriptions > 128K tokens** | Faible | GPT-4.1 ou Gemini 2.5 (1M contexte) en fallback |
| **Fiabilite JSON modeles OSS** | Eleve | Rester sur OpenAI pour les artefacts JSON critiques |
| **Dependance single-provider** | Moyen | Acceptable a court terme, Phase 3 si necessaire |

---

## 9. Sources

- [OpenRouter - GPT-4o](https://openrouter.ai/models/openai/gpt-4o) - Prix et specs
- [OpenRouter - GPT-4o-mini](https://openrouter.ai/models/openai/gpt-4o-mini) - Prix et specs
- [OpenRouter - GPT-4.1](https://openrouter.ai/models/openai/gpt-4.1) - Prix et specs
- [OpenRouter - GPT-4.1-mini](https://openrouter.ai/models/openai/gpt-4.1-mini) - Prix et specs
- [OpenRouter - GPT-4.1-nano](https://openrouter.ai/models/openai/gpt-4.1-nano) - Prix et specs
- [Anthropic Models Documentation](https://platform.claude.com/docs/en/docs/about-claude/models) - Prix Claude, specs, context windows
- [Google AI Pricing](https://ai.google.dev/pricing) - Prix Gemini
- [OpenRouter - Gemini 2.5 Pro](https://openrouter.ai/models/google/gemini-2.5-pro-preview) - Prix et specs
- [OpenRouter - Mistral Large](https://openrouter.ai/models/mistralai/mistral-large-2411) - Prix et specs
- [OpenRouter - Mistral Medium](https://openrouter.ai/models/mistralai/mistral-medium-3) - Prix et specs
- [OpenRouter - Mistral Small](https://openrouter.ai/models/mistralai/mistral-small-24b-instruct-2501) - Prix et specs
- [OpenRouter - Llama 4 Maverick](https://openrouter.ai/models/meta-llama/llama-4-maverick) - Prix et specs
- [OpenRouter - Llama 4 Scout](https://openrouter.ai/models/meta-llama/llama-4-scout) - Prix et specs
- [OpenRouter - DeepSeek V3](https://openrouter.ai/models/deepseek/deepseek-chat-v3-0324) - Prix et specs
- [OpenRouter - Qwen3 235B](https://openrouter.ai/models/qwen/qwen3-235b-a22b) - Prix et specs
- [OpenRouter - o4-mini](https://openrouter.ai/models/openai/o4-mini) - Prix et specs
- [Artificial Analysis LLM Leaderboard](https://artificialanalysis.ai/leaderboards/models) - Intelligence Index, vitesse, latence
