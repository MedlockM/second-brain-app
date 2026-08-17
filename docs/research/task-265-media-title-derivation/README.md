---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark: title derivation strategies for ingested media

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — texte libre décrivant la décision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes précises de correction à intégrer au prochain passage)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Retain approach C — "metadata-first, deterministic distrust, LLM only where metadata is structurally absent" — with the title written onto `job.title` immediately before the worker publishes `episode_completion_status`.**

Three findings drive this choice, and none of them is about money:

1. **The plumbing already exists and is free.** `job.title = X` followed by `await database_async.update_processing_job(job)` propagates to the durable library row on its own: `database_async.py:337-360` calls `_mirror_job_to_durable_library(job)` from both `create_processing_job` and `update_processing_job`, and `durable_media_service.mirror_job` (`:341-350`) mirrors `("title", "title")` for any non-empty value. The Inbox (`GET /api/media`) and the digest (`digest_service.py:92` reads `record.title`) both read that row. `media_completed_worker.py:178-186` builds the Algolia indexing message from `canonical_job.title` on the completion event. So a title written **before** that event reaches all four consumers with **zero** new queue, zero new table and zero Algolia re-index. This is not a design to build — it is a hook to use.
2. **Most of the metadata the app needs is already in memory and thrown away.** The YouTube worker holds the full yt-dlp `info` dict (`youtube_ingestion_worker.py:1060`) and never reads `info["title"]`. The TikTok worker holds one too (`tiktok_ingestion_worker.py:1017`) whose `title` *is* the video caption. `article_extraction_worker.py` imports trafilatura, whose `Document` exposes `title` (verified on the installed 2.0.0), and calls `extract(..., output_format="txt")`, which discards it. The RSS poller reads the feed item's `<title>` into a local variable (`rss_feed_poll_worker.py:51`) and drops it. Fixing that is one extra field read per source: **no new provider, no new dependency, no added latency, 0 €**.
3. **Cost does not discriminate the LLM approaches — quality and latency do.** A title from `gpt-5-nano` costs **$0.00007–$0.00014 per item** (§8). Generating a title for *every* item (approach B) would add **0,024 €/month** to the most text-heavy tier of task-65, i.e. 1,8 % of that tier's media cost. B is therefore *not* rejected on price. It is rejected because (a) it discards good provider titles in favour of a paraphrase on the ~85 % of items where a real title exists (the share follows task-65’s baskets, which are dominated by articles, YouTube and podcasts — see §8.3), (b) it puts a model round-trip on the critical path of every ingestion, including the article path that has no model call at all today, and (c) it opens a headline-hallucination surface on 100 % of items instead of ~15 % (§10).

Concretely, what the owner would be validating:

- **One shared, pure derivation helper** (e.g. `core/media_ingestion/title_derivation.py`) with two entry points: `normalize_title_candidate(raw, context)` and `derive_title(candidates, source_platform, saved_at, transcript_head)`. It normalises (percent-decode, strip the extension, collapse `_`/`-`/`+` into spaces, drop a trailing ` | Site Name` / ` - Site Name`, trim to 120 chars on a word boundary), rejects candidates by the **deterministic** rules of §6.1, and returns the first survivor.
- **Each producer sets `job.title` and calls `update_processing_job(job)` before publishing `episode_completion_status`.** Every one of those publish sites already calls `update_processing_job` on the preceding lines: `youtube_ingestion_worker.py:1206-1213`, `tiktok_ingestion_worker.py` (native + Apify branches), `orchestrators.py:289-300` (Apify social-video bypass) and `:339-352` (shared text), `article_extraction_worker.py:379+`, `document_parsing/worker.py:260-270`, `transcription/deepgram_worker.py:807-819`, `x_ingestion_worker.py:456` (already correct — the reference implementation).
- **`gpt-5-nano` is called only when no candidate survives**, on the first ~1 200 tokens of the transcript, with `reasoning_effort: "minimal"` and a hard `max_output_tokens` cap; a failure or a timeout degrades to the deterministic label, never to a failed job.
- **The sentinels are deleted outright**, not hidden: `orchestrators.py:163`, `use_cases.py:140,172`. The deterministic last-resort label (platform label + save date, §9.2) replaces them, computed server-side and stored — and the two divergent mobile fallbacks (`MediaListCard.tsx:40` returns the source URL, `search.tsx:491` returns `"Untitled"`) are deleted so that exactly one rule exists.

**Trade-offs accepted.** This is the widest blast radius of the six options: ~6 workers + 2 resolvers + 1 API endpoint + 1 mobile helper. That is unavoidable — the title is written in six places today, and there is no downstream choke point holding all the candidates. The only true convergence point for audio, the Deepgram worker, has *no* metadata at all: `grep -n title transcription/deepgram_worker.py` returns nothing, and its success event carries no title field. The single-file alternative is approach B; if the owner prefers minimal churn over metadata fidelity, B is the honest second choice and §5 states exactly what it costs. Second trade-off: an LLM title is not reproducible across re-ingests of the same shared text. Acceptable — nothing keys on the title, and there are no users (`AGENTS.md` § "Nothing is deployed yet").

**One caveat for the implementer, not for the decision**: pin the model id at implementation time. Artificial Analysis flags `gpt-5-nano` as deprecated on its model page while OpenAI's pricing page still lists it; if the `gpt-5-nano-2025-08-07` snapshot used by `transcript_translation.py` is retired, fall back to `gpt-5.4-nano-2026-03-17` (task-72's choice for every other artifact) — 3,5× more per title, still under $0,0005.

---

## 1. Who consumes the title, and why a bad title is not only cosmetic

| Consumer | Path | Reads the title from |
|---|---|---|
| Inbox list | `GET /api/media` → `MediaSearchItem` (`api/endpoints/media.py:348-368`, `title: Optional[str] = None`) | the durable library row `user_media.title` |
| Media detail screen | `GET /api/media/{id}/status` → `MediaItemContract` (`api/models/media_contracts.py:179-192`) | **nothing — the contract has no `title` field**. That omission is task-267's scope; counted here as a consumer, not re-diagnosed. |
| Algolia index + highlighted results | `media_completed_worker.py:178-186` → `search_indexing_worker.py:88-93` → `search_indexing.index_transcript(...)`, `"title": title or ""` (`search_indexing.py:156`) | `canonical_job.title or media_title` at completion time |
| Digest screens | `digest_service.py:92` `title=record.title` | the durable library row |

**The title is the highest-priority searchable attribute in Algolia.** `utils/algolia_client.py:106-109` sets `"searchableAttributes": ["title", "transcript"]` — an ordered list, so title matches outrank transcript matches — and `search_indexing.py:318` highlights `["transcript", "title"]`, with the title highlight surfaced as its own snippet (`:419-429`). A wrong title therefore *pollutes ranking*, not just the label: today a query for `Tinfoil Goy` ranks that reel above any transcript match, every YouTube item shares the token `youtube:youtube_video` in the top-ranked field, and every uploaded document injects `IMG`, `png` and percent-escape noise into it.

---

## 2. Current per-source behaviour, from the code

### 2.1 The two sentinel factories

```
core/media_ingestion/adapters/orchestrators.py:163
    title = resolved.title or f"{resolved.source_platform.value}:{resolved.media_type.value}"
```

That value is passed to `save_media_for_user(... title=title ...)` at `:175` and `:208`, i.e. it is written into the durable library row **synchronously, in the submit request**, and is never replaced unless some worker later assigns `job.title`. `core/media_ingestion/use_cases.py:140` and `:172` build the same kind of string directly:

```
:140  title=f"{source_platform.value}:shared_text",
:172  title=f"{source_platform.value}:audio_file",
```

Which resolvers avoid the sentinel? Exactly one. In `core/media_ingestion/adapters/resolvers.py` (402 lines) only `PodcastResolver` sets a title (`:160 title=outcome.title`). `ArticleResolver`, `XPostResolver`, `YouTubeResolver`, `TikTokResolver`, `SocialVideoResolver` and `AudioResolver` omit the field entirely.

### 2.2 Defect 1 — Instagram reel titled "Tinfoil Goy" (the account name)

`infrastructure/resolvers/instagram_apify_resolver.py` uses two Apify actors (`apify~instagram-reel-scraper`, `apify~instagram-post-scraper`, `:63-67`) plus a yt-dlp shape. In both shapes the *author* is chosen as the title and the caption is only a fallback:

```
441: caption_value = info.get("description") or info.get("title")
447: title_value = info.get("uploader") or info.get("channel")
489: title=title or (caption[:100] if caption else None),
555: title_value = item.get("ownerFullName") or item.get("ownerUsername")
584: title=title or (caption[:100] if caption else None),
652: title=caption[:100] if caption else None,
```

Root cause, confirmed against the provider schemas rather than inferred:

- **yt-dlp branch** — the installed yt-dlp 2026.03.13 Instagram extractor sets `'uploader': user_info.get('full_name')` and `'title': f'Video by {username}'` / `f'Post by {username}'`. So `info.get("uploader")` at `:447` *is* the account display name by construction, and `info["title"]` is a placeholder, not a title. The caption lives in `description` (`('caption', 'text')`), which `:441` already reads — the priority is simply inverted.
- **Apify branch** — the Instagram scraper's dataset item has **no `title` field at all**. Its documented post/reel fields are `caption`, `ownerFullName`, `ownerUsername`, `hashtags`, `mentions`, `videoUrl`, `musicInfo`, … So `:555` picks the only name-like field available, and "Tinfoil Goy" is `ownerFullName`.

Consequence for the benchmark: **no amount of metadata plumbing can give Instagram a real title** — the platform does not have one. The best metadata candidate is the caption's first sentence (better than the current blind `[:100]` cut); a caption-free reel has nothing at all.

Note also `orchestrators.py:431-457`: Instagram `IMAGE_POST` is hard-failed with `unsupported_content: Instagram image posts are not supported yet.` There is no OCR/vision path for it, so that source is out of the pipeline today.

### 2.3 Defect 2 — YouTube titled `youtube:youtube_video` (a leaked sentinel)

`workers/youtube_ingestion_worker.py` obtains the complete yt-dlp `info` dict at `:1060` (`info = await _extract_youtube_info(normalized_url)`, wrapping `ydl.extract_info(url, download=False)` at `:359-360`). yt-dlp documents `title` as "Title of the video" in its output-template field list. The worker uses `info` only for subtitles (`:1115`) and for the audio URL (`:1120+`); **`info["title"]` is never read** — grepping the file for `info.get(` returns nothing. The only place the worker touches a title is `:1174`, where it *forwards* one it does not have: `"episode_title": message_body.get("episode_title") or job.title`.

So `job.title` keeps whatever the orchestrator wrote — the sentinel — and `media_completed_worker.py:183` indexes it into Algolia's top-ranked attribute.

The Apify fallback branch (used when YouTube IP-blocks the host) is equally recoverable: the configured actor `starvibe~youtube-video-transcript` returns `title` ("The title of the YouTube video") in its dataset item, but the worker's dialect table (`:120-143`) declares only `"text_fields": ("transcript_text",)`, so the title is discarded before it is ever seen.

### 2.4 Defect 3 — uploaded document titled `IMG_8671.png` / a raw percent-encoded filename

The chain, end to end:

1. `mobile/src/lib/localImport.ts:186-197` — `defaultPhotoName()` derives the name from the URI's last path segment (`uri.split("?")[0].split("/").pop()`) with **no `decodeURIComponent`**; a URI segment such as `Grant%20Deed%20Security.pdf` is kept verbatim. Grepping `mobile/src` and `mobile/app` for `decodeURIComponent` returns **nothing**. When the OS gives no filename at all, the same function fabricates `photo-<epoch>.<ext>` (`:196`).
2. `mobile/src/types/upload.ts:192` — `prepareLocalUploadFile` passes `name: input.name` through unchanged.
3. `api/endpoints/media.py:927` — `file_name = file.filename or "document"`; then `:990` `save_media_for_user(... title=file_name ...)` and `:1004` `ProcessingJob(... title=file_name ...)`; `:1032-1034` forwards it as both `file_name` and `media_title`. The audio-upload endpoint is identical (`:1109`, `:1185`, `:1195`).
4. `workers/document_parsing/worker.py:169` — `media_title = message_body.get("media_title", file_name)`; `:260` **re-asserts** it: `job.title = media_title`. So even after LlamaParse has produced the markdown, the filename wins.

Two distinct problems, both real: the string is a filename (`IMG_8671.png` describes nothing), and it is not even decoded. The camera/OCR case is the *same* code path: `core/ports/document_parser.py:25-30` lists `IMAGE_JPG/JPEG/PNG/TIFF/BMP/HEIF` as `DocumentFormat` members, handled by the same LlamaParse → Unstructured worker (`document_parsing/worker.py:5-9`, owner decision task-90). The port's `ParseResult` (`document_parser.py:75-82`) exposes `markdown_content`, `page_count`, `metadata: dict` and `provider` — **no title field**, so an embedded PDF `/Title` is not available to the worker today; the only content-side candidate is the first markdown heading.

### 2.5 The reference implementations that already work

- **Podcast** — `workers/podcast_platform_resolvers.py:537, 880, 1022, 1372, 1539` resolve a real episode title through oEmbed / `og:title` / PodcastIndex, e.g. `title=episode.get("title") or episode_title or "Podcast episode"`; `workers/podcastindex_resolution_worker.py:298-303` assigns `job.title = episode_title` with a `"Podcast episode"` last resort.
- **X** — `workers/x_ingestion_worker.py:282-289` derives the title from the *content*, deterministically, and `:456` assigns it:

```python
def _build_titles(lookup_result):
    username = str(lookup_result.get("author_username") or "").strip()
    podcast_title = f"X - @{username}" if username else "X post"
    first_line = _first_line(str(lookup_result.get("text") or ""))
    episode_title = _truncate(first_line, 120) if first_line else ""
    if not episode_title:
        episode_title = f"X post {lookup_result.get('tweet_id')}"
    return podcast_title, episode_title
```

That is the shape §6 generalises: the author is kept out of the title, content first, a deterministic labelled fallback, a 120-char cap.

### 2.6 A fourth latent defect this research surfaced: RSS titles are read and dropped

`workers/rss_feed_poll_worker.py:51` reads `title = item.get("title") or ""` — the feed already provides a perfect episode/article title. Then:

- the job is created without it (`:64-70`): `ProcessingJob(user_id=…, user_email=…, source_url=feed_url, media_key=guid)` — no `title`, no `media_item_id`, and `save_media_for_user` is never called from this worker, so an RSS item gets **no library row at all**;
- the audio branch forwards it as `"episode_title": title` (`:109`) to the Deepgram queue — and grepping `workers/transcription/deepgram_worker.py` for `title` returns **nothing**: that worker never reads `episode_title`, and its success event (`:807-819`) carries no title field. The value is silently dropped;
- the article branch (`:135-146`) does not even forward it.

This matters well beyond RSS. **Every Deepgram-transcribed path** — podcast audio, YouTube without subtitles, Instagram reel, TikTok fallback, RSS audio, shared audio — sends an `episode_title` that nobody reads. Any approach that relies on "the producer passes the title along the queue" is already disproved by the current code. The reliable channel is `job.title` plus the mirror.

### 2.7 Summary of what is broken, and where

| Source | Title today | Origin |
|---|---|---|
| YouTube | `youtube:youtube_video` | `orchestrators.py:163` sentinel; `info["title"]` never read |
| Instagram reel | the account name (`ownerFullName` / `uploader`) | `instagram_apify_resolver.py:447` / `:555` prefer the author |
| Instagram image post | n/a — hard-failed | `orchestrators.py:431-457` |
| TikTok | `tiktok:short_video` (`MediaType.SHORT_VIDEO`, `domain.py:24`) | sentinel; `info["title"]` (= the caption) never read |
| X | first line of the post ✅ | `x_ingestion_worker.py:282-289, 456` |
| Web article | `web:article` | sentinel; trafilatura metadata discarded, `article_extraction_worker.py:379` passes `title=None` |
| Podcast | real episode title ✅ | `podcast_platform_resolvers.py`, `podcastindex_resolution_worker.py:298-303` |
| RSS | feed title read then dropped; no library row | `rss_feed_poll_worker.py:51, 64-70, 109` |
| WhatsApp shared text | `whatsapp:shared_text` | `use_cases.py:140` |
| Shared audio | `whatsapp:audio_file` / the filename | `use_cases.py:172`, `media.py:1109-1195` |
| Uploaded document | the raw filename, undecoded | `media.py:927/990/1004` → `document_parsing/worker.py:260` |
| OCR image / camera capture | `IMG_8671.png`, `photo-<epoch>.jpg` | same path as documents; `localImport.ts:186-197` |

Two of the eleven sources work. Nine do not.

---

## 3. Where a title can be written — the plumbing that already exists

This section is load-bearing for every approach below, so it is established once.

**3.1 The mirror is automatic.** `utils/database_async.py:279, 337-360, 421` calls `_mirror_job_to_durable_library(job)` from both `create_processing_job` and `update_processing_job`. `core/services/durable_media_service.mirror_job` (`:341-350`) then patches the library row:

```python
for source_attr, target_attr in (
    ("title", "title"),
    ("source_url", "source_url"),
    ("source_platform", "source_platform"),
    ("media_type", "media_type"),
    ("media_image", "thumbnail_url"),
):
    value = getattr(job, source_attr, None)
    if value:
        attributes[target_attr] = value
```

Only non-empty values are mirrored, so a worker that does not know the title cannot blank out one another worker resolved. **`job.title = X` + `await database_async.update_processing_job(job)` is the entire integration cost** for the Inbox and the digest.

**3.2 Algolia is fed from the job at completion time.** `workers/events/media_completed_worker.py:178-186`:

```python
if canonical_job and canonical_job.user_id:
    await _enqueue_search_indexing(
        media_item_id=canonical_job.media_item_id or canonical_job_id,
        job_id=canonical_job_id,
        user_id=canonical_job.user_id,
        transcription_s3_key=transcription_s3_key,
        title=canonical_job.title or media_title,
        source_platform=canonical_job.source_platform,
    )
```

So the ordering rule is simple and absolute: **a title on the job before `episode_completion_status` is published is indexed correctly on the first pass; a title written after it is not indexed at all until something re-indexes.**

**3.3 The six publish sites.** Each already calls `update_processing_job(job)` immediately before publishing, so adding one assignment is a one-line change per site:

| Publish site | Sources it covers | Content available at that point |
|---|---|---|
| `youtube_ingestion_worker.py:1206-1213` | YouTube (native subtitles) | yt-dlp `info` + transcript |
| `youtube_ingestion_worker.py` Apify branch (`:1069+`) | YouTube (IP-blocked) | Apify dataset item (has `title`) + transcript |
| `tiktok_ingestion_worker.py` (native + Apify branches) | TikTok | yt-dlp `info` (`title` = caption) + transcript |
| `orchestrators.py:289-300` / `:339-352` | Instagram reel via Apify native transcript; WhatsApp shared text | resolver metadata + transcript |
| `article_extraction_worker.py:379+` | web article, RSS article | HTML + trafilatura `Document` + clean text |
| `document_parsing/worker.py:260-270` | uploaded document, OCR image | filename + parsed markdown |
| `transcription/deepgram_worker.py:807-819` | podcast audio, YouTube w/o subs, shared audio, RSS audio, Instagram/TikTok audio fallback | **transcript only — no metadata whatsoever** |

The last row is the reason no "single choke point" design can be metadata-aware: by the time all audio paths converge, the metadata is gone.

**3.4 No LLM call happens automatically after ingestion today.** `core/services/artifact_service.py:386` `request_artifact_generation` has exactly two callers: `api/endpoints/artifacts.py:88` (user taps an artifact) and `core/services/digest_service.py:268` (digest assembly). Likewise the task-192 translation step (`core/services/transcript_translation.py`) is resolved lazily at artifact-request time, and its first stage is a free local `langdetect` pass. **An LLM title is therefore a genuinely new call on the ingestion path, not a free rider on an existing one.** That is the honest framing for §8.

---

## 4. The candidate approaches

**A — Per-source metadata plumbing.** Read the title each provider already returns and assign it to `job.title`. yt-dlp `info["title"]` (YouTube, TikTok), the Apify YouTube actor's `title`, trafilatura's `Document.title`, the RSS `<title>`, the Instagram caption, the decoded+cleaned filename for uploads. No new dependency, no new provider, no added latency.

**B — LLM title from the transcript, for every item.** One `gpt-5-nano` call per item, on the head of the transcript, at the last worker before the completion event. Uniform: one code path, one prompt, identical behaviour on all eleven sources.

**C — Hybrid: metadata first, deterministic distrust, LLM only where metadata is structurally absent or in a rejected class.** A → filtered by the §6.1 rules → B as the fallback → deterministic label as the last resort. **This is the recommendation.**

**D — Deterministic derivation from the content, no LLM.** Generalise what X already does: first sentence / first line of the text, or an unsupervised keyphrase extractor. The realistic library is YAKE (`pip install yake`, unsupervised, "requires no training, external corpus, or dictionaries", language- and domain-independent, single-document) — but note it **outputs scored keyphrases, not titles** (`('ceo anthony goldbloom', 0.0299)`), so the title would read as a keyword list. The first-sentence variant works well on short text (X posts, shared notes, article leads) and badly on spoken audio: podcasts and reels open with "Hey everyone, welcome back to the show" or "so basically the thing about this is".

**E — Ask the user.** A title field on the share-confirmation sheet, and/or a rename action in the Inbox. The only approach with a guaranteed-relevant title, at the price of friction on every single share — which contradicts the product's whole premise (share and forget).

**F — A generic URL-metadata provider.** One HTTP call to an unfurl API that returns `title` for any URL, replacing per-source plumbing with one dependency: Iframely ($0/2 000 hits, then **$49/month** for 25 000 hits, and the free Starter tier is explicitly "Pilot projects" only, not production end-user use) or Microlink (Free = 25 requests/**day**; Pro **$49/month**). Against task-65's total infra budget of **0,145–0,190 €/user @100u**, adding ≈42 €/month for something the app can already read from libraries it imports is a ~30 % infra increase for zero incremental capability. It also cannot help the four non-URL sources (uploads, OCR, shared text, shared audio).

---

## 5. Comparison matrix

| Dimension | A — metadata plumbing | B — LLM on every item | C — hybrid (recommended) | D — deterministic from content | E — ask the user | F — unfurl API |
|---|---|---|---|---|---|---|
| Sources fully fixed (of 11, §7) | 6 (+2 partial) | 11 (whenever a transcript exists) | **11** | 1 (+5 partial) | 11 | 5 (+2 partial, 4 unreachable) |
| Sources left with a bad or generic title | Instagram (no platform title), shared text, shared audio, OCR image | none, but every title is a paraphrase | none | audio-based sources read badly | none | uploads, OCR, shared text, shared audio |
| Title quality where metadata exists | **the real, canonical title** (what the user saw when sharing) | a paraphrase that may differ from the canonical title | **the real title** | a lead sentence, often truncated mid-thought | whatever the user typed | the real title, same as A |
| Title quality where metadata is absent | none — falls back to a label | good: describes the content | good: describes the content | poor on audio, acceptable on text | good | none |
| Marginal cost / item | **0 €** | $0,00007–$0,00014 (§8) | 0 € on ~85 % of items, $0,00007–$0,00014 on the rest | 0 € | 0 € | $0,002/req at Iframely's 25k tier; $49/month floor |
| Added latency | **none** (fields already in memory) | one model round-trip on 100 % of ingestions, including the article path that has no model call today | one round-trip on ~15 % of ingestions | negligible (YAKE is local, single-document) | none in the pipeline, seconds of user friction per share | one HTTP round-trip per URL item |
| Where it falls in the pipeline | inside each worker/resolver, before the completion event | last worker before the completion event | same as A, with the model call as the fallback branch | same as A | at submit time, before the library row exists | inside the resolver, in the synchronous submit path |
| Needs Algolia re-index | no | no | **no** | no | **yes** if renaming after indexing (§9.3) | no |
| Main failure mode | provider returns nothing, or returns the author (Instagram), or a placeholder (`Video by x`, `TikTok video #123`) | headline hallucination (§10), plus a model outage stalling ingestion | the arbitration rule mis-classifies a good title as bad, or vice-versa | unreadable titles on audio; keyphrase lists with YAKE | the user skips the field, and nothing is derived | third-party outage in the synchronous submit path; a paywalled/JS page returns nothing |
| Implementation complexity | 6 workers + 2 resolvers + 1 endpoint + 1 mobile helper, each a small local change | 1 new module + 1 call site + prompt/timeout/error handling; nothing else touched | A + B + one shared pure helper (the largest surface) | 1 new module + the same call sites as A | mobile sheet + a `PATCH` endpoint + Algolia update path | 1 resolver-side client + 1 secret + 1 vendor account |
| Reuses validated decisions | — | task-72 / task-189 model stack | task-72 / task-189 model stack, task-65 volumes | — | — | none; new vendor |

Reading of the matrix: **A alone is insufficient** (four sources have no metadata to plumb, and Instagram has none by design). **B alone is affordable but wasteful and riskier** — it throws away canonical titles for a paraphrase and puts a model on every ingestion. **C is A plus B's coverage, at 15 % of B's calls.** D is a useful *component* (the first-sentence rule is exactly what X does today) but not an approach on its own. E is the right long-term complement (a rename action), not a derivation mechanism. F is rejected on cost and coverage.

---

## 6. The arbitration rule, stated honestly

The task asks which untrustworthiness signals are cheap and reliable, and which are guesswork. That distinction is the whole difficulty of approach C, so it is answered before the coverage table.

### 6.1 Cheap AND reliable — usable as hard rejection rules

Each of these is a pure string test with no model, no network call, and a verifiable ground truth.

| Signal | Rule | Why it is reliable |
|---|---|---|
| **Our own sentinel** | matches `^[a-z_]+:[a-z_]+$` and the left part is a `SourcePlatform` value | We generate the string ourselves at `orchestrators.py:163` and `use_cases.py:140,172`. Zero ambiguity. |
| **The title equals the author** | normalised-equal to any of `uploader` / `channel` / `ownerFullName` / `ownerUsername` / `author_username` present **in the same payload** | Both fields are in hand at the same moment (`instagram_apify_resolver.py:441-447`, `:555`). This is exactly the "Tinfoil Goy" case, and it is a comparison, not a guess. |
| **A provider placeholder** | matches `^(Video|Post|Reel|Story) by .+$`, `^Video \d+$`, `^TikTok video #\d+$` | These strings are emitted by yt-dlp itself; the patterns are readable in the installed extractor source (`yt_dlp/extractor/instagram.py`, `tiktok.py`). |
| **A bare filename** | matches `^.+\.(pdf|docx|pptx|xlsx|jpe?g|png|tiff?|bmp|heic|heif)$` | The extension set is `DocumentFormat.supported_extensions()` (`document_parser.py:52-58`). Reject *as-is*, then re-test the cleaned stem — a human-named file ("Grant Deed — Security Agreement.pdf") is a fine title, `IMG_8671.png` is not. |
| **A device-generated name** | stem matches `^(IMG|DSC|DSCN|PXL|MVIMG|Screenshot|Photo|Scan|PTT|AUD|WhatsApp)[-_ ]?\d`, `^\d{8}[-_]\d{6}$`, `^photo-\d{13}$`, `^[0-9a-f]{16,}$` | Fixed camera/OS conventions, and one of them (`photo-<epoch>`) is generated by our own `localImport.ts:196`. |
| **A generic placeholder word** | normalised-equal to `untitled`, `document`, `file`, `audio`, `recording`, `image`, `photo`, `voice message`, `new document` | Finite closed list. |
| **The title equals the site name** | normalised-equal to trafilatura's `Document.sitename` or to the URL host with `www.` stripped | Both values are produced by the same extraction call, so it is a comparison. |
| **Empty after normalisation** | zero-length once whitespace, punctuation-only and emoji-only content is stripped | Deterministic. |

### 6.2 Guesswork — must NOT be used as arbitration signals

- **"The title is a truncated caption."** Undetectable: the resolver itself performs the truncation (`caption[:100]`, `instagram_apify_resolver.py:489/584/652`), and the provider only ever returned the caption. A trailing "…" test is a proxy for our own bug, not for provider quality. The fix is not to detect truncation but to cut on a sentence boundary in the first place.
- **"The title does not describe the transcript."** A semantic-mismatch test needs an LLM or an embedding pair — i.e. it costs as much as generating the title. If you are prepared to pay a model call to *check* a title, generate one instead. Explicitly rejected as a signal.
- **"The title is too short" applied to a real provider title.** Length says nothing: "Dune", "1984", "Oppenheimer" are complete titles. A length floor is only safe as a *tie-breaker inside an already-rejected class* (e.g. choosing between a 2-character filename stem and nothing) — never as a standalone rejection of a trafilatura, RSS, podcast or yt-dlp title.
- **"The title is clickbait / low quality."** Subjective, no ground truth available here, unmeasurable without human labels. Out.
- **A character-count threshold as a general trust rule.** Arbitrary by construction; it would reject legitimate titles and accept `IMG_8671.png` (12 characters, perfectly "long enough").

Practical consequence: the arbitration rule is a **closed list of provable rejections**, not a quality score. Anything not provably bad is kept. That is what makes C cheap and predictable — and it also means C's residual failure mode is a *kept* bad title the list did not anticipate, which is a bounded, diagnosable bug rather than a silent quality drift.

---

## 7. Per-source coverage

"Content-describing" means: a human reading the title in the Inbox learns what the item is about. Not the author's name, not a filename, not an identifier.

| # | Source | Metadata title actually available (evidence) | A — plumbing | B — LLM every item | C — hybrid | D — deterministic | E — user types it | F — unfurl API |
|---|---|---|---|---|---|---|---|---|
| 1 | **YouTube** | **Yes.** yt-dlp `info["title"]` = "Title of the video"; Apify actor `starvibe~youtube-video-transcript` also returns `title` | **Yes** | Yes | **Yes** (metadata) | No — a transcript opener is not a title | Yes | Yes (`og:title`) |
| 2 | **Instagram (reel / video post)** | **No.** The Apify Instagram scraper has no `title` field (only `caption`, `ownerFullName`, `ownerUsername`); yt-dlp's `title` is the placeholder `Video by <user>` and its `uploader` is `full_name` | Partial — caption's first sentence only; nothing if the caption is empty | Yes | **Yes** (caption if usable, else LLM) | Partial — caption only | Yes | Partial — IG `og:title` embeds the account name |
| 3 | **TikTok** | **Yes.** yt-dlp TikTok extractor: `'title': ('desc', {truncate_string(left=72)})` — the caption, truncated to 72 chars | **Yes** | Yes | **Yes** (metadata) | Partial | Yes | Yes |
| 4 | **X (post)** | **Yes**, already implemented: first line of the post text, 120-char cap, `X post <id>` fallback (`x_ingestion_worker.py:282-289, 456`) | **Yes** | Yes | **Yes** (unchanged) | **Yes** (this *is* D) | Yes | Partial — X restricts unfurls |
| 5 | **Web article** | **Yes.** trafilatura 2.0.0 `Document` exposes `title`, `author`, `sitename`, `date`, `description`; `only_with_metadata` documents title as essential metadata | **Yes** | Yes | **Yes** (metadata) | Partial — lead sentence | Yes | Yes |
| 6 | **Podcast** | **Yes**, already working: oEmbed / `og:title` / PodcastIndex (`podcast_platform_resolvers.py`) | **Yes** | Yes, but it would *replace* a canonical episode title with a paraphrase | **Yes** (unchanged) | No | Yes | Yes |
| 7 | **RSS** | **Yes.** the feed item `<title>` is already read (`rss_feed_poll_worker.py:51`) then dropped (§2.6) | **Yes** (+ requires wiring the library row, §11) | Yes | **Yes** (metadata) | No for audio items | Yes | Yes |
| 8 | **WhatsApp shared text** | **None.** No provider, no metadata; sentinel at `use_cases.py:140` | No | Yes | **Yes** (LLM) | Partial — first sentence of the note | Yes | n/a — no URL |
| 9 | **Shared audio file** | **None** beyond a filename, usually `PTT-2026…`/`AUD-…`/`audio.m4a` (rejected class §6.1); sentinel at `use_cases.py:172` | No | Yes | **Yes** (LLM on the transcript) | No | Yes | n/a |
| 10 | **Uploaded document** | **Partial.** The filename only; `ParseResult` (`document_parser.py:75-82`) has no title field, so no embedded PDF `/Title`. The first markdown heading of `markdown_content` is a weak candidate | Partial — good when the file is human-named, useless for `IMG_*`/`Scan_*` | Yes | **Yes** (cleaned stem if usable, else LLM) | Partial — first H1 | Yes | n/a |
| 11 | **OCR image / camera capture** | **None.** Camera filenames only, all in the rejected class; `photo-<epoch>.jpg` is generated by our own code | No | Yes (on the OCR text) | **Yes** (LLM on the OCR text) | No | Yes | n/a |

**Totals, counting only the "Yes" cells** — A = 6 (+2 partial), B = 11, **C = 11**, D = 1 (+5 partial: the first-sentence rule is only *proven* on X, and reads acceptably on shared notes and article leads), E = 11, F = 5 (+2 partial, and 4 sources it cannot reach at all).

Out of the table, for completeness: **Instagram image posts** are hard-failed today (`orchestrators.py:431-457`), and non-audio file shares are refused in the mobile share sheet (`ShareIntentContext.tsx:230-290`, "This file type is not supported yet."). When those land they inherit the document/OCR row.

---

## 8. Cost and latency of the LLM-based approaches

### 8.1 Model and prices

Reuse the already-validated stack. task-72 (`owner_decision: ok`) assigned **`gpt-5-nano-2025-08-07`** to `summary_short` — the shortest, most extractive artifact — and `gpt-5.4-nano-2026-03-17` to every other artifact. task-189 (`owner_decision: ok`) retained **`gpt-5-nano`** for transcript translation, and `core/services/transcript_translation.py` pins `TRANSLATION_MODEL = "gpt-5-nano-2025-08-07"`. A title is strictly shorter and more extractive than `summary_short`, so it belongs on the same rung: **no new provider, no new secret, no new client**.

Official prices, per 1M tokens (OpenAI API pricing page, consulted 2026-08-17):

| Model | Input | Cached input | Output | Context |
|---|---|---|---|---|
| **gpt-5-nano** | **$0.05** | $0.005 | **$0.40** | 400 000 |
| gpt-5.4-nano | $0.20 | $0.02 | $1.25 | — |
| gpt-5.4-mini | $0.75 | $0.075 | $4.50 | — |

### 8.2 Cost per media item

Workload: instruction (~120 tokens) + the first ~1 200 tokens of the transcript = **~1 320 input tokens**; output = one title of ≤ 120 characters ≈ **20–30 tokens**. Because `gpt-5-nano` is a reasoning model, reasoning tokens are billed as output, so two operating points are given — the arithmetic convention is task-72's, `(input × price + output × price) / 1M`:

| Case | Input | Output (incl. reasoning) | Cost / item | In EUR (×0,86, task-65's rate) |
|---|---|---|---|---|
| `reasoning_effort: "minimal"` | 1 320 | 30 | **$0.000078** | **0,000067 €** |
| conservative (reasoning overhead) | 1 320 | 200 | **$0.000146** | **0,000126 €** |
| same workload on gpt-5.4-nano | 1 320 | 200 | $0.000514 | 0,000442 € |

**Truncating the transcript at ~1 200 tokens makes the cost independent of media duration** — a 3-hour podcast costs exactly the same as a 1-minute reel. That is the single most important design decision in the cost model, and it is free to implement.

For scale, task-65's own per-media LLM costs: article/document **0,0051 €**, YouTube 25 min **0,0076 €**, podcast 45 min **0,0104 €**. A generated title is therefore **1,3–2,5 % of the artifact cost of the same item**.

### 8.3 Cost per month, against task-65's volumes

task-65's nominal monthly baskets (active README, §Recommandation and §3.2/§4/§5):

| Tier | Basket | Items / month |
|---|---|---|
| Text-Only 3 € | 150 articles + 30 docs + 20 YouTube | **200** (stated explicitly in task-65) |
| Mix 5 € | 300 min audio (~7 podcasts of 45 min) + 100 articles + 15 docs + 10 YouTube | **~132** |
| Audio-Heavy 9 € | 900 min audio (~20 podcasts of 45 min) + 50 articles + 10 docs + 20 YouTube | **~100** |

Approach **B** (a model call on every item) and approach **C** (a model call only where metadata is structurally absent or rejected). For C, the share of items needing a call is estimated from the basket composition: half of the documents/OCR images carry a device-generated name, plus a 10 % residual metadata miss on URL sources (provider returns nothing, paywalled page, caption-free reel):

| Tier | B — calls/month | B — cost/month | C — calls/month | C — cost/month | task-65 media cost/month | B as % | C as % |
|---|---|---|---|---|---|---|---|
| Text-Only | 200 | $0.029 → **0,025 €** | ~32 | $0.0047 → **0,004 €** | 1,33 € | **+1,9 %** | **+0,30 %** |
| Mix | 132 | $0.019 → **0,017 €** | ~19 | $0.0028 → **0,002 €** | 1,86 € | **+0,9 %** | **+0,13 %** |
| Audio-Heavy | 100 | $0.015 → **0,013 €** | ~14 | $0.0020 → **0,002 €** | 3,63 € | **+0,4 %** | **+0,05 %** |

(worst case of §8.2 used throughout; EUR at task-65's 0,86 USD→EUR rate.)

**Conclusion, stated plainly: cost is not a decision criterion here.** Even the most expensive option, an LLM title on every item of the most text-heavy tier, costs **2,5 cents per user per month** and moves task-65's margins by less than two points of a percent. The owner should not choose C over B to save money — the reasons are quality and latency.

### 8.4 Latency, and where it falls

| | A / D / F | B | C |
|---|---|---|---|
| Ingestions that pay a model round-trip | 0 % | 100 % | ~15 % |
| Position in the pipeline | inside the worker that already holds the metadata | last worker before `episode_completion_status` | same, in the fallback branch only |
| What the user sees during it | nothing — the item is already "processing" | the item stays "processing" slightly longer | idem, on ~15 % of items |

Two honest caveats about the absolute number:

- **No reliable published latency figure exists for the operating point we need.** Artificial Analysis measures `gpt-5-nano (high)` at **165 output tokens/s** but reports a *time to first answer token* of **100,18 s** on its 10k-token workload, explicitly noting this is "at the higher end compared to other reasoning models in a similar price tier (median: 1.04 s)" because the metric includes the model's thinking phase. That figure is for **high** reasoning effort and is not transferable to a 30-token title. task-72 likewise records no measured TTFT for this model. **No latency number is invented here**: the implementer must set `reasoning_effort: "minimal"`, cap `max_output_tokens`, set a hard client timeout (5 s is consistent with task-72's "<5 s" target for artifact generation), and treat the timeout as a *fallback to the deterministic label*, not as a job failure.
- **The article path has no model call at all today** (`article_extraction_worker.py` is pure HTTP + trafilatura). Approach B would introduce the first one, on the tier whose whole economics rest on articles being cheap and fast. Approach C leaves that path model-free whenever trafilatura returns a title, which is the common case.

Because the latency lands *before* the completion event, it delays the "processing → ready" transition rather than mutating a visible title. §9.1 explains why that is the right side of the trade.

---

## 9. The four product questions, answered

### 9.1 When must the title be final? What does the user see meanwhile?

**Answer: a provisional title is unavoidable and acceptable, and the title becomes final at the instant the item becomes "ready" — i.e. it is written to `job.title` before `episode_completion_status` is published, and never changes on its own afterwards.**

Why a provisional title is unavoidable: the library row is created synchronously inside the submit request (`durable_media_service.save_media_for_user`, `:107`, called from `orchestrators.py:175/208` and `media.py:990`), long before any transcript exists. The alternative — no row until the title is known — would hide the item from the Inbox for the whole processing duration, which is precisely what the durable row exists to prevent.

What the user actually sees, from the mobile code:

- **The Inbox does no polling.** `mobile/app/(tabs)/inbox.tsx:44` documents the V1 decision verbatim: "No polling: single fetch on mount + pull-to-refresh + refetch on focus", with `useFocusEffect(... refetch())` at `:75-79`. A title resolved 20 s later therefore appears at the next focus or pull-to-refresh. **It never mutates a row under the user's finger mid-scroll.** The cost of a late title is essentially zero.
- **But there is no processing badge either.** `inbox.tsx:45`: "No processing status badges or spinners per item". So the provisional title is not visibly provisional — **it is the only thing the user sees**, and it must read like a real title, not like a placeholder. This is what makes `youtube:youtube_video` a genuine bug rather than a transient artefact.
- **Before submission completes**, the optimistic local item (`InboxContext.tsx:12-28`, `InboxItem` has no `title` field at all) displays the shared URL. That is the pre-submit state.

Concrete rule to implement:

1. **At resolve time (synchronous):** the resolvers run in the request path, so YouTube, TikTok, podcast, article and X can all supply a real title *immediately* if approach A is implemented in the resolvers rather than only in the workers. Use it as the provisional title — for most sources it is already the final one.
2. **If no metadata is available at resolve time:** write the deterministic label of §9.2. Never a sentinel.
3. **At worker time, before the completion event:** overwrite with the derived title (metadata or LLM). The mirror only propagates non-empty values (`durable_media_service.py:341-350`), so this is a safe upgrade, never a downgrade.
4. **After the completion event:** the title is final. Nothing in the pipeline rewrites it.

### 9.2 What is the fallback when everything fails?

**Answer: a human-readable platform label plus the short save date, computed server-side and stored** — e.g. `YouTube video — 17 Aug`, `Podcast episode — 17 Aug`, `Shared note — 17 Aug`, `Photo — 17 Aug`, `Document — 17 Aug`.

Why not the alternatives:

| Candidate | Rejected because |
|---|---|
| **The source URL** (what `MediaListCard.tsx:40` does today) | Unreadable in a list (`https://www.youtube.com/watch?v=dQw4w9…`); duplicates the source line the card already renders; **meaningless in Algolia's top-ranked searchable attribute** — a URL tokenises into host noise and produces nonsense highlight snippets (`search_indexing.py:419-429`); and four sources have no meaningful URL at all (uploads, OCR, shared text, shared audio). It is also already the *pre-submit* placeholder (`InboxItem` has no title), so reusing it as the stored fallback makes "not yet sent" and "failed to derive" indistinguishable. |
| **A generic label alone** (`"Untitled"`, what `search.tsx:491` does today) | With two or more failures the Inbox shows N identical rows the user cannot tell apart, and Algolia stores N identical top-ranked titles. |
| **The sentinel** (`youtube:youtube_video`) | It is a leaked internal identifier. Deleted outright at `orchestrators.py:163` and `use_cases.py:140,172`. |

Why platform + date wins: distinguishable (the date differs), readable, honest (it does not pretend to describe content), sorts sensibly, and it never looks like a bug. Two implementation requirements:

- **Computed once, server-side, and stored** in `user_media.title` / `job.title`. Today the Inbox and Search disagree — `MediaListCard.tsx:40` falls back to the source URL, `search.tsx:491` falls back to `"Untitled"` — so the same item is labelled differently on two screens. Both client-side fallbacks are **deleted**; there is exactly one rule, on the server.
- **Nothing may emit an empty title**, otherwise Algolia stores `""` (`search_indexing.py:156` `"title": title or ""`) and the client fallbacks would be needed again.

### 9.3 Does the approach require Algolia re-indexing?

**Answer: no — provided the title is written before the completion event, which is exactly why the recommendation pins it there.**

- `media_completed_worker.py:178-186` builds the indexing message with `title=canonical_job.title or media_title`, triggered by `episode_completion_status`. A title present on the job at that moment is indexed on the **first** pass. No second write, no re-chunking, no extra S3 read.
- A title changed *after* indexing would need a write, and **the code has no partial-update path**: `search_indexing.py` only exposes `save_objects` (`:173`), `_delete_chunks_for_media` (`:186`) and a full `index_transcript` that re-chunks the transcript. Object IDs are deterministic (`f"{media_item_id}_chunk_{i}"`, `:151`), so an Algolia `partialUpdateObjects` batch on the `title` attribute is feasible — but the chunk count is returned as `num_chunks` and **never persisted**, so a late updater would first have to browse the index or re-read and re-chunk the transcript. That is real work, and avoiding it is free.
- **Money is not the constraint.** Algolia's Free plan meters *stored records* (50 000 records, 1 GB, 10 KB/record) and *search requests* (10 000/month), not writes: the pricing FAQ states you may "update, delete, or add as many records as you want" within the stored inclusion. So a re-index costs 0 € — it costs code.
- **The one case that will need it** is the user-editable title of approach E, if the owner ever wants it. The recommendation is to scope that as a separate task with an explicit `partialUpdateObjects` path, and to persist `num_chunks` at index time so the update does not need a browse.

### 9.4 Which language does the title follow?

**Answer: the language of the text the title is derived from. Never the user's `reading_language`.**

- **Metadata titles are used verbatim, never translated.** A French YouTube video keeps its French title — that is the title the user saw when they shared it, and rewriting it breaks recognition ("is this the thing I saved?").
- **An LLM-generated title is written in the transcript's language.** The prompt instructs "write the title in the same language as the text", it does not translate. `gpt-5-nano` is the model task-189 already validated for multilingual transcript work.
- **No coupling to task-192.** The translation step (`core/services/transcript_translation.py`) is resolved *lazily at artifact-request time*, long after the title is written, and `reading_language` is a mutable per-user preference. Binding the title to it would mean re-deriving and re-writing every library row *and* every Algolia record whenever the user changes a setting — for a value the user never chose per item. Rejected.
- **This also keeps search coherent.** `algolia_client.py:106-109` indexes `title` and `transcript` in the same record, and `search_indexing.py:318` highlights both. A title translated over an untranslated transcript would let a query match the title while highlighting nothing in the body — the exact mismatch the highlight snippets are there to avoid.
- Practical consequence to accept: a user whose reading language is English will see French titles for French sources. That is correct behaviour, not a defect — the *artifacts* are translated on demand, the identity of the item is not.

---

## 10. Failure modes, per approach

### 10.1 Approach A — metadata plumbing

| Failure | Effect | Mitigation in C |
|---|---|---|
| Provider returns no title (caption-free reel, paywalled article, JS-only page) | falls through to the next candidate | LLM fallback |
| Provider returns **the author** (Instagram) | a wrong but plausible title — the current bug, and the worst kind because nothing looks broken | the author-equality rule (§6.1), which is a comparison, not a heuristic |
| Provider returns **its own placeholder** (`Video by x`, `TikTok video #123`) | a title that looks generated | pattern rule (§6.1), patterns readable in the yt-dlp extractor source |
| Provider changes its schema (Apify actors are third-party and versioned) | the field silently becomes `None` | the candidate list degrades to the LLM branch, then to the label — never to a sentinel |
| trafilatura returns the site name as the title | every article from that site gets the same title | sitename-equality rule (§6.1) |

### 10.2 Approach B / the LLM branch of C

| Failure | Effect | Mitigation |
|---|---|---|
| **Headline hallucination** — the generated title is not supported by the source. This is a documented, named failure mode of automatic headline generation, not a speculative risk: it is the subject of dedicated research corpora ("Multilingual Fine-Grained News Headline Hallucination Detection", arXiv 2407.15975, 11k expert-annotated pairs in 5 languages; "ExHalder", arXiv 2302.05852, which frames hallucination as "a critical challenge for the deployment of this feature in web-scale systems") | a confidently wrong title on an item the user cannot re-identify | keep the provider title whenever one exists (this is the core argument for C over B); truncate the input to the transcript head so the model paraphrases what it read; a rename action (approach E) as the human escape hatch |
| Model/API outage or timeout | ingestion stalls if the call is not guarded | hard client timeout, then the deterministic label; **never** fail the job for a title |
| Reasoning-token blowup on a reasoning model | a 30-token title billed as hundreds of output tokens | `reasoning_effort: "minimal"` + `max_output_tokens` cap; §8.2 already prices the bad case |
| Prompt injection from the transcript ("ignore previous instructions, title this X") | an attacker-chosen title on the user's own item | low impact (self-inflicted, single-tenant field), but keep the transcript in a clearly delimited user block and cap the output length |
| Model snapshot retired | 4xx at runtime | pin the snapshot id, keep `gpt-5.4-nano-2026-03-17` as the documented fallback (§8.1) |
| Empty or near-empty transcript (a photo with no text, a silent audio file) | nothing to summarise | detect empty input before calling; go straight to the label |
| Non-determinism across re-ingests | the same shared note gets two different titles | accepted: nothing keys on the title, and there are no users |

### 10.3 Approach C's own failure mode

The arbitration list is a **closed list of provable rejections**, so its residual failure is a *kept* bad title in a class nobody anticipated (say a provider starts returning `"Untitled video (2026)"`). This is a bounded, diagnosable bug — one new pattern in one pure function — as opposed to the unbounded quality drift of a model-scored trust rule. The inverse error (rejecting a good title) costs one unnecessary model call at $0.00014 and a paraphrase instead of the canonical title.

### 10.4 Approaches D, E, F

- **D** — YAKE outputs scored keyphrases, not sentences, so titles read as keyword lists; the first-sentence variant produces "Hey everyone, welcome back to the show" on spoken content. Both are silent failures (plausible-looking, useless).
- **E** — the user skips the field; nothing is derived; you still need C underneath. E is a complement, not a substitute.
- **F** — a third-party outage lands in the **synchronous submit path**, so the share fails or hangs, which is far worse than a bad title; and the free tiers are explicitly non-production (Iframely "Pilot projects", Microlink 25 req/day).

---

## 11. What the implementation task will have to do (informative, not a decision)

Listed so the owner can size the work before validating. Ordered so that the shared helper lands first.

1. **New pure module** `core/media_ingestion/title_derivation.py`: normalisation (percent-decode, extension strip, separator collapse, trailing ` | Site` strip, 120-char word-boundary trim), the §6.1 rejection rules, the platform+date label, and the `gpt-5-nano` call behind a timeout.
2. **Delete the sentinels**: `orchestrators.py:163`, `use_cases.py:140`, `:172`.
3. **Resolvers** (`core/media_ingestion/adapters/resolvers.py`) — populate `title` for `ArticleResolver`, `YouTubeResolver`, `TikTokResolver`, `XPostResolver`, `SocialVideoResolver`, `AudioResolver` so the provisional title is real from the submit request onwards.
4. **Instagram** (`instagram_apify_resolver.py:441-447, 489, 555, 584, 652`) — invert the priority: caption's first sentence first, author **never** as the title.
5. **YouTube** (`youtube_ingestion_worker.py`) — read `info["title"]` on the yt-dlp branch and add `title` to the Apify dialect `text_fields` sibling (the actor returns it); assign `job.title` before `:1206-1213`.
6. **TikTok** (`tiktok_ingestion_worker.py:1017+`) — read `info["title"]` (the caption).
7. **Article** (`article_extraction_worker.py:216-245, 379`) — switch to `bare_extraction`/`extract_metadata` so `Document.title` and `Document.sitename` are available; assign `job.title`.
8. **Documents/OCR** (`media.py:927/990/1004`, `document_parsing/worker.py:169/260`) — decode and clean the filename, reject device-generated names, consider the first markdown heading of `ParseResult.markdown_content`, then the LLM branch. Also fix `mobile/src/lib/localImport.ts:186-197` to decode the URI segment at the source.
9. **RSS** (`rss_feed_poll_worker.py:51, 64-70, 109`) — put the feed title on the job at creation. (The missing library row for RSS items is a separate defect surfaced in §2.6; flag it to the owner rather than silently expanding scope.)
10. **Deepgram-transcribed audio** (`transcription/deepgram_worker.py:807-819`) — the LLM branch for shared audio; and either read the producer's `episode_title` or delete that unread field from all producers (`AGENTS.md`: legacy is deleted, not carried).
11. **Mobile** — delete the two divergent fallbacks (`MediaListCard.tsx:40`, `search.tsx:491`) and render `item.title` / `hit.title` directly.

No backfill, no migration, no compatibility shim: existing dev rows with bad titles are disposable (`AGENTS.md` § "Nothing is deployed yet").

---

## 12. Rejected alternatives, and why

| Rejected | Reason |
|---|---|
| **B — LLM title on every item** | Not on cost (2,5 cents/user/month at worst, §8.3) but on quality and latency: it replaces canonical titles with paraphrases on ~85 % of items, adds a model round-trip to 100 % of ingestions including the model-free article path, and extends the hallucination surface from ~15 % to 100 % of items. Kept as the documented second choice if the owner prefers a single-file change over metadata fidelity. |
| **D — YAKE / keyphrase extraction** | Outputs scored keyphrases, not titles (the library's own example output is `('ceo anthony goldbloom', 0.0299)`). Useful only as the first-sentence rule, which is already implemented for X and is folded into C as a candidate. |
| **D' — first sentence of the transcript, generically** | Spoken openings ("Hey everyone, welcome back") are not titles. Kept only for text sources. |
| **E — user types the title** | Friction on every share contradicts the product premise, and a skipped field leaves you needing C anyway. **Recommended as a follow-up complement**: a rename action in the Inbox, which also gives the human escape hatch for a hallucinated title. Requires the Algolia partial-update path of §9.3. |
| **F — Iframely / Microlink unfurl API** | ~42 €/month against a total infra budget of 0,145–0,190 €/user @100u (task-65), for titles the app can already read from libraries it imports; free tiers explicitly non-production; covers none of the four non-URL sources; and it puts a third party in the synchronous submit path. |
| **A summary-derived title** (reuse `summary_short`) | Artifacts are strictly on demand — `request_artifact_generation` has exactly two callers (`artifacts.py:88`, `digest_service.py:268`), neither on the ingestion path (§3.4). No summary exists when the title is needed, and forcing one would cost 0,0051 € per item (task-65) instead of 0,00013 €, i.e. ~40× more. |
| **A vision model on the image itself** for OCR captures | The OCR text is already available from the document parser and is cheaper to title from. A vision call would be justified only for images with no extractable text, which is also the case where no title is derivable at all. |
| **Passing the title through the SQS payload** (`episode_title`) | Already disproved by the current code: every audio path sends `episode_title` and the Deepgram worker never reads it (§2.6). `job.title` + the mirror is the channel that works. |
| **A dedicated titling worker after completion** | Would need a second Algolia write with no persisted chunk count (§9.3) plus a new queue, alarm and DLQ — to save latency that the Inbox's no-polling design (§9.1) makes invisible anyway. |
| **Keeping the sentinel as an internal marker** | It reaches Algolia's top-ranked searchable attribute (`media_completed_worker.py:183` → `search_indexing.py:156`). There is no "internal" here. |

---

## 13. Observations outside this benchmark's scope

Recorded so they are not lost; none of them changes the recommendation.

1. **task-65's Algolia record budget may be stated against the wrong meter.** task-65 (line 158) sizes the Build free tier as "1 GB index max" and projects "100u × 200 docs × 4 = 80k records × 9 KB = 720 MB < 1 GB ✓". The current pricing page shows the Free plan with **"50K records included"** alongside the 1 GB cap, i.e. the record *count* would bind before the size does at that volume. Worth a separate check by the owner; it has no bearing on title derivation.
2. **RSS items never get a durable library row** (`rss_feed_poll_worker.py:64-70` creates a job with no `media_item_id` and never calls `save_media_for_user`), so no RSS item can appear in the Inbox regardless of its title. Surfaced by §2.6; needs its own task.
3. **`episode_title` / `podcast_title` are dead fields on the Deepgram queue** — produced by YouTube, TikTok, Instagram, RSS and podcast paths, read by nobody. Per `AGENTS.md`, they should be deleted rather than carried.
4. **`MediaItemContract` has no `title`** (`media_contracts.py:179-192`) — task-267, confirmed but not re-diagnosed here.

---

## 14. Sources

Code (this repository, verified at the stated lines on 2026-08-17):
`core/media_ingestion/adapters/orchestrators.py`, `core/media_ingestion/use_cases.py`, `core/media_ingestion/adapters/resolvers.py`, `core/services/durable_media_service.py`, `core/services/search_indexing.py`, `core/services/digest_service.py`, `core/services/artifact_service.py`, `core/services/transcript_translation.py`, `core/ports/document_parser.py`, `utils/database_async.py`, `utils/algolia_client.py`, `api/endpoints/media.py`, `api/models/media_contracts.py`, `infrastructure/resolvers/instagram_apify_resolver.py`, `workers/youtube_ingestion_worker.py`, `workers/tiktok_ingestion_worker.py`, `workers/x_ingestion_worker.py`, `workers/article_extraction_worker.py`, `workers/rss_feed_poll_worker.py`, `workers/document_parsing/worker.py`, `workers/transcription/deepgram_worker.py`, `workers/events/media_completed_worker.py`, `workers/search_indexing_worker.py`, `workers/podcast_platform_resolvers.py`, `workers/podcastindex_resolution_worker.py`, `mobile/app/(tabs)/inbox.tsx`, `mobile/app/(tabs)/search.tsx`, `mobile/src/components/MediaListCard.tsx`, `mobile/src/contexts/InboxContext.tsx`, `mobile/src/contexts/ShareIntentContext.tsx`, `mobile/src/lib/localImport.ts`, `mobile/src/types/upload.ts`.

Prior owner-validated benchmarks:
- `docs/research/task-72-llm-artifact-benchmark/README.md` (`owner_decision: ok`) — model stack per artifact type.
- `docs/research/task-189-transcript-translation-benchmark/README.md` (`owner_decision: ok`) — `gpt-5-nano` for transcript translation.
- `docs/research/task-65-pricing-v1-benchmark/README.md` (`owner_decision: ok`, active 5th pass) — tier volumes, per-media costs, USD→EUR 0,86, infra budget.

Providers and libraries (all consulted 2026-08-17):
- OpenAI API pricing — https://developers.openai.com/api/docs/pricing
- OpenAI `gpt-5-nano` model page — https://developers.openai.com/api/docs/models/gpt-5-nano
- Artificial Analysis, GPT-5 nano measurements (output speed, time to first answer token, deprecation flag) — https://artificialanalysis.ai/models/gpt-5-nano
- Algolia pricing and record/search meters — https://www.algolia.com/pricing
- yt-dlp output-template field list (`title` = "Title of the video") — https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md ; TikTok and Instagram extractor behaviour verified directly in the installed yt-dlp 2026.03.13 (`yt_dlp/extractor/tiktok.py`: `'title': ('desc', {truncate_string(left=72)})`; `yt_dlp/extractor/instagram.py`: `'uploader': user_info.get('full_name')`, `'title': f'Video by {username}'`)
- trafilatura core functions (`extract_metadata`, `bare_extraction`, `with_metadata`, title as essential metadata) — https://trafilatura.readthedocs.io/en/latest/corefunctions.html and https://trafilatura.readthedocs.io/en/latest/usage-python.html ; `Document` fields verified on the installed trafilatura 2.0.0 (`title`, `author`, `url`, `hostname`, `description`, `sitename`, `date`, `image`, `language`, …)
- Apify — YouTube transcript actor output schema incl. `title` and $5.00/1 000 results — https://apify.com/starvibe/youtube-video-transcript
- Apify — Instagram scraper output schema (no `title`; `caption`, `ownerFullName`, `ownerUsername`) — https://apify.com/apify/instagram-scraper
- YAKE (unsupervised keyphrase extraction, no training corpus, scored keyphrases) — https://github.com/LIAAD/yake
- Iframely pricing (Starter free = pilot only; Business $49/mo) — https://iframely.com/pricing
- Microlink pricing (Free = 25 req/day; Pro $49/mo) — https://microlink.io/pricing

Literature on the LLM-title failure mode:
- "Multilingual Fine-Grained News Headline Hallucination Detection" — https://arxiv.org/abs/2407.15975
- "'Why is this misleading?': Detecting News Headline Hallucinations with Explanations" (ExHalder) — https://arxiv.org/abs/2302.05852
