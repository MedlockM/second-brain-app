---
id: task-391
title: >-
  Générer l'aperçu de source sur une sauvegarde dédupliquée et borner l'âge d'un
  pending
status: Done
assignee: []
created_date: '2026-09-10 11:21'
updated_date: '2026-09-10 12:40'
labels:
  - backend
  - media_summarizer
  - bug
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui est observé

Un aperçu de source (« review blurb ») peut rester indéfiniment annoncé comme en cours de rédaction, ou annoncé indisponible alors que le contenu existe ailleurs. Un correctif mobile a déjà été intégré : il rend l'écran honnête (plus de spinner éternel, état terminal atteint, reprise au retour sur l'écran). Il ne fait pas apparaître les aperçus manquants — la cause qui fabrique les lignes incohérentes est en amont, dans `media_summarizer/`.

## Cause établie

Deux défauts indépendants, côté backend :

1. **Sauvegarde dédupliquée sans blurb.** `finalize_deduplicated_save` (`core/services/durable_media_service.py`) et ses deux appelants n'appellent jamais `trigger_review_blurb_generation` ni `copy_review_blurb_to_library_row`. Le scope de l'artefact étant identique entre deux sauvegardes du même contenu par le même utilisateur, l'API voit l'artefact `READY` et répond `status: "ready"`, tandis que la nouvelle ligne `user_media` n'a jamais reçu le blurb — le contrat annonce un contenu qui n'existe pas. Pour un *autre* utilisateur, il n'y a rien dans son scope et le job est terminal : l'aperçu est annoncé indisponible.
2. **Un `pending` sans borne d'âge.** Une entrée bloquée en `queued` (sans `awaiting_expires_at`) ou en `generating` n'est reprise par aucun sweeper et n'expire jamais : elle reste `pending` indéfiniment côté contrat.

## Périmètre

Déclencher la génération et la copie du blurb dans `finalize_deduplicated_save`, pour les deux cas (même utilisateur, autre utilisateur). Borner l'âge d'un `pending` côté API, de sorte qu'une entrée bloquée finisse par répondre un statut terminal au lieu d'un `pending` perpétuel.

Aucun benchmark : correction de bug, la forme est claire, aucun choix de fournisseur ni d'architecture ouvert.

## Notes au propriétaire (hors critères d'acceptation)

Le correctif ne prend effet qu'après déploiement, qui a lieu au push sur `main`, après le passage de l'implémenteur. Vérification manuelle ensuite : enregistrer deux fois la même source depuis le même compte, puis depuis un second compte, et constater que l'aperçu apparaît dans les deux bibliothèques. Origine : retour d'un beta testeur TestFlight sur le build 9.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 finalize_deduplicated_save déclenche la génération de l'aperçu et sa copie sur la nouvelle ligne user_media, pour une re-sauvegarde par le même utilisateur comme pour une sauvegarde par un autre utilisateur ; le chemin de code est câblé depuis les deux appelants existants.
- [x] #2 Une entrée d'aperçu bloquée en queued ou generating au-delà d'une borne d'âge explicite n'est plus rapportée comme pending par l'API : elle aboutit à un statut terminal.
- [x] #3 ruff et mypy passent sans erreur sur les modules touchés.
- [x] #4 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre qu'après une sauvegarde dédupliquée la ligne user_media porte bien le review_blurb.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Défaut 1 — la sauvegarde dédupliquée reçoit son aperçu (AC #1)

`finalize_deduplicated_save` (`media_summarizer/core/services/durable_media_service.py`) provisionne
désormais l'aperçu via le nouveau helper `_provision_review_blurb`, appelé dans la même branche que
l'indexation du transcript (`processing_status == READY` **et** `content_job is not None`) : ce sont
exactement les conditions dans lesquelles le contenu est lisible, et donc les seules où un aperçu peut
être produit. Aucun appelant n'a eu besoin d'être modifié — les deux (`core/services/media_submission.py`
et `core/media_ingestion/adapters/orchestrators.py::_build_duplicate_outcome`) passent par cette fonction,
le câblage vaut donc pour les deux.

Un seul appel couvre les deux cas de l'AC, parce que l'`artifact_id` est un sha256 déterministe qui
n'inclut aucune composante temporelle et dont le `scope_id` de contenu est le `media_key` :

- **même utilisateur, re-sauvegarde** : les deux sauvegardes hachent sur le même `artifact_id`,
  `trigger_review_blurb_generation` retombe sur `REUSED` et `copy_review_blurb_to_library_row` recopie
  l'aperçu déjà rédigé sur la nouvelle ligne. Zéro appel LLM.
- **autre utilisateur** : le `user_id` entre dans le hash, donc rien n'existe dans son scope et une vraie
  génération est mise en file sous son propre scope.

`_provision_review_blurb` avale toute exception (log `review_blurb.trigger_failed` en WARNING) : la partie
stricte de la finalisation est l'écriture du statut, un aperçu non provisionné ne doit pas transformer une
sauvegarde réussie en 500, et `scripts/backfill_review_blurbs.py` rattrape le reste.

**Course résiduelle fermée dans la foulée** : si la seconde sauvegarde atterrit pendant que le premier
aperçu est encore en génération, `REUSED` renvoie un artefact non-`READY`, donc aucune copie n'a lieu, et
la complétion ne miroitait l'aperçu que sur `record.scope_id` — la seconde ligne restait vide alors que
l'entrée partagée annonce `ready`. C'est le symptôme même que vise l'AC #1. `complete_artifact_generation`
appelle maintenant `_mirror_review_blurb_onto_content_rows`, qui étend la cible à toutes les lignes
`user_media` du même `media_key` (`list_for_user_by_media_key`) quand le scope de contenu diffère du
`scope_id` d'origine. Un échec de fan-out est loggué (`artifact.review_blurb_fanout_failed`) sans casser la
complétion.

### Défaut 2 — le `pending` est borné (AC #2)

Nouvelle constante `INTERNAL_GENERATION_STALL_SECONDS` dans `core/services/artifact_service.py`, à 1800 s
par défaut (six baux de génération de 300 s), surchargeable par `ARTIFACT_INTERNAL_STALL_SECONDS`.

`latest_internal_artifact_status` passe désormais par `_bounded_internal_status`, qui balaie à la lecture :

1. Écarte le cas courant sur le `created_at` projeté par le GSI `scope-index` — une entrée jeune n'est
   jamais réexaminée, donc aucun coût supplémentaire sur le chemin chaud.
2. Le GSI ne projetant ni `updated_at` ni `lease_expires_at`, un `GetItem` sur la table de base est
   nécessaire pour *confirmer* le dépassement, et le juge sur `updated_at` + bail encore vivant.
3. Bascule terminale via le nouveau `fail_stalled_artifact` (`utils/media_artifacts.py`) →
   `failed` / `error_code = generation_stalled`, loggué `artifact.generation_stalled`.

`fail_awaiting_artifact` n'était pas réutilisable : sa condition exige `awaiting_expires_at`, qu'une entrée
interne bloquée ne porte jamais (les types internes lèvent `ArtifactTranscriptNotReadyError` au lieu de
créer une entrée en attente). D'où l'écriture conditionnelle dédiée, dont la borne temporelle
(`updated_at < :stale_before`) est **dans la condition DynamoDB** : un worker qui aurait réclamé l'entrée
entre la lecture et l'écriture a bumpé `updated_at`, la condition échoue, et une génération vivante n'est
jamais tuée. Tout chemin d'échec retourne le statut connu précédemment.

Aucun changement de logique côté API : `_ARTIFACT_STATUS_TO_REVIEW_BLURB_STATUS` mappe déjà `FAILED` sur
`CanonicalReviewBlurbStatus.FAILED`. Seule la docstring de `_resolve_review_blurb_status` a été enrichie, et
`docs/CANONICAL_MEDIA_API_CONTRACT.md` documente la borne et le provisionnement sur sauvegarde dédupliquée.

### AC #3 — lint et types

`ruff check media_summarizer/` → *All checks passed!*
`mypy media_summarizer/` → *Success: no issues found in 186 source files*

### AC #4 — vérification directe contre le `-dev` réel

Région forcée à `eu-west-3` (le `AWS_REGION` du shell annonce `us-east-1`, ce qui fait passer une table
présente pour absente). Configuration runtime (noms de tables/buckets/queues uniquement) reprise de la
Lambda API dev.

État initial dans `user_media-dev` : deux sauvegardes du même `media_key` (`mkey_v1_4051e906…`) par le même
compte ; `mi_7cac3a22…` portait un `review_blurb`, sa jumelle `mi_d51f15dc63fc43839f3635a499c326f3` avait
`review_blurb = None`. L'artefact `art_c8f8cd7d108362a10beb0d9d67140b6d` (`review_blurb`, `ready`) existait
déjà pour le scope de contenu.

Exécution du nouveau `finalize_deduplicated_save` sur la ligne sans aperçu, contre le `-dev` réel :

```
BEFORE review_blurb = None
finalize returned    = <job du contenu>
AFTER  review_blurb  = {"hook": "Menu et carte de salades à composer Mister Garden (bases, ingrédients, sauces)", "points": [ … 4 items … ]}
```

Confirmé indépendamment par `aws dynamodb get-item --consistent-read --region eu-west-3` sur
`user_media-dev` → `review_blurb present: True`. Aucun nouvel artefact créé (chemin `REUSED`), donc aucune
dépense LLM.

La borne d'âge a été exercée de la même façon sur `media_artifacts-dev`, avec des lignes jetables sous un
`user_id` synthétique :

```
queued, one minute old           -> API reports queued  | row now queued (None)
queued, two hours old            -> API reports failed  | row now failed (generation_stalled)
generating, two hours old        -> API reports failed  | row now failed (generation_stalled)
```

Lignes de sonde supprimées ensuite ; un scan CLI confirme `probe rows remaining: 0`.

### Hors périmètre, constaté au passage

Le chemin « doublon » de l'orchestrateur (`_build_duplicate_outcome`) n'enregistre aucune entrée
`media_watchers` : une sauvegarde dédupliquée effectuée alors que le contenu est *encore* en cours
d'ingestion récupère bien son statut via `mirror_job`, mais ne redéclenche pas d'aperçu à la complétion du
contenu. La nouvelle borne d'âge garde au moins le contrat honnête dans ce cas (statut terminal au lieu d'un
`pending` perpétuel). Non traité ici pour ne pas empiéter sur task-392, dispatchée en parallèle sur
l'identité de média et la déduplication.

Aucun test automatisé ajouté, conformément à la règle du dépôt (aucun AC n'en demandait).
<!-- SECTION:NOTES:END -->
