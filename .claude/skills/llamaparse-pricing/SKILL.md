---
name: llamaparse-pricing
description: >-
  LlamaParse / LlamaCloud credit rates (parse, extract, index, storage, split, classify) and what
  they imply for this repo's document path. Read this BEFORE costing a page of document parsing,
  quoting a per-page or per-credit figure, editing `provider_pools.llamaparse`,
  `unit_conversion.document_pages_per_minute` or `cost_per_minute_eur`, adding a mode/tier to the
  LlamaParse upload, sizing the free pool, or reasoning about the 402-exhaustion fallback to
  Unstructured. Triggers on: llamaparse, llamacloud, llamaindex, credit, credits per page, cost per
  page, document_pages_per_minute, parse_mode, result_type, agentic, agentic plus, cost-effective,
  402, pool exhausted, provider_pool_guard, unstructured fallback, document parsing cost.
---

# LlamaParse pricing

The rate tables are in `references/pricing.md` — read that file for any number. **Never quote a
credits-per-page figure from memory.**

## The only conversion you need

**1,000 credits = $1.25** in both North America and Europe → **1 credit = $0.00125 = 0.001076 €**
at the ECB reference rate of 0.8611 EUR/USD (the code constant is `USD_EUR = 0.86` in
`media_summarizer/core/services/llm_pricing.py:20`; the difference is −0.13 %, ignore it).

There is no regional premium. A credit costs the same in eu-west-3 as in us-east-1.

## What this repo actually calls, and the number nobody has verified

`media_summarizer/infrastructure/resolvers/llamaparse_resolver.py`:

- `:36` — `https://api.cloud.llamaindex.ai/api/parsing`, so **the v1 API** (modes), not v2 (tiers).
  Use the v1 table.
- `:191-194` — the upload payload is **exactly** `result_type: markdown` and `language: en`. No
  mode, no model, no `target_pages`, no expiration, no retention.

Because no mode is sent, the billed rate is **the provider's v1 default, which the pricing page
does not publish**. That single unknown decides everything below, and it has one strong constraint:
the doc states that the 1-credit tier "outputs spatial text only — **no markdown**". This repo asks
for markdown. **So 1 credit/page is almost certainly not what it is being charged**, and the
cheapest rate compatible with a markdown result is **3 credits/page** (v1 "Cost-effective" /
"Parse page with LLM").

## What follows, arithmetically

The config bills a document page at `cost_per_minute_eur / document_pages_per_minute`
= `0.00664 / 5` = **0.001328 €** (`pricing_config_service.py:99,157`).

| Rate actually applied | € / page | Coverage vs. 0.001328 € billed | `monthly_capacity: 10000` really buys |
| --- | --- | --- | --- |
| 1 credit — "Parse without AI" (no markdown) | 0.001076 | **123 %** | 10 000 pages |
| **3 credits — Cost-effective / "Parse page with LLM"** | 0.003229 | **41 %** (cost is 2.4× billed) | **3 333 pages** |
| 10 credits — Agentic | 0.010764 | 12 % (8.1×) | 1 000 pages |
| 45 credits — Agentic Plus / Layout Agent | 0.048437 | 3 % (36.5×) | 222 pages |

Three consequences, in order of how much they cost if ignored:

1. **The "documents are the only correctly calibrated non-audio path, +23 % margin" claim holds
   only at 1 credit/page** — the one rate that cannot produce the markdown this repo requests. At
   the likeliest real rate the documentary path is **under-billed 2.4×**. Do not repeat the +23 %
   figure without re-deriving it from the mode actually in force.
2. **`capacity_unit: "pages"` is the wrong unit** (`pricing_config_service.py:140-146`). The
   provider meters credits; the guard counts pages —
   `provider_pool_guard.record_spend(..., units=pages)` at
   `media_summarizer/workers/document_parsing/worker.py:253-260`. At 3 credits/page the pool
   believes it has spent **a third** of what it has. `alarm_pct: 60` fires past real exhaustion and
   `stop_pct: 90` never fires at all.
3. **`stop_pct` is dead code regardless.** That same block calls `record_spend` and **never**
   `spend_allowed` — verified: `spend_allowed` appears nowhere in
   `workers/document_parsing/worker.py`. So HTTP 402 on an exhausted pool is caught as a plain
   `ParseError` and falls through to Unstructured at $0.015/page (**0.012916 €**, 9.7× the billed
   page). Exhaustion arrives 3× sooner than the config assumes, which makes that fallback the
   normal regime, not an incident.

## Rules when you touch this

- **Send the mode explicitly.** An upload that omits it buys whatever the provider decides to
  charge, and the rate can change under you without a single line of the repo changing. The mode is
  a pricing decision; it belongs in the request.
- **Meter in credits, not pages.** Any pool, alarm or quota that talks to LlamaParse has to count
  the unit the provider bills. Pages only equal credits at the no-AI rate.
- **Spreadsheets bill per sheet (1 credit/sheet), not per page.** XLSX reaches LlamaParse
  (`docs/INGESTION_WORKERS_PROVIDERS.md:484`) and `record_spend` charges it `page_count` pages —
  a different unit again.
- **Layout extraction is +3 credits/page on top of any mode.** It is not sent today. If someone
  adds it for table quality, the page rate doubles at the Cost-effective rate.
- **The .md billing rule does not apply here, and won't.** TXT/MD/RTF are routed to
  `PlainTextResolver` before LlamaParse is called (`worker.py:142`,
  `docs/INGESTION_WORKERS_PROVIDERS.md:487-492`) and report `page_count: 0`. If a future change
  sends markdown to LlamaParse, re-read the ".md" bullet — one file bills one page whatever its
  length, plus one page per extracted inline image.
- **Re-parsing the same file inside 48 h is free** (parse cache). Worth remembering before
  scoping a retry or a re-index as a cost.

## What the table does not answer

State these as unknown rather than guessing:

- **The v1 default mode**, hence the actual rate this repo pays. The decisive question. It is
  readable from a real job's usage metadata, or from the LlamaCloud usage dashboard — the owner is
  the only one who can look.
- **Whether uploaded documents count as retained storage.** Retained files bill **100 credits per
  GB per day** (0.1 per MB); files uploaded with an expiration or retention period never do. This
  repo's upload sends neither. 1 GB left retained for a month = 3 000 credits = $3.75, i.e. 30 % of
  a 10 000-credit month, for storage alone — a line item no cost model in this repo has.
- **Plan allowances.** This table gives rates, not what a plan includes. The free-plan figure in use
  (10 000 credits/month, Starter $50 for 40 K) comes from `llamaindex.ai/pricing`, a different page.

## Where the analysis lives

`docs/research/pricing-challenge/README.md` is the end-to-end pricing challenge
(`owner_decision: pending`). Its § "Ce que je n'ai pas pu vérifier" lists this very table as
unreachable (404) and its § 3.4 / § 2.2b are built on the 1-credit assumption. When the owner
resolves the default mode, that README's documentary-path arithmetic is what needs re-deriving —
correction #2 in its "Ce qui doit changer" table (wire `spend_allowed`) is unaffected and still
stands on its own.
