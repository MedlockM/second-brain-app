---
id: task-360
title: >-
  Mettre l'artefact en attente de génération au lieu de refuser quand la
  transcription ou la traduction n'est pas terminée
status: To Do
assignee: []
created_date: '2026-09-06 11:04'
labels:
  - artifacts
  - api
  - backend
  - mobile
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observé

Dans l'onglet IA, demander un artefact pendant que la préparation des sources n'est pas finie renvoie un refus. Deux chemins, deux messages, aucun ne produit d'artefact :

- **traduction du transcript en cours** — `resolve_scope_sources` remonte `TranslationInProgressError` en `ArtifactTranscriptNotReadyError`, `POST /api/artifacts` répond `409 sources_not_ready`, et le mobile affiche « La transcription est encore en préparation. Réessayez dans un instant. » (`artifacts.refusal.transcriptPending`).
- **transcription pas encore produite** — la source est exclue en `transcript_unavailable`, le scope devient vide, `enforce_scope_ceilings` lève `ArtifactScopeEmptyError` → `422 scope_empty` → « Cet élément n'a pas encore de transcription : il n'y a rien à générer. »

Dans les deux cas, l'utilisateur doit revenir taper lui-même plus tard. C'est ce qu'on remplace.

## Comportement attendu (décision owner, 2026-09-06)

La demande est **honorée, pas refusée** : l'entrée d'artefact est écrite et présentée comme en cours de génération, exactement comme une génération normale, et elle démarre d'elle-même quand la préparation aboutit.

L'état vit dans le backend, pas dans l'écran : l'entrée est persistée en `queued`, elle apparaît dans l'historique du scope, et l'attente survit à la sortie de l'écran comme à la fermeture de l'app. Un affichage optimiste local a été explicitement écarté — il promet un artefact qui s'évapore dès qu'on quitte l'écran, ce qui est pire que le message d'erreur actuel.

Portée : **les deux onglets IA**, média et collection. Ils partagent déjà `describeArtifactRefusal` et reçoivent le même refus.

## Conséquence assumée sur l'écran média

`app/media/[id].tsx` rend aujourd'hui les tuiles inertes tant que `mediaReady` est faux (`ArtifactTile.sourceReady`, mention « Traitement… ») — c'est-à-dire précisément pendant la transcription. Cette garde n'a plus lieu d'être : elle existait pour ne pas offrir un bouton que l'API refuserait, et l'API ne refuse plus. Sans cela, le cas « transcription pas finie » resterait inatteignable depuis un média isolé.

## Points durs à traiter (le mécanisme reste au choix de l'implémenteur)

- **Une seule entrée, un seul débit.** `build_artifact_id` hache l'ensemble des sources et `parameters`, qui porte `language` — alimenté par la `target_language` *résolue*. Une entrée écrite avant résolution risque de ne pas hacher comme la génération finale : on obtiendrait une entrée en attente orpheline à côté du vrai artefact, et deux passages dans `quota_enforcer.record_generation`. La règle de réutilisation de task-322 (« un artefact couvre exactement ces sources ») doit rester vraie une fois l'artefact produit.
- **Deux points de jonction existent déjà pour la reprise** : la fin d'ingestion (`workers/events/media_completed_worker.py`, qui déclenche déjà le `review_blurb`) et la fin de traduction (`workers/transcript_translation_worker.py`, transition → `done`). Rien ne doit reposer sur une boucle de re-POST du client : task-327 et task-328 ont retiré exactement ce genre de boucle.
- **Attente ≠ échec définitif.** Une traduction refusée pour de bon (`TranslationPermanentlyFailedError`, task-327) et une ingestion en échec ne sont pas des attentes : l'entrée doit finir `failed` avec son code, ce qui retombe sur l'état d'échec actionnable posé par task-328. Aujourd'hui `EXCLUDED_REASON_TRANSCRIPT_UNAVAILABLE` confond « pas encore transcrit » et « ne le sera jamais » ; c'est cette confusion qu'il faut lever.
- **Aucune attente perpétuelle.** Une entrée dont la préparation ne vient jamais doit être bornée et finir `failed`, pas tourner indéfiniment.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Le `409 sources_not_ready` disparaît du contrat de `POST /api/artifacts` : on retire la branche serveur, les clés i18n et la branche cliente, sans repli ni fenêtre de dépréciation. `ArtifactTranscriptNotReadyError` reste en revanche : `review_blurb_service` et `digest_service` s'en servent encore, hors de tout chemin HTTP.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle t'appartient et demande un déploiement plus un build : enregistrer un média en langue étrangère, demander un résumé pendant la transcription puis pendant la traduction, et voir la tuile tourner puis l'artefact arriver sans nouvelle action.
- Si le mécanisme retenu ajoute une ressource AWS, elle sera visible dans ton `terraform plan` avant le push.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `POST /api/artifacts` ne refuse plus une demande dont les sources sont en préparation : la branche qui traduit `ArtifactTranscriptNotReadyError` en `409 sources_not_ready` est retirée de `media_summarizer/api/endpoints/artifacts.py`, et la réponse est une entrée d'artefact en cours (`queued`) qui figure dans l'historique du scope
- [ ] #2 Une source encore en transcription compte comme en préparation et non comme exclue : le chemin qui aboutissait à `scope_empty` pour un média dont l'ingestion est en cours produit lui aussi une entrée en attente, tandis qu'une source dont l'ingestion a échoué reste exclue définitivement
- [ ] #3 La reprise est automatique et branchée sur les points de jonction existants (fin d'ingestion, fin de traduction) : quand la dernière source d'une entrée en attente devient lisible, la génération est enfilée sans action de l'utilisateur, et aucun chemin client ne rejoue le POST
- [ ] #4 Une préparation qui n'aboutira pas fait passer l'entrée en `failed` avec son `error_code` (traduction définitivement refusée, ingestion en échec), et une entrée en attente est bornée dans le temps : aucun `queued` ne peut rester indéfiniment
- [ ] #5 Une demande mise en attente et la génération qui en découle sont une seule et même entrée : un seul `artifact_id`, un seul `quota_enforcer.record_generation`, aucune entrée résiduelle, et la réutilisation par empreinte des sources reste vraie une fois l'artefact produit ; le raisonnement sur l'id est écrit dans les notes d'implémentation
- [ ] #6 Le code du refus supprimé l'est partout : branche `sources_not_ready` de `mobile/src/lib/artifactRefusal.ts` et clés `artifacts.refusal.transcriptPending` / `artifacts.refusal.sourcesPending.*` des 11 catalogues `mobile/src/i18n/`, sans repli conservé — `ArtifactTranscriptNotReadyError` restant en place pour `review_blurb_service` et `digest_service`
- [ ] #7 Les deux onglets IA offrent la génération pendant la préparation et montrent la tuile en cours : la garde `sourceReady` de `app/media/[id].tsx` n'interdit plus la demande pendant la transcription, aucun chemin n'affiche de bandeau de refus pour une préparation en cours, et toute chaîne ajoutée est présente dans les 11 catalogues
- [ ] #8 `ruff` et `mypy` passent sur les modules Python modifiés ; `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
- [ ] #9 Si le mécanisme retenu demande une ressource d'infrastructure, elle est déclarée dans `infrastructure/terraform/` et `terraform validate` sort 0 sur `envs/dev` ; sinon les notes d'implémentation disent pourquoi aucune n'est nécessaire
<!-- AC:END -->
