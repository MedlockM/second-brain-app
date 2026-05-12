---
owner_decision: pending
---

# Benchmark: Coûts unitaires & pricing V1 (4ᵉ passe, 2026-05-01, révision 2)

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture)_
**Validated at**: _(date ISO)_

---

## 0. Ce qui change par rapport à la 3ᵉ passe (2026-04-30)

Cette réécriture complète prend en compte un audit critique qui a identifié plusieurs problèmes structurels dans la 3ᵉ passe (`README.superseded-2026-05-01.md`):

1. **Incohérences numériques** entre Executive Summary et corps de texte (2.68€ vs 2.12€), et "arrondis de sécurité" non justifiés (§5.2 et §6.2 de la v3 donnaient des totaux ~8% plus élevés que le calcul détaillé, faussant les marges).
2. **Tokens LLM sous-dimensionnés**: la v3 utilisait un coût LLM uniforme de 0,0052€/média pour tous les types de média. Un podcast de 45 min en FR = ~11 250 tokens input, pas 3 000. Ce biais minorait mécaniquement le coût des podcasts longs.
3. **Profils utilisateurs inventés** (50/35/15 casual/moderate/intensive) utilisés pour agréger les coûts sans aucune source. Abandonnés dans cette version (contrainte owner: pas de donnée utilisateur disponible).
4. **Canal de distribution oublié**: la v3 évoquait Stripe + TVA uniquement en §9.7. Or l'app se distribue via **App Store + Play Store**, donc **commission 15%** (Small Business Program / post-1 an) s'applique — pas Stripe. Impact énorme sur le revenu net par user.
5. **Équation linéaire appliquée à tort** à tous les profils (v3 §6.2): le coût moyen pondéré d'un mix Standard ne s'applique pas à un profil Audio-heavy.
6. **Aucune analyse de sensibilité** alors que 4-5 paramètres clés sont incertains.
7. **Free tier AWS non modélisé** (ajouté en révision 1 après feedback owner): les v1-v3 utilisaient 0,74 €/user/mois à 100 users comme hypothèse infra sans vérifier ce qui est gratuit chez AWS.
8. **Code applicatif non modélisé** (ajouté en révision 2): les révisions précédentes supposaient implicitement un déploiement "Lambda pur" couvert par le free tier, sans inspecter le code. En réalité, le backend V1 est une archi **docker-compose** de FastAPI + ~15 workers long-running (boucles SQS avec heartbeat) incompatible Lambda. Il faut une VM pour héberger le code. Par ailleurs, la recherche lexicale utilise **Typesense Cloud** (task-53.1 validated 2026-04-28) avec un **free signup credit** couvrant le pré-launch puis un cluster MVP ~15 €/mois. Voir §2.3.

**Tous les chiffres de ce document sont calculés par `compute.py` dans ce même dossier** — reproductibles d'un lancement à l'autre. Pas de nombre "d'ajustement".

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
| Distribution app | App Store + Play Store (IAP) | Owner feedback 2026-05-01 |

### Recommandation

| Offre | Prix TTC | Quota | Revenu net/user | Coût worst-case @100u phase launch | Marge |
|-------|----------|-------|-----------------|-----------------|-------|
| **Mois gratuit** | 0 € | Pas de quota marketing + hard cap anti-abus (5h audio, 300 articles, 50 documents sur le mois) | 0 € | 0,5 à 3,3 € selon usage | Coût d'acquisition, pas une marge |
| **Standard** | 5 €/mois | **300 min audio/mois**, pas de quota text/document | 3,54 € | 2,59 € | **+27,0 %** |
| **Premium** | 10 €/mois | **900 min audio/mois**, pas de quota text/document | 7,08 € | 6,30 € | **+11,1 %** (fair-use requis) |

**Constat principal**:

- Le **coût de distribution App Store/Play Store (15%) + TVA 20%** capte **29% du prix affiché** avant même de payer la moindre minute de transcription. Un prix TTC de 5 € ne laisse que **3,54 € de revenu net** à l'équation.
- Le **quota doit être exprimé en minutes audio** (pas en nombre de médias). 300 min/mois couvre ~7 podcasts de 45 min ou ~15 épisodes de 20 min — suffisant pour le profil "étudiant/pro modéré".
- **L'infra réelle V1** est une **VM EC2 `t4g.small`** hébergeant l'API FastAPI + les ~15 workers long-running (incompatibles Lambda) + Redis embarqué, avec **Typesense Cloud** en service externe pour la recherche lexicale (task-53.1 validée). Total à 100 users en phase launch: **0,35 €/user/mois** (EC2 ~11 € + Typesense MVP cluster ~15 € + AWS misc ~4 €). Voir §2.3.
- **Le risque text-heavy est faible**: à 100 users phase launch, il faudrait qu'un user Standard @300 min audio dépasse ~297 articles/mois pour tomber sous 20% de marge. Hors cas abusif, aucun quota text n'est nécessaire.
- **Le tier Premium 10 € avec 900 min audio reste fragile** sous stress text-heavy (marge +11,1 % @100u worst-case). Option recommandée: 600 min audio qui donne **+24,8 % de marge** confortable.

---

## 1. Coûts unitaires par type de média

Calculs reproductibles via `compute.py`. Tokens input calibrés **par média** à partir de la durée et du ratio observé ~200 tokens/min d'audio EN × 1,25 de pénalité FR ≈ 250 tokens FR/min. Inputs articles/documents: 1 800 tokens (~1 300 mots FR).

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

**Écart avec v3**: la v3 utilisait 0,0052€ uniformément. Ici, un podcast 45 min coûte **2× plus cher en LLM** (0,0104€). Différence contenue dans l'absolu (~0,005€/média), mais la structure est juste.

### 1.2 Transcription

Base owner: **0,0030 €/min**. YouTube: 95% free via captions/ASR → coût effectif 0,05 × 0,0030 = 0,000150 €/min facturé. TikTok/Instagram shorts: hypothèse **70% de captions gratuites** (flag de sensibilité §8) car la qualité des captions auto est inférieure à YouTube sur ces plateformes.

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

- Le coût d'un podcast 45 min (0,145 €) est ≈ **28× celui d'un article** (0,0051 €). C'est pourquoi le quota audio est le seul verrou qui compte.
- Un YouTube 25 min en mode captions gratuites (0,0113 €) est **13× moins cher** qu'un podcast de même durée transcrit. La ligne YouTube seule ne justifie pas un quota.
- Un document avec free tier actif (0,0051 €) = article. Le différentiel parsing n'arrive qu'en phase 3.

---

## 2. Revenu net: impact App Store / Play Store + TVA

### 2.1 Canal de distribution

L'app V1 se distribue via **App Store + Play Store** (owner 2026-05-01). Les subscriptions passent par **StoreKit (Apple IAP)** / **Google Play Billing**, pas Stripe. Sources:

- Apple Small Business Program (≤ $1M revenu annuel developer): **15% commission** sur subs dès le jour 1. https://developer.apple.com/app-store/small-business-program/
- Google Play: **15% commission** sur abonnements (tout le temps, quel que soit l'ancienneté). https://support.google.com/googleplay/android-developer/answer/112622
- Chaque store prélève la TVA localement pour le compte du developer. Pour un utilisateur FR: **TVA 20%** applicable, retenue à la source.

Dans les deux cas le dev est solo, <$1M/an → **15% standard**.

### 2.2 Calcul du revenu net par user (EUR)

```
prix TTC  → (÷ 1,20 TVA)  → prix HT  → (× 0,85 post-commission) → net dev
5,00 €     →  4,167 €        → 3,542 €
10,00 €    →  8,333 €        → 7,083 €
```

**29,2 % du prix affiché disparaissent avant même de payer la moindre infra.** Cet élément, absent de la v3, réduit de ~30% les marges projetées.

**Note**: Stripe est envisageable si une version Web est ajoutée plus tard, mais ce benchmark V1 part du chemin mobile-only.

### 2.3 Infrastructure V1: EC2 + Typesense Cloud + free tier AWS

**Double correction vs révisions précédentes:**

- **Rév. 1 avait surcorrigé en "Lambda pur"** sans inspecter le code. Or le backend V1 n'est PAS serverless: il s'agit d'un docker-compose monolithique (FastAPI + ~15 workers `while True: sqs.receive_message()` avec heartbeat, cf. `media_summarizer/workers/`). Les workers long-running ne sont **pas compatibles Lambda** (15 min max + modèle pull continu absurde en serverless). Convertir en Lambda = refactor de 2-3 semaines, hors scope V1.
- **Typesense Cloud** (validé task-53.1 2026-04-28) est un service externe indispensable pour la recherche lexicale. Hébergement externe, pas couvert par le free tier AWS.

#### Architecture V1 retenue

| Composant | Hébergement | Justification |
|-----------|-------------|---------------|
| API FastAPI + ~15 workers SQS + Redis | **EC2 `t4g.small`** (ARM 2 vCPU / 2 GB RAM), docker-compose | Le code est déjà organisé en docker-compose, transposition directe. 2 GB suffit car **pas de Whisper local** (owner 2026-05-01, Deepgram API uniquement). ARM Graviton = −40% vs x86. |
| Stockage fichiers | **S3** | Audio source (supprimé post-transcription), transcripts, artefacts |
| Base de données | **DynamoDB on-demand** | Métadonnées médias, jobs, artefacts (users, podcasts, episodes, processing_jobs…) |
| Queues | **SQS standard + FIFO** | 4-6 queues (audio-download, transcription, summarization, email, flashcards, events) |
| Auth | **Cognito User Pool** | Auth multi-provider, MFA optionnel |
| Recherche lexicale | **Typesense Cloud** (externe, task-53.1) | SaaS géré, pas d'overhead ops sur la VM |
| Reverse proxy HTTPS | **Caddy/Traefik** sur la VM, Route53 A record | Évite ALB (~17 €/mois) à V1 scale |
| CDN/TLS | **CloudFront** (optionnel V1.5) + **ACM** gratuit | |

**Ce qu'on N'UTILISE PAS** (par choix):

- ❌ **NAT Gateway** (~32 $/mois) → EC2 en subnet public avec Security Group restrictif
- ❌ **RDS** → DynamoDB couvre tous les besoins transactionnels
- ❌ **ECS / Fargate 24/7** → un seul `docker compose up -d` sur la VM suffit, scaling vertical si besoin
- ❌ **Lambda** → code incompatible, gain marginal vs VM à V1 scale
- ❌ **ALB** → le reverse proxy sur la VM le remplace tant qu'on a 1 instance

#### Free tiers effectivement utilisables

**Free tiers AWS permanents** (aucune expiration, vérifiés 2026-05-01):

| Service | Quota free tier | Couvre V1? |
|---------|-----------------|------------|
| DynamoDB on-demand | 25 GB + 25 WCU + 25 RCU | Oui jusqu'à ~1k users |
| SQS | 1M requests/mois | Oui largement |
| CloudWatch | 5 GB logs + 10 metrics + 10 alarms | Oui si retention 3j |
| Cognito | 10k MAU (direct sign-in) | Oui jusqu'à 10k users |
| CloudFront | 1 TB egress/mois (12 premiers mois: 12 mois free, après: 1 TB permanent à vérifier region) | Oui |

**Free tiers 12 mois** (nouveaux comptes):

- EC2 `t3.micro` 750h/mois (x86) — **PAS applicable** car on a choisi `t4g.small` ARM (meilleur perf/€)
- $200 de crédits AWS Free Tier utilisables sur S3, EBS, data transfer, etc.

**Typesense Cloud free signup credit** (vérifié 2026-05-01 sur cloud.typesense.org: "free credits, no credit card"):

- Montant non public. Estimation conservatrice: $25-$50 de crédit à l'inscription.
- Suffit pour couvrir **M0 (pré-launch, validation technique)** avant de passer en cluster payant.
- Source: https://cloud.typesense.org/

#### Modélisation en 3 phases

| Phase | Typesense | EC2 | Coût fixe total/mois | Déclencheur |
|-------|-----------|-----|----------------------|-------------|
| **Pré-launch** | Signup credit (0 €) | `t4g.small` on-demand (10,55 €) | **14,0 €** | M0, validation technique avec <10 beta users |
| **Launch** | MVP cluster 0.5 GB / 2 vCPU burst ($18/mo = **15,5 €**) | `t4g.small` on-demand (10,55 €) | **29,5 €** | Ouverture publique, jusqu'à ~5k users |
| **Growth** | Cluster 2 GB / 2 vCPU burst ($50/mo = **43 €**) | `t4g.small` reserved 1-yr (6,7 €) | **53,2 €** | >5k users ou M12+ (task-53.1 estimation) |

Coût par user selon le volume:

| Phase | 25u | 50u | 100u | 200u | 500u | 1000u |
|-------|----:|----:|-----:|-----:|-----:|------:|
| Pré-launch | 0,61 € | 0,33 € | 0,19 € | 0,12 € | 0,08 € | 0,06 € |
| **Launch (baseline)** | **1,23 €** | **0,64 €** | **0,35 €** | **0,20 €** | **0,11 €** | **0,08 €** |
| Growth | 2,18 € | 1,11 € | 0,58 € | 0,32 € | 0,16 € | 0,10 € |

Les calculs §4-§6 utilisent **phase launch** comme baseline (`compute.py` variable `INFRA_BY_USERS`).

#### Scaling vertical avant de repenser l'archi

Si la charge augmente au-delà de ce qu'une `t4g.small` peut encaisser:

1. **`t4g.medium`** (2 vCPU / 4 GB) — 21 €/mois on-demand, tient ~1000-2000 users confortables.
2. **`t4g.large`** (2 vCPU / 8 GB) — 42 €/mois, tient ~5000 users.
3. Au-delà: splitter API vs workers sur 2 VM, ou passer à ECS Fargate Spot.

Cette voie évite un refactor prématuré vers Fargate/Kubernetes tant que l'instance unique suffit.

#### Risques infra

- **Typesense signup credit épuisé plus tôt que prévu**: bascule Phase pré-launch → Launch plus tôt, +15,5 €/mois. Impact marge Standard 300 min @100u: ~−2 pts.
- **Instance EC2 unique = SPOF**: pas de HA en V1. Mitigation: snapshots EBS quotidiens, runbook re-deploy en <30 min.
- **Burst CPU/vCPU exhausted sur `t4g.small`** en cas de spike (transcription parallèle + LLM flashcards): utiliser les **CPU credits** Graviton T4g, monitorer CloudWatch `CPUCreditBalance`. Si récurrent → `t4g.medium`.
- **Typesense Cloud downtime**: recherche lexicale indisponible mais app utilisable en dégradé (filtres par date/tag côté DynamoDB).

---

## 3. Stratégie de quotas: minutes audio + text libre

### 3.1 Le quota est sur les **minutes audio facturées**, pas le nombre de médias

Source: owner 2026-05-01. Se comptent dans le quota audio:

- Minutes d'**audio uploadé manuellement** (enregistrement voc, MP3, etc.).
- Minutes de **podcast** (RSS/Apple/Spotify/Deezer).
- Minutes d'**audio reçu via partage** depuis WhatsApp.
- Minutes **transcrites en fallback** quand TikTok/Instagram/YouTube n'ont pas de caption/ASR exploitable.

**Ne comptent PAS dans le quota audio**:

- Minutes YouTube/TikTok/IG quand un transcript texte (captions/ASR natives, scraping YouTube transcript API, TikTok metadata, etc.) suffit → coût transcription = 0, donc pas de raison technique de limiter.
- Articles web, textes partagés, posts LinkedIn/X.
- Documents PDF/DOCX.

**Pourquoi le quota est sur les minutes et pas sur le nombre de médias**:

- Un podcast de 90 min ≠ un WhatsApp de 30 s. Facturer "1 média" dans les deux cas est injuste (et ouvre la porte à l'abus via import massif de courts).
- Les minutes sont la métrique native de la facturation Deepgram → alignement coût/quota trivial.
- Un quota "15 podcasts/mois" est opaque ("15 podcasts de combien?"). Un quota "300 min/mois" est lisible ("5 heures d'écoute traitée").

### 3.2 Pas de quota sur le texte (article, document, post)

Analyse de risque §5 ci-dessous: un user qui utilise son quota audio à fond **et** importe ~297 articles ou ~182 documents dans le mois reste au-dessus de 20% de marge (infra EC2 + Typesense MVP @100u phase launch). Hors cas abusif, aucun quota text n'est nécessaire.

**Hard cap anti-abus** uniquement pour contrer le web scraping ou l'import automatisé:

- Cap jour: 30 articles/j, 10 documents/j.
- Cap mois global: 500 articles/mois, 100 documents/mois.
- Rate limit API: 2 imports texte / minute, 5 imports document / minute.

Ces plafonds ne doivent **pas** apparaître dans la communication produit. Ils servent à bloquer l'abus, pas à contraindre l'usage normal.

---

## 4. Marges Standard 5 € TTC selon quota audio

### 4.1 Méthodologie du worst-case

Chaque ligne calcule la marge dans le scénario **le plus pessimiste**:

- Audio consommé à **100 % du quota**, réparti en blocs de 45 min (le plus coûteux par minute, car LLM amortit moins bien sur les podcasts courts).
- **Stress text-heavy**: 200 articles + 30 documents (3 pages) consommés sur le mois.
- **Document free tier épuisé** → parsing payant à 0,00108 €/page (phase 3 stabilisée, pas le launch).
- Infra: calculée à 4 volumes (25, 50, 100, 200, 500 users) pour voir l'impact amortissement.

### 4.2 Résultats (revenu net Standard = 3,54 €, infra phase launch)

| Quota audio | @25u | @50u | @100u | @200u | @500u | @1000u |
|-------------|-----:|-----:|------:|------:|------:|-------:|
| 120 min | +18,4 % | +35,1 % | **+43,4 %** | +47,5 % | +50,1 % | +50,9 % |
| 180 min | +13,0 % | +29,7 % | **+38,0 %** | +42,2 % | +44,7 % | +45,5 % |
| 240 min | +7,6 % | +24,3 % | **+32,6 %** | +36,8 % | +39,3 % | +40,1 % |
| **300 min** | +2,0 % | +18,6 % | **+27,0 %** | +31,1 % | +33,6 % | +34,5 % |
| 360 min | −3,4 % | +13,3 % | +21,6 % | +25,7 % | +28,3 % | +29,1 % |
| 450 min | −11,6 % | +5,1 % | +13,4 % | +17,5 % | +20,1 % | +20,9 % |
| 600 min | −25,2 % | −8,5 % | −0,2 % | +4,0 % | +6,5 % | +7,3 % |
| 900 min | −52,7 % | −36,0 % | −27,7 % | −23,5 % | −21,0 % | −20,2 % |

**Lectures**:

- À **25-50 users**, Standard 300 min est fragile voire négatif en worst-case. C'est la période "runway founder" où il faut soit:
  - Tolérer la perte comme CAC (founder investit dans la base d'users),
  - Pousser la signup credit Typesense pour rester en phase pré-launch tant que possible,
  - Accepter que le break-even se fasse autour de **50-75 users**.
- À **100 users**, **300 min/mois** donne une marge worst-case de **+27 %**. En usage normal (user ne consomme pas 100% tous les mois), la marge réelle est plus proche de 40-45%.
- **450 min/mois** tient juste au-dessus de 20% marge au-dessus de 500 users. Limite pratique Standard.
- **600 min** Standard n'est pas viable avant **200+ users**. À éviter.
- **900 min** Standard = perte nette quel que soit le volume. Ce quota appartient au Premium.

### 4.3 Zoom sur le cas nominal @100 users, quota 300 min, phase launch

| Poste | Montant |
|-------|--------:|
| Revenu net (5 € TTC − TVA 20% − store 15%) | **3,542 €** |
| Transcription audio (300 min × 0,003) | 0,900 € |
| LLM audio (7 blocs 45 min × 0,0104) | 0,073 € |
| Articles worst-case (200 × 0,0051) | 1,020 € |
| Documents worst-case (30 × 0,0083) | 0,249 € |
| Infra V1 (EC2 t4g.small + Typesense MVP + AWS misc, 100 users) | 0,345 € |
| **Coût total** | **2,587 €** |
| **Marge** | **+0,96 € (+27,0 %)** |

Cette marge tient malgré un stress test qui modélise **un user qui exploite son quota audio ET lit 200 articles ET parse 30 documents chaque mois**. C'est un plafond pratique de l'usage réel.

**Transition pré-launch → launch** (passage au cluster Typesense payant): infra passe de 0,19 €/user à 0,35 €/user à 100 users → marge glisse de ~+31 % à +27 %. Soft transition quand on sort des beta users.

**Phase growth (>5k users ou M12+)**: infra monte à ~0,58 €/user @100u mais à 500+ users on est à 0,16 €/user donc la marge réelle s'améliore avec le volume malgré le cluster Typesense plus gros.

---

## 5. Risque text-heavy: est-ce vraiment safe sans quota ?

Calcul direct: combien d'articles ou de documents un user Standard peut-il consommer **en plus** de son quota audio plein avant que la marge passe sous 20 % ?

| Quota audio | Budget restant après audio+infra | Max articles | Max documents |
|-------------|---------------------------------:|-------------:|--------------:|
| 180 min | 1,91 € | **374** | 229 |
| 300 min | 1,52 € | **297** | 182 |
| 450 min | 1,03 € | **203** | 124 |
| 600 min | 0,55 € | **109** | 67 |

**Interprétation (infra EC2 + Typesense MVP, phase launch @100u)**:

- Avec un quota Standard à **300 min audio**, il faudrait 297 articles OU 182 documents **en plus** de l'audio plein pour passer sous 20% de marge. Cela correspond à **10+ articles par jour** pendant tout un mois. Statistiquement négligeable.
- Avec un quota à **450 min audio**, le seuil descend à 203 articles → 7/j. Défendable.
- Avec un quota à **600 min audio**, on passe à 109 articles/mois → 3-4/j. Commence à se resserrer mais les hard caps couvrent.

**Conclusion**: **pas de quota text nécessaire** quel que soit le quota audio retenu entre 180 et 600 min. Les hard caps anti-abus (§3.2) suffisent.

---

## 6. Tier Premium 10 € TTC

### 6.1 Même méthodologie, prix doublé

Revenu net: **7,08 €**. Stress text-heavy poussé à 500 articles + 60 documents (Premium = usage intensif). Infra phase launch.

| Quota audio | @25u | @50u | **@100u** | @200u | @500u | @1000u |
|-------------|-----:|-----:|----------:|------:|------:|-------:|
| 300 min | +25,9 % | +34,2 % | **+38,4 %** | +40,5 % | +41,7 % | +42,1 % |
| 450 min | +19,1 % | +27,4 % | **+31,6 %** | +33,7 % | +34,9 % | +35,3 % |
| **600 min** | +12,3 % | +20,6 % | **+24,8 %** | +26,9 % | +28,1 % | +28,5 % |
| 750 min | +5,3 % | +13,7 % | +17,9 % | +19,9 % | +21,2 % | +21,6 % |
| 900 min | −1,4 % | +6,9 % | **+11,1 %** | +13,1 % | +14,4 % | +14,8 % |
| 1200 min | −14,8 % | −6,5 % | −2,3 % | −0,3 % | +0,9 % | +1,3 % |

### 6.2 Options Premium

**Option A — Premium 10 € TTC / 900 min audio** (15h/mois):

- Marge worst-case à 100 users: **+11,1 %**. Sous le seuil de 20 % ciblé. Acceptable uniquement avec wording "fair use" strict et monitoring individuel.
- Wording: "15h de podcasts transcrits / mois" + fair use sur articles/documents.
- Monitoring individuel obligatoire (alerte à 6 € de coût/user, throttle à 8 €).

**Option B — Premium 10 € TTC / 600 min audio** (10h/mois) ★ recommandée:

- Marge worst-case @100u: **+24,8 %** — largement au-dessus du seuil 20 %.
- Wording: "10h de podcasts / mois".
- Positionnement: l'écart Standard 300 min → Premium 600 min (×2 audio) justifie le doublement de prix.

**Option C — Premium 12 € TTC / 900 min audio**:

- Prix TTC 12 € → net 8,50 €. À 900 min worst-case @100u: coût ~6,30 €, **marge +25,9 %**.
- Ligne de prix cohérente si l'owner veut vendre "15h" sans fair-use.

**Recommandation**: **Option B** pour V1 (10 €, 600 min, marge confortable, wording simple). Si un A/B sur 3 mois montre que la demande pousse sur "15h", migrer vers Option A (avec fair-use renforcé) ou Option C (remontée de prix).

---

## 7. Mois gratuit: que coûte-t-il ?

L'owner a rejeté la modélisation "profils 50/35/15". Approche alternative: **table de couverture par comportement**, sans distribution supposée.

Infra amortie à 100 users en phase launch = **0,345 €/user**. Document free tier actif (cas normal du launch).

Attention: j'ai volontairement recalculé la section en partant du fait que le podcast 45 min devrait être écrémé par le hard cap mensuel (300 min = ~6-7 blocs max). La ligne "30 podcasts 45 min" est conservée uniquement comme référence théorique avant plafonnement.

| Comportement mensuel | Coût média | Coût total (+ infra 0,345 €) |
|---------------------|-----------:|----------------------------:|
| 1 podcast 45 min | 0,145 € | 0,49 € |
| 5 podcasts 45 min | 0,727 € | 1,07 € |
| 10 podcasts 45 min (proche hard cap 300 min) | 1,454 € | 1,80 € |
| 20 podcasts 45 min (au-delà du hard cap) | 2,908 € | 3,25 € |
| **30 podcasts 45 min (théorique, bloqué en pratique)** | 4,361 € | **4,71 €** |
| 10 YouTube 25 min | 0,113 € | 0,46 € |
| 50 YouTube 25 min | 0,567 € | 0,91 € |
| 100 articles | 0,510 € | 0,86 € |
| **500 articles (text-heavy, hard cap 500)** | 2,548 € | **2,89 €** |
| 20 documents 3p (free tier) | 0,102 € | 0,45 € |
| 50 documents 3p (hard cap free) | 0,255 € | 0,60 € |

**Lectures**:

- Un utilisateur free trial "raisonnable" (10 podcasts + 50 YouTube + 100 articles + 20 docs) = ~**3 €/mois** de coût complet.
- Le hard cap 300 min audio défini en §3.2 limite le coût audio max à ~**1,8 €/mois/user**. L'abus articles se contient à **2,9 €** avec le cap 500 articles. **Total max free trial = ~5 € pour un abuser tenace, ~1-2 € pour un user normal.**
- **Le marketing "1 mois gratuit sans quota" est défendable** sous condition d'appliquer les hard caps de §3.2 techniquement sans les communiquer. Le risque financier du free trial reste **raisonnable** malgré l'infra réelle plus coûteuse qu'un Lambda pur.

**Il n'y a pas de "coût moyen free trial" dans ce rapport** parce qu'on ne connaît pas la distribution. Le chiffre 2,12 €/user de la v3 n'est pas reproductible ici.

---

## 8. Analyse de sensibilité

6 paramètres incertains. Pour chacun, impact sur la marge Standard 5 € @ 300 min @ 100 users (baseline **+27,0 %** en phase launch).

| Paramètre | Baseline | Variante pessimiste | Impact marge |
|-----------|----------|---------------------|--------------|
| Tokens FR par minute | 250 | 300 (+20%) | −2,5 pts → +24,5 % |
| Taux captions YouTube gratuites | 95 % | 75 % | négligeable (YouTube ne compte pas dans le quota audio si captions OK; si fallback, les minutes comptent) |
| Taux captions TikTok/IG gratuites | 70 % | 50 % | ~0 pt (volume marginal sur 300 min) |
| Stripe pass-through | 0 (IAP) | 2,9% + 0,25€ si Web | −7 pts → +20,0 % (si future Web ajoutée) |
| Rétries LLM (JSON flashcards) | 0% | 15% retry avg | −1,5 pts → +25,5 % |
| Document free tier épuisé dès M1 | Non | Oui | −0,3 pts sur text-heavy worst-case |
| Typesense Cloud sizing (cluster MVP → Growth prématuré) | MVP $18/mo | Growth $50/mo sans besoin | −7,8 pts → +19,2 % |
| Base users (100 → 25u au launch réel) | 100u | 25u | **−25 pts → +2,0 %** (runway founder) |
| Passage à `t4g.medium` si charge augmente | `t4g.small` 11 €/mo | `t4g.medium` 21 €/mo | −2,9 pts → +24,1 % |

**Paramètres dominants**: **le volume d'users** et **le sizing Typesense**.

- À **25-50 users**, la marge est fragile ou négative; c'est un problème de **runway**, pas de pricing. Il faut absorber cette perte comme CAC ou retarder l'ouverture publique.
- Le **cluster Typesense** représente à lui seul ~15 € fixes/mois. Ne pas passer en Growth ($50/mo) avant que le volume ne l'exige vraiment (>5k users per task-53.1).
- La sensibilité aux autres paramètres (tokens, retries, upgrade EC2) est faible et cumulée laisse la marge au-dessus de 18%.

---

## 9. Positionnement concurrent (données vérifiées 2026-05-01)

| App | Prix mensuel | Annuel effectif | Limite clé | Source |
|-----|-------------:|----------------:|------------|--------|
| **Snipd Free** | 0 $ | — | 2 épisodes AI/semaine | snipd.com/pricing |
| **Snipd Premium** | 6,99 $ | — | 900 min AI upload/mois | snipd.com/pricing |
| **Otter Free** | 0 $ | — | 300 min/mois + 3 imports lifetime | otter.ai/pricing |
| **Otter Pro** | 16,99 $ mensuel | 8,33 $/mois (−50%) | 1 200 min recording + 10 imports/mois | otter.ai/pricing |
| **Otter Business** | 30 $ mensuel | 19,99 $/mois | Illimité | otter.ai/pricing |
| **Readwise Lite** | — | 5,59 $/mois (annuel) | Highlights seulement | readwise.io/pricing |
| **Readwise Full** | 12,99 $ mensuel | 9,99 $/mois (annuel) | + Reader app | readwise.io/pricing |
| **Recall Free** | 0 $ | — | 10 AI cards/mois | recall.it/pricing |
| **Recall Plus** | — | 10 $/mois (annuel) | "Living knowledge base" | recall.it/pricing |
| **Recall Max** | — | 38 $/mois (annuel) | Modèles frontière | recall.it/pricing |

**Note**: la v3 mentionnait Otter Pro à 8,49 €/mois — c'est le tarif **annualisé**, pas mensuel. Le tarif mensuel réel (pas d'engagement annuel) est **16,99 $ ≈ 14,50 €**. Corrigé ici.

**Positionnement V1 recommandé**:

- **Standard 5 € TTC**: prix d'entrée plus bas que Snipd Premium (6,99 $) et Otter Pro. Justifié par un scope multi-média (audio + YouTube + articles + documents), là où les concurrents sont mono-thème.
- **Premium 10 € TTC**: aligné sur Recall Plus annuel (10 $/mois). Offre "illimité" avec fair use, comparable à Readwise Full.
- **Pas de plan annuel** pour V1: la cross-platform store-billing rend l'annuel compliqué à prix cassé côté Apple/Google. À rajouter en V1.5 si le churn mensuel l'exige.

---

## 10. Rate limiting chiffré pour implémentation

### 10.1 Rate limits fournisseurs externes

| Fournisseur | Plan | Limite | Marge de sécurité |
|-------------|------|--------|-------------------|
| **Deepgram** pay-as-you-go | 10 concurrent requests, 100 req/10s | **8 concurrent** worker max | https://developers.deepgram.com/docs/rate-limits |
| **OpenAI Tier 1** (nouveau compte) | 500 RPM, 200k TPM par modèle | 400 RPM par modèle | https://platform.openai.com/docs/guides/rate-limits |
| **LlamaParse** free/starter | Non publié, ~100 RPM estimé | 80 concurrent | https://llamaindex.ai/pricing |
| **Unstructured API** free | Non publié, ~50-100 RPM estimé | 40 concurrent | https://unstructured.io/pricing |

### 10.2 Rate limits applicatifs par tier

| Action | Standard | Premium | Free trial |
|--------|---------:|--------:|-----------:|
| Imports audio / jour | 10 (≤ 60 min) | 20 (≤ 60 min) | 5 (≤ 30 min) |
| Imports texte / jour | 30 | 100 | 30 |
| Imports document / jour | 10 | 30 | 10 |
| Imports texte / minute | 5 | 10 | 2 |
| Génération artefact retry / min | 3 | 5 | 2 |
| API calls / minute | 30 | 60 | 15 |

### 10.3 Hard caps mensuels anti-abus

| Ressource | Standard | Premium | Free |
|-----------|---------:|--------:|-----:|
| Minutes audio total | 300 (plancher) | 600 (plancher) | 300 |
| Articles | 500 | 1 500 | 300 |
| Documents | 100 | 300 | 50 |
| Durée max d'un média audio | 180 min | 180 min | 90 min |

### 10.4 Monitoring de coût individuel

Alertes CloudWatch sur coût par user (DynamoDB tracking):

| Tier | Warning (coût/user) | Hard block | Action |
|------|-------------------:|-----------:|--------|
| Free | 5 € | 8 € | Bloquer nouveaux imports audio; email "utilisation intensive détectée" |
| Standard | 4 € | 6 € | Throttle (1 import audio/h); email |
| Premium | 8 € | 12 € | Contact perso owner; suggestion Premium+ futur |

### 10.5 Implémentation technique

- **Redis** (ElastiCache) pour sliding-window counters (rate limiting per-user, per-minute).
- **SQS FIFO** avec `MessageGroupId=user_id` pour sérialiser les imports d'un même user et éviter les parallélisations abusives.
- **DynamoDB TTL** sur table `user_monthly_usage` avec reset au 1er du mois.
- **CloudWatch alarms** sur `cost_per_user_eur` métrique custom.

---

## 11. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Tokens FR plus élevés que 250/min | ~2-3 pts marge | Mesurer empiriquement sur 5-10 transcripts réels en Phase 1 et recalibrer |
| Captions YouTube indisponibles pour contenu niche | Minute audio → quota | Compter dans le quota audio dès le fallback; déjà prévu |
| Fallback TikTok/IG >30% (hypothèse 70% gratuit optimiste) | Marge Standard | Monitorer taux réel; ajuster hard cap durée audio si >40% |
| Dérive archi vers NAT Gateway / RDS / ECS 24/7 | Marge chute brutale | Code review terraform avant merge; refuser toute intro de NAT Gateway, RDS, ALB tant que la VM unique suffit |
| Fin du free tier AWS 12 mois | ~1-2 pts marge | Optimisation logs retention, S3 lifecycle, reserved instance EC2 à M10 |
| Typesense signup credit épuisé plus tôt que prévu | −2 pts marge | Monitorer consommation credit dès M0; passer en MVP cluster ($18/mo) en anticipation |
| Volume users < 50 au launch | Marge négative (runway) | Phase pré-launch étendue (Typesense signup credit); accepter coût d'acquisition |
| Spike CPU `t4g.small` | Lenteurs API / workers | CloudWatch alarm `CPUCreditBalance`; scaling vertical `t4g.medium` (+10 €/mo) |
| Instance EC2 unique (SPOF) | Downtime sur incident | Snapshots EBS quotidiens, runbook re-deploy < 30 min, monitoring ALB/uptime externe gratuit |
| Retries LLM pour JSON flashcards | +1-2 pts marge | Budgeter 15% retry; monitorer; fallback `gpt-4o-mini` si échec persistant |
| Document free tier épuisé plus vite que prévu | ~0,3 pts marge | Monitorer consommation mensuelle, passer à LlamaParse Starter ($50/mo) dès 8k pages/mois |
| App Store rejects subscriptions model | Blocking | Utiliser StoreKit 2 / Google Play Billing v6 — standards, pas de raison d'être rejeté |
| Change de commission Apple/Google | Marge | Aujourd'hui 15% Small Business; au-delà $1M revenu, passe à 30% → margin compression de ~14 pts. À anticiper |
| Churn mensuel 8-10% | LTV | À 5 € net 3,54 € × (1/0,10) = LTV ~35 €. CAC doit rester < 10 € pour LTV/CAC ≥ 3 |

---

## 12. Recommandation finale

### 12.1 Offre à lancer

1. **Mois gratuit**
   - 1 mois, pas de quota marketing visible.
   - Hard caps techniques (§3.2 + §10.3): 300 min audio, 300 articles, 50 documents max.
   - Monitoring coût individuel avec alerte à 5 € et hard block à 8 €.

2. **Standard 5 € TTC / mois**
   - Quota: **300 min audio / mois**.
   - Pas de quota text/document (hard caps anti-abus seulement).
   - Revenu net: 3,54 €. Marge worst-case @100u phase launch: **+27,0 %**. Phase growth (>5k users ou M12+) : reste >20% grâce à l'amortissement du cluster.

3. **Premium 10 € TTC / mois** (option recommandée: **Option B**)
   - Quota: **600 min audio / mois** (10h).
   - Pas de quota text/document.
   - Revenu net: 7,08 €. Marge worst-case @100u phase launch: **+24,8 %**.
   - Alternative si l'owner veut vendre "15h": Option A (900 min avec fair use strict, marge +11,1 %) ou Option C (12 €, 900 min, marge +25,9 %).

### 12.2 Contraintes opérationnelles

- **Architecture VM unique `t4g.small` + Typesense Cloud**: le code docker-compose existant se déploie tel quel sur EC2. Refus de tout refactor "serverless pur" en V1 (Lambda n'est pas compatible avec les workers long-running du code actuel, cf. §2.3).
- **Phase pré-launch étendue** (Typesense signup credit actif): maximiser cette période pour la validation beta avec <50 users. Économie ~15 €/mois sur Typesense.
- **Passage Typesense MVP → Growth retardé** jusqu'à franchir 5k users ou saturation visible du cluster 0.5 GB. Évite une dépense prématurée de +25 €/mois.
- **Mesure empirique des tokens FR** dans les 4 premières semaines de Phase 1 pour recalibrer. Si la mesure donne 300 tokens/min au lieu de 250, la marge glisse de ~2,5 pts mais reste au-dessus de 20%.
- **Monitoring coût individuel** dès le jour 1 (DynamoDB tracking + CloudWatch alarms — tout dans le free tier permanent à V1 volume).
- **Bloquer le creep d'architecture**: code review terraform pour refuser toute intro de NAT Gateway, RDS, ALB, ECS long-running tant que la VM unique n'est pas saturée. Le scaling vertical (`t4g.medium`, puis `t4g.large`) tient jusqu'à ~5000 users.
- **Snapshots EBS quotidiens** + runbook re-deploy <30 min pour mitiger le SPOF VM unique.
- **Pas de plan annuel en V1** à cause de la complexité store-billing. À reconsidérer si le churn dépasse 12%.

### 12.3 Ce que cet arbitrage ne tranche pas

- Pas de Web app pour V1 → si Web vient plus tard, refaire le calcul avec Stripe (marge −7 pts).
- Pas de plan Family / multi-device partage.
- Pas de modèle étudiant (−50% type Readwise).
- Pas d'offre Lifetime (risque de cash flow négatif côté developer).

Ces questions sont V1.5+, hors scope de ce benchmark.

---

## 13. Sources

### Projet

- `docs/research/task-72-llm-artifact-benchmark/README.md` (owner_decision: ok, 2026-04-29)
- `docs/research/task-90-document-parser-benchmark/README.md` (owner_decision: ok)
- `docs/research/task-73-cloud-provider-analysis/README.md` (owner_decision: ok)
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `docs/research/task-65-pricing-v1-benchmark/README.superseded-2026-05-01.md` (ce que cette version remplace)
- `docs/research/task-65-pricing-v1-benchmark/README.owner-rejected-2026-04-30.md`
- `docs/research/task-65-pricing-v1-benchmark/README.owner-rejected-2026-04-29.md`

### Fournisseurs

- OpenAI pricing: https://openai.com/api/pricing/
- OpenAI rate limits: https://platform.openai.com/docs/guides/rate-limits
- Deepgram rate limits: https://developers.deepgram.com/docs/rate-limits
- LlamaParse pricing: https://llamaindex.ai/pricing
- Unstructured pricing: https://unstructured.io/pricing
- USD/EUR spot 2026-04-30: https://www.x-rates.com/historical/?amount=1&date=2026-04-30&from=USD

### Distribution & fiscalité

- Apple Small Business Program: https://developer.apple.com/app-store/small-business-program/
- Google Play service fees: https://support.google.com/googleplay/android-developer/answer/112622
- TVA FR services numériques B2C (taux normal 20%): https://www.impots.gouv.fr/
- Stripe fees EEA (pour Web future): https://stripe.com/fr/pricing

### Concurrents (vérifiés 2026-05-01)

- Snipd: https://www.snipd.com/pricing
- Otter.ai: https://otter.ai/pricing
- Readwise: https://readwise.io/pricing
- Recall: https://www.recall.it/pricing

---

**Reproductibilité**: tous les chiffres de ce document sont générés par `compute.py` dans ce dossier. Modifier une hypothèse → relancer → diffs identifiés.

**Document généré**: 2026-05-01 — 4ᵉ passe du benchmark task-65 (révision 2).
**Changes vs v3 (2026-04-30)**: correction des incohérences numériques, tokens LLM calibrés par média, intégration App Store/Play Store commission, suppression des profils utilisateurs inventés, analyse de sensibilité, validation empirique concurrents.
**Révision 1 (2026-05-01)**: intégration du free tier AWS (Lambda, DynamoDB, SQS, Cognito, CloudWatch permanents + API Gateway/S3 12 mois). L'erreur v3 "0,74 €/user" corrigée vers l'autre extrême (Lambda pur ~0,07 €/user) — mais ce modèle ignorait encore le code applicatif réel.
**Révision 2 (2026-05-01)**: **inspection du code backend actuel** (FastAPI + ~15 workers long-running docker-compose, incompatible Lambda) + **intégration de Typesense Cloud** (validé task-53.1 avec free signup credit puis cluster payant). Nouvelle archi infra: EC2 `t4g.small` + Typesense Cloud. Modèle en 3 phases (pré-launch / launch / growth). Marges révisées à la baisse vs rév. 1 mais plus réalistes. À 100 users en phase launch: 0,345 €/user, Standard 300 min marge +27 %, Premium 600 min marge +25 %. Voir §2.3 et §8.
