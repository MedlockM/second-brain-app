---
id: task-258
title: >-
  Stop mobile-build-distribute.yml from firing production builds on every push
  to main
status: Done
assignee: []
created_date: '2026-08-13 18:51'
labels:
  - ci
  - mobile
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`.github/workflows/mobile-build-distribute.yml` est aujourd'hui un workflow qui ne peut que rater, et qui raterait *bruyamment* le jour où il cesserait de rater. Trois défauts cumulés, tous vérifiés le 2026-08-13.

## 1. Tout push sur `main` touchant `mobile/**` déclenche un build ET une soumission store

Le déclencheur mélange branches et tags dans un même bloc `push` :

```yaml
on:
  push:
    branches: [main]
    paths: ["mobile/**", ".github/workflows/mobile-build-distribute.yml"]
    tags: ["mobile-v*"]
```

GitHub applique `branches` aux pushes de branche et `tags` aux pushes de tag : le tag n'est donc pas une condition supplémentaire, c'est un déclencheur **de plus**. Résultat : n'importe quel commit sur `main` qui touche un fichier de `mobile/` lance un build EAS `production` sur les deux plateformes, puis `eas submit` vers TestFlight et Google Play Internal Testing. C'est du quota EAS brûlé et une soumission store involontaire à chaque commit mobile.

L'étape « Determine build profile » aggrave le tableau : ses trois branches `if` / `elif tag` / `else` retournent toutes `production`. Le calcul est mort, il n'y a aucun moyen d'obtenir un build `preview` autrement que par `workflow_dispatch`.

Attendu : un build production/submit ne part **que** sur tag `mobile-v*` ou `workflow_dispatch` explicite. Un push sur `main` ne doit rien construire, ou au plus un build `preview` sans `eas submit` — au choix de l'implémenteur, du moment que le chemin « push sur main → soumission store » disparaît.

## 2. Le job de notification d'échec échoue lui aussi

L'étape « Create GitHub Issue for persistent failures » fait `gh issue create --label "bug,ci/cd"`. Le label `ci/cd` **n'existe pas** dans le dépôt (`gh label list` ne renvoie que les 9 labels GitHub par défaut : `bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`). `gh issue create` échoue sur un label inconnu : le job censé signaler la panne tombe en panne à son tour, et l'échec réel n'est jamais remonté. Le workflow n'a par ailleurs aucun bloc `permissions:`, alors que créer une issue exige `issues: write` sur le `GITHUB_TOKEN`.

## 3. `EXPO_TOKEN` n'est pas provisionné

`gh secret list` renvoie 6 secrets et aucun n'est lié à Expo. Sans `EXPO_TOKEN`, tous les `eas build --non-interactive` du workflow échouent à l'authentification — c'est la cause du `Mobile Build & Distribute | push | failure` du dernier push. Le workflow doit échouer **tôt et lisiblement** dans ce cas au lieu de partir installer Node, `npm ci` et l'EAS CLI pour mourir sur un `eas build` à la douzième étape.

> **Note à l'owner (hors AC, aucun agent ne peut le faire) :** créer le token sur https://expo.dev/settings/access-tokens puis `gh secret set EXPO_TOKEN`. Sans ce secret, le workflow reste non fonctionnel même après cette tâche — celle-ci le rend seulement inoffensif et diagnosticable.

## Défaut adjacent à corriger au passage

`cache-dependency-path: mobile/package.json` dans les deux jobs : `npm ci` lit `mobile/package-lock.json` (présent dans le dépôt). La clé de cache doit pointer sur le lockfile, sinon le cache ne s'invalide pas quand les dépendances résolues changent.

## Vérification

Pas de moyen de déclencher un vrai build depuis un worktree isolé (et il ne faut surtout pas en déclencher un : quota EAS). La vérification passe par la lecture du YAML, `gh label list`, et `actionlint` s'il est disponible.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un push sur `main` touchant `mobile/**` ne peut plus déclencher d'`eas submit` : le déclencheur et/ou les conditions de job réservent le couple build production + submit aux tags `mobile-v*` et à `workflow_dispatch`, et le YAML modifié est commenté pour expliciter cette règle
- [x] #2 L'étape « Determine build profile » ne contient plus de branche morte : soit elle produit réellement des profils différents selon l'événement, soit elle est supprimée au profit d'une valeur unique explicite
- [x] #3 L'étape « Create GitHub Issue for persistent failures » ne référence plus aucun label absent du dépôt — vérifiable en croisant les labels cités dans le YAML avec la sortie de `gh label list`
- [x] #4 Le workflow déclare un bloc `permissions:` explicite couvrant au minimum `issues: write` pour le job `notify-failure` (et un `contents: read` par défaut ailleurs)
- [x] #5 Une garde en tête des jobs de build échoue immédiatement avec un message nommant `EXPO_TOKEN` quand le secret est vide, avant toute installation de Node ou de l'EAS CLI
- [x] #6 `cache-dependency-path` pointe sur `mobile/package-lock.json` dans les deux jobs de build
- [x] #7 `actionlint .github/workflows/mobile-build-distribute.yml` passe sans erreur — ou, si `actionlint` n'est pas installable dans le worktree, le fait est noté dans les Implementation Notes et le YAML est validé par `python -c "import yaml,sys; yaml.safe_load(open(...))"`
- [x] #8 `mobile/MOBILE_CI_CD.md` décrit le nouveau contrat de déclenchement (ce qui part sur tag, ce qui part sur dispatch, ce qui ne part plus sur push) et mentionne `EXPO_TOKEN` comme prérequis owner
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

`.github/workflows/mobile-build-distribute.yml`

- **Trigger** (AC #1) : le bloc `push` perd `branches: [main]` et `paths:` ; il ne
  reste que `tags: ["mobile-v*"]`. Un push de branche ne déclenche donc plus rien
  du tout — pas de build, pas de submit. Un en-tête de commentaire de ~25 lignes
  documente le contrat (deux points d'entrée : tag `mobile-v*` → production +
  submit ; `workflow_dispatch` → au choix de l'opérateur), explique pourquoi
  `branches` + `tags` dans le même bloc `push` était un OU et non un ET, et
  interdit explicitement de réintroduire un filtre de branche. En ceinture et
  bretelles, les deux étapes `Submit to …` portent en plus
  `(github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/mobile-v'))`,
  donc même si quelqu'un rouvre le trigger sur une branche plus tard, la
  soumission store reste hors d'atteinte.
- **Défauts de dispatch** : `profile` passe de `production` à `preview` et
  `submit` de `true` à `false`. Un run manuel lancé sans réfléchir est désormais
  inoffensif ; soumettre demande une action explicite.
- **Profil** (AC #2) : « Determine build profile » devient « Resolve build profile
  and submit flag », avec deux branches réellement distinctes (dispatch → entrées
  de l'opérateur ; sinon → tag, donc `production` + `submit=true`). La branche
  morte `elif tag … else …` qui retournait deux fois `production` a disparu. Le
  step émet aussi `submit`, consommé par l'étape de soumission (à la place de
  l'ancien `github.event.inputs.submit == 'true'` qui, sur un push, était vrai par
  défaut via le `github.event_name != 'workflow_dispatch' ||`).
- **Label d'issue** (AC #3) : `--label "bug,ci/cd"` → `--label "bug"`. `gh label list`
  sur le dépôt ne renvoie que les 9 labels GitHub par défaut (vérifié le
  2026-08-13) ; `bug` est le seul label cité dans le YAML après ce changement
  (`grep -n label` sur le fichier ne montre plus que `bug` et les commentaires
  qui l'expliquent). Un commentaire indique la commande `gh label create ci/cd …`
  à exécuter d'abord si on veut le remettre.
- **Permissions** (AC #4) : `permissions: contents: read` au niveau workflow, plus
  un bloc `permissions: {contents: read, issues: write}` sur le job
  `notify-failure` — sans quoi `gh issue create` reçoit un 403 même avec un label
  valide.
- **Garde `EXPO_TOKEN`** (AC #5) : premier step des deux jobs de build,
  `Require EXPO_TOKEN`, avant `actions/checkout`, `actions/setup-node` et
  `npm install -g eas-cli`. Il émet un `::error::` nommant `EXPO_TOKEN`, l'URL de
  création du token, la commande `gh secret set EXPO_TOKEN` et le pointeur vers
  `mobile/MOBILE_CI_CD.md`, puis `exit 1`.
- **Cache** (AC #6) : `cache-dependency-path: mobile/package-lock.json` dans
  `ios-build` et `android-build`.
- Divers : le résumé de succès ne prétend plus « Submitted » pour les deux
  plateformes (c'était faux dès qu'un submit était sauté) et rappelle de vérifier
  les steps de soumission ; « Missing `EXPO_TOKEN` » ajouté à la liste des causes
  fréquentes du résumé d'échec ; le champ Slack « Branch » devient « Ref » puisque
  le déclencheur est un tag.

`mobile/MOBILE_CI_CD.md` (AC #8) : schéma d'en-tête refait autour des deux entrées,
section « Workflow Triggers » réécrite avec un tableau événement → build/profil/
submit (dont la ligne « Push to a branch (`main` included) → **Nothing** »), une
sous-section expliquant le bug de trigger corrigé et où se trouve le feedback
per-commit (`pr.yml` / `main.yml`), l'exemple `gh workflow run` pour un preview
sans submit, les nouveaux défauts de dispatch, une sous-section « Owner
prerequisite: `EXPO_TOKEN` » (secret non provisionné au 2026-08-13, comportement
de la garde, procédure en 2 étapes), la note sur le label `bug` seul + les
permissions du job, et une entrée de troubleshooting pour la garde.

`docs/V1_LAUNCH_PLAN.md` : Phase 7 item 4 réécrit — il décrivait le workflow comme
« rouge et toujours trop agressif — inchangé ». Il liste maintenant ce qui est
corrigé et isole le seul reste : provisionner `EXPO_TOKEN` (action owner).

### Verification

- `actionlint 1.7.7` a pu être téléchargé dans le worktree (binaire hors dépôt,
  `/tmp`) : `actionlint .github/workflows/mobile-build-distribute.yml` → exit 0,
  0 erreur. `-verbose` confirme que le fichier est bien analysé (les règles
  `shellcheck`/`pyflakes` sont désactivées, ces binaires étant absents de la
  machine). Contrôle négatif : une copie temporaire avec une entrée invalide sur
  `actions/checkout` fait sortir actionlint en 1 avec 2 erreurs, donc le exit 0 du
  vrai fichier n'est pas un faux positif de chargement. À noter : le fichier
  *avant* modification passait déjà actionlint — les trois défauts de cette tâche
  sont sémantiques, pas syntaxiques.
- YAML parsé avec PyYAML : triggers = `{'push': {'tags': ['mobile-v*']}, 'workflow_dispatch': …}`,
  jobs = `ios-build, android-build, notify-failure, distribute-summary`,
  `permissions = {'contents': 'read'}`.
- `gh label list` : 9 labels (`bug`, `documentation`, `duplicate`, `enhancement`,
  `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`). Croisé avec
  les labels cités dans le YAML (`bug` seul) → aucun label absent référencé.

### Not done / out of scope

- **Aucun build ni submit déclenché**, conformément aux hard rules : le
  comportement réel du workflow ne pourra être constaté qu'au prochain tag
  `mobile-v*` ou dispatch manuel de l'owner. Ce que cette tâche garantit est
  lisible dans le YAML, pas dans un run.
- **`EXPO_TOKEN` reste non provisionné** — action owner (token sur
  https://expo.dev/settings/access-tokens puis `gh secret set EXPO_TOKEN`). Le
  workflow est maintenant inoffensif et diagnosticable, pas fonctionnel.
- `.github/workflows/mobile-store-promote.yml` a le même
  `cache-dependency-path: mobile/package.json` dans ses deux jobs et aucun bloc
  `permissions:`/garde `EXPO_TOKEN`. Hors périmètre de cette tâche (les AC ciblent
  `mobile-build-distribute.yml`), volontairement laissé tel quel — candidat à une
  tâche de suivi.
- Aucun test automatisé ajouté (règle projet).
<!-- SECTION:NOTES:END -->
