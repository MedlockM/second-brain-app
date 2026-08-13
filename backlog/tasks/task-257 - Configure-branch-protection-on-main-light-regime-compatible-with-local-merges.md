---
id: task-257
title: >-
  Configure branch protection on main (light regime, compatible with local
  merges)
status: To Do
assignee: []
created_date: '2026-08-13 18:50'
updated_date: '2026-08-13 18:54'
labels:
  - ci
  - security
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Poser une branch protection sur `main`. **Dispatchable** : l'action se fait entièrement via `gh api`, et les droits nécessaires sont présents — `gh api repos/:owner/:repo` renvoie `permissions.admin: true` et le token porte le scope `repo` (vérifié le 2026-08-13).

## Contexte

`task-113` (Done) avait explicitement mis la branch protection **hors scope** : « à activer manuellement par l'owner sur `main` après que les workflows passent verts une première fois ». Les workflows sont verts depuis `task-223`/`227`/`228`, et le dépôt est désormais **public** — un force-push ou une suppression de `main` est maintenant un accident irréversible et visible de tous. État actuel : `gh api repos/:owner/:repo/branches/main/protection` renvoie `404 Branch not protected`.

## Régime à appliquer : léger, et rien de plus

Le régime est **tranché**, ne le rediscutez pas et ne l'élargissez pas : protéger contre la réécriture et la suppression d'historique, sans toucher au flow de merge.

```jsonc
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
```

Les quatre premiers champs sont **obligatoires dans le body** de l'API `PUT`, même à `null` — l'appel échoue s'ils manquent. Comme `gh api -F` ne sait pas passer des `null` imbriqués, utilisez `--input -` avec un heredoc JSON.

```bash
gh api -X PUT repos/:owner/:repo/branches/main/protection --input - <<'JSON'
{ ... }
JSON
gh api repos/:owner/:repo/branches/main/protection        # relire l'état appliqué
gh api -X DELETE repos/:owner/:repo/branches/main/protection   # rollback complet
```

## Quatre choix à ne pas faire, et pourquoi

1. **Ne pas exiger `Main Branch Checks`.** Ce workflow ne se déclenche que sur `push: branches: [main]` : il ne tourne **jamais** sur une pull request. Le requérir laisserait le check à jamais `expected` et bloquerait toute PR. Les seuls contextes réellement produits sur une PR sont les deux jobs de `PR Checks` (`.github/workflows/pr.yml`) : `Backend (lint + typecheck)` et `Mobile (lint + typecheck)`.
2. **Ne pas exiger `Mobile E2E Tests (Maestro)`.** `task-254` a mis ses déclencheurs automatiques en sommeil : il ne tourne plus que sur `workflow_dispatch`. Même effet de blocage.
3. **`required_linear_history` doit rester `false`.** Les tâches sont mergées en local sur `main` avec de vrais commits de merge : `git log -1 --merges --format="%h parents=%p"` donne `855a419 parents=c538ea2 9ae5c2c`, soit deux parents. L'historique linéaire interdit les commits de merge et casserait donc `Merge task-XXX` au prochain push.
4. **Ne pas activer `required_pull_request_reviews`, même à 0 approbation.** Cela imposerait une PR pour chaque tâche mergée, alors que le flow actuel est un merge local suivi d'un push. Idem pour les required status checks : ils s'appliquent aussi aux pushes directs, et comme les checks ne tournent qu'*après* le push, tout push direct serait rejeté.

`enforce_admins: false` est délibéré : il garde une porte de sortie à l'owner si la protection devait gêner une opération exceptionnelle.

## Précaution

C'est une mutation de configuration d'un dépôt public, pas une modification de fichiers dans le worktree : elle prend effet immédiatement pour tout le monde, y compris pour les autres agents en cours d'exécution. Le régime léger n'interdit aucun push normal, donc l'impact attendu est nul — mais relisez l'état appliqué juste après l'appel, et notez la commande de rollback dans les Implementation Notes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `gh api repos/:owner/:repo/branches/main/protection` renvoie 200 (et non plus `404 Branch not protected`)
- [ ] #2 Dans cette réponse : `allow_force_pushes.enabled` et `allow_deletions.enabled` sont à `false`, `required_linear_history.enabled` est à `false`, et ni `required_status_checks` ni `required_pull_request_reviews` ne sont configurés — la sortie JSON complète est collée dans les Implementation Notes
- [ ] #3 Aucun required status check n'existe, donc en particulier aucun ne référence `Main Branch Checks` ni `Mobile E2E Tests (Maestro)`
- [ ] #4 Les Implementation Notes contiennent la commande `PUT` exacte utilisée et la commande de rollback `gh api -X DELETE repos/:owner/:repo/branches/main/protection`
- [ ] #5 La case #10 de `task-113` est annotée comme couverte par `task-257`, avec la date
<!-- AC:END -->
