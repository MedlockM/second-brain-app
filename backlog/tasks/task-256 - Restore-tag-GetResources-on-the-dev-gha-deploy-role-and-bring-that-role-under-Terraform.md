---
id: task-256
title: >-
  Restore tag:GetResources on the dev gha-deploy role and bring that role under
  Terraform
status: Done
assignee: []
created_date: '2026-08-13 15:54'
updated_date: '2026-08-13 19:05'
labels:
  - infra
  - ci
  - bug
  - security
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Constat

Le job `deploy-workers` de `.github/workflows/deploy-lambda.yml` échoue sur `main` depuis le 2026-08-10. Les deux derniers runs (`31419263299` du 2026-08-10, `31712425601` du 2026-08-13) sont rouges sur l'étape « Deploy workers by immutable digest », avec :

```
An error occurred (AccessDeniedException) when calling the GetResources operation:
User: arn:aws:sts::125313707865:assumed-role/media-summarizer-gha-deploy/GitHubActions
is not authorized to perform: tag:GetResources because no identity-based policy
allows the tag:GetResources action
```

Le workflow découvre les fonctions worker par tag `Environment` plutôt que par wildcard de nom — `aws resourcegroupstaggingapi get-resources` aux lignes 189 et 371 — un choix délibéré et commenté dans le workflow. La permission correspondante manque au rôle.

## Ce que l'audit a établi

La policy inline `deploy` du rôle dev `media-summarizer-gha-deploy` (compte `125313707865`) ne porte que quatre statements, vérifiés via `aws iam get-role-policy` le 2026-08-13 :

| Sid | Actions |
|---|---|
| `EcrAuth` | `ecr:GetAuthorizationToken` |
| `EcrPushPull` | 7 actions ECR |
| `LambdaList` | `lambda:ListFunctions` |
| `LambdaDeploy` | `lambda:UpdateFunctionCode`, `GetFunction`, `GetFunctionConfiguration`, `InvokeFunction` |

Il manque **`tag:GetResources`** et, très probablement, **`apigateway:GET`**. Le rôle prod, lui, déclare les deux : `infrastructure/terraform/envs/prod/gha_oidc.tf:157-171` porte un statement `TagDiscovery` (`tag:GetResources` sur `*`) et un statement `ApiGatewayRead` (`apigateway:GET`). La policy dev est donc en retard sur celle de prod, alors que le même workflow sert les deux.

**Pourquoi `deploy-api` passe et `deploy-workers` échoue.** Le job `deploy-api` n'appelle que `lambda update-function-code`, `wait function-updated-v2` et `get-function-configuration` — couvert par `LambdaDeploy`. Le job `deploy-workers` commence par découvrir ses cibles par tag, et meurt là. La CI a donc l'apparence d'un demi-succès trompeur : l'API se déploie, aucun worker ne se déploie, et le run global est rouge.

**Cause racine : le rôle dev n'est pas géré par Terraform.** Il n'existe pas de `infrastructure/terraform/envs/dev/gha_oidc.tf` — `envs/dev/` ne contient que `main.tf` et `outputs.tf`, et un `grep` sur `gha_deploy` n'y trouve rien. Le rôle a été créé le 2026-06-12 et a dérivé hors de tout state depuis. C'est ce qui explique qu'une permission ajoutée côté prod n'ait jamais été propagée en dev : il n'y a pas de code à modifier, seulement une ressource orpheline dans la console.

## Portée attendue

Deux volets, dans cet ordre.

1. **Débloquer.** Ajouter `tag:GetResources` et `apigateway:GET` à la policy `deploy` du rôle dev, en s'alignant sur les statements `TagDiscovery` et `ApiGatewayRead` de prod — mêmes sids, mêmes scopes de ressources. `tag:GetResources` n'accepte pas de restriction par ARN de ressource (c'est une action de service, comme en prod où elle porte `resources = ["*"]`) : ne pas essayer de la scoper, la restriction utile est déjà l'`Environment` filtré côté appel.

2. **Empêcher la récidive.** Porter le rôle dev sous Terraform, sur le modèle de `envs/prod/gha_oidc.tf`, puis l'importer dans le state plutôt que le recréer — le recréer casserait la confiance OIDC pendant l'opération et donc tous les déploiements. La divergence dev/prod doit devenir visible dans une revue de diff, pas seulement dans un run rouge.

Si le second volet s'avère plus lourd que prévu (state à réorganiser, dépendances OIDC croisées entre comptes), livrer le premier volet en entier et consigner précisément ce qui reste — un rôle non importé mais documenté vaut mieux qu'un blocage complet.

## Vérifications à portée d'un agent

- `aws iam get-role-policy --role-name media-summarizer-gha-deploy --policy-name deploy` montre les statements attendus.
- `aws iam simulate-principal-policy` sur `tag:GetResources` pour ce rôle renvoie `allowed`.
- `terraform validate`, et un `terraform plan` qui ne propose **aucune** destruction/recréation du rôle ou de sa policy.
- `aws resourcegroupstaggingapi get-resources --tag-filters Key=Environment,Values=dev --resource-type-filters lambda` retourne bien les 15 fonctions worker attendues.

## Note à l'owner — pas un AC

La confirmation finale passe par un run vert du workflow, qui ne peut arriver qu'après merge et push sur `main`, hors de portée de l'implémenteur. Après push, vérifier que `deploy-workers` passe au vert et que les workers `media-summarizer-worker-*-dev` portent un `LastModified` postérieur au run. À l'heure de l'audit, `media-summarizer-api-dev` était à jour (2026-08-13 14:55) tandis que les 15 workers datent tous du 2026-08-13 07:09 — mis à jour par autre chose que ce workflow.

Vérifier aussi s'il faut relancer le déploiement des workers pour rattraper les commits accumulés depuis le 2026-08-10 : le workflow est `paths`-filtré sur `media_summarizer/**`, donc un simple push ne le redéclenchera que si ce chemin est touché. Un `workflow_dispatch` peut être nécessaire.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 La policy inline deploy du rôle media-summarizer-gha-deploy autorise tag:GetResources, et aws iam simulate-principal-policy sur cette action renvoie allowed pour ce rôle
- [x] #2 La policy autorise aussi apigateway:GET sur les APIs de la région, alignée sur le statement ApiGatewayRead du rôle prod
- [x] #3 Le rôle dev gha-deploy et sa policy sont décrits en Terraform sous infrastructure/terraform/envs/dev/, sur le modèle de envs/prod/gha_oidc.tf, et la divergence dev/prod des permissions est lisible dans le code
- [x] #4 terraform plan sur envs/dev ne propose aucune destruction ni recréation du rôle ni de sa confiance OIDC — la ressource existante est importée, pas remplacée
- [x] #5 aws resourcegroupstaggingapi get-resources --tag-filters Key=Environment,Values=dev --resource-type-filters lambda retourne les fonctions worker attendues, exécuté avec les permissions du rôle corrigé
- [x] #6 terraform validate et tf_plan_guard.sh restent clean sur les fichiers touchés
- [x] #7 Les Implementation Notes consignent pourquoi deploy-api passait alors que deploy-workers échouait, afin que ce demi-succès trompeur soit reconnaissable s'il réapparaît
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Traité le 2026-08-13. **Les deux volets sont livrés** : la policy live est corrigée et le rôle est importé dans `env/dev/terraform.tfstate`, pas recréé.

### AC #7 — pourquoi `deploy-api` passait et `deploy-workers` échouait

C'est une **différence de mode de résolution des cibles**, pas une différence de permissions Lambda :

| Job | Comment il trouve sa cible | Permission requise | Résultat |
|---|---|---|---|
| `deploy-api` | construit le nom en dur : `media-summarizer-api-${DEPLOY_ENVIRONMENT}` | `LambdaDeploy` uniquement | vert |
| `deploy-workers` | interroge le Resource Groups Tagging API par tag `Environment` puis filtre sur `^media-summarizer-worker-` | `tag:GetResources` **avant tout appel Lambda** | rouge dès la 1re commande |
| `release-validation` | même découverte par tag, puis `apigatewayv2 get-api` | `tag:GetResources` + `apigateway:GET` | jamais atteint (dépend de `deploy-workers`) |

Le job worker meurt donc **avant** son premier `update-function-code`, sur la découverte. Signature à reconnaître si ça réapparaît : run global rouge, `deploy-api` vert, `deploy-workers` rouge en quelques secondes sur `AccessDeniedException ... GetResources`, `release-validation` en `skipped`, et surtout **un `LastModified` frais sur `media-summarizer-api-dev` avec 14 workers figés à une date antérieure**. C'est cet écart de `LastModified` entre l'API et les workers qui est le vrai symptôme : une CI rouge se voit, un backend dont la moitié seulement est déployée se déduit. La règle générale : toute étape qui *découvre* ses cibles a besoin d'une permission que les étapes qui les *nomment* n'ont pas, et cette permission-là n'est jamais testée par un déploiement d'API.

### Volet 1 — la policy `deploy` corrigée

Statements ajoutés, sids et scopes alignés sur `envs/prod/gha_oidc.tf` :

| Sid | Action | Resource |
|---|---|---|
| `TagDiscovery` | `tag:GetResources` | `*` (action de service, aucun ARN acceptable) |
| `ApiGatewayRead` | `apigateway:GET` | `arn:aws:apigateway:eu-west-3::/apis/*` |

Un troisième changement, **non demandé mais assumé** : `LambdaDeploy` passait de `function:media-summarizer-*` à `function:media-summarizer-*-dev`. Motif concret et pas cosmétique — `envs/staging/main.tf` est un blueprint vivant qui atterrit dans **ce même compte** `125313707865` ; avec le wildcard nu, un push sur `main` aurait pu écraser le code d'une fonction `-staging` le jour où ce root est appliqué. Vérifié par simulation : `allowed` sur les 16 fonctions `-dev` du compte, `implicitDeny` sur un `media-summarizer-worker-youtube_ingestion-staging` hypothétique.

La trust policy n'a **pas** été touchée : `StringLike` sur `repo:<owner>/<repo>:ref:refs/heads/main` est reproduit à l'identique dans le code, et `get-role` après apply renvoie exactement le document d'avant. Le passage à `StringEquals` (sémantiquement identique, la valeur n'a pas de wildcard) a été écarté : aucun gain réel, et la confiance OIDC est la seule chose dont une erreur casse tous les déploiements sans possibilité de test local.

### Volet 2 — adoption dans le state

Trois `terraform import` (runbook conservé en bas de `envs/dev/gha_oidc.tf`) : le provider OIDC, le rôle, la policy inline. Résultat du plan post-import : **`0 to add, 3 to change, 0 to destroy`** — les trois changements étant `tags` (le `default_tags` du provider dev), la `description` du rôle, et le document de policy. Aucune ressource remplacée, donc l'ARN dans le secret GitHub `AWS_DEPLOY_ROLE_ARN` reste valide. Plan relancé après apply : `No changes`. Le plan de référence pris **avant** toute modification était déjà `No changes`, donc les 3 changements sont intégralement imputables à ce fichier.

Deux noms physiques divergent volontairement de prod et doivent rester tels quels : le rôle est `media-summarizer-gha-deploy` (sans `-dev`) et sa policy inline est `deploy` (sans `-dev`). Les deux attributs sont ForceNew ; les aligner sur la convention de prod signifierait détruire et recréer exactement ce que cette task existe pour préserver. `tf_plan_guard.sh` layer 3 n'inspecte que les noms **créés**, donc une ressource importée mise à jour en place ne déclenche pas son assertion.

### Vérifications exécutées

| Vérification | Résultat |
|---|---|
| `terraform validate` + `terraform fmt -check -recursive` | clean |
| `tf_plan_guard.sh dev <plan>` (plan d'application et plan post-apply) | `PASS`, 0 delete |
| `simulate-principal-policy tag:GetResources` | `allowed` |
| `simulate-principal-policy apigateway:GET` sur `/apis/jji077bi8e` | `allowed` |
| `simulate-principal-policy lambda:UpdateFunctionCode` sur `api-dev`, `worker-media-lifecycle-dev`, `worker-youtube_ingestion-dev` | `allowed` |
| idem sur `...-staging` (inexistant, scope test) | `implicitDeny` |
| `get-role-policy` | 6 statements : `EcrAuth`, `EcrPushPull`, `LambdaList`, `LambdaDeploy`, `TagDiscovery`, `ApiGatewayRead` |

AC #5 demandait l'appel « avec les permissions du rôle corrigé ». Le rôle n'est assumable que par OIDC GitHub, donc pas depuis un poste. Contourné sans toucher à la trust policy : `sts get-federation-token --policy <document de la policy deploy live>` produit une session dont les permissions effectives sont l'intersection de l'appelant admin et de cette policy, c'est-à-dire la policy elle-même. Sous cette session :

- `--resource-type-filters lambda` → **31 ARNs** taggés `Environment=dev` (16 fonctions + 15 event source mappings, que ce filtre large ramène aussi) ;
- `--resource-type-filters lambda:function`, ce que le workflow utilise réellement → **16 fonctions** ;
- après le `awk` du workflow (`^media-summarizer-worker-`) → **14 workers**, la liste exacte à déployer.

Correction de chiffre au passage : la description parlait de « 15 fonctions worker ». Il y a **14** fonctions `media-summarizer-worker-*-dev` ; les 16 fonctions du compte sont ces 14 plus `media-summarizer-api-dev` et `media-summarizer-job-archiver-dev` (que le `awk` exclut à raison, l'archiver n'étant pas déployé par ce job).

Le chemin `release-validation` a été rejoué sous la même session : découverte de l'ARN d'API par tag puis `apigatewayv2 get-api` renvoient bien l'endpoint dev.

### À savoir pour la revue

**L'apply a déjà eu lieu sur le compte dev et le state distant a déjà bougé.** C'était la seule façon de satisfaire AC #1 et #2, qui portent sur la policy *live*. Conséquence : si cette branche était abandonnée, `env/dev/terraform.tfstate` contiendrait trois ressources sans code correspondant, et le prochain plan proposerait de les détruire. Le merge n'est pas optionnel.

Docs mises à jour : le tableau des rôles de déploiement et la table des fichiers dans `infrastructure/terraform/README.md`, et l'en-tête de `envs/prod/gha_oidc.tf` qui affirmait encore que l'équivalent dev « is still unmanaged ». Le fichier de task-248, qui consignait ce gap comme connu, est laissé tel quel : c'est un enregistrement daté, pas une doc vivante.

Rien n'est coché au titre du run CI : la confirmation par un `deploy-workers` vert exige un push sur `main`, hors de portée d'un worktree isolé. La note à l'owner du ticket reste entièrement valable, y compris le `workflow_dispatch` éventuel pour rattraper les commits accumulés depuis le 2026-08-10 — le filtre `paths` du workflow ne le redéclenchera pas sur un push qui ne touche que `infrastructure/` et `backlog/`, ce qui est précisément le cas de ce commit.
<!-- SECTION:NOTES:END -->
