---
id: task-295
title: >-
  Stop the mobile app from dropping a valid session — no purge on network
  errors, single 401 interceptor, shared refresh promise, AppState revalidation
status: To Do
assignee: []
created_date: '2026-08-18 17:25'
labels:
  - bug
  - mobile
  - auth
dependencies:
  - task-293
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problème

Même avec un refresh token réparé (task-293) et pratiquement éternel (task-294), le client mobile perd la session pour des raisons qui n'ont rien à voir avec l'authentification. Quatre trous indépendants :

1. **Une coupure réseau déconnecte.** `AuthService.refresh()` appelle `TokenStorage.clearAll()` sur toute réponse non-OK (`mobile/src/services/authService.ts:136`), et une exception réseau remonte en `getValidToken() → null` (`authService.ts:170`), ce que `AuthContext` interprète comme une session morte et purge (`mobile/src/contexts/AuthContext.tsx:104-113`). Un métro, un avion ou un 5xx passager au mauvais moment coûte une reconnexion alors que le refresh token est parfaitement valide.
2. **Aucun intercepteur 401.** `mobile/src/services/apiClient.ts` ignore complètement l'authentification : les écrans passent le `token` en mémoire du contexte, et `getValidToken()` n'a aucun appelant hors `AuthContext`. Après un retour au premier plan tardif, les requêtes partent avec un JWT périmé, l'UI affiche des erreurs 401 et rien ne se répare avant un redémarrage à froid de l'app.
3. **Le refresh proactif repose sur un `setTimeout`** de la durée de l'access token (`AuthContext.tsx:38-73`), qui ne se déclenche pas de façon fiable en arrière-plan — constat déjà établi et documenté par task-278. Aucun listener `AppState` global n'existe : seul `/share-confirmation` en possède un.
4. **Refresh concurrents.** Le mutex `revalidationRef` ne couvre que `revalidateSession` ; le chemin du timer appelle `AuthService.refresh()` directement. Deux rotations peuvent donc partir en parallèle et se disputer un token single-use.

## Périmètre

- Ne purger le stockage sécurisé que sur un rejet d'authentification explicite du refresh token (401 accompagné du code `SESSION_EXPIRED`). Erreur réseau, timeout, 5xx et 429 : conserver les tokens, réessayer avec un backoff, et laisser l'utilisateur dans l'app avec un état hors ligne plutôt que sur l'écran de connexion.
- Un intercepteur unique dans `apiClient` : sur 401, tenter un refresh puis rejouer la requête une seule fois avant de propager l'erreur. Les écrans cessent de dépendre d'un token capturé en mémoire.
- Une seule promesse de refresh partagée par tous les appelants (timer, intercepteur, revalidation), pour qu'aucune rotation concurrente ne puisse partir.
- Un listener `AppState` dans `AuthProvider` : revalider la session à chaque passage au premier plan. Le `setTimeout` ne sert plus qu'aux longues sessions passées au premier plan.

## Ce qui doit survivre

Le garde-fou de partage posé par task-278 : le parking des intents (`share`, `local`, `current`), leur rejeu après connexion, et la revalidation au focus de `/share-confirmation`. Cette tâche renforce le socle sur lequel il repose et ne doit pas en changer le comportement.

## Notes à l'owner

Vérifications E2E manuelles après merge (ne peuvent pas être des ACs) :
- Mode avion pendant que l'access token expire, puis retour du réseau → l'app se recharge sans passer par l'écran de connexion.
- App en arrière-plan une nuit, puis retour au premier plan → l'inbox répond, sans erreur 401 et sans redémarrage à froid.
- Partager un lien depuis Safari après une longue mise en arrière-plan → le flux task-278 se comporte comme avant.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une erreur réseau, un timeout, un 5xx ou un 429 pendant un refresh ne vide plus le stockage sécurisé et ne fait plus basculer l'app sur l'écran de connexion
- [ ] #2 Seul un rejet d'authentification du refresh token (401 avec le code SESSION_EXPIRED) purge la session et redirige vers le login
- [ ] #3 apiClient tente un refresh puis rejoue une fois la requête ayant reçu un 401, et ne propage l'erreur qu'après l'échec de ce rejeu
- [ ] #4 Tous les chemins de refresh (timer, intercepteur, revalidation) passent par une promesse de refresh partagée unique : aucun appelant n'appelle plus AuthService.refresh() directement
- [ ] #5 AuthProvider revalide la session à chaque retour au premier plan via un listener AppState, indépendamment du timer
- [ ] #6 Le parking d'intent de task-278 et son rejeu après connexion sont préservés, ainsi que la revalidation au focus de /share-confirmation
- [ ] #7 npx tsc --noEmit et npm run lint sont clean dans mobile/
<!-- AC:END -->
