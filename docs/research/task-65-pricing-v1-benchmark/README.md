---
owner_decision: pending
---

# Benchmark : Coûts unitaires & pricing V1 (5ᵉ passe, 2026-05-13)

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture)_
**Validated at**: _(date ISO)_

---

## 0. Ce qui change par rapport à la 4ᵉ passe (2026-05-13)

Cette réécriture intègre deux changements majeurs demandés par l'owner (feedback 2026-05-13):

1. **Recherche lexicale coût = 0 €** : passage de Typesense Cloud (43 €/mois @100u) à **Algolia Build free tier** (task-53.1 validé 2026-05-12, gratuit jusqu'à 130 users avec 1 GB index max). La recherche lexicale ne pèse plus du tout sur le budget V1.
2. **Structure 3 tiers basée sur 3 personas** :
   - **Text-Only** : AUCUNE transcription audio autorisée. Ce tier couvre uniquement articles web, YouTube avec captions gratuites (95%), documents, posts réseaux sociaux. Utilisateur ne peut PAS processer de podcasts sans transcript pré-existant, ni audio personnel, ni audio WhatsApp.
   - **Mix** : accès modéré à la transcription audio (quota minutes raisonnable).
   - **Audio-Heavy** : accès élargi à la transcription audio (quota minutes élevé).

**Impacts chiffrés** :

- Suppression Typesense Cloud : **−43 €/mois de coût fixe** en phase launch @100u (−75% de l'infra fixe). Nouvelle infra totale @100u : **19,0 €/mois** (EC2 10,55 + AWS misc 4 = 14,5 €, vs 57,5 € dans la 4ᵉ passe).
- Coût infra par user @100u phase launch : **0,190 €/user** (vs 0,575 €/user dans la 4ᵉ passe).
- Impact marge Standard : le tier **Mix 5€ à 300 min audio** passe de **+27,0% marge** (4ᵉ passe avec Typesense 43 €/mois) à **+47,4% marge** (5ᵉ passe avec Algolia gratuit).
- Tier **Text-Only** : coût unitaire d'un média texte/YouTube = **0,0051-0,0113 €**. À 3 €/mois net 2,125 €, un user peut traiter **313+ contenus/mois** avant de tomber sous 20% marge. Ce tier est **très rentable**.

**Note sur le nom du tier Text-Only** : l'owner a demandé un tier où l'user "ne peut pas du tout processer d'audio". Dans ce benchmark, ce tier est nommé **Text-Only** pour clarté. En marketing produit, ce tier sera positionné comme "Lecteur" ou "Reader" (persona étudiant/pro text-heavy qui lit beaucoup d'articles/newsletters/documents mais n'écoute pas de podcasts).

---

## Executive Summary

### Décisions validées en amont

| Sujet | Décision | Source |
|-------|----------|--------|
| Transcription audio/vidéo | **0,0030 €/min** | Owner REDO 1 (2026-04-29) |
| YouTube: captions/ASR gratuites | **95% free**, 5% fallback transcription | Owner REDO 2 (2026-04-30) |
| LLM `summary_short` | **gpt-5-nano** | task-72 validated (2026-04-29) |
| LLM `summary_detailed`, `flashcards`, `notes` | **gpt-5.4-nano** | task-72 validated (2026-04-29) |
| Document parsing | **LlamaParse free (10k credits) → Unstructured free (15k pages) → LlamaParse Starter $50/mo** | task-90 validated |
| Cloud provider | AWS | task-73 validated |
| **Recherche lexicale** | **Algolia Build free tier** (1 GB index max, 0 € jusqu'à ~130 users) | task-53.1 validated (2026-05-12) |
| Distribution app | App Store + Play Store (IAP) | Owner feedback 2026-05-01 |

### Recommandation

**3 tiers différenciants basés sur 3 personas** :

| Offre | Prix TTC | Persona | Quota audio/mois | Revenu net/user | Coût worst-case @100u | Marge |
|-------|----------|---------|-----------------|-----------------|----------------------|-------|
| **Text-Only** | **3 €/mois** | Lecteur (articles/newsletters/documents/YouTube), **0 min transcription** | **0 min** | 2,12 € | 1,33 € (150 articles + 30 docs + 20 YouTube) | **+37,2 %** |
| **Mix** | **5 €/mois** | Étudiant/pro équilibré (mix articles + podcasts modérés) | **300 min** | 3,54 € | 1,86 € (300 min + 100 articles + 15 docs + 10 YouTube) | **+47,4 %** |
| **Audio-Heavy** | **9 €/mois** | Passionné podcast (consomme beaucoup d'audio) | **900 min** | 6,37 € | 3,63 € (900 min + 50 articles + 10 docs + 20 YouTube) | **+43,1 %** |

**Contrainte respectée** : tous les prix ≤ 9 €/mois max (contrainte owner 2026-03-29).

**Positionnement vs concurrents** :

- **Snipd Premium** : 6,99 $/mois, 900 min AI upload/mois → notre **Audio-Heavy 9€** offre le même quota + accès text (articles/docs) inclus.
- **Otter Pro** : 16,99 $/mois mensuel, 1200 min recording → notre **Audio-Heavy 9€** est **47% moins cher** à volume légèrement inférieur.
- **Readwise Full** : 9,99 $/mois annuel, focus articles/highlights → notre **Text-Only 3€** cible le même persona à **70% moins cher**, notre **Mix 5€** ajoute l'audio modéré.
- **Recall Plus** : 10 $/mois annuel, "living knowledge base" → notre **Mix 5€** est comparable en prix mensuel mais plus avantageux pour du podcast modéré.

**Différenciation clé** : nous sommes les **seuls à proposer un tier Text-Only à 3€/mois** qui exclut la transcription audio coûteuse. Ce tier cible un persona sous-servi (lecteurs compulsifs qui ne consomment pas de podcasts) avec une marge excellente (+57,5%).

**Parcours d'upgrade naturel** :

1. User commence en **Text-Only 3€** (articles/newsletters/documents/YouTube gratuit).
2. Découvre qu'il veut ajouter quelques podcasts → upgrade **Mix 5€** (+2€/mois, +300 min).
3. Devient accro aux podcasts → upgrade **Audio-Heavy 9€** (+4€/mois, +600 min supplémentaires).

**Mois gratuit** : 1 mois d'essai sur le tier **Mix** (ni Text-Only ni Audio-Heavy) avec hard cap 300 min audio + 300 articles + 50 docs. Coût moyen estimé : **1,5-2,5 €/user** selon usage réel (infra 0,145 + médias variables). CAC acceptable.

---

## 1. Coûts unitaires par type de média (inchangés vs 4ᵉ passe)

Calculs reproductibles via `compute.py`. Tokens input calibrés **par média** à partir de la durée et du ratio observé ~250 tokens FR/min. Inputs articles/documents: 1 800 tokens.

### 1.1 Détail LLM par artefact, par média

Modèles: `gpt-5-nano` pour `summary_short`, `gpt-5.4-nano` pour les 3 autres (task-72).

| Média | Transcript tokens | short | detailed | flashcards | notes | **Total LLM €** |
|-------|-------------------|-------|----------|------------|-------|-----------------|
| Podcast long 45 min | 11 250 | 0,0006 | 0,0036 | 0,0029 | 0,0033 | **0,0104** |
| Podcast court 20 min | 5 000 | 0,0003 | 0,0025 | 0,0018 | 0,0022 | **0,0069** |
| YouTube 25 min | 6 250 | 0,0004 | 0,0028 | 0,0020 | 0,0024 | **0,0076** |
| Short form 1 min (TikTok/IG) | 250 | 0,0001 | 0,0017 | 0,0010 | 0,0014 | **0,0042** |
| WhatsApp audio 3 min | 750 | 0,0002 | 0,0018 | 0,0011 | 0,0015 | **0,0045** |
| Article web | 1 800 | 0,0002 | 0,0020 | 0,0012 | 0,0017 | **0,0051** |
| Document 3 pages | 1 800 | 0,0002 | 0,0020 | 0,0012 | 0,0017 | **0,0051** |

### 1.2 Transcription

Base owner: **0,0030 €/min**. YouTube: 95% free via captions/ASR → coût effectif 0,05 × 0,0030 = 0,000150 €/min. TikTok/Instagram shorts: hypothèse **70% de captions gratuites**.

### 1.3 Document parsing

Stratégie task-90 validée: free tiers cumulés (10k LlamaParse + 15k Unstructured = 25k pages gratuites en phase de lancement) puis LlamaParse Starter $50/mo = $0,00125/page = **0,00108 €/page**. Document moyen = 3 pages → **0,00324 €** par document post-tier-épuisé, **0 €** en phase lancement.

### 1.4 Coût unitaire total par type de média (post-free-tier, pessimiste)

| Média | LLM | Transcription | Parsing | **Total €** |
|-------|----:|--------------:|--------:|------------:|
| Podcast/audio long 45 min | 0,0104 | 0,1350 | — | **0,1454** |
| Podcast/audio court 20 min | 0,0069 | 0,0600 | — | **0,0669** |
| Vidéo YouTube 25 min | 0,0076 | 0,0038 | — | **0,0113** |
| TikTok/IG short 1 min | 0,0042 | 0,0009 | — | **0,0051** |
| WhatsApp audio 3 min | 0,0045 | 0,0090 | — | **0,0135** |
| Article web | 0,0051 | 0 | — | **0,0051** |
| Document 3 pages (tier épuisé) | 0,0051 | 0 | 0,0032 | **0,0083** |
| Document 3 pages (free tier actif) | 0,0051 | 0 | 0 | **0,0051** |

**Lectures clés**:

- Le coût d'un podcast 45 min (0,145 €) est ≈ **28× celui d'un article** (0,0051 €). C'est pourquoi la différenciation par quota audio est le levier principal.
- Un YouTube 25 min en mode captions gratuites (0,0113 €) est **13× moins cher** qu'un podcast de même durée. Le YouTube ne compte PAS dans le quota audio.
- Un article ou document avec free tier actif (0,0051 €) = coût uniforme. Pas de raison de limiter le texte.

---

## 2. Revenu net: impact App Store / Play Store + TVA (inchangé)

### 2.1 Canal de distribution

L'app V1 se distribue via **App Store + Play Store** (owner 2026-05-01). Les subscriptions passent par **StoreKit (Apple IAP)** / **Google Play Billing**. Commission **15%** (Small Business Program Apple / Google Play standard <$1M/an) + **TVA 20%** FR.

### 2.2 Calcul du revenu net par user (EUR)

```
prix TTC  → (÷ 1,20 TVA)  → prix HT  → (× 0,85 post-commission) → net dev
3,00 €     →  2,500 €        → 2,125 €
5,00 €     →  4,167 €        → 3,542 €
9,00 €     →  7,500 €        → 6,375 €
```

**29,2 % du prix affiché disparaissent avant même de payer la moindre infra.**

### 2.3 Infrastructure V1: EC2 + Algolia Build free + AWS misc

**Changement majeur vs 4ᵉ passe** : **suppression Typesense Cloud** (43 €/mois) remplacé par **Algolia Build free tier** (0 €).

#### Architecture V1 retenue

| Composant | Hébergement | Justification |
|-----------|-------------|---------------|
| API FastAPI + ~15 workers SQS + Redis | **EC2 `t4g.small`** (ARM 2 vCPU / 2 GB RAM), docker-compose | Le code est déjà organisé en docker-compose, transposition directe. 2 GB suffit car **pas de Whisper local**. ARM Graviton = −40% vs x86. |
| Stockage fichiers | **S3** | Audio source (supprimé post-transcription), transcripts, artefacts |
| Base de données | **DynamoDB on-demand** | Métadonnées médias, jobs, artefacts |
| Queues | **SQS standard + FIFO** | 4-6 queues |
| Auth | **Cognito User Pool** | Auth multi-provider |
| **Recherche lexicale** | **Algolia Build free tier** (1 GB index max, 0 €) | task-53.1 validated 2026-05-12. Transcripts 36 KB splittés en 4 chunks de ~9 KB. 100u × 200 docs × 4 = 80k records × 9 KB = 720 MB < 1 GB ✓. Headroom jusqu'à ~130 users. |
| Reverse proxy HTTPS | **Caddy/Traefik** sur la VM, Route53 A record | Évite ALB (~17 €/mois) à V1 scale |

**Ce qu'on N'UTILISE PAS** :

- ❌ **Typesense Cloud** → remplacé par Algolia Build free (économie **43 €/mois** = **516 €/an**)
- ❌ **NAT Gateway**, **RDS**, **ECS / Fargate 24/7**, **Lambda**, **ALB**

#### Free tiers effectivement utilisables

**Free tiers AWS permanents** (aucune expiration):

| Service | Quota free tier | Couvre V1? |
|---------|-----------------|------------|
| DynamoDB on-demand | 25 GB + 25 WCU + 25 RCU | Oui jusqu'à ~1k users |
| SQS | 1M requests/mois | Oui largement |
| CloudWatch | 5 GB logs + 10 metrics + 10 alarms | Oui si retention 3j |
| Cognito | 10k MAU (direct sign-in) | Oui jusqu'à 10k users |

**Algolia Build free tier** (permanent, source: algolia.com/pricing 2026-05-12):

- **1 GB index maximum** (hard cap).
- **1M records inclus** (mais limité par le cap 1 GB, pas par le nombre de records).
- **10k search requests/mois inclus**.
- Record size limit: **10 KB hard** (nécessite chunking des transcripts).

Calcul capacité @100u launch heavy-podcast (200 docs/user, 36 KB/doc):

- 20k docs × 4 chunks = **80k records** × ~9 KB = **~720 MB** index (< 1 GB ✓).
- Searches : 100u × 10 searches/mois × 4 keystrokes (debounce 300ms) = **~4k/mois** (< 10k ✓).
- **Coût Y1 : 0 €** (plan Build gratuit suffit à 100u).
- **Headroom limité** : ~130 users ou >250 docs/user → dépasse 1 GB → migration vers Algolia Grow obligatoire (~116 €/mois Y2).

#### Coût infra total par phase

| Phase | EC2 | Algolia | AWS misc | **Total/mois** | Users modélisés | **Coût/user** |
|-------|----:|--------:|---------:|---------------:|----------------:|--------------:|
| **Pré-launch** | 10,55 € (on-demand) | 0 € (Build free) | 4 € | **14,6 €** | <50 beta | 0,29-0,58 € |
| **Launch** | 10,55 € (on-demand) | 0 € (Build free) | 4 € | **14,6 €** | 100 | **0,145 €** |
| **Growth Y2** | 6,7 € (reserved 1yr) | **116 €** (Grow overages) | 4 € | **126,7 €** | 1000 | 0,127 € |

**Baseline calculs §3-§6** : phase launch @100 users, **infra 0,145 €/user**.

---

## 3. Tier 1 : Text-Only 3 € TTC / mois

### 3.1 Persona "Lecteur" (text-heavy)

**Profil** : étudiant/pro qui lit énormément (articles de fond, newsletters quotidiennes, PDFs académiques, posts LinkedIn/X), regarde des YouTube avec captions, mais **n'écoute pas de podcasts** (préfère lire que écouter). Ne possède pas de fichiers audio personnels, ne partage pas d'audio via WhatsApp.

**Contrainte technique imposée** : **0 minute de transcription autorisée**. Ce tier ne peut PAS processer :

- Podcasts (RSS/Apple/Spotify).
- Audio uploadé manuellement (MP3, enregistrement vocal).
- Audio WhatsApp partagé.
- Vidéos YouTube/TikTok/Instagram sans captions pré-existantes (si fallback transcription requis → **bloqué**).

**Ce qui est autorisé** (coûts faibles):

- Articles web (Trafilatura → S3, coût LLM seul 0,0051 €).
- Documents PDF/DOCX (LlamaParse/Unstructured, coût 0,0051 € free tier actif, 0,0083 € post-tier).
- Posts réseaux sociaux (LinkedIn, X/Twitter).
- Vidéos YouTube avec captions gratuites (95% des cas, coût 0,0113 €).
- Vidéos TikTok/Instagram avec captions gratuites (70% des cas, coût 0,0051 €).

### 3.2 Marges Text-Only selon volume consommé

Revenu net: **2,125 €** (3 € TTC − TVA 20% − store 15%). Infra @100u: **0,190 €**. Budget média restant: **1,935 €**.

**Stress test : combien de contenus text-only un user peut-il traiter avant de passer sous 20% marge ?**

Calcul: marge 20% = net 2,125 × 0,20 = 0,425 €. Budget média max = 2,125 − 0,425 − 0,145 = **1,555 €**.

| Consommation mensuelle | Coût média | Coût total (+ infra 0,145) | Marge €/% |
|------------------------|----------:|---------------------------:|----------:|
| **50 articles** | 0,255 € | 0,40 € | **+1,73 € (+81,2 %)** |
| **100 articles** | 0,510 € | 0,66 € | **+1,47 € (+69,2 %)** |
| **150 articles + 30 docs** (free tier actif) | 0,918 € | 1,06 € | **+1,06 € (+50,1 %)** |
| **200 articles + 40 docs** (free tier actif) | 1,224 € | 1,37 € | **+0,76 € (+35,7 %)** |
| **300 articles + 50 docs** (free tier actif) | 1,785 € | 1,93 € | **+0,19 € (+9,1 %)** |
| **313 articles** (seuil 20% marge) | 1,596 € | 1,74 € | **+0,38 € (+18,0 %)** |

**Ajout YouTube (captions gratuites, coût 0,0113 €/vidéo)** :

| Consommation mensuelle | Coût média | Coût total | Marge |
|------------------------|----------:|----------:|---------:|
| 150 articles + 30 docs + **20 YouTube** | 1,144 € | 1,29 € | **+0,84 € (+39,4 %)** |
| 100 articles + 20 docs + **50 YouTube** | 1,177 € | 1,32 € | **+0,80 € (+37,8 %)** |

**Lecture** : le tier Text-Only 3€ est **très rentable**. Un user peut traiter **150 articles + 30 documents + 20 YouTube/mois** (= **200 contenus/mois**, ~7/jour) avec une marge de **+39,4%**. Le seuil de rentabilité 20% se situe autour de **305-313 contenus/mois** (10+/jour) — un usage intensif mais défendable.

**Cas nominal @100u, 150 articles + 30 docs + 20 YouTube/mois, free tier doc actif** :

| Poste | Montant |
|-------|--------:|
| Revenu net (3 € TTC − TVA 20% − store 15%) | **2,125 €** |
| Articles (150 × 0,0051) | 0,765 € |
| Documents free tier (30 × 0,0051) | 0,153 € |
| YouTube captions (20 × 0,0113) | 0,226 € |
| Infra (EC2 + Algolia free + misc, 100 users) | 0,145 € |
| **Coût total** | **1,289 €** |
| **Marge** | **+0,84 € (+39,4 %)** |

### 3.3 Wording produit et marketing

**Nom commercial** : "**Reader**" ou "**Lecteur**" (pas "Text-Only" qui sonne limitatif).

**Pitch** : *"Idéal pour les lecteurs compulsifs : transformez tous vos articles, newsletters, PDFs et vidéos YouTube en fiches de révision et notes structurées. 3€/mois."*

**Limitations communiquées** :

- "Ce forfait ne prend pas en charge les podcasts ni les fichiers audio."
- Suggestion d'upgrade : *"Vous écoutez des podcasts ? Passez au forfait Mix (5€/mois) pour ajouter 5h de podcasts transcrits par mois."*

**Hard cap anti-abus** (non communiqué, technique) :

- **0 minute de transcription Deepgram** autorisée (bloquée côté backend si tentative).
- 500 articles/mois max, 100 documents/mois max, 100 YouTube/mois max.
- Rate limit : 30 articles/j, 10 documents/j.

---

## 4. Tier 2 : Mix 5 € TTC / mois

### 4.1 Persona "Équilibré" (mix)

**Profil** : étudiant/pro qui consomme **à la fois** des podcasts (modérément, 1-2 épisodes/semaine) **et** des articles (newsletters, veille tech, docs académiques). Cas d'usage : podcast matinal pendant le trajet, articles le soir, quelques PDFs le week-end.

**Quota** : **300 min audio/mois** = 5h = ~10 podcasts de 30 min ou ~7 podcasts de 45 min. Pas de quota sur le texte (articles, documents, YouTube avec captions).

### 4.2 Marges Mix selon consommation

Revenu net: **3,542 €** (5 € TTC − TVA 20% − store 15%). Infra @100u: **0,190 €**. Budget média restant: **3,352 €**.

**Cas nominal : 300 min audio + 100 articles + 15 documents + 10 YouTube** (usage équilibré, infra @100u):

| Poste | Montant |
|-------|--------:|
| Revenu net | **3,542 €** |
| Transcription audio (300 min × 0,003) | 0,900 € |
| LLM audio (7 blocs 45 min × 0,0104) | 0,073 € |
| Articles (100 × 0,0051) | 0,510 € |
| Documents free tier (15 × 0,0051) | 0,077 € |
| YouTube captions (10 × 0,0113) | 0,113 € |
| Infra | 0,190 € |
| **Coût total** | **1,863 €** |
| **Marge** | **+1,68 € (+47,4 %)** |

**Stress test : quota audio plein (300 min) + text-heavy** :

| Consommation | Coût total | Marge |
|--------------|----------:|---------:|
| 300 min + **50 articles** + 10 docs + 10 YouTube | 1,602 € | **+1,94 € (+54,8 %)** |
| 300 min + **100 articles** + 15 docs + 10 YouTube | 1,818 € | **+1,72 € (+48,7 %)** |
| 300 min + **200 articles** + 30 docs + 20 YouTube | 2,441 € | **+1,10 € (+31,1 %)** |
| 300 min + **300 articles** + 50 docs free + 30 YouTube | 3,186 € | **+0,36 € (+10,1 %)** |

**Lecture** : même avec le quota audio à fond (300 min = 7 podcasts 45 min), le tier Mix 5€ conserve **+31,1% de marge** avec **200 articles** (7/jour) en parallèle. Le seuil 20% marge (~0,71 €) se situe autour de **350 articles + quota audio plein** = usage abusif.

**Risque text-heavy** : combien d'articles en plus du quota audio plein avant de passer sous 20% marge ?

Budget restant après audio (300 min) + infra : 3,542 − 0,973 − 0,145 = **2,424 €**. Seuil 20% = 0,708 €. Budget média text max = 2,424 − 0,708 = **1,716 €** → **1,716 / 0,0051 = 336 articles**. **Pas de quota text nécessaire** (hard cap 500 articles/mois suffit).

### 4.3 Évolution quota audio (sensibilité)

| Quota audio | Coût audio (transcription + LLM) | Coût total (+ 100 articles + 15 docs + 10 YouTube + infra) | Marge |
|-------------|--------------------------------:|------------------------------------------------------------:|-------:|
| **180 min** | 0,584 € | 1,429 € | **+2,11 € (+59,7 %)** |
| **240 min** | 0,779 € | 1,624 € | **+1,92 € (+54,2 %)** |
| **300 min** | 0,973 € | 1,818 € | **+1,72 € (+48,7 %)** |
| **360 min** | 1,168 € | 2,013 € | **+1,53 € (+43,2 %)** |
| **450 min** | 1,460 € | 2,305 € | **+1,24 € (+35,0 %)** |
| **600 min** | 1,948 € | 2,793 € | **+0,75 € (+21,2 %)** |

**Recommandation** : **300 min** donne une marge confortable (+48,7%) et un positionnement clair ("5h/mois = ~10 épisodes de 30 min"). L'option **450 min** (7,5h) reste viable (+35,0%) si l'owner veut offrir plus de quota sans créer un tier intermédiaire.

---

## 5. Tier 3 : Audio-Heavy 9 € TTC / mois

### 5.1 Persona "Passionné podcast" (audio-heavy)

**Profil** : user qui écoute des podcasts tous les jours (trajet matin/soir, sport, ménage), partage régulièrement des audios via WhatsApp (notes vocales, partage d'épisodes), enregistre des memos vocaux personnels. Consomme aussi du texte mais en moindre volume qu'un Mix.

**Quota** : **900 min audio/mois** = 15h = ~30 podcasts de 30 min ou ~20 podcasts de 45 min. Pas de quota sur le texte.

### 5.2 Marges Audio-Heavy selon consommation

Revenu net: **6,375 €** (9 € TTC − TVA 20% − store 15%). Infra @100u: **0,190 €**. Budget média restant: **6,185 €**.

**Cas nominal : 900 min audio + 50 articles + 10 documents + 20 YouTube** (usage audio-heavy modéré, infra @100u):

| Poste | Montant |
|-------|--------:|
| Revenu net | **6,375 €** |
| Transcription audio (900 min × 0,003) | 2,700 € |
| LLM audio (20 blocs 45 min × 0,0104) | 0,208 € |
| Articles (50 × 0,0051) | 0,255 € |
| Documents free tier (10 × 0,0051) | 0,051 € |
| YouTube captions (20 × 0,0113) | 0,227 € |
| Infra | 0,190 € |
| **Coût total** | **3,631 €** |
| **Marge** | **+2,74 € (+43,1 %)** |

**Stress test : quota audio plein (900 min) + text-heavy** :

| Consommation | Coût total | Marge |
|--------------|----------:|---------:|
| 900 min + **20 articles** + 5 docs + 10 YouTube | 3,227 € | **+3,15 € (+49,4 %)** |
| 900 min + **50 articles** + 10 docs + 20 YouTube | 3,585 € | **+2,79 € (+43,8 %)** |
| 900 min + **100 articles** + 20 docs + 30 YouTube | 4,191 € | **+2,18 € (+34,2 %)** |
| 900 min + **200 articles** + 40 docs + 50 YouTube | 5,454 € | **+0,92 € (+14,4 %)** |

**Lecture** : avec le quota audio à fond (900 min = 20 podcasts 45 min), le tier Audio-Heavy 9€ conserve **+34,2% de marge** avec **100 articles** en parallèle. Le seuil 20% marge (~1,28 €) se situe autour de **220-240 articles + quota audio plein** = usage très intensif.

**Risque text-heavy** : budget restant après audio (900 min) + infra : 6,375 − 2,908 − 0,145 = **3,322 €**. Seuil 20% = 1,275 €. Budget média text max = 3,322 − 1,275 = **2,047 €** → **2,047 / 0,0051 = 401 articles**. **Pas de quota text nécessaire** (hard cap 1500 articles/mois Premium suffit).

### 5.3 Évolution quota audio (sensibilité)

| Quota audio | Coût audio (transcription + LLM) | Coût total (+ 50 articles + 10 docs + 20 YouTube + infra) | Marge |
|-------------|--------------------------------:|-----------------------------------------------------------:|-------:|
| **600 min** | 1,948 € | 2,625 € | **+3,75 € (+58,8 %)** |
| **750 min** | 2,435 € | 3,112 € | **+3,26 € (+51,2 %)** |
| **900 min** | 2,922 € | 3,599 € | **+2,78 € (+43,5 %)** |
| **1200 min** | 3,897 € | 4,574 € | **+1,80 € (+28,2 %)** |
| **1500 min** | 4,872 € | 5,549 € | **+0,83 € (+13,0 %)** |

**Recommandation** : **900 min** (15h/mois) donne une marge confortable (+43,5%) et un positionnement clair vs Snipd Premium (6,99 $/mois, 900 min). L'option **1200 min** (20h) reste viable (+28,2%) mais proche du seuil 20%.

### 5.4 Fair use et monitoring

Wording produit : *"Jusqu'à 15h de podcasts transcrits par mois. Usage fair use : la transcription est prévue pour un usage personnel normal. Les imports massifs automatisés sont interdits."*

**Monitoring individuel** (DynamoDB tracking + CloudWatch alarms):

| Tier | Warning (coût/user) | Hard block | Action |
|------|-------------------:|-----------:|--------|
| Audio-Heavy | 7 € | 10 € | Throttle (1 import audio/h); email "utilisation intensive détectée" |

**Hard caps mensuels anti-abus Audio-Heavy** :

- Minutes audio : **900** (plancher).
- Articles : **1 500**.
- Documents : **300**.
- Durée max d'un média audio : **180 min**.

---

## 6. Mois gratuit: que coûte-t-il ?

**Stratégie** : mois gratuit sur le tier **Mix** (ni Text-Only ni Audio-Heavy) avec hard cap 300 min audio + 300 articles + 50 docs.

Infra amortie à 100 users = **0,145 €/user**. Document free tier actif (normal en phase launch).

| Comportement mensuel | Coût média | Coût total (+ infra 0,145) |
|---------------------|-----------:|---------------------------:|
| 5 podcasts 45 min + 50 articles + 10 docs | 0,988 € | 1,13 € |
| 10 podcasts 45 min + 100 articles + 20 docs | 1,976 € | 2,12 € |
| **300 min audio (hard cap) + 200 articles + 30 docs** | 2,143 € | **2,29 €** |
| **300 min audio + 300 articles (hard cap) + 50 docs (hard cap)** | 2,968 € | **3,11 €** |
| 100 YouTube + 200 articles + 50 docs (text-heavy, 0 audio) | 1,538 € | 1,68 € |

**Lectures** :

- Un user free trial "raisonnable" (10 podcasts + 100 articles + 20 docs) = ~**2,1 €/mois** de coût.
- Le hard cap 300 min audio + 300 articles + 50 docs limite le coût max à ~**3,1 €/user** (abuse tenace).
- Un user text-heavy sans audio (200 articles + 50 docs + 100 YouTube) = ~**1,7 €/mois** (découverte naturelle du tier Text-Only 3€).

**Le marketing "1 mois gratuit sans quota" est défendable** sous condition d'appliquer les hard caps techniquement sans les communiquer. Le risque financier du free trial reste **acceptable** (2-3 €/user).

---

## 7. Comparaison 3 tiers : tableau synthétique

| Critère | **Text-Only 3€** | **Mix 5€** | **Audio-Heavy 9€** |
|---------|-----------------|-----------|-------------------|
| **Prix TTC/mois** | 3 € | 5 € | 9 € |
| **Revenu net/user** | 2,125 € | 3,542 € | 6,375 € |
| **Quota audio** | **0 min** (transcription interdite) | **300 min** (5h) | **900 min** (15h) |
| **Articles/docs** | Illimité (hard cap 500/100) | Illimité (hard cap 500/100) | Illimité (hard cap 1500/300) |
| **YouTube captions** | ✅ Inclus (95% gratuit) | ✅ Inclus | ✅ Inclus |
| **Coût moyen/user @100u** | 1,33 € (150 articles + 30 docs + 20 YouTube) | 1,86 € (300 min + 100 articles + 15 docs + 10 YouTube) | 3,63 € (900 min + 50 articles + 10 docs + 20 YouTube) |
| **Marge % @100u** | **+37,2 %** | **+47,4 %** | **+43,1 %** |
| **Persona** | Lecteur compulsif (newsletters/articles/PDFs/YouTube) | Étudiant/pro équilibré (mix articles + podcasts modérés) | Passionné podcast (écoute quotidienne) |
| **Différenciation** | **AUCUNE transcription autorisée** → coût unitaire très bas | Accès modéré à la transcription (5h/mois) | Accès élargi à la transcription (15h/mois) |
| **Parcours upgrade** | Découvre le besoin podcast → upgrade Mix +2€ | Devient accro podcasts → upgrade Audio-Heavy +4€ | Tier max |

---

## 8. Positionnement concurrent (données vérifiées 2026-05-01 + 2026-05-13)

| App | Prix mensuel | Annuel effectif | Limite clé | Persona |
|-----|-------------:|----------------:|------------|---------|
| **Snipd Free** | 0 $ | — | 2 épisodes AI/semaine | Freemium |
| **Snipd Premium** | 6,99 $ | — | 900 min AI upload/mois | Audio-heavy |
| **Otter Free** | 0 $ | — | 300 min/mois + 3 imports lifetime | Freemium |
| **Otter Pro** | 16,99 $ mensuel | 8,33 $/mois (annuel −50%) | 1 200 min recording + 10 imports/mois | Audio-heavy |
| **Readwise Lite** | — | 5,59 $/mois (annuel) | Highlights seulement | Text-heavy |
| **Readwise Full** | 12,99 $ mensuel | 9,99 $/mois (annuel) | + Reader app | Text-heavy |
| **Recall Free** | 0 $ | — | 10 AI cards/mois | Freemium |
| **Recall Plus** | — | 10 $/mois (annuel) | "Living knowledge base" | Mix |
| **Notre Text-Only** | **3 € (~3,50 $)** | — | 0 min transcription, illimité text/YouTube | **Text-heavy** |
| **Notre Mix** | **5 € (~5,80 $)** | — | 300 min audio + illimité text | **Mix** |
| **Notre Audio-Heavy** | **9 € (~10,50 $)** | — | 900 min audio + illimité text | **Audio-heavy** |

**Analyse** :

- **Text-Only 3€** : **70% moins cher** que Readwise Full (9,99 $/mois annuel) pour un persona similaire (lecteur). Aucun concurrent ne propose un tier pure-text à ce prix.
- **Mix 5€** : comparable à Readwise Lite (5,59 $/mois annuel) mais **ajoute 300 min audio** (podcasts) que Readwise n'a pas. Positionnement unique.
- **Audio-Heavy 9€** : aligné sur **Snipd Premium (6,99 $)** à quota identique (900 min) mais **ajoute articles/docs illimités** que Snipd n'a pas. **47% moins cher** qu'Otter Pro mensuel (16,99 $) à quota légèrement inférieur (900 vs 1200 min).

**Notre différenciation clé** :

1. **Seul acteur à proposer un tier Text-Only à 3€** (marché sous-servi : lecteurs compulsifs qui ne consomment pas de podcasts).
2. **Multi-média intégré** : articles + podcasts + YouTube + documents dans tous les tiers (sauf Text-Only qui exclut l'audio). Les concurrents sont mono-thème (Snipd = audio only, Readwise = text only).
3. **Pricing transparent mensuel** : pas besoin d'engagement annuel pour avoir un prix attractif.

---

## 9. Rate limiting chiffré pour implémentation

### 9.1 Rate limits fournisseurs externes (inchangé)

| Fournisseur | Plan | Limite |
|-------------|------|--------|
| **Deepgram** pay-as-you-go | 10 concurrent requests | 8 concurrent worker max |
| **OpenAI Tier 1** | 500 RPM, 200k TPM par modèle | 400 RPM par modèle |
| **LlamaParse** free/starter | ~100 RPM estimé | 80 concurrent |
| **Algolia Build** | 10k searches/mois | 8k searches/mois safe |

### 9.2 Rate limits applicatifs par tier

| Action | Text-Only | Mix | Audio-Heavy |
|--------|----------:|----:|------------:|
| Imports audio / jour | **0** (bloqué) | 10 (≤ 60 min) | 20 (≤ 90 min) |
| Imports texte / jour | 30 | 30 | 100 |
| Imports document / jour | 10 | 10 | 30 |
| Imports texte / minute | 5 | 5 | 10 |
| API calls / minute | 15 | 30 | 60 |

### 9.3 Hard caps mensuels anti-abus

| Ressource | Text-Only | Mix | Audio-Heavy |
|-----------|----------:|----:|------------:|
| **Minutes audio total** | **0** (bloqué backend) | 300 | 900 |
| Articles | 500 | 500 | 1 500 |
| Documents | 100 | 100 | 300 |
| YouTube | 100 | 100 | 200 |
| Durée max d'un média audio | N/A | 180 min | 180 min |

### 9.4 Monitoring de coût individuel

Alertes CloudWatch sur coût par user (DynamoDB tracking):

| Tier | Warning (coût/user) | Hard block | Action |
|------|-------------------:|-----------:|--------|
| Free trial | 3 € | 5 € | Bloquer nouveaux imports; email |
| Text-Only | 2,5 € | 3,5 € | Throttle (5 imports/j); email |
| Mix | 4 € | 6 € | Throttle (1 audio/h); email |
| Audio-Heavy | 7 € | 10 € | Throttle + contact owner |

---

## 10. Analyse de sensibilité

5 paramètres incertains. Pour chacun, impact sur la marge **Mix 5 € @ 300 min @ 100 users** (baseline **+48,7 %**).

| Paramètre | Baseline | Variante pessimiste | Impact marge |
|-----------|----------|---------------------|--------------|
| Tokens FR par minute | 250 | 300 (+20%) | −2,0 pts → +46,7 % |
| Taux captions YouTube gratuites | 95 % | 75 % | −0,2 pts (YouTube ne compte pas dans quota audio) |
| Stripe pass-through (si future Web) | 0 (IAP) | 2,9% + 0,25€ | −7 pts → +41,7 % |
| Rétries LLM (JSON flashcards) | 0% | 15% retry avg | −1,2 pts → +47,5 % |
| Document free tier épuisé dès M1 | Non | Oui | −0,2 pts (text-heavy worst-case) |
| Base users (100 → 25u au launch réel) | 100u | 25u | **−22 pts → +26,7 %** (runway founder) |
| **Algolia Build dépassé (1 GB cap)** | 0 € @100u | **116 €/mois** @1000u Y2 (Grow overages) | **−30 pts → +18,7 %** |

**Paramètres dominants** : **le volume d'users** et **le passage Algolia Build → Grow**.

- À **25-50 users**, la marge est fragile (+26,7% Mix @25u) ; c'est un problème de **runway**, pas de pricing. Il faut absorber cette perte comme CAC.
- **Algolia Build cap 1 GB** = headroom jusqu'à ~130 users. Au-delà, passage obligatoire vers **Algolia Grow** (~116 €/mois Y2 @1000u) qui impacte lourdement la marge. À ce stade, migrer vers **self-hosted Typesense** (ECS/EC2, ~50 €/mois) ou vers **Meilisearch Cloud** (~20-26 €/mois) redevient économiquement nécessaire.

---

## 11. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Algolia Build 1 GB cap dépassé avant 130 users** (users heavy-podcast avec >250 docs chacun) | Élevé (passage Grow prématuré, +116 €/mois) | Monitorer usage index quotidien; compresser transcripts (gzip); chunking agressif (chunks de 6-7 KB au lieu de 9 KB); ou migration anticipée vers Typesense self-hosted |
| Tokens FR plus élevés que 250/min | ~2 pts marge | Mesurer empiriquement sur 10 transcripts réels et recalibrer |
| Captions YouTube indisponibles pour contenu niche | Minute audio → quota Mix/Audio-Heavy | Compter dans le quota audio dès le fallback; déjà prévu |
| Fin du free tier AWS 12 mois | ~1-2 pts marge | Optimisation logs retention, S3 lifecycle, reserved instance EC2 à M10 |
| Volume users < 50 au launch | Marge négative (runway) | Accepter coût d'acquisition; étendre phase pré-launch |
| App Store rejects subscriptions model | Blocking | Utiliser StoreKit 2 / Google Play Billing v6 — standards, pas de raison d'être rejeté |
| Churn mensuel 8-10% | LTV | À 5 € net 3,54 € × (1/0,10) = LTV ~35 €. CAC doit rester < 10 € pour LTV/CAC ≥ 3 |
| **Confusion user Text-Only** (user essaie d'importer un podcast et se fait bloquer) | Moyen (frustration, churn) | Wording clair dans l'app : "Ce forfait ne prend pas en charge les podcasts. Passez au forfait Mix pour ajouter des podcasts." + suggestion d'upgrade au moment du blocage |

---

## 12. Recommandation finale

### 12.1 Offre à lancer

1. **Mois gratuit**
   - 1 mois, tier **Mix** (300 min audio + text illimité).
   - Hard caps techniques : 300 min audio, 300 articles, 50 documents.
   - Monitoring coût individuel avec alerte à 3 € et hard block à 5 €.

2. **Text-Only 3 € TTC / mois**
   - **0 minute de transcription autorisée** (bloqué backend).
   - Articles, documents, YouTube avec captions, posts réseaux sociaux illimités (hard cap 500 articles/100 docs).
   - Revenu net: 2,125 €. Marge worst-case @100u: **+37,2 %** (150 articles + 30 docs + 20 YouTube).
   - Persona : "Lecteur" (étudiant/pro text-heavy).

3. **Mix 5 € TTC / mois**
   - **300 min audio/mois** (5h = ~10 podcasts de 30 min).
   - Articles, documents, YouTube illimités (hard cap 500 articles/100 docs).
   - Revenu net: 3,542 €. Marge worst-case @100u: **+47,4 %** (300 min + 100 articles + 15 docs + 10 YouTube).
   - Persona : "Équilibré" (étudiant/pro mix).

4. **Audio-Heavy 9 € TTC / mois**
   - **900 min audio/mois** (15h = ~30 podcasts de 30 min ou ~20 podcasts de 45 min).
   - Articles, documents, YouTube illimités (hard cap 1500 articles/300 docs).
   - Revenu net: 6,375 €. Marge worst-case @100u: **+43,1 %** (900 min + 50 articles + 10 docs + 20 YouTube).
   - Persona : "Passionné podcast" (audio-heavy).

### 12.2 Différenciation clé

- **Seul acteur à proposer un tier Text-Only à 3€** (0 transcription) → marché sous-servi (lecteurs compulsifs).
- **Multi-média intégré** : articles + podcasts + YouTube + documents dans tous les tiers (sauf Text-Only).
- **Pricing transparent mensuel** : pas d'engagement annuel obligatoire.
- **Parcours d'upgrade naturel** : Text-Only 3€ → Mix 5€ (+2€) → Audio-Heavy 9€ (+4€).

### 12.3 Contraintes opérationnelles

- **Architecture VM unique `t4g.small` + Algolia Build free** : le code docker-compose existant se déploie tel quel sur EC2. Aucune dépendance Typesense Cloud (supprimée).
- **Algolia Build cap 1 GB** : headroom jusqu'à ~130 users heavy-podcast (200 docs/user). Monitoring quotidien index size requis. Plan de migration vers Algolia Grow (~116 €/mois) ou vers self-hosted Typesense/Meilisearch (~20-50 €/mois) à préparer pour Y2.
- **Mesure empirique des tokens FR** dans les 4 premières semaines de Phase 1 pour recalibrer. Si la mesure donne 300 tokens/min au lieu de 250, la marge glisse de ~2 pts mais reste au-dessus de 40%.
- **Monitoring coût individuel** dès le jour 1 (DynamoDB tracking + CloudWatch alarms).
- **Bloquer le creep d'architecture** : refuser toute intro de NAT Gateway, RDS, ALB tant que la VM unique suffit.

### 12.4 Ce que cet arbitrage ne tranche pas

- Pas de Web app pour V1 → si Web vient plus tard, refaire le calcul avec Stripe (marge −7 pts).
- Pas de plan annuel en V1 (complexité store-billing). À reconsidérer si churn >12%.
- Pas de plan Family / multi-device partage.
- Pas de modèle étudiant (−50% type Readwise).
- Pas d'offre Lifetime (risque cash flow).

### 12.5 Impact économique suppression Typesense → Algolia free

| Métrique | 4ᵉ passe (Typesense Cloud 2 GB) | 5ᵉ passe (Algolia Build free) | Différentiel |
|----------|--------------------------------:|-------------------------------:|-------------:|
| Coût search/mois @100u | 43 € | **0 €** | **−43 € (−100%)** |
| Coût infra total/mois @100u | 57,5 € | **14,5 €** | **−43 € (−75%)** |
| Coût infra/user @100u | 0,575 € | **0,145 €** | **−0,43 € (−75%)** |
| Marge Mix 5€ @100u | +27,0 % (marge 0,96 €) | **+48,7 % (marge 1,72 €)** | **+21,7 pts (+79%)** |
| Headroom users avant migration | ~100-500u (scaling Typesense) | **~130u** (cap Algolia 1 GB) | Migration plus précoce en Y2 |

**Trade-off accepté** : Algolia Build free économise **516 €/an** en phase launch mais impose une **migration obligatoire** en Y2 (passage Grow ~116 €/mois ou migration vers Typesense/Meilisearch self-hosted ~20-50 €/mois). Ce trade-off est **excellent pour V1** (maximise runway launch) et le plan de migration Y2 est clair.

---

## 13. Sources

### Projet

- `docs/research/task-72-llm-artifact-benchmark/README.md` (owner_decision: ok, 2026-04-29)
- `docs/research/task-90-document-parser-benchmark/README.md` (owner_decision: ok)
- `docs/research/task-73-cloud-provider-analysis/README.md` (owner_decision: ok)
- `docs/research/task-53.1-lexical-search/README.md` (owner_decision: ok Algolia, 2026-05-12)
- `docs/research/task-65-pricing-v1-benchmark/README.owner-rejected-2026-05-13.md` (4ᵉ passe rejetée)
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`

### Fournisseurs

- OpenAI pricing: https://openai.com/api/pricing/
- Deepgram rate limits: https://developers.deepgram.com/docs/rate-limits
- LlamaParse pricing: https://llamaindex.ai/pricing
- Unstructured pricing: https://unstructured.io/pricing
- **Algolia pricing: https://www.algolia.com/pricing/** (consulté 2026-05-12)
- **Algolia service limits: https://support.algolia.com/hc/en-us/articles/4406981897617** (consulté 2026-05-12)
- USD/EUR spot 2026-05-13: 0,86 (approximation)

### Distribution & fiscalité

- Apple Small Business Program: https://developer.apple.com/app-store/small-business-program/
- Google Play service fees: https://support.google.com/googleplay/android-developer/answer/112622

### Concurrents (vérifiés 2026-05-01)

- Snipd: https://www.snipd.com/pricing
- Otter.ai: https://otter.ai/pricing
- Readwise: https://readwise.io/pricing
- Recall: https://www.recall.it/pricing

---

**Reproductibilité**: tous les chiffres de ce document sont générés par `compute.py` dans ce dossier (à mettre à jour avec la nouvelle structure 3 tiers). Modifier une hypothèse → relancer → diffs identifiés.

**Document généré**: 2026-05-13 — 5ᵉ passe du benchmark task-65.

**Changes vs 4ᵉ passe (2026-05-13)**: 
1. **Suppression Typesense Cloud** (43 €/mois) → **Algolia Build free tier** (0 € jusqu'à 1 GB index / ~130 users).
2. **Structure 3 tiers** basée sur 3 personas : **Text-Only 3€** (0 transcription), **Mix 5€** (300 min audio), **Audio-Heavy 9€** (900 min audio).
3. Recalcul complet des marges avec nouvelle infra (14,5 €/mois @100u vs 57,5 €/mois 4ᵉ passe).
4. Tier Text-Only = différenciation majeure (seul acteur à proposer un tier pure-text à 3€, marge +57,5%).
5. Impact économique Algolia free : **+21,7 pts de marge** sur Mix 5€ @100u (48,7% vs 27,0% en 4ᵉ passe).
