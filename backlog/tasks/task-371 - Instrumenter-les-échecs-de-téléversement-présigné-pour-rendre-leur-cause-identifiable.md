---
id: task-371
title: >-
  Instrumenter les échecs de téléversement présigné pour rendre leur cause
  identifiable
status: To Do
assignee: []
created_date: '2026-09-06 21:45'
labels:
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le fait qui déclenche la tâche

Le 2026-09-06 vers 20:26 UTC, l'import d'un PDF depuis l'app Fichiers a affiché **« Échec de l'enregistrement — Ce fichier n'a pas pu être envoyé. Vérifiez votre connexion et réessayez. »** avec un bouton « Réessayer ». Le second essai a réussi immédiatement.

Les logs `-dev` de l'API montrent la séquence exacte :

```
20:26:09.145  media.upload_url.issued     1re tentative : URL présignée émise
              (aucun /api/media/upload ne suit)
20:26:15.005  media.upload_url.issued     après le tap sur « Réessayer »
20:26:15.678  durable_media.created  202
20:26:16.362  media.upload.created        succès
```

L'API a donc bien signé l'URL du premier coup. L'échec s'est produit **entre l'obtention de l'URL présignée et le `PUT` vers S3** — un appel qui ne traverse pas API Gateway et ne laisse donc aucune trace serveur.

## Pourquoi la cause est introuvable en l'état

`mobile/src/services/presignedUpload.ts` écrase trois causes distinctes dans un message unique :

- `readLocalFile()` (~ligne 50) : `catch` nu autour de `fetch(uri)` / `.blob()` → `upload.transferFailed` ;
- `putToS3()` (~ligne 66) : `catch` nu autour du `fetch` PUT → le même message ;
- `putToS3()` (~ligne 73) : `!response.ok` → encore le même message.

Le commentaire en place assume ce choix (« None of that is actionable: the answer is always send it again »). La conséquence n'était pas voulue : le statut HTTP et le corps XML renvoyé par S3 ne sont conservés nulle part, et on ne sait même pas si le fichier local a pu être lu. Le défaut est reproductible par l'owner et strictement invisible côté serveur.

**Décision owner du 2026-09-06 : on instrumente, on ne répare pas.** Le but de cette tâche est de rendre la cause identifiable au prochain incident, pas de faire disparaître le symptôme.

## Il n'existe aucun canal de télémétrie

Vérifié dans le dépôt : pas de Sentry, pas de logger mobile, pas de route d'ingestion de logs client, et `CreateBugReportPayload` (`mobile/src/services/bugReportService.ts` ~ligne 49) ne porte que `subject`, `description`, `attachment_key`, `source_app_version`, `source_platform` — aucun champ technique.

Un `console.log` ne remonte donc à personne depuis un build TestFlight. **Le diagnostic doit être lisible depuis l'app elle-même**, sous le message d'échec : un bloc de détail technique, secondaire à la phrase principale, que l'utilisateur peut lire, capturer ou recopier dans un rapport de bug.

Créer un canal de télémétrie serait une décision produit à part entière et **n'entre pas dans cette tâche**.

## Ce que le diagnostic doit porter

Au minimum, de quoi distinguer les trois branches et qualifier la troisième :

- quelle étape a échoué : lecture du fichier local, envoi réseau, ou réponse refusée ;
- le statut HTTP quand il existe (un 403 de signature expirée et un 400 de corps tronqué n'appellent pas le même correctif) ;
- le code d'erreur S3 extrait du corps XML quand il existe (`SignatureDoesNotMatch`, `EntityTooLarge`, `RequestTimeout`…) ;
- la taille du blob et le type MIME envoyés, qui permettent de recouper avec ce que l'API a signé.

Attention en lisant le corps : le `Response` du `fetch` ne se consomme qu'une fois, et l'appel `text()` doit lui-même être protégé — un échec de lecture du corps ne doit pas remplacer le diagnostic par une exception.

## Ce qui ne bouge pas

- **Le message principal reste `upload.transferFailed`.** Le détail technique est secondaire, il ne remplace pas la phrase compréhensible.
- **Aucun retry n'est ajouté** et le nombre de tentatives ne change pas. Le bouton « Réessayer » existant reste le seul mécanisme de reprise.
- **Rien ne change côté backend.** L'API signe déjà correctement, elle est hors de cause.
- `bugReportService.uploadAttachment()` a son propre `fetch` avec le même angle mort, mais il est hors périmètre.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de drapeau de configuration pour activer ou désactiver le diagnostic, pas de mode debug conditionnel : le détail est présent dans tous les builds. Un testeur met à jour à la demande et ne détient que le build qu'il a installé.

## Note pour l'owner (pas un AC)

La vérification réelle demande de reproduire l'échec sur un build installé, ce qui n'arrive qu'au push sur `main`. L'échec étant intermittent, il faudra peut-être plusieurs imports avant de le revoir. Le diagnostic obtenu ce jour-là est ce qui permettra d'écrire la tâche de correction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les trois branches d'échec de stageUpload sont distinguées : lecture du fichier local / échec réseau du PUT / réponse HTTP refusée
- [ ] #2 Le diagnostic porte l'étape atteinte ainsi que le statut HTTP et le code d'erreur S3 extrait du corps XML lorsque ceux-ci existent
- [ ] #3 La lecture du corps de la réponse S3 est protégée : son échec dégrade le diagnostic sans lever d'exception ni masquer l'étape atteinte
- [ ] #4 Le message principal affiché reste upload.transferFailed et le détail technique lui est secondaire à l'écran
- [ ] #5 Le diagnostic est lisible depuis l'app sans aucun canal de télémétrie : aucune dépendance de reporting n'est ajoutée
- [ ] #6 Aucun retry ni reprise automatique n'est introduit et le nombre de tentatives du PUT est inchangé
- [ ] #7 Aucun fichier de media_summarizer/ ni d'infrastructure/ n'est modifié par cette tâche
- [ ] #8 Les clés i18n ajoutées sont présentes dans les 11 langues supportées
- [ ] #9 Le typecheck et le lint de mobile/ passent
<!-- AC:END -->
