---
id: task-326
title: Make the reading-language onboarding gate unbypassable and race-free
status: To Do
assignee: []
created_date: '2026-09-01 16:38'
labels:
  - bug
  - mobile
  - auth
  - ui
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problème

Un compte fraîchement créé par email + mot de passe entre dans l'app sans passer par l'écran « Choisissez votre langue de lecture ». L'utilisateur navigue librement dans les onglets, puis l'écran plein écran surgit sans qu'il l'ait demandé — constaté au premier tap sur l'onglet Compte. L'onboarding n'est donc pas sauté, il est **latent** : il se déclenche à un moment arbitraire et hostile.

## Cause

`/onboarding/language` n'a qu'un seul point d'entrée dans toute l'app : `app/index.tsx:38`, via `<Redirect>`. Or `Redirect` d'expo-router (`node_modules/expo-router/build/link/Redirect.js`) appelle `router.replace` depuis un `useFocusEffect`, jamais au montage : la redirection ne part que si la route est focalisée, sinon elle reste armée.

Deux redirections se disputent le stack racine à l'instant de l'inscription, toutes deux déclenchées par le même `setState` d'`AuthContext` :

- `app/(auth)/register.tsx:49` — `router.replace("/")`, qui vise le garde-fou.
- `app/(auth)/_layout.tsx:14` — `<Redirect href="/(tabs)/inbox" />`, dès que `isAuthenticated` passe à `true`.

L'ordre dépend du flush React et de l'animation de transition. Quand la seconde gagne, `index` reste monté sous les onglets avec sa redirection non consommée, qui repart plus tard.

Le même ciblage en dur de `/(tabs)/inbox` existe aussi dans `app/(auth)/login.tsx:49` et `src/components/SocialAuthButtons.tsx:135` et `:173` (Google et Apple) — ces chemins ne traversent jamais le garde-fou du tout.

Le backend est hors de cause : `POST /api/auth/register` renvoie bien `reading_language: null` (`media_summarizer/api/endpoints/auth.py:106`), le garde-fou disposait de la bonne information.

## Direction attendue

Deux volets complémentaires — le premier supprime la course, le second rend l'invariant inviolable. Le second seul corrigerait le symptôme mais laisserait des flashs d'écran et de la flakiness ; le premier seul laisserait le garde-fou dépendre d'un timing.

1. Faire de `/` le point d'entrée unique de tout chemin post-authentification. Aucun écran d'auth, aucun layout d'auth ne décide où va un utilisateur authentifié.
2. Porter la décision d'onboarding dans le layout des onglets, à côté du garde-fou d'authentification qui y vit déjà (`app/(tabs)/_layout.tsx`) — le seul point de passage obligé de tous les onglets. Placer la vérification après les gardes `isLoading` et `!isAuthenticated` existants, pour ne pas rediriger sur un profil encore en cours de chargement.

Attention à ne pas créer de boucle : `updateReadingLanguage` renseigne `localReadingLanguage` dans `UserPreferencesContext` avant que `app/onboarding/language.tsx` ne navigue, donc le garde-fou est satisfait au moment où l'écran d'onboarding rend la main.

## Notes pour l'owner

- Vérification manuelle qui compte, après merge et rebuild : créer un compte neuf par email + mot de passe et vérifier que l'écran de langue s'affiche immédiatement, avant tout onglet ; puis se balader dans les quatre onglets et vérifier qu'il ne resurgit jamais. Répéter avec Google et avec Apple.
- `mobile/.maestro/01_login.yaml` attend déjà `language-onboarding-screen` juste après l'inscription : ce flow devrait cesser d'être intermittent. Non vérifiable par l'implémenteur.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Aucun fichier de `mobile/app/(auth)/` ni `mobile/src/components/SocialAuthButtons.tsx` ne cible plus `/(tabs)/inbox` : un grep de `(tabs)/inbox` sur ces chemins ne renvoie rien.
- [ ] #2 `mobile/app/(tabs)/_layout.tsx` redirige vers `/onboarding/language` quand la langue de lecture n'est pas renseignée, et cette vérification est placée après les gardes `isLoading` et `!isAuthenticated` existants.
- [ ] #3 Le garde-fou de `mobile/app/index.tsx` reste en place et cohérent avec celui du layout des onglets — les deux lisent `needsLanguageOnboarding` depuis `UserPreferencesContext`, sans dupliquer la règle.
- [ ] #4 `mobile/app/onboarding/language.tsx` continue de renseigner la préférence avant de naviguer, et sa cible de sortie ne peut pas ramener l'utilisateur sur le garde-fou : le chemin de sortie est tracé dans une note du fichier ou du rapport de tâche.
- [ ] #5 `npm run typecheck` et `npm run lint` passent dans `mobile/` sans erreur.
- [ ] #6 Aucune couche de compatibilité, aucun fallback vers l'ancien ciblage en dur n'est conservé.
<!-- AC:END -->
