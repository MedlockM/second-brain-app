---
id: task-104
title: >-
  Add 'Generating text...' placeholder + 3s polling on mobile media detail
  screen
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
Décision V1 : remplacer les notifications email par un polling local court, scopé à l'écran détail d'un media uniquement. Quand l'user ouvre un media dont le traitement n'est pas terminé, il voit un écran « Generating text… » qui se met à jour automatiquement dès que les artifacts sont prêts.

À faire côté mobile :

1. `mobile/app/media/[id].tsx` (ou équivalent — l'écran détail d'un media item) :
   - Au mount, si le media a un statut non-terminal (`pending`, `resolving`, `transcribing`, `ready_for_artifacts`, `processing`, etc. — tout ce qui n'est ni `completed` ni `failed`), afficher un écran « Generating text… » avec un spinner / skeleton.
   - Lancer un polling sur `GET /api/media/{id}` toutes les 3 secondes tant que le statut reste non-terminal ET que l'écran est monté.
   - Dès que `status === 'completed'` : arrêter le polling, charger les artifacts (summary, notes, flashcards, etc.), basculer sur l'UI normale du détail.
   - Dès que `status === 'failed'` : arrêter le polling, afficher un écran d'erreur avec le `error_message` du backend.
   - À l'unmount (user revient en arrière), arrêter le polling immédiatement (cleanup dans le `useEffect`).

2. Implémentation suggérée : un hook `useMediaDetailPolling(mediaId)` qui encapsule l'intervalle, le cleanup, et la transition vers les artifacts.

3. UX :
   - Texte « Generating text… » + spinner. Pas de barre de progression (on n'a pas de % côté backend).
   - Optionnel : variante du texte selon `source_platform` (« Transcribing audio… » pour podcasts/YouTube, « Reading document… » pour PDF, « Extracting article… » pour web). Garder simple en V1 si trop de friction.
   - Si l'user reste plus de 5 minutes sur l'écran sans changement de statut : afficher un message « This is taking longer than usual. Pull down to refresh or come back later. » et arrêter le polling pour ne pas spam le backend.

Précautions :
- Le polling DOIT s'arrêter quand l'écran est unmount (cleanup dans `useEffect` return).
- Le polling DOIT s'arrêter quand le statut devient terminal (completed / failed).
- Ne pas dupliquer les requêtes si l'utilisateur revient et repart rapidement de l'écran (debounce ou cleanup propre).
- Pas de polling au niveau de l'app entière — uniquement sur cet écran.

Acceptance :
- Cliquer sur une vignette d'un media en cours de traitement → écran « Generating text… » + spinner.
- Le passage à `completed` côté backend déclenche l'apparition des artifacts en moins de 3s côté UI.
- Le passage à `failed` affiche l'erreur.
- Quitter l'écran arrête immédiatement les requêtes (vérifier dans les logs réseau ou via un breakpoint).
- Aucune requête après 5 min d'attente.
<!-- SECTION:DESCRIPTION:END -->
