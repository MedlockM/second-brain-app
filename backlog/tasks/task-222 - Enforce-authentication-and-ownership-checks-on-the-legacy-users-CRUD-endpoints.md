---
id: task-222
title: Enforce authentication and ownership checks on the legacy users CRUD endpoints
status: Done
assignee: []
created_date: '2026-08-05 17:54'
updated_date: '2026-08-05 18:40'
labels:
  - security
  - api
  - release
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les endpoints de `media_summarizer/api/endpoints/users.py` sont exposés sans **aucune** dépendance d'authentification. Vérifié au 2026-08-05 :

- `create_user` (ligne 49) — `db=Depends(get_db)` seulement
- `get_user` (ligne 88) — lecture de n'importe quel user par id
- `get_user_by_email` (ligne 112) — énumération d'utilisateurs par email
- `update_user` (ligne 136) — modification de n'importe quel compte
- `delete_user` (ligne 187) — **suppression de n'importe quel compte**

Aucun de ces handlers ne dépend de `get_current_user`. N'importe quel appelant anonyme connaissant ou devinant un `user_id` peut lire, modifier ou supprimer un compte tiers. L'API dev est publiquement joignable sur `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`.

C'est un bloquant P0 absolu : cette surface ne doit pas atteindre un environnement staging ou production exposé.

## Objectif

Fermer la surface. La forme exacte est à l'appréciation de l'implémenteur après audit des appelants réels, mais le résultat doit être qu'aucune opération sur un compte utilisateur ne soit possible sans authentification et sans vérification que l'appelant agit sur son propre compte.

Points d'attention :

- **Identifier les appelants réels avant de casser quoi que ce soit** : le mobile, la suite `tests/e2e/` (dont `conftest.py` qui crée et supprime un user de test), et d'éventuels scripts d'ops. `conftest.py` doit continuer à fonctionner, éventuellement via un chemin authentifié.
- **`create_user`** fait doublon avec le flow d'inscription authentifié (`/api/v1/auth/register`). Vérifier si l'endpoint doit simplement être retiré plutôt que protégé.
- **`get_user_by_email`** est un vecteur d'énumération de comptes. Sauf usage interne prouvé, le retirer.
- **`delete_user`** ne doit pas servir de base à la suppression de compte RGPD : cf. la tâche dédiée. Ici on ferme uniquement la surface publique.
- Vérifier qu'aucun autre router n'expose la même classe de problème (audit rapide des endpoints sans `get_current_user`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every retained route in media_summarizer/api/endpoints/users.py requires an authenticated caller
- [ ] #2 Any route that acts on a specific user id or email verifies that the authenticated caller owns that account, returning the same status code for both forbidden and not-found so account existence is not leaked
- [ ] #3 Routes that duplicate the authenticated auth flow or enable account enumeration are removed rather than merely protected, with the decision justified in the task notes
- [ ] #4 An unauthenticated request to each former public route is proven to be rejected against AWS dev
- [ ] #5 The tests/e2e suite including conftest.py user setup and teardown still passes against AWS dev after the change
- [ ] #6 The mobile app has no remaining call path that depended on an unauthenticated users route
- [ ] #7 A short audit confirms no other active router exposes user-scoped mutations without an authentication dependency, and any finding is either fixed or recorded as a follow-up task
<!-- AC:END -->
