---
id: task-257
title: >-
  Configure branch protection on main (light regime, compatible with local
  merges)
status: Done
assignee: []
created_date: '2026-08-13 18:50'
updated_date: '2026-08-13 19:40'
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
- [x] #1 `gh api repos/:owner/:repo/branches/main/protection` renvoie 200 (et non plus `404 Branch not protected`)
- [x] #2 Dans cette réponse : `allow_force_pushes.enabled` et `allow_deletions.enabled` sont à `false`, `required_linear_history.enabled` est à `false`, et ni `required_status_checks` ni `required_pull_request_reviews` ne sont configurés — la sortie JSON complète est collée dans les Implementation Notes
- [x] #3 Aucun required status check n'existe, donc en particulier aucun ne référence `Main Branch Checks` ni `Mobile E2E Tests (Maestro)`
- [x] #4 Les Implementation Notes contiennent la commande `PUT` exacte utilisée et la commande de rollback `gh api -X DELETE repos/:owner/:repo/branches/main/protection`
- [x] #5 La case #10 de `task-113` est annotée comme couverte par `task-257`, avec la date
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch protection posée sur `main` le 2026-08-13. Aucun fichier de code touché : la seule mutation est la config du dépôt GitHub `MedlockM/second-brain-app` (public, `permissions.admin: true`). Le versionné se limite à de la documentation devenue fausse au moment où la protection a pris effet :

- ce fichier de tâche, et l'annotation de la case #10 de `task-113` ;
- `AGENTS.md` § « Never write secrets… » disait « **`main` is unprotected** » ; corrigé, avec la conséquence pratique : effacer une fuite de l'historique demande maintenant à l'owner de lever la protection d'abord ;
- `docs/V1_LAUNCH_PLAN.md`, six endroits qui affirmaient « reste à configurer » / « 404 Branch not protected » : le constat d'état (repo public), Phase 1 point 6 (et son point 7 « reste à faire »), le tableau des comptes externes, Phase 7 point 8, la checklist des décisions ouvertes et le tableau des risques. Phase 7 point 8 disait aussi « y mettre `Main Branch Checks` » — instruction retirée, avec la raison : ce workflow ne tourne jamais sur une PR.

### Commande appliquée

`gh api -F` ne sait pas passer des `null`, donc le body passe par `--input`. Le heredoc `<<'JSON'` de la description a été refusé par l'isolation du worktree (redirection jugée trop complexe) : le body a donc été écrit dans un fichier temporaire hors dépôt, `/tmp/task-257-branch-protection.json`, avec exactement le JSON ci-dessous, puis :

```bash
cat > /tmp/task-257-branch-protection.json <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
JSON

gh api -X PUT repos/:owner/:repo/branches/main/protection \
  --input /tmp/task-257-branch-protection.json
```

Rollback complet (retour à `404 Branch not protected`) :

```bash
gh api -X DELETE repos/:owner/:repo/branches/main/protection
```

### État relu juste après l'appel

`gh api -i repos/:owner/:repo/branches/main/protection` → `HTTP/2.0 200 OK` (avant : `404 Branch not protected`). Corps complet, non tronqué :

```json
{
  "url": "https://api.github.com/repos/MedlockM/second-brain-app/branches/main/protection",
  "required_signatures": {
    "url": "https://api.github.com/repos/MedlockM/second-brain-app/branches/main/protection/required_signatures",
    "enabled": false
  },
  "enforce_admins": {
    "url": "https://api.github.com/repos/MedlockM/second-brain-app/branches/main/protection/enforce_admins",
    "enabled": false
  },
  "required_linear_history": {
    "enabled": false
  },
  "allow_force_pushes": {
    "enabled": false
  },
  "allow_deletions": {
    "enabled": false
  },
  "block_creations": {
    "enabled": false
  },
  "required_conversation_resolution": {
    "enabled": false
  },
  "lock_branch": {
    "enabled": false
  },
  "allow_fork_syncing": {
    "enabled": false
  }
}
```

Les clés `required_status_checks`, `required_pull_request_reviews` et `restrictions` sont **absentes** de la réponse : c'est ainsi que l'API signale « non configuré ». Confirmé sur les sous-ressources : `.../protection/required_status_checks` → `404 Required status checks not enabled`, `.../protection/restrictions` → `404 Push restrictions not enabled`. Zéro required check, donc en particulier aucune référence à `Main Branch Checks` ni à `Mobile E2E Tests (Maestro)` (AC #3).

`gh api repos/:owner/:repo/branches/main` renvoie par ailleurs `"protected": true` avec `required_status_checks.enforcement_level: "off"` et `contexts: []`.

### Piège REST à connaître : `required_pull_request_reviews` répond 200

`gh api repos/:owner/:repo/branches/main/protection/required_pull_request_reviews` renvoie **200** avec `{"dismiss_stale_reviews":false,"require_code_owner_reviews":false,"require_last_push_approval":false,"required_approving_review_count":1}`, alors que rien n'a été demandé. C'est un artefact de cette sous-ressource, qui sert l'enregistrement par défaut même quand la règle est désactivée. La source de vérité est la règle elle-même, et elle dit non :

```bash
gh api graphql -f query='query { repository(owner: "MedlockM", name: "second-brain-app") {
  branchProtectionRules(first: 10) { nodes { pattern requiresApprovingReviews
  requiredApprovingReviewCount requiresStatusChecks requiredStatusCheckContexts
  allowsForcePushes allowsDeletions requiresLinearHistory isAdminEnforced
  restrictsPushes lockBranch blocksCreations } } } }'
```

→ une seule règle, `pattern: "main"`, avec `requiresApprovingReviews: false`, `requiredApprovingReviewCount: null`, `requiresStatusChecks: false`, `requiredStatusCheckContexts: []`, `allowsForcePushes: false`, `allowsDeletions: false`, `requiresLinearHistory: false`, `isAdminEnforced: false`, `restrictsPushes: false`, `lockBranch: false`, `blocksCreations: false`. Ne pas « corriger » le 200 de la sous-ressource : il n'y a rien à corriger.

### Vérification qu'un push normal reste possible

Aucune preuve empirique n'a été produite : un agent en worktree ne pousse pas, et il n'existe pas d'endpoint « puis-je pousser ». La vérification est donc une revue exhaustive des interrupteurs capables de rejeter un `git push` fast-forward sur `main`, tous relus ci-dessus :

| Interrupteur | Valeur | Effet s'il était actif |
|---|---|---|
| `required_status_checks` | non configuré | rejetterait tout push direct (les checks ne tournent qu'*après* le push) |
| `required_pull_request_reviews` | non configuré (`requiresApprovingReviews: false`) | imposerait une PR approuvée par tâche |
| `restrictions` / `restrictsPushes` | non configuré / `false` | limiterait les pushers autorisés |
| `lock_branch` | `false` | branche en lecture seule |
| `block_creations` | `false` | bloquerait la création de refs |
| `required_signatures` | `false` | rejetterait les commits non signés |
| `required_linear_history` | `false` | rejetterait les commits de merge, donc les `Merge task-XXX` |
| `required_conversation_resolution` | `false` | ne concerne que les PR |
| `allow_force_pushes` / `allow_deletions` | `false` | **seuls gardes actifs** : force-push et `git push --delete` |

Il n'y a par ailleurs **aucun ruleset** susceptible d'ajouter une contrainte par un autre chemin : `gh api repos/:owner/:repo/rulesets` → `[]` et `gh api repos/:owner/:repo/rules/branches/main` → `[]`.

Conclusion : seules la réécriture et la suppression d'historique sont bloquées. Un merge local suivi d'un push fast-forward — le flow du dispatcher et de l'owner — n'est touché par aucun garde actif, y compris pour les agents qui tournent en parallèle en ce moment. La confirmation en conditions réelles arrivera au prochain push de l'owner sur `main` ; en cas de surprise, la commande `DELETE` ci-dessus rend l'état initial en une seconde.

`enforce_admins: false` est conservé tel que spécifié : l'owner garde une porte de sortie (un `--force` reste possible pour lui en cas d'opération exceptionnelle).

### Écarts vs `task-113`

La case #10 de `task-113` annonçait « required checks backend + mobile ». Elle est annotée comme couverte par `task-257` au 2026-08-13, en précisant que le régime retenu est plus léger et pourquoi : des required checks s'appliquent aussi aux pushes directs et rejetteraient le flow actuel. Si le projet passe un jour à un flow 100 % PR, les deux seuls contextes réellement produits sur une PR sont `Backend (lint + typecheck)` et `Mobile (lint + typecheck)` (jobs de `.github/workflows/pr.yml`) — jamais `Main Branch Checks` (déclenché sur `push: main` uniquement) ni `Mobile E2E Tests (Maestro)` (en sommeil sur `workflow_dispatch` depuis `task-254`).

Aucun test automatisé ajouté (interdit par les règles du projet, et non demandé ici).
<!-- SECTION:NOTES:END -->
