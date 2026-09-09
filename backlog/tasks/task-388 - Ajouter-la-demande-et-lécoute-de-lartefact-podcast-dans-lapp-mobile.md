---
id: task-388
title: Ajouter la demande et l'écoute de l'artefact podcast dans l'app mobile
status: To Do
assignee: []
created_date: '2026-09-09 16:00'
labels:
  - mobile
  - artifacts
  - feature
dependencies:
  - task-387
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'il faut faire

Rendre le podcast **demandable et écoutable** depuis l'app. Aujourd'hui l'onglet IA propose cinq tuiles et l'écran de détail sait rendre cinq formes de JSON ; il n'existe **aucune lecture audio** dans l'app (`mobile/package.json` ne contient ni `expo-av` ni `expo-audio`).

Cette tâche dépend de task-387, qui livre le type d'artefact et le canal de livraison des octets. **Lire d'abord** `docs/research/task-386-podcast-artifact-generation/README.md` (décision de l'owner) et les Implementation Notes de task-387 : ils fixent l'identifiant du type, les `parameters` demandables, le format audio et **comment on obtient les octets** — ce n'est pas `GET /api/artifacts/{id}/content`, qui inline du JSON parsé.

## Là où ça se pose dans le code

- **La tuile** : `ARTIFACT_TILES` dans `src/components/ArtifactTile.tsx` ; `ArtifactsPanel.tsx` boucle dessus et est le **seul** propriétaire de la mise en page des deux écrans (`app/media/[id].tsx` et `app/media/folders/[id].tsx`). Son en-tête dit explicitement qu'il n'y a « deliberately **no prop per visual difference** » : le sixième type ne doit pas y introduire de branche par écran.
- **Le type wire** : l'union `ArtifactType` de `src/types/media.ts:78`, plus `src/types/artifacts.ts` pour la requête (`GenerateArtifactRequest.parameters` existe déjà).
- **L'écran de détail** : `app/artifacts/[artifactId].tsx` (1723 lignes) documente en tête les cinq formes de `content` et les rend chacune avec son UI. Le podcast est le premier dont la charge utile n'est pas du texte à afficher mais un média à jouer.
- **L'historique** : `ArtifactHistoryRow.tsx` + `src/lib/artifactHistory.ts`. Un podcast est une entrée d'historique comme les autres — append-only, titre écrit par le modèle, nombre de sources sur un dossier.
- **Les refus** : `src/lib/artifactRefusal.ts` et `getFriendlyErrorMessage.ts`. La règle de comptage retenue par task-386 peut produire un refus de quota que l'app doit savoir dire.
- **L'i18n** : **11 locales** dans `src/i18n/` (`en fr es de it pt nl ja zh ar hi`, `ar` en RTL — `RTL_LOCALES` dans `locales.ts`). Toute chaîne nouvelle existe dans les 11.

## La dépendance audio

`expo-audio` est la bibliothèque audio d'Expo (`npx expo install expo-audio`). Deux points relevés dans sa documentation le 2026-09-09, **à revérifier contre la version de la SDK installée** (`expo: ^55` dans `mobile/package.json`, alors que la page de doc consultée référençait la SDK 57) :

- Le config plugin `["expo-audio", { "enableBackgroundPlayback": true }]` ajoute côté iOS le `UIBackgroundMode` `audio`, et côté Android les permissions `FOREGROUND_SERVICE` / `FOREGROUND_SERVICE_MEDIA_PLAYBACK` plus le service `AudioControlsService`. À l'exécution, le mode audio se règle par `setAudioModeAsync` (`shouldPlayInBackground`, `playsInSilentMode`, `interruptionMode: 'doNotMix'`).
- **Sur Android, sans contrôles d'écran verrouillé, la lecture en arrière-plan s'arrête au bout d'environ 3 minutes** (limitation OS documentée). Un épisode dure bien plus : les contrôles ne sont donc pas un ornement, ils sont la condition pour que l'écoute survive à un verrouillage.

L'API exacte (noms des hooks, signature des contrôles d'écran verrouillé) est celle de la version installée, pas celle citée ci-dessus : la vérifier dans la doc de la SDK du projet avant d'écrire le lecteur.

**Une dépendance native implique un nouveau build de dev client** : l'app n'est plus rechargeable en OTA après cette tâche tant qu'un build n'est pas passé. C'est une note à l'owner, pas un AC.

## Ce qui n'est pas prescrit ici

Le **dessin** du lecteur appartient à l'agent mobile et au design system Amber Clarity. Cette tâche impose des comportements (jouer, mettre en pause, se déplacer dans l'épisode, survivre au verrouillage, dire l'état de génération), pas une maquette. Si un mécanisme d'interaction est ajouté, il se justifie par une implémentation de référence — la doc `expo-audio` pour l'audio, les surfaces produit existantes de l'app pour le reste.

## Hors périmètre

- **Le téléchargement hors ligne** d'un épisode et une file de lecture multi-épisodes.
- **La lecture de l'audio source d'un média ingéré** (podcast PodcastIndex, fichier uploadé) : c'est un autre sujet, même si le lecteur écrit ici pourra le servir plus tard.
- **Tout flow Maestro** : les tests E2E sont legacy et ne contraignent pas cette tâche.
- **Toute compatibilité** avec une version installée de l'app : un testeur met à jour à la demande, rien n'est à ponter.

## Notes à l'owner (pas des ACs)

1. **La vérification réelle est visuelle et sonore** : demander un podcast depuis l'app, attendre la génération, l'écouter, verrouiller le téléphone pendant la lecture (surtout sur Android, à cause de la limite des 3 minutes), et se déplacer dans l'épisode.
2. **Un build de dev client est nécessaire** avant de pouvoir tester cette tâche sur appareil, la dépendance audio étant native.
3. **À vérifier sur un épisode long** : la mémoire et la consommation réseau quand l'audio est servi depuis le canal retenu par task-387.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 La décision de l'owner (`docs/research/task-386-podcast-artifact-generation/README.md`) et les Implementation Notes de task-387 sont lues, et les Implementation Notes de cette tâche citent ce qui en a été appliqué : identifiant du type, `parameters` demandables, format audio, canal d'obtention des octets.
- [ ] #2 L'union `ArtifactType` de `src/types/media.ts` porte le nouveau type, et les formes wire de `src/types/artifacts.ts` le traversent sans cast : la demande passe par le `GenerateArtifactRequest` existant, `parameters` inclus.
- [ ] #3 Une sixième tuile existe dans `ARTIFACT_TILES` et s'affiche via la boucle de `ArtifactsPanel.tsx`, sur l'écran média comme sur l'écran dossier, sans qu'aucune prop ni branche par écran ne soit ajoutée à ce composant.
- [ ] #4 Les `parameters` que la décision expose sont choisis par l'utilisateur avant la demande, et deux jeux identiques ne déclenchent pas de seconde génération : l'app rend visible la réutilisation (`generation_outcome: reused`) au lieu de laisser croire qu'un nouvel épisode est en cours.
- [ ] #5 `app/artifacts/[artifactId].tsx` rend une entrée de ce type comme un lecteur audio, et son commentaire d'en-tête — qui énumère les formes de `content` — dit ce que porte cette forme et pourquoi elle n'est pas du texte à afficher.
- [ ] #6 Le lecteur sait jouer, mettre en pause, afficher la position et la durée, et se déplacer dans l'épisode ; les états de chargement, d'erreur réseau et de fin de lecture sont rendus, et un échec de récupération des octets passe par `getFriendlyErrorMessage`.
- [ ] #7 `expo-audio` est ajouté via `npx expo install` (version alignée sur la SDK du projet) et configuré pour la lecture en arrière-plan dans `app.config.ts` ; l'API utilisée est celle de la version installée, vérifiée dans la doc de cette SDK et non recopiée d'une version ultérieure.
- [ ] #8 La lecture survit au verrouillage de l'écran : le mode audio est armé pour l'arrière-plan et des contrôles d'écran verrouillé sont posés avec le titre de l'épisode. Un commentaire dit pourquoi ils sont obligatoires et pas cosmétiques : sans eux, Android coupe l'audio après ~3 minutes.
- [ ] #9 Une entrée de ce type dans l'historique de scope (`ArtifactHistoryRow`) s'ouvre sur le lecteur, affiche son titre écrit par le modèle et, sur un dossier, son nombre de sources — par le même chemin que les cinq autres types.
- [ ] #10 Une entrée encore en génération ou échouée est dite comme telle sans lecteur jouable, et un refus de quota sur ce type produit un message compréhensible via `src/lib/artifactRefusal.ts`.
- [ ] #11 Toute chaîne ajoutée existe dans les 11 catalogues de `src/i18n/`, et le lecteur reste utilisable en RTL (`ar`) : aucune chaîne en dur dans les composants.
- [ ] #12 `npx tsc --noEmit` et le lint du dossier `mobile/` passent.
<!-- AC:END -->
