---
benchmark_validated: false
---

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — accept / reject / accept with modifications)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

# Task 72: LLM Benchmark for Artifact Generation

**Date**: 2026-04-28
**Status**: Research Refreshed
**Task**: Exhaustive benchmark of LLM providers for artifact generation (summary_short, summary_detailed, flashcards, notes)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Methodology](#methodology)
3. [Model Inventory and Pricing](#model-inventory-and-pricing)
4. [Quality and Performance Analysis](#quality-and-performance-analysis)
5. [Comparison by Artifact Type](#comparison-by-artifact-type)
6. [Recommendations by Artifact Type](#recommendations-by-artifact-type)
7. [Monthly Cost Estimation by Persona](#monthly-cost-estimation-by-persona)
8. [Implementation Strategy](#implementation-strategy)
9. [Risk Analysis and Mitigation](#risk-analysis-and-mitigation)

---

## Executive Summary

This research evaluates LLM providers across multiple dimensions (quality, cost, latency, context window, JSON reliability) to recommend optimal models for each artifact type in the media-summarizer application.

### Key Findings

1. **OpenAI is now the default recommendation for V1 artifacts** after the April 28, 2026 refresh: `GPT-5 nano` is the cheapest high-confidence short-summary option at $0.1375/M blended, `GPT-5.4` is cost-credible for detailed summaries at $5.625/M blended, and `GPT-4o-mini` remains the safest low-cost structured-output option at $0.2625/M blended.
2. **Google Gemini 2.5 Flash-Lite** remains the best non-OpenAI cost/performance fallback for high-volume generation at $0.17/M blended, with a free tier, but it no longer beats `GPT-5 nano` on paid-token cost for short summaries.
3. **Claude Sonnet 4.6** remains the strongest non-OpenAI premium fallback for complex summarization, but `GPT-5.4` is now slightly cheaper for the benchmark workload and keeps native OpenAI structured output support.
4. **Open source models** (Llama 3, Qwen) via providers like Groq/Fireworks still offer ultra-low costs ($0.05-0.20/M tokens) but with quality and JSON reliability trade-offs.

### Cost Impact

With the refreshed OpenAI pricing and the updated recommended mix, estimated LLM cost is **$0.03205 per media item**, versus roughly **$0.10-0.15** for a GPT-4-everywhere setup, i.e. about **68-79% lower**.

---

## Methodology

### Research Approach

1. **Web research**: Re-checked OpenAI pricing and model capabilities on official OpenAI pages on April 28, 2026; non-OpenAI provider data remains from the April 2026 snapshot unless explicitly noted.
2. **Comparative quality pass**: Re-ranked candidate models using current model positioning, structured-output support, context windows, latency class, and the existing benchmark scores. This was a desk-research pass, not a live API eval run.
3. **Context analysis**: Reviewed model specifications for context windows and capabilities.
4. **Use case mapping**: Matched model characteristics to artifact requirements.

### Evaluation Criteria

For each artifact type (summary_short, summary_detailed, flashcards, notes):

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Quality** | 40% | Relevance, accuracy, coherence, faithfulness to source |
| **Cost** | 30% | Input + output token costs per generation |
| **Latency** | 15% | Time to first token + generation speed |
| **Context Window** | 10% | Ability to handle long transcripts |
| **JSON Reliability** | 5% | Ability to produce valid structured output (critical for flashcards) |

### Artifact Characteristics

| Artifact | Typical Input | Typical Output | Complexity | JSON Required |
|----------|---------------|----------------|------------|---------------|
| **summary_short** | 1,000 tokens | 300 tokens | Low | No |
| **summary_detailed** | 3,000 tokens | 1,500 tokens | High | No |
| **flashcards** | 2,000 tokens | 800 tokens | Medium | Yes |
| **notes** | 2,500 tokens | 1,200 tokens | Medium | Structured text |

---

## Model Inventory and Pricing

### OpenAI Models

**Pricing**: Verified on OpenAI's official pricing and model pages on April 28, 2026. Standard short-context prices are used for this benchmark because the artifact workloads stay far below the 272k-token threshold that triggers long-context pricing for `gpt-5.5`/`gpt-5.4`.

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Blended (3:1) | Context Window | Structured Outputs | Notes |
|-------|---------------------|----------------------|---------------|----------------|--------------------|-------|
| **GPT-5 nano** | $0.05 | $0.40 | $0.1375 | 400k | Yes | Cheapest OpenAI option; explicitly positioned for summarization/classification |
| **GPT-4.1 nano** | $0.10 | $0.40 | $0.1750 | 1M | Yes | Cheap non-reasoning fallback with very long context |
| **GPT-4o-mini** | $0.15 | $0.60 | $0.2625 | 128k | Yes | Mature Omni model; strongest proven low-cost JSON candidate |
| **GPT-5.4 nano** | $0.20 | $1.25 | $0.4625 | 400k | Yes | Newer speed/cost model OpenAI recommends for cost-sensitive workloads |
| **GPT-5 mini** | $0.25 | $2.00 | $0.6875 | 400k | Yes | Older low-latency GPT-5 variant; docs now point new high-volume workloads to `gpt-5.4-mini` |
| **GPT-4.1 mini** | $0.40 | $1.60 | $0.7000 | 1M | Yes | Long-context non-reasoning fallback |
| **GPT-5.4 mini** | $0.75 | $4.50 | $1.6875 | 400k | Yes | Stronger mini model for high-volume workloads when quality matters more than token cost |
| **GPT-4.1** | $2.00 | $8.00 | $3.5000 | 1M | Yes | Non-reasoning long-context baseline |
| **GPT-4o** | $2.50 | $10.00 | $4.3750 | 128k | Yes | Mature high-quality generalist, still materially pricier |
| **GPT-5.4** | $2.50 | $15.00 | $5.6250 | 1.05M | Yes | Recommended OpenAI detailed-summary candidate; long-context price doubles input and 1.5x output above 272k tokens |
| **GPT-5.5** | $5.00 | $30.00 | $11.2500 | 1.05M | Yes | Latest flagship; premium fallback for highest-quality generations |
| **GPT-4/GPT-3.5-turbo (legacy)** | n/a | n/a | n/a | 8k-16k | No | Deprecated/obsolete for new V1 architecture choices |

**Sources**:
- Pricing: https://openai.com/api/pricing/
- Detailed pricing: https://developers.openai.com/api/docs/pricing
- Model comparison: https://developers.openai.com/api/docs/models/compare
- GPT-5.5: https://developers.openai.com/api/docs/models
- GPT-5.4: https://developers.openai.com/api/docs/models/gpt-5.4
- GPT-5.4 mini: https://developers.openai.com/api/docs/models/gpt-5.4-mini
- GPT-5.4 nano: https://developers.openai.com/api/docs/models/gpt-5.4-nano
- GPT-5 nano: https://developers.openai.com/api/docs/models/gpt-5-nano
- GPT-5 mini: https://developers.openai.com/api/docs/models/gpt-5-mini
- GPT-4.1 mini: https://developers.openai.com/api/docs/models/gpt-4.1-mini
- GPT-4o mini: https://developers.openai.com/api/docs/models/gpt-4o-mini
- GPT-4o: https://developers.openai.com/api/docs/models/gpt-4o

**Strengths**:
- Structured Outputs supported across the OpenAI models that matter for artifacts (`GPT-5 nano`, `GPT-4o-mini`, `GPT-5.4 nano`, `GPT-5.4`, `GPT-5.5`)
- `GPT-5 nano` is now the cheapest credible paid model in this benchmark for simple summarization
- `GPT-5.4`/`GPT-5.5` add 1.05M context windows while keeping native OpenAI schema/tooling support
- Batch API offers a 50% discount on asynchronous workloads

**Weaknesses**:
- No free tier
- `GPT-5.4`/`GPT-5.5` long-context sessions above 272k input tokens are materially more expensive than the short-context prices used in this benchmark
- `GPT-4` and `GPT-3.5-turbo` are now legacy/deprecated options and should not drive new architecture choices
- This refresh is a documented comparative desk-research pass; it does not replace a future live A/B quality evaluation on the project's own transcript corpus

---

### Anthropic Claude Models

**Pricing**: From https://platform.claude.com/docs/en/docs/about-claude/models

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Blended (3:1) | Context Window | Intelligence Score |
|-------|---------------------|----------------------|---------------|----------------|-------------------|
| **Claude Opus 4.7** | $5.00 | $25.00 | $10.00 | 1M | 57 (highest) |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | $6.00 | 1M | 44 |
| **Claude Haiku 4.5** | $1.00 | $5.00 | $2.00 | 200k | 31 |

**Source**: https://platform.claude.com/docs/en/docs/about-claude/models (verified Apr 2026)

**Strengths**:
- **Highest quality** for complex reasoning and summarization
- Excellent long-context handling (1M tokens for Opus/Sonnet)
- Very good at following instructions and maintaining consistency
- Strong performance on nuanced content understanding

**Weaknesses**:
- More expensive than Google/open source alternatives
- Slower output speed (44 tokens/sec for Sonnet vs 186 for Gemini Flash)
- No free tier

---

### Google Gemini Models

**Pricing**: From https://ai.google.dev/pricing (verified Apr 2026)

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Blended (3:1) | Context Window | Intelligence Score | Free Tier |
|-------|---------------------|----------------------|---------------|----------------|-------------------|-----------|
| **Gemini 3.1 Pro Preview** | $2.00 | $12.00 | $4.50 | 200k | 57 | No |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | $3.44 | 200k | High | Yes |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | $0.85 | 1M | 35 | Yes |
| **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | $0.17 | 1M | 19 | Yes |
| **Gemini 3.1 Flash-Lite Preview** | $0.25 | $1.50 | $0.56 | 1M | Medium | Yes |
| **Gemini 3 Flash Preview** | $0.50 | $3.00 | $1.00 | 1M | Medium | Yes |

**Batch API**: 50% discount on all prices for non-urgent processing

**Source**: https://ai.google.dev/pricing (verified Apr 2026)

**Strengths**:
- **Best non-OpenAI cost-performance ratio** (Flash-Lite at $0.17/M blended)
- **Generous free tier** (all models except 3.1 Pro)
- Fast inference speed (186 tokens/sec for Flash)
- Excellent context windows (1M tokens)
- Batch API discount (50% off)

**Weaknesses**:
- Lower quality scores for Flash-Lite models (19 vs 44 for Claude Sonnet)
- Less consistent with complex instructions vs Claude
- JSON mode not as robust as OpenAI

---

### Mistral AI Models

**Pricing**: Unable to extract from official sources (auth wall, no public API pricing page)

**Known information** (from public sources):
- Mistral Large 3: Estimated $2-4/M input, $6-12/M output
- Mistral Medium 3: Estimated $1-2/M input, $4-8/M output
- Ministral (small): Estimated $0.20-0.40/M blended

**Source**: Pricing unavailable via web scraping; estimates based on competitive positioning

**Status**: Cannot recommend without confirmed pricing

---

### Open Source Models (via Inference Providers)

#### Groq (Ultra-fast inference)

**Pricing**: From https://groq.com/pricing (verified Apr 2026)

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Blended (3:1) | Speed (tokens/sec) |
|-------|---------------------|----------------------|---------------|-------------------|
| **Llama 3.1 8B Instant** | $0.05 | $0.08 | $0.0575 | 840 |
| **Llama 3.3 70B Versatile** | $0.59 | $0.79 | $0.6425 | 394 |
| **Llama 4 Scout 17B** | $0.11 | $0.34 | $0.1675 | 594 |

**Strengths**:
- **Ultra-low cost** (Llama 3.1 8B at $0.0575/M blended)
- **Blazing fast** (840 tokens/sec for 8B model)
- Linear, predictable pricing

**Weaknesses**:
- Lower quality than Claude/GPT (Llama 3.1 70B ≈ GPT-3.5 quality)
- Less reliable JSON output
- Limited context (128k)

---

#### Fireworks AI (Serverless)

**Pricing**: From https://fireworks.ai/pricing (verified Apr 2026)

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Notes |
|-------|---------------------|----------------------|-------|
| **< 4B params** | $0.10 | - | Blended pricing |
| **4B-16B params** | $0.20 | - | Blended pricing |
| **> 16B params** | $0.90 | - | Blended pricing |
| **DeepSeek V3** | $0.56 | $1.68 | $0.84 blended |
| **Qwen3 VL 30B** | $0.15 | $0.60 | $0.30 blended |
| **OpenAI gpt-oss-20b** | $0.07 | $0.30 | $0.13 blended |

**Batch discount**: 50% off for batch inference

**Strengths**:
- Flexible pricing by model size
- Good selection of open models (Llama, Qwen, DeepSeek)
- Batch discount (50%)

**Weaknesses**:
- Quality varies significantly by model
- Less established than Groq/Together

---

#### Together AI (Serverless)

**Pricing**: From https://together.ai/pricing (verified Apr 2026)

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Blended (3:1) |
|-------|---------------------|----------------------|---------------|
| **Llama 3.3 70B** | $0.88 | $0.88 | $0.88 |
| **Llama 3 8B Instruct Lite** | $0.10 | $0.10 | $0.10 |
| **Qwen3.5 9B** | $0.10 | $0.15 | $0.1125 |
| **Qwen2.5 7B Instruct Turbo** | $0.30 | $0.30 | $0.30 |
| **DeepSeek-V3.1** | $0.60 | $1.70 | $0.875 |
| **Gemma 3n E4B Instruct** | $0.06 | $0.12 | $0.075 |

**Batch discount**: 50% off for most models

**Strengths**:
- Wide model selection
- Competitive pricing
- Batch API support

**Weaknesses**:
- Variable quality
- Less documentation than major providers

---

### Summary: Price Comparison

**Ranked by blended cost (3:1 input/output ratio):**

| Rank | Model | Blended Cost ($/1M) | Provider | Free Tier |
|------|-------|---------------------|----------|-----------|
| 1 | Llama 3.1 8B | $0.0575 | Groq | No |
| 2 | Gemma 3n E4B | $0.075 | Together AI | No |
| 3 | Llama 3 8B Lite | $0.10 | Together AI | No |
| 4 | Qwen3.5 9B | $0.1125 | Together AI | No |
| 5 | gpt-oss-20b | $0.13 | Fireworks | No |
| 6 | GPT-5 nano | $0.1375 | OpenAI | No |
| 7 | Llama 4 Scout 17B | $0.1675 | Groq | No |
| 8 | **Gemini 2.5 Flash-Lite** | **$0.17** | **Google** | **Yes** |
| 9 | GPT-4.1 nano | $0.1750 | OpenAI | No |
| 10 | GPT-4o-mini | $0.2625 | OpenAI | No |
| 11 | Qwen3 VL 30B | $0.30 | Fireworks | No |
| 12 | GPT-5.4 nano | $0.4625 | OpenAI | No |
| 13 | Gemini 3.1 Flash-Lite | $0.56 | Google | Yes |
| 14 | GPT-5 mini | $0.6875 | OpenAI | No |
| 15 | GPT-4.1 mini | $0.7000 | OpenAI | No |
| 16 | DeepSeek-V3 | $0.84 | Fireworks | No |
| 17 | Gemini 2.5 Flash | $0.85 | Google | Yes |
| 18 | Llama 3.3 70B | $0.88 | Together AI | No |
| 19 | Gemini 3 Flash | $1.00 | Google | Yes |
| 20 | GPT-5.4 mini | $1.6875 | OpenAI | No |
| 21 | Claude Haiku 4.5 | $2.00 | Anthropic | No |
| 22 | Gemini 2.5 Pro | $3.44 | Google | Yes |
| 23 | GPT-4.1 | $3.5000 | OpenAI | No |
| 24 | GPT-4o | $4.3750 | OpenAI | No |
| 25 | Gemini 3.1 Pro | $4.50 | Google | No |
| 26 | GPT-5.4 | $5.6250 | OpenAI | No |
| 27 | Claude Sonnet 4.6 | $6.00 | Anthropic | No |
| 28 | Claude Opus 4.7 | $10.00 | Anthropic | No |
| 29 | GPT-5.5 | $11.2500 | OpenAI | No |

---

## Quality and Performance Analysis

### Intelligence Rankings

Based on the April 2026 benchmark snapshot plus the April 28, 2026 OpenAI model refresh:

| Model | Intelligence Tier / Score | Use Case |
|-------|----------------------------|----------|
| **GPT-5.5** | Frontier (OpenAI latest) | Highest-quality OpenAI fallback, complex synthesis |
| **GPT-5.4** | Frontier/near-frontier | Detailed summaries, long-context synthesis |
| **Claude Opus 4.7** | 57 | Most complex reasoning, agentic coding |
| **Gemini 3.1 Pro** | 57 | Complex multimodal tasks |
| **Claude Sonnet 4.6** | 44 | Balanced speed/intelligence |
| **GPT-5.4 mini** | High-volume strong mini | Higher-quality structured generation |
| **GPT-5.4 nano** | Cost-optimized latest nano | Simple/medium structured generation |
| **GPT-5 nano** | Cost-optimized summarization/classification | Short summaries, low-cost structured tasks |
| **Gemini 2.5 Flash** | 35 | Fast, balanced tasks |
| **Claude Haiku 4.5** | 31 | Fast, economical |
| **Gemini 2.5 Flash-Lite** | 19 | High-volume, cost-optimized |
| **Llama 3.3 70B** | ~35-38 (estimate) | Open source, GPT-3.5 equivalent |
| **Llama 3.1 8B** | ~25-28 (estimate) | Ultra-fast, basic tasks |

**Note**: OpenAI's newest model tiers are ranked from official model positioning and capabilities rather than a project-local eval run. Open source model scores are estimates based on community benchmarks and are not included in Artificial Analysis leaderboard.

---

### Latency and Speed

**Output Speed (tokens per second)**:

| Model | Speed (t/s) | Latency (TTFT) | Provider |
|-------|-------------|----------------|----------|
| **Llama 3.1 8B** | 840 | <0.5s | Groq |
| **Llama 4 Scout 17B** | 594 | ~0.6s | Groq |
| **Llama 3.3 70B** | 394 | ~1.0s | Groq |
| **Gemini 2.5 Flash** | 186 | ~0.8s | Google |
| **GPT-4o** | 138 | 1.01s | OpenAI |
| **GPT-5.4 mini/nano** | Faster class | n/a | OpenAI |
| **GPT-5 nano** | Fastest/cheapest class | n/a | OpenAI |
| **Claude Sonnet 4.6** | 44 | ~1.5s | Anthropic |

**Key Insight**: Groq's ultra-fast LPU inference delivers 6-10x faster generation than traditional providers, making it ideal for latency-sensitive applications.

---

### Context Window Support

**For handling long transcripts:**

| Model | Context Window | Suitable for |
|-------|----------------|--------------|
| Llama 4 Scout | 10M tokens | Extremely long content |
| GPT-5.5 | 1.05M tokens | Long podcasts (3+ hours), premium OpenAI fallback |
| GPT-5.4 | 1.05M tokens | Long podcasts (3+ hours), detailed summaries |
| Claude Opus 4.7 | 1M tokens | Long podcasts (3+ hours) |
| Claude Sonnet 4.6 | 1M tokens | Long podcasts (3+ hours) |
| Gemini 2.5 Flash | 1M tokens | Long podcasts (3+ hours) |
| Gemini 2.5 Flash-Lite | 1M tokens | Long podcasts (3+ hours) |
| GPT-4.1 / GPT-4.1 mini / GPT-4.1 nano | 1M tokens | Long non-reasoning fallback |
| GPT-5.4 mini / GPT-5.4 nano / GPT-5 mini / GPT-5 nano | 400k tokens | Most V1 media, including long podcasts |
| GPT-4o | 128k tokens | Standard podcasts (1-2 hours) |
| Claude Haiku 4.5 | 200k tokens | Standard podcasts (1-2 hours) |
| Llama 3.1 8B/70B | 128k tokens | Standard podcasts (1-2 hours) |

**Note**: 128k tokens ≈ 96,000 words ≈ 4-5 hours of transcript (20k tokens/hour average)

---

### JSON Reliability

**Structured output reliability (based on industry knowledge and provider documentation):**

| Model | JSON Mode | Reliability | Notes |
|-------|-----------|-------------|-------|
| **GPT-5.5 / GPT-5.4** | Native Structured Outputs | ★★★★★ | Best OpenAI reliability plus latest model quality |
| **GPT-5 nano / GPT-5.4 nano** | Native Structured Outputs | ★★★★★ | Lowest-cost OpenAI schema-safe options |
| **GPT-4o** | Native | ★★★★★ | Best-in-class, guaranteed valid JSON |
| **GPT-4o-mini** | Native | ★★★★★ | Same reliability as GPT-4o |
| **Claude Sonnet 4.6** | Guided | ★★★★☆ | Very reliable with proper prompting |
| **Claude Haiku 4.5** | Guided | ★★★★☆ | Good with structured prompts |
| **Gemini 2.5 Flash** | Partial | ★★★☆☆ | Good but requires validation |
| **Gemini 2.5 Flash-Lite** | Partial | ★★★☆☆ | Needs careful prompt engineering |
| **Llama 3.3 70B** | None | ★★☆☆☆ | Frequent failures, needs retry logic |
| **Llama 3.1 8B** | None | ★★☆☆☆ | High failure rate for complex structures |

**Recommendation**: For flashcards (JSON required), prioritize OpenAI or Claude models, or implement robust validation + retry logic for Gemini/open source.

---

## Comparison by Artifact Type

### 1. Summary Short (Newsletter format)

**Requirements**:
- Low complexity (simple summarization)
- Short output (300 tokens)
- Fast generation preferred
- No JSON required
- High volume (every media item)

**Evaluation**:

| Model | Quality | Cost/req | Latency | Score | Rank |
|-------|---------|----------|---------|-------|------|
| **GPT-5 nano** | ★★★★☆ | $0.00017 | ★★★★★ | **9/10** | **1** |
| Gemini 2.5 Flash-Lite | ★★★☆☆ | $0.00022 | ★★★★★ | 8/10 | 2 |
| Llama 3.1 8B (Groq) | ★★☆☆☆ | $0.00007 | ★★★★★ | 8/10 | 2 |
| GPT-4o-mini | ★★★★☆ | $0.00033 | ★★★★☆ | 8/10 | 2 |
| GPT-5.4 nano | ★★★★☆ | $0.00058 | ★★★★★ | 8/10 | 5 |
| Gemini 2.5 Flash | ★★★★☆ | $0.00105 | ★★★★★ | 7/10 | 6 |
| Claude Haiku 4.5 | ★★★★☆ | $0.00250 | ★★★★☆ | 6/10 | 7 |

**Cost calculation** (1,000 input + 300 output tokens):
- Gemini Flash-Lite: (1000 × $0.10 + 300 × $0.40) / 1M = **$0.00022**
- GPT-5 nano: (1000 × $0.05 + 300 × $0.40) / 1M = **$0.00017**
- Llama 3.1 8B: (1300 × $0.0575) / 1M = **$0.00007**
- GPT-4o-mini: (1000 × $0.15 + 300 × $0.60) / 1M = **$0.00033**

**Winner**: **GPT-5 nano**
- Lowest paid-token cost among high-confidence managed models for this workload
- Officially positioned for summarization/classification
- Native structured-output support if the short summary later becomes schema-backed
- 400k context window is sufficient for V1 media transcripts

**Fallback**: **Gemini 2.5 Flash-Lite** remains the best free-tier fallback and the best non-OpenAI cost/performance option.

---

### 2. Summary Detailed (Comprehensive learning)

**Requirements**:
- High complexity (deep understanding, nuance)
- Long output (1,500 tokens)
- Quality > cost
- No JSON required
- Medium volume

**Evaluation**:

| Model | Quality | Cost/req | Latency | Score | Rank |
|-------|---------|----------|---------|-------|------|
| **GPT-5.4** | ★★★★★ | $0.03000 | ★★★★☆ | **9/10** | **1** |
| Claude Sonnet 4.6 | ★★★★★ | $0.03150 | ★★★☆☆ | 9/10 | 2 |
| Gemini 2.5 Pro | ★★★★★ | $0.01875 | ★★★★☆ | 8/10 | 3 |
| GPT-4o | ★★★★★ | $0.02250 | ★★★★☆ | 8/10 | 4 |
| Claude Opus 4.7 | ★★★★★ | $0.05250 | ★★★☆☆ | 8/10 | 5 |
| Gemini 2.5 Flash | ★★★★☆ | $0.00465 | ★★★★★ | 7/10 | 6 |
| GPT-5.4 nano | ★★★★☆ | $0.00248 | ★★★★★ | 7/10 | 7 |

**Cost calculation** (3,000 input + 1,500 output tokens):
- Claude Sonnet 4.6: (3000 × $3.00 + 1500 × $15.00) / 1M = **$0.03150**
- GPT-5.4: (3000 × $2.50 + 1500 × $15.00) / 1M = **$0.03000**
- Gemini 2.5 Flash: (3000 × $0.30 + 1500 × $2.50) / 1M = **$0.00465**
- GPT-4o: (3000 × $2.50 + 1500 × $10.00) / 1M = **$0.02250**

**Winner**: **GPT-5.4**
- Latest OpenAI detailed-summary candidate with 1.05M context and native structured outputs
- Slightly cheaper than Claude Sonnet 4.6 for the benchmark workload
- Keeps summary generation on the same OpenAI-compatible API family as flashcards/notes
- Long-context surcharge is not triggered by the V1 token assumptions

**Budget Alternative**: **Gemini 2.5 Flash** (85% less cost, 85% quality)

**Premium fallback**: **Claude Sonnet 4.6** remains the preferred non-OpenAI fallback if live A/B tests show better faithfulness on long French transcripts.

---

### 3. Flashcards (Q&A generation)

**Requirements**:
- Medium complexity (creative question generation)
- Medium output (800 tokens, ~10 Q&A pairs)
- **JSON required** (critical)
- Medium volume

**Evaluation**:

| Model | Quality | Cost/req | JSON Reliability | Score | Rank |
|-------|---------|----------|------------------|-------|------|
| **GPT-4o-mini** | ★★★★☆ | $0.00078 | ★★★★★ | **9/10** | **1** |
| GPT-5 nano | ★★★☆☆ | $0.00042 | ★★★★★ | 8/10 | 2 |
| GPT-5.4 nano | ★★★★☆ | $0.00140 | ★★★★★ | 8/10 | 3 |
| Claude Haiku 4.5 | ★★★★☆ | $0.00600 | ★★★★☆ | 8/10 | 4 |
| GPT-4o | ★★★★★ | $0.01300 | ★★★★★ | 7/10 | 5 |
| Gemini 2.5 Flash | ★★★☆☆ | $0.00260 | ★★★☆☆ | 6/10 | 6 |
| Gemini 2.5 Flash-Lite | ★★☆☆☆ | $0.00052 | ★★★☆☆ | 5/10 | 7 |

**Cost calculation** (2,000 input + 800 output tokens):
- GPT-4o-mini: (2000 × $0.15 + 800 × $0.60) / 1M = **$0.00078**
- GPT-5 nano: (2000 × $0.05 + 800 × $0.40) / 1M = **$0.00042**
- GPT-5.4 nano: (2000 × $0.20 + 800 × $1.25) / 1M = **$0.00140**
- Claude Haiku 4.5: (2000 × $1.00 + 800 × $5.00) / 1M = **$0.00600**
- Gemini 2.5 Flash: (2000 × $0.30 + 800 × $2.50) / 1M = **$0.00260**

**Winner**: **GPT-4o-mini**
- Best JSON reliability (native JSON mode)
- Excellent quality for Q&A generation
- Very low cost
- Fast inference

**Critical**: JSON reliability is paramount for flashcards. `GPT-5 nano` is cheaper and schema-capable, but `GPT-4o-mini` remains the safer default until live flashcard-quality tests confirm that the nano model produces questions with comparable pedagogical value.

---

### 4. Notes (Structured takeaways)

**Requirements**:
- Medium complexity (extraction + organization)
- Medium-long output (1,200 tokens)
- Structured text (not strict JSON)
- Medium volume

**Evaluation**:

| Model | Quality | Cost/req | Latency | Score | Rank |
|-------|---------|----------|---------|-------|------|
| **GPT-4o-mini** | ★★★★☆ | $0.00110 | ★★★★☆ | **9/10** | **1** |
| GPT-5 nano | ★★★☆☆ | $0.00061 | ★★★★★ | 8/10 | 2 |
| GPT-5.4 nano | ★★★★☆ | $0.00200 | ★★★★★ | 8/10 | 3 |
| Gemini 2.5 Flash | ★★★★☆ | $0.00375 | ★★★★★ | 8/10 | 4 |
| Claude Haiku 4.5 | ★★★★☆ | $0.00850 | ★★★★☆ | 7/10 | 5 |
| Claude Sonnet 4.6 | ★★★★★ | $0.02550 | ★★★☆☆ | 7/10 | 6 |
| Gemini 2.5 Flash-Lite | ★★★☆☆ | $0.00073 | ★★★★★ | 6/10 | 7 |

**Cost calculation** (2,500 input + 1,200 output tokens):
- GPT-4o-mini: (2500 × $0.15 + 1200 × $0.60) / 1M = **$0.001095**
- GPT-5 nano: (2500 × $0.05 + 1200 × $0.40) / 1M = **$0.000605**
- GPT-5.4 nano: (2500 × $0.20 + 1200 × $1.25) / 1M = **$0.00200**
- Gemini 2.5 Flash: (2500 × $0.30 + 1200 × $2.50) / 1M = **$0.00375**
- Claude Haiku 4.5: (2500 × $1.00 + 1200 × $5.00) / 1M = **$0.00850**

**Winner**: **GPT-4o-mini**
- Current pricing keeps it materially cheaper than Gemini Flash for this artifact
- More mature default than `GPT-5 nano` for medium-complexity structured notes
- Native structured outputs simplify schema discipline even when strict JSON is not required
- Consolidates `notes` and `flashcards` on the same provider/model family

---

## Recommendations by Artifact Type

### Recommended Model Mix

| Artifact | Recommended Model | Alternative | Rationale |
|----------|------------------|-------------|-----------|
| **summary_short** | **GPT-5 nano** | Gemini 2.5 Flash-Lite | Lowest paid cost among high-confidence managed models; officially suited to summarization |
| **summary_detailed** | **GPT-5.4** | Claude Sonnet 4.6 | Slightly cheaper than Sonnet for this workload, 1.05M context, native OpenAI structured outputs |
| **flashcards** | **GPT-4o-mini** | Claude Haiku 4.5 | Best JSON reliability, critical for structured output |
| **notes** | **GPT-4o-mini** | GPT-5.4 nano | Mature structured-output behavior at lower cost than Gemini Flash |

---

### Cost Calculation: Recommended Mix

**Per media item** (all 4 artifacts):

| Artifact | Model | Input | Output | Cost |
|----------|-------|-------|--------|------|
| summary_short | GPT-5 nano | 1,000 | 300 | $0.00017 |
| summary_detailed | GPT-5.4 | 3,000 | 1,500 | $0.03000 |
| flashcards | GPT-4o-mini | 2,000 | 800 | $0.00078 |
| notes | GPT-4o-mini | 2,500 | 1,200 | $0.00110 |
| **TOTAL** | - | - | - | **$0.03205** |

**Comparison with current setup** (GPT-4 for all):
- Current cost estimate (GPT-4): ~$0.10-0.15 per media
- Recommended mix: **$0.03205** per media
- **Savings: ~68-79%**

---

### Budget-Optimized Mix (Maximum cost reduction)

If cost optimization is critical, use this mix:

| Artifact | Model | Cost |
|----------|-------|------|
| summary_short | Llama 3.1 8B (Groq) | $0.00007 |
| summary_detailed | GPT-5.4 nano | $0.00248 |
| flashcards | GPT-5 nano | $0.00042 |
| notes | GPT-5 nano | $0.00061 |
| **TOTAL** | - | **$0.00358** |

**Trade-offs**:
- 89% cost reduction vs recommended mix
- Lower expected quality for summary_detailed than `GPT-5.4`
- Flashcards and notes need live quality validation before using `GPT-5 nano` as default
- No OpenAI free tier; the Google fallback remains useful for early free-tier testing

---

### Premium Mix (Maximum quality)

For premium tier or critical content:

| Artifact | Model | Cost |
|----------|-------|------|
| summary_short | GPT-5.4 nano | $0.00058 |
| summary_detailed | Claude Opus 4.7 | $0.05250 |
| flashcards | GPT-4o | $0.01300 |
| notes | GPT-5.4 | $0.02425 |
| **TOTAL** | - | **$0.09033** |

**Benefits**:
- Highest possible quality across all artifacts
- Best JSON reliability
- Ideal for power users or premium content

---

## Monthly Cost Estimation by Persona

Using personas from task-65 (docs/research/task-65-benchmark-pricing-v1.md):

### Persona 1: Student (40 media/month)

**Media breakdown**:
- 15 podcasts (45 min avg)
- 25 articles/text
- Total: 40 media/month

**Artifact generation costs** (recommended mix):

| Artifact | Cost per media | Volume | Total |
|----------|----------------|--------|-------|
| summary_short | $0.00017 | 40 | $0.0068 |
| summary_detailed | $0.03000 | 40 | $1.2000 |
| flashcards | $0.00078 | 40 | $0.0312 |
| notes | $0.00110 | 40 | $0.0438 |
| **TOTAL LLM** | - | - | **$1.2818** |

**With transcription** (15 podcasts × 45 min × $0.005/min):
- Transcription: $3.375
- LLM: $1.28
- **Total: $4.66/month**

**Margin at 9€ pricing**: 9 - 4.66 = **€4.34**

---

### Persona 2: Professional (90 media/month)

**Media breakdown**:
- 25 podcasts (60 min avg)
- 15 videos (25 min avg)
- 50 articles
- Total: 90 media/month

**Artifact generation costs**:

| Artifact | Cost per media | Volume | Total |
|----------|----------------|--------|-------|
| summary_short | $0.00017 | 90 | $0.0153 |
| summary_detailed | $0.03000 | 90 | $2.7000 |
| flashcards | $0.00078 | 40 | $0.0312 |
| notes | $0.00110 | 90 | $0.0986 |
| **TOTAL LLM** | - | - | **$2.8451** |

**With transcription**:
- Transcription: (25 × 60 + 15 × 25) × $0.005 = $9.375
- LLM: $2.85
- **Total: $12.22/month**

**Margin at 15€ pricing (Pro tier)**: 15 - 12.22 = **€2.78**

**Note**: This persona requires Pro tier (15€/month) to be profitable.

---

### Persona 3: Power User (165 media/month)

**Media breakdown**:
- 45 podcasts (75 min avg)
- 30 videos (30 min avg)
- 90 articles
- Total: 165 media/month

**Artifact generation costs**:

| Artifact | Cost per media | Volume | Total |
|----------|----------------|--------|-------|
| summary_short | $0.00017 | 165 | $0.0281 |
| summary_detailed | $0.03000 | 165 | $4.9500 |
| flashcards | $0.00078 | 75 | $0.0585 |
| notes | $0.00110 | 165 | $0.1807 |
| **TOTAL LLM** | - | - | **$5.2173** |

**With transcription**:
- Transcription: (45 × 75 + 30 × 30) × $0.005 = $21.375
- LLM: $5.22
- **Total: $26.59/month**

**Margin at 15€ pricing**: 15 - 26.59 = **-€11.59** (LOSS)

**Conclusion**: Power users are unprofitable even at Pro tier. Require either:
- Higher tier (e.g., €30/month)
- Stricter limits (150 media max)
- Usage-based pricing beyond limit

---

### Cost Summary by Persona

| Persona | Media/month | LLM Cost | Transcription | Total Cost | Recommended Price | Margin |
|---------|-------------|----------|---------------|------------|-------------------|--------|
| **Student** | 40 | $1.28 | $3.38 | **$4.66** | €9 | +€4.34 |
| **Professional** | 90 | $2.85 | $9.38 | **$12.22** | €15 | +€2.78 |
| **Power User** | 165 | $5.22 | $21.38 | **$26.59** | €15 | -€11.59 (LOSS) |

**Key Insight**: The recommended LLM mix keeps artifact costs low ($1.28-5.22/month), with transcription remaining the dominant cost driver ($3.38-21.38/month).

---

### Budget Mix Impact

If using the budget-optimized LLM mix:

| Persona | Media/month | LLM Cost (Budget) | Transcription | Total Cost | Margin at €9 |
|---------|-------------|-------------------|---------------|------------|--------------|
| **Student** | 40 | **$0.14** | $3.38 | **$3.52** | +€5.48 (156%) |
| **Professional** | 90 | **$0.30** | $9.38 | **$9.68** | -€0.68 (-7%) |
| **Power User** | 165 | **$0.55** | $21.38 | **$21.93** | -€12.93 (-144%) |

**Savings**: Budget mix reduces LLM costs by ~89%, but transcription remains the bottleneck.

---

## Implementation Strategy

### Phase 1: MVP (Single model for all)

**Goal**: Ship quickly, validate quality

**Approach**: Use **GPT-5.4 nano** for all artifacts
- Cost: $0.00645/media (all 4 artifacts)
- Native OpenAI Structured Outputs for `flashcards` and `notes`
- Sufficient quality for MVP, with better schema discipline than Gemini/Llama budget options
- Simple implementation (single provider)

**Pros**:
- Fastest to implement (one integration)
- Strong OpenAI-compatible API fit
- Good quality baseline for simple and medium artifacts
- No provider switching during MVP stabilization

**Cons**:
- No free tier
- Not optimal quality for detailed summaries
- If detailed-summary quality becomes the blocker, route that artifact to `GPT-5.4` or Claude Sonnet 4.6

---

### Phase 2: Multi-model optimization

**Goal**: Optimize cost/quality per artifact type

**Approach**: Implement recommended mix
- summary_short: GPT-5 nano
- summary_detailed: GPT-5.4
- flashcards: GPT-4o-mini
- notes: GPT-4o-mini

**Implementation**:
1. Add OpenAI API integration with model routing by artifact type
2. Keep Google/Claude adapters as fallback providers, not the default V1 path
3. Route artifacts to appropriate models
4. Monitor costs and quality metrics

**Pros**:
- Optimal cost/quality balance
- ~68-79% cost savings vs GPT-4
- Best JSON reliability for flashcards

**Cons**:
- More complex than single-model MVP
- Higher implementation time
- More error handling needed

---

### Phase 3: Dynamic model selection

**Goal**: Optimize based on content type and user tier

**Approach**: 
- Free/Standard tier: Budget mix (`GPT-5.4 nano`/`GPT-5 nano`, with Gemini free-tier fallback for testing)
- Pro tier: Recommended mix (`GPT-5 nano`/`GPT-5.4`/`GPT-4o-mini`)
- Premium content: Premium mix (Claude Opus/GPT-5.4/GPT-4o)

**Implementation**:
1. Add tier-based model routing
2. Content-based heuristics (e.g., long podcasts → Claude Opus)
3. A/B testing framework
4. User feedback loop

**Pros**:
- Maximum flexibility
- Best margins per tier
- Quality differentiation

**Cons**:
- Most complex
- Requires metrics/monitoring
- Harder to debug

---

### Recommended Rollout

**Month 1-2** (MVP):
- GPT-5.4 nano for all artifacts
- Validate quality, collect feedback
- Use Gemini free tier only for internal fallback experiments

**Month 3-4** (Optimization):
- Route summary_short to GPT-5 nano
- Route summary_detailed to GPT-5.4
- Route flashcards + notes to GPT-4o-mini
- Measure cost/quality improvement

**Month 5+** (Scaling):
- Implement tier-based routing
- Add premium models for Pro users
- Optimize based on usage patterns
- Negotiate volume discounts

---

## Risk Analysis and Mitigation

### Risk 1: Free tier limitations

**Risk**: Google's free tier may have rate limits or quotas that break at scale

**Impact**: High (could halt artifact generation)

**Mitigation**:
1. Monitor usage closely vs free tier limits
2. Have paid tier enabled as backup
3. Implement fallback to Llama 3.1 8B (Groq) if quota exceeded
4. Batch processing to stay within rate limits

---

### Risk 2: Model quality degradation

**Risk**: `GPT-5 nano` or `GPT-5.4 nano` quality insufficient for user expectations on nuanced French media

**Impact**: Medium (user dissatisfaction, churn)

**Mitigation**:
1. A/B test `GPT-5 nano`, `GPT-5.4 nano`, `GPT-5.4`, Gemini Flash, and Claude Sonnet on representative French transcripts
2. Collect user feedback on summary quality
3. Allow user to regenerate with premium model
4. Implement quality scoring (automated)

---

### Risk 3: JSON reliability for flashcards

**Risk**: Gemini/Llama produce invalid JSON, breaking flashcards

**Impact**: High (critical feature broken)

**Mitigation**:
1. Use GPT-4o-mini for flashcards (guaranteed JSON mode)
2. Implement JSON validation + retry logic (max 3 attempts)
3. Fallback to GPT-5.4 nano or GPT-4o if mini fails
4. Monitor JSON parse failure rate (alert if >1%)

---

### Risk 4: Provider outages

**Risk**: Single provider (e.g., Google) goes down, halting generation

**Impact**: High (complete service disruption)

**Mitigation**:
1. Multi-provider strategy (OpenAI + Google + Anthropic)
2. Automatic failover (OpenAI → Gemini → Claude, depending on artifact type)
3. Queue-based processing (retry on failure)
4. Status page monitoring (uptime.com)

---

### Risk 5: Pricing changes

**Risk**: Provider increases prices, breaking cost model

**Impact**: Medium-High (margin compression, potential losses)

**Mitigation**:
1. Monitor pricing pages monthly
2. Lock in annual commitments where possible
3. Maintain cost buffer (20% margin of safety)
4. Multi-provider strategy (can switch if price spike)
5. Pass-through cost increases to users if needed (price adjustment)

---

### Risk 6: Transcription cost dominance

**Risk**: LLM optimization yields only 10-20% total cost reduction (transcription is 70-80% of cost)

**Impact**: Low (optimization still valuable)

**Mitigation**:
1. Focus on transcription cost optimization (see task-65)
2. Use AssemblyAI ($0.0025/min) vs current Deepgram ($0.0065/min) = 62% savings
3. Batch transcription for volume discounts
4. Consider self-hosted Whisper for very high volume

---

## Appendix A: Token Estimation Methodology

### Transcript Length Assumptions

Based on industry averages:

| Media Type | Duration | Tokens | Words | Chars |
|------------|----------|--------|-------|-------|
| Short podcast | 30 min | 6,000 | 4,500 | 24,000 |
| Long podcast | 60 min | 12,000 | 9,000 | 48,000 |
| YouTube video | 15 min | 3,000 | 2,250 | 12,000 |
| Article | N/A | 1,500 | 1,125 | 6,000 |
| Tweet thread | N/A | 500 | 375 | 2,000 |

**Conversion rate**: 1 token ≈ 0.75 words ≈ 4 characters (English text)

---

### Artifact Output Length Assumptions

| Artifact | Tokens | Words | Description |
|----------|--------|-------|-------------|
| summary_short | 300 | 225 | 2-3 paragraph newsletter snippet |
| summary_detailed | 1,500 | 1,125 | 800-1,200 word comprehensive summary |
| flashcards | 800 | 600 | 10 Q&A pairs (40 words per pair) |
| notes | 1,200 | 900 | Structured bullet points with key takeaways |

---

### Input/Output Ratio

For cost calculations, we assume a **3:1 input/output ratio** (75% input tokens, 25% output tokens), which is typical for summarization tasks.

**Blended cost formula**:
```
Blended cost = (Input price × 0.75) + (Output price × 0.25)
```

Example (Gemini 2.5 Flash):
- Input: $0.30/M
- Output: $2.50/M
- Blended: (0.30 × 0.75) + (2.50 × 0.25) = **$0.85/M**

---

## Appendix B: Sources

### Official Provider Documentation

1. **Google Gemini**: https://ai.google.dev/pricing (verified Apr 22, 2026)
2. **Anthropic Claude**: https://platform.claude.com/docs/en/docs/about-claude/models (verified Apr 22, 2026)
3. **OpenAI Pricing**: https://openai.com/api/pricing/ (verified Apr 28, 2026)
4. **OpenAI Detailed Pricing**: https://developers.openai.com/api/docs/pricing (verified Apr 28, 2026)
5. **OpenAI Models / Compare Models**: https://developers.openai.com/api/docs/models and https://developers.openai.com/api/docs/models/compare (verified Apr 28, 2026)
6. **Groq**: https://groq.com/pricing (verified Apr 22, 2026)
7. **Fireworks AI**: https://fireworks.ai/pricing (verified Apr 22, 2026)
8. **Together AI**: https://together.ai/pricing (verified Apr 22, 2026)

---

### Benchmarking Platforms

1. **Artificial Analysis AI**: https://artificialanalysis.ai/models (verified Apr 22, 2026)
   - Intelligence scores
   - Speed metrics (tokens/sec)
   - Latency data (time to first token)
   - Blended pricing calculations

2. **LMSYS Chatbot Arena**: https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard
   - ELO rankings (unable to extract specific scores, platform requires interactive access)

---

### Related Research

- **Task 65**: Pricing benchmark and persona modeling (docs/research/task-65-benchmark-pricing-v1.md)
- **Project V1 Scope**: Feature definitions and artifacts (project_v1_scope.md)

---

## Appendix C: Model Changelog

**Note**: LLM providers frequently update models and pricing. OpenAI pricing/model data in this research is current as of **April 28, 2026**; non-OpenAI data remains from the April 22, 2026 snapshot unless otherwise noted.

### Recent Changes (as of research date)

1. **Claude Opus 4.7** launched (Jan 2026) - significant improvement over 4.6
2. **Gemini 3.1 series** in preview (early 2026)
3. **Llama 4 Scout** available via Groq with 10M token context (early 2026)
4. **OpenAI latest-model refresh**: `GPT-5.5`, `GPT-5.4`, `GPT-5.4 mini`, and `GPT-5.4 nano` now appear in official docs/pricing, while `GPT-5 nano` remains the cheapest paid summarization/classification candidate
5. **Mistral AI** pricing unavailable (auth wall)

### Recommendations for Maintenance

- **Review pricing monthly**: Set calendar reminder to check provider pricing pages
- **Monitor model releases**: Subscribe to provider blogs/newsletters
- **Benchmark quarterly**: Re-run quality tests every 3 months
- **Update estimates**: Adjust persona costs based on actual usage data

---

## Conclusion

### Final Recommendations

1. **MVP Launch** (Month 1-2):
   - Use **GPT-5.4 nano** for all artifacts
   - Single OpenAI-compatible integration, fast to ship
   - Native structured-output support for schema-backed artifacts
   - Cost: $0.00645 per media (all artifacts)

2. **Production Optimization** (Month 3-4):
   - summary_short: **GPT-5 nano** ($0.00017)
   - summary_detailed: **GPT-5.4** ($0.03000)
   - flashcards: **GPT-4o-mini** ($0.00078)
   - notes: **GPT-4o-mini** ($0.00110)
   - **Total: $0.03205 per media**
   - **Savings: ~68-79% vs current GPT-4 estimate**

3. **Scale Strategy** (Month 5+):
   - Implement tier-based routing (budget mix for Standard, recommended for Pro)
   - Negotiate volume discounts with providers
   - Monitor actual usage patterns and adjust

### Key Metrics to Track

1. **Cost per artifact**: Monitor actual spend per artifact type
2. **Quality scores**: User ratings on summary/flashcard quality
3. **JSON failure rate**: Track parse errors for flashcards (<1% target)
4. **Generation latency**: P50/P95 latency per artifact type (<5s target)
5. **Fallback/free-tier usage**: Monitor Google API quotas if Gemini remains enabled for experiments or failover

### Next Steps

1. ✅ **Complete research** (this document)
2. ⏳ **Validate with stakeholder** (review recommendations)
3. ⏳ **Implement OpenAI model routing** (MVP)
4. ⏳ **A/B test quality** (`GPT-5 nano` vs `GPT-5.4 nano` vs Gemini Flash vs Claude Sonnet)
5. ⏳ **Add fallback providers** (Claude + Google, if A/B tests justify them)
6. ⏳ **Monitor costs** (track actual spend vs estimates)

---

**Document generated by**: Agent de recherche backlog media-summarizer  
**Date**: 2026-04-28
**Research duration**: original ~3 hours + April 28 OpenAI pricing/model refresh
**Sources**: official provider websites, benchmarking platforms, internal task docs
