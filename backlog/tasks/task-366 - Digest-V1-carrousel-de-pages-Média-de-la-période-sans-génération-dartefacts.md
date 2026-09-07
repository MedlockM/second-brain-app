---
id: task-366
title: >-
  Digest V1 : carrousel de pages Média de la période, sans génération
  d'artefacts
status: To Do
assignee: []
created_date: '2026-09-06 15:41'
updated_date: '2026-09-07 14:30'
labels:
  - mobile
  - backend
  - feature
dependencies:
  - task-365
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## La forme décidée

Décision owner du 2026-09-06. Le Digest V1 est **un carrousel horizontal de pages Média, et rien d'autre** :

- une carte = la page Média complète d'un média, avec ses deux onglets Reader et IA ;
- ordre **chronologique croissant** ;
- pagination horizontale reprise de la Revue des non-classés (`mobile/app/media/unsorted-review.tsx`, `ScrollView horizontal pagingEnabled`), **mais sans les actions Jeter / Approfondir / Ranger** : le Digest ne propose aucune action sur le média, il le présente.

L'intérêt visé est la rétention par la répétition : revoir le contenu réel, pas un résumé de résumé.

## Les périodes — révisées le 2026-09-06 avec la décision sur les notifications

Le Digest est notifié : chaque jour à 18h30 locale pour le daily, chaque lundi à 9h30 locale pour le weekly (tâche séparée). Les périodes sont donc définies par ce que la notification annonce, pas par le calendrier :

- **Daily = les 24 heures glissantes précédant l'envoi de 18h30.** Pas la journée calendaire. C'est ce qui garantit qu'un média enregistré à 22h est annoncé exactement une fois, au lieu de rejoindre en silence un digest déjà notifié.
- **Weekly = la semaine écoulée, lundi à dimanche révolus.** Pas la semaine ISO en cours, qui n'a que neuf heures d'âge quand la notification part le lundi à 9h30.

### Conséquence à implémenter explicitement : la fenêtre est figée, pas recalculée

Une fenêtre recalculée à chaque ouverture de l'écran ne correspondrait **jamais** à ce que la notification a annoncé : ouvert à 21h, un digest glissant montrerait 21h−24h, un autre ensemble que celui de 18h30.

Le digest est donc **capturé au moment de l'envoi** et reste stable jusqu'au suivant. Entre minuit et 18h30, l'écran montre la capture de la veille. Le `period_key` reste utilisable : date locale de l'envoi pour le daily, semaine ISO écoulée pour le weekly.

## Dépendance stricte

La carte rend le composant partagé produit par **task-365**, avec son chrome désactivé. Le Digest ne redessine pas la page Média et n'en fait aucune variante : si la page Média change demain, le Digest suit sans qu'on y touche. C'est l'exigence centrale de l'owner, pas une préférence d'implémentation.

Un header unique « Daily / Weekly » est rendu au-dessus du pager. Le sélecteur Daily/Weekly existant de `mobile/app/(tabs)/digest.tsx` est conservé.

## Ce que la V1 supprime

En affichant la page Média entière, la V1 retire son unique consommateur à toute la charge utile actuelle du digest. Elle est supprimée, pas conservée :

- backend : `insights`, `themes`, `stats` (`media_count`, `total_minutes`, `by_type`), `summary_excerpt`, `read_time_minutes` dans `core/models/digest.py`, `utils/digest_db.py` et `api/endpoints/digest.py` ;
- mobile : les mêmes champs dans `mobile/src/types/digest.ts`, et le composant `InsightCard` de l'écran digest.

Le contrat se réduit à **une liste ordonnée d'identifiants de médias** pour la période, plus ce que la pagination exige réellement.

## Le Digest ne génère plus rien

`trigger_summary_short_generation` de `media_summarizer/core/services/digest_service.py` (vers la ligne 252) est supprimé. Avec lui disparaissent `DigestStatus.PENDING` et `DigestStatus.READY`, qui n'existaient que pour suivre cette pré-génération, ainsi que `summary_short_artifact_id` et `summary_short_status` de `DigestMediaItem`.

Conséquence assumée par l'owner : dans le Digest, l'onglet IA d'un média affiche ses tuiles « à générer » tant qu'elles ne l'ont pas été ailleurs, et une génération lancée depuis le Digest débite le quota comme depuis la page Média. C'est le comportement normal de la page, et c'est voulu.

## Période vide

Décision owner : **aucun enregistrement de digest n'est écrit** pour une période sans média, et l'onglet affiche un **état vide sobre**. Pas de repli sur une période précédente remplie, pas de bascule automatique sur Weekly. Aucune notification ne part non plus (traité dans la tâche notifications).

## Le risque technique à traiter

Une page Média scrolle verticalement et porte ses propres onglets ; l'imbriquer dans un pager horizontal expose à des conflits de gestes sur iOS. La Revue des non-classés ne rencontre pas le problème parce que ses cartes sont courtes (`MAX_BULLET_LINES = 3`). C'est le point dur de la tâche et il doit être traité explicitement, pas découvert à l'exécution.

Volume : une période chargée peut compter plusieurs dizaines de médias, chacun avec son `MediaStatusResponse` et ses artefacts. Le montage et le chargement doivent être paresseux — fenêtre autour de la carte courante — faute de quoi l'ouverture du Digest déclenche autant de requêtes que de médias.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Aucun champ conservé « pour compatibilité », aucun rendu de repli sur l'ancienne carte, aucune double lecture du contrat. Les anciens champs sont retirés du modèle, de l'endpoint et des types mobile dans la même passe. La bascule journée calendaire → 24 h glissantes remplace la logique existante, elle ne coexiste pas avec elle.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle du carrousel et du comportement des gestes demande un build : elle t'appartient.
- Le déploiement du contrat réduit se joue au push sur `main`, après la fin de l'agent.
- L'envoi effectif à 18h30 et 9h30 relève de la tâche notifications ; ici, seules les fenêtres de calcul changent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 L'onglet Digest rend un carrousel horizontal paginé où chaque page est le composant partagé de task-365, chrome désactivé, affichant la page Média complète avec ses onglets Reader et IA
- [x] #2 Aucune action Jeter, Approfondir ou Ranger n'est rendue dans le Digest, et un header unique Daily/Weekly est rendu au-dessus du pager, le sélecteur Daily/Weekly étant conservé
- [x] #3 Daily liste les médias enregistrés dans la journée et Weekly ceux de la semaine, dans l'ordre chronologique croissant, vérifiable contre les enregistrements réels de DynamoDB -dev
- [x] #4 Seules la carte courante et ses voisines immédiates sont montées et voient leur donnée chargée : l'ouverture du Digest ne déclenche pas une requête par média de la période
- [x] #5 Le comportement des gestes est traité explicitement : le scroll vertical de la page Média et le changement d'onglet Reader/IA n'empêchent pas la pagination horizontale, et les notes d'implémentation décrivent le mécanisme retenu
- [x] #6 trigger_summary_short_generation est supprimé de digest_service.py, et le Digest ne déclenche plus aucune génération d'artefact, vérifiable sur -dev en constatant qu'aucun artefact n'est créé à l'assemblage d'un digest
- [x] #7 DigestStatus.PENDING et READY, summary_short_artifact_id et summary_short_status ne subsistent plus dans core/models/digest.py ni dans utils/digest_db.py
- [x] #8 Les champs insights, themes, stats, summary_excerpt et read_time_minutes sont retirés du modèle backend, de api/endpoints/digest.py et de mobile/src/types/digest.ts, et le composant InsightCard est supprimé
- [x] #9 Une période sans média enregistré n'écrit aucun enregistrement de digest et l'onglet affiche un état vide, sans repli sur une autre période ni bascule automatique sur Weekly
- [x] #10 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés

- [x] #11 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
### What the digest became

A digest is now the ordered list of media ids a period held, and nothing else. `DigestRecord` keeps `user_id`, `digest_type`, `period_key`, `media_items`, timestamps and `published_at`; `DigestMediaItem` keeps `media_item_id` and `added_at`. `DigestStatus` is deleted outright — it existed only to track the pre-generation that is gone — as are `insights`, `themes`, `stats`, `summary_excerpt`, `read_time_minutes`, `summary_short_artifact_id`, `summary_short_status` and the endpoint's per-item projection with its S3 cover presign. `GET /api/digest/{daily,weekly}` returns `{digest_type, period_key, media_item_ids}` and takes no query parameter. The mobile side mirrors that exactly: one `Digest` interface with three fields, a two-method service, no `InsightCard`.

### The windows, and why they are frozen

`DAILY_SEND_TIME = 18:30`, `WEEKLY_SEND_TIME = Monday 09:30`. `resolve_daily_window` returns the 24 h before the last 18:30 already past; `resolve_weekly_window` returns the Monday-to-Sunday week that closed before the last Monday 09:30. Both windows are half-open `[start, end)`, so a media saved at exactly the send instant belongs to the next period — announced once, never skipped. Between midnight and 18:30 the screen therefore shows yesterday's capture, which is the intended reading.

`_get_or_assemble` freezes the list on first read and returns it verbatim afterwards. Re-deriving would be harmless (the window is entirely in the past) but would cost a library scan per screen open. The window is derived from the `now` the caller passes, not from a clock of its own, so task-367's stored IANA zone will only change the argument.

### Gesture arbitration (AC#5)

Settled by construction, with no gesture library, on four points documented in the header of `mobile/app/(tabs)/digest.tsx`:

1. **The pager is the only horizontal scrollable in the subtree.** Verified by grep: the sole other `horizontal` scroll view in the app is `HomeTile.tsx`, on the Home screen. So no inner view competes for the horizontal pan.
2. **`directionalLockEnabled` on both axes** — on the pager and on the vertical `ScrollView` of `CompletedDetailView`. One drag moves one axis; a mostly-horizontal drag is never eaten by the vertical scroll and the reverse.
3. **Every slot occupies exactly `SCREEN_WIDTH`, mounted or not.** Placeholders reuse the page style, so content width stays `ids.length * SCREEN_WIDTH` at all times and lazy mounting can never move a page boundary under the finger. This is the failure mode `unsorted-review.tsx` has to undo by hand when it removes an item.
4. **The Reader/AI tab row is a row of `Pressable`s**, which cannot consume a pan, and switching tabs repaints one page.

Accepted iOS limitation, stated rather than hidden: a touch that stops a page mid-glide is claimed by that page's scroll view, so the swipe within that same touch does nothing and the next one works. Standard paged-carousel behaviour.

### Mount window (AC#4)

`MOUNT_RADIUS = 1`: the active page and its two neighbours are mounted, everything else is a fixed-width placeholder. Each mounted page runs `useMediaDetailPolling` itself, so mounting *is* what starts loading and unmounting is what stops it — the mount window is the loading policy, with no second cache to keep in sync. A period of fifty media therefore starts three status polls, not fifty, which also bounds the number of live poll timers. Accepted cost: a page left three or more positions behind refetches when revisited, which no single swipe can cause. `RefreshControl` is gone from the pager (it only works on a vertical scroll view, and a frozen capture has nothing to refetch); it stays on the error and empty states.

### Evidence gathered against real -dev resources

Assembled digests by calling the real service against `user_media-dev`, `user_digests-dev` and `user_digest_settings-dev`, at `now = 2026-09-07T13:46Z` (a Monday, before 18:30):

- **AC#3** — daily resolved to `period_key=2026-09-06`, window `[2026-09-05T18:30 → 2026-09-06T18:30)`, 4 items for the busiest test user; weekly resolved to `period_key=2026-W36`, window `[2026-08-31T00:00 → 2026-09-07T00:00)`, 31 items for the same user and 1 for another. Every returned list was ascending on `added_at`. Media saved after 18:30 on 2026-09-06 correctly fell outside the daily window, into tonight's send.
- **AC#6** — `media_artifacts-dev` held 91 rows before the four assemblies and 91 after: delta 0. Assembling a digest creates no artifact and debits no quota.
- **AC#9** — the user whose daily window was empty got **no** `daily#2026-09-06` row written, while their non-empty `weekly#2026-W36` row was written. Three rows total for four assemblies.
- **AC#7 / AC#8, storage side** — the rows the new code persisted carry exactly `created_at, digest_key, digest_type, media_items, period_key, updated_at, user_id`, and each item exactly `added_at, media_item_id`. No `status`, no artifact field, no statistic.

A side effect worth recording: the digest window filters the *visible* library, because `list_library_for_user` drops soft-deleted rows (`deleted_at` + `purge_at` TTL, no `is_deleted` boolean). A raw table scan therefore overcounts a period; the service is the authority.

### Dev data cleanup

`user_digests-dev` held 45 old-shape captures — all carrying `status`, 37 of them empty-period rows the new rule forbids writing, and the non-empty ones assembled under the retired calendar-day rule with the retired transcript filter. A capture is derived data re-assembled from `user_media`, and per AGENTS.md "Nothing is deployed yet" there is nothing to bridge, so all 45 were deleted rather than read through a compatibility path. None carried `published_at`, so no weekly notification can be re-sent as a result. The table is now populated only by the three new-shape rows the verification produced.

### Also touched

`workers/digest/scheduler.py` lost `pre_generate_summary_shorts()`, `STAGGER_DELAY_SECONDS` and its `pre-generate` mode; weekly publication now guards on `published_at is None and media_items`, so a silent week neither stores nor notifies. Two stale doc references to the deleted generation path were reworded (`review_blurb_service.py`, `scripts/backfill_review_blurbs.py`). `CompletedDetailView` gained one prop-free line — `directionalLockEnabled` on its vertical scroll view — which is what makes it swipeable when nested, and constrains nothing on its own route.

### Checks

`uv run ruff check .` clean, `uv run mypy media_summarizer/` clean on 178 files, `npm run typecheck` clean (which also proves all 11 i18n catalogues carry the two new keys, since a missing key is a tsc error), `npm run lint` showing only the pre-existing `purchaseService.ts` warning. `ruff format --check` is not a repo gate and drifts on 127 files including ones untouched here. No automated tests were added, per repository instructions.

### Left to the owner

The visual rendering of the carousel and the feel of the gestures need a build — the task's own owner notes assign that check to the owner. Deploying the reduced contract happens at push to `main`. Actual sending at 18:30 and 09:30 belongs to the notifications task.
<!-- SECTION:NOTES:END -->
