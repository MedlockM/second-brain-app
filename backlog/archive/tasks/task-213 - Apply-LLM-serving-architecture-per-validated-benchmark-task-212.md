---
id: task-213
title: Apply LLM serving architecture per validated benchmark (task-212)
status: To Do
assignee: []
created_date: '2026-06-16 15:01'
labels:
  - feature
  - llm
  - architecture
  - v1
  - scaling
dependencies:
  - task-212
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Tâche d'implémentation découlant du benchmark task-212 (architecture de service LLM pour 100s d'users en production).

## Source de vérité

L'implémentation **doit suivre la décision finale de l'owner** documentée dans le front-matter et la section *Owner Validation* de :

`docs/research/task-212-llm-serving-architecture-benchmark/README.md`

L'implémenteur lit le champ `Decision` du README pour connaître :

- Le pattern d'architecture retenu (statu quo, LLM gateway managé, Azure OpenAI, multi-provider failover, etc.).
- Le ou les providers à intégrer.
- La stratégie de gestion des clés (clé unique, pool, rotation, secret manager).
- Les éventuelles dépendances logicielles (LiteLLM, Portkey SDK, OpenAI Azure SDK, Bedrock SDK, etc.).
- Le pattern d'observabilité per-user et de cost attribution attendu.
- Le plan de migration depuis le code worker actuel.

**Ne pas pré-supposer un pattern dans cette tâche** : la recommandation initiale du benchmark peut différer de la décision finale de l'owner.

## Périmètre d'implémentation (générique, à raffiner selon la décision)

- Refactor des workers LLM pour passer par la couche d'abstraction retenue (au lieu d'instancier `openai.AsyncOpenAI` directement).
- Centralisation de la configuration LLM (provider URL, clé(s), timeouts, retry policy, fallback chain) dans un module unique.
- Stockage des secrets via le secret manager du cloud retenu (AWS Secrets Manager, Parameter Store, etc.) — pas de clé en clair dans les variables d'environnement Lambda.
- Métriques per-user émises (cost, tokens, latency, errors) vers le système d'observabilité existant (CloudWatch / Algolia logs / DynamoDB usage table — selon ce qui existe déjà).
- Tests unitaires sur la couche d'abstraction (mock provider, fallback, rate limit handling, error mapping).
- Tests d'intégration end-to-end sur au moins un worker (`summary_short` recommandé car le plus simple).
- Documentation runbook : comment rotater une clé, comment monitorer la consommation, comment réagir à un incident provider.

## Acceptance Criteria
<!-- AC:BEGIN -->
Les critères ci-dessous sont volontairement génériques. Ils seront raffinés à l'implémentation selon la décision owner.
<!-- SECTION:DESCRIPTION:END -->

- [ ] #1 Lire docs/research/task-212-llm-serving-architecture-benchmark/README.md et appliquer strictement la décision owner (pattern, provider(s), gateway éventuel, librairies)
- [ ] #2 Tous les workers LLM (summary_short, summary_detailed, flashcards, notes, traduction transcript) passent par la couche d'abstraction retenue — plus aucun appel openai.AsyncOpenAI direct hors de cette couche
- [ ] #3 Configuration LLM centralisée dans un module unique avec secret manager (pas de clé en clair dans env Lambda)
- [ ] #4 Métriques per-user émises (cost, tokens, latency, errors) cohérentes avec l'observabilité existante
- [ ] #5 Tests unitaires sur la couche d'abstraction (mock provider, fallback, rate limit handling, error mapping) + test d'intégration e2e sur summary_short
- [ ] #6 Runbook documenté : rotation de clé, monitoring consommation, procédure de réaction à un incident provider
- [ ] #7 Aucune régression fonctionnelle observable sur les artefacts générés (qualité, latence, format JSON) par rapport au pattern actuel
<!-- AC:END -->
