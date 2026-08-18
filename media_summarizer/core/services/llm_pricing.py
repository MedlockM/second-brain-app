"""What a generation actually cost, from the provider's own usage block.

Observability, not enforcement: what bounds a user's spend is their minute
allowance, and a generation over a single item costs zero minutes because its LLM
cost is already inside what the item cost to ingest. This figure lands in the
monthly `cost_eur_estimated` counter so the owner can compare the consumption
model's assumptions with the real invoice.

Prices are catalogue USD per 1M tokens, converted at the same `USD_EUR` rate as
the task-65 pricing benchmark so both numbers stay comparable. A model that is
not listed falls back to the most expensive entry: overestimating is the safe
direction for a figure the owner reads to decide whether the model holds.
"""

from __future__ import annotations

from typing import Dict, Tuple

USD_EUR = 0.86

# model prefix -> (input, cached input, output) USD per 1M tokens
_MODEL_PRICES: Dict[str, Tuple[float, float, float]] = {
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-5-nano": (0.05, 0.005, 0.40),
}
_FALLBACK_PRICE = max(_MODEL_PRICES.values(), key=lambda price: price[0])


def _prices_for(model: str) -> Tuple[float, float, float]:
    normalized = (model or "").lower()
    for prefix, prices in _MODEL_PRICES.items():
        if normalized.startswith(prefix):
            return prices
    return _FALLBACK_PRICE


def estimate_llm_cost_eur(
    *,
    model: str,
    prompt_tokens: int,
    cached_tokens: int,
    completion_tokens: int,
) -> float:
    """Cost in EUR of one call, cached prompt tokens billed at their own rate.

    ``cached_tokens`` is a subset of ``prompt_tokens`` in OpenAI's usage block, so
    the uncached part is the difference — counting both in full would inflate the
    cost of exactly the requests the corpus-first prompt layout is designed to
    make cheap.
    """
    input_price, cached_price, output_price = _prices_for(model)
    billed_cached = max(0, min(cached_tokens, prompt_tokens))
    billed_fresh = max(0, prompt_tokens - billed_cached)
    usd = (
        billed_fresh * input_price
        + billed_cached * cached_price
        + max(0, completion_tokens) * output_price
    ) / 1_000_000
    return round(usd * USD_EUR, 6)
