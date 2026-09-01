---
id: task-326
title: Make the reading-language onboarding gate unbypassable and race-free
status: Done
assignee: []
created_date: '2026-09-01 16:38'
updated_date: '2026-09-01 17:26'
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
- [x] #1 Aucun fichier de `mobile/app/(auth)/` ni `mobile/src/components/SocialAuthButtons.tsx` ne cible plus `/(tabs)/inbox` : un grep de `(tabs)/inbox` sur ces chemins ne renvoie rien.
- [x] #2 `mobile/app/(tabs)/_layout.tsx` redirige vers `/onboarding/language` quand la langue de lecture n'est pas renseignée, et cette vérification est placée après les gardes `isLoading` et `!isAuthenticated` existants.
- [x] #3 Le garde-fou de `mobile/app/index.tsx` reste en place et cohérent avec celui du layout des onglets — les deux lisent `needsLanguageOnboarding` depuis `UserPreferencesContext`, sans dupliquer la règle.
- [x] #4 `mobile/app/onboarding/language.tsx` continue de renseigner la préférence avant de naviguer, et sa cible de sortie ne peut pas ramener l'utilisateur sur le garde-fou : le chemin de sortie est tracé dans une note du fichier ou du rapport de tâche.
- [x] #5 `npm run typecheck` et `npm run lint` passent dans `mobile/` sans erreur.
- [x] #6 Aucune couche de compatibilité, aucun fallback vers l'ancien ciblage en dur n'est conservé.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Volet 1 — `/` devient le point d'entrée unique

Quatre chemins post-authentification nommaient eux-mêmes leur destination. Ils passent tous par `/` :

- `app/(auth)/login.tsx` — `router.replace("/(tabs)/inbox")` → `router.replace(POST_AUTH_ENTRY_POINT)`.
- `app/(auth)/_layout.tsx` — `<Redirect href="/(tabs)/inbox" />` → `<Redirect href={POST_AUTH_ENTRY_POINT} />`.
- `src/components/SocialAuthButtons.tsx` — les deux `router.replace` (Google et Apple), qui ne traversaient jamais le garde-fou.
- `app/(auth)/register.tsx` — visait déjà `/`, passe au constant.

La course décrite dans la tâche n'est pas arbitrée, elle est **dissoute** : les deux redirections qui se disputaient le stack racine au même `setState` d'`AuthContext` visent maintenant la même route, donc l'ordre du flush React ne change plus le résultat.

Le `Redirect` d'`app/(auth)/_layout.tsx` est conservé plutôt que supprimé, parce qu'il ne décide plus rien — il rend la main à `/`. Il garde son seul vrai rôle : ne pas laisser une session vivante assise sur le formulaire de connexion. Ce cas existe sans qu'aucun écran n'ait navigué (`revalidateSession` au retour au premier plan répare une session expirée alors que l'utilisateur est sur `login`, `isAuthenticated` repasse à `true`, et seule cette branche le sort de là).

## Volet 2 — la décision d'onboarding vit dans le layout des onglets

`app/(tabs)/_layout.tsx` lit `needsLanguageOnboarding` et retourne `<Redirect href={LANGUAGE_ONBOARDING_ROUTE} />`, **après** `isLoading` puis `!isAuthenticated` — l'ordre compte, et le commentaire dans le fichier dit pourquoi : `needsLanguageOnboarding` est dérivé du profil, et un profil encore en restauration se lit exactement comme « pas de langue de lecture », ce qui enverrait un utilisateur de retour sur l'écran d'onboarding à chaque démarrage à froid.

Ce qui rend l'invariant inviolable n'est pas la redirection mais **ce qu'elle remplace** : le garde-fou retourne le `Redirect` *à la place* de `<Tabs>`, donc aucun écran d'onglet n'est monté tant que la langue n'est pas renseignée. Il n'y a plus rien à armer. C'était tout le problème d'`app/index.tsx` : `Redirect` appelle `router.replace` depuis un `useFocusEffect`, donc une route non focalisée conserve une redirection non consommée et la tire plus tard — au premier tap sur l'onglet Compte, dans le rapport de bug.

## Chemin de sortie de l'onboarding (AC #4)

Sortie inchangée : `router.replace("/(tabs)/inbox")`, après `await updateReadingLanguage(selectedLanguage)`. Elle ne peut pas ramener sur le garde-fou, et la raison est écrite dans le fichier : l'`await` ne se résout qu'après que `updateReadingLanguage` a écrit `localReadingLanguage` dans `UserPreferencesContext`, donc `needsLanguageOnboarding` vaut déjà `false` quand le layout des onglets exécute sa vérification à son premier rendu. Pas de boucle, pas de fenêtre.

Sortir vers `/` aurait été plus « uniforme » mais strictement moins bon : la préférence est déjà arbitrée au moment de naviguer, il ne reste rien à décider au point d'entrée, et le détour ajoute une frame de l'état de chargement racine. Un échec de l'API lève à la place de naviguer, ce qui garde l'utilisateur sur l'écran avec une erreur au lieu de le lâcher dans les onglets sans langue.

## `src/constants/routes.ts`

Deux constantes, `POST_AUTH_ENTRY_POINT` et `LANGUAGE_ONBOARDING_ROUTE`, utilisées par les six appelants. Ce n'est pas une couche d'indirection pour le plaisir : le bug était précisément un écran qui restatait une destination de son côté, et un chemin nommé une fois rend la règle relisible là où elle est appliquée. Le reste de l'app continue de naviguer avec des chemins inline, ce qui est très bien — `/media/[id]` n'énonce rien d'autre que sa destination.

La **règle**, elle, n'est pas dupliquée (AC #3) : `needsLanguageOnboarding` reste la seule définition de `!readingLanguage`, dans `UserPreferencesContext`. `index.tsx` et `(tabs)/_layout.tsx` lisent ce booléen, ils ne le recalculent pas.

## Ce qui n'a pas bougé

Six `(tabs)/inbox` subsistent dans l'app, aucun n'est un choix de destination post-authentification : `index.tsx` (c'est lui qui décide), la sortie de l'onboarding, le dismiss de `share-confirmation`, `+native-intent.tsx`, la suppression d'un artefact, la fermeture d'`unsorted-review`. Tous partent d'un utilisateur déjà dans l'app.

Aucun fallback, aucun drapeau, aucun double chemin (AC #6) : les anciennes cibles sont remplacées, pas doublées.

## Vérifications

- `grep -rn "(tabs)/inbox" "app/(auth)" src/components/SocialAuthButtons.tsx` : zéro occurrence (AC #1).
- `npm run typecheck` : clean. `npm run lint` : 0 erreur, 2 warnings préexistants (`digest.tsx` `CARD_WIDTH`, `purchaseService.ts` `any`), aucun sur les fichiers touchés.
- Non vérifiable ici, et laissé à l'owner comme le dit la description : le parcours réel sur device (compte neuf email/mot de passe, puis Google, puis Apple) et le flow `mobile/.maestro/01_login.yaml`. Un simulateur n'était pas à disposition et Maestro est déclenché par l'owner.
<!-- SECTION:NOTES:END -->
