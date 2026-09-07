---
id: task-363
title: >-
  Afficher l'aperçu de la source au-dessus du texte complet sur la page Média,
  et retirer « transcription » des libellés de l'onglet Lecture
status: To Do
assignee: []
created_date: '2026-09-06 15:04'
labels:
  - mobile
  - backend
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'on ajoute

Sur la page Média (`mobile/app/media/[id].tsx`), onglet « Lecture » : une section « Aperçu » au-dessus du texte de la source. Elle rend le `hook` et les `points` du `review_blurb` généré à l'ingestion (task-323) et mirroré sur la ligne `user_media` (`media_summarizer/core/models/user_media.py:127`). Aujourd'hui la seule surface qui le lit est l'écran de tri (`mobile/app/media/unsorted-review.tsx`) : l'aperçu disparaît dès qu'un média est trié, alors qu'il répond exactement à la question qu'on se pose en rouvrant une source.

## Vocabulaire (décisions owner du 2026-09-06)

- La nouvelle section s'intitule **« Aperçu »** en français.
- **« Transcription » quitte les libellés visibles de l'onglet Lecture**, trop techniques. Le titre de la section devient **« Texte complet »**, et les états qui l'entourent parlent du texte de la source, pas d'une transcription.
- **Aucun identifiant n'est renommé.** Le type d'artefact reste `review_blurb`, le champ `user_media.review_blurb` reste, les clés i18n restent préfixées `transcript.`. Seules les *valeurs* des catalogues changent. Quand un libellé doit nommer la chose, il dit « l'aperçu » ou « l'essentiel » ; « review blurb » n'apparaît jamais à l'écran.

Le périmètre du renommage est confiné : toutes les clés `transcript.*` ne sont lues que par `mobile/src/components/TranscriptReader.tsx`, lui-même rendu par la seule page Média. Rien d'autre ne bouge.

## L'état d'attente est demandé explicitement

L'owner veut que la section soit **toujours présente** : quand l'aperçu n'est pas encore là, la page dit qu'il se prépare, plutôt que de disparaître sans rien dire.

Ce n'est pas gratuit. `_trigger_review_blurb` (`media_summarizer/workers/events/media_completed_worker.py`) déclenche la génération *après* la complétion, en best-effort : la fonction avale toute erreur, et `media_summarizer/scripts/backfill_review_blurbs.py` est le rattrapage. Un `review_blurb` nul sur la ligne `user_media` ne dit donc pas si l'aperçu est en route ou s'il n'arrivera jamais — il faut le **statut réel**.

Et ce statut n'est pas accessible aujourd'hui : `list_scope_artifacts` filtre `INTERNAL_ARTIFACT_TYPES` (`media_summarizer/core/services/artifact_service.py:116` et `:718`), donc le `GET /api/artifacts?scope=media` que la page appelle déjà ne verra jamais l'entrée. **Ne pas dé-filtrer** : le commentaire sur place dit pourquoi — une ligne littéralement étiquetée « review_blurb » à côté des cinq vraies dans l'onglet AI.

## Ce que ça implique

**Backend.** `MediaItemContract` (`media_summarizer/api/models/media_contracts.py:173`) porte le contenu et son statut :

- le contenu vient de `record.review_blurb` — `_build_media_item_contract` (`media_summarizer/api/endpoints/media.py:912`) projette déjà `UserMediaRecord`, qui le porte ;
- le statut à trois valeurs (`pending` / `ready` / `failed`) se lit sur l'entrée d'artefact interne la plus récente du scope média (`media_artifacts.list_artifacts_by_scope` rend tout le scope, avant le filtre) : `queued`/`generating` → `pending`, `completed` → `ready`, `failed` → `failed`. Aucune entrée alors que le média est terminé → `failed` : le déclenchement best-effort a été perdu, et c'est exactement ce que le backfill répare. Aucune entrée et média pas encore terminé → `pending` ;
- la lecture supplémentaire ne doit pas peser sur le chemin d'ingestion : `IngestUrlResponse` construit le même contrat alors que le statut y vaut trivialement `pending`.

**Mobile.** La section se place au-dessus de `TranscriptReader`, dans la branche `activeTab === "reader"`.

- `ready` → le hook puis les puces via `Bullets` (`mobile/src/components/Bullets.tsx`), le composant que l'écran de tri utilise déjà. Pas de deuxième style de puce.
- `pending` → un état d'attente lisible, qui ne bloque pas la lecture du texte en dessous.
- `failed` → une ligne courte et calme. Pas de bouton « réessayer » : la génération est interne et `POST /api/artifacts` refuse ce type.
- Le `pending` se résout tout seul : poll borné, sur le modèle déjà présent dans l'écran (`TRANSLATION_POLL_DELAY_MS` / `TRANSLATION_POLL_MAX_ATTEMPTS`, `mobile/app/media/[id].tsx:76-80`), arrêté au démontage comme les deux autres polls. Pas de `setInterval` non borné.
- Côté types, `ReviewBlurb` existe déjà (`mobile/src/types/media.ts:201`) ; c'est `MediaItemContract` qui suit le contrat backend.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de branche « média ingéré avant task-323 » à ménager : les rangées dev sans aperçu se rattrapent avec `backfill_review_blurbs.py`, et `failed` est leur état normal, pas un cas legacy à masquer. Le flow `mobile/.maestro/04_media_detail_progression.yaml` assert encore le texte « Transcript » : les flows Maestro ne contraignent ni le code ni cette tâche, ce n'est pas une raison de garder le libellé, et il n'est pas à mettre à jour ici.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle demande un build : l'agent ne peut pas la faire depuis son worktree.
- Le nouveau champ de contrat n'est servi qu'une fois `main` poussé et l'image Lambda redéployée. D'ici là, un build installé lira un champ absent — c'est l'état d'attente que la page montrera.
- Pour voir `pending` en vrai, il faut ouvrir la page dans les secondes qui suivent une ingestion ; les anciennes rangées dev sans aperçu montrent `failed`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `MediaItemContract` porte le contenu de l'aperçu et son statut à trois valeurs (`pending`/`ready`/`failed`), et `_build_media_item_contract` les renseigne : le contenu depuis `record.review_blurb`, le statut depuis l'entrée d'artefact interne la plus récente du scope média
- [ ] #2 Le filtre `INTERNAL_ARTIFACT_TYPES` de `list_scope_artifacts` est intact : aucune entrée `review_blurb` n'apparaît dans l'historique servi à l'onglet AI
- [ ] #3 Le chemin d'ingestion (`IngestUrlResponse`) ne déclenche aucune lecture d'artefact supplémentaire pour renseigner ce statut
- [ ] #4 L'onglet « Lecture » rend la section « Aperçu » au-dessus du texte complet dans ses trois états : le hook et ses puces quand l'aperçu existe, un état d'attente quand il se prépare, une ligne courte sans bouton de régénération quand il a échoué
- [ ] #5 Les puces de l'état `ready` sont rendues par `mobile/src/components/Bullets.tsx` ; aucun second style de puce n'est introduit
- [ ] #6 L'attente se résout par un poll borné : délai et nombre maximal d'essais nommés par des constantes, poll arrêté au démontage, aucun `setInterval` non borné ajouté
- [ ] #7 Le titre de la section du texte de la source dit « Texte complet » en français, et aucune chaîne `transcript.*` lue à l'écran n'emploie plus « transcription » ou son équivalent technique, dans les 11 catalogues de `mobile/src/i18n/`
- [ ] #8 Aucune clé i18n n'est renommée ni supprimée et aucun identifiant technique ne bouge (`review_blurb`, `user_media.review_blurb`, préfixe `transcript.`) ; toute clé ajoutée est présente dans les 11 catalogues
- [ ] #9 Aucune valeur littérale de couleur, d'espacement ou de typographie n'est introduite : tout vient de `mobile/src/constants/theme.ts`
- [ ] #10 `ruff` et `mypy` passent sur les fichiers Python modifiés ; `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
