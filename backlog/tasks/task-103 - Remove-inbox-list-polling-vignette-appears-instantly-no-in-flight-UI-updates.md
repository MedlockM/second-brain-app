---
id: task-103
title: >-
  Remove inbox list polling (vignette appears instantly, no in-flight UI
  updates)
status: Done
assignee: []
created_date: '2026-05-20 10:07'
labels:
  - feature
  - mobile
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Décision V1 : la liste inbox n'a plus à refléter l'état d'avancement du traitement d'un media partagé. La vignette apparaît instantanément lors du share (state local + réponse synchrone du POST `/api/media/ingest-url` ou `/upload`), avec un placeholder titre/thumbnail si pas encore résolu. Si l'user clique avant que le traitement soit fini, il tombe sur l'écran détail qui affiche « Generating text… » (cf. tâche dédiée).

À faire côté mobile :

1. `mobile/src/hooks/useMediaPolling.ts` : supprimer le polling 5s. Le hook devient un simple fetch one-shot au mount + une fonction `refresh()` exposée pour pull-to-refresh.
2. `mobile/app/(tabs)/inbox.tsx` : retirer toute logique de rendering basée sur `status` (badges « processing », spinners par item, etc.). Toutes les vignettes ont la même apparence quel que soit le statut.
3. Insertion optimistic au moment du share : ajouter immédiatement un placeholder dans le state inbox (titre = URL ou nom du fichier, thumbnail = favicon du domaine ou icône générique selon `source_platform`) dès le retour du `POST /api/media/ingest-url` (HTTP 202), sans attendre la résolution complète du media. Le titre/thumbnail réels remplacent le placeholder au prochain refresh ou au tap (qui charge `GET /api/media/{id}`).
4. Pull-to-refresh sur l'écran inbox : conservé, fait un fetch unique de la liste.
5. Refresh au focus de l'écran (`useFocusEffect`) : fait un fetch unique pour rattraper les multi-device.

Précautions :
- Ne pas casser l'écran détail : il aura son propre polling local 3s (autre tâche).
- Pas de modification backend nécessaire (la réponse 202 contient déjà `media_item_id` + `status` + `source_platform`).
- Le placeholder est purement côté client — le backend continue de peupler `title` / `media_image` côté worker, ils seront récupérés au prochain `GET`.

Acceptance :
- Aucune requête réseau récurrente n'est émise par l'écran inbox quand il est ouvert.
- Le partage d'une URL fait apparaître la vignette en moins de 100ms (avant la réponse réseau).
- Pull-to-refresh recharge la liste depuis le backend.
- Le retour sur l'inbox depuis un autre écran (focus) déclenche un fetch.
<!-- SECTION:DESCRIPTION:END -->
