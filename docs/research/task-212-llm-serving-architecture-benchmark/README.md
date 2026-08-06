---
owner_decision: abandoned
---

# Benchmark : LLM Serving Architectures for Production (100-1000 Users) — Including Chatbot Workload

## Owner Validation

**Decision**: _(a remplir par l'owner apres relecture — texte libre decrivant la decision finale)_
**Validated at**: _(date ISO a remplir par l'owner)_

---

## Recommendation

**Pattern V1 recommande : Pattern C (Azure OpenAI Service, deploiement multi-region GlobalStandard + DataZone EU)**

Deployer directement sur Azure OpenAI avec les modeles gpt-5-nano et gpt-5.4-nano en **GlobalStandard** (quotas les plus eleves) pour le chatbot, et **DataZoneStandard EU** pour les artifacts (conformite EU). Proxifier via Cloudflare AI Gateway (gratuit) pour observabilite et caching.

**Pourquoi Azure d'emblee (et non le statu quo OpenAI direct)** :

Le workload chatbot change fondamentalement la donne. Avec des centaines d'users envoient simultanement des requetes a 50-100k+ tokens de contexte, le TPM explose :
- **200 users chatbot simultanes x 75k tokens/requete = 15M tokens en une seule minute** juste en input.
- Les quotas OpenAI direct Tier 3 (10M TPM pour gpt-5.4-nano) sont **insuffisants** pour ce scenario.
- Azure OpenAI Tier 1 GlobalStandard offre 5M TPM par region, mais **cumulable multi-region** (3 regions = 15M TPM). A Tier 2 : 16M TPM/region = 48M en multi-region.
- Azure permet un scale-up automatique via le systeme de Tiers (auto-upgrade avec la consommation) sans action manuelle.

**Pattern V2 de bascule (>500 users ou latence critique) : Azure OpenAI Provisioned Throughput (PTU)**

Migration vers des PTU (Provisioned Throughput Units) pour capacite dediee garantie, latence constante, et decouplage total des quotas partages. Cout fixe previsible, ideal pour le chatbot haute-frequence.

**Justification** : Le chatbot avec longs contextes (50-100k+ tokens) est un multiplicateur de TPM x10-50 par rapport aux artifacts. A 200+ users chatbot simultanes, seule une architecture avec des quotas TPM de l'ordre de 15-50M+ par minute est viable. Azure OpenAI multi-region (GlobalStandard) offre ce niveau de quota des Tier 1-2, avec un path d'escalade vers PTU si la latence devient critique.

---

## Table of Contents

1. [Hypotheses de charge (avec chatbot)](#1-hypotheses-de-charge-avec-chatbot)
2. [Tableau comparatif des 7 patterns](#2-tableau-comparatif-des-7-patterns)
3. [Analyse detaillee par pattern](#3-analyse-detaillee-par-pattern)
4. [Estimation TCO a 100/500/1000 users](#4-estimation-tco-a-1005001000-users)
5. [Analyse de risque](#5-analyse-de-risque)
6. [Recommandation argumentee](#6-recommandation-argumentee)
7. [Plan de migration](#7-plan-de-migration)
8. [Sources](#8-sources)

---

## 1. Hypotheses de charge (avec chatbot)

### 1.1 Workload Artifacts (inchange vs premiere passe)

| Parametre | Valeur |
|-----------|--------|
| Users actifs Y1 | 100 |
| Users actifs Y2 | 1000 |
| Medias/user/mois moyen | 80 |
| Artifacts par media | 4 (summary_short + summary_detailed + flashcards + notes) |
| Requetes LLM/media | 5 (4 artifacts + 1 translation ~30%) |
| Tokens input moyen/req artifact | 3,000 |
| Tokens output moyen/req artifact | 800 |

### 1.2 Workload Chatbot (NOUVEAU — scenario owner)

Le chatbot permet aux users de joindre leurs transcripts (medias de leur base de connaissance) au contexte de la conversation. Hypotheses conservatrices et worst-case :

| Parametre | Conservateur | Worst-case (pic) |
|-----------|-------------|-----------------|
| **Users chatbot simultanes** | 50 (50% des actifs) | 200-300 |
| **Transcripts joints par message** | 2-3 medias | 5-8 medias |
| **Tokens par transcript** | 5,000-11,000 | 11,000-25,000 |
| **Contexte total par requete chatbot** | 20,000-40,000 tokens | 50,000-100,000+ tokens |
| **Messages chatbot/user/session** | 5-10 | 15-20 |
| **Sessions chatbot/user/jour** | 1-2 | 3-5 |
| **Tokens output moyen/message chatbot** | 500-1,000 | 1,500 |

### 1.3 Volume combine estime (artifacts + chatbot)

#### RPM (Requests Per Minute)

| Source | @100u pic | @500u pic | @1000u pic |
|--------|-----------|-----------|------------|
| Artifacts (workers async) | ~6 | ~28 | ~56 |
| Chatbot (users simultanes x3 burst) | ~25 | ~125 | ~250 |
| **Total RPM pic** | **~31** | **~153** | **~306** |

Calcul chatbot RPM : A 100u, 50 users chatbot actifs, ~0.5 msg/min en moyenne, x3 burst = ~25 RPM pic. A 1000u, 200-250 users simultanes en pic.

#### TPM (Tokens Per Minute) — LE POINT CRITIQUE

| Source | @100u pic | @500u pic | @1000u pic |
|--------|-----------|-----------|------------|
| Artifacts input | ~18k (6 req x 3k) | ~84k | ~168k |
| Artifacts output | ~5k (6 req x 800) | ~22k | ~45k |
| **Chatbot input** | **~1.9M** (25 req x 75k avg) | **~9.4M** | **~18.8M** |
| **Chatbot output** | **~25k** (25 req x 1k) | **~125k** | **~250k** |
| **Total TPM pic (input)** | **~1.9M** | **~9.5M** | **~19M** |
| **Total TPM pic (output)** | **~30k** | **~147k** | **~295k** |
| **Total TPM pic (combined)** | **~2.0M** | **~9.6M** | **~19.3M** |

**Conclusion critique** : Le chatbot represente **99%+ du TPM** a cause des longs contextes. Les artifacts sont negligeables en comparaison. C'est le chatbot qui dimensionne l'architecture.

### 1.4 Comparaison avec les quotas disponibles

| Provider/Tier | RPM gpt-5.4-nano | TPM gpt-5.4-nano | Suffisant @100u? | @500u? | @1000u? |
|---------------|------------------|------------------|------------------|--------|---------|
| **OpenAI Tier 1** | 500 | 200k | NON (TPM) | NON | NON |
| **OpenAI Tier 2** | 3,500 | 2M | OUI (limite) | NON | NON |
| **OpenAI Tier 3** | 5,000 | 10M | OUI | OUI (limite) | NON |
| **OpenAI Tier 4** | 10,000 | - | OUI RPM | Depend TPM | - |
| **OpenAI Tier 5** | 30,000 | - | OUI | OUI | OUI |
| **Azure Tier 1 GlobalStandard** | 5,000 | 5M | OUI | NON seul | NON seul |
| **Azure Tier 1 x3 regions** | 15,000 | 15M | OUI | OUI | OUI (limite) |
| **Azure Tier 2 GlobalStandard** | 16,000 | 16M | OUI | OUI | OUI (limite) |
| **Azure Tier 2 x3 regions** | 48,000 | 48M | OUI | OUI | OUI |
| **Azure Tier 3 GlobalStandard** | 46,000 | 46M | OUI | OUI | OUI |
| **Azure Tier 5 DataZone EU** | 50,000 | 50M | OUI | OUI | OUI |

**Point cle** : OpenAI direct ne suffit qu'a Tier 5 ($1000+ de depense cumulee) pour le workload chatbot @1000u. Azure offre des quotas **cumulables multi-region** et un Tier 2 atteint automatiquement avec la consommation, offrant 16M TPM par region des les premieres semaines d'usage.

### 1.5 Cout LLM brut (chatbot + artifacts combines)

Pricing gpt-5-nano : $0.05/M input, $0.40/M output.
Pricing gpt-5.4-nano : $0.20/M input, $1.25/M output.

Le chatbot utilise gpt-5.4-nano (comprehension de longs textes requiert le modele superieur).

| Scale | Artifacts/mois | Chatbot/mois (input) | Chatbot/mois (output) | Cout artifacts | Cout chatbot | **Total** |
|-------|---------------|---------------------|---------------------|---------------|-------------|-----------|
| 100u | 40k req, 120M in, 32M out | ~500M tokens in | ~40M tokens out | ~$80 | ~$150 | **~$230** |
| 500u | 200k req, 600M in, 160M out | ~2,500M tokens in | ~200M tokens out | ~$400 | ~$750 | **~$1,150** |
| 1000u | 400k req, 1.2B in, 320M out | ~5,000M tokens in | ~400M tokens out | ~$800 | ~$1,500 | **~$2,300** |

Calcul chatbot @100u : 100 users x 1.5 sessions/jour x 7.5 msg/session x 30 jours x 50k tokens avg/msg = ~1.7B tokens/mois input, mais avec le pricing gpt-5.4-nano ($0.20/M) = ~$337. Estimation conservatrice corrigee : 50% des users utilisent le chatbot regulierement, 30k tokens/msg moyen → ~500M in/mois = **$100 + $50 output = $150/mois chatbot**.

---

## 2. Tableau comparatif des 7 patterns

| Critere | A: Statu quo (cle unique) | A+: + CF AI Gateway | B: Gateway (Portkey) | C: Azure OpenAI (RECO V1) | D: BYOK | E: Pool cles | F: LiteLLM multi-provider | G: Self-hosted |
|---------|--------------------------|--------------------|--------------------|---------------------------|---------|-------------|--------------------------|---------------|
| **1. Cout @100u/mois** | $230 | $230 | $230 + $49 = $279 | $230 (meme pricing) | $0 owner | $230 | $230 | $600-1200 GPU |
| **2. Cout @1000u/mois** | $2,300 | $2,300 | $2,300 + $49 = $2,349 | $2,300 | $0 owner | $2,300 | $2,300 | $2,500-4,000 GPU |
| **3. Resilience/SLA** | Aucun SLA | Idem + retry CF | Failover multi-provider | **SLA 99.9% contractuel** | Depend user | Isolation partielle | Failover code | 99.9% selon infra |
| **4. Quotas RPM** | 500-30k (Tier 1-5) | Idem (CF ne modifie pas) | Idem provider | **5k-150k/region** (Tier 1-5) | Tier 1/user | Cumul Tiers | Idem provider | Illimite |
| **5. Quotas TPM** | 200k-? (Tier 1-5) | Idem | Idem | **5M-150M/region, cumulable multi-region** | Tier 1/user | Cumul | Idem | Illimite |
| **6. RGPD/DPA** | DPA OpenAI, pas EU garanti | + CF DPA | + Portkey SOC2 | **DPA Microsoft, DataZone EU garanti** | User resp. | Multi-DPA | Multi-DPA | Controle total |
| **7. Observabilite per-user** | Applicative seule | + CF Analytics | Native per-key | Azure Monitor natif | Non | Partielle | LiteLLM dashboard | Custom |
| **8. Securite/anti-abuse** | Rate limit applicatif | + CF rate limit | + Guardrails | Content filter Azure natif | Aucune | Par bucket | Code maison | Code maison |
| **9. Friction onboarding** | 0 | 0 | 0 | 0 | **Forte** | 0 | 0 | 0 |
| **10. Effort ingenierie** | 0 | Faible (1 URL) | Moyen (SDK) | **Moyen (2-3j)** | Eleve | Eleve | Moyen | Tres eleve |
| **11. Compatibilite task-72** | 100% | 100% | 100% | **100%** (memes modeles) | 100% | 100% | 100% (primary) | 0% |
| **12. Suffisant chatbot @1000u?** | **NON** (Tier 3 = 10M TPM, besoin 19M+) | **NON** | **NON** (depend provider) | **OUI** (multi-region 48M+ TPM Tier 2) | **NON** (Tier 1) | Possible si 3+ comptes | Possible multi-deploy | OUI (illimite) |
| **Vendor lock-in** | Fort | Faible (1 URL) | Faible-moyen | Moyen (migration retour triviale) | Nul | Fort | Faible | Nul |

**Le critere decisif est le #12 (suffisance TPM chatbot)** : seuls les patterns C (Azure multi-region), E (pool 3+ comptes OpenAI), et G (self-hosted) peuvent absorber le workload chatbot @1000u. Le pattern G est incompatible task-72. Le pattern E est operationnellement complexe et risque (multi-accounting OpenAI). **Azure OpenAI est la seule option robuste.**

---

## 3. Analyse detaillee par pattern

### Pattern A/A+ : Statu quo OpenAI direct (+/- Cloudflare AI Gateway)

**Pourquoi INSUFFISANT avec le chatbot** :

Les quotas OpenAI direct par Tier (source: developers.openai.com, juin 2026) :
- Tier 1 ($5 depenses) : 500 RPM, 200k TPM → **echec a 100u chatbot** (besoin 2M+ TPM)
- Tier 2 ($50 depenses) : 3,500 RPM, 2M TPM → **limite a 100u, echec a 500u**
- Tier 3 ($100 depenses) : 5,000 RPM, 10M TPM → **echec a 1000u** (besoin 19M+)
- Tier 4 ($250 depenses) : 10,000 RPM, TPM non publie pour nano
- Tier 5 ($1000 depenses) : 30,000 RPM → **probablement suffisant** mais necessite $1000+ de depense cumulee pour y acceder

**Probleme fondamental** : On ne peut pas atteindre Tier 5 rapidement. A $230/mois, il faut ~4-5 mois pour accumuler $1000 de depense et debloquer Tier 5. Pendant ce temps, le chatbot est bride en TPM.

**Cloudflare AI Gateway** ne resout pas ce probleme : CF est un proxy transparent qui ne modifie pas les quotas du provider sous-jacent. Il ajoute retry, caching et observabilite, mais si le provider renvoie 429 (rate limit), CF ne peut rien faire.

**Verdict** : Pattern inadequat pour le workload chatbot. Viable uniquement si le chatbot est lance apres avoir accumule suffisamment de depenses pour atteindre Tier 4-5 (4-6 mois post-launch).

---

### Pattern B : LLM Gateway manage (Portkey, OpenRouter, Helicone)

Portkey et les gateways ne resolvent pas le probleme fondamental des quotas provider. Ils ajoutent :
- Load balancing entre plusieurs cles/comptes (= Pattern E via gateway)
- Failover multi-provider (mais task-72 invalide les alternatives)
- Observabilite et cost attribution

**Portkey peut aider en combinaison avec Azure** : Portkey permet de router entre Azure OpenAI multi-region nativement, avec load balancing intelligent. Mais a $49/mois minimum, Cloudflare AI Gateway offre la meme fonction routing gratuitement.

**Verdict** : Utile en complement mais ne resout pas seul le probleme de quotas TPM. Non recommande en standalone.

---

### Pattern C : Azure OpenAI Service (RECOMMANDE V1)

**Pourquoi Azure resout le probleme du chatbot** :

1. **Quotas massifs et cumulables multi-region** (source: learn.microsoft.com, verifie juin 2026) :

| Modele | Tier | Deployment | RPM | TPM | Multi-region x3 |
|--------|------|-----------|-----|-----|-----------------|
| gpt-5-nano | 1 | GlobalStandard | 5,000 | 5,000,000 | 15,000 RPM / 15M TPM |
| gpt-5-nano | 2 | GlobalStandard | 16,000 | 16,000,000 | 48,000 RPM / 48M TPM |
| gpt-5-nano | 3 | GlobalStandard | 46,000 | 46,000,000 | 138,000 RPM / 138M TPM |
| gpt-5.4-nano | 1 | GlobalStandard | 5,000 | 5,000,000 | 15,000 RPM / 15M TPM |
| gpt-5.4-nano | 2 | GlobalStandard | 16,000 | 16,000,000 | 48,000 RPM / 48M TPM |
| gpt-5.4-nano | 3 | GlobalStandard | 46,000 | 46,000,000 | 138,000 RPM / 138M TPM |
| gpt-5.4-nano | 1 | DataZoneStandard | 2,000 | 2,000,000 | (EU only, 1 region) |
| gpt-5.4-nano | 2 | DataZoneStandard | 6,000 | 6,000,000 | - |
| gpt-5.4-nano | 5 | DataZoneStandard | 50,000 | 50,000,000 | - |

2. **Mecanisme multi-region natif** (extrait de la doc Azure) :

> "Quotas and limits are defined per region, per subscription, and per model or deployment type. Within a single Azure subscription, it's possible to use a larger quantity of total TPM and RPM quota for a given model and deployment type, as long as you have resources and model deployments spread across multiple regions."

Concretement : deployer gpt-5.4-nano en GlobalStandard dans 3 regions (East US, West Europe, Southeast Asia) = 3x le quota par region. A Tier 2 : **48M TPM cumule**, soit 2.5x le besoin @1000u (19M TPM pic).

3. **Auto-upgrade automatique des Tiers** :

> "Automatic tier upgrades are based primarily on customer consumption trends across Foundry Models over time. If a customer's usage increases such that their current quota tier is limiting their ability to use Foundry Models the system will automatically upgrade the customer to the next higher tier."

Pas de blocage artificiel comme chez OpenAI ($1000 de depense cumulee requise pour Tier 5). Azure upgrade automatiquement avec l'usage.

4. **Path d'escalade : Provisioned Throughput Units (PTU)** :

Pour le scenario ou la latence chatbot doit etre garantie (experience conversationnelle interactive) :
- PTU = capacite dediee, latence constante, pas de partage avec d'autres clients
- Ideal pour le chatbot a haute frequence
- Billing fixe par PTU/heure (previsible)
- **Spillover** : si les PTU sont satures, overflow automatique vers un deployment Standard (pas de perte de requetes)

5. **Pricing identique a OpenAI direct** (confirme par Microsoft : "Azure OpenAI uses the same pricing as OpenAI for pay-as-you-go").

6. **Data residency EU garantie** : DataZoneStandard pour les artifacts sensibles, GlobalStandard pour le chatbot (performance max).

---

### Pattern D : BYOK (Bring Your Own Key)

**Verdict inchange** : Incompatible avec un produit consumer. De plus, chaque user serait en Tier 1 OpenAI (200k TPM) ce qui est insuffisant pour le chatbot avec longs contextes.

---

### Pattern E : Pool de cles OpenAI multiples

**Analyse mise a jour** : Avec le chatbot, l'interet du pool de cles augmente (cumul des TPM). 3 comptes Tier 3 = 30M TPM cumule, suffisant @1000u.

**Problemes** :
- OpenAI multi-accounting est risque (politique floue, suspension possible)
- 3+ CB, 3+ comptes, 3+ factures = gestion ops complexe
- Atteindre Tier 3 sur 3 comptes simultanement = 3x plus lent (revenu reparti)
- Pas de SLA, pas de data residency EU

**Verdict** : Hack viable en urgence mais non recommande en production. Azure offre le meme resultat (cumul multi-region) nativement et de maniere supportee.

---

### Pattern F : Multi-provider failover (LiteLLM)

**Analyse mise a jour** : LiteLLM permet le load balancing entre plusieurs deployments Azure OpenAI (meme modele, regions differentes). C'est utile en complement de Azure pour distribuer les requetes chatbot sur 3 regions.

**Mais** : Cloudflare AI Gateway supporte Azure OpenAI nativement et offre le meme routing gratuitement. LiteLLM n'apporte pas de valeur ajoutee significative vs CF AI Gateway pour ce cas precis.

**Cas d'usage LiteLLM pertinent** : Si on veut un fallback vers un autre provider (ex: Anthropic Claude pour le chatbot uniquement, en acceptant une difference de qualite). Pas pertinent V1.

---

### Pattern G : Modeles open source self-hosted

**Verdict inchange** : Incompatible task-72. Cout GPU prohibitif pour le chatbot (context windows 100k+ tokens = GPU haute memoire requises). Non pertinent V1/V2.

---

## 4. Estimation TCO a 100/500/1000 users

### 4.1 Cout mensuel par pattern (EUR/mois, incluant chatbot)

| Pattern | @100u | @500u | @1000u | Chatbot viable? |
|---------|-------|-------|--------|-----------------|
| **A: Statu quo** | 184 EUR | 920 EUR | 1,840 EUR | **NON** @1000u (TPM insuffisant) |
| **A+: + CF AI GW** | 184 EUR | 920 EUR | 1,840 EUR | **NON** (CF ne change pas les quotas) |
| **B: Portkey** | 223 EUR | 959 EUR | 1,879 EUR | **NON** seul |
| **C: Azure OpenAI** | **184 EUR** | **920 EUR** | **1,840 EUR** | **OUI** (multi-region) |
| **C+PTU: Azure PTU** | ~300-500 EUR | ~800-1,200 EUR | ~1,500-2,500 EUR | **OUI** (dedie) |
| **D: BYOK** | 0 EUR owner | 0 EUR owner | 0 EUR owner | NON (Tier 1/user) |
| **E: Pool 3 cles** | 184 EUR | 920 EUR | 1,840 EUR | Possible (risque) |
| **F: LiteLLM** | 184 EUR | 920 EUR | 1,840 EUR | Depend provider |
| **G: Self-hosted** | 2,000+ EUR | 3,000+ EUR | 4,000+ EUR | OUI (illimite) |

Note : Le pricing Azure OpenAI pay-as-you-go est identique a OpenAI direct. Le cout est le meme, seuls les quotas et la robustesse changent.

### 4.2 Cout d'ingenierie initial

| Pattern | Effort initial | Jours-dev |
|---------|---------------|-----------|
| A: Statu quo | 0 | 0 |
| A+: CF AI Gateway | Faible | 0.5 |
| B: Portkey | Moyen | 1-2 |
| **C: Azure OpenAI** | **Moyen** | **2-3** |
| C+PTU: Azure PTU | Moyen-Eleve | 3-5 |
| D: BYOK | Eleve | 5-10 |
| E: Pool cles | Eleve | 3-5 |
| F: LiteLLM | Moyen | 2-4 |
| G: Self-hosted | Tres eleve | 15-30 |

### 4.3 Estimation PTU pour le chatbot (V2)

Pour un workload chatbot a 1000u avec 19M TPM pic, en supposant un ratio PTU similaire aux modeles nano (estimations basees sur gpt-4.1-nano reference) :
- Estimation : ~50-100 PTU necessaires pour absorber 19M TPM chatbot
- Cout PTU hourly : ~$0.50-1.00/PTU/heure (estimation basee sur les modeles nano publies)
- Cout mensuel PTU : ~$1,800-3,600/mois pour les PTU chatbot @1000u
- Vs pay-as-you-go : $2,300/mois → PTU rentable si utilisation > 60-70%

Avec Azure Reservations (engagement 1 an) : reduction ~30-40% = **$1,260-2,520/mois**, potentiellement moins cher que le pay-as-you-go si le chatbot est intensement utilise.

---

## 5. Analyse de risque

### 5.1 Matrice probabilite x impact (focus chatbot)

| Scenario | Probabilite | Impact | Risque | Pattern A (statu quo) | Pattern C (Azure) |
|----------|-------------|--------|--------|----------------------|-------------------|
| **Saturation TPM chatbot (pic simultane)** | **ELEVEE** @500u+ | **Critique** (429 errors, chatbot inutilisable) | **CRITIQUE** | Pas de mitigation (quotas fixes) | Multi-region cumul + spillover PTU |
| **CB owner rejetee/expiree** | Moyenne | Critique (100% down) | ELEVE | Downtime total | Billing Azure (entreprise, pas CB perso) |
| **Compte OpenAI suspendu** | Faible | Critique | MOYEN-ELEVE | Downtime indefini | Compte Azure separe, aucun lien |
| **Panne provider globale** | Moyenne (2-3x/mois) | Moyen (30-120 min) | MOYEN | Aucun recours | SLA 99.9% + multi-region isolation |
| **Latence chatbot degradee (pic)** | Elevee @500u+ | Moyen (UX degradee) | ELEVE | Pas de mitigation | PTU = latence garantie constante |
| **Cout chatbot explose** | Moyenne | Moyen (marge compressee) | MOYEN | Pas de controle | Meme cout + Azure Batch pour async |
| **Abus user chatbot (context flooding)** | Moyenne | Moyen (surcout) | MOYEN | Rate limit applicatif seul | + Content filter Azure + rate limit per-deployment |

### 5.2 Scenarios specifiques au chatbot

**Scenario A : "Rush hour" - 300 users ouvrent le chatbot simultanement**

- Chaque user envoie un message avec 3 transcripts joints (avg 50k tokens)
- Total : 300 req x 50k = **15M tokens input en une minute**
- OpenAI Tier 3 (10M TPM) : **429 errors pour ~33% des users**
- Azure GlobalStandard Tier 2 x3 regions (48M TPM) : **aucun probleme**

**Scenario B : "Power user" - 1 user colle 8 longs transcripts dans un message**

- 8 x 11k tokens = 88k tokens + systeme prompt + historique = ~100k tokens input
- Cout unique de cette requete : 100k x $0.20/M = $0.02 input + ~$0.002 output = $0.022
- Si le user fait 50 messages/jour comme ca : $1.1/jour = $33/mois **pour un seul user**
- Protection necessaire : rate limit applicatif + max tokens per request + max transcripts joints

**Scenario C : "Scaling progressif" - De 100u a 1000u en 6 mois**

- Mois 1-2 : 100u, chatbot leger → 2M TPM suffit (Azure Tier 1, 1 region)
- Mois 3-4 : 300u, chatbot populaire → 6M TPM → ajouter 2eme region
- Mois 5-6 : 700u, adoption massive → 14M TPM → 3 regions + auto-upgrade Tier 2
- Mois 7+ : 1000u, pic → 19M TPM → Tier 2 x3 = 48M TPM (confortable)
- **Aucun changement de code** : le load balancer (CF AI Gateway ou applicatif) route sur les endpoints multi-region

---

## 6. Recommandation argumentee

### V1 (lancement, 100+ users) : Pattern C (Azure OpenAI multi-region + Cloudflare AI Gateway)

**Architecture** :

```
Users → API → Workers (artifacts) → CF AI Gateway → Azure OpenAI (DataZone EU, 1 region)
     → API → Chatbot service    → CF AI Gateway → Azure OpenAI (GlobalStandard, 2-3 regions, load balanced)
```

**Pourquoi Azure d'emblee et non le statu quo "A+" de la premiere passe** :

1. **Le chatbot change tout** : A 100u avec chatbot actif, on a besoin de ~2M TPM. OpenAI Tier 2 (2M TPM) est juste suffisant mais sans marge. Azure Tier 1 GlobalStandard (5M TPM) donne 2.5x de marge. Avec 2 regions : 10M TPM = confortable.

2. **Scaling previsible** : Azure auto-upgrade des Tiers + multi-region = croissance lineaire des quotas avec l'usage, sans action manuelle ni attente de paliers de depense.

3. **Meme cout** : Azure OpenAI = meme pricing qu'OpenAI direct. Pas de surcharge.

4. **SLA et robustesse** : SLA 99.9% contractuel, billing entreprise, pas de CB personnelle en SPOF.

5. **Data residency EU native** : DataZoneStandard pour les artifacts (conformite EU), GlobalStandard pour le chatbot (performance max).

6. **Path vers PTU** : Si le chatbot explose en popularite, migration vers PTU sans changement d'API (meme endpoint Azure).

**Effort** : 2-3 jours dev (creation ressource Azure, deploiements, changement env vars, test).

### V2 (>500 users ou latence chatbot critique) : Azure OpenAI Provisioned Throughput (PTU)

**Declencheurs** :
1. Latence chatbot degrade (p95 > 3s time-to-first-token)
2. Facture LLM > $2,000/mois (PTU peut devenir rentable)
3. Volume > 500 users chatbot actifs simultanement

**Avantages PTU** :
- Capacite dediee, pas de partage avec d'autres clients Azure
- Latence constante et garantie (critique pour UX chatbot interactive)
- Cout previsible (pas de surprises par-token)
- Spillover : overflow vers Standard automatiquement (pas de perte de requetes)

### Pourquoi PAS les autres patterns :

| Pattern | Raison d'exclusion pour le workload chatbot |
|---------|---------------------------------------------|
| A/A+ (OpenAI direct +/- CF) | **TPM insuffisant** avant Tier 5 ($1000+ depense cumulee). Risque de 429 errors sur le chatbot des les premiers mois. CF ne resout pas les limites provider. |
| B (Portkey) | Ne resout pas les quotas TPM. Utile en complement mais $49/mois pour features que CF offre gratuitement. |
| D (BYOK) | Incompatible consumer + chaque user en Tier 1 (200k TPM = 2-3 messages chatbot max). |
| E (Pool cles) | Hack risque (multi-accounting OpenAI), atteinte Tier 3 lente sur chaque compte, ops lourdes. Azure offre le meme resultat nativement. |
| F (LiteLLM) | Utile pour load balancer mais CF AI Gateway fait la meme chose gratuitement. Pas de valeur ajoutee standalone. |
| G (Self-hosted) | Incompatible task-72 + GPU haute memoire pour 100k context = $4k+/mois. |

---

## 7. Plan de migration

### Phase 1 : V1 Launch (Pattern C) — 2-3 jours dev

**Etape 1 : Setup Azure (1 jour)**

1. Creer un compte Azure (ou utiliser un existant)
2. Creer une ressource Azure OpenAI dans France Central (artifacts - DataZone EU)
3. Creer 2-3 ressources Azure OpenAI en GlobalStandard (chatbot - regions: East US, West Europe, Southeast Asia pour couverture globale)
4. Deployer `gpt-5-nano` et `gpt-5.4-nano` dans chaque ressource
5. Configurer les deployments : nommer les deployments (ex: `gpt-5-nano`, `gpt-5.4-nano`)

**Etape 2 : Integration Cloudflare AI Gateway (0.5 jour)**

1. Creer un gateway CF AI pour chaque use case (artifacts, chatbot)
2. Configurer les backends Azure OpenAI (CF supporte Azure nativement)
3. Configurer le load balancing CF entre les 2-3 regions pour le chatbot
4. Configurer rate limiting CF (safety net)
5. Configurer caching (utile pour les artifacts, moins pour le chatbot)

**Etape 3 : Code worker (1-1.5 jours)**

```python
# Changement dans les workers
import os
from openai import AsyncAzureOpenAI, AsyncOpenAI

def get_llm_client():
    if os.environ.get("LLM_PROVIDER") == "azure":
        return AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-10-21",
        )
    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

Pour le chatbot multi-region avec CF AI Gateway, le code pointe vers l'URL CF qui load-balance automatiquement :
```
CHATBOT_LLM_URL=https://gateway.ai.cloudflare.com/v1/{ACCOUNT_ID}/{CHATBOT_GW}/azure-openai/{RESOURCE}/deployments/{DEPLOYMENT}/chat/completions
```

**Etape 4 : Protections chatbot applicatives (0.5 jour)**

- Rate limit : max 10 messages/minute par user
- Max transcripts joints : 5 par message
- Max tokens input : 100k par requete (rejet si depasse)
- Timeout : 60s max par requete chatbot
- Budget per-user/jour : alertes si > $1/user/jour

**Rollback** : Variable `LLM_PROVIDER=openai` revient au pattern A (OpenAI direct) en 30 secondes.

### Phase 2 : V2 (PTU) — 3-5 jours dev (si necessaire)

1. Commander des PTU via le portail Azure pour le deployment chatbot
2. Configurer spillover : overflow vers le deployment Standard
3. Ajuster le load balancer (CF ou applicatif) pour prioriser le deployment PTU
4. Monitorer utilisation PTU et ajuster le nombre de PTU
5. Evaluer Azure Reservations si PTU > 60% utilisation sur 30 jours

### Phase 3 : Optimisations (ongoing)

- Activer le Batch API Azure pour les artifacts non-urgents (50% reduction)
- Implementer un cache semantique pour le chatbot (questions similaires entre users)
- Contexte compression : resumer les longs transcripts avant de les injecter (reduction tokens 50-70%)
- Prompt caching Azure : si meme systeme prompt + memes transcripts = cached input pricing

---

## 8. Sources

### Azure OpenAI

| Source | URL | Verifie |
|--------|-----|---------|
| Azure OpenAI Quotas & Limits (Tiers 0-6, tous modeles) | https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits | Juin 2026 |
| Azure OpenAI Multi-region quota stacking | Idem (section "Regional quota allocation") | Juin 2026 |
| Azure OpenAI Provisioned Throughput | https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/provisioned-throughput | Juin 2026 |
| Azure OpenAI Auto-upgrade Tiers | Idem quotas-limits (section "Quota tiers") | Juin 2026 |
| Azure OpenAI Spillover | Idem provisioned-throughput (section "Spillover") | Juin 2026 |
| Azure SLA 99.9% | https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services | Ref. |
| Azure OpenAI Data Privacy / DataZone EU | https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy | Juin 2026 |

### OpenAI Direct

| Source | URL | Verifie |
|--------|-----|---------|
| OpenAI Rate Limits & Tiers | https://developers.openai.com/api/docs/guides/rate-limits | Juin 2026 |
| OpenAI Pricing | https://openai.com/api/pricing/ | Ref. task-72 (avr 2026) |
| OpenAI Status Page (incidents) | https://status.openai.com/history | Juin 2026 |

### Gateways & Proxies

| Source | URL | Verifie |
|--------|-----|---------|
| Cloudflare AI Gateway | https://developers.cloudflare.com/ai-gateway/ | Juin 2026 |
| Cloudflare AI Gateway Azure support | https://developers.cloudflare.com/ai-gateway/providers/azureopenai/ | Juin 2026 |
| Portkey Pricing | https://portkey.ai/pricing | Juin 2026 |
| LiteLLM Docs | https://docs.litellm.ai/docs/ | Juin 2026 |

### Projet interne

| Source | Chemin |
|--------|--------|
| task-72 (modeles LLM valides) | `docs/research/task-72-llm-artifact-benchmark/README.md` |
| task-65 (pricing V1, hypotheses cout) | `docs/research/task-65-pricing-v1-benchmark/README.md` |
| Premiere passe rejetee (reference) | `docs/research/task-212-llm-serving-architecture-benchmark/README.owner-rejected-2026-06-16.md` |

---

## Annexe A : Quotas Azure OpenAI gpt-5-nano et gpt-5.4-nano verifies (juin 2026)

Extrait direct de https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits :

| Modele | Tier | Deployment | RPM | TPM |
|--------|------|-----------|-----|-----|
| gpt-5-nano | 1 | DataZoneStandard | 2,000 | 2,000,000 |
| gpt-5-nano | 1 | GlobalStandard | 5,000 | 5,000,000 |
| gpt-5-nano | 2 | DataZoneStandard | 6,000 | 6,000,000 |
| gpt-5-nano | 2 | GlobalStandard | 16,000 | 16,000,000 |
| gpt-5-nano | 3 | DataZoneStandard | 16,000 | 16,000,000 |
| gpt-5-nano | 3 | GlobalStandard | 46,000 | 46,000,000 |
| gpt-5-nano | 4 | DataZoneStandard | 31,000 | 31,000,000 |
| gpt-5-nano | 4 | GlobalStandard | 90,000 | 90,000,000 |
| gpt-5-nano | 5 | DataZoneStandard | 50,000 | 50,000,000 |
| gpt-5-nano | 5 | GlobalStandard | 150,000 | 150,000,000 |
| gpt-5.4-nano | 1 | DataZoneStandard | 2,000 | 2,000,000 |
| gpt-5.4-nano | 1 | GlobalStandard | 5,000 | 5,000,000 |
| gpt-5.4-nano | 2 | DataZoneStandard | 6,000 | 6,000,000 |
| gpt-5.4-nano | 2 | GlobalStandard | 16,000 | 16,000,000 |
| gpt-5.4-nano | 3 | DataZoneStandard | 16,000 | 16,000,000 |
| gpt-5.4-nano | 3 | GlobalStandard | 46,000 | 46,000,000 |
| gpt-5.4-nano | 4 | DataZoneStandard | 31,000 | 31,000,000 |
| gpt-5.4-nano | 4 | GlobalStandard | 90,000 | 90,000,000 |
| gpt-5.4-nano | 5 | DataZoneStandard | 50,000 | 50,000,000 |
| gpt-5.4-nano | 5 | GlobalStandard | 150,000 | 150,000,000 |

---

## Annexe B : Decision tree (mise a jour chatbot)

```
                      [V1 Launch - 100+ users avec chatbot]
                                    |
              Pattern C (Azure OpenAI multi-region + CF AI Gateway)
              - Artifacts: DataZone EU (1 region)
              - Chatbot: GlobalStandard (2-3 regions, load balanced)
                                    |
                    +----- Trigger V2 (PTU)? -----+
                    |                              |
              NON (happy path)            OUI (un des triggers)
                    |                              |
              Rester en C                Pattern C + PTU
              (Standard pay-as-you-go)   (Provisioned Throughput)
              scale: multi-region         - Latence garantie
              auto + Tier upgrades        - Capacite dediee
                                          - Spillover vers Standard
                                                   |
                                     +--- Trigger V3? ---+
                                     |                    |
                               NON                  OUI (>5000u)
                                     |                    |
                               Rester en C+PTU      Multi-subscription Azure
                                                    + LiteLLM routing
                                                    + Evaluer modeles alternatifs
```

**Triggers V2 (PTU)** :
- Latence chatbot p95 > 3s TTFT
- Facture LLM > $2,000/mois
- > 500 users chatbot simultanes

**Triggers V3 (Multi-subscription)** :
- > 5000 users actifs
- Facture LLM > $10,000/mois
- Quotas Tier 5 insuffisants (improbable : 150M TPM/region)
