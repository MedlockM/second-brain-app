---
owner_decision: ok
---

# Benchmark: making the audio-minutes quota count real minutes (resolve-before-accept vs reconcile-after)

## Owner Validation

**Decision**: Accept the recommendation as written — the three-layer hybrid (Layer 0 classification fix + Layer 1 duration gate inside the resolution workers before the Deepgram enqueue + Layer 2 settlement from Deepgram's `metadata.duration` under an idempotent conditional write). Neither literal Option A nor literal Option B is retained, for the reasons given in sections 3.5 and 5.1.

All three layers are in scope for implementation, in order 0 → 1 → 2. Specifically retained:

- **Layer 0**: fix `classify_media_type` so `spotify`, `apple_podcasts`, `deezer`, `direct_url` and `manual` land in the `audio` category; unify the two platform detections so the `text_only` tier gate actually fires; add the three missing enforcement points (`POST /media/upload-audio`, `POST /media/ingest-shared-content`, `rss_feed_poll_worker`).
- **Layer 1**: one `check_and_debit(duration)` call inside the resolution workers before the Deepgram enqueue, plus the shared HTTP Range container-probe helper (parse ID3v2 length + MPEG frame header + `Xing`/`Info` directly — no `ffmpeg` dependency). Recommended probe budget 5 s. Never refuse a legitimate share on a metadata failure: fall back to a provisional 1 minute and let Layer 2 settle.
- **Layer 2**: settle inside `deepgram_worker` from `metadata.duration` right after `extract_transcript` — *not* in `media_completed_worker`, and never off the `minutes_used` producer hint. Idempotency via **Variant 1** (atomic conditional `ADD` with a `settled_jobs` string set on the usage item); verify DynamoDB's evaluation of `contains` on a missing attribute at implementation time, and fall back to Variant 2 if that shape does not hold.

Overrun policy accepted as recommended: **store the true value, clamp only for display, never negative, never refund, the next import is refused naturally.** No mobile change required.

Accepted residual risks and follow-ups:

- `unknown` stays inexact before the spend (Layer 2 only) — accepted.
- **M4A/AAC is a genuine implementation risk**: the Range probe was validated on MP3 only. Validate the `mvhd`/tail-Range path during implementation; if it does not hold, fall back to Layer 2 for that container rather than blocking the task.
- The pricing findings in section 2.5 (`audio_heavy` loss-making at full usage, `cost_per_minute_eur: 0.003` understating the real Deepgram PAYG rate by 47 %) are **out of scope here** and go to a separate task revisiting the `task-65` assumptions.
- The LLM cost side and tier sizing remain out of scope.

**Validated at**: 2026-08-13

---

## Recommendation

**Neither Option A nor Option B as stated. Adopt a three-layer hybrid: fix the classification (Layer 0), gate on the real duration inside the existing resolution workers *before* the Deepgram enqueue (Layer 1 = "Option A moved off the request path"), and settle from Deepgram's own billed duration with an idempotent conditional write (Layer 2 = Option B, hardened).**

The task frames the choice as "resolve before accepting the share" vs "reconcile after transcription". The measurements below show a third position that dominates both:

- Option A as literally stated — resolve the duration *inside* `POST /api/media/ingest-url` before returning to the share sheet — costs 0.4 s (Deezer) to 5.2 s (RSS worst case) of added share latency, and is impossible for Instagram (Apify polls up to 120 s) against a hard 30 s ceiling (`lambda_api.tf:91` `timeout = 30` behind an HTTP API). It also duplicates work the resolution workers already do.
- Option B alone leaves the financial hole open: the cost is already spent by the time it reconciles, and it cannot enforce `max_audio_per_import_minutes` at all.
- **The money is not spent when the share is accepted; it is spent when a message reaches `deepgram-transcription-queue`.** Every audio-bearing path passes through a worker that already knows (or can obtain, for free) the exact duration *before* that enqueue. Gating there gives Option A's financial guarantee at **zero added share latency**, with **zero new third-party cost**, and it reuses the resolvers that already exist.

### Per-platform mechanism (the answer to AC #6)

| `SourcePlatform` | Layer 0 category | Layer 1 gate: where + how the real duration is obtained | Layer 2 settlement | Exact quota? |
|---|---|---|---|---|
| `spotify` | **audio** (currently `article`) | `podcastindex_resolution_worker` — already scrapes `music:duration` from the episode page (`podcast_platform_resolvers.py:416-424`), measured 0.91 s, free, exact | yes | **yes** |
| `apple_podcasts` | **audio** (currently `article`) | same worker — PodcastIndex `duration`, else **Range probe** on the resolved enclosure (measured exact, free) | yes | **yes** |
| `deezer` | **audio** (currently `article`) | same worker — `api.deezer.com/episode/{id}` `duration`, measured 0.36-0.73 s, free, exact | yes | **yes** |
| `rss` | audio (already correct) | same worker — `itunes:duration` when present (70-100 % feed-dependent), else **Range probe** | yes | **yes** |
| `direct_url` (audio file) | **audio** (currently `article` by default) | `orchestrators` / resolution worker — **Range probe** on the URL, measured +/-0.02 % | yes | **yes** |
| `whatsapp` (shared audio) | **audio** (currently unmetered) | bytes are local: probe the container in `ingest_shared_content`, ~ms, free | yes | **yes** |
| direct upload (`POST /media/upload-audio`) | **audio** (currently unmetered) | bytes are local, same probe | yes | **yes** |
| `youtube` | keep `youtube` for the caption path; **`audio` for the Deepgram fallback** (`youtube_ingestion_worker.py:1141`) | worker already has the yt-dlp `info` dict (`duration`), measured 1.47 s, free | yes | **yes** |
| `tiktok` | `article` for the subtitle path; **`audio` for the Deepgram fallback** (`tiktok_ingestion_worker.py:1231`) | worker already has yt-dlp/Apify metadata `duration`, measured 1.59 s | yes | **yes** |
| `instagram` | `article` (no Deepgram path today) | n/a — nothing to gate; `videoDuration` already in `metadata["duration_seconds"]` if a Deepgram path is added later | n/a | n/a |
| `x` | `article` (no Deepgram path today) | n/a | n/a | n/a |
| `web` | `article` | n/a — no audio | n/a | n/a |
| `unknown` | `article` (default) | **Range probe** if a media URL is resolved, otherwise Layer 2 only | yes | **best-effort** (see AC #4) |
| RSS auto-poll (`rss_feed_poll_worker`) | **audio** (currently unmetered) | feed item already parsed: `itunes:duration`, else Range probe | yes | **yes** |

### Overrun policy (the answer to AC #5)

**Let the stored counter exceed the cap; clamp only for display; never go negative; never refund; the next import is refused naturally.**

`entitlements.py:118` already computes `minutes_remaining = max(0, cap - used)`, so an `audio_minutes_used` of 312 against a 300 cap renders as `0 minutes remaining` with **no mobile change required**, while the true 312 stays in `user_usage_monthly` where cost telemetry and the cost hard-block need it. Clamping the *stored* value would corrupt the very counter that `check_submission_allowed` §5 uses to decide the cost hard-block.

### Effort and residual exposure

| Layer | Scope | Effort | Financial effect |
|---|---|---|---|
| 0 | `classify_media_type` + unify the two platform detections + add the 3 missing enforcement points | ~1 day | closes the two unmetered endpoints and the `text_only` tier bypass — **the largest single win** |
| 1 | one `check_and_debit(duration)` call in 4 workers + a shared Range-probe helper | ~2-3 days | caps the monthly overrun at one in-flight item (<= `max_audio_per_import_minutes`) |
| 2 | read `metadata.duration` in `deepgram_worker`, settle the delta under a conditional write | ~1 day | makes the counter exact to the second Deepgram actually bills |

Residual exposure after all three layers: **300 + 60 = 360 min/month** for a `mix` user (cap plus one in-flight 60-min item), i.e. **EUR 1.58** of Deepgram against **EUR 3.542** of net revenue — versus **up to EUR 224/month today, plus two endpoints with no ceiling at all** (section 2).

Layers 0 and 1 are worth doing even if the owner rejects Layer 2. Layer 2 alone is *not* sufficient.

---

## 1. What the code actually does today

The task description is correct but incomplete. Reading every quota call site (there are exactly four) turned up three further holes that change the cost of the bug by an order of magnitude.

### 1.1 The four quota call sites

| Call site | `source_platform` passed | `duration_seconds` passed |
|---|---|---|
| `api/endpoints/media.py:598` / `:641` — `POST /media/ingest-url` (the share intent) | `_detect_platform(url)` → only `youtube`, `tiktok`, `instagram`, `audio`, `web` | **0** at check; **0** at record |
| `api/endpoints/media.py:758` / `:829` — `POST /media/upload-document` | `"document"` | 0 (not audio) |
| `api/endpoints/podcasts.py:220` / `:275` — `POST /podcasts/submit` | `"audio"` or `"podcast"` (correct category) | **0** at check and record |
| `core/services/media_submission.py:57` / `:188` — in-app episode selection | `source or "audio"`, but the caller chain `podcast_search.py:286` → `episode_submission.py:53` leaves `source` at its default `"manual"` | **real duration** from PodcastIndex (`podcast_search.py:208-211`) |

The last row is the only path in the codebase that already knows the true duration at submission time — and `classify_media_type("manual")` falls through to the default `return QUOTA_CATEGORY_ARTICLE` (`quota_enforcer.py:61`), so the real minutes it computes are discarded and an `articles +1` is debited instead.

### 1.2 Hole 1 — four audio platforms never touch the audio counter

`classify_media_type` (`quota_enforcer.py:42-61`) returns `audio` only for `("podcast", "audio", "rss", "deepgram")`. Everything else falls to `article`. Consequences:

- `spotify`, `apple_podcasts`, `deezer`, `direct_url`, `manual` → **`articles +1`, `audio_minutes +0`**, even though every one of them ends up on `deepgram-transcription-queue` via `podcastindex_resolution_worker.py:321`.
- Because `_detect_platform` (`media.py:113-134`) returns `"web"` for `open.spotify.com`, `podcasts.apple.com`, `deezer.com` and any RSS feed URL, the **`text_only` tier gate never fires**: `check_submission_allowed` §1 (`quota_enforcer.py:235`) only refuses when `media_category == audio`. A Reader-tier subscriber (EUR 3.00, `audio_minutes_per_month: 0`) can transcribe podcasts all month against the `articles` cap of 500.
- The check and the record disagree on the category for RSS: the check uses `_detect_platform` → `web` → `article`, while the record uses `outcome.metadata["source_platform"]` → `rss` → `audio` (`media.py:643`). So `audio_minutes_used` can climb past a cap of 0 because no check ever compares it to that cap.

### 1.3 Hole 2 — two endpoints have no quota enforcement at all

`grep -rn "record_submission\|check_submission_allowed"` returns four call sites, and neither of these is among them:

- `POST /api/media/upload-audio` (`media.py:874-1057`) — enqueues straight to `DEEPGRAM_TRANSCRIPTION_QUEUE` at `media.py:1010`. No monthly cap, no daily rate limit, no cost check, no counter increment. The task assumed this path "escapes the bug because the duration is known locally"; in fact it escapes the quota system entirely.
- `POST /api/media/ingest-shared-content` (`media.py:1060+`) — the WhatsApp voice-note path. Same: unmetered.
- `workers/rss_feed_poll_worker.py:74` — automatic feed polling enqueues Deepgram transcriptions with no quota check and without `audio_duration_seconds`. Cost scales with followed feeds x new episodes, entirely outside the accounting.

### 1.4 Hole 3 — `duration_seconds = 0` disables two other guards

Passing 0 does not only make the monthly cap wrong:

- `check_submission_allowed` §2 (`quota_enforcer.py:243`) is wrapped in `if media_category == audio and duration_seconds > 0`. So **`audio_too_long`, `max_audio_per_import_minutes` (60 min on `mix`) and `max_audio_duration_minutes` (180 min) are dead code on every URL path.** A 6-hour episode is accepted.
- `estimate_submission_cost` (`quota_enforcer.py:453-456`) returns `round(1 * 0.008, 4)` = **EUR 0.008** per audio import, or the flat **EUR 0.005** when the platform is mis-classified as `article`. The cost hard-block at EUR 6.00 (`mix`) would need ~750-1 200 imports to trigger, so §5 never fires either.

### 1.5 Hole 4 — `minutes_used` in the event is not the real duration, and it is emitted twice

The task states that `deepgram_worker.py:686-695` "recomputes `minutes_used` from the real duration". It does not:

- `minutes_used` is derived from `message_body.get("audio_duration_seconds")` — a **hint supplied by the producer** — and falls back to `1` when absent (`deepgram_worker.py:687-696`). `podcastindex_resolution_worker.py:332` forwards `resolution.get("audio_duration_seconds") or 0`, and `rss_feed_poll_worker` sends nothing at all, so the hint is frequently 0 → `minutes_used = 1`. Reconciling on this field would reproduce the bug.
- `transcription_metadata["duration_seconds"] = transcription_duration` (`deepgram_worker.py:670`) is **wall-clock processing time**, not audio length, despite the name.
- The authoritative value is one line away and currently discarded: `extract_transcript` reads `payload["metadata"]` (`deepgram_worker.py:481`) for `request_id` and `language` but never `metadata["duration"]` — which is exactly what Deepgram bills on.
- The worker sends **two** messages carrying `minutes_used` to the same queue: `episode_completion_status` (`:698`) and `episode_completed` (`:722`); `media_completed_worker.py:121` accepts both plus the legacy `media_completed`. A naive debit in that consumer would therefore double-debit **every** job, before any SQS redelivery is considered.

---

## 2. Current financial exposure, quantified (AC #2)

### 2.1 Cost basis

| Item | Value | Source |
|---|---|---|
| Deepgram Nova-3 monolingual, pay-as-you-go | **USD 0.0048 / min** (Growth: USD 0.0042) | [deepgram.com/pricing](https://deepgram.com/pricing) |
| Same, in EUR at 1 USD = 0.92 EUR | **EUR 0.0044 / min** | FX assumption, 2026-08 |
| What the app assumes | **EUR 0.003 / min** (`pricing_config_service.py:156`) | repo |
| Understatement of the unit cost itself | **+47 %** | derived |
| All-in per audio minute per the app's own model | EUR 0.008/min (0.003 transcription + 0.005 LLM), i.e. **EUR 0.0094/min** at the real Deepgram rate | `quota_enforcer.py:454` |

Figures below use the **Deepgram-only EUR 0.0044/min floor**, which understates the true exposure by roughly 2x.

Net revenue per user per month (`pricing_config_service.py:42-62`): `text_only` EUR 2.125, `mix` EUR 3.542, `audio_heavy` EUR 6.375.

### 2.2 Per-platform ceiling for a single `mix` subscriber, one calendar month

Ceilings are the binding cap in `hard_caps.mix` / `rate_limits.mix`. "Avg min" is a stated assumption, not a measurement.

| Path | Quota category today | Counter debited per import | Binding ceiling | Avg min | Real minutes | Deepgram cost | Minutes debited | Factor |
|---|---|---|---|---|---|---|---|---|
| `rss` share | `audio` | `audio_minutes +1` | 300/mo (audio cap at 1 min/import; daily 10 x 30 = 300) | 60 | 18 000 | **EUR 79.20** | 300 | **60x** |
| `spotify` share | `article` | `articles +1` | 500/mo (`articles` cap) | 60 | 30 000 | **EUR 132.00** | **0** | **infinite** |
| `apple_podcasts` share | `article` | `articles +1` | 500/mo | 60 | 30 000 | **EUR 132.00** | **0** | **infinite** |
| `deezer` share | `article` | `articles +1` | 500/mo | 60 | 30 000 | **EUR 132.00** | **0** | **infinite** |
| `direct_url` (.mp3) | `article` (default) | `articles +1` | 500/mo | 60 | 30 000 | **EUR 132.00** | **0** | **infinite** |
| `youtube`, caption miss → Deepgram (`youtube_ingestion_worker.py:1141`) | `youtube` | `youtube +1` | 100/mo | 30 | 3 000 | EUR 13.20 | **0** | **infinite** |
| `tiktok`, subtitle miss → Deepgram (`tiktok_ingestion_worker.py:1231`) | `article` | `articles +1` | 500/mo | 1.5 | 750 | EUR 3.30 | **0** | **infinite** |
| `instagram` / `x` | `article` | `articles +1` | 500/mo | n/a | 0 (no Deepgram path) | EUR 0 | 0 | n/a |
| `POST /media/upload-audio` | **none** | **none** | **none** | 60 | **unbounded** | **unbounded** | **0** | **infinite** |
| `POST /media/ingest-shared-content` (WhatsApp) | **none** | **none** | **none** | 5 | **unbounded** | **unbounded** | **0** | **infinite** |
| `rss_feed_poll_worker` | **none** | **none** | followed feeds x new episodes | 45 | 3 600 (20 feeds x 4 ep) | EUR 15.84 | **0** | **infinite** |

The article-category rows share a **single** `articles` counter (500/mo), so they do not add up; the audio-category and youtube-category rows are independent counters and do.

**Combined worst case for one `mix` subscriber, URL shares only:** 300 audio-category + 500 article-category + 100 youtube-category imports = 900 imports/month. At 60 min for the audio-bearing ones: 18 000 + 30 000 + 3 000 = **51 000 min = 850 h → EUR 224.40/month of Deepgram against EUR 3.542 of net revenue.** The two unmetered endpoints add an unbounded amount on top.

### 2.3 The `text_only` (Reader) case is the worst per euro of revenue

A Reader subscriber (EUR 2.125 net, tier sold as "no audio transcription") shares Spotify/Apple/Deezer links. `_detect_platform` returns `web` → `article` → §1's tier gate never fires → 500 imports/month x 60 min = **30 000 min = EUR 132.00 of Deepgram on a EUR 2.125/month plan whose headline restriction is that it excludes exactly this.**

### 2.4 Expected loss, not just worst case

The worst case needs a deliberate abuser. The expected loss depends on the heavy-user tail. With stated assumptions — 100 `mix` subscribers, 5 % heavy (3 shares/day of 50 min), 95 % normal (6 shares/month of 50 min):

| Cohort | Real minutes/user/month | Real cost/user | Cohort cost |
|---|---|---|---|
| 5 heavy users | 90 imports x 50 = 4 500 | EUR 19.80 | EUR 99.00 |
| 95 normal users | 6 x 50 = 300 (exactly at cap) | EUR 1.32 | EUR 125.40 |
| **Total actual** | | | **EUR 224.40** |
| Total if the cap were exact (300 min each) | | EUR 1.32 | EUR 132.00 |
| **Overspend** | | | **EUR 92.40/month, i.e. 26 % of the EUR 354 gross** |

The overspend is linear in the heavy-user fraction and unbounded above, because nothing stops a heavy user before 300 *imports*.

### 2.5 Break-even, as a side finding

At EUR 0.0044/min, break-even is 805 min for `mix` and 1 449 min for `audio_heavy` — both above their caps, so the tiers are sound on transcription alone. At the app's own all-in EUR 0.0094/min, break-even is **377 min for `mix`** (cap 300, 20 % margin) and **678 min for `audio_heavy`** (cap **900**) — i.e. `audio_heavy` is **loss-making at full usage even with a perfectly exact quota** (900 x 0.0094 = EUR 8.46 vs EUR 6.375 net). That is a pricing question, out of scope here, but it is the reason quota accuracy matters: there is no margin to absorb a 60x error. Worth a separate task revisiting `task-65`'s EUR 0.003/min assumption.

### 2.6 Exposure after the recommended fix

| | Real minutes/month, `mix` | Deepgram cost | Enforceable per-import cap |
|---|---|---|---|
| Today | up to 51 000 (+ unbounded on 2 endpoints) | up to EUR 224.40 (+ unbounded) | no (`audio_too_long` is dead code) |
| After Layers 0+1+2 | **360** (300 cap + one in-flight item <= 60 min) | **EUR 1.58** | **yes** |

**142x reduction on the metered paths, and the unmetered paths become bounded.**

---

## 3. Option A, assessed per `SourcePlatform` (AC #3)

### 3.1 The hard latency ceiling

`infrastructure/terraform/modules/platform/lambda_api.tf:91-94` sets the API Lambda to `timeout = 30`, and the front door is an `aws_apigatewayv2_api` HTTP API, whose integration timeout is capped at **30 s** and cannot be raised. Anything inline in `POST /media/ingest-url` must therefore fit well inside 30 s; for a share sheet the usable budget is more like **2-3 s p95**.

### 3.2 Measurement method

All timings are `curl` wall-clock (`%{time_total}`) from this sandbox (EU egress) on **2026-08-12**, against live third-party endpoints. Sample counts are given per row; first-call figures are marked *cold* because TLS/DNS setup dominates them. These are single-digit sample counts, not p95 over a fleet: they establish an order of magnitude and, more importantly, **which mechanism yields an exact number at all**. Reference episode: *Lex Fridman #500 (Khabib Nurmagomedov)*, true duration **11 992 s** (3 h 20).

### 3.3 Per-platform results

| `SourcePlatform` | Duration before acceptance? | Mechanism | Third-party cost | Measured latency | Coverage / accuracy |
|---|---|---|---|---|---|
| `spotify` | **yes** | `GET open.spotify.com/episode/{id}` → `<meta property="music:duration">` (already implemented, `podcast_platform_resolvers.py:416-424`) | free | **0.91 s** (1 sample, 217 KB) | value 11 971 vs true 11 992 → **-0.2 %**. Spotify **computes** it, so it is present even when the source feed omits it. Fragile: undocumented markup |
| `spotify` (documented alt.) | yes | Web API `GET /v1/episodes/{id}` → `duration_ms` (required field) | free, but **OAuth client-credentials required** and `market` must be supplied — *"If neither market or user country are provided, the content is considered unavailable for the client"* | not measured (needs credentials the repo does not have) | exact |
| `spotify` oEmbed | **no** | `open.spotify.com/oembed` | free | 0.29 s, 884 B | **no duration field at all** |
| `apple_podcasts` | **partially** | `itunes.apple.com/lookup?id={showId}&entity=podcastEpisode&limit=50` → match `trackId` → `trackTimeMillis` | free, ~20 req/min guidance | **0.37 / 0.40 / 0.42 s** (3 samples, 230 KB); `limit=200`: 0.64 s and 2.38 s, 853 KB | **35/50** episodes carry `trackTimeMillis`, and it is **absent on the newest** (#500 → `null`). Apple **mirrors the feed**, it does not compute. `lookup?id={episodeTrackId}` returns `resultCount: 0` — episode track ids are not directly resolvable, you must page the show |
| `deezer` | **yes** | `GET api.deezer.com/episode/{id}` → `duration` (already implemented, `podcast_platform_resolvers.py:1253`) | **free, no auth** | **0.36 / 0.41 / 0.73 s** (3 samples, 4.7 KB) | `duration = 11992` = exact. Deezer **computes** it (present on #500 where the feed has nothing). Episode list: `GET /podcast/{id}/episodes` 0.43 s |
| `rss` | **mostly** | feed fetch → `<itunes:duration>` (already implemented, `podcast_platform_resolvers.py:1630`) | free | lexfridman.com **1.74 / 1.77 s** (2.10 MB, *cold 3.1 s*); feeds.npr.org/510289 **1.39 s** (2.13 MB); changelog.com **2.26 s** (6.24 MB) | **feed-dependent: 447/501 (89 %), 355/355 (100 %), 1012/1012 (100 %)**. Where there is a gap it is **concentrated on the newest items** — on lexfridman.com only **3 of the newest 5** and **4 of the newest 10** carry a duration. Formats differ (`2364` vs `2:06:48`) |
| `rss` enclosure `length` | **no** | `<enclosure length="...">` | free | 0 | declared **5 242 880** vs real **143 915 525** → **27.4x wrong** (a 5 MiB placeholder). Unusable |
| any resolved audio URL — `HEAD` only | **no** | `HEAD` → `Content-Length` + bitrate guess | free | 1.42 - 2.06 s | error **-50 %** (192 kbps guess) to **0 %** (96 kbps guess) on the same file. Unusable as a billing basis; only as a conservative upper bound |
| any resolved audio URL — **HTTP Range container probe** | **yes** | one ranged `GET bytes=0-65535`: `Content-Range` gives the total size, the first 10 bytes give the ID3v2 tag length, the first MPEG frame header gives bitrate/sample rate, `Xing`/`Info` gives the exact frame count | **free** (64-70 KB of bandwidth) | **1 request: 1.37 s** (Blubrry/CloudFront) and **1.69 s** (podtrac→swap.fm→Simplecast chain); **2 requests: 1.67 + 1.18 = 2.85 s** when the ID3 tag exceeds the window | **+0.01 %, +0.01 %, -0.02 %** on the three files tested (see 3.4). All three CDNs honour `Range` and return the total size |
| `youtube` | **yes** | Data API `videos.list?part=contentDetails` → ISO-8601 `duration`; or the yt-dlp `info` dict the worker already builds | Data API: **1 quota unit**, 10 000 units/day free; yt-dlp: free | yt-dlp metadata-only **1.47 s** (duration 213 s) | exact. Note: YouTube's normal path uses captions, no Deepgram; only the caption-miss fallback spends money |
| `tiktok` | **yes, but not for free** | yt-dlp metadata-only, or the Apify actor the worker already calls | yt-dlp free; Apify ~USD 2.30-2.60 / 1 000 results | yt-dlp **1.59 s** (duration 10 s); **oEmbed 0.80 s has no duration field** | exact via yt-dlp; TikTok clips are short so the exposure is small either way |
| `instagram` | **yes, but not within 30 s** | `InstagramApifyResolver` runs **synchronously in the API request** today and exposes `videoDuration` → `metadata["duration_seconds"]` | Apify Reel Scraper ~USD 2.30-2.60 / 1 000 (`task-107` benchmark) | yt-dlp path ~1.6 s; **Apify path up to ~120 s** (`APIFY_MAX_POLLS=40` x `APIFY_POLL_INTERVAL_SECONDS=3`) — **exceeds the 30 s API Gateway cap** | no Deepgram path today, so nothing to gate |
| `x` | **no reliable free source** | yt-dlp works for some video posts; X API v2 is paid | paid or unreliable | not measured | no Deepgram path today |
| `whatsapp` (shared audio) | **yes, trivially** | bytes are local in `ingest_shared_content`; probe the container | free | ~ms | exact |
| direct upload (`upload-audio`) | **yes, trivially** | same | free | ~ms | exact |
| `web` | n/a | no audio | — | — | — |
| `direct_url` | **yes** | Range container probe | free | 1.37 - 2.85 s | +/-0.02 % |
| `unknown` | **no, by definition** | nothing to resolve until the classifier decides | — | — | see AC #4 |

### 3.4 The Range container probe, measured in detail

This mechanism is not in the codebase and is the single most useful finding of this benchmark: it produces an **exact** duration for **any** direct MP3 URL, for free, in one or two HTTP round trips. Method: read `Content-Range` for the total size, `data[6..9]` (syncsafe integer) for the ID3v2 tag length, then the first `0xFFEx` MPEG frame header for bitrate and sample rate, then `Xing`/`Info`/`VBRI` within that frame for an exact frame count.

| File | CDN / redirect chain | Requests | Latency | ID3 tag | Frame header | Computed | True | Error |
|---|---|---|---|---|---|---|---|---|
| Lex Fridman #500 | media.blubrry.com → CloudFront | **1** (64 KB) | 1.37 s | 1 925 B | 96 kbps / 48 kHz, no Xing (CBR) | 11 992.8 s | 11 992 s | **+0.01 %** |
| Planet Money, newest | tracking.swap.fm → podtrac → Simplecast | **1** (64 KB) | 1.69 s | 77 B | 128 kbps / 44.1 kHz | 2 364.3 s | 2 364 s | **+0.01 %** |
| The Changelog #683 | op3.dev → pscrb.fm → cdn.changelog.com | **2** (64 KB + 4 KB) | 1.67 + 1.18 s | **196 875 B** (chapters/artwork) | 192 kbps / 48 kHz, `Info` header, 316 931 frames | 7 606.3 s | 7 608 s | **-0.02 %** |

Notes and limits:

- The 64 KB first window covers files whose ID3v2 tag is smaller than 64 KB (2 of 3 here). Larger tags need a second 4 KB ranged GET at the tag offset, which the first response already tells you.
- All three servers returned `accept-ranges: bytes` and a `Content-Range` carrying the total size, so **no separate `HEAD` is needed**.
- Verified for **MP3**, the dominant podcast container. **M4A/AAC** requires the MP4 `mvhd` box, which in non-streaming-optimised files sits at the *end* — a tail Range request. **Untested here; must be validated during implementation**, with the Layer 2 settlement as the safety net.
- An earlier attempt using `ffprobe` on a truncated 256 KB / 1 MB prefix failed on a file with a large ID3 tag; parsing the headers directly avoids depending on `ffmpeg` in the Lambda bundle.

### 3.5 Verdict on Option A as literally stated

| Platform | Inline p95 budget needed in `ingest-url` | Fits a 2-3 s share budget? |
|---|---|---|
| `deezer` | ~0.7 s (1 call) | yes |
| `spotify` | ~0.9 s (1 page fetch) | yes |
| `apple_podcasts` | 0.4 s happy path; **~5.1 s worst case** (lookup 0.4 + feed 1.8 + Range probe 2.9) | no |
| `rss` | 1.4-2.3 s happy path; **~5.2 s worst case** | no |
| `direct_url` | 1.4-2.9 s | borderline |
| `youtube` / `tiktok` | 1.5-1.6 s (yt-dlp cold start in-request is worse) | borderline |
| `instagram` | **up to 120 s** | **impossible** (30 s API Gateway cap) |
| `x`, `unknown` | no mechanism | no |

So Option A **cannot** be applied uniformly at the API boundary. It also duplicates third-party calls the resolution workers already make, doubling Apify spend on the social paths. This is what motivates Layer 1: keep the mechanisms of Option A, move them to where they already run.

---

## 4. Platforms where no pre-acceptance duration is reliably obtainable (AC #4)

Naming them explicitly, as required, with the fallback for each. "Reliably" means: available for **every** item of that platform, without a paid call, and exact.

| Platform / path | Why not reliable | Fallback |
|---|---|---|
| **`unknown`** | By definition the classifier has not identified the source, so there is no metadata endpoint to call and possibly no media URL. | **Layer 2 only.** Accept, debit a provisional 1 minute, settle from Deepgram's `metadata.duration`. Residual over-cap exposure bounded by one item. |
| **`apple_podcasts`** | `trackTimeMillis` mirrors the RSS feed and is **absent on the newest episodes** (measured: `null` on Lex #500, 35/50 present overall). PodcastIndex `duration` is also feed-derived, so it inherits the same gap. | Range container probe on the enclosure the resolver has already found (**exact, free, +1.4-2.9 s inside the worker, 0 ms on the share**). |
| **`rss`** | `<itunes:duration>` coverage is feed-dependent (measured 89 %, 100 %, 100 %) and, where it is missing, **missing precisely on the recent items users share** (3/5 newest on lexfridman.com). `<enclosure length>` is a placeholder 27x off. | Same Range container probe. |
| **`x`** | No free public duration metadata; X API v2 is paid; yt-dlp coverage is partial and breaks often. | No Deepgram path exists today, so no exposure. If one is added: Range probe on the resolved media URL, else Layer 2. |
| **`instagram`** | Duration *is* available (`videoDuration`) but only after an Apify run that can take ~120 s — impossible within the 30 s API Gateway ceiling, and it costs ~USD 0.0025 per call. | No Deepgram path today. If one is added: gate inside `instagram` resolution (duration already in `metadata["duration_seconds"]`), never inline. |
| **`spotify`** (strictly speaking) | The working mechanism is an **undocumented page scrape** of `music:duration`. It can break with any front-end change. | Documented Web API `duration_ms` (needs OAuth client-credentials + `market`), then the Range probe on the PodcastIndex-resolved enclosure, then Layer 2. Three levels deep, so effectively reliable. |
| **M4A/AAC enclosures on any platform** | The Range probe was only validated on MP3. `moov`/`mvhd` may sit at the end of the file. | Tail Range request; if that fails, Layer 2. |

**Conclusion for AC #4: `unknown` is the only value for which neither option yields an exact quota before the spend.** For `apple_podcasts` and `rss`, the platform metadata alone is not reliable, but the Range probe closes the gap exactly and for free — so they are exact under Layer 1. `x` and `instagram` have no Deepgram path today, so they carry no audio exposure at all.

### 4.1 What happens when resolution fails or exceeds its budget

Because Layer 1 sits inside the resolution workers, "resolution failed" is **not a new failure mode**: a job whose audio URL cannot be resolved already fails today (`podcastindex_resolution_worker.py:112-120`, `RuntimeError` with `AUDIO_URL_NOT_FOUND`), and no legitimate share is refused for a quota reason it did not deserve. The decision table:

| Situation | Behaviour | Rationale |
|---|---|---|
| Duration obtained, within quota | debit the real minutes, enqueue Deepgram | the intended path |
| Duration obtained, over the monthly cap | fail the job with `quota_exceeded`, **do not** enqueue Deepgram, surface it in the mobile list | the spend is avoided; `task-244` already handles quota refusals client-side |
| Duration obtained, over `max_audio_per_import_minutes` | same, error code `audio_too_long` | this guard becomes live for the first time |
| Duration not obtainable (probe fails, `unknown`, exotic container) | **accept**, debit a provisional 1 minute, enqueue Deepgram, settle in Layer 2 | never refuse a legitimate share on a metadata failure; exposure bounded by one item |
| Probe exceeds its time budget (recommend 5 s, worker timeouts are 60-600 s so there is room) | same as "not obtainable" | latency inside a worker is invisible to the user |
| Resolution itself fails | job fails as it does today, no debit | unchanged |

The user-visible cost of Layer 1 versus literal Option A is that a quota refusal arrives **asynchronously** (job in `failed` state with a quota error code) instead of as a synchronous 403 on the share. Two mitigations: (a) the `text_only` tier gate and the "monthly cap already reached" case are both decidable **without** any duration, so they stay synchronous 403s at zero latency once Layer 0 fixes the classification; (b) only the "this specific episode is too long / would exceed the remaining balance" case becomes asynchronous, and `task-244` already provides the paywall trigger for a quota refusal.

---

## 5. Option B, assessed (AC #5)

### 5.1 Where to hook it, and what the event actually carries

The task suggests `media_completed_worker` as the consumer. **That is the wrong place**, for three reasons found in the code:

1. **The field is not the real duration.** `minutes_used` comes from the producer's `audio_duration_seconds` hint and defaults to `1` (`deepgram_worker.py:687-696`). `rss_feed_poll_worker` never sends the hint; `podcastindex_resolution_worker.py:332` sends `or 0`. Reconciling on this field reproduces the bug it is meant to fix.
2. **The event is emitted twice.** `episode_completion_status` (`deepgram_worker.py:698`) and `episode_completed` (`:722`) both carry `minutes_used` to the same queue, and `media_completed_worker.py:121` accepts both plus legacy `media_completed`. A debit there double-debits **every** job even with zero redelivery.
3. **The authoritative value never leaves the transcription worker.** Deepgram returns `metadata.duration` (audio seconds — the quantity it bills on; visible in the response sample in the [pre-recorded audio docs](https://developers.deepgram.com/docs/pre-recorded-audio)), and `extract_transcript` already reads `payload["metadata"]` (`deepgram_worker.py:481`) for `request_id`/`language` while discarding `duration`.

**Recommendation: settle inside `deepgram_worker`, from `metadata.duration`, immediately after `extract_transcript`.** One reader, one writer, one source of truth, no event contract to change. `minutes_used` in the events can then be corrected to the real value for observability, but nothing bills off it.

### 5.2 The idempotency problem, precisely

| Fact | Source |
|---|---|
| `increment_monthly_usage` issues `UpdateExpression = "ADD ... SET #lu = :lu"` with **no `ConditionExpression`** | `utils/quota_usage_db.py:141` |
| `deepgram-transcription` is a **standard** SQS queue, `visibility_timeout_seconds = 3600`, `maxReceiveCount = 3` | `infrastructure/terraform/modules/platform/sqs.tf:187-192` |
| `episode-completed-events` is standard too, `visibility_timeout_seconds = 360`, `maxReceiveCount = 3` | `sqs.tf:327-333` |
| Standard queues are **at-least-once**; a message can be delivered more than once even without a failure | [AWS SQS standard queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html) |
| The worker also **re-enqueues** to its own queue on some paths (`deepgram_worker.py:763`, `:868`) | repo |

So an unguarded delta debit would over-charge on: (a) any SQS redelivery, up to 3x; (b) the double event emission, 2x; (c) the worker's own re-enqueue paths. A double debit is a **false quota refusal for a paying user** — the exact failure mode `task-251` calls out.

### 5.3 The idempotency solution

The codebase already uses conditional writes for exactly this purpose: `utils/user_media.py:103` does `put_item` under `ConditionExpression="attribute_not_exists(media_item_id)"`, and `user_media.py:204` updates under `attribute_exists(media_item_id)`. Two viable variants:

**Variant 1 (recommended) — one atomic conditional `ADD` on the usage item.** Extend `increment_monthly_usage` with an optional settlement token:

```
UpdateExpression:      ADD audio_minutes :m, settled_jobs :jobset  SET #lu = :lu
ConditionExpression:   attribute_not_exists(settled_jobs) OR NOT contains(settled_jobs, :job)
```

`settled_jobs` is a DynamoDB string set; `ADD` on a set is a union, and the condition makes the whole debit a no-op on replay. Atomic: no window between "record the receipt" and "debit". Item-size bound: the `audio_heavy` daily rate limit is 20 audio imports/day, so <= 620 job ids/month x ~36 B = **~22 KB**, well inside the 400 KB item limit; the item is per `(user_id, period)` so it resets monthly. The `attribute_not_exists(...) OR NOT contains(...)` shape must be verified against DynamoDB's evaluation of `contains` on a missing attribute at implementation time.

**Variant 2 — receipt on the job / durable media row.** Write `quota_settled_minutes` under `attribute_not_exists(quota_settled_minutes)` on the `user_media` row and debit only if that write succeeds. `durable_media_service.py:295-346` already writes `duration_seconds` onto that row from `extraction_metadata["audio_duration_seconds"]` (task-240), so the anchor exists and `user_media.update_attributes` already supports conditional writes. Downside: two writes, so a crash between them loses the debit (fails **open**, which is the safer direction, but it is not atomic).

Either way the guard belongs to the **debit**, not to the event consumer, so it also protects against the double emission and any future producer.

### 5.4 What happens to an overrun detected after the fact — explicit answer

The three options in the task, decided:

| Option | Verdict | Why |
|---|---|---|
| **Negative balance** (let `minutes_remaining` go below zero) | **rejected** | `entitlements.py:118` already returns `max(0, cap - used)`, and a negative number displayed to a paying user reads as a debt. Nothing in the product can collect it. |
| **Clamp the stored counter at the cap** | **rejected** | it destroys the information. `check_submission_allowed` §5 (`quota_enforcer.py:341-345`) blocks on `cost_eur_estimated`, and the cost-monitoring alarms and any future margin analysis read the same row. Clamping makes a 60x overrun indistinguishable from normal usage. |
| **Store the truth, clamp for display, refuse the next import** | **recommended** | `audio_minutes_used = 312` against a cap of 300 renders as `0 minutes remaining` with **no mobile change** (`entitlements.py:118` already clamps), `check_submission_allowed` §3 refuses the next audio import naturally (`312 + n > 300`), and the true figure stays where cost telemetry needs it. |

Additional decisions that follow:

- **Never retroactively cancel or delete an already-transcribed item.** The money is spent and the user has the content; removing it is a worse product outcome than a one-item overrun.
- **Never refund minutes on failure** beyond not debiting them in the first place: if Deepgram fails, no `metadata.duration` exists, so nothing is settled — the provisional 1 minute stays debited. Over-charging by 1 minute on a failed job is acceptable; the alternative (a compensating credit) needs its own idempotency guard for no material gain.
- **Do not double-debit the paths that already know the duration.** With Layer 1 in place, every path debits exactly once at the gate and then settles a *delta* in Layer 2 (`delta = ceil(deepgram_duration/60) - already_debited_minutes`), which is 0 whenever the gate already had the exact value. The `settled_jobs` guard makes the delta computation replay-safe. This is the answer to `task-251` scope item 4.

### 5.5 The residual gap Option B cannot close, quantified

The task correctly notes that Option B fixes the accounting, not the prevention: nothing stops a user with 1 minute left from launching a 3-hour podcast. Under Layer 1 that gap becomes **bounded and small**:

| | Worst single over-cap item | Cost |
|---|---|---|
| Option B alone | unbounded (no per-import cap is enforceable without a pre-spend duration) | e.g. a 6 h episode = 360 min = EUR 1.58 in one shot |
| Layers 1+2 | `max_audio_per_import_minutes` = **60 min** (`mix`) / 90 min (`audio_heavy`), now enforceable for the first time | **EUR 0.26** / EUR 0.40 |

That is the concrete reason Layer 1 is worth its 2-3 days: it turns `audio_too_long` from dead code into the bound on the residual exposure.

---

## 6. Options considered and rejected

| Option | Why rejected |
|---|---|
| **Literal Option A** — resolve inline in `POST /media/ingest-url` | +0.4 s to +5.2 s of share latency depending on platform; impossible for `instagram` (Apify up to 120 s vs a 30 s API Gateway ceiling); duplicates third-party calls the workers already make, doubling Apify spend on social paths. Section 3.5. |
| **Literal Option B alone** — debit the delta in `media_completed_worker` | the field it would read is a producer hint that defaults to 1 (5.1); the event is emitted twice so it double-debits every job; and it cannot enforce `max_audio_per_import_minutes`, leaving the single-item overrun unbounded (5.5). |
| **Pessimistic reservation** — debit `max_audio_per_import_minutes` (60 min) up front, refund the difference after transcription | needs a refund path, hence a second idempotency guard; and it makes `minutes_remaining` collapse by 60 the moment a share is accepted, which is a worse lie than today's counter. |
| **Charge per import with an explicit "imports" cap** — i.e. keep the current behaviour and rename the counter | honest, and it would fix the mobile label, but it does not fix the money: the exposure in section 2 is unchanged, and `audio_heavy` has no margin to absorb it (2.5). Rejected on cost, not on honesty. |
| **`ffprobe`/`ffmpeg` on a downloaded prefix** | needs `ffmpeg` in the Lambda bundle, and it failed on a truncated prefix of a file with a 196 KB ID3 tag. Parsing the ID3 length and the MPEG frame header directly is ~30 lines, has no binary dependency, and was exact on all three files tested (3.4). |
| **Trust PodcastIndex `duration` everywhere** | it is feed-derived, so it inherits the exact gap measured on Apple/RSS (missing on the newest episodes). The code already treats `0` as unknown (`podcastindex_resolution_worker.py:130`), which is evidence the gap is real in production. |
| **Trust `<enclosure length>` and a bitrate constant** | measured 27.4x wrong on the reference file (a 5 MiB placeholder), and a bitrate guess is -50 % to 0 % wrong (3.3). |

---

## 7. What this benchmark does not solve

Stated explicitly, as required by the task ("ne pas masquer les plateformes où aucune des deux options ne donne un quota exact"):

1. **`unknown` remains inexact before the spend.** Layer 2 makes the *accounting* exact after the fact; the prevention is limited to one item.
2. **M4A/AAC enclosures are unvalidated** for the Range probe. Must be checked during implementation; Layer 2 is the net.
3. **The LLM cost side is untouched.** Summarisation cost scales with transcript length too, and `estimate_submission_cost` bills a flat EUR 0.005 for non-audio items. Out of scope here.
4. **Tier sizing and pricing are out of scope**, but section 2.5 shows `audio_heavy` is loss-making at full usage at the real Deepgram rate, and that `providers.transcription.cost_per_minute_eur = 0.003` understates the PAYG rate by 47 %. Worth a separate task revisiting the `task-65` assumptions.
5. **No implementation is included** (AC #7). `quota_enforcer.py`, the endpoints and the workers are unmodified in this task; `git diff --stat` for this commit touches only `docs/research/` and the backlog task file.

---

## 8. Sources

### Third-party APIs and pricing

- Deepgram pricing (Nova-3 monolingual PAYG USD 0.0048/min, Growth USD 0.0042/min): https://deepgram.com/pricing
- Deepgram pre-recorded audio response, `metadata.duration`: https://developers.deepgram.com/docs/pre-recorded-audio
- Spotify Web API, `GET /episodes/{id}` (`duration_ms`, OAuth, `market` caveat): https://developer.spotify.com/documentation/web-api/reference/get-an-episode
- Deezer public API, `/episode/{id}` and `/podcast/{id}/episodes`: https://developers.deezer.com/api/episode
- iTunes Search API / `lookup` (`entity=podcastEpisode`, `trackTimeMillis`, rate guidance): https://performance-partners.apple.com/search-api
- YouTube Data API quota costs (`videos.list` = 1 unit, 10 000 units/day default): https://developers.google.com/youtube/v3/determine_quota_cost
- Podcasting namespace / `itunes:duration` semantics: https://help.apple.com/itc/podcasts_connect/#/itcb54353390
- Apify Instagram actor pricing (USD 2.30-2.60 / 1 000 results): https://apify.com/store — as costed in `docs/research/task-107-instagram-extraction-benchmark/README.md`

### AWS behaviour relied upon

- SQS standard queues are at-least-once, duplicates possible: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html
- API Gateway HTTP API integration timeout ceiling (30 s): https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html
- DynamoDB `ADD` on number/set attributes and conditional expressions: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html
- DynamoDB 400 KB item size limit: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ServiceQuotas.html

### Container formats

- ID3v2 tag header, syncsafe size integer: https://id3.org/id3v2.3.0
- MPEG audio frame header (bitrate / sample-rate tables): http://www.mp3-tech.org/programmer/frame_header.html
- Xing / Info / VBRI headers and exact frame counts: http://gabriel.mp3-tech.org/mp3infotag.html
- HTTP Range requests, `Content-Range` total length: https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests

### Repository evidence

- `media_summarizer/core/services/quota_enforcer.py` — `classify_media_type:42-61`, tier gate `:235`, per-import guard `:243`, monthly caps `:283`, cost block `:341`, `record_submission:378-437`, `estimate_submission_cost:440-459`
- `media_summarizer/api/endpoints/media.py` — `_detect_platform:113-134`, `ingest_url` quota `:598`/`:641`, `upload_document` `:758`/`:829`, `upload_audio:874-1057` (**unmetered**, Deepgram enqueue at `:1010`), `ingest_shared_content:1060+` (**unmetered**)
- `media_summarizer/api/endpoints/podcasts.py:220`/`:275` — `duration_seconds=0`
- `media_summarizer/core/services/media_submission.py:57`/`:188` — real duration, `source` default `"manual"` → `article`
- `media_summarizer/api/endpoints/podcast_search.py:208-211`/`:286` — the only site with a real duration at submission
- `media_summarizer/workers/transcription/deepgram_worker.py` — `extract_transcript:461-496` (`metadata.duration` discarded), wall-clock `duration_seconds:670`, `minutes_used:687-696`, double event emission `:698` and `:722`, self re-enqueue `:763`/`:868`
- `media_summarizer/workers/podcastindex_resolution_worker.py:130`/`:332` — `audio_duration_seconds or 0`; Podcasting 2.0 short-circuit `:137-262`
- `media_summarizer/workers/podcast_platform_resolvers.py` — Spotify `music:duration` `:416-424`, Apple PodcastIndex `duration` `:894`, Deezer `duration` `:1253`, RSS `_extract_episode_duration` `:1630`
- `media_summarizer/workers/youtube_ingestion_worker.py:1141` and `media_summarizer/workers/tiktok_ingestion_worker.py:1231` — Deepgram fallbacks on caption/subtitle miss
- `media_summarizer/workers/rss_feed_poll_worker.py:74` — unmetered Deepgram enqueue
- `media_summarizer/utils/quota_usage_db.py:141`/`:232` — unconditional `ADD`
- `media_summarizer/utils/user_media.py:103`/`:204` — existing conditional-write pattern
- `media_summarizer/core/services/durable_media_service.py:295-346` — durable `duration_seconds` anchor (task-240)
- `media_summarizer/api/endpoints/entitlements.py:118` — `minutes_remaining = max(0, cap - used)` (already display-clamped)
- `media_summarizer/core/services/pricing_config_service.py:34-157` — tiers, caps, rate limits, cost monitoring, `cost_per_minute_eur: 0.003`
- `media_summarizer/core/media_ingestion/domain.py:31-43` — the `SourcePlatform` enum covered in section 3
- `infrastructure/terraform/modules/platform/lambda_api.tf:91-94` — API Lambda `timeout = 30`
- `infrastructure/terraform/modules/platform/sqs.tf:187-192`, `:327-333` — standard queues, `maxReceiveCount = 3`
- `docs/research/task-196-worker-timeouts-audit/README.md` — worker timeout/latency budgets used in section 4.1
- `docs/research/task-107-instagram-extraction-benchmark/README.md` — Apify per-1 000-result pricing

### Live measurements

All `curl` timings, byte counts, feed coverage counts and container-probe results in sections 3.3 and 3.4 were taken from this sandbox on **2026-08-12** against the live endpoints listed above. Reference episode: *Lex Fridman Podcast #500*, true duration 11 992 s, cross-validated across three independent sources (Deezer API `11992`, Spotify `music:duration` `11971`, Range probe `11992.8`).
