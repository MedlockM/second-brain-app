---
owner_decision: ok   # pending | ok | abandoned | redo | more
---

# Benchmark: cover image and creator name extraction per ingestion source

## Owner Validation

**Decision**: Approach C
**Validated at**: 2026-08-20

---

## Recommendation

**Retain approach C — "read what the pipeline already holds, hotlink the URLs that are public and stable, re-host only the three sources whose URL is signed or private" — carried by `job.media_image` / a new `job.creator_name` and the existing `mirror_job` hook.**

Four findings drive this, and only one of them is about money.

1. **The creator name is not missing — it is already passed as an argument and then dropped.** task-266 gave every worker a rejection rule "the title must never be the author", and to apply it each worker had to *find the author first*. So the value is in hand, named, at the exact line that discards it: `article_extraction_worker.py:271` (`authors=[document.author]`), `youtube_ingestion_worker.py:1125` (`authors=[info["uploader"], info["channel"]]`), `tiktok_ingestion_worker.py:992` (`authors=[info["uploader"], info["creator"]]`), `instagram_apify_resolver.py:458` and `:551` (`authors=[item["ownerFullName"], item["ownerUsername"]]`), `x_ingestion_worker.py:286` (`authors=[username, author_name]`). The podcast path is even further along: `podcastindex_resolution_worker.py:129` resolves `podcast_title` — the show name — into a dict, forwards it to the Deepgram queue at `:355`, and **nothing ever reads it back** (the same dead-field pattern task-265 §2.6 found for `episode_title`). Adding a creator to the library row is not an extraction project. It is *stopping a `del`*.

2. **The image is one field read away on five sources, and free on all five.** `trafilatura.extract_metadata()` is *already called* at `article_extraction_worker.py:263`, and the `Document` it returns exposes `image` — verified on the installed trafilatura 2.0.0, whose metadata module maps `og:image`, `og:image:url`, `og:image:secure_url`, `twitter:image` and `twitter:image:src` onto that one attribute (`.venv/…/trafilatura/metadata.py:127-147`). The yt-dlp `info` dict is *already in memory* at `youtube_ingestion_worker.py:988` and at the TikTok equivalent, and carries `thumbnail`. `_extract_image_urls_from_post_result` at `instagram_apify_resolver.py:83-100` *already parses* `displayUrl` — for image posts only; the reel branch at `:461` ignores the same field the same actor returns. Podcasts already work end to end. **No new provider, no new API call, no new secret, 0 € on these five.**

3. **Hotlink vs re-host is not one decision, it is two populations.** `i.ytimg.com`, podcast artwork, `pbs.twimg.com` and publisher `og:image` URLs are unsigned and stable — hotlinking them costs nothing and rots slowly. Instagram and TikTok CDN URLs are **signed with an embedded expiry** (`oh`/`oe` on `scontent.*.cdninstagram.com`, `x-expires` on `*.tiktokcdn.com`) and return 403 "URL signature expired" within hours to days; storing one is storing a guaranteed-broken image. And a camera or gallery photo is not a third-party URL at all — it is the user's own private file, already sitting in our `documents` bucket. So: **hotlink 8 sources, re-host 3** (Instagram, TikTok, photos). Applying either policy globally is what makes this decision look hard; per source it is nearly mechanical.

4. **Cost does not arbitrate, and neither does bandwidth.** Re-hosting a 40 KB cover for ~20 items/user/month at task-65's 100-user launch scale accumulates ~80 MB/month, i.e. **$0.02/month of S3 at M12** against a 19,0 €/month infra line — 0,1 %. Egress stays inside AWS's free 100 GB/month even with every tile downloaded once per device (§5.4). The real price of re-hosting is **one new dependency (Pillow) in the worker image, one bucket, and a URL-resolution step at read time** — effort, not euros.

Concretely, what the owner would be validating:

- **`user_media.thumbnail_url` is reused as the single image carrier, and its value becomes a two-shape string**: an absolute `https://…` URL when hotlinked, an `s3://<bucket>/<key>` locator when re-hosted. `GET /api/media` resolves the `s3://` shape into a presigned URL at read time and returns it in the existing `media_image` field, so the client sees one thing. No parallel image field, no second column, `mirror_job`'s `("media_image", "thumbnail_url")` pair untouched.
- **One new attribute, `creator_name: Optional[str]`, on `UserMediaRecord`, `ProcessingJob` and `ResolvedMedia`**, mirrored by adding exactly one line — `("creator_name", "creator_name")` — to the tuple at `durable_media_service.py:445-452`. It is a *publisher-first* field: the channel, the show, the site, the account. Not a second author field (§7.3).
- **`creator_name` becomes Algolia-searchable in second position** — `["title", "creator_name", "transcript"]` — because the completion event is the only moment it is free to index and this repo has no re-index path (§7.4).
- **Mobile renders with `expo-image`**, `contentFit="cover"`, `recyclingKey`, and a `cacheKey` derived from `${media_item_id}:${updated_at}` so a rotating presigned URL does not defeat the disk cache (§6). A missing, expired or refused image degrades to **the media-type icon that `inbox.tsx:396-399` already renders today** — never an empty grey box. Tile ratio **16:9**.
- **A shared `cover_capture` helper** (fetch → resize to 640×360 → PUT) used by the Instagram, TikTok and document/photo workers only. Pillow enters `pyproject.toml`'s `worker` extra.

**Trade-offs accepted.** Three sources will never have a cover and must say so out loud rather than leave a blank: shared text, uploaded documents (no page-render path exists — `ParseResult` has `markdown_content`, `page_count`, `metadata`, `provider`, and no image), and audio files. Their tile keeps the type icon, which is the current Inbox rendering promoted to a designed state instead of a placeholder. Second trade-off: a 16:9 crop cuts a square podcast artwork on its left and right edges and cuts a 9:16 reel hard — accepted, because a row of tiles with per-source heights is unreadable (§6.4). Third: hotlinked article covers *will* rot, and some publishers refuse a request carrying no `Referer`; a native app sends none. That is a visible, per-item, silent-degradation failure, and §5.3 argues it is cheaper to accept than to re-host 150 articles/user/month.

**One correction to this task's premises, established before anything else was decided** (§2.5): the description states "the app renders no remote image anywhere today". It does — `mobile/app/(tabs)/digest.tsx:299-305` renders `<Image source={{ uri: item.thumbnail_url }} resizeMode="cover" />`. What is actually broken there is the other end: `DigestMediaItemResponse` (`api/endpoints/digest.py:32-39`) has **no** `thumbnail_url` field, while `mobile/src/types/digest.ts:14` declares one. The digest's image slot has been structurally empty since it was written. It is in this task's blast radius and is scoped in §10.

---

## 1. Who consumes a cover and a creator, and what each costs when absent

| Consumer | Path | Reads image from | Reads creator from |
|---|---|---|---|
| Inbox list (the tile this task exists for) | `GET /api/media` → `MediaSearchItem` (`api/endpoints/media.py:328-338`) | `media_image`, mapped from `record.thumbnail_url` (`media_search_service.py:238`) | **nothing — no such field** |
| Media detail screen | `GET /api/media/{id}` → `MediaItemContract` (`api/models/media_contracts.py`) | **nothing — the contract has no image field** | **nothing** |
| Digest screens | `GET /api/digest/*` → `DigestMediaItemResponse` (`api/endpoints/digest.py:32-39`) | **nothing — the field is absent server-side while the client renders it** (§2.5) | **nothing** |
| Algolia index | `media_completed_worker.py` → `search_indexing.index_transcript(...)` | n/a — an index carries no image | **nothing today**; §7.4 recommends adding it |

Three of four consumers cannot render an image even if one existed, and none can render a creator. That is the honest measure of the work: this is not "populate a field", it is "add a field and wire the two contracts that will show it".

The cost of absence is not only cosmetic. The owner's reference tile is *image + title + creator*; with two of three permanently empty, every row in the Inbox collapses to a title over a domain string — which is exactly the current rendering (`inbox.tsx:412-422`).

---

## 2. What exists today, from the code

### 2.1 The image field exists, is wired end to end, and is populated by one source

`UserMediaRecord.thumbnail_url` (`core/models/user_media.py:95`) → serialised at `:155` → exposed as `media_image` by `media_search_service.py:238` → declared on `MediaSearchItem` (`api/endpoints/media.py:336`) → declared in the mobile type `mobile/src/types/media.ts:190` — **where no component reads it**. `mobile/src/components/MediaListCard.tsx:55` and `inbox.tsx:397` both render a `thumbnailContainer` holding an `Ionicons` glyph, never an image.

The single writer is the podcast path:

```
podcastindex_resolution_worker.py:309   episode_image = resolution.get("episode_image") or job.media_image or ""
podcastindex_resolution_worker.py:313   job.media_image = resolution.get("episode_image") or job.media_image
```

and the value reaches the durable row through the pair `("media_image", "thumbnail_url")` at `durable_media_service.py:450`. Upstream, `podcast_platform_resolvers.py` resolves that image from four independent shapes — oEmbed `thumbnail_url` (`:439`), page `og:image` (`:754-759`), PodcastIndex / Apple / Deezer episode `image` (`:548`, `:889`, `:1383`), and the RSS `<itunes:image>` of the item or its channel (`_extract_episode_image`, `:1781-1795`). **Podcasts are the reference implementation for images, exactly as X was for titles in task-265.**

Every other source stores nothing.

### 2.2 The creator name does not exist anywhere — but every worker holds it

There is no author, creator, publisher or channel attribute on `UserMediaRecord`, on `ProcessingJob`, on `MediaSearchItem`, on `MediaItemContract` or on `DigestMediaItem`. `grep -rn "creator\|author" media_summarizer/core/models/` returns nothing relevant.

And yet, at the moment task-266 rejects "the title must not be the account name", each worker has already located the account name:

| Source | The creator, already in a variable | Line |
|---|---|---|
| Article | `document.author` (byline) and `document.sitename` (publisher) | `article_extraction_worker.py:271-273` |
| YouTube (yt-dlp) | `info["uploader"]`, `info["channel"]`, `info["uploader_id"]` | `youtube_ingestion_worker.py:1125` |
| TikTok (yt-dlp) | `info["uploader"]`, `info["creator"]`, `info["uploader_id"]` | `tiktok_ingestion_worker.py:992` |
| Instagram reel | `item["ownerFullName"]`, `item["ownerUsername"]` | `instagram_apify_resolver.py:458` |
| Instagram post | same | `instagram_apify_resolver.py:551` |
| X | `author_username`, `author_name` — and already **persisted** into `extraction_metadata` at `x_ingestion_worker.py:304-306` | `:230-231`, `:286` |
| Podcast | `podcast_title` = the show name, resolved through `feedTitle` / the channel `<title>` | `podcastindex_resolution_worker.py:129`, `podcast_platform_resolvers.py:544, 883, 1596, 1838` |

The podcast case deserves its own sentence, because it is the strongest single argument in this benchmark. `podcastindex_resolution_worker.py:129` builds `"podcast_title": outcome.metadata.get("podcast_title") or "Podcast"`, `:308` reads it back into a local, `:355` forwards it onto the Deepgram queue — and grepping the consumers shows the value is only ever re-emitted as `job.source_platform` fallbacks (`youtube_ingestion_worker.py:1191`, `tiktok_ingestion_worker.py:1042`) or handed to `deepgram_dispatch.py:42` which passes it through to a provider field. **No consumer stores it, no screen shows it.** A fully resolved, canonical show name is computed on every podcast ingestion and thrown away.

### 2.3 What the providers actually return, verified

| Provider | Cover field | Creator field | Verified against |
|---|---|---|---|
| yt-dlp 2026.03.13, YouTube | `thumbnail` (always `https://i.ytimg.com/…`) | `channel`, `uploader` | installed extractor: `yt_dlp/extractor/youtube/_video.py` asserts `'thumbnail': r're:https?://i\.ytimg\.com/.+'` on every test case |
| yt-dlp 2026.03.13, TikTok | `thumbnail` (`*.tiktokcdn.com`, signed) | `uploader`, `creator` | installed extractor |
| trafilatura 2.0.0 | `Document.image` (from `og:image` / `og:image:url` / `og:image:secure_url` / `twitter:image` / `twitter:image:src`) | `Document.author`, `Document.sitename` | installed package: `metadata.py:127-147`; `Document.__slots__` includes `image` |
| Apify `apify/instagram-reel-scraper` | `displayUrl`, `images[]` | `ownerFullName`, `ownerUsername` | actor page, output schema |
| Apify `apify/instagram-scraper` | `displayUrl`, `images[]` | `ownerFullName`, `ownerUsername` | actor page, output schema |
| Apify `starvibe/youtube-video-transcript` | not in the declared output schema | not declared | actor page; the worker's dialect table (`youtube_ingestion_worker.py:114-129`) declares only `transcript_text`, and the title is probed defensively at `:132` |
| X API v2 | `media.fields=preview_image_url,url` behind `expansions=attachments.media_keys` — **not requested today** | `user.fields=username,name` — **already requested** (`x_ingestion_worker.py:63-66`) | X API v2 reference |
| PodcastIndex / Apple / Spotify / Deezer / RSS | `episode_image` | `feedTitle` / channel `<title>` | already implemented, §2.1 |

Two conclusions. **Nothing here requires a new vendor.** And the only source needing a changed request is X — where the change is adding two query parameters to a lookup that is *already being made*, so it costs zero extra API reads under X's post-February-2026 pay-per-use model (~$0.005 per post read; expansions do not multiply reads).

### 2.4 Where the tile would render, today

`mobile/package.json` has no `expo-image` and no image-cache library. It does have `expo-image-picker` (a picker, not a renderer). The only remote-image rendering in the app is `digest.tsx:299-305`, using React Native's built-in `Image`.

### 2.5 Correction to two premises in the task description

Recorded because both change how an implementer would read the task, not to score a point.

1. **"the app renders no remote image anywhere today" — false.** `digest.tsx:299-305` does. The real defect is the contract: `DigestMediaItemResponse` (`api/endpoints/digest.py:32-39`) and `DigestMediaItem` (`core/models/digest.py:36-45`) carry `media_item_id`, `title`, `media_type`, `source_platform`, `summary_short_artifact_id`, `summary_short_status`, `added_at` — and **no image**, while `mobile/src/types/digest.ts:14` declares `thumbnail_url?: string`. `digest_service.py:91-98` builds each item without one. The digest card has been rendering an always-`null` image and falling back to `cardThumbnailPlaceholder`, an empty grey `View`, since it was written. Scoped in §10.
2. **Several `file:line` references have moved**, because task-265/266 shipped in between: `instagram_apify_resolver.py:447/:555` are now `:458`/`:551`; `youtube_ingestion_worker.py:1060` is now `:988`. More importantly the diagnosis has changed shape — the workers do **not** "hold the value and drop it" passively; they **actively read it and pass it as `authors=` to `derive_media_title`**, which is a much shorter distance to cover than the description assumes.

---

## 3. The plumbing that already exists

Load-bearing for every option below, so it is established once.

**3.1 The mirror is automatic and already carries an image.** `utils/database_async.py` calls `_mirror_job_to_durable_library(job)` from both `create_processing_job` and `update_processing_job`; `durable_media_service.mirror_job` (`:446-453`) then patches the library row from this tuple:

```python
for source_attr, target_attr in (
    ("title", "title"),
    ("source_url", "source_url"),
    ("source_platform", "source_platform"),
    ("media_type", "media_type"),
    ("media_image", "thumbnail_url"),      # ← already there
):
    value = getattr(job, source_attr, None)
    if value:
        attributes[target_attr] = value
```

`job.media_image = X` + `await database_async.update_processing_job(job)` is the **entire** integration cost for the image. Only non-empty values are mirrored, so a worker that does not know the cover cannot blank out one another worker resolved. A creator field costs exactly one more line in that tuple.

**3.2 The submit path can carry both from the first second.** `orchestrators.py:326-355` derives the title and passes it to `save_media_for_user(...)` before any worker runs. `ResolvedMedia` (`core/media_ingestion/domain.py:129-140`) is a frozen dataclass with `title`, `audio_url`, `raw_text`, `metadata` — adding `cover_url` and `creator_name` beside `title` makes the resolver-side values available at submit time, exactly as the title is. This matters for Instagram, whose resolver already parses both.

**3.3 The completion event feeds Algolia, and is the only free indexing moment.** As established in task-265 §3.2, `media_completed_worker.py` builds the indexing message from `canonical_job.title` when the completion event fires. A value written on the job **before** that event is indexed on the first pass; a value written after is never indexed, because this repo has no re-index path (no persisted chunk count — task-265 §9.3). Whatever is decided for `creator_name` searchability must therefore be decided **now**, not "later if useful".

**3.4 Presigned URL generation already exists** — `utils/s3.py:354-395`, used by the audio upload path (`media.py:1188`, 600 s expiry) and by bug-report attachments. It is a local HMAC signature, not a network call to S3. One caveat for the implementer, not for the decision: the current helper opens a fresh aioboto3 client per call (`async with session.create_client("s3", …)`), so signing 20 covers for one list page would open 20 clients. Hoisting the client is a prerequisite of the re-host option, not an argument against it.

**3.5 The buckets are private, and one of them already holds the photos.** `infrastructure/terraform/modules/platform/s3.tf` defines 9 buckets on the `${project}-${role}-${account}-${env}` convention, all with `prevent_destroy`. None declares a public-access-block resource (only `bug_reports.tf:68-74` does), and none is public — S3 has blocked public access by default on new buckets since April 2023. Uploaded documents **and camera/gallery photos** land in the `documents` bucket at `{job.id}/{file_name}` (`media.py:987-995`), capped at 50 MB (`media.py:99`).

---

## 4. Per-source coverage — the 11 ingestion paths

"Already available" means the value is in a live variable in our process at the cited line, needing no new request. Camera and gallery photos are listed separately as the task asks, but share one endpoint (`POST /api/media/upload`) and one worker (`workers/document_parsing/worker.py`).

| # | Source | Cover comes from | Already available? | Creator comes from | Already available? | Fallback when the source has none |
|---|---|---|---|---|---|---|
| 1 | **Web article** | `Document.image` — `og:image` / `og:image:url` / `og:image:secure_url` / `twitter:image` | **Yes** — `extract_metadata()` is called at `article_extraction_worker.py:263`; the attribute is simply not read | `Document.sitename` (publisher) with `Document.author` (byline) as the second candidate | **Yes** — both already read at `:271-273`, used only as title-rejection signals | No cover: many blogs and paywalled pages ship no `og:image`. → type icon |
| 2 | **YouTube video** | `info["thumbnail"]` (`i.ytimg.com`) | **Yes** — `info` at `youtube_ingestion_worker.py:988` | `info["channel"]`, then `info["uploader"]` | **Yes** — `:1125` | Apify branch (IP-blocked host): the actor declares no thumbnail → derive `https://i.ytimg.com/vi/<video_id>/hqdefault.jpg` from the id already parsed out of the URL. `hqdefault` always exists; `maxresdefault` does not |
| 3 | **Podcast episode** | `episode_image` — oEmbed / `og:image` / PodcastIndex-Apple-Deezer `image` / RSS `<itunes:image>` | **Yes, and already stored** — `podcastindex_resolution_worker.py:313` | `podcast_title` (the **show**) | **Yes** — resolved at `:129`, forwarded at `:355`, read back by nobody (§2.2) | Feed with no artwork at all: rare. → type icon |
| 4 | **TikTok** | `info["thumbnail"]` (`*.tiktokcdn.com`, signed, `x-expires`) | **Yes** — same `info` dict as the title at `tiktok_ingestion_worker.py:991` | `info["uploader"]` / `info["creator"]` | **Yes** — `:992` | Apify/ScrapeCreators branch returns transcript only (`_build_apify_native_extraction_metadata`, `:637-660`): no cover, no creator → type icon |
| 5 | **Instagram (reel / post)** | `displayUrl` (signed `scontent.*.cdninstagram.com`) | **Yes for posts** — parsed at `instagram_apify_resolver.py:83-100`. **Yes but ignored for reels** — the Reel Scraper returns the same field, the reel branch at `:461` never reads it | `ownerFullName`, then `ownerUsername` | **Yes** — `:458` and `:551` | Reel with no `displayUrl` in the dataset item → type icon |
| 6 | **X post** | `media.fields=preview_image_url,url` behind `expansions=attachments.media_keys` | **No** — the lookup at `x_ingestion_worker.py:63-66` does not request media. Same request, two extra params, **no extra API read** | `author_name`, then `@author_username` | **Yes** — `:230-231`, already persisted at `:304-306` | Text-only post (the majority): no media at all. Do **not** substitute the author avatar — an avatar is not a cover (§5.5) → type icon |
| 7 | **Shared text (WhatsApp)** | **Structurally none.** No URL, no provider, no media | n/a | **Structurally none.** The sharer is the user | n/a | Type icon. State it as a designed outcome, not a gap |
| 8 | **Uploaded document** | **None available.** `ParseResult` (`core/ports/document_parser.py:75-82`) exposes `markdown_content`, `page_count`, `metadata`, `provider` — no image, no page render. A first-page thumbnail needs a PDF rasteriser (PyMuPDF / Poppler) in the Lambda image | No | `ParseResult.metadata` *may* carry a PDF `/Author`, provider-dependent and unverifiable here — treat as absent | No | Type icon. §11 rejects the rasteriser |
| 9 | **Camera photo** | **The media itself** — already in the `documents` bucket at `{job_id}/{file_name}` (`media.py:987-995`) | **Yes, and it is already ours** — but up to 50 MB, so it must be resized, never served raw | **Structurally none** | n/a | A capture that fails to decode → type icon |
| 10 | **Gallery photo** | Same path as #9 | Same | **Structurally none.** EXIF `Artist` is empty on virtually all phone captures | n/a | Same |
| 11 | **Audio file (upload / shared)** | **None.** An MP3 may carry an ID3 `APIC` cover, but the file goes straight to Deepgram; reading it needs `mutagen` and only helps ripped podcasts | No | ID3 `artist`, same caveat | No | Type icon |

**Totals.** Cover already in hand and free: **5** (article, YouTube, podcast, TikTok, Instagram). One extra request parameter: **1** (X). Ours already, needs resizing: **2** (camera, gallery). Structurally impossible: **3** (shared text, document, audio file).
Creator already in hand and free: **6** (article, YouTube, podcast, TikTok, Instagram, X). Structurally impossible: **5** (shared text, document, camera, gallery, audio).

The RSS polling path (`workers/rss_feed_poll_worker.py`) is deliberately absent from the table: task-265 §13.2 established that it creates a job with no `media_item_id` and never calls `save_media_for_user`, so RSS items have **no library row** and therefore no tile. That is a pre-existing defect with its own task, not an ingestion path this benchmark can populate.

---

## 5. Hotlink versus re-host, argued per source

### 5.1 The two populations, on evidence

**Unsigned and stable — hotlink.**

- `i.ytimg.com` serves the current thumbnail for as long as the video exists, from a plain unsigned path (`/vi/<id>/<name>.jpg`); yt-dlp's own YouTube test suite asserts the pattern on every case. Deleted videos return a placeholder rather than a broken URL, which is a *better* degradation than a 404. `hqdefault` is always present; `maxresdefault` and `sddefault` are not, on older or low-resolution uploads.
- Podcast artwork is served from the publisher's own host or Apple's, unsigned, and is already what the app stores today.
- `pbs.twimg.com` media URLs are unsigned.
- Publisher `og:image` URLs are unsigned, though not always *reachable* — see §5.3.

**Signed with an embedded expiry — hotlinking stores a guaranteed-broken value.**

- Instagram: `scontent.*.cdninstagram.com` URLs carry `oh` (hash) and `oe` (expiry) parameters; once past it the CDN answers **403, "URL signature expired"**. Meta's own Instagram Platform documentation describes these as privacy-aware CDN URLs that stop serving when the content is deleted or the URL has expired, without publishing the window.
- TikTok: cover URLs carry `x-expires` as a Unix timestamp. TikTok's Display API docs show the parameter in their example payload without documenting a duration, and direct developers to re-query `/v2/video/query/` to refresh a `cover_image_url`'s TTL. Third-party reports put the practical life anywhere from ~1 hour to a few days.
- Iframely — a vendor whose entire product is unfurling these two platforms — states the position plainly: thumbnails from TikTok and Instagram "come with expiration signatures", commonly break "within a few days", and the recommended handling is to "fetch and store the images on your servers or CDN as soon as you get them".

**Neither — it is already ours.** Camera and gallery photos are private user files in the `documents` bucket. "Hotlink" is meaningless; the only question is how to serve them, and at what size.

### 5.2 URL rot, per source, stated as an expectation

| Source | Signed? | Expected rot | Failure the user sees |
|---|---|---|---|
| YouTube | No | Only if the video is deleted | Placeholder image from YouTube's own CDN |
| Podcast | No | Slow — a feed moving or re-hosting its artwork | 404 → type icon |
| X | No | Only if the post is deleted | 404 → type icon |
| Web article | No | Moderate — CMS migrations, expiring campaign images, hotlink protection (§5.3) | 403/404 → type icon |
| Instagram | **Yes** (`oh`/`oe`) | **Certain**, hours to days | 403 on every tile of that source |
| TikTok | **Yes** (`x-expires`) | **Certain**, hours to days | 403 on every tile of that source |
| Camera / gallery photo | n/a (private) | None once re-hosted | n/a |

A benchmark that recommended global hotlinking would therefore be recommending that **every Instagram and TikTok tile in the library goes blank within a week**, permanently, with no repair path — the resolver output is not retained and re-running an Apify actor to refresh a thumbnail costs $1.50–$2.70 per 1 000 results. That is disqualifying on its own.

### 5.3 The article case, which is the only genuinely arguable one

Articles are the highest-volume source in task-65's baskets (150/month on Text-Only, 100 on Mix, 50 on Audio-Heavy) — so whatever is decided for them dominates any re-host cost estimate. Three facts:

- **`og:image` is designed to be fetched by third parties.** It exists so Facebook, WhatsApp, Slack and every unfurler can display it. Hotlinking it is the use the publisher marked it up for.
- **But hotlink protection is Referer-based, and a native app sends no Referer.** Cloudflare-style hotlink protection is all-or-nothing for third parties, and some CDN configurations reject an empty Referer outright, producing 403s for legitimate clients. So a fraction of article covers will fail *at display time*, per device, unpredictably.
- **Weight is real but bounded.** The `og:image` convention is 1200×630; the widely-followed guidance targets under 300 KB, with 80–150 KB typical for a JPEG at q80–85. Twenty tiles of 150 KB is ~3 MB for a first cold scroll of the Inbox, downloaded once per device thanks to the disk cache.

Recommendation for articles: **hotlink, and treat the failures as the designed degraded state**. Re-hosting them would triple the re-host volume (§5.4), add a fetch to the article worker's critical path on every single ingestion — the one path in the pipeline that today makes no external call beyond the page fetch itself — and buy a fix for a minority failure that the type-icon fallback already handles gracefully. If the owner disagrees, the change is one flag in the shared helper: article covers become the fourth re-hosted source, and §5.4's cost figures multiply by ~8, i.e. from $0.02/month to $0.16/month. **The cost is not the reason to say no; the added latency on the highest-volume path is.**

### 5.4 What re-hosting three sources actually costs

Volumes. task-65's nominal baskets are 200 items/month (Text-Only), ~132 (Mix), ~100 (Audio-Heavy) — and **none of the three lists Instagram, TikTok or photos at all**, so the re-host population is out-of-basket by construction. Estimating generously at **20 re-hosted items per user per month**:

| Line | Calculation | Monthly cost @100 users |
|---|---|---|
| Storage, month 1 | 100 × 20 × 40 KB = 80 MB × $0.023/GB | **$0.002** |
| Storage, month 12 (cumulative, covers live as long as the media) | 960 MB × $0.023/GB | **$0.022** (~0,019 €) |
| PUT requests | 2 000/month × $0.005/1 000 | **$0.01** |
| GET requests | ≤ 20 000/month × $0.0004/1 000 | **$0.008** |
| Egress to internet | ≤ 800 MB/month, against AWS's free 100 GB/month | **$0.00** |
| **Total at M12** | | **≈ $0.04/month → 0,034 €** |

Against task-65's launch infra of **19,0 €/month @100u** (0,145–0,190 €/user), that is **0,18 %**. Against the media budget of the cheapest tier (1,33 €/user/month), a per-user cover cost of 0,0003 € is **0,03 %**.

Sizing assumption: a 640×360 JPEG at q80 lands at ~40 KB — consistent with the 80–150 KB figure for a 1200×630 og:image at the same quality, scaled down by ~3,5× in pixel count.

**Added pipeline latency**, per re-hosted item: one HTTP GET of the source image (100–400 ms), one decode+resize (Pillow, tens of ms at these sizes), one S3 PUT (50–100 ms) → **~0,3–0,6 s**. It lands inside workers that already spend 20–60 s in an Apify actor or a Deepgram transcription. Invisible.

**Effort**, which is the real price:

- `pillow` added to `pyproject.toml`'s `worker` extra (manylinux wheels; no system packages).
- One new bucket in `s3.tf` following the existing convention, with `prevent_destroy`.
- A shared `cover_capture(url_or_s3_key) -> s3://…` helper, used by 3 workers.
- A read-time resolution step in `media_search_service` / `media.py` turning `s3://…` into a presigned URL.
- The purge cascade must delete cover objects with the media (`workers/cleanup/media_lifecycle.py`).

### 5.5 Serving a re-hosted cover: three ways, one recommendation

| | (a) Public bucket | (b) CloudFront + OAC | (c) Presigned at read time |
|---|---|---|---|
| New infra | bucket + public policy | bucket + distribution + OAC + invalidation policy | **bucket only** |
| Private photos exposed? | **Yes — unacceptable.** #9/#10 are the user's own photos | No | No |
| Client cache | perfect (stable URL) | perfect | broken by the rotating query string **unless** `cacheKey` is set — and `expo-image` has exactly that prop (§6.2) |
| Cost | storage + egress | + CloudFront (free tier 1 TB/month covers this easily) | storage + egress |
| Reuses existing code | no | no | **yes** — `utils/s3.py:354` |

**(c) is the recommendation.** It is the only one that needs no new AWS resource type, it keeps the user's private photos private with no bucket policy to get wrong, and its single weakness — cache invalidation by a rotating signature — is answered by a prop that already exists in the recommended client library. Expiry should be generous (24 h) so an Inbox held open across a session never renders a stale-signed URL.

### 5.6 Hotlink correctness, said plainly

Neither option is spotless, and the honest framing is that they fail in opposite directions.

- **Hotlinking** copies nothing, but consumes a third party's bandwidth on every render, and is the behaviour hotlink protection exists to block. It is normal and expected for `og:image` and for `i.ytimg.com`; it is what every unfurler and every chat app does.
- **Re-hosting** makes a copy on our infrastructure. That is a stronger act, mitigated here by three facts: it is a downscaled thumbnail, it is stored in a private bucket, and it is served only to the one user who saved that media — no public URL, no redistribution, no index. There is no scenario in this design where a re-hosted cover is reachable by anyone other than its saver.

For the two sources where re-hosting is recommended, the alternative is not "a cleaner hotlink" — it is **no image at all**. That is the actual comparison.

---

## 6. Client-side rendering

### 6.1 `expo-image`, not React Native's `Image`

`expo-image` wraps SDWebImage on iOS and Glide on Android, and is installed with `npx expo install expo-image` (it is not bundled). At Expo SDK 55 that resolves to the SDK-matched version, so it carries no upgrade risk for the project.

What decides it is not "it is faster". It is three props React Native's `Image` does not have:

| Prop | Why this project needs it |
|---|---|
| `source.cacheKey` — *"The cache key used to query and store this specific image. If not provided, the `uri` is used also as the cache key."* | Without it, the presigned strategy of §5.5(c) re-downloads every re-hosted cover on every list refresh, because the signature changes. With it, the cover is cached under a stable identity |
| `recyclingKey` — resets the view before loading a new source, for recycled rows | The Inbox is a `FlatList`; without it a recycled row shows the *previous* item's cover while the new one loads. This is the single most visible defect of naive image lists |
| `cachePolicy` (`none` / `disk` / `memory` / `memory-disk`, default `disk`) | An explicit `memory-disk` keeps a scrolled-back tile instant and survives app restarts |

Supporting props to use: `contentFit="cover"` (CSS `object-fit` semantics; replaces `resizeMode`), `transition={150}` for a cross-dissolve instead of a pop-in, `priority="low"` so covers never contend with anything interactive, `onError` for the degraded state below.

One caveat the implementer should not take on faith: community guides state the disk cache is capped at 100 MB with LRU eviction on both platforms, but **the official documentation does not document a default cap or eviction policy**. Treat the cap as unspecified rather than guaranteed.

### 6.2 The exact source shape

```tsx
<Image
  source={{ uri: item.media_image, cacheKey: `${item.media_item_id}:${item.updated_at}` }}
  recyclingKey={item.media_item_id}
  cachePolicy="memory-disk"
  contentFit="cover"
  transition={150}
  onError={() => setFailed(true)}
/>
```

Note what this costs the API contract: **nothing.** `media_item_id` and `updated_at` are both already on `MediaSearchItem` (`api/endpoints/media.py:328-338`). The cache key is stable across presigned rotations and *changes* when the row is updated — which is exactly when a cover may legitimately have been replaced. No new field, no version column.

### 6.3 The degraded state, which is the current rendering promoted

Three failure cases, one visual answer:

| Case | Detection | Rendering |
|---|---|---|
| `media_image` is `null` (3 sources structurally, plus every miss) | server-side, no image ever requested | the media-type `Ionicons` glyph on the tinted container — **the exact rendering of `inbox.tsx:396-399` today** |
| The URL 404s, 403s, or the signature expired | `onError` | same |
| Still loading | `placeholder` | the tinted container, flat colour — **not** a spinner, and **not** a blurhash (none is computed) |

**Never an empty grey box.** This rule is not hypothetical: `digest.tsx:306` renders `cardThumbnailPlaceholder`, an empty `View`, and that is precisely what to stop doing. The tile must be visually complete without an image, because for three of eleven sources it permanently will be.

### 6.4 Aspect ratio

Source ratios are irreconcilable: 16:9 (YouTube), 1:1 (podcast artwork), 9:16 (TikTok, Instagram reels), ~1.91:1 (`og:image`), arbitrary (photos).

**Recommendation: 16:9, with `contentFit="cover"`.** Reasons: it matches the two highest-volume sources (YouTube natively, `og:image` at 1.91:1 with a ~5 % crop); a square tile costs too much vertical space in a scrolling list; and a fixed ratio is what allows `FlatList` row heights to be uniform.

What it costs, stated rather than hidden: a square podcast artwork loses ~44 % of its width to the crop, and a 9:16 reel cover is cropped hard, keeping only its middle band. Both remain recognisable because artwork and reel covers are centre-composed. The alternative — per-source ratios — produces a ragged column and is rejected.

---

## 7. The creator field, fully specified

### 7.1 Name and type

```python
# core/models/user_media.py, in the "display metadata" block beside title
creator_name: Optional[str] = None
```

`Optional[str]`, nullable forever (5 of 11 sources can never have one), trimmed to **80 characters** on a word boundary — long enough for "The Rest Is History" or "Le Monde diplomatique", short enough that a tile's second line never wraps. The name is deliberately `creator_name` and not `author` or `publisher`: it must read naturally whether it holds a channel, a show, a site or an account (§7.3).

The same attribute is added to `ProcessingJob` (beside `title`, and to the `optional_fields` list at `core/models/processing_job.py:183-195` so it persists) and to `ResolvedMedia` (`core/media_ingestion/domain.py:129-140`, beside `title`) so resolvers can supply it at submit time.

### 7.2 Write path onto the durable row

**The `mirror_job` hook, exactly like the title — one line.** In `durable_media_service.py:445-452`:

```python
for source_attr, target_attr in (
    ("title", "title"),
    ("creator_name", "creator_name"),        # ← added
    ("source_url", "source_url"),
    ("source_platform", "source_platform"),
    ("media_type", "media_type"),
    ("media_image", "thumbnail_url"),
):
```

Each worker sets `job.creator_name = …` before the `update_processing_job(job)` call it already makes ahead of publishing `episode_completion_status`. The submit path additionally passes `creator_name=` to `save_media_for_user` in `orchestrators.py:346-355`, so a tile has its creator from the first render for the sources whose resolver knows it (Instagram, podcast).

Rejected alternative: passing it on the SQS payload. task-265 §2.6 already disproved that channel — `episode_title` and `podcast_title` are produced by five paths and read back by no consumer. The mirror is the channel that works.

### 7.3 Publisher or author? — one field, publisher semantics

The tile has one second line. Asking whether it should hold the publisher or the author is really asking **which of the two a user recognises**, per source:

| Source | Publisher-ish value | Author-ish value | Which the saver recognises |
|---|---|---|---|
| Podcast | the show ("Acquired") | the host | **the show** |
| YouTube | the channel | — (same thing) | the channel |
| Article | the site ("Le Monde") | the byline ("J. Dupont") | **the site**, in the large majority |
| TikTok / Instagram | the account | the account | the account |
| X | @handle / display name | same | the handle |

In five of six, the recognisable entity is **the thing that publishes**, not a natural person. A second field would therefore be populated identically to the first on four sources, be empty on three, and force the tile to choose at render time — a decision the schema would have pushed onto the UI for no gain.

**Decision: one field, publisher-first.** Where a source offers both, the resolution order is publisher then author: article → `Document.sitename` else `Document.author`; podcast → `podcast_title`; YouTube → `info["channel"]` else `info["uploader"]`; TikTok/Instagram → `ownerFullName`/`uploader` else the handle; X → `author_name` else `@author_username`. The byline is not lost where it matters — `extraction_metadata` already carries it for X (`x_ingestion_worker.py:304-306`) and can for articles — and a future "author" line on the detail screen can read it there without a schema change.

One normalisation rule worth stating, because it is the failure mode: a creator name that is **equal to the title** must be dropped rather than rendered twice. This is the inverse of task-266's rejection rule and reuses its `_normalize_for_comparison` helper (`title_derivation.py:176`).

### 7.4 Algolia — yes, in second position

`utils/algolia_client.py:106-109` sets `"searchableAttributes": ["title", "transcript"]`. The list is **ordered**: a match in an earlier attribute outranks a match in a later one.

**Recommendation: `["title", "creator_name", "transcript"]`**, plus `creator_name` added to `attributesToRetrieve` and to the indexing message built by `media_completed_worker.py`.

Arguments, since this is a ranking decision and not a detail:

- **For.** "Everything I saved from Acquired" is a real and obvious query, and it is currently answered only by accident — via the creator's name happening to appear inside transcripts ("welcome to the show"), which ranks it below any transcript noise and misses every article.
- **Position.** Above `transcript` because a creator match is a strong intent signal; below `title` because an exact title match must stay first.
- **Timing is the decisive argument.** §3.3: the record is written once, at completion, and this repo has no re-index path. Adding the attribute later means either a full manual re-index or a permanently half-populated field. It is free **now** and expensive **later**.
- **Cost.** ~20–40 bytes per record against ~9 KB chunks (task-65 §1). Immaterial on both the size and record-count meters.

Against, and rejected: "the tile already shows the creator, so search does not need it" — that confuses display with retrieval, and the same argument would remove `title` from the index.

---

## 8. Options, comparison, and the recommendation

### 8.1 The candidate options

**A — Metadata plumbing only, hotlink everything.** Read `thumbnail` / `image` / `displayUrl` / `episode_image` and the creator fields; store the third-party URL as-is. No new bucket, no new dependency, no added latency.

**B — Re-host everything.** Every cover downloaded, resized and stored in S3, articles included. One uniform policy, zero rot, and a fetch added to every ingestion path.

**C — Hybrid: hotlink the unsigned sources, re-host the signed ones and the photos.** A, plus a `cover_capture` step in the Instagram, TikTok and document/photo workers only. **This is the recommendation.**

**D — No image at all; ship the creator only.** Half the tile, a third of the work, and it does not deliver what the reference screenshot is built on.

**E — A generic unfurl API (Iframely, Microlink) for covers.** One vendor instead of per-source reads. Already priced and rejected by task-265 §4/§12 at ~42 €/month against a 19,0 €/month infra line; and it reaches none of the four non-URL sources.

### 8.2 Comparison

| Dimension | A — hotlink all | B — re-host all | **C — hybrid** | D — creator only | E — unfurl API |
|---|---|---|---|---|---|
| Sources with a cover (of 11) | 6 | 8 | **8** | 0 | 4 |
| Sources whose cover is guaranteed to break | **2** (Instagram, TikTok) | 0 | **0** | n/a | 2 |
| Photos (#9/#10) rendered | no — 50 MB raw is unservable | yes | **yes** | no | no |
| Recurring cost @100u | **0 €** | ~0,25 €/month at M12 | **~0,03 €/month at M12** | 0 € | ~42 €/month |
| Added pipeline latency | **none** | +0,3–0,6 s on **every** ingestion, incl. the article path that makes no external call today | +0,3–0,6 s on ~15 % of ingestions | none | +1 HTTP call per URL item, in the **synchronous submit path** |
| New dependency | none | Pillow | Pillow | none | vendor + secret |
| New AWS resource | none | 1 bucket | **1 bucket** | none | none |
| Read-path change | none | URL resolution | URL resolution | none | none |
| Client cache behaviour | native (stable URLs) | needs `cacheKey` | needs `cacheKey` | n/a | native |
| Main failure mode | Instagram/TikTok tiles go blank within days, unrepairable | a source fetch failure inside every worker | same, confined to 3 workers | the tile never matches the reference design | vendor outage in the submit path |
| Delivers the owner's reference tile | partly | yes | **yes** | no | partly |

**Reading.** A is free and fast and quietly breaks two sources forever — the one outcome the reference screenshot cannot survive. B buys uniformity at the price of putting a network fetch on the article path, which is the highest-volume source and the only one currently free of external calls. C is A's cost and latency profile on 8 sources and B's durability on the 3 that need it. D and E do not deliver the deliverable.

### 8.3 Effort, ordered

| Piece | Where | Size |
|---|---|---|
| `creator_name` on 3 models + 1 mirror line + `MediaSearchItem` + `_record_to_search_result` | `user_media.py`, `processing_job.py`, `domain.py`, `durable_media_service.py:450`, `media.py:336`, `media_search_service.py:238` | small, mechanical |
| Read the cover + creator in 6 workers/resolvers | article, YouTube, TikTok, Instagram, X, podcast | 6 × a few lines — the values are already in scope (§2.2) |
| `cover_capture` helper + Pillow + bucket | new module, `pyproject.toml`, `s3.tf` | medium |
| `s3://` → presigned resolution at read time, + hoisting the aioboto3 client (§3.4) | `media_search_service.py`, `utils/s3.py` | small |
| Algolia: 1 setting + 1 field through the indexing message | `algolia_client.py:106`, `media_completed_worker.py`, `search_indexing.py` | small |
| Mobile: `expo-image`, the tile, the degraded state | `package.json`, `inbox.tsx`, `MediaListCard.tsx`, `digest.tsx` | medium |
| Purge cascade deletes covers | `workers/cleanup/media_lifecycle.py` | small |
| Digest contract gains `thumbnail_url` (§2.5) | `core/models/digest.py`, `api/endpoints/digest.py`, `digest_service.py:91-98` | small |

---

## 9. Failure modes, per option

**C's own failure modes**, stated so the owner is not surprised:

1. **A hotlinked article cover 403s on a device behind hotlink protection.** Visible per-device, silent, degrades to the type icon. Accepted (§5.3).
2. **`cover_capture` fetches an image the source no longer serves.** Must never fail the ingestion — a cover is a display detail. The helper swallows every exception and returns `None`, exactly as `_extract_article_title` does at `article_extraction_worker.py:262-265`.
3. **A resized cover is stored but the row update fails.** Leaves an orphan S3 object. Bounded by the lifecycle rule that already purges media objects; worth an explicit cleanup entry rather than a retry.
4. **The presigned URL expires while the Inbox is open.** With a 24 h expiry and a list refetched on focus, this needs a session held open across a day. The `onError` fallback covers it.
5. **`cacheKey` is forgotten in a later refactor.** Silent: covers still render, they are just re-downloaded every refresh. Worth a comment at the call site, since nothing will break visibly.

**A's failure mode** is the one that disqualifies it: two entire sources go blank within days, with no repair path short of re-paying an Apify actor per item.

**B's failure mode** is subtler — every article ingestion gains a dependency on a second host being up, on the highest-volume path in the product.

---

## 10. What the implementation task will have to do (informative, not a decision)

Ordered so the shared pieces land first.

1. **Schema and contracts.** `creator_name` on `UserMediaRecord`, `ProcessingJob` (+ `optional_fields`), `ResolvedMedia`, `MediaSearchItem`, `_record_to_search_result`, and the mobile `MediaListItem` type. Bump `USER_MEDIA_SCHEMA_VERSION` if the convention requires it.
2. **Mirror.** One line in `durable_media_service.py:450`'s tuple.
3. **`cover_capture` helper + Pillow + the covers bucket** in `s3.tf`, plus the read-time `s3://` → presigned resolution and the aioboto3 client hoist (§3.4).
4. **Six producers**, each reading values already in scope: `article_extraction_worker.py:263-277` (`Document.image`, `sitename`, `author`); `youtube_ingestion_worker.py:988/1124` (`info["thumbnail"]`, `channel`) plus the deterministic `i.ytimg.com/vi/<id>/hqdefault.jpg` fallback on the Apify branch; `tiktok_ingestion_worker.py:991` (`info["thumbnail"]` → `cover_capture`, `uploader`); `instagram_apify_resolver.py:458/551` (`displayUrl` → `cover_capture`, `ownerFullName`) — **including the reel branch, which ignores a field the actor returns**; `x_ingestion_worker.py:63-66` (add `expansions=attachments.media_keys` and `media.fields=preview_image_url,url`; creator from `:230-231`); `podcastindex_resolution_worker.py:129/313` (image already stored — only `job.creator_name = podcast_title` is missing).
5. **Photos.** In `workers/document_parsing/worker.py`, when the parsed format is one of `DocumentFormat`'s image members, resize the already-uploaded object into a cover instead of fetching anything.
6. **Algolia.** `["title", "creator_name", "transcript"]`, `attributesToRetrieve`, and the field carried through `media_completed_worker` → `search_indexing`.
7. **Mobile.** `npx expo install expo-image`; rewrite the Inbox tile and `MediaListCard`; §6.2's source shape; §6.3's degraded state; and fix `digest.tsx:306`'s empty-`View` placeholder.
8. **Digest contract** gains `thumbnail_url` (§2.5) so the card the app already renders stops being fed `null`.
9. **Purge cascade** deletes cover objects with the media.

No backfill and no migration: existing `-dev` rows stay imageless and creator-less until re-ingested, and that is fine (`AGENTS.md`, "Nothing is deployed yet"). Do not scope a dual-read, a second image field, or a "legacy rows keep working" path.

---

## 11. Rejected alternatives

| Rejected | Reason |
|---|---|
| **Hotlinking Instagram and TikTok covers** | Their URLs are signed with an embedded expiry (`oh`/`oe`, `x-expires`) and answer 403 within hours to days. Storing one stores a value known in advance to break, with no refresh path that does not re-pay an Apify actor at $1.50–$2.70/1 000 |
| **Re-hosting article covers too (option B)** | Not on cost — $0.16/month at 8× the volume — but on latency and blast radius: it puts a second-host fetch on the highest-volume ingestion path, the only one currently free of external calls. One flag away if the owner disagrees (§5.3) |
| **A public covers bucket** | Sources #9/#10 are the user's own private photos. A public read policy on the same bucket that holds them is not an option, and splitting into a public and a private covers bucket doubles the infra to save one signature call |
| **CloudFront + OAC** | Correct and slightly faster, but adds a distribution, an OAC, and an invalidation story to save a presigned-URL call that already exists in `utils/s3.py:354`. Revisit if cover egress ever leaves the free tier — at 800 MB/month against 100 GB it will not |
| **A second image field beside `thumbnail_url`** | Explicitly the failure mode named in the task. `thumbnail_url` is already wired from the model through `mirror_job`, the list endpoint and the mobile type; the only thing it needs is a documented two-shape value (`https://…` or `s3://…`) resolved at read time |
| **A separate `publisher` and `author` pair** | Identical on four sources, empty on three, and it pushes a render-time choice into the schema for a tile that has one second line (§7.3) |
| **A PDF first-page thumbnail for documents** | Needs a rasteriser (PyMuPDF or Poppler) in the Lambda image, and produces a grey rectangle of text that identifies nothing. The type icon carries more information at a glance |
| **Reading an MP3's ID3 `APIC` cover** | Needs `mutagen` on the audio path and only pays off for ripped podcast episodes — which already have a real artwork through the podcast path |
| **The X author's avatar as a cover** | An avatar is a person, not a subject. It would make every text-only X post look like a profile card, and it is the same category error task-266 fixed for titles |
| **An unfurl API for covers (Iframely / Microlink)** | ~42 €/month against a 19,0 €/month infra line, for values five of our sources already return in memory; reaches none of the four non-URL sources; free tiers explicitly non-production. Already rejected in task-265 §12 |
| **An LLM or vision model to caption/select an image** | There is nothing to arbitrate: each source has at most one cover candidate. A model call would be pure cost |
| **Backfilling existing `-dev` rows** | Zero users, zero production data (`AGENTS.md`). Re-ingest or leave them |

---

## 12. Observations outside this benchmark's scope

Recorded so they are not lost; none changes the recommendation.

1. **The digest image slot has never worked** — `DigestMediaItemResponse` has no `thumbnail_url` while `mobile/src/types/digest.ts:14` declares one and `digest.tsx:299` renders it (§2.5). Folded into §10.8 because it is the same field, but it is a pre-existing bug, not new scope.
2. **`podcast_title` is a dead field on the Deepgram queue**, produced by the podcast, YouTube, TikTok and Instagram paths and read back by no consumer — the same pattern task-265 §13.3 found for `episode_title`. §7.2 gives it a real consumer for podcasts; the other producers should be deleted rather than carried (`AGENTS.md`).
3. **`MediaItemContract` has no image and no creator**, so the detail screen cannot show either. Sibling of task-267 (which added the title); needs its own task if the detail screen is meant to match the tile.
4. **`utils/s3.py:354` opens an aioboto3 client per presigned URL.** Harmless at one call per audio upload, wasteful at 20 per list page. Prerequisite of §5.5(c), noted at §3.4.
5. **RSS-polled items still have no library row** (`rss_feed_poll_worker.py`), so no cover work can make them visible. Pre-existing, surfaced by task-265 §13.2.

---

## 13. Sources

Code (this repository, verified at the stated lines on 2026-08-20):
`core/models/user_media.py`, `core/models/processing_job.py`, `core/models/digest.py`, `core/media_ingestion/domain.py`, `core/media_ingestion/use_cases.py`, `core/media_ingestion/adapters/orchestrators.py`, `core/media_ingestion/adapters/resolvers.py`, `core/media_ingestion/title_derivation.py`, `core/services/durable_media_service.py`, `core/services/media_search_service.py`, `core/services/media_submission.py`, `core/services/digest_service.py`, `core/ports/document_parser.py`, `utils/s3.py`, `utils/algolia_client.py`, `utils/deepgram_dispatch.py`, `api/endpoints/media.py`, `api/endpoints/digest.py`, `api/endpoints/artifacts.py`, `api/models/media_contracts.py`, `infrastructure/resolvers/instagram_apify_resolver.py`, `workers/article_extraction_worker.py`, `workers/youtube_ingestion_worker.py`, `workers/tiktok_ingestion_worker.py`, `workers/x_ingestion_worker.py`, `workers/document_parsing/worker.py`, `workers/podcast_platform_resolvers.py`, `workers/podcastindex_resolution_worker.py`, `workers/rss_feed_poll_worker.py`, `workers/events/media_completed_worker.py`, `infrastructure/terraform/modules/platform/s3.tf`, `mobile/package.json`, `mobile/app/(tabs)/inbox.tsx`, `mobile/app/(tabs)/digest.tsx`, `mobile/src/components/MediaListCard.tsx`, `mobile/src/types/media.ts`, `mobile/src/types/digest.ts`, `mobile/src/types/upload.ts`, `mobile/src/lib/localImport.ts`.

Installed packages, inspected directly:
- trafilatura 2.0.0 — `Document.__slots__` contains `image`; `trafilatura/metadata.py:127-147` maps `og:image`, `og:image:url`, `og:image:secure_url`, `twitter:image`, `twitter:image:src` onto it.
- yt-dlp 2026.03.13 — `yt_dlp/extractor/youtube/_video.py` asserts `'thumbnail': r're:https?://i\.ytimg\.com/.+'` across its test matrix.

Prior owner-validated benchmarks:
- `docs/research/task-265-media-title-derivation/README.md` (`owner_decision: ok`) — the mirror hook, the completion-event indexing rule, the per-source method this document follows, and the dead-queue-field finding.
- `docs/research/task-65-pricing-v1-benchmark/README.md` (`owner_decision: ok`, 5th pass) — tier baskets, infra 19,0 €/month @100u, 0,145–0,190 €/user, USD→EUR 0,86.
- `docs/research/task-218-durable-media-library-persistence/README.md` — the durable row as the library's source of truth.
- `docs/INGESTION_WORKERS_PROVIDERS.md` (task-174) — per-source primary path and fallback chains.

Providers, libraries and pricing (all consulted 2026-08-20):
- Expo — `expo-image` reference (props `source`, `placeholder`, `contentFit`, `cachePolicy`, `transition`, `recyclingKey`, `priority`, `onError`; SDWebImage on iOS, Glide on Android; `ImageSource.cacheKey` — "The cache key used to query and store this specific image. If not provided, the `uri` is used also as the cache key.") — https://docs.expo.dev/versions/latest/sdk/image/
- Iframely — "How to deal with expiring images of TikTok and Instagram" (expiration signatures, breakage "within a few days", recommendation to fetch and store) — https://iframely.com/help/015914-how-to-deal-with-expiring-images-of-tik-tok-and-instagram
- TikTok for Developers — Video List / Query Videos, `cover_image_url` with `x-expires` in the example payload and `/v2/video/query/` to refresh the TTL — https://developers.tiktok.com/doc/tiktok-api-v2-video-list
- Meta for Developers — Instagram Platform, privacy-aware CDN URLs that stop serving expired or deleted media — https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/
- Apify — `apify/instagram-reel-scraper` output schema (`displayUrl`, `images`, `videoUrl`, `ownerFullName`, `ownerUsername`, `caption`, `videoDuration`) and pricing ($2.00–$2.30 / 1 000 results) — https://apify.com/apify/instagram-reel-scraper
- Apify — `apify/instagram-scraper` output schema and pricing ($1.50–$2.70 / 1 000 results) — https://apify.com/apify/instagram-scraper
- Apify — `starvibe/youtube-video-transcript` output schema — https://apify.com/starvibe/youtube-video-transcript
- YouTube thumbnail URL structure and availability (`hqdefault` always present, `maxresdefault`/`sddefault` not guaranteed; deleted videos serve a placeholder) — https://github.com/paulirish/lite-youtube-embed/blob/master/youtube-thumbnail-urls.md
- Open Graph image sizing conventions (1200×630, target < 300 KB, 80–150 KB typical at JPEG q80–85) — https://og-image.org/learn/og-image-size
- Hotlink protection is Referer-based and all-or-nothing for third parties; empty Referers are commonly rejected — https://developers.cloudflare.com/workers/examples/hot-link-protection and https://www.ctrl.blog/entry/modern-hotlink-protection.html
- AWS S3 pricing — Standard $0.023/GB-month (first 50 TB), PUT $0.005/1 000, GET $0.0004/1 000, first 100 GB/month of internet egress free — https://aws.amazon.com/s3/pricing/
- AWS CloudFront pricing — $0.085/GB (first 10 TB, US/CA/EU), always-free tier of 1 TB/month and 10 M requests — https://aws.amazon.com/cloudfront/pricing/
- X API v2 — post lookup with `expansions=attachments.media_keys` and `media.fields`; pay-per-use since February 2026 at ~$0.005 per post read — https://docs.x.com/x-api/posts/lookup
</content>
