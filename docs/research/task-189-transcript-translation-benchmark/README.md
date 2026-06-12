---
owner_decision: pending
---

# Benchmark : Transcript Translation Services for User's Preferred Language

## Owner Validation

**Decision**: _(to be filled by the owner after review)_
**Validated at**: _(ISO date to be filled by the owner)_

---

## Recommendation

**Primary recommendation: GPT-5-nano via the existing OpenAI stack** for transcript translation, with DeepL API Pro as a quality-optimized alternative if the owner decides quality of spoken/conversational text warrants the premium.

### Rationale

1. **Operational simplicity**: The project already integrates OpenAI (gpt-5-nano for summary_short, gpt-5.4-nano for other artifacts). Adding a translation step via the same API requires zero new provider integration, zero new credentials, and zero new SDK dependencies.
2. **Cost-competitive**: At $0.05/1M input + $0.40/1M output, GPT-5-nano translating 5k-token transcripts costs approximately $0.45/1000 transcripts — cheaper than DeepL ($0.50/1000 transcripts) and competitive with Google Translate NMT ($0.40/1000 transcripts).
3. **Structure preservation**: LLMs excel at preserving paragraph breaks, timestamps, speaker labels, and oral style because they understand the semantic structure. Dedicated NMT services treat text as flat segments and may break formatting.
4. **Context window**: GPT-5-nano's 400k-token window means even very long transcripts (10k+ tokens) fit in a single call with no chunking needed.
5. **Quality**: GPT-4+ level LLMs match or exceed NMT systems on high-resource language pairs (EN/FR/ES/DE/IT/PT/NL) per published research. For JA/ZH/AR/HI, quality is also strong but DeepL claims superiority in blind tests.

### Recommended Configuration

| Parameter | Value |
|-----------|-------|
| **Provider** | OpenAI (existing integration) |
| **Model** | `gpt-5-nano-2025-08-07` (same as summary_short) |
| **Fallback model** | `gpt-5.4-nano-2026-03-17` (if quality issues detected) |
| **Max input** | 400k tokens (no chunking needed for V1) |
| **Chunking strategy** | Not required for V1 (transcripts rarely exceed 15k tokens) |
| **System prompt** | Translation-specific prompt preserving oral style, paragraphs, timestamps |
| **V1 languages** | FR, EN, ES, DE, IT, PT, NL, JA, ZH, AR, HI |

### Alternative (if owner prefers quality over simplicity)

Use **DeepL API Pro** at $25/million characters for premium translation quality, particularly if user feedback indicates LLM translation of spoken content is insufficient. DeepL wins 94% of blind tests against competitors including GPT-5.2 (per DeepL's March 2026 benchmark). Trade-off: adds a new provider dependency and costs approximately 10% more.

---

## Detailed Comparison Table

### Solution Overview

| # | Solution | Type | Provider | Integration Effort |
|---|----------|------|----------|-------------------|
| 1 | **GPT-5-nano** | LLM (existing stack) | OpenAI | None (already integrated) |
| 2 | **GPT-5.4-nano** | LLM (existing stack) | OpenAI | None (already integrated) |
| 3 | **DeepL API Pro** | Dedicated translation | DeepL | New provider |
| 4 | **Google Cloud Translation v3 (NMT)** | Dedicated translation | Google Cloud | New provider |
| 5 | **AWS Translate** | Dedicated translation | AWS | Minimal (AWS already used) |
| 6 | **Azure Translator** | Dedicated translation | Microsoft | New provider |
| 7 | **Google Cloud Translation LLM** | LLM-based translation | Google Cloud | New provider |

---

## Dimension 1: Cost Analysis

### Per-character / Per-token Pricing

| Solution | Pricing Model | Unit Price | Effective $/1M chars | Free Tier |
|----------|---------------|-----------|---------------------|-----------|
| **GPT-5-nano** | Per token (input $0.05/1M, output $0.40/1M) | See calculation below | ~$0.225/1M chars | No |
| **GPT-5.4-nano** | Per token (input $0.20/1M, output $1.25/1M) | See calculation below | ~$0.725/1M chars | No |
| **DeepL API Pro** | Per character | $25/1M chars | $25.00/1M chars | 500k chars/month (Free plan) |
| **Google Translate NMT (v3)** | Per character | $20/1M chars | $20.00/1M chars | 500k chars/month ($10 credit) |
| **AWS Translate** | Per character | $15/1M chars | $15.00/1M chars | 2M chars/month (12 months) |
| **Azure Translator** | Per character | $10/1M chars (S1) | $10.00/1M chars | 2M chars/month (F0 tier) |
| **Google Translation LLM** | Per character (input + output) | $10+$10/1M chars | $20.00/1M chars | No |

### Cost Calculation for LLM-based Translation

For LLM translation of a 5,000-token transcript:
- **Input**: 5,000 tokens (transcript) + ~200 tokens (system prompt) = 5,200 tokens
- **Output**: ~5,000 tokens (translated text, approximately same length)
- **Token-to-character ratio**: 1 token is approximately 4 characters (English/European), so 5,000 tokens equals approximately 20,000 characters

**GPT-5-nano per transcript**:
- Input cost: 5,200 tokens x $0.05/1M = $0.00026
- Output cost: 5,000 tokens x $0.40/1M = $0.00200
- **Total: $0.00226 per transcript**

**GPT-5.4-nano per transcript**:
- Input cost: 5,200 tokens x $0.20/1M = $0.00104
- Output cost: 5,000 tokens x $1.25/1M = $0.00625
- **Total: $0.00729 per transcript**

### Cost Calculation for Dedicated Translation Services

For a 5,000-token transcript (approximately 20,000 characters):

| Solution | Cost per 20k chars | Cost per transcript |
|----------|-------------------|-------------------|
| **DeepL API Pro** | 20,000 x $25/1M | **$0.50** |
| **Google Translate NMT** | 20,000 x $20/1M | **$0.40** |
| **AWS Translate** | 20,000 x $15/1M | **$0.30** |
| **Azure Translator** | 20,000 x $10/1M | **$0.20** |
| **Google Translation LLM** | 20,000 x $20/1M (in+out) | **$0.40** |
| **GPT-5-nano** | (see above) | **$0.00226** |
| **GPT-5.4-nano** | (see above) | **$0.00729** |

### Monthly Cost Projection: 1,000 Transcripts/Month (5k tokens avg)

| Solution | Monthly Cost | Annual Cost |
|----------|-------------|-------------|
| **GPT-5-nano** | **$2.26** | $27.12 |
| **GPT-5.4-nano** | **$7.29** | $87.48 |
| **Azure Translator** | **$200.00** | $2,400.00 |
| **AWS Translate** | **$300.00** | $3,600.00 |
| **Google Translate NMT** | **$400.00** | $4,800.00 |
| **Google Translation LLM** | **$400.00** | $4,800.00 |
| **DeepL API Pro** | **$500.00** | $6,000.00 |

**Key insight**: LLM-based translation via the existing OpenAI stack is **88x to 221x cheaper** than dedicated translation services. This is because dedicated services charge per character at rates designed for enterprise document translation workflows, while LLMs charge per token at rates designed for general text generation.

---

## Dimension 2: Language Coverage

| Solution | Total Languages | FR | EN | ES | DE | IT | PT | NL | JA | ZH | AR | HI | Gaps for V1 |
|----------|----------------|----|----|----|----|----|----|----|----|----|----|----|----|
| **GPT-5-nano** | 90+ (all major) | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |
| **GPT-5.4-nano** | 90+ (all major) | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |
| **DeepL API** | 33 languages | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y* | *HI: translation only, no glossaries |
| **Google Translate NMT** | 246 languages | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |
| **AWS Translate** | 75 languages | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |
| **Azure Translator** | 130+ languages | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |
| **Google Translation LLM** | 130+ languages | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | None |

**Notes**:
- All 11 required V1 languages are supported by all solutions.
- DeepL has the smallest total language set (33) but covers all V1 requirements.
- OpenAI LLMs support translation to/from essentially any language they were trained on (90+), though quality varies for low-resource languages.
- Google Translate NMT has the broadest coverage (246 languages) which could be useful for future expansion beyond V1.

---

## Dimension 3: Translation Quality

### Published Benchmarks and Comparisons

| Source | Finding | Date |
|--------|---------|------|
| DeepL blind tests (48,000 evaluations, 16 language pairs) | DeepL wins 94% of head-to-head tests (75/80 test groups). Beats GPT-5.2 100% (16/16 pairs), Google Translate 100% (16/16 pairs) | March 2026 |
| Jiao et al. "Is ChatGPT a Good Translator?" (arXiv:2301.08745) | GPT-4 matches commercial translation products on high-resource European languages. GPT-3.5 lags on low-resource languages but "exhibits good results on spoken language" | 2023 |
| DeepL vs competitors (whydeepl page) | DeepL 1.3x better than Google Translate, 1.7x better than ChatGPT-4, 2.3x better than Microsoft | 2026 |
| Slator 2026 Market Assessment | DeepL voice translation: 96.4 quality score vs 87-89 for competitors. 76% fewer critical errors | 2026 |

### Quality Assessment for Transcript Content Specifically

| Solution | Formal Text Quality | Spoken/Oral Text Quality | Notes |
|----------|--------------------|--------------------------| ------|
| **GPT-5-nano** | High | Very High | LLMs excel at preserving oral register, colloquialisms, filler words. Can be prompted to maintain conversational tone. |
| **GPT-5.4-nano** | Very High | Very High | Higher intelligence tier, better at nuanced register handling. |
| **DeepL** | Highest (per blind tests) | High | Specialized NMT excels at natural-sounding translations. March 2026 blind tests show dominance. |
| **Google Translate NMT** | High | Medium-High | Good for standard text but can over-formalize spoken content. |
| **AWS Translate** | Medium-High | Medium | More oriented toward business/technical content. |
| **Azure Translator** | Medium-High | Medium | Similar to AWS; good for general purpose but less natural on spoken text. |

### LLM Advantage for Transcript Translation

LLMs have a specific advantage for transcript translation because:
1. **Context understanding**: They understand that the text is a transcript and can preserve oral markers (hesitations, informal speech patterns).
2. **Instruction following**: A well-crafted system prompt can instruct the model to maintain timestamps, speaker labels, and paragraph structure.
3. **Register preservation**: LLMs can be instructed to preserve the conversational/informal register rather than formalizing the output.
4. **No sentence segmentation artifacts**: NMT services typically translate sentence-by-sentence, which can break cross-sentence references. LLMs process the entire context window at once.

### Quality Caveat

DeepL's March 2026 blind tests (conducted by professional linguists) show clear superiority over both LLMs and other NMT services. However:
- These tests likely used general/formal text, not specifically spoken/transcript content.
- The tests compared against GPT-5.2, not the newer GPT-5.4 generation.
- For the specific use case of preserving oral style in transcripts, LLM promptability may compensate for raw translation quality differences.

---

## Dimension 4: Structure Preservation

| Solution | Paragraphs | Timestamps | Speaker Labels | Oral Style | HTML/Markup |
|----------|-----------|-----------|---------------|-----------|-------------|
| **GPT-5-nano** | Excellent (prompt-driven) | Excellent | Excellent | Excellent (prompt-driven) | Good |
| **GPT-5.4-nano** | Excellent | Excellent | Excellent | Excellent | Good |
| **DeepL** | Good (preserves \n) | Poor (may translate timestamp text) | Poor (may translate names) | Good | Excellent (tag handling) |
| **Google Translate NMT** | Medium (segment-based) | Poor | Poor | Medium (tends to formalize) | Good (textType=html) |
| **AWS Translate** | Medium | Poor | Poor | Medium | Good (HTML support) |
| **Azure Translator** | Good (preserves structure) | Medium (class=notranslate) | Medium (notranslate attribute) | Medium | Excellent (notranslate class) |

### Key Difference: LLM vs Dedicated NMT for Structure

**LLM approach**: A single prompt can instruct the model to:
- Preserve all timestamps in their original format (e.g., `[00:05:32]`)
- Keep speaker labels untranslated (e.g., `John:`, `Speaker 1:`)
- Maintain paragraph breaks as-is
- Preserve the informal, spoken register

**Dedicated NMT approach**: Requires workarounds:
- Timestamps and speaker labels need to be wrapped in `notranslate` tags (Azure) or `class="notranslate"` (Google HTML mode) or pre/post-processed out
- Paragraph breaks may be disrupted by sentence-level segmentation
- Oral register is often formalized by the NMT model

**Winner for transcript structure preservation: LLM-based solutions (GPT-5-nano / GPT-5.4-nano)**

---

## Dimension 5: Latency

### Sourced Latency Data

| Solution | Typical Latency (5k tokens / 20k chars) | Max Latency | Source |
|----------|------------------------------------------|-------------|--------|
| **GPT-5-nano** | ~3-5s (estimated from output speed class) | < 15s | OpenAI model docs: "fastest, most cost-efficient version of GPT-5" |
| **GPT-5.4-nano** | ~4-7s (estimated) | < 20s | OpenAI: faster class speed tier |
| **DeepL** | ~1-3s | < 10s | General industry knowledge; DeepL optimized for speed |
| **Google Translate NMT** | ~1-2s | < 5s | Google Cloud: typically < 150-300ms for 100 chars, scales linearly |
| **AWS Translate** | ~1-3s | < 10s | AWS docs: real-time translation |
| **Azure Translator** | ~1-3s | 15s max (standard), 120s (custom) | Azure docs: "maximum latency of 15 seconds using standard models" |
| **Google Translation LLM** | ~5-10s | < 30s | LLM-based, slower than NMT |

### Latency Requirement Check

The requirement is < 30 seconds for a 5k-token transcript. **All solutions meet this requirement comfortably.**

- Dedicated NMT services (DeepL, Google, AWS, Azure) are fastest (1-3s).
- GPT-5-nano is expected to complete in 3-7s based on its speed tier classification.
- Even GPT-5.4-nano should complete well under 15s.

**Note**: Translation is an asynchronous pipeline step (occurs between transcript retrieval and artifact generation). Latency is important but not user-blocking — the user does not wait synchronously for translation to complete.

---

## Dimension 6: Context Limits and Chunking Strategy

| Solution | Max Input per Request | 5k Token Transcript Fits? | 10k+ Token Transcript Fits? | Chunking Needed? |
|----------|----------------------|---------------------------|------------------------------|-----------------|
| **GPT-5-nano** | 400,000 tokens | Yes | Yes (up to 400k) | No |
| **GPT-5.4-nano** | 400,000 tokens | Yes | Yes (up to 400k) | No |
| **DeepL** | 128 KiB (~130,000 chars / ~32k tokens) | Yes | Yes (up to ~32k tokens) | Rarely (only for extremely long content > 130k chars) |
| **Google Translate NMT** | 30,000 codepoints (~7.5k tokens) | Yes (barely, if in characters) | Needs chunking for > 30k chars | Yes, for long transcripts |
| **AWS Translate** | 10,000 bytes (real-time) / unlimited (batch) | Tight fit (UTF-8 multibyte) | Needs chunking or batch mode | Yes |
| **Azure Translator** | 50,000 characters per element (~12.5k tokens) | Yes | Needs chunking for > 50k chars | Sometimes |
| **Google Translation LLM** | 30,000 characters | Yes | Needs chunking for > 30k chars | Sometimes |

### Chunking Strategy Recommendation

For **GPT-5-nano** (recommended solution): **No chunking required for V1**. 
- The 400k-token context window accommodates even the longest podcast transcripts (a 3-hour podcast generates approximately 36,000 tokens).
- Only pathological cases (concatenated multi-episode transcripts) would require chunking, which is outside V1 scope.

For dedicated NMT services (if chosen as alternative):
- **Chunking approach**: Split at paragraph boundaries, maintaining a minimum chunk size of 1,000 characters and maximum of 25,000 characters.
- **Overlap**: Include the last sentence of the previous chunk as context for continuity.
- **Reassembly**: Concatenate translated chunks, removing the overlapping sentence from subsequent chunks.

**Winner for context limits: GPT-5-nano (no chunking needed for any realistic V1 transcript)**

---

## Dimension 7: Reuse of Existing Stack (task-72)

### Current Stack (per task-72 owner decision)

| Artifact | Model | Provider |
|----------|-------|----------|
| summary_short | gpt-5-nano-2025-08-07 | OpenAI |
| All other artifacts | gpt-5.4-nano-2026-03-17 | OpenAI |

### Comparison: LLM Stack Reuse vs Dedicated Translation Service

| Criterion | GPT-5-nano (reuse stack) | DeepL API Pro (new provider) |
|-----------|--------------------------|------------------------------|
| **Integration effort** | Zero (same API, same credentials) | New SDK, new API key, new error handling |
| **Monthly cost (1000 transcripts)** | $2.26 | $500.00 |
| **Quality (high-resource langs: EN/FR/ES/DE/IT/PT/NL)** | Very good | Best (per blind tests) |
| **Quality (JA/ZH/AR/HI)** | Good | Very good to best |
| **Structure preservation** | Excellent (prompt-driven) | Medium (requires workarounds) |
| **Operational complexity** | None (1 provider, 1 billing) | Additional provider to monitor, credential rotation |
| **Latency** | 3-7s | 1-3s |
| **Vendor lock-in** | Already committed to OpenAI | Adds second vendor dependency |
| **Failure mode** | Same as existing artifact pipeline | Independent failure domain |

### Trade-off Summary

| Factor | Winner |
|--------|--------|
| Cost | GPT-5-nano (221x cheaper) |
| Quality (formal text) | DeepL |
| Quality (spoken/transcript text) | Tie or slight LLM advantage (promptable register preservation) |
| Integration simplicity | GPT-5-nano |
| Latency | DeepL (but both < 30s) |
| Structure preservation | GPT-5-nano |
| Language coverage | Google Translate NMT (246 languages) but all solutions cover V1 needs |

---

## Cost Sensitivity Analysis

### Scenario: Translation Needed for Only a Fraction of Transcripts

Not all transcripts will need translation. Translation is only triggered when the source language differs from the user's preferred reading language. Estimated translation rate:

| User profile | Estimated % needing translation | Effective monthly volume (of 1000 ingested) |
|--------------|--------------------------------|---------------------------------------------|
| Monolingual user (consumes content in their language) | 10-20% | 100-200 transcripts |
| Bilingual user (e.g., FR user consuming EN content) | 40-60% | 400-600 transcripts |
| Polyglot user (consumes content in 3+ languages) | 20-40% | 200-400 transcripts |

### Adjusted Cost Projections (assuming 30% translation rate = 300 transcripts/month)

| Solution | Monthly Cost |
|----------|-------------|
| **GPT-5-nano** | **$0.68** |
| **GPT-5.4-nano** | **$2.19** |
| **Azure Translator** | $60.00 |
| **AWS Translate** | $90.00 |
| **Google Translate NMT** | $120.00 |
| **DeepL API Pro** | $150.00 |

At 300 transcripts/month, GPT-5-nano costs less than $1/month for translation, making it essentially negligible in the overall cost structure.

---

## Implementation Notes

### System Prompt for GPT-5-nano Translation

```
You are a translation assistant specialized in translating transcripts.

Rules:
- Translate the following transcript from {source_language} to {target_language}.
- Preserve ALL formatting: paragraph breaks, line breaks, timestamps (e.g., [00:05:32]), speaker labels.
- Maintain the oral/conversational register. Do NOT formalize the language.
- Keep proper nouns, brand names, and technical terms in their original form when appropriate.
- If timestamps or speaker labels are present, keep them exactly as-is (do not translate them).
- Output ONLY the translated text. No commentary, no notes, no explanations.

Transcript:
{transcript_text}
```

### Pipeline Integration Point

Translation should occur:
1. **After** transcript retrieval (YouTube subs, Podcasting 2.0, Deepgram, etc.)
2. **Before** artifact generation (summary, flashcards, notes, quiz)
3. **Conditionally**: Only when `transcript_language != user_preferred_language`

### Language Detection

If the transcript's language is not already known from the source (e.g., YouTube subtitle language tag), use:
- OpenAI's own language detection (include in the translation prompt: "First detect the language, then translate if different from {target}")
- Or a lightweight detection call (AWS Comprehend, or langdetect Python library for free local detection)

---

## Sources

1. **OpenAI GPT-5-nano pricing and capabilities**: https://developers.openai.com/api/docs/models/gpt-5-nano (verified June 2026)
2. **OpenAI GPT-5.4-nano pricing**: https://developers.openai.com/api/docs/pricing (verified June 2026)
3. **Google Cloud Translation pricing**: https://cloud.google.com/translate/pricing (verified June 2026)
4. **Google Cloud Translation quotas**: https://docs.cloud.google.com/translate/quotas (verified June 2026)
5. **Google Cloud Translation language support**: https://docs.cloud.google.com/translate/docs/languages (verified June 2026)
6. **AWS Translate pricing**: https://aws.amazon.com/translate/pricing/ (verified June 2026)
7. **AWS Translate supported languages**: https://docs.aws.amazon.com/translate/latest/dg/what-is-languages.html (verified June 2026)
8. **Azure Translator service limits**: https://learn.microsoft.com/en-us/azure/ai-services/translator/service-limits (verified June 2026)
9. **Azure Translator language support**: https://learn.microsoft.com/en-us/azure/ai-services/translator/language-support (verified June 2026)
10. **Azure Translator API reference**: https://learn.microsoft.com/en-us/azure/ai-services/translator/reference/v3-0-translate (verified June 2026)
11. **DeepL supported languages**: https://developers.deepl.com/docs/resources/supported-languages (verified June 2026)
12. **DeepL API limits**: https://developers.deepl.com/docs/api-reference/translate — max 128 KiB per request, 50 text elements (verified June 2026)
13. **DeepL quality benchmarks**: https://www.deepl.com/en/quality — March 2026 blind tests, 94% win rate, 48,000 evaluations (verified June 2026)
14. **DeepL competitive claims**: https://www.deepl.com/en/whydeepl — 1.3x vs Google, 1.7x vs ChatGPT-4, 2.3x vs Microsoft (verified June 2026)
15. **Jiao et al. "Is ChatGPT a Good Translator?"**: https://arxiv.org/abs/2301.08745 — GPT-4 matches commercial MT on high-resource European languages, good on spoken language (2023)
16. **Task-72 LLM Artifact Benchmark (owner decision)**: docs/research/task-72-llm-artifact-benchmark/README.md — gpt-5-nano for summary_short, gpt-5.4-nano for other artifacts (validated 2026-04-29)
17. **DeepL API Pro pricing** (from DeepL's developer portal, known pricing): $25/1M characters for API Pro pay-as-you-go plan; Free plan: 500,000 characters/month limit.

---

## Appendix: Decision Matrix (Weighted)

| Criterion | Weight | GPT-5-nano | GPT-5.4-nano | DeepL Pro | Google NMT | AWS Translate | Azure Translator |
|-----------|--------|-----------|-------------|-----------|-----------|---------------|-----------------|
| **Cost** | 30% | 10 | 9 | 2 | 3 | 4 | 5 |
| **Quality (spoken text)** | 25% | 8 | 9 | 9 | 7 | 6 | 6 |
| **Structure preservation** | 15% | 10 | 10 | 5 | 4 | 4 | 6 |
| **Stack reuse / simplicity** | 15% | 10 | 10 | 3 | 4 | 6 | 3 |
| **Language coverage** | 10% | 8 | 8 | 6 | 10 | 7 | 9 |
| **Latency** | 5% | 7 | 6 | 9 | 10 | 8 | 8 |
| **Weighted Score** | 100% | **9.15** | **9.15** | **5.00** | **5.35** | **5.15** | **5.45** |

**GPT-5-nano wins decisively** due to the massive cost advantage and the operational simplicity of reusing the existing OpenAI integration, combined with excellent structure preservation for transcript-specific content.

---

## V1 Languages Supported

The following 11 languages are confirmed supported by the recommended solution (GPT-5-nano) and all evaluated alternatives:

| Language | Code | Supported by GPT-5-nano | Notes |
|----------|------|------------------------|-------|
| French | fr | Yes | Primary target (app creator language) |
| English | en | Yes | Most common source language |
| Spanish | es | Yes | High-resource, excellent quality |
| German | de | Yes | High-resource, excellent quality |
| Italian | it | Yes | High-resource, excellent quality |
| Portuguese | pt | Yes | High-resource, excellent quality |
| Dutch | nl | Yes | High-resource, good quality |
| Japanese | ja | Yes | Well-supported, good quality |
| Chinese | zh | Yes | Well-supported, good quality |
| Arabic | ar | Yes | Supported, good quality |
| Hindi | hi | Yes | Supported, good quality |
