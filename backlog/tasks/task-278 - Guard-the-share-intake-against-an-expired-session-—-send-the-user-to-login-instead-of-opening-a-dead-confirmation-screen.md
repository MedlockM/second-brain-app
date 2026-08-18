---
id: task-278
title: >-
  Guard the share intake against an expired session — send the user to login
  instead of opening a dead confirmation screen
status: Done
assignee:
  - '@Codex'
created_date: '2026-08-17 21:53'
updated_date: '2026-08-18 01:01'
labels:
  - bug
  - mobile
  - auth
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Observed on 2026-08-17: when the session has expired, sharing a media into the app still opens the share-confirmation screen. The screen looks fully usable — preview, collection picker, tags, Save — but nothing in it works: Save ends on `You must be signed in to save links.` (or the equivalent upload error), and the content is lost. The user is left believing the app is usable while their session is gone; the only honest outcome here is to be sent to the login screen.

## Why it happens

Two independent holes, both must be closed:

1. **`/share-confirmation` is an unguarded root route.** The auth guard lives in `mobile/app/(tabs)/_layout.tsx:25` and `mobile/app/index.tsx:36`; `/share-confirmation` sits at the root of `mobile/app/`, outside the `(tabs)` group, so nothing redirects it when `isAuthenticated` is false. `ShareIntentContext` only checks auth once, at intake time (`mobile/src/contexts/ShareIntentContext.tsx:367`), and never again — so a session that expires while the screen is open leaves it open and interactive.

2. **`isAuthenticated` can still be true with a dead session.** The proactive refresh is a `setTimeout` scheduled in `mobile/src/contexts/AuthContext.tsx` (`scheduleTokenRefresh`, `REFRESH_BUFFER_MS`). Timers do not fire reliably while the app is backgrounded, and the app is backgrounded for exactly as long as the user was elsewhere before hitting Share. On the warm path (app resumed from a share intent rather than cold-started), the in-memory state is whatever it was when the app went to sleep — authenticated — even though the stored token is long expired and `AuthService.getValidToken()` would now return null. `processShareIntent` therefore navigates, and the failure only surfaces on Save.

Note that the cold-start path is already correct: `AuthContext` re-validates at init, the intent is parked in `pendingIntentRef`, and the queued intent is replayed after login (`ShareIntentContext.tsx:381`). That replay behaviour is the target shape and must survive this fix.

## Scope

- Re-validate the session when the app comes back to the foreground with a share intent, before any navigation to `/share-confirmation` — the check must be against the stored token's real validity (with a refresh attempt), not against the in-memory `isAuthenticated` flag alone.
- When the session is dead: do not open the confirmation screen. Park the intent as the cold-start path already does, surface the existing `sessionError` on the login screen (`mobile/app/(auth)/login.tsx:56` already renders it), and replay the parked intent after a successful sign-in so the share the user made is not lost.
- Guard `/share-confirmation` itself so it cannot stay open (or be reached) without a session — a session expiring while the screen is already open must close it and land the user on login, rather than leaving a screen whose Save always fails.
- Same treatment for the non-share entries into the same screen — the inbox "add" gesture (`startLocalUpload`, file and photo intakes) reaches `/share-confirmation` through the same route and has the same hole.

## Notes to the owner

- Manual E2E check after merge (cannot be an AC): sign in, force the session to expire (shorten the token TTL or clear it from the backend side), background the app, share a link from Safari/Instagram — expect the login screen with "Your session has expired. Please sign in again.", and after signing in, the confirmation screen opening on the link that was shared.
- Worth checking on both platforms: the iOS share extension and the Android share intent take different paths into `+native-intent.tsx`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Sharing content while the session is expired never opens /share-confirmation: the code path re-validates the stored token (refresh attempt included) before navigating, and routes to the login screen instead when it is invalid
- [x] #2 The share intent is parked when the session is dead and replayed on the confirmation screen after a successful sign-in, on the warm-resume path as well as the existing cold-start path
- [x] #3 /share-confirmation is guarded: a session that dies while the screen is open closes it and lands the user on login rather than leaving a screen whose Save always fails
- [x] #4 The inbox add gesture (startLocalUpload, file and photo intakes) goes through the same guard and cannot open the confirmation screen without a valid session
- [x] #5 The login screen shows the existing sessionError message when the user is redirected there from a share attempt
- [x] #6 npx tsc --noEmit and npm run lint are clean in mobile/
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Cartographier AuthContext, AuthService, ShareIntentContext, les entrées locales et la route /share-confirmation afin d’identifier le contrat de revalidation et de replay existant.
2. Exposer dans AuthContext une revalidation autoritative de la session persistée (getValidToken avec tentative de refresh), qui synchronise l’état d’authentification et le sessionError quand la session est morte.
3. Centraliser dans ShareIntentContext le garde avant navigation : valider la session, parquer sans perte tout intent partagé/local invalide, rediriger vers login, puis rejouer après authentification.
4. Garder /share-confirmation pendant toute sa durée de vie, notamment au focus/retour foreground, afin qu’une session expirée ferme l’écran et conserve l’intent pour replay.
5. Exécuter `npx tsc --noEmit` et `npm run lint` dans mobile/, auditer les six critères et les secrets, consigner la tâche, la passer Done et committer uniquement son périmètre.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée le 2026-08-18.

- `AuthContext` expose désormais `revalidateSession()`, sérialisé entre appelants. Il relit SecureStore via `AuthService.getValidToken()` (qui tente le refresh d’un access token expiré), resynchronise le token mémoire et le timer en cas de succès, ou purge la session et pose `Your session has expired. Please sign in again.` en cas d’échec.
- `ShareIntentContext` possède un pipeline unique avant `/share-confirmation`. Les intents natifs, fichiers, photos de photothèque et photos caméra sont d’abord parqués, revalident la session, puis seulement mappés et navigués. Un échec conserve l’entrée en mémoire et remplace la route par le login ; le passage à `isAuthenticated` après login rejoue l’entrée.
- Le parking est unifié en trois formes (`share`, `local`, `current`) : une confirmation déjà ouverte conserve aussi son contenu, son dossier et ses tags pendant la réauthentification.
- `/share-confirmation` reste non interactif avant validation et revalide au focus ainsi qu’à chaque retour foreground via `AppState`. Une session morte parque l’état courant et remplace immédiatement la route par le login sans appeler `dismiss()`.
- La clé stable d’intent empêche les rerenders de réexécuter le même contrôle/navigation, tout en restant réinitialisée quand l’intent natif disparaît.

Vérifications dans `mobile/` : `npx tsc --noEmit` exit 0 ; `npm run lint` exit 0. Le lint global signale huit warnings préexistants dans cinq fichiers hors périmètre ; un passage ciblé sur les trois fichiers modifiés sort à 0 sans diagnostic. `git diff --check` est propre et aucun secret/credential/email/identifiant de support n’a été ajouté. Aucun test automatisé ajouté ou exécuté, conformément à la règle du dépôt.
<!-- SECTION:NOTES:END -->
