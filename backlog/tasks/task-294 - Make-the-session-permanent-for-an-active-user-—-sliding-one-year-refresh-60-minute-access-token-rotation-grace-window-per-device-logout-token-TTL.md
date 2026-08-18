---
id: task-294
title: >-
  Make the session permanent for an active user — sliding one-year refresh,
  60-minute access token, rotation grace window, per-device logout, token TTL
status: In Progress
assignee: []
created_date: '2026-08-18 17:24'
labels:
  - auth
  - feature
dependencies:
  - task-293
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Décision de l'owner (2026-08-18) : **un utilisateur ne doit jamais avoir à se reconnecter**. Même une fois le refresh réparé (task-293), la session reste bornée à 30 jours absolus, parce que `/api/auth/refresh` recrée le token de remplacement avec le `expires_at` d'origine (`media_summarizer/api/endpoints/auth.py:206`) : un utilisateur quotidien est éjecté tous les 30 jours.

## Politique cible

- **Refresh glissant d'un an, sans plafond absolu.** Chaque rotation repose `expires_at = now + 1 an`. Un utilisateur qui ouvre l'app au moins une fois par an ne se reconnecte jamais, et un appareil abandonné finit malgré tout par sortir du système. La durée reste pilotée par `REFRESH_TOKEN_EXPIRE_DAYS` (`media_summarizer/utils/auth_utils.py:37`), dont le défaut passe de 30 à 365. L'option retenue est explicitement le glissant sans plafond, pas une date d'expiration lointaine figée.
- **Access token à 60 minutes** au lieu de 30. Sans conséquence sur la révocation : `get_current_user` relit l'utilisateur en DynamoDB à chaque requête (`media_summarizer/api/dependencies/auth.py:76`), donc un compte supprimé est rejeté immédiatement quelle que soit la durée du JWT.
- **Fenêtre de grâce sur la rotation.** La rotation est single-use (`AuthToken.mark_as_used`), donc deux refresh concurrents suffisent à déconnecter l'utilisateur. Un refresh token consommé depuis moins de 60 secondes doit renvoyer le couple de tokens déjà émis pour cette rotation, au lieu d'un 401. Au-delà de la fenêtre, la réutilisation reste un rejet. Ce point compte doublement quand un backup restauré sur un nouvel appareil laisse deux appareils détenir le même token.
- **Logout par appareil.** `revoke_user_tokens(user_id, REFRESH_TOKEN)` (`media_summarizer/utils/database_async.py:861`) révoque tous les appareils du compte : se déconnecter d'une tablette déconnecte le téléphone. Le logout ne doit révoquer que la lignée de tokens de l'appareil courant. La lignée peut être générée côté serveur au login et propagée à chaque rotation, sans identifiant fourni par le client ; en contrepartie, le logout mobile doit présenter son refresh token (déjà en keychain) en plus de son access token — c'est le seul changement mobile de cette tâche. La révocation globale reste utilisée par la suppression de compte.
- **TTL DynamoDB sur `auth_tokens`.** La table n'a aucun TTL (`infrastructure/terraform/modules/platform/dynamodb_core_tables.tf:107`) et conserve à vie une ligne par rotation. Ajouter un attribut d'expiration epoch et l'activer, positionné strictement après `expires_at` pour qu'un TTL ne puisse jamais tuer une session vivante.

## Notes à l'owner

- `terraform apply` du TTL à faire côté owner ; il porte sur une table avec `prevent_destroy` et PITR, l'ajout d'un TTL est une modification en place sans remplacement — à confirmer sur le `plan`.
- Vérification après déploiement (ne peut pas être une AC) : provoquer deux refresh consécutifs et lire l'item en base — `expires_at` du dernier token doit être à ~1 an de l'appel, et non la date du login initial.
- Vérification manuelle du logout par appareil : se connecter sur deux appareils avec le même compte, se déconnecter de l'un, vérifier que l'autre continue de fonctionner après l'expiration de son access token.
- Non retenu délibérément : un « déconnecter tous mes appareils » dans les réglages. Le mécanisme de révocation globale existe côté serveur, l'exposer dans l'UI est une tâche produit distincte.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 La rotation dans /api/auth/refresh réémet un expires_at glissé à chaque appel et ne propage plus l'expiration absolue du token d'origine
- [x] #2 Le défaut de REFRESH_TOKEN_EXPIRE_DAYS est 365 et .env.example documente la politique glissée sans plafond absolu
- [x] #3 Le défaut de JWT_ACCESS_TOKEN_EXPIRE_MINUTES est 60 dans le code et dans .env.example
- [x] #4 Un refresh token consommé depuis moins de 60 secondes renvoie le couple de tokens déjà émis pour cette rotation au lieu d'un 401, et sa réutilisation au-delà de la fenêtre reste rejetée
- [x] #5 Le logout ne révoque que la lignée de tokens de l'appareil qui le demande : il n'appelle plus la révocation globale des refresh tokens du compte
- [x] #6 La suppression de compte continue de révoquer toutes les lignées du compte
- [x] #7 Le logout mobile transmet son refresh token en plus de son access token, et npx tsc --noEmit et npm run lint sont clean dans mobile/
- [x] #8 La table auth_tokens déclare un attribut TTL activé dans Terraform, calculé strictement après expires_at, et terraform validate est clean
- [x] #9 ruff check et mypy sont clean sur media_summarizer/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### La session glisse, elle ne se plafonne plus

`/api/auth/refresh` recréait le token de remplacement avec l'`expires_at` du token
consommé, ce qui figeait la session à la date du login. La rotation appelle maintenant
`get_refresh_token_expires_at()` comme le login, donc `expires_at = now + 365 j` à chaque
appel. Le paramètre `absolute_expires_at` de `AuthToken.create_refresh_token` a disparu
avec son défaut `expires_in_days=30` : l'expiry est un argument requis, décidé par
l'appelant, ce qui rend impossible de refabriquer un plafond absolu par inadvertance.

Défauts déplacés dans `media_summarizer/utils/auth_utils.py` :
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` 30 → 60, `REFRESH_TOKEN_EXPIRE_DAYS` 30 → 365. Le
secret runtime `dev` ne définit ni l'une ni l'autre de ces variables (vérifié par
`aws secretsmanager get-secret-value`, clés seulement) : les défauts du code sont donc
bien ce qui s'applique à l'exécution, sans intervention côté secret.

### Lignée d'appareil : un uuid généré au login, recopié à chaque rotation

`AuthToken` porte un `lineage_id` (uuid4, `default_factory`). Le login / register / les
deux endpoints natifs n'en passent aucun : chaque nouvelle session ouvre sa propre
lignée. `/refresh` passe celui du token consommé, donc toute la chaîne de rotations d'un
appareil partage un identifiant stable. Le client n'en voit jamais rien et n'en fournit
jamais : c'est une identité purement serveur, ce qui évite qu'un appareil puisse se faire
passer pour un autre ou révoquer la session d'un tiers.

`revoke_user_tokens(user_id, token_type)` est **supprimé** — plus aucun appelant. À sa
place, `revoke_refresh_token_lineage(user_id, lineage_id)` ne désactive que les tokens de
refresh de la lignée demandée. Une lignée n'a en régime normal qu'un seul token vivant
(sa tête), mais la boucle couvre toute la lignée : un logout qui court avec un refresh
ne peut pas laisser le successeur utilisable.

`get_auth_tokens_by_user_id` est désormais **paginé**. Ce n'était pas cosmétique : avec un
refresh glissant qui écrit une ligne par rotation, un compte ancien dépasse la page de
1 Mo d'une query, et c'est exactement la liste que la suppression de compte itère pour
effacer les lignes — une lecture tronquée aurait laissé des sessions derrière elle.

### Fenêtre de grâce de 60 s

Au moment de la rotation, `mark_as_rotated` (qui remplace `mark_as_used`) enregistre sur
la ligne consommée le couple qu'elle a produit : `replaced_by_refresh_token` et
`replaced_by_access_token`. Un `/refresh` qui présente un token consommé depuis moins de
`REFRESH_ROTATION_GRACE_SECONDS` (60) rejoue ce couple au lieu de répondre 401 ; passé la
fenêtre, ou si la ligne n'a pas de couple enregistré, c'est un rejet comme avant. Le test
de grâce précède volontairement les contrôles `is_active` / `used_at`, puisqu'un token
rotaté est précisément inactif et consommé.

Deux propriétés qui comptent :

- Un token **révoqué par un logout** a `used_at = None` et aucun couple enregistré, donc
  il n'est jamais rejouable. Une déconnexion ne peut pas être annulée par un rejeu.
- La réponse de rejeu annonce `expires_in = access_seconds - âge de la rotation`, pas une
  durée pleine : l'access token rejoué a déjà vécu jusqu'à une minute, et le client
  calcule son expiration locale à partir de cette valeur.

L'ordre des écritures de la rotation est également volontaire : le successeur est créé
**avant** que le parent soit marqué consommé, de sorte qu'une panne entre les deux laisse
l'appelant avec un token qui fonctionne encore, plutôt qu'une session morte.

### Logout par appareil

`POST /api/auth/logout` prend un corps `{"refresh_token": "..."}` (`LogoutRequest`) en
plus du header `Authorization`. L'access token dit *qui* se déconnecte, le refresh token
dit *depuis quel appareil* — sans lui le serveur ne peut que tout révoquer. Un token
inconnu, déjà révoqué ou appartenant à quelqu'un d'autre renvoie un succès sans rien
révoquer : le logout est idempotent et ne doit pas servir d'oracle sur l'existence d'un
token.

Côté mobile, le seul changement est dans `mobile/src/services/authService.ts` : `logout()`
lit le refresh token du secure store et le poste avec l'appel. La signature
`logout(token)` est inchangée, donc `AuthContext.tsx` n'a pas été touché — task-295 refond
ce fichier en parallèle, et la surface de conflit est restée d'une seule fonction. S'il
n'y a aucun refresh token stocké, il n'y a pas de session serveur à fermer et seul le
nettoyage local est effectué.

La révocation de **toutes** les lignées d'un compte reste le fait de la suppression de
compte (`core/services/account_deletion_service.py:_purge_identity`), qui supprime les
lignes plutôt que de les désactiver — plus fort qu'une révocation, et inchangé ici hormis
le bénéfice de la pagination.

### TTL

`auth_tokens` n'avait aucun TTL et gardait à vie une ligne par rotation. Le modèle écrit
maintenant `expire_at` (epoch, Number) à **chaque** put, valant `expires_at +
TOKEN_TTL_MARGIN` avec une marge de 7 jours, et Terraform active le TTL sur cet attribut.

La marge est la propriété de sûreté demandée : la date de balayage est strictement
postérieure au moment où le token cesse de pouvoir authentifier quoi que ce soit, donc un
TTL ne peut jamais tuer une session vivante, et 7 jours couvrent largement les ~48 h que
DynamoDB peut prendre pour honorer un TTL. `expire_at` n'est jamais une durée de vie
autonome : il est toujours dérivé de `expires_at`, y compris pour les tokens de
vérification d'e-mail.

Une ligne écrite avant cette tâche n'a pas de `lineage_id` : `from_dynamodb_item` lui en
attribue un neuf à la lecture, ce qui est la bonne réponse (elle appartient à exactement
une session d'appareil) et évite un crash de validation Pydantic sur les 145 lignes
présentes en dev.

### Vérifications

- `ruff check media_summarizer/` → clean ; `mypy media_summarizer/` → 170 fichiers, 0 erreur.
- `terraform validate` (env `dev`) → Success ; `terraform fmt -check` → clean.
- `terraform plan -target=module.platform.aws_dynamodb_table.auth_tokens_v1` contre l'état
  `dev` réel → `0 to add, 1 to change, 0 to destroy`, `~ ttl { + attribute_name =
  "expire_at", enabled = false -> true }`. C'est la confirmation demandée dans la
  description : l'ajout du TTL est une modification **en place**, sans remplacement, sur
  une table `prevent_destroy` avec PITR. L'`apply` reste à la charge de l'owner.
- `aws dynamodb describe-time-to-live --table-name auth_tokens-dev` → `DISABLED` avant
  apply, ce qui est l'état attendu tant que l'owner n'a pas appliqué.
- `npx tsc --noEmit` et `npm run lint` dans `mobile/` → 0 erreur (8 warnings préexistants,
  aucun dans `authService.ts`).

Aucun test automatisé n'a été écrit, conformément aux règles du dépôt ; aucun AC n'en
demandait.

### Ce que l'owner doit vérifier après déploiement

Hors de portée d'un worktree non déployé, donc pas des ACs :

- Deux `/refresh` consécutifs, puis lire la ligne en base : l'`expires_at` du dernier
  token doit être à ~1 an de l'appel, pas à la date du login.
- Deux appareils connectés au même compte, déconnexion de l'un : l'autre doit continuer à
  fonctionner après l'expiration de son access token.
- Deux `/refresh` concurrents avec le même refresh token : les deux doivent obtenir une
  session utilisable, aucun 401.
- `terraform apply` du TTL, puis `describe-time-to-live` → `ENABLED`.
<!-- SECTION:NOTES:END -->
