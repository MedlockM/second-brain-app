---
id: task-53.1
title: Cadrer la recherche lexicale par utilisateur dans la base de transcripts media
status: To Do
assignee: []
created_date: '2026-03-16 22:20'
updated_date: '2026-04-23 08:58'
labels:
  - search
  - lexical-search
  - transcript
  - scoping
dependencies:
  - task-53
parent_task_id: task-53
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Définir l’approche de recherche lexicale la plus adaptée pour permettre à chaque utilisateur de retrouver, dans son historique de medias déjà soumis à l’application, les contenus pertinents à partir de mots ou expressions présents dans les transcripts. La tâche doit aboutir à une recommandation claire tenant compte de la pertinence pour le cas d’usage, de la montée en charge attendue pour une application distribuée sur les stores, de l’isolation des données par utilisateur, du coût d’exploitation, ainsi que de la complexité de mise en œuvre et de maintenance.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le besoin produit exact de recherche est cadré, incluant les types de requêtes attendues, le périmètre des contenus recherchables et les signaux de pertinence utiles pour un utilisateur.
- [ ] #2 Les principales options d’implémentation de recherche lexicale sont comparées et une recommandation explicite est formulée pour ce cas d’usage.
- [ ] #3 L’analyse documente l’impact des différentes options sur la qualité des résultats dans des transcripts potentiellement longs, bruités ou hétérogènes.
- [ ] #4 L’analyse documente les implications de scalabilité, de latence, d’isolation multi-tenant et d’exploitation pour une montée en charge grand public.
- [ ] #5 L’analyse documente les implications de coût, de complexité de mise en œuvre, de maintenance et de réversibilité.
- [ ] #6 La recommandation finale explicite les hypothèses retenues, les risques principaux, le hors périmètre et les décisions restantes avant implémentation.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Référence conversation ChatGPT à prendre en compte pour le cadrage : https://chatgpt.com/share/69b88516-6edc-8000-8307-85cc2d85efb2

Dispatch 2026-04-23: Recherche complétée par agent-task-53.1. Document de recherche créé: docs/research/task-53.1-lexical-search-transcript-scoping.md. Recommandation: Meilisearch Cloud (ou Typesense) pour le MVP. Commit direct sur second-brain-project.
<!-- SECTION:NOTES:END -->

REDO 2ᵉ passe (2026-05-12) : Recherche complétée en mode redo par agent-task-53.1. Intégration complète des feedbacks owner (2026-04-28) :
- Ajout Neon Postgres (pg_trgm / full-text) comme candidat avec pricing variable par documents
- Ajout SQLite FTS5 sur VM EC2 comme solution locale gratuite (0 € additionnel, VM déjà budgetée)
- Documentation pricing variable par nombre de documents pour TOUTES les solutions (DynamoDB, Neon, SQLite, Typesense, Meilisearch, OpenSearch, Algolia)
- Hypothèses usage réalistes V1 corrigées : 400-2000 recherches/mois total app (pas 1M/mois) alignées sur task-65 @100 users
- Trace explicite du pivot Typesense vs Meilisearch : scoped API keys + signup credit + field weighting justifient Typesense malgré scoring Meilisearch légèrement supérieur (9,15 vs 8,95)
- Intégration signup credit Typesense Cloud (phase pré-launch gratuite M0-M1)
- SQLite FTS5 positionné comme fallback si signup credit épuisé avant launch (2j dev, économie 15,5 €/mois)
- Alignment complet task-65 rév. 2 (infra EC2 + Typesense Cloud, 3 phases pré-launch/launch/growth)
Document : docs/research/task-53.1-lexical-search/README.md (owner_decision: pending).
Recommandation finale inchangée (Typesense Cloud) mais avec justification renforcée et alternatives crédibles documentées (Neon, SQLite FTS5).
Commit sur second-brain-project.
