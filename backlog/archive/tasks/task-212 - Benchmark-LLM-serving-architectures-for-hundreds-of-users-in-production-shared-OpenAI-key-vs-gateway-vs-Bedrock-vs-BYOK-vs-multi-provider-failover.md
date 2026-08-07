---
id: task-212
title: >-
  Benchmark LLM serving architectures for hundreds of users in production
  (shared OpenAI key vs gateway vs Bedrock vs BYOK vs multi-provider failover)
status: To Do
assignee: []
created_date: '2026-06-16 15:00'
labels:
  - benchmark
  - llm
  - architecture
  - v1
  - scaling
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le pattern actuellement prévu pour servir les appels LLM (générés par les workers `summary_short`, `summary_detailed`, `flashcards`, `notes`, traduction de transcripts, etc.) à des **centaines d'utilisateurs en production** est le suivant :

> **Tous les appels LLM des users transitent par UNE clé API OpenAI personnelle de l'owner, sur laquelle l'owner met l'argent nécessaire (paiement automatique, rechargement au fil de l'eau).**

Cette tâche a pour but de **challenger ce pattern** par un benchmark exhaustif des alternatives, avant de figer l'architecture de production V1.

Modèles LLM cibles déjà validés (task-72) :
- `summary_short` : `gpt-5-nano-2025-08-07`
- `summary_detailed`, `flashcards`, `notes`, traduction transcript (task-189) : `gpt-5.4-nano-2026-03-17`

Charge cible : **100 users actifs Y1 → 1000 users Y2**, ~200 médias/user/mois max selon le pricing V1 (task-65).

## Pourquoi challenger ce pattern ?

Risques connus du pattern "clé OpenAI unique partagée" à 100s+ users :

1. **Single point of failure financier** : si la CB de l'owner est rejetée, refusée, plafonnée, ou si OpenAI suspend le compte (suspicion d'abus, content policy violation déclenchée par UN user, etc.) → 100% de la plateforme tombe instantanément. Aucune redondance.
2. **Quotas RPM/TPM partagés** : OpenAI Tier 1 = 500 RPM / 200k TPM. Tier 2/3/4/5 selon dépense cumulée. Un seul user qui spamme peut saturer la file de tous les autres. Le rate limiting applicatif (task-65 : 5 audio/day Standard, 10/day Premium) protège partiellement mais ne couvre pas les pics simultanés.
3. **Pas d'attribution per-user au niveau provider** : impossible de demander à OpenAI "combien a coûté l'user X ?". L'attribution se fait uniquement côté applicatif via les tokens loggés, ce qui suffit pour la facturation mais pas pour le forensic abuse (un attaquant qui prompt-injecte pour générer 10k tokens/req passe inaperçu côté OpenAI).
4. **Conformité / DPA** : OpenAI fournit un DPA standard mais l'owner est seul signataire. À 100s d'users EU, il faut vérifier l'alignement RGPD (sous-traitance OpenAI, data residency, opt-out training — déjà OK par défaut sur l'API mais à confirmer par écrit).
5. **Pas de failover provider** : si OpenAI a un incident global (ils en ont eu plusieurs en 2024-2026), tous les workers d'artefacts plantent jusqu'à résolution. Pas de bascule automatique vers Anthropic/Google/Azure OpenAI.
6. **Risque de fraude / abuse** : un user malveillant peut tenter de forcer la génération via des médias gigantesques (transcripts 100k tokens), du prompt injection, ou de l'enchaînement rapide. Le coût absorbé par l'owner peut exploser avant que les guards applicatifs ne réagissent.
7. **Vendor lock-in** : aucune abstraction → migration future vers un autre provider = refonte des workers.

## Patterns alternatifs à benchmarker exhaustivement

Benchmark exhaustif requis (recherche internet + retours d'expérience + sources fournisseurs) sur les patterns suivants :

### Pattern A : Statu quo (clé OpenAI mutualisée + paiement owner)
Décrire précisément les garanties OpenAI à différents Tiers (Tier 1 → Tier 5), le mécanisme d'auto-recharge, les SLA financiers, et les conditions de suspension de compte. Coût = pure pass-through.

### Pattern B : LLM Gateway managé (Portkey, OpenRouter, Helicone, LangSmith, Anyscale, Together AI router, Cloudflare AI Gateway, AWS Bedrock multi-model, etc.)
- Couche d'abstraction au-dessus de plusieurs providers (OpenAI + Anthropic + Google + open source).
- Failover automatique, rate limiting per-virtual-key, observabilité per-user, cost attribution, caching sémantique, prompt firewall.
- Markup typique : 0% (Cloudflare AI Gateway, OpenRouter pass-through) à 5-15% (Portkey, Helicone Pro).
- Évaluer chaque acteur sur : pricing exact, support GPT-5-nano / GPT-5.4-nano, SLA, multi-region, conformité RGPD, latence ajoutée.

### Pattern C : Cloud-native (AWS Bedrock, Azure OpenAI Service, Google Vertex AI)
- Bedrock : pas d'OpenAI mais Claude/Llama/Mistral/Cohere — rupture du choix task-72 si on veut tout migrer dessus, ou pattern hybride.
- **Azure OpenAI Service** : OpenAI models avec quotas Azure, DPA enterprise, data residency EU garantie, billing intégré au cloud provider, PTU (provisioned throughput) en option. **À évaluer en détail** car potentiellement le meilleur compromis (mêmes modèles que task-72).
- Vertex AI : Gemini + Anthropic Claude — encore une fois rupture task-72.
- Évaluer : compatibilité modèles task-72, quotas per-deployment vs partagés, pricing vs OpenAI direct, conformité, observability native CloudWatch / Azure Monitor / Cloud Logging.

### Pattern D : BYOK (Bring Your Own Key)
- Chaque user fournit sa propre clé OpenAI / Anthropic / autre.
- Élimine le risque financier owner mais friction onboarding massive (l'user doit créer un compte OpenAI, mettre une CB, gérer son budget).
- Adapté à un pricing freemium "self-hosted plan" mais pas à un produit consumer 5€/mois.
- Évaluer en B2B / power-users seulement (option future éventuelle).

### Pattern E : Pool de clés OpenAI multiples (sharding par user-bucket, round-robin)
- Plusieurs comptes OpenAI séparés gérés par l'owner, sharding par user-id ou tenant.
- Bénéfice : isolation des incidents (suspension d'une clé n'affecte qu'un sous-ensemble), cumul des Tier-limits.
- Inconvénients : multiplication des CB, KYC OpenAI répété, gestion ops lourde, conformité plus floue.

### Pattern F : Multi-provider failover applicatif (sans gateway managé)
- Implémentation maison dans les workers : OpenAI primary → Anthropic fallback → Google fallback.
- Maîtrise totale, pas de vendor LLM gateway, mais coût d'ingénierie et maintenance.
- Évaluer librairies open source : LiteLLM (proxy + SDK), LangChain providers abstraction, Vercel AI SDK.

### Pattern G : Modèles open source self-hosted (Llama 3.x, Qwen 3, etc.)
- Déploiement sur GPU dédiés (Modal, RunPod, Lambda Labs, fly.io GPU, AWS Inferentia/Trainium).
- Coût fixe vs variable, indépendance vendor, contrôle complet, pas de quotas.
- Trade-off qualité (vs gpt-5-nano) à mesurer sur les artefacts.
- Probablement hors-scope V1 mais à mentionner comme option V2 si la facture OpenAI explose à 1000+ users.

## Critères de comparaison

Pour chaque pattern, documenter :

1. **Coût total** : à 100u, 500u, 1000u, en réutilisant les hypothèses task-65 (modèles task-72, ~200 médias/user/mois max). Inclure : coût LLM brut + markup gateway éventuel + coût ops (multi-CB, key rotation) + coût d'ingénierie initial.
2. **Résilience / SLA** : tolérance à une panne provider, à une suspension de clé, à un pic de trafic. Documenter les incidents historiques connus du provider (status pages, postmortems publics).
3. **Quotas et scaling** : RPM/TPM disponibles à chaque palier (Tier OpenAI, déploiement Azure, virtual keys gateway). Comportement quand on hit le quota.
4. **Conformité RGPD / DPA** : data residency, sous-traitance, opt-out training, processeur unique vs multi-processeurs, signature DPA, audit trail. **Important** car users EU.
5. **Observabilité et cost attribution per-user** : possibilité de tracer le coût exact par user (pour facturation, anti-abuse, forensic), latences par modèle, taux d'erreur, prompt logging.
6. **Sécurité / anti-abuse** : protection contre prompt injection, content moderation pré-envoi, rate limiting per-virtual-key, blocage automatique d'abus, key rotation sans downtime.
7. **Friction onboarding user** : 0 (statu quo, gateway, cloud-native) → forte (BYOK).
8. **Effort d'ingénierie** : initial (intégration), récurrent (maintenance, key rotation, monitoring), migration (depuis le code worker actuel qui appelle OpenAI directement).
9. **Vendor lock-in et exit cost** : combien coûte de migrer vers une autre option dans 12 mois.
10. **Compatibilité avec les modèles task-72** : `gpt-5-nano-2025-08-07` et `gpt-5.4-nano-2026-03-17` doivent rester accessibles (sauf si le benchmark recommande explicitement un changement de modèle, ce qui imposerait alors une re-validation task-72).

## Livrable

`docs/research/task-212-llm-serving-architecture-benchmark/README.md` avec :

1. Tableau comparatif des 7 patterns (A à G) sur les 10 critères ci-dessus.
2. Analyse détaillée de chaque pattern avec sources.
3. Estimation de coût TCO à 100u / 500u / 1000u pour chaque pattern.
4. Analyse de risque : matrice probabilité × impact pour chaque scénario d'incident (CB rejetée, compte suspendu, panne provider, abuse user, etc.) selon le pattern retenu.
5. Recommandation argumentée : un pattern principal V1 (qui peut très bien être le statu quo si l'analyse le justifie, ou une bascule vers Azure OpenAI / Cloudflare AI Gateway / Portkey / etc.) + un pattern de bascule V2 documenté.
6. Plan de migration concret depuis le pattern actuel (workers appellent `openai.AsyncOpenAI(api_key=...)` directement) vers le pattern recommandé.
7. Front-matter `owner_decision: pending` pour validation owner.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tableau comparatif d'au moins 7 patterns d'architecture (statu quo OpenAI unique, LLM gateway managé, cloud-native Azure/Bedrock/Vertex, BYOK, pool de clés, failover applicatif, self-hosted)
- [ ] #2 Pour chaque pattern : coût TCO chiffré à 100/500/1000 users, conformité RGPD documentée, observabilité per-user, friction onboarding, effort d'ingénierie, vendor lock-in
- [ ] #3 Analyse de risque explicite des modes d'échec du pattern actuel (CB rejetée, compte OpenAI suspendu, panne provider, abuse user, quotas RPM/TPM saturés) avec mitigation par pattern
- [ ] #4 Compatibilité vérifiée avec les modèles validés task-72 (gpt-5-nano-2025-08-07 et gpt-5.4-nano-2026-03-17), ou re-validation explicite si le benchmark recommande de les changer
- [ ] #5 Recommandation finale argumentée avec pattern V1 retenu + pattern V2 de bascule + plan de migration concret depuis le code worker actuel
- [ ] #6 Sources publiques vérifiables pour pricing, SLA, incidents historiques, conformité de chaque acteur évalué
- [ ] #7 Front-matter owner_decision: pending dans docs/research/task-212-llm-serving-architecture-benchmark/README.md
<!-- AC:END -->

## Implementation Notes

**Mode**: initial (first research pass, no prior README existed)

**Deliverable**: `docs/research/task-212-llm-serving-architecture-benchmark/README.md`

**Summary of research produced (2026-06-16)**:
- Comprehensive benchmark of 7+ patterns (A through G, plus A+ variant) across 10 criteria
- TCO estimates at 100/500/1000 users for each pattern
- Risk matrix with probability x impact for 7 failure scenarios
- GDPR/DPA compliance comparison table (OpenAI vs Azure vs Cloudflare)
- Full list of OpenAI API incidents March-June 2026 from status page
- Azure OpenAI quota tiers (Tier 1-6) verified with gpt-5-nano and gpt-5.4-nano availability confirmed
- Concrete migration plan (Phase 1: env var change for CF AI Gateway, Phase 2: Azure OpenAI SDK swap)

**Recommendation**: Pattern A+ (OpenAI + Cloudflare AI Gateway, gratuit) for V1, Pattern C (Azure OpenAI DataZone EU) for V2 fallback.

**La recommandation attend la validation de l'owner.**

---

**Mode**: redo (second pass — integrating owner feedback about chatbot workload)

**Deliverable**: `docs/research/task-212-llm-serving-architecture-benchmark/README.md` (new file replacing the rejected one)

**Owner feedback integrated (2026-06-16)**:
- Added chatbot workload hypothesis: users attach long transcripts (50-100k+ tokens per request) to a chatbot
- Recalculated TPM requirements: chatbot represents 99%+ of TPM demand (1.9M-19M TPM pic depending on scale)
- Identified that OpenAI direct (Tier 1-3) is INSUFFICIENT for the chatbot workload at 500-1000 users
- Verified Azure OpenAI quotas from official docs: multi-region stacking allows 15M-48M+ TPM at Tier 1-2
- Changed recommendation from "A+ (statu quo + CF)" to "C (Azure OpenAI multi-region)" as V1 pattern
- V2 pattern changed from "Azure OpenAI" to "Azure PTU (Provisioned Throughput)" for latence-critical chatbot

**Summary of research produced (2026-06-16, redo pass)**:
- Updated load hypotheses with chatbot TPM/RPM analysis (Section 1)
- Demonstrated that Pattern A/A+ (OpenAI direct) fails at scale with chatbot (TPM saturation)
- Verified Azure OpenAI Tier 1-6 quotas for gpt-5-nano and gpt-5.4-nano (data from official Microsoft docs)
- Confirmed Azure multi-region quota stacking mechanism (each region has independent quota)
- Documented Azure auto-upgrade Tiers and PTU spillover mechanisms
- Risk matrix with chatbot-specific scenarios (rush hour, power user, scaling progressif)
- Migration plan in 3 phases (Azure setup + CF AI Gateway + PTU escalation)

**Recommendation**: Pattern C (Azure OpenAI multi-region GlobalStandard + CF AI Gateway) for V1, Pattern C+PTU (Azure Provisioned Throughput) for V2.

**La recommandation attend la validation de l'owner.**
