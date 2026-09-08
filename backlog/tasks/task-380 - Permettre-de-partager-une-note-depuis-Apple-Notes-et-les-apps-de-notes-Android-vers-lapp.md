---
id: task-380
title: >-
  Permettre de partager une note depuis Apple Notes et les apps de notes Android
  vers l'app
status: To Do
assignee: []
created_date: '2026-09-08 10:03'
labels:
  - mobile
  - ingestion
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui existe déjà

Le tunnel de partage entrant accepte déjà du texte brut sur les deux plateformes, donc une note partagée depuis Apple Notes ou Google Keep atteint probablement déjà l'écran de confirmation. Trois conséquences la rendent inutilisable comme note :

- le média créé est attribué à WhatsApp (`mobile/src/services/sharedContentService.ts`), quelle que soit l'app d'origine ;
- l'écran de confirmation annonce le contenu comme un « Message texte WhatsApp » (`mobile/app/share-confirmation.tsx`, clé `share.whatsappText`) ;
- un export fichier est refusé : les extensions acceptées (`mobile/src/types/upload.ts`, `DocumentFormat` côté backend) couvrent pdf/docx/pptx/xlsx et les images, pas les fichiers texte. Or plusieurs apps de notes Android n'envoient pas de texte brut mais un fichier.

## Ce qui est demandé

Qu'un utilisateur puisse envoyer une note depuis l'app Notes d'iOS et depuis les apps de notes Android (Google Keep, Samsung Notes) vers notre app par la feuille de partage système, et la retrouver dans sa bibliothèque comme une note lisible, correctement nommée et correctement attribuée.

## Décisions produit (tranchées par le propriétaire)

**Source dédiée « Notes ».** Une note partagée n'est pas un message WhatsApp : elle porte sa propre source, distincte, qui apparaît dans la liste des sources servie au paywall. WhatsApp reste la source des notes vocales.

Aucune API publique iOS n'expose l'app hôte à une extension de partage, donc l'origine d'un texte partagé n'est pas identifiable de façon fiable. Par conséquent : un texte partagé dont l'origine n'est pas identifiable par la plateforme est attribué à « Notes ». Conséquence assumée par le propriétaire : sur iOS, un texte partagé depuis une messagerie sera présenté comme une note.

**Les fichiers texte deviennent un format accepté** (`.txt`, `.md`, `.rtf`), au même titre que les documents déjà pris en charge, parce que c'est la forme sous laquelle certaines apps de notes exportent. Aucun nouveau fournisseur : le traitement doit produire un contenu lisible avec les briques existantes.

**Refus lisibles plutôt que dead-ends.** Une note verrouillée ou sans texte n'arrive avec aucun contenu exploitable, et un texte peut dépasser la limite existante : dans les deux cas l'utilisateur doit lire la raison, pas rester devant un écran vide.

## Périmètre

Contenu texte d'une note, reçu soit comme texte partagé soit comme fichier texte, sur iOS et Android. Les images intégrées et les pièces jointes d'une note ne sont pas visées — mais une réception qui en contient ne doit ni échouer silencieusement ni afficher un écran vide.

La consommation facturée pour un fichier texte est à définir : le barème actuel des documents compte des pages, ce qu'un fichier texte n'a pas.

Aucun benchmark : pas de décision de fournisseur ni d'architecture ouverte.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après intégration et build : partager une note depuis l'app Notes d'iOS (note simple, note avec image, note verrouillée), depuis Google Keep, et depuis Samsung Notes en export fichier ; vérifier la présence de l'app dans la feuille de partage, le titre du média obtenu, la source affichée et le message de refus sur une note vide. Le nouveau format de fichier et l'attribution ne prennent effet côté backend qu'après déploiement, qui a lieu au push sur `main`, après le passage de l'implémenteur.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le parcours de partage entrant traite le texte d'une note reçue depuis une app de notes sur iOS et Android, de la réception jusqu'à la soumission, et le média créé porte la source « Notes » et non la source WhatsApp.
- [x] #2 Un texte partagé dont l'origine n'est pas identifiable par la plateforme est attribué à « Notes » ; WhatsApp reste la source des notes vocales et du texte dont l'origine est identifiable.
- [x] #3 Le titre du média créé dérive du contenu de la note — sa première ligne quand elle en tient lieu — et non d'un libellé de plateforme.
- [x] #4 Les fichiers texte .txt, .md et .rtf sont acceptés de bout en bout : l'app est déclarée pour eux dans les feuilles de partage des deux plateformes, la validation locale les accepte avant tout transfert, et ils sont routés vers un traitement qui produit un contenu lisible.
- [x] #5 La liste des sources et des formats servie au paywall annonce « Notes » et les formats texte, et la vérification d'exhaustivité exécutée au démarrage de l'API reste satisfaite après l'ajout de la nouvelle source et des nouveaux formats.
- [x] #6 La consommation facturée pour un fichier texte est définie explicitement, lisible dans la configuration de tarification, et ne repose pas sur un nombre de pages inexistant.
- [x] #7 Un partage sans contenu exploitable (note verrouillée, note sans texte, fichier texte vide) et un texte au-delà de la limite existante produisent un refus explicite dans l'écran de confirmation, avec un message qui nomme la raison.
- [x] #8 Aucun écran ne présente plus un texte partagé comme un message WhatsApp ; les libellés concernés sont mis à jour dans tous les catalogues de traduction, sans clé orpheline restante.
- [x] #9 Une réception contenant plusieurs éléments (note avec pièces jointes) ne se solde ni par un écran vide ni par un échec silencieux : l'élément retenu est celui présenté à l'utilisateur.
- [x] #10 `ruff check media_summarizer/` et `mypy media_summarizer/` passent ; dans `mobile/`, `npx tsc --noEmit` et `npm run lint` passent, aux avertissements préexistants près.
- [x] #11 La matrice de validation manuelle et la checklist de test mobile listent les cas à vérifier sur appareil : partage depuis l'app Notes d'iOS, Google Keep et Samsung Notes, note verrouillée, et export fichier texte.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**AC #1 reste non coché**, et c'est le résultat attendu : il porte sur le média
effectivement créé au bout d'un partage réel sur les deux plateformes. Cela demande
(a) un backend déployé, qui ne l'est qu'au push sur `main`, après la sortie de
l'implémenteur, et (b) un **nouveau build EAS**, parce que la déclaration
`application/rtf` ajoutée aux `androidIntentFilters` est de la config native et que
`runtimeVersion.policy` est `fingerprint` — une mise à jour OTA ne la porterait pas.
Les cas à jouer sont écrits : `docs/testing/manual-e2e-validation-matrix.md` §4.1b
(NO-01…NO-13) et lignes S13–S16, et `mobile/MANUAL_TEST_CHECKLIST.md` §2. Tout le
chemin est câblé et chaque maillon vérifié en lecture : le client envoie
`source_platform: "notes"`, l'enum API l'accepte, `SourcePlatform.NOTES` existe dans
le domaine, et `SHARE_TARGETS` le déclare.

**Attribution.** `expo-share-intent` n'expose l'app hôte sur aucune des deux
plateformes (vérifié dans les types du paquet : `ShareIntent` n'a pas de champ
d'origine). Il n'y a donc aucune branche « origine identifiable » à alimenter
aujourd'hui : tout texte partagé part en `notes`, et `whatsapp` ne reste que sur la
pièce jointe audio (`isWhatsAppAudioFile` conservé exprès).

**Les formats texte n'appellent aucun fournisseur.** Nouveau
`infrastructure/resolvers/plain_text_resolver.py` : décodage multi-encodages, dé-RTF
en une passe sans bibliothèque ajoutée, `page_count=0` assumé comme *valeur*. Le
worker de parsing route `TEXT_FORMATS` vers lui avant LlamaParse.

**Facturation d'un fichier texte : zéro.** `text_file_minutes: 0` dans
`DEFAULT_PRICING_CONFIG["unit_conversion"]`, servi par `GET /api/pricing`, lu par le
paywall (ligne « A note or a text file / Free » construite depuis la valeur servie,
pas codée en dur). `_conversion()` plancher à 1 ne peut pas exprimer 0, d'où un
`minutes_for_text_file()` dédié et un `record_text_file_parse()` qui débite
`minutes=0, documents=1`. Le pré-contrôle d'upload demande `minutes_needed=0` pour
une extension texte.

**Refus et sélection d'élément.** `validateSharedNoteText()` rend `no_text` ou
`too_long` avec le message affiché ; `selectShareIntentFile()` choisit dans l'ordre
audio → fichier routable → premier fichier avec un chemin, et un `intent.type` non
nul mais inexploitable produit un `invalid` explicite. Le seul cas resté silencieux
est `intent.type === null`, qui est la forme d'un intent périmé.

**Aucun test automatisé n'a été écrit** (règle du projet). Les vérifications sont :
`ruff check media_summarizer/` → all checks passed ; `mypy media_summarizer/` →
Success, 182 fichiers ; `npx tsc --noEmit` → clean ; `npm run lint` → 1 warning
préexistant (`src/services/purchaseService.ts:98`), inchangé.
<!-- SECTION:NOTES:END -->
