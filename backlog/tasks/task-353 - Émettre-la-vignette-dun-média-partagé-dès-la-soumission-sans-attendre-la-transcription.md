---
id: task-353
title: >-
  Émettre la vignette d'un média partagé dès la soumission, sans attendre la
  transcription
status: Done
assignee: []
created_date: '2026-09-04 13:37'
labels:
  - backend
  - ingestion
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui est remonté

Un beta testeur TestFlight (Feedback-Id `AMJ0KSQjGg3YQ0EeAOegfk8`, build `1.0.0 (6)`) constate qu'après avoir partagé puis enregistré un média, la tuile reste sur l'icône générique (trombone) dans « Ajouts récents » et n'affiche l'image qu'une fois la transcription terminée. Sa demande : que l'image apparaisse dès que possible.

## Pourquoi c'est une tâche backend

La tuile mobile ne peut rien afficher plus tôt par elle-même : elle lit `image_url` / `media_image` renvoyés par le serveur, et `InboxItem` (`mobile/src/contexts/InboxContext.tsx:12-37`) ne porte aucun URI de fichier local — seulement `url`, `sourcePlatform`, `state`. Les deux voies possibles étaient (a) plomber l'URI local du fichier mis en scène pour l'upload jusqu'à l'item pending côté mobile, ou (b) faire émettre l'image plus tôt par le backend.

**L'owner a tranché la voie (b) : c'est le backend qui émet l'image plus tôt.** Motif : cela bénéficie à tous les clients au lieu de dupliquer un cache d'URI temporaires dans le mobile, et cela évite d'avoir à gérer la durée de vie d'un fichier que iOS peut purger. Ne pas re-poser cette question ni implémenter la voie mobile.

## Le travail

`media_image` existe déjà sur le job (`media_summarizer/core/models/processing_job.py:75`) et transite par `media_submission.py` (`thumbnail_url` / `media_image` / `episode_image`) ; l'orchestrateur d'ingestion le renseigne à `orchestrators.py:398` (`media_image=cover_url`). Le point à établir est **quand** cette valeur devient lisible par le client par rapport au reste du pipeline : aujourd'hui l'image n'est visible qu'en fin de traitement, alors que pour un média partagé depuis le téléphone la source de l'image est disponible dès la soumission.

Établir d'abord le fait, en lisant le code et les items réels sur les tables `-dev`, puis rendre l'image lisible dès que la source en dispose, sans attendre la transcription. La forme exacte (écriture anticipée du champ au moment de la soumission, ou exposition plus tôt dans la réponse de lecture) est à l'appréciation de l'implémenteur une fois le pipeline établi — mais le résultat doit valoir pour un item encore en cours de traitement, pas seulement pour un item terminé.

Rappel de cadrage (`AGENTS.md`, « Nothing is deployed yet ») : rien n'est en production, aucun contrat à préserver. Pas de champ de compatibilité, pas de double écriture, pas de fenêtre de dépréciation — l'ancien chemin est remplacé, pas doublé.

## Note pour l'owner (pas un AC)

La vérification qui compte est visuelle et vous revient : après merge et push de `main`, partager une photo vers l'app, enregistrer, et regarder si la tuile « Ajouts récents » porte l'image avant la fin de la transcription. L'implémenteur ne peut pas la faire depuis son worktree — son code n'est pas déployé pendant qu'il travaille.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le champ portant la vignette est renseigné et lisible pour un média encore en cours de traitement : un item soumis sur les ressources `-dev` porte sa valeur d'image avant que la transcription soit terminée, vérifié par une lecture directe DynamoDB/AWS CLI
- [x] #2 Aucun chemin de lecture ne dépend plus de la fin du traitement pour exposer la vignette ; les points d'appel touchés sont tous mis à jour, aucun ancien chemin conservé en parallèle
- [x] #3 `ruff` et `mypy` passent proprement sur `media_summarizer/`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Le fait établi : c'est l'écriture qui était tardive, pas la lecture

Aucun chemin de lecture ne gardait la vignette derrière la fin du traitement. `GET /api/media`
(`media_search_service._record_to_search_result` puis `resolve_cover_urls`) et
`GET /api/media/{id}` (`_build_media_item_contract`) projettent `user_media.thumbnail_url`
sans condition sur `processing_status`. Ce qui arrivait tard, c'est **l'écriture** du champ.

Mesuré sur les ressources `-dev`, sur une photo réellement partagée par l'owner
(`IMG_9241.PNG`, titre « Photo — 04 Sep 2026 ») :

| horodatage | fait |
|---|---|
| 12:03:42.97 | ligne `user_media-dev` créée par `POST /api/media/upload`, **sans `thumbnail_url`** |
| 12:03:43.02 | job créé ; les octets de la photo sont déjà dans le bucket documents |
| 12:03:46.12 | `mark_extracting` |
| **12:04:08.43** | `completed_at` du job |
| **12:04:09** | `LastModified` de l'objet `covers/mi_9cf9….jpg` (32 Ko) |

L'objet vignette naissait donc à la seconde du `mark_completed()` : `_capture_cover` était appelé
dans le même `update_processing_job` que la complétion, alors que la source de l'image était
disponible dès la seconde 0. 26 s de trombone pour une image déjà sur S3.

Deux sources écrivaient leur vignette à l'update terminal alors qu'elles la connaissaient plus tôt :

1. **Upload document/photo** — une photo *est* sa vignette, et elle est dans le bucket dès la
   soumission.
2. **YouTube** — `youtube_thumbnail_url(video_id)` est déterministe depuis l'URL, mais n'était
   écrit qu'au `mark_completed` de la branche Apify. La branche de repli audio n'en écrivait
   **aucune** : deux lignes YouTube de `-dev` (18 et 19 août) ont un `thumbnail_url` vide.

Les autres sources n'ont pas de point plus tôt et n'ont pas été touchées : Instagram écrit sa
vignette avec `mark_transcribing`, TikTok juste avant, le podcast à la résolution — déjà conformes.
Article et X tirent leur image du même appel réseau que leur texte, donc leur écriture terminale
*est* le plus tôt possible. L'audio (upload et partage) n'a aucune source d'image.

### La forme retenue

Persister la vignette au premier instant où la source la connaît, sans nouveau champ ni double
écriture — `job.media_image` → `mirror_job` → `user_media.thumbnail_url` reste le seul porteur.

- **Photo uploadée** : `_capture_photo_cover` tourne désormais **avant le parse**, sur le fichier
  que le worker vient de télécharger, et son résultat est persisté par un `update_processing_job`
  intermédiaire — donc la ligne de bibliothèque porte l'image pendant que son statut est encore
  `processing`. `_capture_cover` (qui mélangeait photo et rendu de page) est supprimé et scindé en
  `_capture_photo_cover` / `_capture_page_cover` : aucun ancien chemin conservé en parallèle, et la
  photo n'est plus capturée une seconde fois à la complétion.
- **Document paginé / tableur** : `_capture_page_cover` reste sur le chemin de complétion, parce que
  le rendu de la page 1 est un *produit du parse* — il n'existe pas plus tôt.
- **YouTube** : `YouTubeResolver` renseigne `cover_url`, donc l'orchestrateur écrit
  `thumbnail_url` dès la soumission, sans appel réseau. Le repli
  `or youtube_thumbnail_url(video_id)` de la branche Apify est supprimé : il ne réécrivait que la
  valeur déjà présente. Seule la vignette propre à l'acteur, quand il en renvoie une, met la valeur
  à niveau.
- **Un seul parseur d'id YouTube** : `media_metadata.youtube_video_id` (pur, `None` au lieu de
  lever). `_extract_video_id` du worker lui délègue et n'est plus qu'une conversion en
  `YouTubeIngestionError` — le doublon de parsing a disparu.
- **`cover_capture.capture_from_s3` → `capture_from_file`** : l'appelant unique a le fichier sur
  disque, donc plus de second transfert S3 de jusqu'à 50 Mo entre la sauvegarde de l'utilisateur et
  l'apparition de sa vignette. Pillow décode depuis le chemin, ce qui supprime au passage la lecture
  non bornée en mémoire signalée par `docs/research/task-343-document-page-render/README.md` §5.2.

### Vérifications

**AC #1** — la séquence nouvelle a été rejouée telle quelle contre les ressources `-dev` réelles
(pas de déploiement, pas de test automatisé) : ligne `user_media-dev` créée sans vignette, job créé,
`mark_extracting`, `capture_from_file` sur une image, `job.media_image = <locator>`,
`update_processing_job`. Lecture directe ensuite :

- `aws dynamodb get-item --table-name user_media-dev` → `processing_status = "processing"` **et**
  `thumbnail_url = "s3://media-summarizer-covers-125313707865-dev/covers/mi_….jpg"`
- `aws dynamodb get-item --table-name processing_jobs-dev` → `media_image` renseigné, **aucun**
  `completed_at`, **aucun** `transcription_s3_key` : l'item est bien en cours de traitement
- `aws s3api head-object` sur le bucket covers `-dev` → 5088 octets, `image/jpeg`
- l'URL signée que `resolve_cover_urls` produit pour cette ligne répond **HTTP 200 image/jpeg** :
  le client peut réellement afficher l'image à ce moment-là

Les trois artefacts jetables (ligne `user_media-dev`, job `processing_jobs-dev`, objet cover) ont
été supprimés après la vérification ; `get-item` et `head-object` confirment leur absence. Aucune
fixture de l'owner n'a été modifiée.

Côté YouTube, les quatre formes d'URL présentes sur `-dev` (`/watch?v=`, `youtu.be/`, `/shorts/`,
`m.youtube.com` avec `&t=`) donnent un id et une vignette `i.ytimg.com` qui répond **HTTP 200** ;
une URL de playlist donne `None` et laisse l'item sans vignette, comme avant.

**AC #2** — les chemins de lecture n'ont pas eu à changer : ils ne dépendaient pas de la complétion
(voir « le fait établi »). Les points d'appel d'écriture touchés sont tous mis à jour et aucun
ancien n'est conservé : `_capture_cover` supprimé, `capture_from_s3` supprimé, repli
`youtube_thumbnail_url` de la branche Apify supprimé, parseur d'id YouTube dédoublonné.

**AC #3** — `ruff check media_summarizer/` : *All checks passed*. `mypy media_summarizer/` :
*Success: no issues found in 180 source files*.

### Hors de portée / pour l'owner

La vérification visuelle (la tuile « Ajouts récents » porte l'image avant la fin de la
transcription) reste celle de la note de la description : elle demande l'image Lambda reconstruite
et déployée, ce qui se déclenche au push sur `main`, bien après cette session. Aucun test automatisé
n'a été ajouté, conformément aux règles de livraison.

Constat annexe, non corrigé parce que hors périmètre : `InboxContext.addItem`
(`mobile/src/contexts/InboxContext.tsx`) n'est appelé par aucun composant, donc la liste `items` est
toujours vide et les tuiles `kind: "pending"` de `buildRecentlyAdded` (`mobile/app/(tabs)/inbox.tsx`)
ne s'affichent jamais. C'est bien la tuile serveur que le testeur voyait, ce qui confirme que la
voie (b) tranchée par l'owner était la bonne — mais le code mort côté mobile subsiste.
<!-- SECTION:NOTES:END -->
