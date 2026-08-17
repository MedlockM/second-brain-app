"""Cost / call-count model for collection-scoped artifact generation (task-269).

Run with `python3 compute.py` to regenerate every figure quoted in README.md.
No network access, no API key, no LLM traffic: this is arithmetic over published
list prices and over transcript sizes measured read-only on the dev environment
(the AWS CLI commands are quoted in the README).

Prices are OpenAI list prices in USD per 1M tokens, converted to EUR with the
same spot rate as docs/research/task-65-pricing-v1-benchmark/compute.py so the
two documents stay comparable.
"""

from __future__ import annotations

import math

USD_EUR = 0.86  # same approximation as task-65 compute.py

# OpenAI list prices, USD / 1M tokens (developers.openai.com/api/docs/pricing).
# Tuple is (input, cached_input, output).
PRICES = dict(
    [
        ("gpt-5-nano", (0.05, 0.005, 0.40)),
        ("gpt-5.4-nano", (0.20, 0.02, 1.25)),
    ]
)

# Model per artifact type, mirroring the defaults hardcoded in the generators of
# media_summarizer/workers/artifact_generator.
MODEL_BY_TYPE = dict(
    [
        ("summary_short", "gpt-5-nano"),
        ("summary_detailed", "gpt-5.4-nano"),
        ("notes", "gpt-5.4-nano"),
        ("flashcards", "gpt-5.4-nano"),
        ("quiz", "gpt-5.4-nano"),
    ]
)

# Output budget per type. summary_short, summary_detailed, flashcards and notes
# come from task-65 compute.py; quiz is added here (5-10 questions, 4 options
# each, plus an explanation) because task-65 predates the quiz artifact.
OUTPUT_TOKENS = dict(
    [
        ("summary_short", 300),
        ("summary_detailed", 1_500),
        ("notes", 1_200),
        ("flashcards", 800),
        ("quiz", 1_200),
    ]
)

ALL_TYPES = list(MODEL_BY_TYPE)

# Instruction block per type (rules plus JSON schema example), estimated by
# reading the existing build_prompt bodies: 350-450 tokens.
INSTRUCTION_TOKENS = 400
# Per-source header injected in the corpus: label, title, language, media id.
SOURCE_HEADER_TOKENS = 20

# ---------------------------------------------------------------------------
# Measured read-only on the dev environment, 2026-08-17
# ---------------------------------------------------------------------------
BYTES_PER_TOKEN = 3.4  # French UTF-8 transcripts, cross-checked vs 250 FR tok/min
DEV_TRANSCRIPT_COUNT = 190
DEV_TRANSCRIPT_TOTAL_BYTES = 1_252_913
DEV_MEDIAN_REAL_BYTES = 15_715  # objects of 2 KB or more, n=82
DEV_MEAN_REAL_BYTES = 14_608
DEV_P90_REAL_BYTES = 17_041
DEV_MAX_BYTES = 41_932

MEDIAN_SOURCE_TOKENS = int(DEV_MEDIAN_REAL_BYTES / BYTES_PER_TOKEN)
MAX_SOURCE_TOKENS = int(DEV_MAX_BYTES / BYTES_PER_TOKEN)

# Model ceilings (developers.openai.com/api/docs/models/gpt-5.4-nano)
MAX_INPUT_TOKENS = 272_000
CONTEXT_WINDOW = 400_000

# Recommended caps
CAP_SOURCES = 25
CAP_CORPUS_TOKENS = 120_000


def eur(input_tokens, cached_tokens, output_tokens, model):
    price_in, price_cached, price_out = PRICES[model]
    usd = (
        input_tokens * price_in / 1_000_000
        + cached_tokens * price_cached / 1_000_000
        + output_tokens * price_out / 1_000_000
    )
    return usd * USD_EUR


# ---------------------------------------------------------------------------
# Strategies. Each returns (eur_total, llm_calls, sequential_calls).
# "sequential_calls" is the number of calls on the critical path of ONE artifact
# type: that is what has to fit in the 300 s Lambda timeout and the 180 s HTTP
# timeout of the artifact-generator worker.
# ---------------------------------------------------------------------------


def s1_stuff(n_sources, src_tokens, cache):
    """S1: one call per type over the full concatenated corpus."""
    corpus = n_sources * (src_tokens + SOURCE_HEADER_TOKENS)
    total = 0.0
    warm_models = []
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        if cache and model in warm_models:
            total += eur(INSTRUCTION_TOKENS, corpus, OUTPUT_TOKENS[artifact_type], model)
        else:
            total += eur(corpus + INSTRUCTION_TOKENS, 0, OUTPUT_TOKENS[artifact_type], model)
            warm_models.append(model)
    return total, len(ALL_TYPES), 1


def s2_map_reduce(n_sources, src_tokens, map_out=800):
    """S2: one condensation call per source on the cheap model, then one reduce per type."""
    total = 0.0
    for _ in range(n_sources):
        total += eur(src_tokens + INSTRUCTION_TOKENS, 0, map_out, "gpt-5-nano")
    reduced = n_sources * (map_out + SOURCE_HEADER_TOKENS)
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        total += eur(reduced + INSTRUCTION_TOKENS, 0, OUTPUT_TOKENS[artifact_type], model)
    return total, n_sources + len(ALL_TYPES), n_sources + 1


def s3_reuse_detailed(n_sources, src_tokens, missing):
    """S3: reduce over per-media summary_detailed artifacts, generating the missing ones."""
    total = 0.0
    for _ in range(missing):
        total += eur(
            src_tokens + INSTRUCTION_TOKENS,
            0,
            OUTPUT_TOKENS["summary_detailed"],
            MODEL_BY_TYPE["summary_detailed"],
        )
    reduced = n_sources * (OUTPUT_TOKENS["summary_detailed"] + SOURCE_HEADER_TOKENS)
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        total += eur(reduced + INSTRUCTION_TOKENS, 0, OUTPUT_TOKENS[artifact_type], model)
    return total, missing + len(ALL_TYPES), missing + 1


def s4_refine(n_sources, src_tokens):
    """S4: sequential refine, folding one source at a time into a running artifact."""
    total = 0.0
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        out = OUTPUT_TOKENS[artifact_type]
        for step in range(n_sources):
            carried = 0 if step == 0 else out
            total += eur(src_tokens + carried + INSTRUCTION_TOKENS, 0, out, model)
    return total, n_sources * len(ALL_TYPES), n_sources


def s5_rag(n_sources, src_tokens, kept=0.4):
    """S5: embed every chunk once, retrieve part of the corpus, one call per type."""
    embed_usd_per_m = 0.02  # text-embedding-3-small
    corpus = n_sources * src_tokens
    total = corpus * embed_usd_per_m / 1_000_000 * USD_EUR
    retrieved = int(corpus * kept)
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        total += eur(retrieved + INSTRUCTION_TOKENS, 0, OUTPUT_TOKENS[artifact_type], model)
    return total, len(ALL_TYPES), 1


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def main():
    src = MEDIAN_SOURCE_TOKENS
    corpus_all = int(DEV_TRANSCRIPT_TOTAL_BYTES / BYTES_PER_TOKEN)
    print("bytes per token      : %s" % BYTES_PER_TOKEN)
    print("median real source   : %d B = %d tokens" % (DEV_MEDIAN_REAL_BYTES, src))
    print("p90 real source      : %d B = %d tokens"
          % (DEV_P90_REAL_BYTES, int(DEV_P90_REAL_BYTES / BYTES_PER_TOKEN)))
    print("largest dev source   : %d B = %d tokens" % (DEV_MAX_BYTES, MAX_SOURCE_TOKENS))
    print("whole dev corpus     : %d B = %d tokens (%.2f x max input)"
          % (DEV_TRANSCRIPT_TOTAL_BYTES, corpus_all, corpus_all / MAX_INPUT_TOKENS))
    print()

    print("== corpus size vs model ceiling, median source ==")
    for n in (5, 10, 20, 25, 50, 60):
        corpus = n * (src + SOURCE_HEADER_TOKENS)
        fits = "fits" if corpus == min(corpus, MAX_INPUT_TOKENS) else "OVER"
        print("  %3d sources -> %7d tokens (%5.1f%% of max input, %s)"
              % (n, corpus, corpus / MAX_INPUT_TOKENS * 100, fits))
    worst = math.floor(MAX_INPUT_TOKENS / MAX_SOURCE_TOKENS)
    print("  worst case, every source at the dev max of %d tokens: %d sources saturate the ceiling"
          % (MAX_SOURCE_TOKENS, worst))
    print()

    print("== cost of ALL 5 types on one collection, EUR ==")
    names = ("S1 stuff", "S1+cache", "S2 m/r", "S3 warm", "S3 cold", "S4 refine", "S5 rag")
    print("sources | " + " | ".join(n.rjust(9) for n in names))
    print("-" * 90)
    for n in (5, 10, 20, 25):
        row = (
            s1_stuff(n, src, False)[0],
            s1_stuff(n, src, True)[0],
            s2_map_reduce(n, src)[0],
            s3_reuse_detailed(n, src, 0)[0],
            s3_reuse_detailed(n, src, n)[0],
            s4_refine(n, src)[0],
            s5_rag(n, src)[0],
        )
        print("%7d | " % n + " | ".join("%9.4f" % v for v in row))
    print()
    print("== LLM calls for 10 sources, all 5 types ==")
    rows = (
        ("S1 stuff", s1_stuff(10, src, False)),
        ("S2 map-reduce", s2_map_reduce(10, src)),
        ("S3 reuse warm", s3_reuse_detailed(10, src, 0)),
        ("S3 reuse cold", s3_reuse_detailed(10, src, 10)),
        ("S4 refine", s4_refine(10, src)),
        ("S5 rag", s5_rag(10, src)),
    )
    for name, result in rows:
        print("  %-16s total=%3d  sequential-per-type=%3d" % (name, result[1], result[2]))
    print()

    print("== per-type cost at the recommended cap of %d sources ==" % CAP_SOURCES)
    corpus = CAP_SOURCES * (src + SOURCE_HEADER_TOKENS)
    print("  corpus = %d tokens" % corpus)
    for artifact_type in ALL_TYPES:
        model = MODEL_BY_TYPE[artifact_type]
        cold = eur(corpus + INSTRUCTION_TOKENS, 0, OUTPUT_TOKENS[artifact_type], model)
        warm = eur(INSTRUCTION_TOKENS, corpus, OUTPUT_TOKENS[artifact_type], model)
        print("  %-17s %-13s cold=%.4f EUR  cached=%.4f EUR" % (artifact_type, model, cold, warm))
    print()

    print("== quota units, 1 unit = one source in one generation ==")
    unit_cold = eur(src, 0, 0, "gpt-5.4-nano")
    unit_cached = eur(0, src, 0, "gpt-5.4-nano")
    print("  marginal input cost of one unit: cold=%.5f EUR  cached=%.5f EUR"
          % (unit_cold, unit_cached))
    caps = (("text_only 300/mo", 300), ("mix 300/mo", 300), ("audio_heavy 900/mo", 900))
    for label, units in caps:
        print("  %-20s worst-case LLM input spend = %.3f EUR/month" % (label, units * unit_cold))
    print()
    print("  one full 5-type run on a 10-source collection = %d units" % (10 * 5))
    print("  one full 5-type run at the cap = %d units" % (CAP_SOURCES * 5))


if __name__ == "__main__":
    main()
