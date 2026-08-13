---
id: task-256
title: >-
  Restore tag:GetResources on the dev gha-deploy role and bring that role under
  Terraform
status: To Do
assignee: []
created_date: '2026-08-13 15:54'
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
- [ ] #1 La policy inline deploy du rôle media-summarizer-gha-deploy autorise tag:GetResources, et aws iam simulate-principal-policy sur cette action renvoie allowed pour ce rôle
- [ ] #2 La policy autorise aussi apigateway:GET sur les APIs de la région, alignée sur le statement ApiGatewayRead du rôle prod
- [ ] #3 Le rôle dev gha-deploy et sa policy sont décrits en Terraform sous infrastructure/terraform/envs/dev/, sur le modèle de envs/prod/gha_oidc.tf, et la divergence dev/prod des permissions est lisible dans le code
- [ ] #4 terraform plan sur envs/dev ne propose aucune destruction ni recréation du rôle ni de sa confiance OIDC — la ressource existante est importée, pas remplacée
- [ ] #5 aws resourcegroupstaggingapi get-resources --tag-filters Key=Environment,Values=dev --resource-type-filters lambda retourne les fonctions worker attendues, exécuté avec les permissions du rôle corrigé
- [ ] #6 terraform validate et tf_plan_guard.sh restent clean sur les fichiers touchés
- [ ] #7 Les Implementation Notes consignent pourquoi deploy-api passait alors que deploy-workers échouait, afin que ce demi-succès trompeur soit reconnaissable s'il réapparaît
<!-- AC:END -->
