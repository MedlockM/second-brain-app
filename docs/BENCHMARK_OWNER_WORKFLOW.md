# Benchmark Workflow — Owner Guide

Guide de référence pour valider les benchmarks produits par les agents de recherche et débloquer les tâches d'implémentation associées.

## Où et comment l'owner agit

Pour chaque benchmark, l'owner ouvre le fichier `docs/research/task-XX-<short-description>/README.md` et édite :

1. Le champ `owner_decision` dans le front-matter YAML (entre les deux `---` en tête du fichier)
2. Le champ `**Decision**:` sous `## Owner Validation` (texte libre : la décision finale, les remarques ou consignes)
3. Le champ `**Validated at**:` (date ISO : `YYYY-MM-DD`)

Exemple :

```markdown
---
owner_decision: ok
---

# Benchmark: ...

## Owner Validation

**Decision**: Accept recommendation Typesense Cloud for MVP.
**Validated at**: 2026-04-28
```

## Table des décisions possibles

| `owner_decision` | Quand l'utiliser | Action automatique au prochain dispatch (Phase 0) | Ce que fait `task-research` au prochain run |
|---|---|---|---|
| `pending` | Défaut après production du benchmark. L'owner n'a pas encore relu. | Rien. | Rien (tâche skippée par Phase 1, sauf si un `complement-request-*.md` est ouvert). |
| `ok` | Benchmark accepté tel quel (ou avec modifications mineures décrites dans `Decision`). | Marque la tâche benchmark `Done` → débloque la tâche d'implémentation liée via sa dépendance. | Rien. |
| `abandoned` | Benchmark rejeté, la tâche n'est plus à mener. | Archive la tâche benchmark ET toutes les tâches qui en dépendent (la tâche d'implémentation liée disparaît du backlog). | Rien. |
| `redo` | Benchmark insatisfaisant, à refaire entièrement. Consignes de correction obligatoires dans `Decision`. | Renomme le README courant en `README.owner-rejected-<date>.md`, repasse la tâche benchmark à `To Do`. | Mode **redo** : relit tous les `README.owner-rejected-*.md` pour comprendre les rejets précédents, puis produit un nouveau `README.md` qui intègre les feedbacks. |
| `more` | Benchmark de base OK mais il manque de l'information pour trancher. Consignes précises sur ce qu'il faut ajouter dans `Decision`. | Extrait les consignes dans `complement-request-<date>.md`, remet `owner_decision` à `pending` dans le README (Decision/Validated at gardés pour trace), repasse la tâche benchmark à `To Do`. | Mode **complement** : lit le `complement-request-<date>.md` le plus récent non traité, produit un `complement-response-<date>.md` qui y répond, sans toucher au README principal. |

## Règles importantes

- **Le `README.md` principal est la seule source de vérité**. Les fichiers `README.owner-rejected-*.md`, `complement-request-*.md` et `complement-response-*.md` sont consultatifs et n'ont pas de front-matter actif.
- Quand tu es satisfait — potentiellement après plusieurs rounds `more` et/ou `redo` — tu mets `owner_decision: ok` **uniquement sur le README principal**. L'implémentation se lance au prochain dispatch.
- Dans le champ `Decision` tu peux référencer les fichiers complémentaires (ex: "Accept recommendation X as refined by `complement-response-2026-05-05.md`"). L'agent d'implémentation suivra ces références.
- Si un benchmark nécessite plusieurs passes `more`, les fichiers s'accumulent dans le dossier et constituent l'historique complet du cheminement vers la décision finale.

## Workflow typique

1. Le dispatcher lance `task-research` sur une tâche benchmark → README créé avec `owner_decision: pending`.
2. Tu relis le README. Cas possibles :
   - Tu es satisfait → `owner_decision: ok` + `Decision: Accept recommendation X`.
   - Tu rejettes complètement → `owner_decision: abandoned` + `Decision: <justification>`.
   - Tu veux une autre passe avec des corrections → `owner_decision: redo` + `Decision: <consignes de correction>`.
   - Il te manque juste un complément d'info → `owner_decision: more` + `Decision: <consignes de complément>`.
3. Au prochain dispatch, Phase 0 synchronise le backlog selon ta décision, puis Phase 1 sélectionne les tâches dispatchables.
4. Tu re-relis si `redo` ou `more` → boucle jusqu'à `ok` (ou `abandoned`).
5. Quand `ok`, la tâche d'implémentation liée devient dispatchable et sera prise en charge par l'agent approprié (`task-feature`, `task-ingestion`, etc.) qui lira ton `Decision` pour savoir quoi implémenter.

## Référence technique

- Logique dispatcher : `.claude/agents/backlog-dispatcher.md` (Phase 0 et Phase 1)
- Agent de recherche : `.claude/agents/task-research.md` (détection des modes initial / redo / complement)
- Convention de création de tâches : `CLAUDE.md` et `AGENTS.md`
