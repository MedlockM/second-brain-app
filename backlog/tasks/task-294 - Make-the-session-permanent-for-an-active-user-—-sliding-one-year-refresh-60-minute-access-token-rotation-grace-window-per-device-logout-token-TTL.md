---
id: task-294
title: >-
  Make the session permanent for an active user — sliding one-year refresh,
  60-minute access token, rotation grace window, per-device logout, token TTL
status: To Do
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
- [ ] #1 La rotation dans /api/auth/refresh réémet un expires_at glissé à chaque appel et ne propage plus l'expiration absolue du token d'origine
- [ ] #2 Le défaut de REFRESH_TOKEN_EXPIRE_DAYS est 365 et .env.example documente la politique glissée sans plafond absolu
- [ ] #3 Le défaut de JWT_ACCESS_TOKEN_EXPIRE_MINUTES est 60 dans le code et dans .env.example
- [ ] #4 Un refresh token consommé depuis moins de 60 secondes renvoie le couple de tokens déjà émis pour cette rotation au lieu d'un 401, et sa réutilisation au-delà de la fenêtre reste rejetée
- [ ] #5 Le logout ne révoque que la lignée de tokens de l'appareil qui le demande : il n'appelle plus la révocation globale des refresh tokens du compte
- [ ] #6 La suppression de compte continue de révoquer toutes les lignées du compte
- [ ] #7 Le logout mobile transmet son refresh token en plus de son access token, et npx tsc --noEmit et npm run lint sont clean dans mobile/
- [ ] #8 La table auth_tokens déclare un attribut TTL activé dans Terraform, calculé strictement après expires_at, et terraform validate est clean
- [ ] #9 ruff check et mypy sont clean sur media_summarizer/
<!-- AC:END -->
