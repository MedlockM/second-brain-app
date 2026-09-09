---
owner_decision: pending
---

# Benchmark: generating an audio podcast from a media item or a folder

## Owner Validation

**Decision**:
**Validated at**:

---

## Recommendation

**Drive Azure AI Speech *batch synthesis* directly over REST, from the existing
`artifact_generator` worker, with a submit-then-poll shape modelled on
`apify_orchestration`. Adopt nothing from `podcast-creator` / `open-notebook`.**

Concretely:

| Decision | Value |
| --- | --- |
| Script writer | The corpus + LLM layer we already own (`artifact_service`, `gpt-5.4-nano`, the folder corpus cap of 120 000 tokens). No new library. |
| TTS | Azure AI Speech, **batch synthesis** REST API, `api-version=2024-04-01`, region `francecentral`, pricing tier `S1`, *Neural* (standard) voices. |
| Multi-voice | One SSML document containing several `<voice>` elements. `<speak>` and `<voice>` markup is **not billable**. |
| Assembly | **None on our side.** The provider renders **one** file. No ffmpeg, no pydub, no moviepy, no new Python dependency. |
| Output | `audio-24khz-48kbitrate-mono-mp3` → 1.8 / 5.4 / 10.8 MB for a 5 / 15 / 30-minute episode. |
| Compute envelope | **Unchanged**: `artifact_generator` stays at 512 MB / 300 s on the existing unified `artifact-generator-queue`. Nothing needs Step Functions or Fargate. The one code-level constraint is that `GENERATION_LEASE_SECONDS` must be **re-armed on every poll hop**. |
| Byte delivery | A new sibling route returning a short-lived **presigned S3 GET URL**, reusing `utils/s3.generate_presigned_url`. Range requests work (verified), so the mobile player can seek. |
| Artifact type id | **`audio_digest`** — `podcast` is already taken by PodcastIndex episodes. |
| Metering | `2 × target_minutes + 5` metered minutes, at **both** scopes (media included). Still "only minutes", per task-287. |
| Duration menu | Expose **5 and 15 minutes**. A 30-minute episode costs 65 metered minutes and therefore **does not fit at all** inside the Reader tier's 60-minute allowance. |
| Credentials to provision | An Azure **Speech** resource in `francecentral`: its **key**, its **region**, its **resource name**. Nothing else. (Values never written to this repo.) |

Why this and not the owner's lead: `podcast-creator` earns its keep by *stitching
N audio segments together with moviepy*. That is the one thing we must not do —
ffmpeg is absent from the worker image by choice — and it is the only part of the
pipeline we do not already own. Taking the package costs **+138.6 MB of wheels
(3.48×)**, six wheels that do not exist for our glibc 2.26 base image, a
`tiktoken` hard dependency this repo deliberately excluded, and a `pillow`
version collision that upstream itself has to override. Measured numbers in
§13.

Why Azure and not the cheaper-looking rivals: **every other provider caps a
single request well below one episode** (Polly 3 000 billed characters and
10 minutes; Deepgram 2 000 characters; ElevenLabs ≤2 000 characters advised;
Gemini ≈21.3 minutes by token budget, 2 speakers max, headerless PCM; Azure's own
*real-time* endpoint 10 minutes). Anything but Azure batch hands us back the
concatenation problem. Azure is also *not* a compromise on price: at
€12.88/1M characters it is the cheapest per-character neural voice in the
comparison except Polly Standard, and it is the only candidate that covers all
11 of our locales including `ar` and `hi` with a two-voice cast.

**One-paragraph version for an implementer who reads nothing else.** Generate the
two-host script with the existing LLM layer in the artifact's language. Wrap it
in one SSML document alternating two `<voice name="…">` elements picked from a
static per-locale table. `PUT` it to
`https://<resource>.cognitiveservices.azure.com/texttospeech/batchsyntheses/<id>?api-version=2024-04-01`
with header `Ocp-Apim-Subscription-Key`, `inputKind: "SSML"`,
`properties.outputFormat: "audio-24khz-48kbitrate-mono-mp3"`. Re-enqueue the SQS
message with a delay to poll `GET` on the same URL; on `status: "Succeeded"`,
download `outputs.result` (a ZIP), take the single audio file, `PutObject` it to
the artifact bucket under a `.mp3` key, read the duration straight from
`properties.durationInMilliseconds` (no probing needed), then `DELETE` the
synthesis job. Serve it later as a presigned GET URL.

---

## 1. Method, and the one conversion this benchmark rests on

Everything below is dated **2026-09-09**; every figure carries a URL in §16 or
inline. Where a number is *not* published by a vendor, it is labelled
**ESTIMATE** with its arithmetic, per AC #12.

### 1.1 The characters-per-minute basis (ESTIMATE)

Most TTS vendors bill per character but sell a product measured in minutes. To
compare them at all, this benchmark fixes:

> **1 000 billable characters ≈ 1 minute of synthesised speech**
> ⇒ **5 000 / 15 000 / 30 000 characters** for a 5 / 15 / 30-minute episode.

This is an **estimate**, not a vendor figure. Method and anchor:

- Azure publishes a per-voice `WordsPerMinute` property in its voice list and
  states it "can be used to estimate the length of the output speech". Sample
  values seen in the voice catalogue span **139 to 293** words per minute.
- At 1 000 characters/minute, 139–293 wpm implies **3.4 to 7.2 characters per
  word** including the trailing space. For the mid-range voices (150–190 wpm)
  that is 5.3–6.6 characters/word, which is the right order for European prose.
- **Counter-datum, disclosed:** Microsoft's own batch-synthesis example bills
  29 characters for 2 500 ms of audio, i.e. **696 characters/minute**. But that
  sample is a single five-word sentence ("The rainbow has seven colors."), and
  its leading/trailing silence dominates. It is not a usable basis for a
  30-minute continuous dialogue.

Because per-character pricing is linear, **a reader who prefers a different
basis can rescale every TTS figure in §4 by one multiplication.** At
850 chars/min, multiply by 0.85; at 1 200 chars/min, multiply by 1.2. Nothing
else in the recommendation moves.

Two sourced adjustments that are *not* folded into the tables, and why:

- **Azure counts each Chinese character as two for billing**, "including kanji
  used in Japanese, hanja used in Korean, or hanzi used in other languages".
  Real, and it will roughly double the `zh` and inflate the `ja` line. Not
  quantified here because converting that into a per-minute factor would require
  a characters-per-minute figure for CJK speech that no vendor publishes —
  inventing one would violate AC #12. Flagged as a known open risk in §12.
- Locale-dependent text expansion (French and German being wordier than English
  for the same content) is real but **no citable measurement was found**, so no
  factor is applied.

### 1.2 Currency

USD figures are converted at the repo's own constant, `USD_EUR = 0.86`
(`media_summarizer/core/services/llm_pricing.py`). Azure figures are taken
directly in EUR from the Azure Retail Prices API for `francecentral`, so no
conversion is applied to them.

### 1.3 What was read, and where

Vendor prices come from vendor pricing pages and, for Azure and AWS, from the
machine-readable price APIs (`prices.azure.com/api/retail/prices`,
`aws pricing get-products --region us-east-1` filtered on `location='EU (Paris)'`)
because both HTML pricing pages render their tables in JavaScript and return
placeholders to a fetcher.

For AC #2, `open-notebook` and `podcast-creator` were read **in their sources**,
not their READMEs: `pyproject.toml`, `src/podcast_creator/core.py`,
`src/podcast_creator/nodes.py`, `src/podcast_creator/retry.py`,
`commands/podcast_commands.py`. Dependency weight was **measured**, not
estimated, by resolving both wheel closures for `linux/aarch64` + CPython 3.12
(§13).

---

## 2. The owner's lead, settled in the sources (AC #2)

### 2.1 What `open-notebook` actually uses

**It does not implement a podcast pipeline.** It delegates the whole thing to a
separate PyPI package by the same author.

- `open-notebook` **1.14.0** declares `"podcast-creator>=0.12.0,<1"` in
  `[project.dependencies]` of its `pyproject.toml`. Licence: **MIT**.
  `requires-python = ">=3.11,<3.13"`.
- `commands/podcast_commands.py` contains exactly
  `from podcast_creator import configure, create_podcast`. The command is
  registered as `@command("generate_podcast", app="open_notebook", retry={"max_attempts": 1})`.
- So "the podcast module of open-notebook" is, factually, **`podcast-creator`**.
  The owner's hypothesis about which package is correct.

### 2.2 What `podcast-creator` is made of

`podcast-creator` **0.12.0**, `license = "MIT"`, `requires-python = ">=3.10.6"`.
Its declared dependencies:

`ai-prompter>=0.3.1`, `click>=8.0.0`, `content-core>=1.14.1`, `esperanto>=2.19.4`,
**`langgraph>=1.0.6`**, `loguru>=0.7.3`, **`moviepy>=2.2.1`**, `nest-asyncio>=1.6.0`,
**`pydub>=0.25.1`**, `python-dotenv>=1.1.1`, `requests>=2.0`, `pycountry>=24.6.1`,
`tenacity>=8.2.0`, **`tiktoken>=0.9.0`**; extra `ui = ["streamlit>=1.44.0"]`.

The pipeline, read in `src/podcast_creator/`:

1. `nodes.py` builds an outline, then a transcript, as LangGraph nodes.
2. `generate_all_audio_node` — *"Generate all audio clips using sequential
   batches to respect API limits"* — synthesises **one audio file per dialogue
   turn**, in batches of `TTS_BATCH_SIZE` (default **5**) via
   `await asyncio.gather(*batch_tasks)`, with a delay between batches.
3. `core.py::combine_audio_files` — *"Combines multiple audio files into a single
   MP3 file using moviepy"* — does
   `from moviepy import AudioFileClip, concatenate_audioclips`, then
   `final_clip = concatenate_audioclips(clips)` and
   `final_clip.write_audiofile(str(output_path), codec="mp3")`.

**That is the whole added value of the package over what we already own: step 3.**
Steps 1 and 2 are an LLM prompt chain — we have one, tuned for prompt caching,
with a corpus builder and a token cap.

### 2.3 Three shapes of adoption, arbitrated

| Option | Verdict | Why |
| --- | --- | --- |
| **(a) Depend on `podcast-creator`** | **Rejected** | +138.6 MB of wheels (3.48× the current closure, §13); six transitive wheels have **no glibc-2.17-compatible build**, so it cannot even install on the current Amazon Linux 2 base image; forces `tiktoken`, which this repo deliberately excluded (`BYTES_PER_TOKEN = 3.4  # tiktoken is not in the Lambda image`); forces `moviepy`, which drags `imageio-ffmpeg` (25.63 MB, ships an ffmpeg binary) — the exact dependency `audio_duration_probe.py` exists to avoid; and its own `pillow<12` cap collides with ours (§13.3). |
| **(b) Copy and adapt its code** | **Rejected** | The only part worth copying is `combine_audio_files`, and it is a five-line moviepy wrapper — copying it means adopting moviepy anyway. Its retry/orchestration logic is LangGraph-shaped and does not transplant onto an SQS worker. Its error convention is *in-band*: `combine_audio_files` returns `{"combined_audio_path": "ERROR: No valid clips"}` / `"ERROR: Concatenation failed - …"` / `"ERROR: Failed to write output audio - …"` as **strings**, so a caller that does not string-match a failure silently stores a broken path. `open-notebook`'s own code carries a comment noting that podcast-creator reports audio-combination failures in-band. |
| **(c) Reimplement only what we do not already own** | **Adopted — and the answer is "almost nothing"** | We own the corpus builder, the LLM call, the artifact store, the queue, the quota gate. What is missing is (i) a two-host script prompt and (ii) a call to a TTS provider. Choosing a provider that renders **one file** makes (iii) assembly disappear entirely. |

Two further reasons not to adopt, found in the sources:

- **`configure("templates", {...})` compiles Jinja2 template *source* supplied by
  the caller.** `open-notebook` carries an explicit `SECURITY NOTE` about this in
  `commands/podcast_commands.py`, referencing advisory `GHSA-f35w-wx37-26q7`
  (server-side template injection). Any adoption inherits the obligation to never
  route user-controlled text into that argument.
- **A factual correction to this task's own premise.** The task states that
  open-notebook documents "no automatic retry". That is true at **job** level
  (`retry={"max_attempts": 1}`, and its user docs say *"automatic retries are
  disabled to prevent confusion"*) but **false at call level**:
  `src/podcast_creator/retry.py` wraps each LLM call and each TTS clip in
  tenacity with `DEFAULT_MAX_ATTEMPTS = 3` and
  `wait_exponential(multiplier=5, max=30)`, excluding `ValueError`/`TypeError`
  and 4xx other than 429. Worth knowing because it means a "single attempt"
  episode can still have paid a provider up to three times per clip.

### 2.4 The nearest OSS alternative, for completeness

`podcastfy` **0.4.3**, `license = "Apache-2.0"`, is the other well-known
open-source "NotebookLM podcast" clone. Same structural problem, worse: its
declared dependencies include `pydub`, a package literally named `ffmpeg`,
`PyMuPDF`, `pandas`, `numpy<2`, `langchain` + `langchain-community` +
`langchain-google-vertexai` + `langchain-google-genai`, `litellm`, `elevenlabs`,
`edge-tts`, `google-cloud-texttospeech` — **and `sphinx-rtd-theme`, `nbsphinx`
and `pytest` as runtime dependencies**, which is a maintenance signal in itself.
Rejected on the same grounds as (a), with less to gain.

---

## 3. The candidates (AC #1) — 14 short-listed, 7 more set aside

Three families, as the task asks. "Multi-voice in one call" is the column that
decides the architecture; "Max audio per call" is the column that decides whether
we own an assembly step.

### Family A — OSS pipelines we would host ourselves

| # | Solution | Licence | Cost | Latency (published) | Languages | Multi-voice in one call | Max audio per call | Output format |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | **`podcast-creator` 0.12.0** (the podcast engine of `open-notebook` 1.14.0) | MIT | Free code; you pay the underlying TTS | **"10+ minutes for a 30-minute episode"** (open-notebook docs) | Whatever the chosen TTS supports | No — **one file per dialogue turn**, then moviepy `concatenate_audioclips` | 1 turn | MP3 (written by moviepy, `codec="mp3"`) |
| A2 | **`podcastfy` 0.4.3** | Apache-2.0 | Free code; you pay the underlying TTS | Not published | Whatever the chosen TTS supports | No — per-turn, then `pydub` | 1 turn | MP3 |
| A3 | **Kokoro-82M** (self-hosted model weights) | Apache-2.0 | Compute only (no per-character fee) | Not published for any Lambda-class target | **9** `lang_code` values: a, b, e, f, h, i, j, p, z (US/UK English, Spanish, French, Hindi, Italian, Japanese, Portuguese, Mandarin) | No | n/a | Raw waveform (you encode) |

**Family A verdict: all three rejected.** A1 and A2 both end at "N segments,
concatenate locally", which is the outcome we must avoid (§6). A3 additionally
fails the language requirement outright (**no `de`, no `nl`, no `ar`** — §7),
needs the `espeak-ng` **system binary** in the image, and its checkpoint alone is
327.21 MB, on top of a PyTorch runtime, inside a 10 GB image budget that would
then also need a GPU-less inference story with no published latency. A benchmark
cannot recommend an unmeasured latency for a 30-minute render against a 900 s
ceiling.

### Family B — TTS providers we drive ourselves

| # | Provider / model | Price (list) | Latency (published) | Languages | Multi-voice in one call | Max audio per call | Output format |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | **Azure AI Speech — batch synthesis, Neural (standard)** | **€12.88 / 1M chars** (`francecentral`, meter *S1 Neural Characters*) | **p50 10–20 s, p95 ≤120 s**, asynchronous | **All 11 of our locales** (§7) | **Yes** — many `<voice>` elements in one SSML doc; `<speak>`/`<voice>` markup **not billable** | 2 MB JSON payload; up to 1 000 `inputs`; 10 000 input limit. **No audio-length cap** — the API exists precisely "to create synthesized audio longer than 10 minutes" | MP3 / WAV / Opus / µ-law, incl. `audio-24khz-48kbitrate-mono-mp3` |
| B2 | Azure AI Speech — batch synthesis, **Neural HD** | €18.8906 / 1M chars (`francecentral`) | as B1 | Fewer locales than Neural; `hi-IN` and `en-*` covered, `ar` **not** | Yes, but HD voices do not support all SSML tags | as B1 | as B1 |
| B3 | Azure AI Speech — **real-time REST** | same per-character meter as B1 | Synchronous | as B1 | Yes (SSML) | **10 minutes** — beyond that the request is not the right tool (the docs point you to batch) | MP3 / WAV / Opus |
| B4 | **Amazon Polly — Neural** | $16 / 1M chars → **€13.76 / 1M** | Not published | `eu-west-3`: 100 voices, engines `neural` + `standard` only. **No `hi-IN` voice at all**; one `cmn-CN` female; Modern Standard Arabic (`arb`) is **standard-only, single female** | **No — `<voice>` is not a supported SSML tag** | `SynthesizeSpeech`: 3 000 billed chars, **audio truncated at 10 min**. `StartSpeechSynthesisTask`: 100 000 billed chars, writes to S3 | MP3 / OGG / PCM |
| B5 | Amazon Polly — **Standard** | $4 / 1M chars → **€3.44 / 1M** | Not published | as B4, lower quality | No | as B4 | as B4 |
| B6 | **OpenAI `tts-1` / `tts-1-hd`** | $15 / $30 per 1M chars → **€12.90 / €25.80 per 1M** | Not published | Not enumerated as a supported-locale list | No — one `voice` per request | Not published as a duration | MP3 / Opus / AAC / FLAC / WAV / PCM |
| B7 | OpenAI **`gpt-4o-mini-tts`** | $12 / 1M **audio output tokens** | Not published | as B6 | No | Not published | as B6 |
| B8 | **ElevenLabs** — v3 / Multilingual v2 | **$0.10 / 1 000 chars** → €86 / 1M | v3 ~280 ms model latency (excl. app+network) | 32 languages (v3) | **Partly** — *Text-to-Dialogue* takes multiple speakers, max **10 unique voice IDs** | Text-to-Dialogue: **≤2 000 characters advised** | MP3 / PCM / µ-law |
| B9 | ElevenLabs — Flash v2.5 / Turbo / v3-Conversational | **$0.05 / 1 000 chars** → €43 / 1M | Flash v2.5 **~75 ms** model latency (excl. app+network) | 32 languages | as B8 | as B8 | as B8 |
| B10 | **Deepgram Aura-2 / Aura-1** | $0.030 / $0.0150 per 1 000 chars → €25.80 / €12.90 per 1M | Not published as a per-request duration | **7 only**: en, es, de, fr, nl, it, ja | No | **2 000 characters** (413 beyond that) | MP3 / WAV / Opus / linear16 / µ-law / a-law / FLAC |
| B11 | **Gemini TTS** (2.5 Flash TTS / 2.5 Pro TTS / 3.1 Flash TTS) | $10 / $20 / $20 per 1M **audio output tokens**; billing note: **25 audio tokens per second** | Not published | 24 languages | **Yes — but 2 speakers maximum** | **≈21.3 minutes**: the session token window is 32 000 tokens, and 32 000 ÷ 25 tok/s = 1 280 s | **Headerless 24 kHz signed 16-bit PCM** — you write the WAV/MP3 header yourself |

### Family C — turnkey "make me a podcast" APIs

| # | Service | Price | Latency (published) | Languages | Multi-voice | Max duration | Output format |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | **AutoContent API** | **10 credits per episode regardless of duration**; Amateur €24/1 000 cr, Professional €58/5 000 cr, Enterprise €108/10 000 cr | **"typically takes 2-5 minutes"** | Multilingual (not enumerated per locale) | Yes (two hosts, fixed format) | `duration` presets only: `short` 3–5 min, `default` 8–12 min, **`long` 15–20 min** — **no 30-minute option** | MP3 (URL returned) |
| C2 | **Wondercraft** | ~10 credits per minute; Creator $25 / 1 000 credits; **account cap 100 min/month** | Async job, not published | Multilingual | Yes | Not published | MP3 |
| C3 | **Jellypod** | **1 credit per second** (60/min); Creator $50 / 11 000 credits; **cap 183 min/month**, **30-min episode maximum** | Async job, not published | Multilingual | Yes | 30 minutes | MP3 |
| C4 | **NotebookLM Enterprise "Audio Overview"** | **No published price** | Not published | `languageCode` parameter, set not enumerated | Fixed 2 hosts | Not published | `mimeType`: WAV or MP4 |

**Family C verdict: all four rejected, each for a different structural reason.**

- **C1** is by far the cheapest thing in this entire benchmark — **€0.108–€0.24 per
  episode flat, regardless of length**, which beats Azure at 15 minutes and
  crushes it at 30. It loses on **product shape**, not price: its longest preset
  is 15–20 minutes, its output format and voice cast are not ours to choose, and
  it re-ingests our sources rather than consuming the corpus we have already
  built, cached and quota-metered. Worth re-opening if the product ever wants a
  fixed ~10-minute "daily digest" and nothing else.
- **C2 and C3 are subscription-capped, not usage-priced.** A 100-min or 183-min
  *account* ceiling cannot back a per-user backend: a single Audio-Heavy
  subscriber's monthly allowance would consume most of it. And at €6.45–€7.04 per
  30-minute episode they are **16–18× Azure**.
- **C4 has no retrieval path.** The generation API exists only in
  `discoveryengine.googleapis.com` **v1alpha** (revision 20260831):
  `projects.locations.notebooks.audioOverviews.create` (POST) and `.delete` —
  **no `get`, no `list`**. The `GoogleCloudNotebooklmV1alphaAudioOverview`
  schema carries only `name`, `audioOverviewId`, `mimeType`, `languageCode`,
  `generationOptions`, `status`; **no URI, no bytes, no GCS path appears anywhere
  in the v1alpha schema set**. `audioOverview` appears **0 times** in the v1beta
  and v1 discovery documents. You can ask for an episode and you cannot fetch it.

### Family B verdict, in one line each

| | Why not | |
| --- | --- | --- |
| B2 | Costs 47% more than B1 and **drops Arabic**. | |
| B3 | 10-minute ceiling ⇒ 3 calls for a 30-minute episode ⇒ we own the assembly. | |
| B4/B5 | **`<voice>` unsupported** ⇒ one synthesis task per dialogue turn (60–150 tasks for a 30-minute two-host episode) ⇒ we own the assembly. Plus **no Hindi voice at all in `eu-west-3`**, and the better `generative`/`long-form` engines are **not offered in `eu-west-3`**. | |
| B6/B7 | One voice per request ⇒ per-turn calls ⇒ we own the assembly. B7 is **not even costable**: priced per audio output token with no published tokens-per-second. | |
| B8/B9 | 6.7× (B8) / 3.3× (B9) the price of B1, and ≤2 000 characters per Text-to-Dialogue request ⇒ ~15 calls for a 30-minute episode ⇒ we own the assembly. | |
| B10 | **7 languages.** Fails `pt`, `zh`, `ar`, `hi` outright. Notable because Deepgram is already our STT provider, so reusing it would have saved a credential — it cannot serve our locale set. | |
| B11 | 2 speakers max is survivable; **≈21.3 min per call is not**, so a 30-minute episode needs ≥2 calls and local stitching — and the output is **headerless PCM**, so we would also own container writing. | |

### Also considered, and set aside with the decisive fact

The task's description names seven further candidates. Each was checked; none
reaches the short-list, and for four of them the reason is that **no usable public
API exists**.

| Candidate | Family | Public API? | Decisive fact (checked 2026-09-09) |
| --- | --- | --- | --- |
| **Cartesia** (Sonic-3.6) | B | Yes — REST + WebSocket, `X-API-Key` | **44 languages** incl. `ar` and `hi` — the best coverage in this whole benchmark — but **one voice per call**: *"Pass either a voice ID string or an object with a required `id`"*, *"Use the same value for all generation requests made to the same context."* A dialogue is therefore N calls plus our own concatenation. Priced in monthly credits (Free 20K ≈ 27 min TTS, Pro $5 / 100K ≈ 133 min, Startup $49 / 1.25M ≈ 1 667 min) with **no published per-character overage rate**, and **commercial use requires Pro or above**. **ESTIMATE** from the Startup tier: $49 ÷ 1 667 min = $0.0294/min → €0.0253/min → **≈ €0.76 for a 30-min episode, about 2× Azure**. |
| **PlayHT / PlayAI** | B | **Could not be evaluated** | `play.ht`, `www.play.ht`, `play.ai` and `www.play.ai` **do not resolve** (DNS `ENOTFOUND`), and `docs.play.ai` presents an **expired TLS certificate** (`ssl_verify_result=10`). A vendor whose own documentation host is unreachable is not a dependency this benchmark can recommend. |
| **Hume Octave** | B | Yes | Billed per 1 000 characters, tier-dependent: **$0.15/1k (Creator) down to $0.05/1k (Business)**. At 30 000 characters that is $4.50 → **€3.87** at the entry rate and $1.50 → **€1.29** at the highest-volume rate — **3.3× to 10× Azure**. The pricing page publishes **no supported-language count**, so 11-locale coverage cannot be certified. |
| **XTTS-v2** (Coqui) | A | Weights only | 17 languages incl. `ar` and `hi`. Released under the **Coqui Public Model License** — and **the licence text is no longer retrievable**: `https://coqui.ai/cpml`, the exact URL the model card points to, returns **HTTP 404**. A model whose licence terms cannot be read cannot be adopted, whatever its quality. |
| **Chatterbox** (Resemble AI) | A | Weights only, **MIT** | Multilingual V3, 0.5B parameters, **23 languages** incl. Arabic and Hindi — coverage passes, and MIT is clean. But it generates **one utterance at a time with a single reference voice** (`model.generate(text, audio_prompt_path=…)`), so a dialogue is per-turn plus our concatenation — and it is a 0.5B model to host, with no published latency for any Lambda-class target. |
| **Podcastle** (now `async.com`) | C | **No developer API documented** | `podcastle.ai/pricing` 308-redirects to `async.com/pricing`, which mentions no developer API, renders **no dollar figure** for any paid tier, and meters TTS in credits ("15+ languages"; Pro ≈ "10 hours (500k characters)"). Not integrable. |
| **Google Illuminate** | C | **No public API** | `illuminate.google.com` is a sign-in-gated Google **"Experiment"**; the page documents no API, no endpoint, no pricing. The only Google audio-generation surface with an addressable API is the NotebookLM `audioOverviews` v1alpha resource (C4 above) — and that one cannot return the audio. |

Note the pattern: **six of these seven, plus every Family-B provider except Azure,
fail on the same axis** — one voice per call. Multi-voice-in-one-file is rare, and
it is the single property that decides whether we own an audio assembly step.


---

## 4. Cost in EUR per episode, LLM and TTS separated (AC #3)

### 4.1 The LLM script (identical for every candidate)

The script is written by the existing layer, so this cost is the **same whichever
TTS wins** — which is why the two must be reported separately.

Inputs, all from the repo:

- Model `gpt-5.4-nano-2026-03-17`; price **$0.20 / $0.02 / $1.25** per 1M input /
  cached-input / output tokens (`llm_pricing.py`).
- Worst case input = the folder corpus cap, `MAX_FOLDER_CORPUS_TOKENS = 120_000`.
- Output tokens = script characters ÷ `BYTES_PER_TOKEN = 3.4`.
- `USD_EUR = 0.86`.

| Episode | Script chars | Output tokens | Uncached input | LLM total (USD) | **LLM total (EUR)** | Fully-cached-prefix floor (EUR) |
| --- | --- | --- | --- | --- | --- | --- |
| 5 min | 5 000 | 1 471 | 120 000 | $0.02584 | **€0.0222** | €0.0036 |
| 15 min | 15 000 | 4 412 | 120 000 | $0.02951 | **€0.0254** | €0.0068 |
| 30 min | 30 000 | 8 824 | 120 000 | $0.03503 | **€0.0301** | €0.0115 |

The "fully-cached-prefix floor" is what the same call costs when the corpus prefix
hits OpenAI's exact-prefix cache — the layout the corpus builder is already
engineered for. Real cost sits between the two columns. **A media-scope episode
is cheaper than these figures**, because a single media item's corpus is far under
the 120 000-token folder cap; the table is deliberately the worst case.

The LLM is **not** the cost driver: at 30 minutes it is **12.8×** smaller than the
Azure TTS bill.

### 4.2 TTS, per episode (at 1 000 chars/min — §1.1)

| Candidate | €/1M chars (derivation) | **5 min** (5 000 ch) | **15 min** (15 000 ch) | **30 min** (30 000 ch) |
| --- | --- | --- | --- | --- |
| **B1 Azure Neural (recommended)** | €12.88 (direct, `francecentral`) | **€0.0644** | **€0.1932** | **€0.3864** |
| B5 Polly Standard | €3.44 ($4 × 0.86) | €0.0172 | €0.0516 | €0.1032 |
| B10 Deepgram Aura-1 | €12.90 ($15 × 0.86) | €0.0645 | €0.1935 | €0.3870 |
| B6 OpenAI `tts-1` | €12.90 ($15 × 0.86) | €0.0645 | €0.1935 | €0.3870 |
| B11 Gemini 2.5 Flash TTS | €8.60/1M **audio tokens**; 1 500 tok/min | €0.0645 | €0.1935 | €0.3870 |
| B4 Polly Neural | €13.76 ($16 × 0.86) | €0.0688 | €0.2064 | €0.4128 |
| B2 Azure Neural HD | €18.8906 (direct, `francecentral`) | €0.0945 | €0.2834 | €0.5667 |
| B6 OpenAI `tts-1-hd` | €25.80 ($30 × 0.86) | €0.1290 | €0.3870 | €0.7740 |
| B10 Deepgram Aura-2 | €25.80 ($30 × 0.86) | €0.1290 | €0.3870 | €0.7740 |
| B11 Gemini 2.5 Pro TTS / 3.1 Flash TTS | €17.20/1M audio tokens | €0.1290 | €0.3870 | €0.7740 |
| Azure **legacy** Long Audio meter | €85.8664 (direct, `francecentral`) | €0.4293 | €1.2880 | €2.5760 |
| B9 ElevenLabs Flash/Turbo/v3-Conv. | €43 ($0.05/1k × 0.86) | €0.2150 | €0.6450 | €1.2900 |
| B8 ElevenLabs v3 / Multilingual v2 | €86 ($0.10/1k × 0.86) | €0.4300 | €1.2900 | €2.5800 |
| B7 OpenAI `gpt-4o-mini-tts` | **not computable** | — | — | — |

Turnkey services, priced per episode rather than per character:

| Candidate | 5 min | 15 min | 30 min |
| --- | --- | --- | --- |
| **C1 AutoContent** (10 credits flat, Enterprise / Professional / Amateur tier) | €0.108 / €0.116 / €0.24 | €0.108 / €0.116 / €0.24 | **not offered** (max preset 15–20 min) |
| C2 Wondercraft (Creator, ~10 cr/min) | €1.075 | €3.225 | €6.450 |
| C3 Jellypod (Creator, 60 cr/min) | €1.173 | €3.518 | €7.036 |
| C4 NotebookLM Enterprise | no published price | no published price | no published price |

**Two important caveats on that legacy Azure line.** `francecentral` still exposes
a meter named `S1 Neural Long Audio Characters` at **€85.8664 / 1M** — 6.7× the
standard Neural meter. That is the **Long Audio API**, which **retires
2027-04-01** and which the batch-synthesis API replaces. Batch synthesis bills on
the ordinary `neuralCharacters` meter (the `GET` response literally reports
`billingDetails.neuralCharacters`). Do **not** let an implementer wire the Long
Audio API: it is the expensive, deprecated door to the same room. (Separately,
the retail price feed also carries a `Commitment Tier … 2000M Unit` monthly line
whose figure is four orders of magnitude larger; it is a monthly commitment, not
a per-character rate, and is not applicable to us.)

### 4.3 All-in per episode, for the recommendation

| Episode | LLM (worst case) | Azure TTS | **Total** |
| --- | --- | --- | --- |
| 5 min | €0.0222 | €0.0644 | **€0.0866** |
| 15 min | €0.0254 | €0.1932 | **€0.2186** |
| 30 min | €0.0301 | €0.3864 | **€0.4165** |

S3 storage and egress add **≈€0.001 per episode ever downloaded** (§8.4) — three
orders of magnitude below the synthesis, so they are ignored in the metering rule.

---

## 5. Compute envelope (AC #4)

### 5.1 The envelope we have

| Constraint | Value | Source |
| --- | --- | --- |
| Lambda timeout, hard ceiling | **900 s** | AWS Lambda quotas |
| Lambda memory | 128 – 10 240 MB (1 vCPU at 1 769 MB) | AWS Lambda quotas |
| Lambda `/tmp` | 512 MB – 10 240 MB | AWS Lambda quotas |
| Container image, uncompressed | 10 GB | AWS Lambda quotas |
| `artifact_generator` today | **512 MB / 300 s**, ARM64, `public.ecr.aws/lambda/python:3.11-arm64` | repo |
| Generation lease | `GENERATION_LEASE_SECONDS = 300` (`artifact_service.py`) | repo |
| Queue | one unified `artifact-generator-queue` (task-195) | repo |

### 5.2 Named envelope: **unchanged — 512 MB / 300 s, submit-then-poll**

The recommendation **fits inside the current envelope with room to spare**, and it
does so by never synthesising audio in-process.

Invocation 1 (script + submit):
1. Build the corpus (existing code path).
2. One LLM call → the two-host script. This is the longest single step, and it is
   the same call shape that already fits in 300 s for the five existing artifact
   types.
3. Render one SSML document; `PUT` the batch synthesis job. Return.

Invocation 2..n (poll):
4. `GET` the job. If `Running`, re-enqueue with a delay and return.
5. On `Succeeded`: download `outputs.result` (a ZIP), extract the single audio
   file (**10.8 MB** at 30 minutes), `PutObject` to the artifact bucket, read
   `properties.durationInMilliseconds`, `DELETE` the job, mark the artifact ready.

The sourced latencies that make this work — and that make the alternatives fail:

| Path | Sourced latency | Fits 900 s? |
| --- | --- | --- |
| **Azure batch synthesis (recommended)** | **p50 10–20 s; p95 ≤120 s**, asynchronous | Yes, trivially — and it is asynchronous, so the wall-clock is not even ours |
| `podcast-creator` / `open-notebook` | **"10+ minutes for a 30-minute episode"** | **No** — exceeds 900 s at the documented figure, before any margin |
| AutoContent | "typically takes 2-5 minutes" | Yes if synchronous-polled, but the product does not do 30 minutes |
| Any per-turn provider (Polly, OpenAI, Deepgram, ElevenLabs) | Per-request latency **not published** by any of them | **Unknowable** — 60–150 sequential requests against an unpublished per-request latency is not something a benchmark can certify against a hard ceiling |

That last row is the real argument. Even at a generous 3 s per turn, 120 turns is
360 s of pure network time *plus* concatenation, i.e. past the current 300 s
timeout, and the figure cannot be sourced. Choosing a provider that renders one
file removes the question entirely rather than answering it optimistically.

### 5.3 What is therefore *not* recommended, and why

- **Raise memory / timeout:** not needed. Nothing in the flow is CPU-bound and
  the largest object in memory is a 10.8 MB MP3. Raising memory would only buy
  vCPU we have no use for.
- **Per-segment fan-out on `artifact-generator-queue`:** explicitly rejected.
  It is the shape that creates the "already synthesised and already paid for"
  reconciliation problem (§12), and it exists only to serve providers that cannot
  render one file.
- **Step Functions:** rejected. It would add a new orchestration primitive to the
  stack to express a two-state machine (`submitted` → `succeeded`) that a delayed
  SQS message already expresses, using the exact pattern the repo already runs for
  Apify (`apify_orchestration.start_run_for_job` + the delayed-SQS
  `apify_backstop` + `apify_state` on the job).
- **Fargate:** rejected. There is no long-running or CPU-heavy step to host.

### 5.4 The one coupling an implementer must not miss

`GENERATION_LEASE_SECONDS = 300` is measured against wall-clock, and a polled job
spans **several invocations**. A job that needs three poll hops can exceed 300 s
of wall-clock while every individual invocation is short — at which point the
lease looks abandoned, a second worker picks the artifact up, and **we pay Azure
twice for the same episode**.

So: **the lease must be re-armed on every poll hop**, and the Azure synthesis id
must be derived deterministically from the `artifact_id` so that even a duplicated
worker converges on the same job rather than creating a second one. Because
`PUT` on an existing synthesis id is not documented as idempotent, the worker
should `GET` first and only `PUT` when the job is absent (the API answers
**HTTP 204** for "request successful, but the resource doesn't exist", and
**404** for an unknown synthesis id).

Rate limit to respect: **100 requests per 10 s per Speech resource**, HTTP 429
beyond. One poll per job is nowhere near it.

---

## 6. Audio assembly (AC #5)

### 6.1 The fact this must be answered against

`media_summarizer/core/services/audio_duration_probe.py` exists, in its own words,
for *"Audio duration probing without an ffmpeg dependency (task-250 Layer 1)"*. It
hand-parses ID3v2 tags, MPEG frame headers, MP4 `moov`/`mvhd` boxes, Ogg granule
positions, WAV `fmt `/`data` chunks and FLAC STREAMINFO over HTTP Range requests
— several hundred lines of container parsing — **specifically so that ffmpeg is
not in the worker image**. That is a deliberate, paid-for architectural choice,
not an accident. `pydub` (which shells out to ffmpeg) and `moviepy` (which pulls
`imageio-ffmpeg`, a wheel that *ships an ffmpeg binary*) are absent for the same
reason.

### 6.2 Verdict: **one file, rendered by the provider. Zero concatenation.**

Azure batch synthesis offers two provider-side mechanisms, either of which
produces a single audio file:

1. **One SSML document with several `<voice>` elements.** SSML is explicitly
   designed to "attribute multiple voices to a single document", and
   `<speak>`/`<voice>` markup is on the **non-billable** list, so the multi-voice
   structure is free. One `inputs` entry → one output file.
2. **`properties.concatenateResult: true`** with up to 1 000 `inputs`: each
   synthesised result is written to the same audio output file.

Mechanism 1 is the recommendation (simpler; one document; the turn order is the
document order). Mechanism 2 is the fallback if a script ever needs to exceed the
payload limit.

Sizes check out: the JSON payload limit is **2 MB**, and a 30-minute episode is
~30 000 characters ≈ **30 KB** of text. Two orders of magnitude of headroom.

### 6.3 What this adds to the worker image

**Nothing.** The whole integration is:

- three HTTP calls (`PUT`, `GET`, `DELETE`) with an `Ocp-Apim-Subscription-Key`
  header, over the HTTP client already in the image;
- one `zipfile` read — **stdlib**;
- one string-templated SSML document — stdlib.

**No ffmpeg, no pydub, no moviepy, no `azure-cognitiveservices-speech` SDK, no new
Python dependency at all.** The Speech SDK is deliberately not used: it exists for
real-time streaming, and the batch API is plain REST.

A bonus consequence: `audio_duration_probe` does not even need to run on this
artifact. The batch `GET` response returns `properties.durationInMilliseconds` and
`properties.sizeInBytes` for the rendered file, so the duration is known
authoritatively before the bytes are stored.

### 6.4 What the rejected paths would have cost

Every non-Azure candidate ends in local concatenation, which means one of:

- **`moviepy`** → `imageio-ffmpeg` (25.63 MB, ships an ffmpeg binary) + `numpy`
  (15.67 MB) + `pillow` — and reverses task-250's decision;
- **`pydub`** → requires an ffmpeg/avconv **system binary** in the image, which
  the Amazon Linux 2 base does not provide, so it means vendoring a static
  ffmpeg build and owning its security updates;
- **hand-rolled MP3 frame splicing** → technically possible for constant-bitrate
  MP3 (concatenating frame streams), but it means writing and owning a bitstream
  editor to save an API parameter. Rejected on maintenance grounds.

---

## 7. Language coverage for the 11 locales (AC #6)

`mobile/src/i18n/locales.ts` ships
`["en","fr","es","de","it","pt","nl","ja","zh","ar","hi"]`, with
`FALLBACK_LOCALE = "en"` and `RTL_LOCALES = ["ar"]`. A two-host dialogue needs
**two distinguishable voices per locale** — in practice one Female + one Male.

### 7.1 Azure Neural (the recommendation): 11/11 served

Voice counts and genders below are read off the Azure *Language and voice support*
table (`?tabs=tts`). The named pairs are a concrete, verified default cast; an
implementer should re-read the table at implementation time in case the catalogue
has moved.

| Locale | Azure locale used | Neural voices available | Verified Female / Male default pair |
| --- | --- | --- | --- |
| `en` | `en-US` (also `en-GB`: 20) | **118** | `en-US-JennyNeural` (F) / `en-US-GuyNeural` (M) |
| `fr` | `fr-FR` | **23** | `fr-FR-DeniseNeural` (F) / `fr-FR-HenriNeural` (M) |
| `es` | `es-ES` | **24** | `es-ES-ElviraNeural` (F) / `es-ES-AlvaroNeural` (M) |
| `de` | `de-DE` | **23** | `de-DE-KatjaNeural` (F) / `de-DE-ConradNeural` (M) |
| `it` | `it-IT` | **26** | `it-IT-ElsaNeural` (F) / `it-IT-DiegoNeural` (M) |
| `pt` | `pt-PT` (also `pt-BR`: 28) | **5** (2 F / 3 M) | `pt-PT-RaquelNeural` (F) / `pt-PT-DuarteNeural` (M) |
| `nl` | `nl-NL` | **7** (4 F / 3 M) | `nl-NL-ColetteNeural` (F) / `nl-NL-MaartenNeural` (M) |
| `ja` | `ja-JP` | **12** (6 F / 6 M) | `ja-JP-NanamiNeural` (F) / `ja-JP-KeitaNeural` (M) |
| `zh` | `zh-CN` | **66** | `zh-CN-XiaoxiaoNeural` (F) / `zh-CN-YunxiNeural` (M) |
| **`ar`** | `ar-EG` (16 Arabic locales available) | **32 total** — every Arabic locale ships exactly **1 F + 1 M** | `ar-EG-SalmaNeural` (F) / `ar-EG-ShakirNeural` (M) |
| **`hi`** | `hi-IN` | **9 Standard** (5 M / 4 F) **+ 8 HD / HD-Flash** | `hi-IN-SwaraNeural` (F) / `hi-IN-MadhurNeural` (M) |

### 7.2 Explicit verdict on `ar` and `hi`

**`ar` — served, with the thinnest margin of the eleven.** Arabic has *no HD
tier* on Azure, and each of the 16 Arabic locales carries exactly **one Female and
one Male** Standard voice. That is precisely enough for a two-host dialogue and
**not one voice more**: there is no room for a third host, no room for a voice
that is unavailable, and no upgrade path to HD. `ar-EG` is the recommended
default (largest Arabic-speaking audience of the 16 available locales). The
mobile side already flags `ar` as RTL, which affects the transcript display, not
the audio.

**`hi` — fully served, with margin.** Nine Standard voices, comfortably
gender-balanced (`hi-IN-Swara` F / `hi-IN-Madhur` M as the default pair, plus
`Aarav`, `Aarti`, `Ananya`, `Arjun`, `Kavya`, `Kunal`, `Rehaan`), **and** eight
`MAI-Voice-2` HD / HD-Flash entries (`hi-IN-Arjun:MAI…`, `Dhruv`, `Kavya`,
`Priya`, each in HD and HD-Flash). Hindi is the locale where the *rival* providers
collapse, which makes it the single most decisive column in this benchmark.

### 7.3 How the rejected providers fare on the same 11 locales

| Provider | Verdict on our 11 locales |
| --- | --- |
| **Amazon Polly (`eu-west-3`, 100 voices, engines `neural`+`standard`)** | **Fails.** **No `hi-IN` voice exists at all** — the closest is `en-IN` bilingual (Aditi, Kajal). Mandarin is a single female (`cmn-CN` Zhiyu), so no two-host cast. Modern Standard Arabic (`arb`) is one female, `standard` engine only; a neural Arabic pair exists only in Gulf Arabic (`ar-AE` Hala + Zayd). No male *neural* voice in `nl-NL` or `pt-PT`. |
| **Deepgram Aura** | **Fails hardest.** **7 languages**: en, es, de, fr, nl, it, ja. No `pt`, no `zh`, no `ar`, no `hi`. Worth stating plainly because Deepgram is already our STT provider and reusing it would have saved provisioning a credential — it simply cannot serve the locale set. |
| **ElevenLabs** | 32 languages incl. `ar` and `hi`; passes on coverage, loses on price (3.3–6.7× Azure) and the ≤2 000-character dialogue request. |
| **Gemini TTS** | 24 languages; passes on coverage, loses on the ≈21.3-minute per-call ceiling, 2-speaker cap and headerless PCM. |
| **Kokoro-82M** | **Fails.** 9 `lang_code` values (a, b, e, f, h, i, j, p, z) → **no `de`, no `nl`, no `ar`**. |
| **OpenAI TTS** | No enumerated supported-locale list to check against, which is itself disqualifying for a benchmark that must certify 11 locales. |
| **Turnkey C1–C4** | All advertise "multilingual" without an enumerated locale list, so none can be certified against the 11. |

---

## 8. Delivering the audio bytes (AC #7)

### 8.1 Why the existing route cannot do it

`GET /api/artifacts/{artifact_id}/content` is declared
`response_model=ArtifactContentResponse`, whose `content` field is typed
`Dict[str, Any]`, and its docstring says it *"downloads the blob and inlines the
parsed content in the response so the mobile client doesn't need to deal with
presigned URLs"*. It parses JSON and inlines it. Audio can be neither parsed as
JSON nor sensibly base64-inlined: 10.8 MB of MP3 becomes ~14.4 MB of base64 in a
JSON body, with no seeking and no partial fetch.

### 8.2 Recommendation: a sibling route returning a presigned S3 GET URL

- **New route**, e.g. `GET /api/artifacts/{artifact_id}/audio-url`, returning a
  short-lived presigned URL and the metadata the player needs
  (`duration_seconds`, `content_type`, `size_bytes` — all three already known from
  the batch synthesis response, §6.3).
- Implemented with **`media_summarizer/utils/s3.py::generate_presigned_url`**,
  which already exists and is already used for exactly this purpose in
  `api/endpoints/media.py` (`# Generate pre-signed S3 GET URL (10 min validity)`,
  `expiration=AUDIO_PRESIGNED_URL_EXPIRATION, http_method="GET"`). **No new code
  shape, no new dependency, no new IAM pattern.**
- **Rejected: streaming the bytes through the API.** Every byte would pass through
  Lambda (paid twice, once egress from S3 and once from Lambda), the response
  would fight the API Gateway payload limit, and seeking would require
  reimplementing `Range` handling.
- **Rejected: CloudFront.** A distribution plus signed URLs/cookies to front
  ~11 MB per episode whose egress costs a tenth of a cent (§8.4). Revisit only if
  episodes are ever shared publicly.

### 8.3 Format, bitrate, weight

Recommended Azure `outputFormat`: **`audio-24khz-48kbitrate-mono-mp3`**.

- **Mono**, because a two-host dialogue carries no stereo information.
- **24 kHz**, because it is the native sample rate of the Neural voices ("each
  standard voice model is available at 24 kHz and high-fidelity 48 kHz") and the
  content is speech.
- **48 kbit/s**, which is a normal speech-podcast bitrate.

Weight (arithmetic: 48 000 bit/s ÷ 8 = 6 000 bytes/s):

| Episode | Bytes | Size |
| --- | --- | --- |
| 5 min (300 s) | 1 800 000 | **1.8 MB** |
| 15 min (900 s) | 5 400 000 | **5.4 MB** |
| 30 min (1 800 s) | 10 800 000 | **10.8 MB** |

If the owner ever judges 48 kbit/s too thin, `audio-24khz-96kbitrate-mono-mp3`
doubles every figure above and changes nothing else in the architecture.

### 8.4 Seek support: verified, not assumed

A presigned S3 GET URL on a `-dev` bucket was issued and re-fetched with a
`Range: bytes=0-9` header. S3 answered **`206 Partial Content`** with
**`Accept-Ranges: bytes`** and **`Content-Range: bytes 0-9/100416`**. So byte-range
seeking works over a presigned URL with no extra infrastructure, which is what a
mobile audio player needs to scrub. (The presigned URL itself is a credential and
is deliberately not reproduced here.)

### 8.5 Storage and egress cost, `eu-west-3`

From the AWS Price List API filtered on `location='EU (Paris)'`:

| Item | Rate | Cost for one 30-min episode |
| --- | --- | --- |
| S3 Standard storage (first 50 TB) | $0.024 / GB-month | **$0.00026 / month** |
| Data transfer out (first 10 TB/month, beyond the 100 GB/month free tier) | $0.090 / GB | **$0.00097 per full download** |
| GET requests | $0.0042 / 10 000 | **$0.00000042 per request** |

Three orders of magnitude under the synthesis cost. Not worth metering.

### 8.6 One code change this forces

`build_artifact_storage_key` currently returns
`f"{artifact_type.value}/{artifact_id}.json"` — the extension is hard-coded. It
must become type-aware so this type lands on a `.mp3` key. Nothing is deployed, so
this is a straight edit with no migration and no dual-write.

---

## 9. Metering (AC #8)

### 9.1 The validated decision this must live inside

task-287 (`owner_decision: ok`, validated 2026-08-18) fixed:

- **The unit is the minute, and nothing else.** No second currency, no "credits".
- **1 minute = 0.00664 EUR of provider budget**, and *"the internal debit for any
  action is `round(real_cost / 0.00664)` with a floor of zero"*.
- Tiers: Reader **60 min** (3 EUR), Mix **300 min** (5 EUR), Audio-Heavy
  **720 min** (9 EUR).
- Two rows of the conversion table matter here:
  **"AI generation over one item → charged 0 → free"** (real cost 0.0005–0.0032 EUR)
  and **"AI generation over a collection → 1 per 5 sources"**, implemented as
  `quota_enforcer.minutes_for_folder_sources` (1 per 5 sources, `MAX_FOLDER_SOURCES = 25`).

**This proposal does not invent a new unit.** It adds one row to that table, using
task-287's own formula.

### 9.2 The formula, derived not invented

Apply `round(real_cost / 0.00664)` to §4.3:

| Episode | Real cost | Exact units | task-287-derived debit |
| --- | --- | --- | --- |
| 5 min | €0.0866 | 13.04 | 13 |
| 15 min | €0.2186 | 32.92 | 33 |
| 30 min | €0.4165 | 62.73 | 63 |

Proposed **closed form**, which dominates every derived value while staying
trivially explainable:

> **`metered_minutes = 2 × target_minutes + 5`**

Where each term comes from:

- **The `2`** — Azure Neural at €12.88 / 1M characters × 1 000 chars/min =
  **€0.01288 per minute of audio**; €0.01288 ÷ €0.00664 = **1.94**, rounded up.
- **The `+5`** — worst-case LLM script €0.0301 ÷ €0.00664 = **4.53**, rounded up.
  It is not a coincidence that this equals 5: `minutes_for_folder_sources` already
  charges exactly **5** for a full 25-source folder (25 ÷ 5), so **the flat term is
  literally the existing folder-corpus price**, and the rule reads as "the folder
  corpus you already pay for, plus two minutes per minute of audio".

| Episode | Charged | Cost covered | Real cost | Margin |
| --- | --- | --- | --- | --- |
| 5 min | **15** | €0.0996 | €0.0866 | +15.0% |
| 15 min | **35** | €0.2324 | €0.2186 | +6.3% |
| 30 min | **65** | €0.4316 | €0.4165 | +3.6% |

Worst-case over-billing is **1.15×**, which is *better than the worst row already
accepted in task-287's table* (YouTube-with-captions, 1.5×). The margin is
deliberately front-loaded on short episodes, where it also absorbs the CJK
character-doubling risk (§1.1) and a single retried LLM call.

### 9.3 The departure from task-287 that must be flagged

**Media-scope generation cannot stay free for this type.** task-287 charges 0 for
"AI generation over one item" because its real cost is €0.0005–€0.0032. A
5-minute audio digest over a single item costs **€0.0866** — **27× to 173× that
row**. The free-media rule rests on "the cost is dust"; here it is not dust,
because the expense is the *output*, which did not exist at ingestion time and
therefore was not paid for when the item was ingested.

So the proposed rule is: **`2 × target_minutes + 5` at both scopes**, media
included, and this type is the first artifact type that is not free at media
scope. Everything else in task-287 is untouched — same unit, same conversion
constant, same formula, same tiers.

### 9.4 What this does to the ladder — the finding that shapes the product

| | Reader (60) | Mix (300) | Audio-Heavy (720) |
| --- | --- | --- | --- |
| 5-min episodes / month | 4 | 20 | 48 |
| 15-min episodes / month | **1** | 8 | 20 |
| 30-min episodes / month | **0 — cannot afford a single one** | 4 | 11 |

A 30-minute episode costs 65 metered minutes against a Reader allowance of 60.
**It does not fit at all.** Offering a duration a whole tier can never buy is a
support ticket, not a feature.

Hence the recommendation in the header: **expose `5` and `15` minutes only.** That
gives Reader one long episode or four short ones per month, Mix a comfortable
weekly habit, and Audio-Heavy twenty. If the owner wants 30 minutes, the honest
options are (a) gate it above Reader, or (b) revisit the Reader allowance in
task-287 — a decision that belongs to the owner, not to this benchmark.

---

## 10. Artifact type identifier and `parameters` (AC #9)

### 10.1 The collision

`podcast` is already taken: it denotes **an episode ingested from PodcastIndex**,
a *source* the user subscribed to. Reusing it for a *generated* artifact would
make "podcast" mean both an input and an output in the same codebase.

### 10.2 Recommendation: **`audio_digest`**

`MediaArtifactType.AUDIO_DIGEST = "audio_digest"`. Verified: the strings
`audio_digest` and `audio_overview` appear **nowhere** in `media_summarizer/` or
`mobile/src/` today, so neither collides.

Alternatives considered and rejected:

| Candidate | Rejected because |
| --- | --- |
| `podcast` | The collision itself. |
| `podcast_episode` | Worse — it reads as a PodcastIndex episode. |
| `audio_overview` | Google's product name for the NotebookLM feature. Borrowing a competitor's feature name into our own enum and S3 prefix is gratuitous. |
| `audio_summary` | Sits inside the `summary_short` / `summary_detailed` family and implies it is a third summary flavour, which it is not (different cost class, different delivery, different metering). |
| `briefing` | Carries no audio connotation; a future text briefing would then have nowhere to go. |

`audio_digest` is a valid Python identifier, a valid enum value, a valid S3 key
prefix and a valid bucket-name fragment, so it drops straight into
`get_artifact_bucket` / `build_artifact_storage_key`.

### 10.3 `parameters` to expose

| Key | Type | Values | Why |
| --- | --- | --- | --- |
| `target_minutes` | int, **closed set** | `5`, `15` | Drives the whole cost and the metered debit (§9). Must be a closed set, not a free integer — see §10.4. |
| `hosts` | int, **closed set** | `1`, `2` | `2` is the default and works in all 11 locales (§7.1). `1` is a monologue, cheaper to prompt, useful where a single voice reads better. `3+` is not offered: Arabic has exactly two voices. |
| `tone` | str, **closed enum** | e.g. `neutral`, `lively`, `academic` | Free text here would be both an id-space explosion and a prompt-injection surface. The enum maps to a fixed prompt fragment chosen server-side. |
| *(language)* | — | — | **Already carried by `parameters` today** for the existing types. No new key; the audio's language is the artifact's reading language, and it must equal the locale of the voices picked (§12.3). |

Deliberately **not** exposed: voice names (a leaked provider detail that would
pin us to Azure), bitrate/format (a single server-side choice, §8.3), speaking
rate, and anything free-text.

### 10.4 Consequence on `build_artifact_id`

`artifact_id` is a SHA-256 over (user, scope, `scope_id`, type, **`parameters`**,
sorted source ids), prefixed `art_`; time and `generator_version` are deliberately
excluded. Therefore:

1. **Every distinct `parameters` tuple is a distinct, separately-billed artifact.**
   `{target_minutes: 5, hosts: 2, tone: neutral}` and
   `{target_minutes: 15, hosts: 2, tone: neutral}` are two different `art_…` ids
   over the same folder. That is correct and desirable — they *are* two different
   episodes and each really costs money.
2. **Re-requesting an identical tuple is free and instantaneous**, because the id
   resolves to the existing immutable artifact. This is the append-only model
   working exactly as designed, and it is the reason a "regenerate" button must not
   exist for this type without changing a parameter.
3. **This is why every parameter must be a closed set.** With a free-integer
   `target_minutes` or a free-text `tone`, one screen can mint an unbounded number
   of distinct paid ids — each one a cache miss, each one an Azure bill. The
   closed sets cap the reachable id space per (user, scope, source set) at
   `2 durations × 2 host counts × |tone|`.
4. Adding a source to a folder changes the sorted source ids and therefore the id,
   so a folder that grows yields a new episode rather than mutating the old one.
   Again correct, and again billable — worth surfacing in the UI copy.

---

## 11. Licence and Terms of Service (AC #10)

### 11.1 Licences of the OSS candidates

| Project | Version read | Licence |
| --- | --- | --- |
| `podcast-creator` | 0.12.0 | **MIT** (`license = "MIT"` in `pyproject.toml`) |
| `open-notebook` | 1.14.0 | **MIT** (MIT classifier in `pyproject.toml`) |
| `podcastfy` | 0.4.3 | **Apache-2.0** (`license = "Apache-2.0"`) |
| Kokoro-82M (model weights) | model card | **Apache-2.0** |

All four are permissive and would pose **no licence obstacle** to adoption. The
rejection in §2.3 is on engineering grounds (dependency weight, glibc, ffmpeg),
not licensing — worth stating explicitly so the owner does not read a legal
objection where there is none.

### 11.2 Azure AI Speech: ownership and redistribution of the generated audio

- **Ownership.** Microsoft's Product Terms, under *Microsoft Generative AI
  Services → Output Content*: **"Output Content is Customer Data."** and
  **"Microsoft does not own Customer's Output Content."** So the MP3 is ours to
  store, serve to the requesting user, and (if the product ever wanted it)
  redistribute.
- **Input rights are our problem, not Microsoft's.** *"You're also responsible for
  obtaining any licenses, permissions, or other rights necessary for the content
  you input to the text to speech service to generate audio, image, and/or video
  output."* We feed it a script derived from third-party media. The mitigation is
  the same one that already applies to text summaries: the artifact is private to
  the requesting user and is never published.
- **Retention — the one action the worker must take.** For **prebuilt neural
  voices** in real time, *"Neither input text nor output audio content is stored in
  Microsoft logs."* For **batch** synthesis it is different: *"Scripts provided via
  the [batch] API for text to speech … are stored in Azure storage to process the
  batch synthesis request. The input text can be deleted via the delete API at any
  time."* And the batch API's own documentation is unambiguous: history is kept
  **168 hours (7 days) by default**, configurable via `timeToLiveInHours` up to
  **744 hours**, with the result ZIP sitting behind a SAS URL until then.
  **⇒ the worker must `DELETE` the synthesis job after downloading.** That is both a
  data-minimisation measure and free.
- **Disclosure.** *"Some jurisdictions may impose special legal requirements … and
  mandate disclosing the use of synthetic voices, images, and/or videos to users."*
  Microsoft publishes disclosure design guidelines and patterns. Practically: the
  episode must be labelled as AI-generated in the UI. That is a product
  requirement, cheap to satisfy, and the implementation task should carry it.
- **Not applicable to us, noted for completeness:** the entire biometric-data and
  voice-talent-acknowledgement regime applies to *custom* and *personal* voices. We
  use prebuilt voices only, so none of it binds us.

### 11.3 ElevenLabs, for the record

*"you retain all rights in and to your Output"* (Terms of Service §4(c)(ii)), but
the **free tier is non-commercial only**, so any use in this product requires a
paid plan. Not the recommendation, so not pursued further.

### 11.4 Voice cloning: out of scope

Per the task, cloning the user's voice is **explicitly out of scope**. This
matters for provider choice: it means we never touch Azure custom neural voice or
personal voice, and therefore never enter their limited-access application
process, their voice-talent acknowledgement requirements, their biometric-data
obligations, or their per-voice-per-day storage billing. The recommendation uses
**prebuilt voices exclusively**, which is the cheapest and least-regulated corner
of the product.

---

## 12. Failure modes and retry (AC #11)

### 12.1 The question, and why the architecture answers it

The task asks what becomes of segments already synthesised **and paid for** when a
generation fails. **With the recommended architecture there are no segments.**

Azure bills *"based on the total number of characters in each **successfully
processed** request"*. One episode is one request. It either succeeds — one MP3,
one charge, reported as `billingDetails.neuralCharacters` alongside
`succeededAudioCount` / `failedAudioCount` — or it fails and there is nothing to
reconcile. There is no partially-paid inventory, no bookkeeping of which turns
already exist, no "resume from turn 47".

**This is the strongest single argument against per-segment fan-out.** With 120
segments across N queue messages, a failure at segment 112 leaves 111 paid-for
objects, and a naive retry re-pays for all of them; avoiding that requires a
per-segment ledger, a per-segment idempotency key, and a garbage collector for
orphaned segments. Choosing a provider that renders one file deletes that entire
subsystem before it is written.

### 12.2 Consistency with the generation lease

`GENERATION_LEASE_SECONDS = 300`. The failure story and the lease interact in
exactly one place, already stated in §5.4 and repeated here because it is the
single most expensive mistake available:

1. **Re-arm the lease on every poll hop.** A polled job spans multiple
   invocations; the wall-clock of the whole job can exceed 300 s while each
   invocation is short. Without re-arming, the artifact looks abandoned, a second
   worker starts, and **Azure is paid twice**.
2. **Derive the Azure synthesis id from the `artifact_id`.** It is already
   deterministic and content-addressed. The id must satisfy Azure's constraint:
   3–64 characters, only digits, letters, hyphens, underscores and dots, starting
   and ending with a letter or digit.
3. **`GET` before `PUT`.** `PUT` on an existing synthesis id is not documented as
   idempotent. The API answers **HTTP 204** for "request was successful, but the
   resource doesn't exist" and **404** for an unknown id, so a probe is cheap and
   unambiguous. A duplicated SQS message then joins the existing job instead of
   creating a second one.
4. **If the artifact is already stored, the retry is a no-op.** Immutability plus a
   deterministic id means the terminal state is idempotent for free.

### 12.3 The failure that costs money without producing audio

> *"Charges apply even if speech is not generated due to a mismatch between the
> selected voice language and the input text."*

This is the one way to pay for silence. Mitigation is structural, not defensive:
**the voice pair must be selected from the same locale as the script**, from a
static table (§7.1), keyed by the artifact's language parameter — never inferred
from the generated text, never configurable per request. A single source of truth
for "which locale is this episode in", used for both the prompt and the
`<voice name>` attributes.

### 12.4 The rest of the failure matrix

| Failure | Response |
| --- | --- |
| `PUT` → **400** (bad `outputFormat`, missing `inputs`, F0 tier in a Standard-only region) | Permanent. Fail the artifact with the API's `error.message`. Never retried — a retry cannot fix a malformed request, and Azure would not charge anyway. |
| `PUT`/`GET` → **429** ("up to 100 requests per 10 seconds for each Speech resource") | Transient. Re-enqueue with a longer delay. At one poll per job this should never fire. |
| `PUT`/`GET` → **500** | Transient. Re-enqueue with backoff; the job may or may not exist, so the next hop's `GET`-before-`PUT` resolves it. |
| Job `status: "Failed"` | Terminal for this attempt. Read `failedAudioCount`, surface the error, `DELETE` the job. Whether Azure charged is knowable from `billingDetails.neuralCharacters` in the same response — **log it**, so the quota debit can be reconciled against what actually happened. |
| Job stuck in `Running` past a backstop deadline | Follow the existing Apify precedent: a delayed-SQS **backstop** message that fails the artifact and `DELETE`s the job rather than polling forever. |
| Result ZIP download fails | Transient, and **free to retry**: the job is still `Succeeded` and the SAS URL is valid until TTL. Re-enqueue. |
| S3 `PutObject` fails | Transient. Re-enqueue; the ZIP can be re-downloaded (previous row). |
| Quota debit vs. actual charge | Debit on **submit** (so a user cannot fan out unbounded submissions), and reconcile against `neuralCharacters` on completion — the same two-phase shape task-250 already uses for Deepgram (provisional minute, then settlement on real duration). |

### 12.5 One thing the user-facing flow should copy from open-notebook, and one it should not

**Copy:** surfacing the provider's error message on the failed episode, so a
failure is legible rather than a silent absence.

**Do not copy:** their Retry button *deletes the failed episode and submits a new
generation job*. Under our immutable, content-addressed model the id is a pure
function of the inputs, so "delete and resubmit" is not retry — it is the same id
again. Retry must resume the existing artifact's job, and only a **changed
parameter** produces a new episode (§10.4).

---

## 13. Dependency weight, measured

The task asks specifically what `langgraph` + `moviepy` + `pydub` weigh against
"the provider SDK alone". The honest answer is that the recommendation needs
**no SDK at all** — the batch synthesis API is three plain REST calls — so the
comparison is *N megabytes* versus **zero**. Here is the N.

### 13.1 Method

Both wheel closures were resolved from scratch for the worker's target
(`linux/aarch64`, CPython 3.12), with `--only-binary=:all:` so that only real
wheels are counted:

- **Baseline:** the repo's `[project.dependencies]` + the `worker` extra.
- **With adoption:** the same, plus `podcast-creator==0.12.0`.

Platform tags requested: `manylinux2014_aarch64`, `manylinux_2_28_aarch64`,
`manylinux_2_34_aarch64`. Two packages present in **both** closures ship no wheel
at all (`langdetect` and `sgmllib3k`, sdist-only) and were excluded from both sides
so the comparison stays symmetric.

### 13.2 Result

| | Wheels | Total size |
| --- | --- | --- |
| Worker today | **70** | **55.8 MB** |
| Worker + `podcast-creator` | **149** | **194.4 MB** |
| **Delta** | **+79** | **+138.6 MB, i.e. 3.48x** |

Five largest additions:

| Package | Size | What it is |
| --- | --- | --- |
| `nodejs-wheel-binaries` | **60.59 MB** | A **full Node.js runtime**, shipped as a Python wheel |
| `imageio-ffmpeg` | **25.63 MB** | **Ships an ffmpeg binary** — pulled in by `moviepy` |
| `pymupdf` | **25.10 MB** | A PDF engine |
| `numpy` | **15.67 MB** | Pulled in by `moviepy` |
| `pandas` | **10.49 MB** | — |

A 60 MB Node.js runtime and a bundled ffmpeg binary, to make a two-host audio file.

### 13.3 Two findings that make adoption impossible today, not merely heavy

**(a) Six wheels have no glibc-2.17 build.** The worker base image is
`public.ecr.aws/lambda/python:3.11-arm64`, i.e. **Amazon Linux 2, glibc 2.26** —
a constraint the repo already documents in `pyproject.toml`, where the
`pillow>=11.0.0,<12.3` ceiling is annotated *"12.3.0 is the first release to drop
the `manylinux_2_17_aarch64` wheel ... Lift the ceiling by moving the image to the
AL2023 base (python:3.12-arm64), not by loosening this line."* The same wall
blocks these six:

| Package | Lowest platform tag available |
| --- | --- |
| `caio` | `manylinux_2_34` |
| `nodejs-wheel-binaries` | `manylinux_2_28` |
| `numpy` | `manylinux_2_27`+ |
| `pandas` | `manylinux_2_24`+ |
| `pymupdf` | `manylinux_2_28` |
| `tiktoken` | `manylinux_2_28` |

**Adopting `podcast-creator` therefore requires migrating the worker image to the
AL2023 base first.** That is a real, separately-scoped piece of work — and this
benchmark would be recommending it in service of a library whose only unique
contribution is a moviepy call.

**(b) The `pillow` collision is real, and upstream itself has to work around it.**
Resolved empirically: our closure lands on **pillow 12.2.0**; the
`podcast-creator` closure lands on **pillow 11.3.0**, held back by `moviepy`'s
`pillow<12` cap. `open-notebook`'s own `pyproject.toml` carries
`override-dependencies = ["pillow>=12.2.0"]`, with the comment *"Pillow < 12.2.0
has open security advisories (PSD OOB write, FITS decompression bomb, PDF trailer
DoS). The only thing holding it back is moviepy's `pillow<12` cap, pulled in via
podcast-creator 0.12.0 ... Drop this override once podcast-creator ships a release
without moviepy (already removed on its main branch)."*

Upstream is documenting a security-advisory workaround caused by the exact
dependency we would be adopting — and telling us it is on its way out. Waiting for
that release would remove `moviepy`, and with it the only thing the package
uniquely does.

### 13.4 What the recommendation adds

**Zero packages.** The HTTP client already in the image, `zipfile` (stdlib),
`json` (stdlib), and string formatting for the SSML. The Azure Speech SDK is
deliberately not used — it exists for real-time streaming and would add a large
native dependency to replace three `curl`-shaped calls.

---

## 14. What this benchmark does not decide

Per the task, deliberately out of scope:

- **The mobile player UI.** Nothing here prescribes a screen, a waveform, a
  mini-player or a lock-screen integration. Section 8 only guarantees the
  *capability* the player needs: a seekable presigned URL plus a known duration.
- **Automatic generation at the end of ingestion.** **No.** This type is
  user-requested, like the other five. Auto-generating a EUR 0.09-0.42 artifact per
  ingested item is not defensible against any of the three tier allowances (9.4).
- **Voice cloning / the user's own voice.** Out of scope (11.4).
- **Tier re-pricing.** Section 9.4 *reports* that a 30-minute episode does not fit
  inside Reader's 60 minutes. Whether to change Reader, gate the duration, or drop
  30 minutes is the owner's call in the `Decision` field.

Two things this benchmark also does not settle, flagged so they are not mistaken
for settled:

- **The CJK billing factor.** Azure counts each Chinese character as two, and
  Japanese kanji likewise. Real and sourced (1.1), but no per-minute factor is
  computed because no vendor publishes characters-per-minute for CJK speech. The
  metering margin in 9.2 absorbs some of it; the implementation should log
  `neuralCharacters` per episode so the real factor becomes measurable from
  production data rather than guessed.
- **Prompt design for a two-host script.** The prompt is the implementer's, and it
  is the main quality lever. The token budget in 4.1 is the only constraint this
  benchmark places on it.

---

## 15. Credentials to provision (names only)

The recommendation needs **one** new third-party credential set. Per the repo's
public-repository rule, only the names are written here; the values go in the
secret store and the Lambda runtime environment.

| What | Kind | Where it lives |
| --- | --- | --- |
| Azure **Speech resource key** | secret | secret store + worker runtime env |
| Azure **Speech resource region** (`francecentral`) | non-secret config | worker runtime env |
| Azure **Speech resource name** (the `<resource>` in `https://<resource>.cognitiveservices.azure.com`) | non-secret config | worker runtime env |

Resource prerequisites the owner will need to satisfy in the Azure portal, in the
order the portal presents them:

1. **Create a resource -> AI + machine learning -> Speech** (equivalently
   *Azure AI services -> Speech service*).
2. **Region: France Central.** This is what keeps the EUR 12.88/1M meter and keeps
   the audio in the EU, matching the `eu-west-3` posture of the rest of the stack.
3. **Pricing tier: Standard S1.** *Not* Free F0 — the batch synthesis API returns
   **HTTP 400** for an F0 resource in a region that only supports Standard.
4. After creation, **Resource Management -> Keys and Endpoint** holds the key and
   the endpoint. Copy them into the secret store; do not commit them.

No other provider credential is required: the LLM already has one, and S3/SQS use
the worker's IAM role.

**Owner note (not an acceptance criterion, and not satisfiable by an
implementation agent):** the first end-to-end run can only happen after the key is
provisioned and the worker image is redeployed on a push to `main`.

---

## 16. Sources

All URLs consulted **2026-09-09**.

### The owner's lead (read in sources, not READMEs)

- `open-notebook` `pyproject.toml` — https://raw.githubusercontent.com/lfnovo/open-notebook/main/pyproject.toml
- `open-notebook` podcast command — https://raw.githubusercontent.com/lfnovo/open-notebook/main/commands/podcast_commands.py
- `open-notebook` podcast concepts doc (latency, retry, provider costs) — https://raw.githubusercontent.com/lfnovo/open-notebook/main/docs/2-CORE-CONCEPTS/podcasts-explained.md
- `podcast-creator` `pyproject.toml` — https://raw.githubusercontent.com/lfnovo/podcast-creator/main/pyproject.toml
- `podcast-creator` `core.py` (moviepy concatenation, in-band errors) — https://raw.githubusercontent.com/lfnovo/podcast-creator/main/src/podcast_creator/core.py
- `podcast-creator` `nodes.py` (per-turn TTS, `TTS_BATCH_SIZE`) — https://raw.githubusercontent.com/lfnovo/podcast-creator/main/src/podcast_creator/nodes.py
- `podcast-creator` `retry.py` (tenacity, 3 attempts) — https://raw.githubusercontent.com/lfnovo/podcast-creator/main/src/podcast_creator/retry.py
- `podcast-creator` on PyPI — https://pypi.org/project/podcast-creator/
- `podcastfy` `pyproject.toml` — https://raw.githubusercontent.com/souzatharsis/podcastfy/main/pyproject.toml
- Kokoro-82M model card (Apache-2.0, `lang_code` list, checkpoint size) — https://huggingface.co/hexgrad/Kokoro-82M

### Azure AI Speech (the recommendation)

- Batch synthesis API — REST verbs, `concatenateResult`, 2 MB payload, latency p50/p95, TTL 168-744 h, HTTP 200/201/204/400/404/429/500, `billingDetails.neuralCharacters`, Long Audio API retires 2027-04-01 — https://learn.microsoft.com/azure/ai-services/speech-service/batch-synthesis
- Batch synthesis properties — https://learn.microsoft.com/azure/ai-services/speech-service/batch-synthesis-properties
- Text to speech overview — billable characters, `<speak>`/`<voice>` not billable, mismatch-still-charged, CJK counted double, 24 kHz/48 kHz voices, batch is for >10 min — https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech
- Language and voice support, `?tabs=tts` — per-locale voice lists and genders, HD/MAI voices, `WordsPerMinute` — https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts
- Text to speech REST API — audio output formats incl. `audio-24khz-48kbitrate-mono-mp3`, real-time 10-minute limit — https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech
- SSML structure and the `<voice>` element — https://learn.microsoft.com/azure/ai-services/speech-service/speech-synthesis-markup-voice
- Data, privacy and security for text to speech — input-rights responsibility, real-time not logged, batch scripts stored in Azure storage, disclosure obligations — https://learn.microsoft.com/azure/ai-foundry/responsible-ai/speech-service/text-to-speech/data-privacy-security
- Microsoft Product Terms, *Microsoft Generative AI Services / Output Content* — "Output Content is Customer Data", "Microsoft does not own Customer's Output Content" — https://www.microsoft.com/licensing/terms/product/ForOnlineServices/all
- Speech service pricing page — https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/
- Azure Retail Prices API, used for the `francecentral` EUR meters (*S1 Neural Characters* EUR 12.88/1M, *Neural HD* EUR 18.8906/1M, legacy *S1 Neural Long Audio Characters* EUR 85.8664/1M) — https://prices.azure.com/api/retail/prices with filter `serviceName eq 'Speech Services' and armRegionName eq 'francecentral'`; API reference https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices

### Other TTS providers

- Amazon Polly pricing — Standard $4/1M, Neural $16/1M, Generative $30/1M, Long-Form $100/1M — https://aws.amazon.com/polly/pricing/
- Amazon Polly quotas — 3 000 billed chars and 10-minute truncation on `SynthesizeSpeech`; 100 000 billed chars on `StartSpeechSynthesisTask`; **`<voice>` not supported** — https://docs.aws.amazon.com/polly/latest/dg/limits.html
- Polly voices actually available in `eu-west-3` — `aws polly describe-voices --region eu-west-3`; catalogue at https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
- OpenAI pricing — `tts-1` $15/1M chars, `tts-1-hd` $30/1M chars, `gpt-4o-mini-tts` $12/1M audio output tokens — https://platform.openai.com/docs/pricing
- ElevenLabs pricing — https://elevenlabs.io/pricing
- ElevenLabs models — v3 ~280 ms, Flash v2.5 ~75 ms "excluding application & network latency", 32 languages — https://elevenlabs.io/docs/models
- ElevenLabs Text-to-Dialogue — multi-speaker, <=2 000 characters advised, max 10 unique voice IDs — https://elevenlabs.io/docs/capabilities/text-to-dialogue
- ElevenLabs Terms of Service — output rights, free tier non-commercial — https://elevenlabs.io/terms-of-use
- Deepgram pricing — Aura-1 $0.0150/1k, Aura-2 $0.030/1k — https://deepgram.com/pricing
- Deepgram TTS models and languages — 7 languages — https://developers.deepgram.com/docs/tts-models
- Deepgram Speak API — 2 000-character limit — https://developers.deepgram.com/reference/text-to-speech-api/speak
- Gemini speech generation — 2 speakers max, 32 000-token session window, headerless 24 kHz PCM, 24 languages, 25 audio tokens/second — https://ai.google.dev/gemini-api/docs/speech-generation
- Gemini API pricing — 2.5 Flash TTS $10/1M, 2.5 Pro TTS and 3.1 Flash TTS $20/1M audio output tokens — https://ai.google.dev/gemini-api/docs/pricing

### Turnkey podcast APIs

- AutoContent API — credit packs, 10 credits/episode, `duration` presets `short`/`default`/`long`, "typically takes 2-5 minutes", "if the request is not successful you are not charged" — https://autocontentapi.com/ and https://autocontentapi.com/docs
- Wondercraft pricing — Creator $25/1 000 credits, 100 min/month — https://www.wondercraft.ai/pricing
- Jellypod pricing — Creator $50/11 000 credits, 1 credit/second, 183 min/month, 30-min episode max — https://www.jellypod.com/pricing
- NotebookLM "Audio Overview" API surface — Discovery Engine **v1alpha** discovery document, revision 20260831 — https://discoveryengine.googleapis.com/$discovery/rest?version=v1alpha (compared against `?version=v1beta` and `?version=v1`, where `audioOverview` appears 0 times)

### AWS platform limits and prices

- AWS Lambda quotas — 900 s timeout, 128-10 240 MB memory, 512 MB-10 240 MB `/tmp`, 10 GB container image — https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- Amazon S3 pricing — https://aws.amazon.com/s3/pricing/ ; `eu-west-3` figures read from the AWS Price List Query API (`aws pricing get-products --region us-east-1 --service-code AmazonS3`, filtered on `location='EU (Paris)'`) — https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html
- S3 `GetObject` `Range` / `206 Partial Content` behaviour — https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html (also verified empirically against a `-dev` bucket, 8.4)

### Candidates set aside (section 3, "Also considered")

- Cartesia TTS API reference — single `voice` per call, 44-code `language` enum, `X-API-Key` — https://docs.cartesia.ai/api-reference/tts/tts
- Cartesia pricing — credit tiers, "Commercial use license" from Pro — https://cartesia.ai/pricing
- PlayHT / PlayAI — `play.ht`, `www.play.ht`, `play.ai`, `www.play.ai` fail DNS resolution and `docs.play.ai` presents an expired TLS certificate; verified with `curl -w '%{http_code} ssl=%{ssl_verify_result}'` on 2026-09-09. Nominal entry point: https://docs.play.ai/
- Hume pricing — Octave per-1 000-character overage $0.15 to $0.05 by tier — https://www.hume.ai/pricing
- Coqui XTTS-v2 model card — "This model is licensed under Coqui Public Model License", 17 languages — https://huggingface.co/coqui/XTTS-v2 ; the licence text it links to, https://coqui.ai/cpml, returns HTTP 404
- Resemble AI Chatterbox model card — MIT, Multilingual V3 0.5B, 23 languages, single reference voice per `generate()` — https://huggingface.co/ResembleAI/chatterbox
- Podcastle — https://podcastle.ai/pricing 308-redirects to https://async.com/pricing ; no developer API and no rendered prices
- Google Illuminate — https://illuminate.google.com/ ; sign-in-gated "Experiment", no documented API

### This repository

- `docs/research/task-287-consumption-model/README.md` (`owner_decision: ok`, 2026-08-18) — the minute unit, `1 min = 0.00664 EUR`, `round(real_cost / 0.00664)`, the three tiers, and the "AI generation over one item = free" / "1 per 5 sources" rows.
- `media_summarizer/core/services/artifact_service.py` — `OPENAI_MODEL`, `MAX_FOLDER_SOURCES`, `MAX_FOLDER_CORPUS_TOKENS`, `BYTES_PER_TOKEN`, `GENERATION_LEASE_SECONDS`, `build_artifact_id`, `build_artifact_storage_key`, `get_artifact_bucket`, `get_artifact_queue`.
- `media_summarizer/core/services/quota_enforcer.py` — `minutes_for_folder_sources`, `cost_eur_per_minute()`.
- `media_summarizer/core/services/llm_pricing.py` — `USD_EUR = 0.86`, `gpt-5.4-nano` rates.
- `media_summarizer/core/services/audio_duration_probe.py` — "Audio duration probing without an ffmpeg dependency (task-250 Layer 1)".
- `media_summarizer/core/models/media_artifact.py` — `MediaArtifactType`.
- `media_summarizer/api/endpoints/artifacts.py` — `get_artifact_content`, `ArtifactContentResponse.content: Dict[str, Any]`.
- `media_summarizer/utils/s3.py` — `generate_presigned_url`; precedent in `media_summarizer/api/endpoints/media.py`.
- `media_summarizer/core/services/apify_orchestration.py` plus the `apify_backstop` delayed-SQS path — the submit-then-poll precedent 5.2 copies.
- `mobile/src/i18n/locales.ts` — the 11 locales, `FALLBACK_LOCALE`, `RTL_LOCALES`.
- `pyproject.toml` — the `worker` extra and the documented glibc-2.26 / `pillow<12.3` constraint.
