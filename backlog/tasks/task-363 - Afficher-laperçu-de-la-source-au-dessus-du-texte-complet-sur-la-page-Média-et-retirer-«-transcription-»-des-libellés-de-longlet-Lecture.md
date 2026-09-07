---
id: task-363
title: >-
  Afficher l'aperçu de la source au-dessus du texte complet sur la page Média,
  et retirer « transcription » des libellés de l'onglet Lecture
status: Done
assignee: []
created_date: '2026-09-06 15:04'
updated_date: '2026-09-07 12:00'
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
- [x] #1 `MediaItemContract` porte le contenu de l'aperçu et son statut à trois valeurs (`pending`/`ready`/`failed`), et `_build_media_item_contract` les renseigne : le contenu depuis `record.review_blurb`, le statut depuis l'entrée d'artefact interne la plus récente du scope média
- [x] #2 Le filtre `INTERNAL_ARTIFACT_TYPES` de `list_scope_artifacts` est intact : aucune entrée `review_blurb` n'apparaît dans l'historique servi à l'onglet AI
- [x] #3 Le chemin d'ingestion (`IngestUrlResponse`) ne déclenche aucune lecture d'artefact supplémentaire pour renseigner ce statut
- [x] #4 L'onglet « Lecture » rend la section « Aperçu » au-dessus du texte complet dans ses trois états : le hook et ses puces quand l'aperçu existe, un état d'attente quand il se prépare, une ligne courte sans bouton de régénération quand il a échoué
- [x] #5 Les puces de l'état `ready` sont rendues par `mobile/src/components/Bullets.tsx` ; aucun second style de puce n'est introduit
- [x] #6 L'attente se résout par un poll borné : délai et nombre maximal d'essais nommés par des constantes, poll arrêté au démontage, aucun `setInterval` non borné ajouté
- [x] #7 Le titre de la section du texte de la source dit « Texte complet » en français, et aucune chaîne `transcript.*` lue à l'écran n'emploie plus « transcription » ou son équivalent technique, dans les 11 catalogues de `mobile/src/i18n/`
- [x] #8 Aucune clé i18n n'est renommée ni supprimée et aucun identifiant technique ne bouge (`review_blurb`, `user_media.review_blurb`, préfixe `transcript.`) ; toute clé ajoutée est présente dans les 11 catalogues
- [x] #9 Aucune valeur littérale de couleur, d'espacement ou de typographie n'est introduite : tout vient de `mobile/src/constants/theme.ts`
- [x] #10 `ruff` et `mypy` passent sur les fichiers Python modifiés ; `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Backend : le statut se lit à côté du filtre, pas à travers

`list_scope_artifacts` et `INTERNAL_ARTIFACT_TYPES` n'ont pas été touchés d'une ligne. Le statut vient d'une lecture **séparée**, `latest_internal_artifact_status` (`media_summarizer/core/services/artifact_service.py`), qui interroge le scope média via `media_artifacts.list_artifacts_by_scope` — donc avant tout filtrage — et rend le statut de la première entrée interne rencontrée. La requête est faite **sans `limit`** : un scope média ne porte au plus qu'une entrée par type, alors qu'une lecture paginée pourrait rendre une première page d'artefacts utilisateur en laissant l'entrée interne sur la suivante.

Piège trouvé en route, qui aurait fait répondre `failed` partout : les entrées internes sont indexées sous le **`media_key`**, pas le `media_item_id` (`review_blurb_service.trigger_review_blurb_generation` passe `content_scope_id=record.media_key`). `_resolve_review_blurb_status` lit donc `record.media_key or record.media_item_id`.

Deuxième écart avec la description de la tâche : elle annonçait `completed` → `ready` pour le statut d'artefact, mais `MediaArtifactStatus` n'a pas de valeur `COMPLETED` — son état de succès est `READY`. La table `_ARTIFACT_STATUS_TO_REVIEW_BLURB_STATUS` (`media_summarizer/api/endpoints/media.py`) mappe donc `QUEUED`/`GENERATING` → `pending`, `READY` → `ready`, `FAILED` → `failed`. Absence d'entrée : `failed` si le job est dans un état terminal (`completed`/`failed`/`cancelled`), `pending` sinon.

`MediaItemContract` (`media_summarizer/api/models/media_contracts.py`) porte `review_blurb: Optional[ReviewBlurb]` et `review_blurb_status: ReviewBlurbStatus = PENDING`. Le module importe le `ReviewBlurb` du domaine plutôt que d'en recopier la forme — `MediaSearchItem` sert déjà `user_media.review_blurb` verbatim sur le endpoint liste, et un second modèle à deux champs ici serait libre de dériver de celui que le mirror écrit. C'est le premier import `core` de ce module de contrats ; vérifié qu'il n'introduit pas de cycle.

AC #3 tient par structure, pas par un drapeau : `_build_media_item_contract` reçoit le statut en paramètre par défaut (`PENDING`), et le seul appelant qui le résout est `GET /api/media/{id}`. Le `IngestUrlResponse` local (`media.py:465`) ne construit d'ailleurs aucun contrat — il ne porte que `media_item_id`/`status`/`source_platform`.

### Mobile : une section présentationnelle, un poll dans l'écran

`mobile/src/components/SourcePreview.tsx` est nouveau et purement présentationnel. Il exporte `SourcePreviewState` (une union à trois branches) et `resolveSourcePreviewState`, qui réconcilie les deux champs de contrat : le contenu gagne — un blurb avec un `hook` est un aperçu, quoi que dise l'entrée d'artefact — et seule son absence se lit sur le statut, où seul `failed` clôt la question. Les puces de l'état `ready` passent par `Bullets` ; aucun style de puce n'est défini dans le composant.

L'état et le poll vivent dans `CompletedDetailView` (`mobile/app/media/[id].tsx`), même découpage que `TranscriptReader`. Le poll est nécessaire parce que `useMediaDetailPolling` s'arrête dès que le job est `completed`, or la génération de l'aperçu part *de* cet événement : sans ce poll, rien ne ramènerait jamais l'aperçu sur une page ouverte au bon moment. Chaîne de `setTimeout` qui se replanifie elle-même, bornée par `PREVIEW_POLL_DELAY_MS` (3 s) et `PREVIEW_POLL_MAX_ATTEMPTS` (20, soit une minute), armée depuis l'état d'attente lui-même et coupée par le cleanup de l'effet — que l'aperçu se résolve ou que l'écran disparaisse. Aucun `setInterval`.

`mobile/src/types/media.ts` : `ReviewBlurbStatus` ajouté, `review_blurb`/`review_blurb_status` ajoutés à `MediaItemContract`. Le statut est typé **requis**, pas optionnel : l'API le sérialise toujours (défaut Pydantic `pending`), et le typer optionnel aurait été une couche de compatibilité déguisée. Conséquence : les deux `MediaItemContract` synthétisés dans `ShareIntentContext` après un partage texte/audio portent maintenant `review_blurb_status: "pending"`, ce qui est la vérité — la ligne vient d'être créée.

### i18n : 3 clés ajoutées, 11 catalogues, aucune clé renommée

Nouveau préfixe `preview.` (`preview.heading`, `preview.pending`, `preview.failed`), vérifié inédit, inséré juste avant le bloc `transcript.*` pour garder le diff local. Le préfixe `transcript.` est intact — seules les *valeurs* changent. `transcript.heading` dit « Texte complet » en français, « Full text » en anglais, et son équivalent dans les neuf autres langues ; plus aucune valeur `transcript.*` n'emploie « transcription », « transcript », « Transkript », « trascrizione », « ट्रांसक्रिप्ट », « 文字起こし », « 文字记录 » ou « النص المكتوب ».

`media.transcriptLoadFailed` a suivi la même décision bien que ce ne soit pas une clé `transcript.*` : elle s'affiche sur ce même onglet Lecture. En revanche `media.processing.*` (écran de traitement) et `paywall.subtitle` (le quota mensuel *est* du temps de transcription) sont restés tels quels — hors onglet Lecture.

Le libellé de l'onglet lui-même n'a pas bougé : `media.tab.reader` disait déjà « Lecture ».

### Vérifications

`ruff check` et `mypy` propres sur les trois fichiers Python touchés. `tsc --noEmit` et `eslint src app` propres sur tout le projet mobile (restent deux warnings préexistants, dans `app/(tabs)/digest.tsx` et `src/services/purchaseService.ts`, hors périmètre). `docs/CANONICAL_MEDIA_API_CONTRACT.md` documente le nouveau champ et l'énum.

Conformément aux règles du dépôt, **aucun test automatisé** n'a été ajouté. Les deux notes owner de la description restent d'actualité : la vérification visuelle demande un build, et le champ n'est servi qu'après push sur `main` et redéploiement de l'image Lambda — d'ici là un build lit un champ absent, que `resolveSourcePreviewState` traite comme `pending`.
<!-- SECTION:NOTES:END -->
