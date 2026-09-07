---
id: task-360
title: >-
  Mettre l'artefact en attente de génération au lieu de refuser quand la
  transcription ou la traduction n'est pas terminée
status: Done
assignee: []
created_date: '2026-09-06 11:04'
updated_date: '2026-09-07 00:00'
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
- [x] #1 `POST /api/artifacts` ne refuse plus une demande dont les sources sont en préparation : la branche qui traduit `ArtifactTranscriptNotReadyError` en `409 sources_not_ready` est retirée de `media_summarizer/api/endpoints/artifacts.py`, et la réponse est une entrée d'artefact en cours (`queued`) qui figure dans l'historique du scope
- [x] #2 Une source encore en transcription compte comme en préparation et non comme exclue : le chemin qui aboutissait à `scope_empty` pour un média dont l'ingestion est en cours produit lui aussi une entrée en attente, tandis qu'une source dont l'ingestion a échoué reste exclue définitivement
- [x] #3 La reprise est automatique et branchée sur les points de jonction existants (fin d'ingestion, fin de traduction) : quand la dernière source d'une entrée en attente devient lisible, la génération est enfilée sans action de l'utilisateur, et aucun chemin client ne rejoue le POST
- [x] #4 Une préparation qui n'aboutira pas fait passer l'entrée en `failed` avec son `error_code` (traduction définitivement refusée, ingestion en échec), et une entrée en attente est bornée dans le temps : aucun `queued` ne peut rester indéfiniment
- [x] #5 Une demande mise en attente et la génération qui en découle sont une seule et même entrée : un seul `artifact_id`, un seul `quota_enforcer.record_generation`, aucune entrée résiduelle, et la réutilisation par empreinte des sources reste vraie une fois l'artefact produit ; le raisonnement sur l'id est écrit dans les notes d'implémentation
- [x] #6 Le code du refus supprimé l'est partout : branche `sources_not_ready` de `mobile/src/lib/artifactRefusal.ts` et clés `artifacts.refusal.transcriptPending` / `artifacts.refusal.sourcesPending.*` des 11 catalogues `mobile/src/i18n/`, sans repli conservé — `ArtifactTranscriptNotReadyError` restant en place pour `review_blurb_service` et `digest_service`
- [x] #7 Les deux onglets IA offrent la génération pendant la préparation et montrent la tuile en cours : la garde `sourceReady` de `app/media/[id].tsx` n'interdit plus la demande pendant la transcription, aucun chemin n'affiche de bandeau de refus pour une préparation en cours, et toute chaîne ajoutée est présente dans les 11 catalogues
- [x] #8 `ruff` et `mypy` passent sur les modules Python modifiés ; `npx tsc --noEmit` et ESLint passent sur les fichiers mobile modifiés
- [x] #9 Si le mécanisme retenu demande une ressource d'infrastructure, elle est déclarée dans `infrastructure/terraform/` et `terraform validate` sort 0 sur `envs/dev` ; sinon les notes d'implémentation disent pourquoi aucune n'est nécessaire
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The shape: a third state for a source, and one attribute on the entry

`resolve_scope_sources` used to sort each source into two buckets and abort the
whole request on a third case it could not represent. It now returns three:

- **read** — `ResolvedSource`, its effective transcript measured;
- **pending** — `PendingSource` (new), the text is coming;
- **excluded** — `ArtifactSource(excluded=True)`, the text will never come.

`ScopeResolution.pending` / `.is_awaiting` / `.expected_source_ids` carry it, and
`ArtifactSource.preparation` (`"transcription"` | `"translation"`) is the snapshot
line of a pending source — the third state of a line, next to read and excluded.
It is `None` everywhere else, so `exclude_none` keeps it out of the item entirely
once the generation actually runs.

On the record, one new attribute: `MediaArtifactRecord.awaiting_expires_at`. It
does double duty and that is deliberate — it is both **the marker that tells the
two kinds of `queued` apart** (waiting for a source vs waiting for the generator,
which no other field distinguishes) and **the deadline**. A `queued` entry with it
is un-enqueued; a `queued` entry without it has a message in flight.

### AC#5 — why the id does not move, and why there is exactly one debit

`build_artifact_id` hashes `user_id | scope | scope_id | artifact_type |
_stable_json(parameters) | sorted(source content ids)`. Two of those three moving
parts had to be made knowable *before* any source is readable.

**The source set.** `plan_artifact_generation` keys on
`resolution.expected_source_ids` = the content ids of the read sources **plus** the
pending ones. A source being transcribed is part of what the artifact will have
read, so it belongs in the fingerprint. Leaving it out is precisely what would
produce the failure mode the task named: one id for the deferred request, another
for the generation, two entries, two debits.

**`parameters["language"]`.** It used to be copied from the first resolved source's
`translation_metadata["target_language"]` — unknowable when nothing is resolved.
It is now `normalize_language_tag(reading_language)`, computed in
`resolve_scope_sources` itself. This is not an approximation: every construction of
`TranslationOutcome` in `transcript_translation.py` passes
`target_language=normalized_target`, which is `normalize_language_tag(target_language)`
of the very `reading_language` handed in. Same value, one call earlier. (The
private `_normalize_lang` was renamed `normalize_language_tag` for that import;
`raw_content_service` follows.)

**And the safety net.** At resume, `artifact_wait_service._resume_one` recomputes
the id from the *finished* resolution and enqueues only on an exact match. A
mismatch means the scope's sources moved while the entry waited, so generating
would store an artifact under an id that no longer describes it — and the next
identical request would regenerate and be charged again, since task-322's reuse
rule keys on exactly that equality. The entry fails with `sources_changed`
instead. The stored `parameters` go back through
`normalize_artifact_parameters` before hashing, which is why that function now
coerces `Decimal`: DynamoDB returns numbers that way and `_stable_json` cannot
serialise them.

**One debit.** The POST debits `quota_enforcer.record_generation(...,
idempotency_token=record.artifact_id)` on `created` / `retried`, waiting entry
included — the request was accepted. The resume charges nothing. A second POST
while the entry waits is answered `reused` (200, no debit) by the ordinary reuse
branch, since a `queued` entry is not `failed`. `check_generation_allowed` is
now asked about `len(resolution.expected_source_ids)`, i.e. the same figure
`record.source_count` debits — checking the smaller "readable only" count would
let a deferred collection past a ceiling it exceeds.

### AC#3 — the resume, with no new queue, schedule or index

`media_summarizer/core/services/artifact_wait_service.py` hangs off the two join
points the task named, both of which already existed:

- `workers/events/media_completed_worker.py` — after the watcher fan-out loop (the
  resume re-resolves the scope, so it must run *after* the loop marks the jobs
  completed), in the `if not watchers:` branch (a waiting entry hangs off the
  library row, not off a watcher), and on the failure path;
- `workers/transcript_translation_worker.py` — after `worker.translation_completed`
  is logged (the lock must read `done` before the resume re-resolves, or it would
  see the translation as still in progress), and on the empty-transcript
  `mark_translation_done`.

Both hooks are keyed on `media_key`, which is what a waiting entry names. The
lookup: `user_media.list_by_media_key` (the cross-user GSI — ingestion is
deduplicated globally) → per row, the media scope key plus the folder scope keys
of its collection **and every ancestor** (a collection artifact covers its
descendants) → `media_artifacts.list_queued_artifact_ids_by_scope` on the existing
`scope-index` → one `GetItem` per id (at most five per scope, one per type)
because the index does not project `awaiting_expires_at` → keep the entries whose
own snapshot names one of this media's library rows with a `preparation` on it.

That last check is what makes the lookup honest without a second index: an entry
that had already *excluded* this media before the request is never mistaken for
one waiting on it.

Exactly-once is `media_artifacts.claim_awaiting_artifact`: `SET sources,
source_count, updated_at REMOVE awaiting_expires_at` conditional on the entry
still being a waiting `queued` one. Whoever clears the attribute owns the enqueue;
every other caller — the other join point, the second of two sources landing
together, a redelivered SQS message — reads `False` and sends nothing. The
snapshot is replaced in the same write because a waiting entry's lines carry no
transcript key, and the snapshot must designate the exact text the model reads.

No client path replays the POST: the mobile only ever polls
`GET /api/artifacts?scope=`, which is what already drove `queued` → `generating`.

**Chaining is expected.** A transcription completing may leave the entry pending on
a *translation* — reserved and dispatched by the resume's own re-resolution. The
resume logs `artifact.still_awaiting` and returns; the translation-completed hook
then brings it back.

### AC#4 — waiting is not failing, and no wait is unbounded

A preparation that cannot complete ends the wait **immediately**, with
`sources_preparation_failed`:

- failed ingestion → `media_completed_worker` failure path;
- permanently refused translation → `transcript_translation_worker`, both terminal
  branches (`TranscriptTranslationError` and `outcome.translation_failed`).

A **transient** translation failure deliberately does *not* end the wait. Resuming
there would re-resolve the scope, which reserves and re-enqueues the very
translation that just failed — a loop task-327 exists to prevent. The entry's own
deadline is what ends it if the provider never recovers.

The deadline is `awaiting_expires_at` = now + `AWAITING_SOURCES_TIMEOUT_SECONDS`
(`ARTIFACT_AWAITING_TIMEOUT_SECONDS`, 1 h). It is **stored, not derived from
`created_at`**: `plan_artifact_generation` preserves `existing.created_at` when it
reclaims a failed entry, so a retried request would otherwise be born already
expired. Enforced in three places, each for its own reason:

1. `list_scope_artifacts` → `end_overdue_waits`, so the deadline is felt at the
   only moment it matters, when someone is looking at the tile. Two-step: the
   `scope-index` projects `created_at` but not `awaiting_expires_at`, and the two
   differ for a reclaimed entry, so the projected date can only *rule out* an
   expiry — which is enough to make the common poll cost zero extra reads;
2. `plan_artifact_generation`, so a new request is never answered by a dead wait;
3. `workers/cleanup/media_lifecycle.run_reconciliation`, the backstop for the entry
   nobody ever looks at again. Its artifact scan now projects `status` and
   `awaiting_expires_at`, and the report gains `artifact_waits_overdue` /
   `artifact_waits_expired`.

All three write through `media_artifacts.fail_awaiting_artifact`, conditional on
the entry still being a waiting one — an event racing a resume can never mark a
running generation failed. Three terminal codes:
`sources_preparation_timeout`, `sources_preparation_failed`, `sources_changed`.
Each lands on the actionable failed tile task-328 defined, and asking again starts
a fresh generation over whatever is readable by then.

### AC#9 — no infrastructure resource is needed

Checked, not assumed:

- `infrastructure/terraform/modules/platform/runtime_env.tf` — `MEDIA_ARTIFACTS_TABLE`
  and `ARTIFACT_GENERATOR_QUEUE` are in `local.table_names` / `local.queue_names`,
  both merged into `local.lambda_environment`, which the API **and every worker**
  Lambda share. The two resume hooks therefore already have the table and the queue
  in their environment;
- `infrastructure/terraform/modules/platform/iam_lambda.tf` — `aws_iam_policy.lambda_worker`
  grants `sqs:SendMessage` on `aws_sqs_queue.artifact_generator.arn` and DynamoDB CRUD
  on `local.table_arns` (which covers `table/*<suffix>/index/*`, hence the
  `scope-index` query). `lambda_media_lifecycle` runs under the same role;
- `ARTIFACT_AWAITING_TIMEOUT_SECONDS` has a code default, so it needs no declaration
  to work — only to be tuned;
- the `scope-index` projection is **deliberately not** extended to
  `awaiting_expires_at`. DynamoDB cannot alter an existing GSI's projection in
  place; it would mean creating a second index to save one `GetItem` per queued
  entry per lookup, capped at five per scope.

No new queue, no new schedule, no new index, no new table. Hence no
`infrastructure/terraform/` diff and nothing for `terraform validate` to judge.

### What the mobile lost

`ArtifactTile.sourceReady` and its "Processing…" note are gone, and so is the
`ArtifactsPanel` prop that forwarded them: how far along a source is is no longer
the tile's business, since the request is accepted either way. Both call sites drop
the prop (`app/media/[id].tsx`, `app/media/collections/[id].tsx`), the
`sources_not_ready` branch of `lib/artifactRefusal.ts` is deleted, and the
`artifacts.refusal.transcriptPending` / `sourcesPending.*` keys are out of all 11
catalogues (49 lines, `ar.ts` included with its four extra plural forms).

**No string was added.** The owner's decision was that a deferred request looks
"exactly like a normal generation", so a waiting entry renders through the existing
`artifacts.status.queued` — which is also what keeps the two kinds of `queued`
indistinguishable to the user, as intended. `artifacts.processing` stays: it is
`TranscriptReader`'s, not the tile's.

### Owner notes (not ACs)

- **A residual screen-level gate on the media tab.** `app/media/[id].tsx` renders a
  full-screen processing placeholder while `processing_job.status !== "completed"`,
  so the AI tab itself is unreachable during ingestion of a *single* media — the
  `sourceReady` guard this task removed was, on that path, only ever reached with
  the job already complete. On the media scope the deferral therefore engages for
  the **translation** window (job done, transcript being translated) and for a
  transcript that is not readable yet; the **transcription** window is exercised
  from a collection's AI tab, where a still-ingesting member is a genuine pending
  source. Opening the detail screen mid-ingestion is a separate screen decision
  (and task-365 is restructuring that file), so it was left alone.
- **Poll duration.** `ARTIFACT_POLL_INTERVAL_MS` is 3 s and the poll runs while any
  entry is `queued` or `generating`, with no cap. A waiting entry can now hold that
  open for the length of a transcription rather than the length of a generation.
  Same cadence `useMediaDetailPolling` already uses for the same window, and one
  `scope-index` query per tick, so it was not changed — but it is the one cost this
  feature moves.
- **Existing dev artifacts will not be reused.** `parameters["language"]` is now
  derived one call earlier, and pending sources enter the fingerprint, so ids
  computed before this change do not match the ones computed after. Nothing is
  deployed and nothing has to be bridged: the first request per scope regenerates.
- No automated test was added — the project forbids them unless explicitly
  requested.
<!-- SECTION:NOTES:END -->
