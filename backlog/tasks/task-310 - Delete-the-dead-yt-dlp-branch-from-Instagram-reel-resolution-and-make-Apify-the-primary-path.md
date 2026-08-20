---
id: task-310
title: >-
  Delete the dead yt-dlp branch from Instagram reel resolution and make Apify
  the primary path
status: Done
assignee: []
created_date: '2026-08-20 19:39'
updated_date: '2026-08-20 22:20'
labels:
  - backend
  - ingestion
  - cleanup
  - instagram
dependencies:
  - task-309
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Same finding as task-309, on the other platform where yt-dlp is tried first. Measured on dev on 2026-08-20:

- All 10 Instagram jobs in `processing_jobs-dev` resolved through `apify~instagram-reel-scraper`. **None** resolved through yt-dlp.
- `/aws/lambda/media-summarizer-worker-instagram_ingestion-dev` logs `instagram.reel.ytdlp_ip_blocked` — "yt-dlp IP-blocked on Instagram, starting async Apify fallback" — on **6 attempts out of 6**, spanning 2026-08-18 to 2026-08-20.

task-145 already recorded this at 6/6 on 2026-08-17 and the owner chose to hold the residential-proxy answer to V2. Three days and a fresh set of saves later the rate is still 100%, so the branch is not a fallback that fires occasionally — it is dead code that every reel ingestion pays for before Apify does the actual work.

The owner's decision on 2026-08-20 is to delete it. There is no installed base to keep working, so Apify becomes *the* Instagram resolution path and the yt-dlp attempt goes away in the same run.

## Relationship to task-145 (must be handled, not ignored)

task-145 §3 is written as "on `_InstagramYtdlpBlocked`, retry yt-dlp through the residential proxy". After this task there is no such branch and no yt-dlp call site to retry. That does not invalidate task-145 — a proxied yt-dlp path is still the cheap primary it argues for — but it changes it from *modify the existing branch* to *introduce a proxied path where none remains*, for Instagram specifically. Its TikTok half is unaffected: TikTok still resolves via yt-dlp and works (2/2 saves in `native_subtitles`, zero IP blocks logged on 2026-08-20).

So update task-145's description and acceptance criteria to match reality rather than leaving them pointing at deleted code.

## Scope

In `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`, remove `_resolve_reel_via_ytdlp`, the `_InstagramYtdlpBlocked` exception and every branch raising or catching it, the `instagram.reel.ytdlp_ip_blocked` event, and the yt-dlp import. Reels take the same `InstagramApifyRequired` route posts already take, so the queue worker starts the Apify run directly.

Then check the metadata contract downstream: the yt-dlp path set `audio_url_kind: audio_ytdlp` and `resolution_mode: deepgram_via_ytdlp_audio_url`. If any consumer branches on those values, it must be reconciled with what the Apify path actually writes (observed on dev: `provider: apify`, `transcript_source: deepgram_pending`, then a Deepgram push on the `cdninstagram` URL).

`media_summarizer/utils/ytdlp_helpers.py` is imported only by this resolver and by the YouTube worker, and task-309 removes the other importer. Delete the module here, once it has no remaining importer. If task-309 has not landed, this task's dependency ordering is wrong — check before deleting rather than leaving a broken import.

Anything in `infrastructure/terraform` keyed on the `instagram.reel.ytdlp_ip_blocked` event or a yt-dlp-specific Instagram metric goes with the code.

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`: mark the Instagram section superseded and record Apify-only as the current strategy, with the 6/6 measurement as the reason. The ADR's TikTok section stays as it is — it still describes what runs.

## Owner note (not an acceptance criterion)

Confirm after the deploy on `main` by saving a reel and a non-reel Instagram post on dev, and checking the worker no longer logs `instagram.reel.ytdlp_ip_blocked` and that the Deepgram transcript still lands.

## References

- Resolver: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`.
- Worker: `media_summarizer/workers/instagram_ingestion_worker.py`.
- Shared module to delete: `media_summarizer/utils/ytdlp_helpers.py`.
- YouTube counterpart: task-309. V2 proxy work to amend: task-145. Prior measurement of the same block: task-274.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Instagram resolver no longer imports yt_dlp and contains no yt-dlp resolution attempt, no _InstagramYtdlpBlocked exception and no instagram.reel.ytdlp_ip_blocked event
- [x] #2 Reels and non-reel posts both resolve through the Apify path, with the queue worker starting the Apify run directly and no branch left that distinguishes them by extraction strategy
- [x] #3 Any consumer that branched on audio_url_kind or resolution_mode values produced only by the yt-dlp path is reconciled with the values the Apify path writes, or the check is removed if no consumer reads them
- [x] #4 media_summarizer/utils/ytdlp_helpers.py is deleted and a repo-wide grep confirms no remaining importer
- [x] #5 Every Terraform dashboard widget and alarm keyed on the instagram.reel.ytdlp_ip_blocked event or a yt-dlp-specific Instagram metric is removed, and terraform validate is clean
- [x] #6 task-145's description and acceptance criteria are updated so its Instagram half describes introducing a proxied yt-dlp path rather than modifying a branch that no longer exists, and its TikTok half is left unchanged
- [x] #7 docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md marks the previous Instagram strategy superseded and records Apify-only as the current one, citing the 2026-08-20 dev measurement (6/6 ytdlp_ip_blocked, 10/10 saves via Apify), with the TikTok section left unchanged
- [x] #8 The TikTok worker's yt-dlp path is untouched and the yt_dlp dependency remains declared for it
- [x] #9 ruff and mypy are clean on the changed Python files
<!-- AC:END -->


## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Apify est désormais le chemin unique de résolution Instagram.

**Resolver** (`instagram_apify_resolver.py`) — suppression de `_resolve_reel_via_ytdlp`, de l'exception interne `_InstagramYtdlpBlocked`, du détecteur `_looks_like_ig_ip_blocked_error`, de l'événement `instagram.reel.ytdlp_ip_blocked`, de la constante `YTDLP_TIMEOUT_SECONDS` et des imports `yt_dlp` / `asyncio` / `os`. `resolve()` classifie l'URL puis lève `InstagramApifyRequired` pour tous les types de contenu ; reels, IGTV et posts empruntent la même route, le worker démarre l'acteur directement.

**Sentinel E2E** — `strip_e2e_force_ip_block_sentinel` a aussi été retiré du resolver : il n'existait que pour forcer la branche Apify tant que yt-dlp était primaire. Sans yt-dlp il n'y a plus rien à forcer, et le laisser aurait signifié soit un booléen mort, soit une URL polluée par `__e2e_force_ip_block__=1` transmise à l'acteur. Le sentinel a donc été retiré de l'URL soumise par `tests/e2e/test_fallback_chains.py::test_instagram_apify_fallback` (qui valide maintenant le chemin primaire Apify → Deepgram push), et TikTok reste son seul consommateur.

**Contrat de métadonnées (AC #3)** — `audio_url_kind: audio_ytdlp` et `resolution_mode: deepgram_via_ytdlp_audio_url` n'étaient lus par personne. Le seul lecteur de `audio_url_kind` est `instagram_ingestion_worker.py:478`, qui le journalise sans brancher dessus. Les occurrences de `resolution_mode` dans `adapters/resolvers.py` appartiennent au resolver podcast et sont sans rapport. Rien à réconcilier, donc, au-delà du fait que le chemin Apify écrit désormais toujours `provider: apify`, `audio_url_kind: audio|video`, `resolution_mode: deepgram_via_apify_audio_url`.

**`utils/ytdlp_helpers.py` supprimé (AC #4)** — le resolver Instagram en était le dernier importeur ; task-309 avait retiré celui de YouTube. Le worker TikTok n'importait pas ce module : il porte ses propres copies privées (`_collect_subtitle_candidates`, `_resolve_direct_media_url`, …), il n'est donc pas affecté. `grep -rn "ytdlp_helpers" --include=*.py` ne renvoie plus rien.

**Terraform (AC #5)** — aucun widget ni alarme n'était indexé sur `instagram.reel.ytdlp_ip_blocked` ni sur une métrique yt-dlp spécifique à Instagram : `grep -rn "ytdlp" infrastructure/terraform/` était déjà vide avant la modification. Rien à supprimer. `terraform validate` sur `envs/dev` : `Success! The configuration is valid.`

**TikTok intact (AC #8)** — aucun fichier TikTok touché hormis deux références de documentation qui pointaient vers le module supprimé : `docs/INGESTION_WORKERS_PROVIDERS.md` renvoyait à `utils/ytdlp_helpers.py::resolve_direct_media_url` pour la cascade TikTok alors que le worker utilise sa propre `_resolve_direct_media_url`. Corrigé. `yt-dlp` reste déclaré dans `pyproject.toml:27`.

**Docs** — ADR : nouvelle section « Instagram extraction (V2, post-task-310) », l'ancienne section Instagram marquée SUPERSEDED, la section TikTok inchangée, et la justification « le paquet yt-dlp reste pour TikTok et Instagram » de la section YouTube corrigée (TikTok est le dernier consommateur). Également mis à jour : `INGESTION_WORKERS_PROVIDERS.md` (chemin primaire, cascade, modes Deepgram, carte des modules, diagramme ASCII de routage — dont la colonne YouTube restée périmée depuis task-309), `MEDIA_INGESTION_CORE_ARCHITECTURE.md` et la ligne du tableau E2E de `V1_LAUNCH_PLAN.md`.

**task-145 (AC #6)** — description et AC mis à jour : sa moitié Instagram décrit maintenant l'introduction d'un chemin yt-dlp proxifié là où il n'en reste aucun (avec l'avertissement que `ytdlp_helpers.py` a disparu et que le `ResolvedMedia` devra porter `cover_url`/`creator_name`, ce que la branche supprimée ne faisait pas), la moitié TikTok est inchangée.

**Vérifications** — `ruff check media_summarizer/ tests/` et `mypy media_summarizer/` (173 fichiers) propres, `terraform validate` OK sur `-dev`.

**Note owner (hors AC)** : après le merge et le push sur `main`, sauvegarder un reel et un post non-reel sur dev, puis vérifier que le worker ne journalise plus `instagram.reel.ytdlp_ip_blocked` et que le transcript Deepgram arrive bien.
<!-- SECTION:NOTES:END -->
