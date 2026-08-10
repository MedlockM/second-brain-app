---
id: task-232
title: >-
  Implémenter le mode viewer de transcript lisible per validated benchmark
  (task-231)
status: To Do
assignee: []
created_date: '2026-08-06 00:39'
labels:
  - mobile
  - ingestion
dependencies:
  - task-231
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implémenter l'amélioration du rendu du transcript dans le viewer de détail média mobile, selon l'architecture validée par le benchmark task-231.

Lire impérativement `docs/research/task-231-.../README.md` pour connaître la décision finale de l'owner (format de stockage retenu, présence ou non de paragraphes/speakers/timestamps, stratégie de migration des transcripts existants) avant de commencer l'implémentation. Ne pas se baser sur une recommandation initiale qui pourrait avoir été amendée par l'owner — seule la section "Decision" du README fait foi.

Périmètre attendu (à affiner selon la décision du README) :
- Adapter le pipeline d'extraction/stockage du transcript si le README l'exige (media_summarizer/workers/transcription/deepgram_worker.py, media_summarizer/core/services/raw_content_service.py).
- Adapter l'affichage dans mobile/app/media/[id].tsx (TranscriptContent) pour restituer une lecture structurée (paragraphes, espacement, éventuellement speakers/timestamps selon la décision).
- Vérifier la compatibilité avec le pipeline de traduction existant (RawContentResponse.translation).
- Vérifier que les transcripts déjà ingérés restent lisibles (stratégie de migration ou fallback si le README en définit une).
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Interpretation of the owner's decision

`docs/research/task-231-transcript-formatting/README.md` carries
`owner_decision: ok` with `**Decision**: option B`. "Option B" is the row labelled
`B` in the option table of §5.1 and detailed in §10:

> **Structured plain text via a shared normalizer** — the canonical S3 object stays
> plain UTF-8 text with blank-line paragraph breaks, produced by one shared
> normalizer applied by the backend **at write time and idempotently at read
> time**. No client-side heuristic, no migration.

This is unambiguous, and it happens to coincide with the benchmark's own
`Recommendation` block, so there was no divergence to arbitrate. Everything below
implements that option and only that option. Explicitly *not* implemented, per the
README's rejected options: JSON storage (C/D), client-side re-paragraphing (A), a
JSON sidecar (E, deferred), an LLM re-paragraphing pass (F), an S3 backfill (§6.10),
timestamps (§7.2), a reading/raw-mode toggle (§6.9), and markdown rendering (§11.6).

### New shared module

`media_summarizer/core/services/transcript_formatting.py` is the single source of
truth for "what a readable transcript looks like". Public surface:

- `normalize_transcript_text(text, *, source=None)` — any transcript shape in,
  blank-line-delimited plain text out.
- `group_caption_lines(lines, *, source=None)` — subtitle/caption cues in (a cue is
  a display unit, never a semantic boundary), paragraphs out.
- `count_paragraphs(text)` — paragraph count of a normalized transcript.
- `deepgram_transcript_text(alt, utterances=None)` — picks the richest available
  Deepgram representation (speaker-grouped utterances → `paragraphs.paragraphs[]`
  with speaker → `paragraphs.transcript` → flat `transcript`).

Three guarantees, verified empirically on synthetic one-hour transcripts of each
pathological shape (flat punctuated blob, unpunctuated caption cues, single
unpunctuated line, Deepgram `paragraphs.transcript`, trafilatura article,
short social post, diarized utterances):

1. **Idempotence** — `normalize(normalize(x)) == normalize(x)`. This is what makes
   read-time normalization safe and the S3 backfill unnecessary (migration M0).
   The invariant is enforced by the `PARAGRAPH_MAX_CHARS` gate in `_split_block`.
2. **Content preservation** — only whitespace is ever added or removed;
   `normalize(x).split() == x.split()`.
3. **Bounded blocks** — no paragraph exceeds `PARAGRAPH_MAX_CHARS` (900).

The README §9.4 acceptance assertion (at least `floor(len/2000)` blank-line
separators, no paragraph over 1200 chars) passes on all three input shapes.

The missing behaviour that produced the original defect — a single 53,999-character
paragraph for YouTube/TikTok auto-captions — is the unpunctuated fallback: when a
block has no sentence boundary at all, `_group_words` groups on a ~110-word budget
instead of giving up.

### Write path (all 8 producers)

Every producer now normalizes before uploading to S3, so the stored bytes are
already readable and translation, artifact prompts and Algolia chunking all benefit,
not just the viewer:

- `workers/transcription/deepgram_worker.py` — `extract_transcript` delegates to
  `deepgram_transcript_text`, so `paragraphs.transcript` (free, already blank-line
  delimited) is preferred over the flat string. Raises
  `NonRetryableDeepgramError` on an empty transcript.
- `utils/ytdlp_helpers.py` (YouTube + TikTok native captions),
  `workers/youtube_ingestion_worker.py` (Apify flat field and segment array),
  `workers/tiktok_ingestion_worker.py` (native + Apify),
  `workers/x_ingestion_worker.py`, `workers/article_extraction_worker.py`,
  `utils/rss_transcript.py`, `workers/podcastindex_resolution_worker.py`,
  `core/media_ingestion/adapters/orchestrators.py`.

Document parsing is deliberately untouched: it writes `{job_id}.md` as
`text/markdown` and is a separate, already-structured corpus (README §13.3).

### Read path

`core/services/raw_content_service.py` lost ~240 lines of unreachable formatting
code written for a storage format that never existed (README §12): the whole
`deepgram_json` / `whisper_json` / generic-JSON family, plus the per-source
formatters, plus the local sentence splitter. What remains is:

- `_detect_source_format(media_type, source_platform, transcript_s3_key)` — a
  simple media-type classification (`plain_text`, `article_text`, `social_post`,
  `ocr`, `markdown`), with the `.md` extension detected so parsed documents pass
  through untouched.
- `_format_content(raw_text, source_format)` — markdown short-circuits, everything
  else goes through the shared normalizer.

Legacy transcripts written before this change are therefore structured on the fly
at read time, with no S3 rewrite: stored bytes never change, so artifact sha256
fingerprints and the translation cache stay valid.

### Translation compatibility

`get_raw_content` still resolves the translation **before** formatting, and that
ordering must not be inverted (README §8.2, §8.4): the translated object is
normalized on read exactly like the original, which makes the path self-healing if
the LLM ever drops a paragraph break. `build_translated_transcript_key` is
unchanged, so no cache is invalidated. The `RawContentResponse.translation` contract
is untouched.

### Mobile viewer

`mobile/app/media/[id].tsx` gains a `TranscriptBody` component used by all three
content branches of `TranscriptContent` (`ready`, `translation_pending`,
`translation_failed`), replacing the single flat `<Text>` node:

- `splitTranscriptParagraphs` splits on blank lines (tolerating trailing
  whitespace) and pops an optional `Speaker N:` prefix. No re-chunking heuristic
  client-side — the backend already guarantees the structure.
- The split is memoized on the content string, because the component re-renders
  every 3 000 ms while translation polling runs.
- One `<Text selectable>` per paragraph inside a `<View>` wrapper (children of a
  `Text` use text layout, not Flexbox, so they would flow inline).
- The speaker label is a *nested* `Text` so it reflows with the body copy.
- `transcriptParagraph` uses `Typography.body.lineHeight` (25.6), fixing the
  off-system hardcoded `lineHeight: 24` flagged in README §13.2, and
  `marginBottom: Spacing.md` for the paragraph separation. `transcriptSpeaker` is
  `Colors.textMuted` + `fontWeight: "600"`. All tokens come from
  `mobile/src/constants/theme.ts`; no literal colour, size or spacing was added.
- `allowFontScaling` left at its default so Dynamic Type keeps working.
- The `ScrollView` is kept (README §11.4): ~120 `Text` nodes for a one-hour
  transcript is a lighter native text-measurement job than the single
  46 000-character node it replaces, and virtualizing would mean restructuring the
  whole detail screen.
- No new npm dependency.

### Diarization (owner question 1 of README §14)

Kept **off** by default, as recommended: it is a paid add-on (+41.7 % per
transcribed minute) and is not needed for readable paragraphs. Two env vars were
added to `.env.example`: `DEEPGRAM_DIARIZE=false` and `DEEPGRAM_DIARIZE_MODEL=v2`.
Flipping `DEEPGRAM_DIARIZE` to `true` is the only change needed — the worker then
sends `diarize_model` (never the deprecated `diarize=true`), the normalizer emits
in-band `Speaker N:` prefixes, and the mobile viewer already renders them as
labels. Speaker labels are emitted as plain text, **not** markdown, because nothing
in the mobile app renders markdown and asterisks would show up literally.

### `segments_count` made comparable (README §13.1)

The badge previously mixed units: Deepgram utterances for podcasts, raw caption
line counts for YouTube, word counts for articles and X posts — for the same
one-hour video the YouTube number could be an order of magnitude larger. Every
producer now reports a paragraph count, and the mobile badge reads "N paragraphs"
instead of "N segments". `extraction_metadata.word_count` is kept on articles (it
is legitimately a word count) and a new `paragraph_count` feeds the transcription
metadata. The `TranscriptInfo.segments_count` field name is unchanged, so no API
contract breaks; its description now documents the unit.

Note for the owner: already-ingested media keep the old `segments_count` value in
DynamoDB, so their badge stays on the old unit until they are re-ingested. This is
cosmetic only — the transcript body itself is corrected at read time for all
existing media.

### Deviation from the task instructions: no automated tests

The dispatch instructions asked to "add or update tests (backend pytest and/or
mobile tests as applicable)". This was **not done**, because it contradicts both
`AGENTS.md` ("No automated tests unless explicitly requested") and the standing
implementation-agent rule that forbids adding automated tests. Behaviour was
instead verified with throwaway scripts (idempotence, word-for-word content
preservation, block-size ceiling, the README §9.4 acceptance assertion, markdown
pass-through, diarization-off-by-default query params, per-producer paragraph
counts), which were deleted before commit. If the owner wants this locked down by
a regression suite, `transcript_formatting.py` is pure and dependency-free, so it
is the cheapest possible unit-test target — worth a follow-up task.

### Gates

- `uv run ruff check media_summarizer/` → all checks passed.
- `uv run mypy media_summarizer/` → success, no issues in 155 source files.
- `cd mobile && npm run typecheck` → clean.
- `cd mobile && npm run lint` → 0 errors. The single warning in
  `app/media/[id].tsx` is pre-existing (verified by linting the file at HEAD).

### Owner verification suggested

1. Open an already-ingested podcast, YouTube video and article in the mobile
   viewer and confirm the transcript now reads as paragraphs (this exercises the
   read-time normalization path with zero re-ingestion).
2. Re-ingest one item per source and confirm the stored S3 object is itself
   paragraphed (write path).
3. Open a media whose transcript is being translated and confirm both the pending
   and the completed translation render as paragraphs.
4. Decide whether to enable `DEEPGRAM_DIARIZE` for the multi-speaker use case
   (README §14, question 1).
<!-- SECTION:NOTES:END -->
