---
owner_decision: ok
---

# Benchmark : mise en forme du transcript pour le viewer media (task-231)

**Evidence base**: repository code read at commit `29e970e` (branch `main`), Deepgram public API and pricing documentation (August 2026), React Native 0.83 documentation, plus quantitative simulations executed against the *actual* repo functions (`_format_plain_text`, `_split_sentences`) and a storage sizing model. No source file was modified by this benchmark.

## Owner Validation

**Decision**: option B
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Adopt Option B — "structured plain text with a single shared normalizer, applied both at write time and at read time".**

Concretely:

1. **Keep the canonical S3 transcript object as plain UTF-8 text** (`{job_id}.txt`, `text/plain`), unchanged key scheme, unchanged content type. Do **not** switch it to JSON.
2. **Stop throwing away Deepgram's paragraph structure.** `extract_transcript()` must prefer `results.channels[0].alternatives[0].paragraphs.transcript` — which Deepgram already returns today, already blank-line delimited, at **+0.3 % storage** and **$0 extra cost** — over the flat `alternatives[0].transcript` currently used (`media_summarizer/workers/transcription/deepgram_worker.py:458`).
3. **Create one shared normalizer module** (`media_summarizer/core/services/transcript_formatting.py`) that turns any transcript shape into paragraph-delimited plain text, and call it from **every** producer before upload (Deepgram, YouTube/Apify, YouTube native captions, TikTok, X, article, RSS/PodcastIndex, orchestrators) so all 8 write sites emit the same readable shape.
4. **Call the same normalizer at read time** in `raw_content_service._format_content()`. Because the normalizer is idempotent (text that already contains blank-line separators passes through untouched), this single property removes the need for **any S3 data migration**: legacy transcripts get structured on the fly, new transcripts arrive pre-structured. Zero backfill, zero artifact-fingerprint churn, zero translation-cache invalidation.
5. **Render one selectable Text node per paragraph** in `TranscriptContent` (`mobile/app/media/[id].tsx:1128-1178`), separated by `Spacing.md`, with `lineHeight` fixed to the design-system value `Typography.body.lineHeight` (25.6) instead of the hardcoded `24`. Keep the existing `ScrollView`; no virtualization needed at the measured volumes (about 120 paragraphs for a 1-hour transcript).
6. **Speaker labels: ship the rendering, but keep diarization OFF by default.** Implement the `Speaker N:` prefix parsing and label styling so it works the day diarization is enabled, and expose diarization behind the existing env-var pattern (`DEEPGRAM_DIARIZE`, default `false`). Diarization is a **paid Deepgram add-on at $0.0020/min, i.e. +41.7 % over the current Nova-3 promotional line item**; that is an owner pricing decision, not a formatting decision.
7. **Timestamps: do not display them in V1.** The mobile app has no audio player (no `expo-av` / `expo-audio` in `mobile/package.json`), so a timestamp is a non-actionable decoration. Revisit as part of a player task.

**Rejected options** (details in section 6): storing the raw Deepgram JSON as the canonical object (x42.6 storage, breaks the 4 text consumers), a compact structured JSON sidecar in V1 (+2.2 % storage but silently degrades in translated mode), client-only heuristic re-paragraphing (proven to produce **1 paragraph** on the two most common non-Deepgram inputs), an LLM re-paragraphing pass ($6.08 per 1000 hours for a problem solvable for free), a read-time-only fix without touching the producers (throws away free model-derived structure), an S3 backfill migration (unnecessary and costly), sentence-level timings (+32.2 % storage), and a "reading mode / raw mode" toggle (no user value, added state).

**Estimated effort**: about 1.5 to 2 days total — backend normalizer plus 8 call sites plus dead-code removal (about 1 day), mobile rendering (about 0.5 day). No infrastructure change, no Terraform change, no schema change, no migration script.

---

## Table of contents

1. Problem statement and measured evidence
2. What Deepgram actually returns (and what we discard)
3. Storage format analysis: plain text vs structured JSON
4. Cross-source impact: the 8 transcript producers
5. Options compared
6. Rejected options and why
7. Speaker labels and timestamps: feasibility and cost
8. Translation pipeline compatibility
9. Migration of existing transcripts
10. Target design
11. UI implementation plan (React Native)
12. Dead code to delete
13. Side findings
14. Open questions for the owner
15. Sources

---

## 1. Problem statement and measured evidence

### 1.1 The three layers of the defect

The unreadable transcript is not one bug, it is three independent failures stacked on top of each other:

| Layer | Where | What happens |
|---|---|---|
| **L1 — structure discarded at ingestion** | `media_summarizer/workers/transcription/deepgram_worker.py:452-478` | Deepgram is asked for `paragraphs=true` and `utterances=true` and returns both. `extract_transcript()` reads them **only to count segments** (line 471) and then returns the *flat* string. The paragraph structure never reaches S3. |
| **L2 — read-time formatter always falls into its weakest branch** | `media_summarizer/core/services/raw_content_service.py:485-532` | `_detect_source_format()` can return `deepgram_json` and route to a complete, already-written Deepgram formatter — but nothing ever writes Deepgram JSON to S3, so that branch is **unreachable**. Every transcript takes `_format_plain_text()` (line 723), a fixed "one paragraph every 5 sentences" heuristic. |
| **L3 — UI renders one giant Text node** | `mobile/app/media/[id].tsx:1138`, `:1156`, `:1175` | `<Text style={styles.transcriptBody}>{state.content}</Text>`. Any blank-line separator the backend does send renders as a bare line break with **no paragraph spacing**, because `transcriptBody` (line 1645) has only `paddingVertical`, no inter-paragraph margin. |

### 1.2 Code evidence table

| Fact | File:line | Evidence |
|---|---|---|
| Deepgram is asked for paragraphs and utterances | `deepgram_worker.py:113-121` | `"paragraphs": str(DEEPGRAM_PARAGRAPHS).lower(), "utterances": str(DEEPGRAM_UTTERANCES).lower()` |
| Those flags plus `smart_format` and `punctuate` all default to `true` | `deepgram_worker.py:88-92` | four `os.environ.get(..., "true")` |
| **No `diarize` / `diarize_model` parameter is sent at all** | `deepgram_worker.py:113-121` | the query dict has exactly 6 keys, none of them diarization |
| Only the flat transcript string is extracted | `deepgram_worker.py:458` | `transcript_text = (alt.get("transcript") or "").strip()` |
| Utterances and words are read then dropped | `deepgram_worker.py:462-471` | `segments_count = len(utterances) if utterances else len(words)` |
| Stored as `text/plain` under `{job_id}.txt` | `deepgram_worker.py:642-643` and `:140-153` | `transcript_s3_key = f"{job_id}.txt"`, `content_type="text/plain"` |
| Job model stores only a key plus free-form metadata (no segment structure) | `media_summarizer/core/models/processing_job.py:66`, `:79`, `:299`, `:309` | `transcription_s3_key`, `transcription_metadata` |
| Read path: download, then translate, then detect format, then format | `raw_content_service.py:106-192` | formatting at line 184 happens **after** translation resolution at line 140 |
| Unreachable Deepgram formatters already exist | `raw_content_service.py:535-636` | `_format_deepgram_transcript`, `_format_utterances` (emits `**Speaker N:** ...`), `_format_deepgram_paragraphs` (reads `para["speaker"]` and `para["sentences"][].text`) |
| Heuristic actually used in production | `raw_content_service.py:723-764` | docstring: "Splits long continuous text into paragraphs at sentence boundaries approximately every 3-5 sentences" |
| Early return that defeats the heuristic | `raw_content_service.py:749-750` | `if len(sentences) <= 5: return text` |
| Response is always `text/plain` | `raw_content_service.py:186-192` | `content_type="text/plain"` |
| API exposes `source_format`, the client types it and never reads it | `media_summarizer/api/endpoints/media.py:1463-1469` and `mobile/src/services/mediaService.ts:54-62` | `source_format?: string \| null` |
| The whole detail screen is a non-virtualized ScrollView | `mobile/app/media/[id].tsx:771` | single `<ScrollView>` |
| Hardcoded lineHeight diverges from the design system | `mobile/app/media/[id].tsx:1645-1650` vs `mobile/src/constants/theme.ts:40-44` | `lineHeight: 24` vs `Typography.body.lineHeight = 25.6` |

### 1.3 Quantitative proof that the current heuristic cannot be the whole fix

Executed against the real functions imported from `media_summarizer.core.services.raw_content_service`, on inputs sized like one hour of speech (about 9 000 words):

| Input shape | Sentences detected | Paragraphs produced | Avg paragraph length | Verdict |
|---|---|---|---|---|
| Deepgram flat transcript, punctuated, single line (**today's Deepgram output**) | 600 | 120 | 379 chars | Mechanically acceptable, semantically arbitrary — a hard cut every 5 sentences ignores topic and speaker boundaries |
| YouTube auto-caption cue lines joined by single newlines, unpunctuated (**today's YouTube output**) | 1 | **1** | **53 999 chars** | Catastrophic: one wall of text |
| Unpunctuated ASR speech on a single line | 1 | **1** | 53 999 chars | Catastrophic |

Root cause of the two catastrophic rows: `_format_plain_text` joins short cue lines when their average length is at most 80 chars (`raw_content_service.py:740-745`); `_split_sentences` (line 767, `re.split(r'(?<=[.!?])\s+', text)`) then finds a single "sentence" because there is no terminal punctuation; and the `len(sentences) <= 5` early return (line 749) hands the raw blob straight back.

`_detect_source_format` was also verified to return `plain_text` for both a Deepgram flat transcript and a YouTube caption blob — **the read path never varies by provider today**.

---

## 2. What Deepgram actually returns (and what we discard)

### 2.1 Response shape, confirmed against the current API reference

With the parameters we already send today (`model=nova-3`, `smart_format=true`, `punctuate=true`, `paragraphs=true`, `utterances=true`, `detect_language=true`), the pre-recorded `/v1/listen` response contains:

```
results
├── channels[0].alternatives[0]
│   ├── transcript                 <- flat string, THE ONLY FIELD WE USE TODAY
│   ├── confidence
│   ├── words[]                    <- word, start, end, confidence (+ speaker when diarized)
│   └── paragraphs
│       ├── transcript             <- SAME TEXT, with "\n\n" between paragraphs  <-- FREE STRUCTURE
│       └── paragraphs[]
│           ├── sentences[]        <- text, start, end
│           ├── speaker            <- integer, present when diarization is on
│           ├── num_words
│           ├── start              <- float seconds
│           └── end                <- float seconds
└── utterances[]                   <- start, end, confidence, channel, transcript, words[], speaker, id
```

Sources: Deepgram paragraphs feature doc and the pre-recorded listen API reference (see section 15). Two facts matter most:

1. **`paragraphs.transcript` is the same transcript text with paragraph breaks already inserted** — the docs describe it as the transcript "including line breaks where the transcript is divided into paragraphs", with a leading newline and blank lines between blocks. It is a *string*, so it slots into our existing `text/plain` storage with **no format change whatsoever**.
2. **`paragraphs.paragraphs[].speaker` is documented as an integer in the OpenAPI reference**, but the paragraphs feature page never mentions it and states only that "paragraph breaks are influenced by speaker changes" when diarization is on. Conclusion: speaker attribution requires diarization, and the paragraph-level `speaker` field must be treated as *optional and possibly absent*.

### 2.2 Feature cost matrix (Deepgram pay-as-you-go, checked 2026-08-07)

| Feature | Price | Already enabled? | Structural value for us |
|---|---|---|---|
| Nova-3 Monolingual pre-recorded | $0.0048/min promotional, $0.0077/min list | yes (`DEEPGRAM_MODEL=nova-3`) | baseline |
| Nova-3 Multilingual | $0.0058/min promotional, $0.0092/min list | only if `detect_language` routes there | baseline |
| Smart Formatting | **Included** | yes | punctuation + paragraphs are its documented minimum |
| `punctuate` | Included (implied by smart_format) | yes | required for any sentence-based splitting |
| `paragraphs` | Not billed as an add-on | yes | **gives us `paragraphs.transcript` for free — this is the whole fix** |
| `utterances` | Not billed as an add-on | yes | semantic units; only adds value with diarization |
| **Speaker Diarization** | **$0.0020/min add-on** | **no** | required for any `Speaker N` label |

Cost impact of enabling diarization on a 1-hour item: **+$0.12**, i.e. **+41.7 %** relative to the $0.288 Nova-3 promotional line item (+26.0 % relative to the $0.462 list rate). That is a real unit-economics decision that belongs to the owner, and it is *not* required to fix readability.

Also noted from the diarization doc: `diarize=true` is **deprecated** in favour of `diarize_model` (`v2` / `latest`), sending both is rejected, and on recent self-hosted releases `diarize=true` silently returns no speaker labels. If the owner ever turns diarization on, the implementer must use `diarize_model`, not `diarize`.

### 2.3 The single highest-leverage line in the codebase

`deepgram_worker.py:458` currently reads:

```python
transcript_text = (alt.get("transcript") or "").strip()
```

`alt["paragraphs"]["transcript"]` sits right next to it in the same `alt` dict, already paid for, already newline-structured. Preferring it (with a fallback to the flat string) is a two-line change that fixes readability for every future Deepgram transcript.

---

## 3. Storage format analysis: plain text vs structured JSON

### 3.1 Who consumes the S3 transcript object

The transcript object in the `TRANSCRIPT_BUCKET` (`infrastructure/terraform/s3.tf:15`, wired into the API Lambda at `infrastructure/terraform/lambda_api.tf:114`) is read by **four independent consumers, all of which decode it as UTF-8 text and treat it as prose**:

| Consumer | File:line | How it uses the bytes | Breaks if the object becomes JSON? |
|---|---|---|---|
| Translation worker | `media_summarizer/workers/transcript_translation_worker.py:173` | `transcript_text = raw_bytes.decode("utf-8")` then sends the whole string to the LLM | **Yes** — would translate JSON keys and structure |
| Artifact generation (summary, notes, flashcards) | `media_summarizer/core/services/artifact_service.py:310`, `:333-343`, `:179-196` | `sha256` of the transcript bytes is the idempotence fingerprint; text is the LLM prompt input | **Yes** twice — prompt pollution *and* every fingerprint changes, forcing full regeneration of all artifacts |
| Algolia search indexing | `media_summarizer/core/services/search_indexing.py:40-77` (`_MAX_CHUNK_TEXT_BYTES = 9500`) | chunks the text on whitespace boundaries into sub-10 KB records | **Yes** — would index JSON braces and float timings as searchable content |
| Raw-content API | `raw_content_service.py:132` | `raw_text = raw_bytes.decode("utf-8")` then formats | partially handled (a `deepgram_json` branch exists), but only for Deepgram |

This is the decisive constraint of the whole task: **the canonical transcript object is a shared contract with four consumers, three of which have no notion of structure.** Any format change is a four-way breaking change plus a full artifact regeneration.

### 3.2 Sizing model

Model: 1 hour of speech at 150 wpm = 9 000 words, about 6 bytes per word including the separator, i.e. **54 000 bytes (52.7 KiB) of plain text**. Word objects measured by serializing a realistic Deepgram word dict (`word`, `start`, `end`, `confidence`, `speaker`, `punctuated_word`) as compact JSON: 111 bytes each.

| Candidate stored object | Size for 1 h | Ratio vs plain | Extra info carried |
|---|---|---|---|
| Plain text, flat (**today**) | 52.7 KiB | x1.00 | none |
| Plain text with blank-line paragraph breaks (**recommended**) | 52.9 KiB | **x1.003** | paragraph boundaries |
| Plain text with `Speaker N:` prefixes | 53.6 KiB | x1.017 | paragraphs + speakers |
| Compact JSON blocks `{"t": text, "s": speaker}` | 53.9 KiB | x1.022 | paragraphs + speakers, machine-readable |
| Compact JSON blocks `{"t","s","b","e"}` (paragraph timings) | 55.6 KiB | x1.055 | + paragraph start/end |
| Sentence-level JSON with timings | 68.1 KiB | x1.322 | + per-sentence timings |
| **Full raw Deepgram payload** (transcript + words + paragraphs + utterances with duplicated words) | **2 246 KiB** | **x42.6** | everything |

At current volumes the absolute S3 cost of any of these is negligible (52 KiB at $0.023/GB/month is about $0.0000012/month per transcript). The decision is therefore **not** driven by storage cost — it is driven by (a) the four-consumer contract, (b) API Lambda payload size and the 30 s timeout (`lambda_api.tf:93-94`), and (c) implementation risk. The x42.6 raw payload additionally means a 1-hour transcript would push a 2.2 MB body through the raw-content endpoint, versus 53 KiB today.

### 3.3 Verdict

**Plain UTF-8 text stays canonical.** Paragraph structure is expressed *in-band* as blank lines, which is:

- invisible to the three structure-blind consumers (a blank line is just whitespace to a chunker, an LLM prompt, or a sha256),
- already the exact shape Deepgram hands us for free (`paragraphs.transcript`),
- already the shape trafilatura produces for articles (`article_extraction_worker.py:215`) and that `_format_article_text` (`raw_content_service.py:694-714`) preserves,
- already the shape the translation prompt is explicitly instructed to preserve (`transcript_translation.py:222-227`),
- and trivially renderable by splitting on blank lines in the mobile client.

If speaker/timestamp metadata is later needed in a machine-readable form, add it as a **separate sidecar object** (`{job_id}.blocks.json`) rather than mutating the canonical object — see section 6.2 for why that is deferred, not adopted, in V1.

---

## 4. Cross-source impact: the 8 transcript producers

Deepgram is only one of eight write sites. Every one of them writes plain text to the same key scheme, so **any fix scoped to Deepgram alone leaves most of the library unreadable.**

| # | Producer | File:line | Upstream text shape | Structure available? | What the normalizer must do |
|---|---|---|---|---|---|
| 1 | Deepgram transcription | `deepgram_worker.py:642-643` | flat punctuated string | **yes, free**: `paragraphs.transcript`, plus `paragraphs[]` with `speaker`/`start`/`end` | prefer `paragraphs.transcript`; fall back to sentence grouping |
| 2 | YouTube via Apify actor | `youtube_ingestion_worker.py:803`, text picked at `:647-670` | actor's flat `transcript_text` / `transcript_only_text`, else segment array joined with single newlines | segment array has per-cue text (timings available but discarded) | group cues into paragraphs; never leave 1-line-per-cue |
| 3 | YouTube native captions (yt-dlp) | `media_summarizer/utils/ytdlp_helpers.py:154-171`, `:197`, upload at `youtube_ingestion_worker.py:1163` | VTT/JSON cues, timestamps stripped, joined with single newlines; `segments_count = len(text.splitlines())` (`:289`) | cue boundaries only, frequently **unpunctuated** | join cues, then split on punctuation *or* fixed word budget when punctuation is absent |
| 4 | TikTok | `tiktok_ingestion_worker.py:781`, `:1058`, `:1116` | native caption text or Deepgram fallback | same as 2/3, or same as 1 | same |
| 5 | X / Twitter | `x_ingestion_worker.py:264`, `:436` | short post text | author's own line breaks are meaningful | preserve verbatim (short content, do not re-split) |
| 6 | Article extraction | `article_extraction_worker.py:240`, `:358` | trafilatura output | **already paragraphed** | pass through unchanged (idempotence) |
| 7 | RSS / PodcastIndex transcript | `podcastindex_resolution_worker.py:207`, normalization in `media_summarizer/utils/rss_transcript.py:210` | SRT / VTT / JSON normalized to text | cue boundaries; punctuation varies by publisher | same as 3 |
| 8 | Ingestion orchestrator adapters | `media_summarizer/core/media_ingestion/adapters/orchestrators.py:260`, `:314` | provider text | varies | same |
| (9) | Document parsing | `media_summarizer/workers/document_parsing/worker.py:235` | markdown, key `{job_id}.md`, `text/markdown` | **already structured markdown** | out of scope — must be left untouched (see section 13.3) |

Two conclusions:

1. **The normalizer must live in one shared module, not in the Deepgram worker.** Eight duplicate implementations would drift immediately.
2. **The hardest input is the unpunctuated caption blob** (rows 3, 4, 7), and it is also the most common one for YouTube/TikTok. The normalizer therefore needs a *punctuation-free fallback*: when `_split_sentences` yields fewer than 2 sentences for a text longer than about 1 200 characters, fall back to grouping on a **word budget** (about 90-130 words per block, matching the 379-char paragraphs the punctuated path produces). This is the single functional requirement that today's `_format_plain_text` is missing.

A pleasant consequence: fixing rows 2, 3, 4 and 7 also repairs the misleading `segments_count` badge shown at `mobile/app/media/[id].tsx:1082-1088`, which currently reports raw cue-line counts for YouTube (`ytdlp_helpers.py:289`) versus Deepgram utterance counts (`deepgram_worker.py:471`) — two incomparable units under the same label.

---

## 5. Options compared

### 5.1 The option space

| ID | Option | Storage format | Where structure is computed | Migration needed |
|---|---|---|---|---|
| **A** | Client-side heuristic only | unchanged plain flat text | mobile client | none |
| **B** | **Structured plain text via a shared normalizer (recommended)** | plain text with blank-line paragraph breaks | backend, at write time **and** idempotently at read time | none |
| **C** | Compact structured JSON as the canonical object | JSON blocks | backend at write time | full backfill of all transcripts |
| **D** | Raw Deepgram JSON as the canonical object | raw provider payload | backend at read time (formatters already written) | full backfill; impossible for legacy items |
| **E** | Compact JSON sidecar next to the plain text | plain text + `{job_id}.blocks.json` | backend at write time | optional (sidecar absent = fallback) |
| **F** | LLM re-paragraphing pass | plain text with blank lines | extra LLM call per transcript | none |
| **G** | Read-time-only normalization (no producer change) | unchanged plain flat text | backend at read time | none |

### 5.2 Scoring matrix

Legend: `++` excellent, `+` good, `o` neutral, `-` poor, `--` unacceptable.

| Criterion | A client | **B normalizer** | C JSON canonical | D raw JSON | E sidecar | F LLM | G read-only |
|---|---|---|---|---|---|---|---|
| Readability for Deepgram sources | - | **++** | ++ | ++ | ++ | ++ | + |
| Readability for caption sources (YouTube/TikTok/RSS) | -- | **++** | ++ | -- (no Deepgram JSON to parse) | ++ | ++ | ++ |
| Readability for legacy transcripts | - | **++** | -- | -- | + | ++ | ++ |
| Preserves the 4-consumer contract | ++ | **++** | -- | -- | ++ | ++ | ++ |
| Artifact sha256 fingerprint stability | ++ | **++** | -- | -- | ++ | ++ | ++ |
| Translation-cache compatibility | ++ | **++** | -- | -- | o (translated mode loses the sidecar) | + | ++ |
| Speaker labels possible | -- | **+** (in-band prefix) | ++ | ++ | ++ | - | - |
| Timestamps possible | -- | **-** | ++ | ++ | ++ | -- | -- |
| Storage overhead | ++ (0 %) | **++ (+0.3 %)** | + (+2.2 %) | -- (+4160 %) | + (+2.2 %) | ++ | ++ |
| Recurring cost | ++ $0 | **++ $0** | ++ $0 | ++ $0 | ++ $0 | - $6.08/1000 h | ++ $0 |
| Migration effort | ++ none | **++ none** | -- full backfill | -- impossible | + optional | ++ none | ++ none |
| Implementation effort | ++ 0.5 d | **+ 1.5-2 d** | -- 4-6 d | -- 5-7 d | o 3-4 d | + 1-2 d | ++ 1 d |
| Latency added to the read path | ++ | **++** (pure string ops, sub-ms) | + | - (parse 2 MB JSON in a 30 s Lambda) | + | -- (LLM round-trip) | ++ |
| Deletes existing dead code | -- | **++** | + | -- (revives it) | + | o | + |
| **Overall** | **reject** | **ADOPT** | reject | reject | **defer to V2** | reject | reject (subsumed by B) |

### 5.3 Why B wins

1. **It is the only option that fixes all sources and all legacy content with zero migration.** Idempotent read-time normalization covers everything already in S3; write-time normalization means new content is correct at rest (so translation, artifacts and search all consume readable text too, not just the viewer).
2. **It preserves every existing contract**: same key, same content type, same four consumers, same artifact fingerprints (for new items), same translation cache keys.
3. **It costs nothing recurring** and captures structure Deepgram already bills us for.
4. **It removes dead code instead of adding more** (see section 12).
5. **Speaker labels degrade gracefully**: with diarization off nothing changes; with diarization on, an in-band `Speaker N:` prefix appears, the translation prompt already knows to preserve it (`transcript_translation.py:222-227`), and the mobile client can style it.

The only capability B gives up is **timestamps**, which are worthless until the app has a player (`mobile/package.json` has no `expo-av` / `expo-audio`). Option E is the natural V2 upgrade path *if and when* a player lands, and B does not block it — a sidecar can be added later without touching the canonical object.

---

## 6. Rejected options and why

### 6.1 Option A — client-side heuristic re-paragraphing only: **REJECTED**

The task description explicitly asks to evaluate this as the fallback if structured data is unavailable or not worth backporting. It is not viable **as the sole fix**:

- Structured data **is** available and **is** free (section 2), so the premise does not hold for Deepgram.
- Measured in section 1.3: a punctuation-based client heuristic produces **1 paragraph of 53 999 characters** on unpunctuated caption input, which is the dominant YouTube/TikTok shape. A client cannot invent sentence boundaries that the text does not contain, and it has no access to the model's paragraph decisions.
- It would fix only the viewer. The transcript stays a wall of text for the translation LLM, for artifact prompts, and for Algolia — three consumers that all benefit from paragraph structure at rest.
- It duplicates in TypeScript a heuristic that already exists in Python (`raw_content_service.py:723-764`), creating two divergent implementations.

**Partially retained**: the *word-budget fallback* idea is kept, but implemented **backend-side inside the shared normalizer**, where it also benefits translation, artifacts and search. The client only splits on blank lines — a two-line, zero-heuristic operation.

### 6.2 Option E — compact JSON sidecar: **DEFERRED, not adopted in V1**

Attractive on paper (+2.2 % storage, machine-readable speakers and timings, no breaking change to the canonical object) but rejected for V1 on three grounds:

1. **It silently degrades in translated mode.** Translation produces a *separate* object (`{stem}.translated.{lang}.{ext}`, `transcript_translation.py:195-210`) whose paragraph count is not guaranteed to match the source. Aligning a sidecar's blocks to translated text requires either per-block translation (11x the LLM calls for the 11 V1 languages of task-189) or a fragile alignment step. With the recommended in-band approach, translation carries the structure for free because it is *inside* the text the LLM rewrites.
2. **It needs a second API field and a second S3 GET** on the raw-content path, inside a 30 s API Gateway budget (`lambda_api.tf:93-94`) that already performs up to two S3 downloads plus DynamoDB translation-state work (`raw_content_service.py:112-180`).
3. **Its only unique payoff is timestamps**, and there is no player to make them actionable.

Revisit when an in-app player exists; the recommended design does not foreclose it.

### 6.3 Option C — compact structured JSON as the canonical object: **REJECTED**

Breaks all four consumers of section 3.1 simultaneously, and — critically — **changes the sha256 of every transcript**, which is the artifact idempotence fingerprint (`artifact_service.py:179-196`, `:310`). Every existing summary, set of notes and flashcard deck would be considered stale and regenerated at LLM cost. Requires a full backfill for content that cannot be reconstructed (section 9). No readability benefit over Option B.

### 6.4 Option D — raw Deepgram JSON as the canonical object: **REJECTED**

This is the option the dormant code in `raw_content_service.py:535-636` was evidently written for. Rejected because:

- **x42.6 storage** (2 246 KiB vs 52.7 KiB for one hour, section 3.2) and a 2.2 MB raw-content response body.
- Breaks the same four consumers as Option C, plus the same artifact-fingerprint churn.
- **Only works for Deepgram** — 7 of the 8 producers have no such payload, so the library stays inconsistent.
- **Impossible for legacy items**: the Deepgram payload was never persisted anywhere (`deepgram_worker.py:452-478` returns a 4-key dict; nothing writes the raw response to S3 or DynamoDB), so historical transcripts can never be back-parsed.
- Parsing a multi-megabyte JSON on every read inside a 1024 MB / 30 s Lambda is a needless latency and memory risk.

### 6.5 Option F — LLM re-paragraphing pass: **REJECTED**

Cost: 54 000 characters is about 13 500 tokens in and out; at the translation pricing already configured in the repo (`transcript_translation.py:84-85`, $0.05/1M input and $0.40/1M output) that is **$0.00608 per hour of audio, i.e. $6.08 per 1 000 hours** — recurring, for a problem that `paragraphs.transcript` solves for $0. It also adds an LLM round-trip to the pipeline, a new failure mode, a new idempotence state machine, and a risk of the model altering transcript wording (a correctness hazard for a verbatim artifact).

Narrow future exception worth noting: LLM re-paragraphing is the *only* technique that could add semantic paragraphs to **unpunctuated legacy captions**. If the owner later judges the word-budget fallback insufficient for that specific corpus, it can be revisited as a targeted, opt-in repair — not as the default path.

### 6.6 Option G — read-time normalization only, no producer change: **REJECTED (subsumed by B)**

Cheaper (about 1 day) and it does fix the viewer, but it deliberately throws away the free, model-derived paragraph structure from `paragraphs.transcript` and replaces it with a generic heuristic — strictly worse output for our highest-quality source. It also leaves the *stored* transcript unreadable, so translation, artifact prompts and search keep consuming a wall of text. Option B includes G's read-time layer (that is what makes migration unnecessary) and adds the write-time layer, for about half a day more.

### 6.7 Enabling diarization by default: **REJECTED as a default**

+$0.0020/min is **+41.7 %** on the current Nova-3 promotional rate. Diarization is a genuine product feature (multi-speaker podcasts and interviews), not a formatting prerequisite: `paragraphs.transcript` already delivers paragraph breaks without it. Recommended as an env-gated, owner-decidable flag (`DEEPGRAM_DIARIZE=false` by default) with the UI rendering path implemented so switching it on requires no further code change. Note the deprecation: use `diarize_model=v2` (or `latest`), never `diarize=true`.

### 6.8 Sentence-level timings in storage: **REJECTED**

+32.2 % storage (68.1 KiB vs 52.7 KiB per hour, section 3.2) for data with no consumer: no player, no seek, no karaoke highlighting. Paragraph-level timings (+5.5 %) are cheaper and sufficient if timings are ever needed.

### 6.9 A "reading mode / raw mode" toggle: **REJECTED**

The task description raises it. There is no user story for deliberately reading a *worse* rendering: paragraph breaks add no information loss, and the current flat rendering is a defect, not a mode. A toggle would add UI surface, persisted preference state and two code paths to maintain for zero value. `selectable` text already covers the underlying real need (copy the transcript out).

### 6.10 An S3 backfill migration: **REJECTED as unnecessary**

See section 9: idempotent read-time normalization makes legacy content readable without touching a single stored object, and a rewrite would change transcript bytes, invalidating artifact fingerprints and translation caches for content whose readability is already fixed for free.

---

## 7. Speaker labels and timestamps: feasibility and cost

### 7.1 Speaker labels

**Availability.** Confirmed from the Deepgram docs: the `speaker` integer appears on `results.utterances[]`, on `alternatives[].words[]` (with `speaker_confidence` for pre-recorded), and — per the OpenAPI reference — on `paragraphs.paragraphs[]`. All of it requires diarization, which is a **$0.0020/min paid add-on we do not currently buy**. Today, therefore, **no speaker information exists anywhere in our data**, for any source.

**Cost to display.** Near zero once diarization data exists, because the backend already knows how to emit the labels: `_format_utterances` (`raw_content_service.py:580-608`) produces `**Speaker N:** ...` blocks joined by blank lines, and `_format_deepgram_paragraphs` (`:611-636`) does the same from paragraph objects. The recommended in-band encoding drops the markdown asterisks (nothing renders markdown in the app — `mobile/package.json` has no markdown renderer) in favour of a plain `Speaker N:` prefix that the client detects with a small regex.

**Recommended plan:**

- Add `DEEPGRAM_DIARIZE` (default `false`) next to the existing flags at `deepgram_worker.py:88-92`, translated into `diarize_model=v2` when enabled (never the deprecated `diarize=true`).
- The normalizer emits a paragraph prefixed with `Speaker N: ` whenever a speaker index is known and differs from the previous block.
- The mobile renderer detects a leading `^Speaker \d+: ` and renders the label as a distinct inline run (`Colors.textMuted`, `Typography.label`) followed by the body text, using nested `<Text>` so the label reflows with the paragraph — a `<View>` wrapper would break the paragraph into blocks (React Native `Text` documentation: inside a `Text`, layout is text layout, not Flexbox).
- Fallback when diarization is off: no prefix, no label, zero visual change.

**Non-Deepgram sources will never have speakers.** Apify actors, yt-dlp captions and RSS transcripts do not carry speaker identity. The UI must therefore treat speaker labels as strictly optional, per paragraph.

### 7.2 Timestamps

**Availability.** Deepgram gives paragraph and sentence `start`/`end` in seconds. Apify YouTube actors return a timestamped segment array (`youtube_ingestion_worker.py:658-670`) which we currently reduce to text. yt-dlp cue timings are **actively stripped** (`ytdlp_helpers.py:154-171`, `:197`). Articles and X posts have none.

**Cost to display.** The rendering cost is negligible; the *plumbing* cost is not — it is exactly the Option E sidecar problem (section 6.2), including the translated-mode alignment issue.

**Recommendation: do not display timestamps in V1.** Justification:

1. **No player.** `mobile/package.json` contains no `expo-av`, no `expo-audio` and no other media playback dependency, and there is no player component in the media detail screen. A timestamp the user cannot tap to seek is decoration that competes with the body text for attention.
2. **Coverage is inconsistent** — articles, X posts and yt-dlp captions have no timings, so a third of the library would show a feature the rest lacks.
3. **It contradicts the goal.** The complaint is visual noise and no structure; inserting `[00:12:34]` markers every paragraph adds noise. Note that the translation prompt would faithfully preserve them (`transcript_translation.py:222-227`), so the noise would survive translation too.

Revisit together with a player task; paragraph-level timings (+5.5 % storage) are the right granularity at that point.

### 7.3 Reading ergonomics: expected outcome

| Aspect | Today | After Option B |
|---|---|---|
| Paragraphs | none (one block) | about 120 blocks per hour, about 379 chars each, about 90-130 words |
| Inter-paragraph spacing | none | `Spacing.md` (16 px) |
| Line height | 24 px (hardcoded, off-system) | 25.6 px (`Typography.body.lineHeight`, 1.6x) |
| Text selection | not selectable | `selectable` per paragraph |
| Speaker cues | none | optional `Speaker N:` label (only if diarization is enabled) |
| Timestamps | none | none in V1 (deliberate) |
| Scroll container | single `ScrollView` | unchanged (about 120 `Text` nodes is well within budget) |

The 379-char / 90-130-word paragraph target sits in the conventional readable range for long-form body copy and matches what Deepgram's own paragraph segmentation produces, so the punctuated and fallback paths yield visually consistent output.

---

## 8. Translation pipeline compatibility

This is the constraint that eliminates every structured-JSON option, so it is worth spelling out precisely.

### 8.1 How translation works today

| Step | File:line | Behaviour |
|---|---|---|
| Read path resolves translation **before** formatting | `raw_content_service.py:139-184` | `_resolve_translation()` at line 140, then `_detect_source_format` / `_format_content` at lines 183-184 on the **effective** (possibly translated) text |
| Translated object is a distinct S3 key | `transcript_translation.py:195-210` | `{stem}.translated.{target}.{ext}` — a cache key, so it must stay deterministic |
| Worker treats the transcript as one opaque string | `transcript_translation_worker.py:173-186` | `raw_bytes.decode("utf-8")`, single LLM call, no chunking |
| The system prompt already mandates structure preservation | `transcript_translation.py:222-227` | "Preserve ALL formatting: paragraph breaks, line breaks, timestamps (e.g., [00:05:32]), speaker labels" and "keep them exactly as-is" |
| Model and pricing | `transcript_translation.py:70`, `:84-85` | `gpt-5-nano-2025-08-07`, $0.05/1M in, $0.40/1M out |
| Translated upload stays text | `transcript_translation.py:741-753` | `content_type="text/plain; charset=utf-8"` |

### 8.2 Why in-band structure is the compatible choice

1. **The prompt is already written for it.** Paragraph breaks and speaker labels are named explicitly in the system prompt with an instruction to keep them as-is. Option B needs **zero prompt changes** and zero worker changes.
2. **Formatting runs after translation** (`raw_content_service.py:183-184`), on the effective text. With the normalizer being idempotent, translated text that already has blank lines passes through untouched; if the LLM ever collapses them, the read-time normalizer re-derives paragraphs from the translated punctuation. **Self-healing by construction.**
3. **Cache keys are untouched.** `build_translated_transcript_key` derives from `(transcript_s3_key, target_language)`, both unchanged.
4. **No extra token cost.** Blank lines are essentially free tokens; the +0.3 % byte increase is noise against a 13 500-token call.
5. **11 languages stay in one call.** A per-block scheme (Option C/E) would either multiply calls or require alignment across 11 V1 languages (task-189).

### 8.3 Risk and mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Translation LLM collapses paragraph breaks despite the prompt | low-medium | read-time idempotent normalizer re-derives paragraphs from the translated text's punctuation — no data loss, worst case a slightly different split |
| Translation LLM translates the literal word "Speaker" | medium (and arguably desirable) | acceptable; make the client's label regex tolerant, or fall back to rendering the prefix as plain text |
| Blank lines shift token counts and hit a length limit | negligible | +0.3 % bytes |
| Existing cached translations lack paragraph breaks | certain, for content already translated | read-time normalizer handles them exactly like legacy originals; no cache invalidation needed |

### 8.4 What the implementer must NOT do

- Do not translate a JSON structure (guaranteed to corrupt keys and float timings).
- Do not add per-block translation calls (multiplies cost by the number of blocks).
- Do not change `build_translated_transcript_key` (would orphan every cached translation).
- Do not move formatting before translation in `get_raw_content` (would translate already-formatted text and lose the self-healing property).

---

## 9. Migration of existing transcripts

### 9.1 What is recoverable from existing data

| Data | Recoverable for legacy transcripts? | Evidence |
|---|---|---|
| Paragraph structure from the Deepgram payload | **No** — the raw response was never persisted | `deepgram_worker.py:452-478` returns a 4-key dict; only `transcript["text"]` reaches S3 (`:641-643`); `transcription_metadata` (`:645-661`) stores no structure |
| Speaker labels | **No** — diarization was never enabled | `deepgram_worker.py:113-121` has no `diarize` parameter |
| Timestamps | **No** for Deepgram (dropped); **no** for yt-dlp (stripped at `ytdlp_helpers.py:154-171`) | as cited |
| Sentence boundaries | **Yes, when punctuation exists** (Deepgram/Apify flat text is punctuated because `smart_format` is on) | `deepgram_worker.py:89` |
| Cue boundaries | **Lost** — cues were joined with single newlines and the read path collapses them | `ytdlp_helpers.py:171`, `raw_content_service.py:738-745` |

**Conclusion: re-parsing is impossible.** No backfill can recover what was never stored. Any "migration" would be a *re-derivation* from the plain text — exactly what the read-time normalizer does, for free, on demand.

### 9.2 The three candidate strategies

| Strategy | Cost | Risk | Verdict |
|---|---|---|---|
| **M0 — no migration; idempotent read-time normalization** | $0, zero ops | none: the stored bytes never change, so artifact fingerprints (`artifact_service.py:310`) and translation caches stay valid | **RECOMMENDED** |
| M1 — batch S3 rewrite with the normalizer | one script, one full-bucket pass, S3 PUT costs | **changes the sha256 of every transcript**, marking every existing summary/notes/flashcard deck stale and triggering paid LLM regeneration; also requires re-indexing Algolia | **REJECTED** |
| M2 — LLM re-paragraphing backfill | $6.08 per 1 000 hours of stored audio, plus M1's risks | same as M1 plus wording-drift risk on a verbatim artifact | **REJECTED** |

### 9.3 Why M0 is sufficient

`_format_content` is already called on **every** raw-content read (`raw_content_service.py:184`). Replacing its `plain_text` branch with the shared normalizer means:

- **legacy transcripts** (flat, punctuated) get the sentence-grouping path, producing about 120 paragraphs per hour;
- **legacy caption transcripts** (unpunctuated) get the new word-budget fallback — which is precisely the case that produces 1 paragraph today;
- **new transcripts** arrive already structured and pass through unchanged (idempotence);
- **translated transcripts** are handled identically, whether cached before or after the change.

The only property legacy content will never gain is speaker labels and timestamps — which no strategy can deliver, since the data was never captured.

### 9.4 Acceptance check the implementer should run

Pick one existing media item per source family (Deepgram podcast, YouTube via Apify, YouTube native captions, TikTok, RSS transcript, article, X post) and verify via `GET /api/media/{id}/raw-content` that the returned `content` contains at least `floor(chars / 2000)` blank-line separators, with no paragraph exceeding about 1 200 characters. That single assertion catches every regression the current heuristic exhibits.

---

## 10. Target design

### 10.1 New shared module

`media_summarizer/core/services/transcript_formatting.py` — the single source of truth for "what a readable transcript looks like". Suggested public surface:

| Function | Responsibility |
|---|---|
| `normalize_transcript_text(text, *, source=None) -> str` | The idempotent core. Returns paragraph-delimited plain text. Called by every producer before upload **and** by the read path. |
| `deepgram_transcript_text(alt, utterances=None) -> str` | Picks the best available Deepgram representation: speaker-grouped utterances if a speaker index is present, else `alt["paragraphs"]["transcript"]`, else `alt["transcript"]` passed through `normalize_transcript_text`. |
| `group_caption_lines(lines) -> str` | Turns cue lines (yt-dlp, RSS SRT/VTT, Apify segment arrays) into paragraphs. |

Normalizer algorithm (deliberately boring, per the KISS rule in `AGENTS.md`):

1. Strip and normalize line endings; collapse runs of 3+ blank lines to exactly one blank line.
2. **Idempotence gate**: if the text already contains a blank-line separator, keep those paragraphs, only re-splitting any single paragraph longer than a hard ceiling (about 1 500 chars).
3. If the text contains single newlines only, treat them as cue lines: join them into one stream (keeping the cue text order) and continue.
4. Split into sentences with the existing regex.
5. **Punctuated path**: group sentences into blocks targeting about 90-130 words (about 350-450 chars), never breaking mid-sentence.
6. **Unpunctuated fallback** (fewer than 2 sentences detected for a text longer than about 1 200 chars): group on a word budget of about 110 words per block. This is the missing behaviour that causes today's 53 999-char paragraph.
7. Very short content (X posts, under about 400 chars): return as-is, preserving the author's own line breaks.
8. Join blocks with a blank line.

Properties the implementer must guarantee: `normalize(normalize(x)) == normalize(x)`, no character of transcript content ever added or removed (only whitespace changes), and no dependency on the source platform for correctness (the `source` argument is a hint for the short-content rule only).

### 10.2 Write-path changes

| File:line | Change |
|---|---|
| `deepgram_worker.py:452-478` | `extract_transcript()` returns `deepgram_transcript_text(alt, utterances)` instead of the flat string. Keep raising on empty. Keep `segments_count`, and add `paragraphs_count` to `transcription_metadata` (`:645-661`) for observability. |
| `deepgram_worker.py:88-92`, `:113-121` | Add `DEEPGRAM_DIARIZE` (default `false`); when true, send `diarize_model=v2`. **Never** `diarize=true` (deprecated, and silently label-free on recent self-hosted releases). |
| `youtube_ingestion_worker.py:647-670`, `:803`, `:1069`, `:1163` | Run the extracted text through `normalize_transcript_text`; for the Apify segment-array branch use `group_caption_lines`. |
| `ytdlp_helpers.py:154-171`, `:197`, `:289` | Keep returning cue lines, but let the caller group them; make `segments_count` count paragraphs, not raw lines, so the mobile badge becomes comparable across sources. |
| `tiktok_ingestion_worker.py:781`, `:1058`, `:1116` | Same as YouTube. |
| `podcastindex_resolution_worker.py:207` and `media_summarizer/utils/rss_transcript.py:210-222` | Normalize after SRT/VTT/JSON conversion. |
| `article_extraction_worker.py:240`, `:358` | Normalize (a no-op pass-through for trafilatura output — a good idempotence canary). |
| `x_ingestion_worker.py:264`, `:436` | Normalize (short-content path preserves author line breaks). |
| `media_summarizer/core/media_ingestion/adapters/orchestrators.py:260`, `:314` | Normalize. |
| `media_summarizer/workers/document_parsing/worker.py:235` | **No change** — markdown, different extension, already structured. |

### 10.3 Read-path changes

| File:line | Change |
|---|---|
| `raw_content_service.py:519-532` | `_format_content` delegates `plain_text` / `ocr` to `normalize_transcript_text`. Keep `article_text` and `social_post` branches (or let the normalizer subsume them if behaviour is identical). |
| `raw_content_service.py:723-772` | Delete `_format_plain_text` and `_split_sentences` (moved into the shared module). |
| `raw_content_service.py:485-517` | Simplify `_detect_source_format`: the `deepgram_json` / `whisper_json` / `json_transcript` branches are unreachable (nothing writes JSON to this bucket). Keep the field in the API response (the mobile type already declares it) but stop pretending to detect provider payloads. |
| `raw_content_service.py:139-192` | **Unchanged ordering**: translate first, then format. Preserves the self-healing property of section 8.2. |
| `media_summarizer/api/endpoints/media.py:1459-1553` | No contract change. `content` stays a `text/plain` string; the client splits on blank lines. |

### 10.4 What explicitly does not change

- S3 key scheme (`{job_id}.txt`), bucket, and `text/plain` content type.
- `ProcessingJob` schema (`processing_job.py:66`, `:79`) — no new field required.
- `RawContentResponse` shape (`media.py:1459-1483`) and `mobile/src/services/mediaService.ts:54-62`.
- Translation cache keys, prompt, worker, and DynamoDB state machine.
- Artifact fingerprinting logic and Algolia chunking.
- Terraform: no new bucket, queue, env var (beyond `DEEPGRAM_DIARIZE`), timeout, or memory change.

---

## 11. UI implementation plan (React Native)

### 11.1 Scope

All changes are confined to `mobile/app/media/[id].tsx`: the `TranscriptContent` component (lines 1128-1233) and the `transcriptBody` style (lines 1645-1650). No new dependency, no change to `mobile/src/services/mediaService.ts`.

### 11.2 Rendering model

Replace each of the three occurrences of the single flat node (`:1138`, `:1156`, `:1175`) with a shared paragraph renderer:

- Split `state.content` on blank-line separators (tolerating optional surrounding whitespace), drop empty entries, and memoize the result with `useMemo` keyed on the content string so the split does not re-run on every render (the component re-renders on translation polling every 3 000 ms, `mobile/app/media/[id].tsx:110-112`).
- Render one `<Text selectable style={styles.transcriptParagraph}>` per block inside a plain `<View>`. A `<View>` wrapper is required to get block layout: per the React Native `Text` documentation, children of a `Text` use text layout, not Flexbox, and would flow inline.
- Detect an optional leading `Speaker N: ` prefix per block. When present, render it as a **nested** `<Text style={styles.transcriptSpeaker}>` inside the paragraph `Text` so it reflows with the body rather than becoming its own block.
- Key each paragraph by index (blocks are positionally stable for a given content string).

### 11.3 Styles

| Style | Value | Rationale |
|---|---|---|
| `transcriptParagraph.fontSize` | `Typography.body.fontSize` (16) | unchanged |
| `transcriptParagraph.lineHeight` | `Typography.body.lineHeight` (25.6) | fixes the off-system hardcoded `24` at line 1648 |
| `transcriptParagraph.color` | `Colors.textMain` | unchanged |
| `transcriptParagraph.marginBottom` | `Spacing.md` (16) | the actual paragraph separation, replacing `paddingVertical: Spacing.sm` |
| `transcriptSpeaker.color` | `Colors.textMuted` | subordinate to the body text |
| `transcriptSpeaker.fontWeight` | `"600"` | scannable without shouting |

Keep `allowFontScaling` at its default (`true`) so Dynamic Type / font-size accessibility settings keep working on body copy.

### 11.4 Virtualization: not needed

The screen is one `ScrollView` (`mobile/app/media/[id].tsx:771`), which renders all children eagerly. Measured volume: about 120 paragraphs for a one-hour transcript (section 1.3) — roughly 120 `Text` nodes, versus the single 46 000-character node rendered today (which is itself the heavier native text-measurement job). Converting the screen to a `FlatList` would mean restructuring the entire detail screen (header, metadata, artifacts, transcript) into list sections, and `getItemLayout` is unavailable because paragraph heights vary — the React Native optimization guide names that as the case where virtualization tuning gets hard. **Recommendation: keep the `ScrollView`.** If a pathological transcript is ever observed (say more than 800 paragraphs), the cheap escalation is a "show more" clamp on the transcript section, not a full virtualization rewrite.

### 11.5 Optional, cheap ergonomics wins (owner's call)

| Idea | Cost | Value |
|---|---|---|
| `selectable` on paragraphs | trivial | lets users copy quotes — the real need behind any "raw mode" request |
| Collapse long transcripts behind a "Show full transcript" affordance using `numberOfLines` + `onTextLayout` | small | shortens the scroll to the AI artifacts below; note the Android constraint that only `ellipsizeMode="tail"` behaves correctly when `numberOfLines > 1` |
| Max reading width / horizontal padding | trivial | shorter measure improves readability on tablets |

### 11.6 Explicitly out of scope for V1

- Timestamp rendering (section 7.2).
- Any markdown rendering. Nothing in `mobile/package.json` renders markdown, so the backend must **not** emit `**bold**` speaker labels the way `_format_utterances` does today (`raw_content_service.py:596`, `:605`, `:632`) — those asterisks would show up literally.
- Search-within-transcript, auto-scroll, karaoke highlighting (all require a player or a search UI).
- A reading/raw mode toggle (section 6.9).

### 11.7 Design system note

`mobile-design-mockups/` contains no transcript-rendering reference (grepping the media-detail mockup for "transcript" returns nothing), so there is **no existing visual spec to conform to**. The plan above therefore derives entirely from `mobile/src/constants/theme.ts` (Amber Clarity: `Typography.body` 16/25.6, `Spacing.md` 16, `Colors.textMain` / `Colors.textMuted`). If the owner wants a mockup first, that is a prerequisite worth flagging on task-232.

---

## 12. Dead code to delete

`AGENTS.md` states the project is pre-production and that obsolete code must be deleted rather than kept for compatibility. This task is the right moment to remove a large block of unreachable formatting code in `raw_content_service.py`, all of it written for a storage format that never existed:

| Function | Lines | Why it is dead |
|---|---|---|
| `_format_deepgram_transcript` | 535-577 | reachable only when `_detect_source_format` returns `deepgram_json`, which requires the S3 object to be a Deepgram JSON payload. No producer ever writes one. |
| `_format_utterances` | 580-608 | called only by the above. Also emits markdown asterisks that no client renders. |
| `_format_deepgram_paragraphs` | 611-636 | same. Its logic should be **relocated**, not deleted, into `deepgram_transcript_text()` in the new module, where it becomes reachable. |
| `_format_whisper_transcript` | 639-662 | Whisper transcription is on the "Do NOT touch" list in `AGENTS.md`; no producer writes Whisper JSON here. |
| `_format_json_transcript` | 665-691 | no producer writes generic JSON to this bucket. |
| `_detect_source_format` JSON branches | 493-506 | detect JSON shapes that never occur. |
| `_format_plain_text` / `_split_sentences` | 723-772 | superseded by the shared normalizer (move, do not duplicate). |

That is roughly 240 lines of unreachable code whose mere existence made this defect hard to see — paragraph and speaker formatting *looked* implemented, which plausibly explains why task-69 was closed with an acceptance criterion ("Deepgram transcripts formatted into readable text with paragraphs and speaker labels where available") that the runtime never satisfied.

**Recommendation:** delete the unreachable functions, relocate the `_format_deepgram_paragraphs` / `_format_utterances` logic into the new module where the write path actually calls it, and keep the `source_format` response field (harmless, already typed client-side) reporting a simplified media-type-based classification.

---

## 13. Side findings

### 13.1 `segments_count` is not comparable across sources

The mobile UI shows "N segments" (`mobile/app/media/[id].tsx:1082-1088`) from a value that means Deepgram utterances for podcasts (`deepgram_worker.py:471`) but raw caption line counts for YouTube (`ytdlp_helpers.py:289`). For a one-hour video the YouTube number can be an order of magnitude larger for the same content. Once paragraphs are canonical, reporting `paragraphs_count` makes the badge meaningful and comparable. Cheap to fix inside task-232, or as a separate small task.

### 13.2 `transcriptBody.lineHeight` is off-system

`lineHeight: 24` (`mobile/app/media/[id].tsx:1648`) versus `Typography.body.lineHeight = 25.6` (`mobile/src/constants/theme.ts:43`). The 1.6x ratio is the design system's stated intent, and the transcript is the longest body text in the app — the place where it matters most.

### 13.3 Parsed documents are a separate, already-structured corpus

`document_parsing/worker.py:235` writes `{job_id}.md` with `content_type="text/markdown"`, and the raw-content endpoint returns it as `text/plain` after running it through `_format_plain_text`. Markdown headings and lists survive by accident (they carry their own line breaks). The normalizer's idempotence gate must not damage them: **detect the `.md` extension on `transcription_s3_key` and pass such content through untouched.** Rendering markdown properly is a separate concern (no renderer is installed) and out of scope here.

### 13.4 The read path can do two S3 GETs plus DynamoDB work inside 30 s

`raw_content_service.py:112-180` downloads the original, may resolve translation state in DynamoDB, and may download the translated object, all within the API Lambda's 30 s timeout (`infrastructure/terraform/lambda_api.tf:93-94`). Another argument against adding a sidecar GET (section 6.2) and against parsing multi-megabyte JSON (section 6.4).

### 13.5 Apify and yt-dlp timings are thrown away too

`youtube_ingestion_worker.py:658-670` reduces a timestamped segment array to joined text, and `ytdlp_helpers.py:154-171` strips cue timings. If timestamps are ever pursued, the data exists upstream for these sources as well — a future player task should revisit all producers together, not just Deepgram.

---

## 14. Open questions for the owner

1. **Diarization**: accept the recommendation to keep it off by default (+41.7 % per transcribed minute if enabled), or enable it now for the multi-speaker use case? The implementation should be written so that flipping the flag is the only change needed.
2. **Timestamps**: confirm they are deliberately out of V1 (no player exists), or is a passive `[hh:mm:ss]` paragraph marker wanted despite the noise and the inconsistent coverage?
3. **Paragraph target length**: about 90-130 words / about 379 characters is proposed (matching Deepgram's own segmentation). Shorter blocks read faster on mobile but lengthen the scroll.
4. **Design mockup**: none exists for the transcript (section 11.7). Ship on design-system defaults, or block task-232 on a mockup?
5. **Dead-code cleanup scope**: is deleting the roughly 240 unreachable lines in `raw_content_service.py` in scope for task-232, or should it be split into its own task?
6. **`segments_count` semantics** (section 13.1): change it to `paragraphs_count` as part of task-232, or handle it separately?

---

## 15. Sources

### Repository code (read at commit `29e970e`)

- `media_summarizer/workers/transcription/deepgram_worker.py` — 88-92 (feature flags), 113-121 (query params, no diarize), 140-161 (upload as `text/plain`), 452-478 (`extract_transcript`, the discard point), 640-661 (S3 write plus metadata)
- `media_summarizer/core/services/raw_content_service.py` — 74-192 (`get_raw_content`, translate-then-format ordering), 485-532 (format detection and dispatch), 535-636 (unreachable Deepgram formatters), 639-691 (unreachable JSON formatters), 694-714 (article formatter), 723-772 (`_format_plain_text`, `_split_sentences`)
- `media_summarizer/core/models/processing_job.py` — 66, 79, 149-173, 299-314
- `media_summarizer/api/endpoints/media.py` — 1459-1483 (`RawContentResponse`), 1485-1553 (endpoint)
- `media_summarizer/core/services/transcript_translation.py` — 70 and 84-85 (model and pricing), 195-210 (cache key), 213-230 (system prompt preserving paragraphs, timestamps, speaker labels), 741-753 (translated upload)
- `media_summarizer/workers/transcript_translation_worker.py` — 173-186 (decode as one string, single call)
- `media_summarizer/core/services/artifact_service.py` — 128-133 and 179-196 (sha256 fingerprint), 245-260 (`_load_transcript_bytes`), 297-346 (`_resolve_effective_transcript`)
- `media_summarizer/core/services/search_indexing.py` — 34-77 (Algolia chunking at 9 500 bytes)
- `media_summarizer/workers/youtube_ingestion_worker.py` — 647-670, 803-808, 1069, 1163
- `media_summarizer/utils/ytdlp_helpers.py` — 154-171, 197, 230-289
- `media_summarizer/workers/tiktok_ingestion_worker.py` — 781-786, 1058, 1116
- `media_summarizer/workers/x_ingestion_worker.py` — 264-269, 436
- `media_summarizer/workers/article_extraction_worker.py` — 215-225, 240-245, 358
- `media_summarizer/workers/podcastindex_resolution_worker.py` — 207-213
- `media_summarizer/utils/rss_transcript.py` — 92-100, 210-222
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py` — 260-276, 314-323
- `media_summarizer/workers/document_parsing/worker.py` — 228-245
- `mobile/app/media/[id].tsx` — 100-112 (`RawContentState`, polling), 644-734 (fetch and poll), 771 (single ScrollView), 1011-1126 (`TranscriptSection`, metadata badges), 1128-1233 (`TranscriptContent`), 1645-1650 (`transcriptBody`)
- `mobile/src/services/mediaService.ts` — 51-62 (`RawContentResponse`), 117-130 (`getRawContent`)
- `mobile/src/constants/theme.ts` — 40-44 (`Typography.body`), Spacing and Colors
- `mobile/package.json` — 21-42 (Expo 55, react-native 0.83.6; no markdown renderer, no `expo-av` / `expo-audio`)
- `infrastructure/terraform/lambda_api.tf` — 93-94 (30 s timeout, 1024 MB), 114 (`TRANSCRIPT_BUCKET`), 219
- `infrastructure/terraform/s3.tf` — 15 (transcripts bucket)
- `docs/research/task-189-transcript-translation-benchmark/README.md` — validated translation architecture (gpt-5-nano, 11 V1 languages)
- `docs/research/task-218-durable-media-library-persistence/README.md` — structure template for this document

### External sources

- Deepgram, Paragraphs feature: https://developers.deepgram.com/docs/paragraphs — response shape, `paragraphs.transcript` carrying blank-line separators, paragraph breaks influenced by speaker changes, punctuation auto-enabled
- Deepgram, Smart Format: https://developers.deepgram.com/docs/smart-format — "At minimum, Smart Format applies" punctuation and paragraphs; paragraphs limited to whitespace-delimited languages
- Deepgram, Utterances: https://developers.deepgram.com/docs/utterances — `results.utterances[]` fields; `speaker` requires diarization
- Deepgram, Diarization: https://developers.deepgram.com/docs/diarization — `speaker` and `speaker_confidence` on words, `metadata.diarize_info`, `diarize=true` deprecated in favour of `diarize_model`, requests setting both are rejected
- Deepgram, pre-recorded listen API reference: https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded — OpenAPI schema showing `paragraphs.paragraphs[]` carrying `speaker` as an integer plus `sentences`, `num_words`, `start`, `end`; utterance object fields
- Deepgram pricing: https://deepgram.com/pricing — Nova-3 Monolingual $0.0048/min promotional and $0.0077/min list; Multilingual $0.0058 / $0.0092; Smart Formatting "Included"; Speaker Diarization add-on $0.0020/min
- React Native, Text: https://reactnative.dev/docs/text — `selectable`, `onTextLayout`, `numberOfLines`, `ellipsizeMode` with the Android `tail`-only constraint above one line, and the "inside a Text, layout is text layout, not Flexbox" containers rule
- React Native, Optimizing FlatList configuration: https://reactnative.dev/docs/optimizing-flatlist-configuration — `getItemLayout` requires uniform item heights; `windowSize`, `initialNumToRender`, `maxToRenderPerBatch` tradeoffs; VirtualizedList windowing model
- LLM pricing basis for the rejected Option F: the repo's own configured rates at `media_summarizer/core/services/transcript_translation.py:84-85` ($0.05/1M input, $0.40/1M output, `gpt-5-nano-2025-08-07`)

### Measurements performed for this benchmark

- Formatting simulation: `_format_plain_text` and `_split_sentences` imported from `media_summarizer.core.services.raw_content_service` and run on three 1-hour-scale inputs (section 1.3).
- Storage sizing: compact-JSON serialization of realistic Deepgram word, sentence, paragraph and utterance objects against a 54 000-byte plain-text baseline (section 3.2).
- Cost arithmetic: Deepgram per-minute rates times 60 minutes; LLM re-paragraphing at the repo's configured token prices (sections 2.2 and 6.5).
