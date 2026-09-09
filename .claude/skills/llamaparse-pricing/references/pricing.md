# LlamaParse / LlamaCloud credit pricing — verbatim rate tables

> **Provenance.** Supplied by the owner on **2026-09-09** from the LlamaIndex developer
> documentation ("Pricing | Developer Documentation"). This is the table that
> `docs/research/pricing-challenge/README.md` § "Ce que je n'ai pas pu vérifier" reports as
> unreachable (`.../cloud/llamaparse/general/pricing/index.md` returned **404**).
> Reproduced as given, minus the tab-widget artifacts. In-page links are relative to the
> LlamaIndex docs site and are kept as-is.
>
> Re-check before reusing these numbers in a decision that ships. Rates change; the owner is
> the only one who can re-read the page.

All features are priced using **credits**, which are billed per page (or minute for audio). Credits
vary by parsing mode, model, and whether files are cached.

---

## Credit Rates

| Region        | Price per 1,000 Credits |
| ------------- | ----------------------- |
| North America | $1.25                   |
| Europe        | $1.25                   |

## Parsing

### v2 API — tiers

In the v2 API, parsing uses a simplified **tier-based** system. Choose a tier and the platform
handles model selection automatically.

| Tier           | Credits per Page |
| -------------- | ---------------- |
| Fast           | 1                |
| Cost-effective | 3                |
| Agentic        | 10               |
| Agentic Plus   | 45               |

**Additional Configs:**

- **Layout extraction:** +3 credits per page (can be added to any tier)
- **Enriched forms output (Beta):** +10 credits per page containing a form
  ([details](/llamaparse/parse/examples/enriched_forms/index.md); not available on Fast)
- **Spreadsheet:** 1 credit per sheet
- **Audio:** 3 credits per minute
- **Markdown (.md):** the file itself bills as a single Fast page (1 credit) regardless of length,
  plus 1 page at the job's tier rate for each successfully extracted inline image (base64 data URI
  or remote URL; relative/local paths are never extracted). Fast-tier jobs don't extract inline
  images, so a .md file on Fast always bills exactly 1 credit.

### v1 API — modes

In the v1 API, you select a parse mode and model directly.

| Category                 | Mode                         | Model                             | Credits per Page |
| ------------------------ | ---------------------------- | --------------------------------- | ---------------- |
| **Recommended Settings** | Cost-effective               | -                                 | 3                |
|                          | Agentic                      | -                                 | 10               |
|                          | Agentic Plus                 | -                                 | 45               |
| **Presets**              | Invoice                      | -                                 | 90               |
|                          | Scientific papers            | -                                 | 90               |
|                          | Technical documentation      | -                                 | 90               |
|                          | Forms                        | -                                 | 90               |
| **Modes**                | Parse without AI             | -                                 | 1                |
|                          | Parse page with LLM          | -                                 | 3                |
|                          | Parse page with LVM          | anthropic-sonnet-3.5 (deprecated) | 60               |
|                          |                              | anthropic-sonnet-3.7              | 60               |
|                          |                              | anthropic-sonnet-4.0              | 60               |
|                          |                              | anthropic-sonnet-4.5              | 60               |
|                          |                              | anthropic-haiku-4.5 (preview)     | 30               |
|                          |                              | openai-gpt-4o-mini                | 15               |
|                          |                              | openai-gpt-4o                     | 30               |
|                          |                              | openai-gpt-4-1-nano               | 15               |
|                          |                              | openai-gpt-4-1-mini               | 20               |
|                          |                              | openai-gpt-4-1                    | 30               |
|                          |                              | openai-gpt-5-nano                 | 10               |
|                          |                              | openai-gpt-5-mini                 | 30               |
|                          |                              | openai-gpt-5                      | 150              |
|                          |                              | gemini-2.0-flash                  | 6                |
|                          |                              | gemini-2.5-flash                  | 25               |
|                          |                              | gemini-2.5-pro                    | 60               |
|                          |                              | Custom Azure Model                | 1                |
|                          |                              | Use your own API key              | 1                |
|                          | Parse page with Layout Agent | -                                 | 45               |
|                          | Parse page with Agent        | anthropic-sonnet-3.5 (deprecated) | 45               |
|                          |                              | anthropic-sonnet-3.7              | 90               |
|                          |                              | anthropic-sonnet-4.0              | 90               |
|                          |                              | anthropic-sonnet-4.5              | 90               |
|                          |                              | anthropic-haiku-4.5 (preview)     | 45               |
|                          |                              | openai-gpt-4-1-mini               | 10               |
|                          |                              | openai-gpt-4-1                    | 45               |
|                          |                              | openai-gpt-5-nano                 | 10               |
|                          |                              | openai-gpt-5-mini                 | 45               |
|                          |                              | openai-gpt-5                      | 90               |
|                          |                              | gemini-2.0-flash                  | 10               |
|                          |                              | gemini-2.5-flash                  | 10               |
|                          |                              | gemini-2.5-pro                    | 45               |
|                          | Auto Mode                    | -                                 | 3–45             |
|                          | Parse document with LLM      | -                                 | 30               |
|                          | Parse document with Agent    | anthropic-sonnet-3.7              | 90               |
|                          |                              | anthropic-sonnet-4.0              | 90               |
|                          |                              | anthropic-sonnet-4.5              | 90               |
| **Other Options**        | Structure Output             | -                                 | 3                |
| **File Type Modes**      | Spreadsheet                  | -                                 | 1 per sheet      |
|                          | Audio                        | -                                 | 3 per minute     |
| **Legacy Modes**         | Continuous Mode              | -                                 | 30               |

**Additional Configs:**

- **Layout extraction:** +3 credits per page (can be added to any mode)
- **Markdown (.md):** the file itself bills as a single page at the selected mode's rate regardless
  of length, plus 1 page at the same rate for each successfully extracted inline image (base64 data
  URI or remote URL; relative/local paths are never extracted). "Parse without AI" doesn't extract
  inline images, so a .md file there always bills exactly 1 page.

---

## Indexing

### v2

| Action          | Credits      |
| --------------- | ------------ |
| Exported page   | 2 per page   |
| Retrieval query | 1 per query  |
| Chat turn       | 100 per turn |

These charges are on top of parsing and document storage costs.

### v1

| Mode        | Credits per Page (or Sheet) |
| ----------- | --------------------------- |
| Standard    | 1                           |
| Spreadsheet | 2                           |
| Multi-modal | 2                           |

---

## Storage

Retained files — files stored without an expiration — are billed daily on each project's total
stored size:

| Item                  | Credits                         |
| --------------------- | ------------------------------- |
| Retained file storage | 100 per GB per day (0.1 per MB) |

LlamaCloud snapshots each project's retained storage once a day and charges it at the rate above.
Ephemeral files — files uploaded with an expiration or retention period, including files in
ephemeral directories — are never charged for storage.

Retained storage is also capped per project by plan tier; see the plan comparison
(`/llamaparse/general/billing#plans/index.md`) for the limits and what happens when a project
reaches them. To stop paying for a file, delete it, or upload files ephemerally when you don't need
them retained.

---

## Extraction

### v2 (Tiers)

In the v2 API, total credits per page are the extract tier plus the parse tier.

The default price includes both steps:

| Extract tier   | Extract credits/page | Default parse tier | Parse credits/page | Default total |
| -------------- | -------------------: | ------------------ | -----------------: | ------------: |
| Agentic Plus   |                   50 | Agentic            |                 10 |            60 |
| Agentic        |                   15 | Agentic            |                 10 |            25 |
| Cost-effective |                    5 | Cost-effective     |                  3 |             8 |

You can choose a different parse tier under Advanced Options. Its cost is added to the extract
tier:

| Parse tier     | Credits/page |
| -------------- | -----------: |
| Agentic Plus   |           45 |
| Agentic        |           10 |
| Cost-effective |            3 |
| Fast           |            1 |

For text files or files already parsed by LlamaParse, only the extract tier applies. Text files
(md, txt, csv, html) use 600 tokens as one page.

**Turbo:** Turbo prepares documents itself instead of running a separate Parse step, so it has no
parse tier and one all-in rate:

| Extract tier | Credits/page |
| ------------ | -----------: |
| Turbo        |           35 |

Because Turbo skips parsing, it produces no parse output and accepts no parse tier or parse
configuration — those settings are ignored if sent. It does not produce granular bounding boxes.

**Large schemas on Agentic Plus:** Agentic Plus supports schemas up to 3,200 fields. Above 200
fields, credits per page are multiplied based on schema size:

| Schema size (fields) | Multiplier |
| -------------------- | ---------: |
| 0–200                |         ×1 |
| 201–800              |         ×2 |
| 801–1,600            |         ×3 |
| 1,601–2,400          |         ×4 |
| 2,401–3,200          |         ×5 |

Schema size is the number of leaf fields in the schema you submit, not a count of what the document
returns. A table with 40 rows and 10 columns is 10 fields.

**Spreadsheet mode:** Spreadsheet mode reads an Excel or CSV workbook directly. When
`spreadsheet_mode` is on it bills at the Agentic Plus extract rate of 50 credits/page with no
separate parse tier added, and a CSV is billed as a workbook rather than under the text-file rule
above. A workbook has no fixed pages, so the billed page count is
`10 + ceil(non_empty_cells / 1000)`, independent of the number of worksheets. A workbook with
1–1,000 non-empty cells bills 11 pages (550 credits at 50 credits/page); 5,500 cells bills 16
pages. Read `metadata.usage.num_pages_billed` from the completed job for the exact count charged.

### v1 (Modes)

| Mode       | Credits per Page | Credits per Page (extract only)\* |
| ---------- | ---------------- | --------------------------------- |
| Fast       | 5                | 4                                 |
| Balanced   | 10               | 7                                 |
| Multimodal | 20               | 14                                |
| Premium    | 60               | 15                                |

*\*For text files or pre-cached parsed files.*

- For text files (md, txt, csv, html), a page is defined as the equivalent of 600 tokens.
- For text files or if the file has previously been parsed by LlamaParse, only extraction costs
  apply.
- For Multimodal mode, 6 additional credits will be charged for docx/pptx format.

---

## Split

| Mode    | Credits per Page       |
| ------- | ---------------------- |
| Default | 4 (3 for cached files) |

> If the file is already present in the LlamaParse cache, only split costs apply.

---

## Classification

| Mode       | Credits per Page |
| ---------- | ---------------- |
| Fast       | 1                |
| Multimodal | 2                |

---

## Cost Optimization Strategies

### Parse

1. **Use caching** — Parsed files are cached for 48 hours. Re-parsing the same file within that
   window is free.
2. **Choose the right tier** — Start with Cost-effective (3 credits) for initial testing. Only move
   to Agentic (10) or Agentic Plus (45) when document complexity requires it. Fast (1 credit)
   outputs spatial text only — no markdown.
3. **Use page ranges** — Parse only the pages you need instead of entire documents. Specify
   `target_pages` to avoid processing irrelevant content.

### Cross-product

4. **Leverage extract-only pricing** — If a file was previously parsed, subsequent extractions cost
   less (extract-only rates apply). Parse once, extract many times.
5. **Pre-filter with Classify** — Use Classify (1-2 credits/page) to filter documents before running
   more expensive Parse or Extract jobs.
6. **Batch strategically** — Group similar documents in a single job when possible rather than
   submitting many small requests.
