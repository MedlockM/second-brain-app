---
id: task-379
title: Ajouter un média par saisie de son URL depuis le menu « + » de l'Accueil
status: To Do
assignee: []
created_date: '2026-09-08 09:58'
labels:
  - mobile
  - ux
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'Accueil (`mobile/app/(tabs)/inbox.tsx`, bouton `inbox-add-button`) ouvre `AddSourceSheet` (`mobile/src/components/AddSourceSheet.tsx`), qui ne propose aujourd'hui que deux entrées : importer un fichier et importer une photo. Un troisième bouton, hors du menu, prend une photo. Autrement dit : depuis l'app elle-même, on ne peut ajouter que du local. Ajouter un média par son URL n'est possible que par le partage système depuis une app tierce.

## Demande

Ajouter dans ce menu « + » une entrée qui permet à l'utilisateur de saisir ou coller l'URL du média qu'il veut ajouter. Dès que l'URL est ajoutée, le traitement du média qui se trouve à cette URL démarre — sans attendre une confirmation supplémentaire, exactement comme le partage système depuis task-378.

## Périmètre

- **Entrée dans le menu** : une ligne de plus dans `AddSourceSheet`, alignée sur les deux existantes (icône, libellé, description, chevron), avec sa copie dans les 11 catalogues i18n de `mobile/src/i18n/` (en, fr, es, de, it, pt, nl, ja, zh, ar, hi).
- **Surface de saisie** : une surface produit de l'app, pas un dialogue système — `Alert.prompt` est iOS-only et n'existe pas sur Android. Champ mono-ligne, clavier de type URL, sans autocapitalisation ni autocorrection, collage par le clavier système. Pas de nouveau module natif : un bouton « Coller » explicite demanderait `expo-clipboard` et donc un nouveau build natif, ce qui est hors périmètre.
- **Validation** : réutiliser `mobile/src/lib/urlValidation.ts` — schémas http/https, hôte avec point, extraction d'une URL entourée de texte, domaine nu complété en `https://`. Une saisie sans URL exploitable est refusée sur place, avec un message, et ne crée aucune sauvegarde.
- **Ingestion** : réutiliser le chemin URL existant (`ShareIntentContext` → `MediaService.ingestUrl` → `POST /api/media/ingest-url`). Aucun nouvel endpoint, aucun contrat backend touché, aucune nouvelle plateforme à reconnaître. Le `source_app` envoyé doit distinguer cette entrée du partage système (`ios-share-extension` / `android-share-intent`), pour que l'origine reste lisible côté données.
- **Déclenchement et confirmation** : le traitement part dès que l'URL est validée. L'écran de confirmation existant (`mobile/app/share-confirmation.tsx`) reste la surface où l'utilisateur choisit le dossier pendant que le traitement avance. Reprendre la sémantique déjà tranchée par task-378 pour un média dont le traitement est lancé avant confirmation : « Enregistrer » confirme la conservation sans relancer l'ingestion ni créer une seconde sauvegarde ; la croix supprime la sauvegarde créée par cette saisie, que le traitement soit en cours ou terminé, via la suppression canonique, et un échec de suppression est visible et réessayable plutôt que présenté comme une annulation réussie.
- **Gardes conservées** : session et authentification (une saisie en attente de connexion reprend après), quota et minutes, déduplication (une URL déjà ingérée revient en succès avec la formulation « déjà dans votre boîte »), erreurs réseau et rate limit.

## Hors périmètre

Le partage système entrant, les imports fichier/photo/caméra, tout changement backend, l'ajout de plateformes sources.

## Note au propriétaire (pas une condition de clôture)

À valider sur un build après intégration : depuis l'Accueil, coller une URL d'article puis une URL YouTube, sur iOS et Android ; constater que le traitement a démarré avant tout appui sur « Enregistrer », puis vérifier la croix pendant le traitement et après sa fin, et la conservation par « Enregistrer ».
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le menu « + » de l'Accueil propose une entrée de saisie d'URL, alignée sur les deux entrées d'import existantes ; sa copie existe dans les 11 catalogues i18n de mobile/src/i18n/.
- [ ] #2 La saisie se fait sur une surface de l'app, sans dialogue système iOS-only, avec un champ à clavier URL, sans autocapitalisation ni autocorrection, et collage par le clavier ; aucun nouveau module natif n'est ajouté à mobile/package.json.
- [ ] #3 La validation passe par mobile/src/lib/urlValidation.ts ; une saisie sans URL exploitable est refusée sur place avec un message et ne crée aucune sauvegarde ni n'ouvre l'écran de confirmation.
- [ ] #4 Une URL validée déclenche l'ingestion par le chemin existant (MediaService.ingestUrl) sans attendre « Enregistrer », et ouvre l'écran de confirmation où le dossier reste choisissable pendant que le traitement avance.
- [ ] #5 Le source_app envoyé par cette entrée est distinct de celui du partage système ; aucun endpoint, contrat backend ou modèle de requête n'est modifié.
- [ ] #6 « Enregistrer » confirme la conservation sans seconde sauvegarde ni relance du traitement ; la croix supprime la sauvegarde créée par cette saisie, en cours de traitement comme terminée, selon la suppression canonique existante, et un échec de suppression est affiché avec une possibilité de réessayer.
- [ ] #7 Les gardes existantes restent câblées en amont de la soumission : authentification avec reprise après connexion, quota et minutes, déduplication annoncée comme succès, erreurs réseau et rate limit.
- [ ] #8 Une même saisie ne peut pas être soumise deux fois (cycle de vie de l'écran, retour d'authentification), tandis qu'une nouvelle saisie volontaire repart.
- [ ] #9 npm run lint et npm run typecheck passent dans mobile/.
- [ ] #10 mobile/MANUAL_TEST_CHECKLIST.md et docs/testing/manual-e2e-validation-matrix.md couvrent le nouveau parcours : nouveaux cas SI-xx décrits, total de la catégorie Share Intake et grand total du Results Summary mis à jour en conséquence.
<!-- AC:END -->
