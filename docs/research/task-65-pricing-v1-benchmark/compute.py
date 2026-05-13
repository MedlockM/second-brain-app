"""Cost model for media-summarizer V1 pricing (5th pass, 2026-05-13).

Purpose: reproducibility. Every number in README.md must be derivable from this
file. Run with `python compute.py` to regenerate the figures quoted in the
benchmark.

CHANGES vs 4th pass:
1. Remove Typesense Cloud cost entirely (replaced by Algolia Build free tier).
2. Add 3-tier structure: Text-Only 3€ (0 min audio), Mix 5€ (300 min), Audio-Heavy 9€ (900 min).
3. Infra cost drops from 57.5 €/mo @100u to 14.5 €/mo @100u.

No rounding "for safety margin" — only explicit math.
"""

from dataclasses import dataclass

USD_EUR = 0.86  # spot 2026-05-13 (approximation)

# ---------------------------------------------------------------------------
# LLM pricing (USD per 1M tokens, OpenAI, verified via task-72 2026-04-28)
# ---------------------------------------------------------------------------
GPT5_NANO_IN = 0.05
GPT5_NANO_OUT = 0.40
GPT54_NANO_IN = 0.20
GPT54_NANO_OUT = 1.25

# ---------------------------------------------------------------------------
# Per-artifact prompt & output token budgets, PER MEDIA TYPE.
# Source: task-72 Appendix A (English transcript tokens) + French 1.25x
# penalty. Output sizes stay constant (artifact format constrained by UX).
# ---------------------------------------------------------------------------

# Transcript tokens in French for each media archetype.
# Ratio: ~200 English tokens per minute of speech * 1.25 FR penalty = 250 FR tokens/min.
MEDIA_INPUT_TOKENS = {
    "podcast_long_45min":        250 * 45,   # 11 250
    "podcast_short_20min":       250 * 20,   # 5 000
    "video_youtube_25min":       250 * 25,   # 6 250
    "short_form_1min":           250 * 1,    # 250
    "whatsapp_audio_3min":       250 * 3,    # 750
    "article_web":               1_800,      # ~1 300 words FR article
    "document_3pages":           1_800,      # similar order of magnitude
}

# Output size per artifact (tokens). Constrained by UX, not by input.
OUTPUT = {
    "summary_short":    300,
    "summary_detailed": 1_500,
    "flashcards":       800,
    "notes":            1_200,
}

# Prompt overhead (system prompt + schema + instructions). Modest, stable.
SYSTEM_OVERHEAD = 400


def llm_cost_eur(input_tokens: int, output_tokens: int,
                 price_in_usd_per_m: float, price_out_usd_per_m: float) -> float:
    in_cost = input_tokens * price_in_usd_per_m / 1_000_000
    out_cost = output_tokens * price_out_usd_per_m / 1_000_000
    return (in_cost + out_cost) * USD_EUR


def llm_cost_per_media(transcript_tokens: int) -> dict:
    """All 4 artifacts, sharing the same transcript as input.

    Returns a dict with each artifact cost + total in EUR.
    """
    inp = transcript_tokens + SYSTEM_OVERHEAD
    # task-72 owner decision: summary_short -> gpt-5-nano,
    # all other artefacts -> gpt-5.4-nano.
    short = llm_cost_eur(inp, OUTPUT["summary_short"], GPT5_NANO_IN, GPT5_NANO_OUT)
    detailed = llm_cost_eur(inp, OUTPUT["summary_detailed"], GPT54_NANO_IN, GPT54_NANO_OUT)
    flashcards = llm_cost_eur(inp, OUTPUT["flashcards"], GPT54_NANO_IN, GPT54_NANO_OUT)
    notes = llm_cost_eur(inp, OUTPUT["notes"], GPT54_NANO_IN, GPT54_NANO_OUT)
    return {
        "summary_short": short,
        "summary_detailed": detailed,
        "flashcards": flashcards,
        "notes": notes,
        "total": short + detailed + flashcards + notes,
    }


# ---------------------------------------------------------------------------
# Transcription costs (owner-fixed at 0.003 EUR/minute)
# ---------------------------------------------------------------------------
TRANSCRIPTION_EUR_PER_MIN = 0.003

# Share of YouTube / TikTok / Instagram content where free transcript/caption
# extraction works; rest falls back to paid transcription.
# Owner feedback REDO 2: 95% for YouTube.
# For TikTok/IG short-form: lower quality captions, assume 70% free retrieval.
FREE_CAPTION_RATE = {
    "youtube": 0.95,
    "tiktok_instagram": 0.70,
}


def transcription_cost_eur(duration_min: float, media_type: str) -> float:
    if media_type in ("podcast_long_45min", "podcast_short_20min",
                       "whatsapp_audio_3min"):
        return duration_min * TRANSCRIPTION_EUR_PER_MIN
    if media_type == "video_youtube_25min":
        return duration_min * TRANSCRIPTION_EUR_PER_MIN * (1 - FREE_CAPTION_RATE["youtube"])
    if media_type == "short_form_1min":
        return duration_min * TRANSCRIPTION_EUR_PER_MIN * (1 - FREE_CAPTION_RATE["tiktok_instagram"])
    return 0.0  # article, document


# ---------------------------------------------------------------------------
# Document parsing: LlamaParse free 10k credits/month + Unstructured free
# 15k pages initial. Past free tiers: LlamaParse Starter USD 50/month for
# 40k credits -> USD 0.00125/page ~= 0.00108 EUR/page.
# Owner decision task-90 ok.
# ---------------------------------------------------------------------------
LLAMAPARSE_PAID_EUR_PER_PAGE = 0.00125 * USD_EUR   # ~0.00108
DOC_AVG_PAGES = 3


def document_parsing_cost_eur(pages: int = DOC_AVG_PAGES,
                              free_tier_exhausted: bool = False) -> float:
    if not free_tier_exhausted:
        return 0.0
    return pages * LLAMAPARSE_PAID_EUR_PER_PAGE


# ---------------------------------------------------------------------------
# Infra cost per user per month, per phase.
#
# V1 architecture (5th pass, 2026-05-13):
#   - API FastAPI + 15 long-running workers (SQS pollers).
#   - Rate limiting via slowapi+Redis (embedded on VM).
#   - Lexical search: **Algolia Build free tier** (task-53.1 validated 2026-05-12).
#     Replaces Typesense Cloud (43 €/mo @100u) with 0 € (free tier 1 GB index max).
#   - Transcription: Deepgram API.
#   - Storage + queues: S3 + DynamoDB on-demand + SQS (all free-tier covered).
#
# Compute hosting: single EC2 t4g.small (ARM 2 vCPU / 2 GB RAM) running the
# API + all workers + embedded Redis via docker-compose.
# ---------------------------------------------------------------------------

# -- Compute (EC2) ----------------------------------------------------------
EC2_T4G_SMALL_ONDEMAND_USD_PER_HOUR = 0.0168
EC2_T4G_SMALL_RESERVED_1YR_USD_PER_HOUR = 0.0107

def ec2_monthly_eur(reserved: bool = False) -> float:
    rate = (EC2_T4G_SMALL_RESERVED_1YR_USD_PER_HOUR if reserved
            else EC2_T4G_SMALL_ONDEMAND_USD_PER_HOUR)
    return rate * 730 * USD_EUR  # 730 hours/month avg

# -- EBS gp3 storage --------------------------------------------------------
EBS_GP3_USD_PER_GB_MONTH = 0.08
EBS_GP3_GB = 30
EBS_MONTHLY_EUR = EBS_GP3_USD_PER_GB_MONTH * EBS_GP3_GB * USD_EUR

# -- Route53 ---------------------------------------------------------------
ROUTE53_MONTHLY_EUR = 0.50 * USD_EUR  # 1 hosted zone

# -- Algolia Build free tier (task-53.1, validated 2026-05-12) -------------
# Permanent free tier: 1 GB index max, 1M records, 10k searches/mois.
# Record size limit: 10 KB hard (requires chunking transcripts).
# At 100u launch heavy-podcast (200 docs/user, 36 KB/doc):
#   - 20k docs × 4 chunks = 80k records × ~9 KB = ~720 MB < 1 GB ✓
#   - Searches: 100u × 10 searches/mo × 4 keystrokes = ~4k/mo < 10k ✓
# Cost Y1 @100u: 0 €.
# Headroom: ~130 users before hitting 1 GB cap → migration to Algolia Grow
# (~116 €/mo @1000u Y2) or self-hosted Typesense/Meilisearch (~20-50 €/mo).
ALGOLIA_BUILD_FREE_EUR_PER_MONTH = 0.0  # free tier
ALGOLIA_GROW_Y2_ESTIMATE_EUR_PER_MONTH = 116.0  # Y2 @1000u overages

# -- Data transfer + misc CloudWatch overage --------------------------------
MISC_VARIABLE_EUR_PER_USER = 0.05

# Small fixed buffer for surprise AWS lines (ACM free, KMS, etc.)
AWS_MISC_FIXED_EUR_PER_MONTH = 1.0


def infra_fixed_eur_per_month(phase: str = "launch") -> float:
    """Sum of monthly fixed infra costs (doesn't scale with users).

    Phases:
      - 'prelaunch': Algolia Build free, EC2 on-demand.
      - 'launch':   Algolia Build free, EC2 on-demand (main phase Y1).
      - 'growth':   Algolia Grow (Y2 @1000u, overages ~116 €/mo), EC2 reserved 1-yr.
    """
    if phase == "prelaunch":
        ec2 = ec2_monthly_eur(reserved=False)
        search = ALGOLIA_BUILD_FREE_EUR_PER_MONTH
    elif phase == "launch":
        ec2 = ec2_monthly_eur(reserved=False)
        search = ALGOLIA_BUILD_FREE_EUR_PER_MONTH
    elif phase == "growth":
        ec2 = ec2_monthly_eur(reserved=True)
        search = ALGOLIA_GROW_Y2_ESTIMATE_EUR_PER_MONTH
    else:
        raise ValueError(f"Unknown phase: {phase}")
    fixed = (ec2 + EBS_MONTHLY_EUR + ROUTE53_MONTHLY_EUR
             + search + AWS_MISC_FIXED_EUR_PER_MONTH)
    return fixed


def infra_cost_per_user(n_users: int, phase: str = "launch") -> float:
    """Monthly infra cost per user (EUR) at a given user count & phase."""
    return infra_fixed_eur_per_month(phase) / n_users + MISC_VARIABLE_EUR_PER_USER


def infra_table(phase: str = "launch") -> dict:
    return {n: round(infra_cost_per_user(n, phase), 3)
            for n in (25, 50, 100, 200, 500, 1000)}


# Back-compat alias used in scenarios below — baseline is 'launch'.
INFRA_BY_USERS = infra_table("launch")


# ---------------------------------------------------------------------------
# Total cost per media (EUR)
# ---------------------------------------------------------------------------
@dataclass
class Media:
    key: str
    label: str
    duration_min: float
    audio_minutes_billed: float  # What counts against user audio quota


def media_cost_eur(m: Media, free_tier_doc: bool = False) -> dict:
    llm = llm_cost_per_media(MEDIA_INPUT_TOKENS[m.key])["total"]
    transcribe = transcription_cost_eur(m.duration_min, m.key)
    parse = document_parsing_cost_eur(DOC_AVG_PAGES,
                                      free_tier_exhausted=not free_tier_doc) if m.key == "document_3pages" else 0.0
    return {
        "llm": llm,
        "transcription": transcribe,
        "document_parsing": parse,
        "total": llm + transcribe + parse,
    }


MEDIAS = [
    Media("podcast_long_45min",   "Podcast / audio long (45 min)",     45,  45),
    Media("podcast_short_20min",  "Podcast / audio court (20 min)",    20,  20),
    Media("video_youtube_25min",  "Vidéo YouTube (25 min)",            25,  25 * 0.05),  # only 5% billed
    Media("short_form_1min",      "TikTok/Reel/Short (1 min)",         1,   1 * 0.30),   # only 30% billed
    Media("whatsapp_audio_3min",  "Audio WhatsApp (3 min)",            3,   3),
    Media("article_web",          "Article web / texte",               0,   0),
    Media("document_3pages",      "Document PDF/DOCX (3 pages)",       0,   0),
]


# ---------------------------------------------------------------------------
# Revenue side: Apple/Google + VAT
# ---------------------------------------------------------------------------
# App stores keep 15% (Small Business Program Apple / Google Play <$1M/year).
APP_STORE_COMMISSION = 0.15
VAT_FR = 0.20  # TVA service numérique B2C France


def net_revenue_eur(sticker_price_ttc: float) -> float:
    """Net cash after VAT & store commission, assuming sticker is TTC (IAP)."""
    ht = sticker_price_ttc / (1 + VAT_FR)
    after_store = ht * (1 - APP_STORE_COMMISSION)
    return after_store


# ---------------------------------------------------------------------------
# Section: unit cost tables
# ---------------------------------------------------------------------------
def print_unit_costs():
    print("=" * 76)
    print("UNIT COSTS PER MEDIA (EUR) — transcription + LLM + parsing")
    print("=" * 76)
    print(f"{'Media':<34} {'LLM':>7} {'Transcr':>8} {'Parsing':>8} {'Total':>8}")
    for m in MEDIAS:
        c = media_cost_eur(m, free_tier_doc=False)
        print(f"{m.label:<34} {c['llm']:7.4f} {c['transcription']:8.4f} "
              f"{c['document_parsing']:8.4f} {c['total']:8.4f}")
    print()
    print("Free-tier document (first months):")
    c = media_cost_eur(Media("document_3pages", "", 0, 0), free_tier_doc=True)
    print(f"  Document PDF/DOCX (3 pages), free-tier active: "
          f"LLM {c['llm']:.4f} + parsing {c['document_parsing']:.4f} = {c['total']:.4f}")
    print()


def print_llm_breakdown():
    print("=" * 76)
    print("LLM COST BREAKDOWN PER MEDIA TYPE (EUR)")
    print("=" * 76)
    print(f"{'Media':<34} {'short':>8} {'detailed':>9} {'flash':>7} {'notes':>7} {'TOTAL':>8}")
    for m in MEDIAS:
        b = llm_cost_per_media(MEDIA_INPUT_TOKENS[m.key])
        print(f"{m.label:<34} {b['summary_short']:8.4f} {b['summary_detailed']:9.4f} "
              f"{b['flashcards']:7.4f} {b['notes']:7.4f} {b['total']:8.4f}")
    print()


# ---------------------------------------------------------------------------
# Scenario helpers for 3 tiers
# ---------------------------------------------------------------------------
def tier_scenario(title: str, sticker_ttc: float,
                  quota_audio_minutes: int,
                  articles: int, documents: int, youtube: int,
                  free_tier_doc: bool = False):
    """Compute cost+margin for a given tier at different user counts.
    
    Args:
        title: scenario name
        sticker_ttc: tier price TTC (e.g. 3€, 5€, 9€)
        quota_audio_minutes: audio quota (0 for Text-Only, 300 for Mix, 900 for Audio-Heavy)
        articles: number of articles/mo
        documents: number of documents/mo
        youtube: number of YouTube videos/mo (with free captions 95%)
        free_tier_doc: whether document parsing free tier is active
    """
    net = net_revenue_eur(sticker_ttc)
    
    # Audio cost: full quota used as long podcasts (most expensive per min).
    audio_cost = quota_audio_minutes * TRANSCRIPTION_EUR_PER_MIN
    # Add LLM cost for the audio quota assuming average 45-min blocks.
    audio_llm_per_block = llm_cost_per_media(MEDIA_INPUT_TOKENS["podcast_long_45min"])["total"]
    n_audio_blocks = max(1, round(quota_audio_minutes / 45)) if quota_audio_minutes > 0 else 0
    audio_llm = n_audio_blocks * audio_llm_per_block if quota_audio_minutes > 0 else 0.0
    
    # Text media costs
    article_cost = articles * llm_cost_per_media(MEDIA_INPUT_TOKENS["article_web"])["total"]
    doc_unit = (llm_cost_per_media(MEDIA_INPUT_TOKENS["document_3pages"])["total"]
                + document_parsing_cost_eur(DOC_AVG_PAGES, free_tier_exhausted=not free_tier_doc))
    doc_cost = documents * doc_unit
    youtube_cost = youtube * media_cost_eur(Media("video_youtube_25min", "", 25, 25*0.05), free_tier_doc=False)["total"]
    
    media_cost = audio_cost + audio_llm + article_cost + doc_cost + youtube_cost
    
    print(f"\n{title} (prix TTC {sticker_ttc:.2f}€, quota audio {quota_audio_minutes} min)")
    print(f"  Net revenue: {net:.3f}€")
    print(f"  Media: {articles} articles, {documents} docs, {youtube} YouTube, audio quota {quota_audio_minutes} min")
    print(f"  Cost breakdown: audio_tr={audio_cost:.3f}, audio_llm={audio_llm:.3f}, articles={article_cost:.3f}, docs={doc_cost:.3f}, youtube={youtube_cost:.3f}")
    print(f"  {'Users':<6} {'Infra':>6} {'Media':>7} {'Total':>7} {'Margin':>7} {'Margin %':>9}")
    
    for n_users, infra in INFRA_BY_USERS.items():
        total_cost = media_cost + infra
        margin = net - total_cost
        margin_pct = 100 * margin / net if net else 0
        print(f"  {n_users:<6} {infra:>6.3f} {media_cost:>7.3f} {total_cost:>7.3f} {margin:>+7.3f} {margin_pct:>+8.1f}%")


# ---------------------------------------------------------------------------
# Tier scenarios
# ---------------------------------------------------------------------------
def print_tier_scenarios():
    print("=" * 90)
    print("TIER 1: TEXT-ONLY 3€ TTC (0 min audio, text-heavy)")
    print("=" * 90)
    # Nominal: 150 articles + 30 docs + 20 YouTube
    tier_scenario("Text-Only nominal", 3.00, 0, 150, 30, 20, free_tier_doc=True)
    # Stress: 200 articles + 40 docs + 30 YouTube
    tier_scenario("Text-Only stress", 3.00, 0, 200, 40, 30, free_tier_doc=True)
    # Max before 20% margin: ~313 articles (no docs/YouTube for simplicity)
    tier_scenario("Text-Only max (20% margin threshold)", 3.00, 0, 313, 0, 0, free_tier_doc=True)
    
    print("\n" + "=" * 90)
    print("TIER 2: MIX 5€ TTC (300 min audio)")
    print("=" * 90)
    # Nominal: 300 min + 100 articles + 15 docs + 10 YouTube
    tier_scenario("Mix nominal", 5.00, 300, 100, 15, 10, free_tier_doc=True)
    # Stress: 300 min + 200 articles + 30 docs + 20 YouTube
    tier_scenario("Mix stress", 5.00, 300, 200, 30, 20, free_tier_doc=True)
    # Alternative quotas
    tier_scenario("Mix 450 min audio", 5.00, 450, 100, 15, 10, free_tier_doc=True)
    
    print("\n" + "=" * 90)
    print("TIER 3: AUDIO-HEAVY 9€ TTC (900 min audio)")
    print("=" * 90)
    # Nominal: 900 min + 50 articles + 10 docs + 20 YouTube
    tier_scenario("Audio-Heavy nominal", 9.00, 900, 50, 10, 20, free_tier_doc=True)
    # Stress: 900 min + 100 articles + 20 docs + 30 YouTube
    tier_scenario("Audio-Heavy stress", 9.00, 900, 100, 20, 30, free_tier_doc=True)
    # Alternative quotas
    tier_scenario("Audio-Heavy 1200 min", 9.00, 1200, 50, 10, 20, free_tier_doc=True)


# ---------------------------------------------------------------------------
# Free trial coverage
# ---------------------------------------------------------------------------
def print_trial_coverage():
    print("\n" + "=" * 90)
    print("FREE TRIAL COST COVERAGE (tier Mix: 300 min audio max + text)")
    print("=" * 90)
    cases = [
        ("5 podcasts 45 min + 50 articles + 10 docs",  [("podcast_long_45min", 5), ("article_web", 50), ("document_3pages", 10)]),
        ("10 podcasts 45 min + 100 articles + 20 docs", [("podcast_long_45min", 10), ("article_web", 100), ("document_3pages", 20)]),
        ("300 min audio (hard cap) + 200 articles + 30 docs", [("podcast_long_45min", 7), ("article_web", 200), ("document_3pages", 30)]),
        ("300 min audio + 300 articles (hard cap) + 50 docs (hard cap)", [("podcast_long_45min", 7), ("article_web", 300), ("document_3pages", 50)]),
        ("100 YouTube + 200 articles + 50 docs (text-heavy, 0 audio)", [("video_youtube_25min", 100), ("article_web", 200), ("document_3pages", 50)]),
    ]
    for label, parts in cases:
        media_cost = 0.0
        for mkey, count in parts:
            m = next(x for x in MEDIAS if x.key == mkey)
            c = media_cost_eur(m, free_tier_doc=True)
            media_cost += count * c["total"]
        # Use 100-user infra amortization as baseline
        infra = INFRA_BY_USERS[100]
        total = media_cost + infra
        print(f"  {label:<60} media={media_cost:6.3f}€  +infra={infra:.3f}€  =  {total:6.3f}€")
    print()


def print_infra_table():
    print("=" * 76)
    print("INFRA COST PER USER PER MONTH (EUR) — EC2 t4g.small + Algolia Build free")
    print("=" * 76)
    for phase in ("prelaunch", "launch", "growth"):
        fixed = infra_fixed_eur_per_month(phase)
        ec2 = ec2_monthly_eur(reserved=(phase == "growth"))
        if phase in ("prelaunch", "launch"):
            search = ALGOLIA_BUILD_FREE_EUR_PER_MONTH
            search_label = "Algolia Build free (0€)"
        else:
            search = ALGOLIA_GROW_Y2_ESTIMATE_EUR_PER_MONTH
            search_label = f"Algolia Grow Y2 ({ALGOLIA_GROW_Y2_ESTIMATE_EUR_PER_MONTH:.0f}€)"
        print(f"Phase {phase}: fixed = {fixed:.2f} €/mo"
              f"  (EC2 {ec2:.2f} + EBS {EBS_MONTHLY_EUR:.2f}"
              f" + Route53 {ROUTE53_MONTHLY_EUR:.2f}"
              f" + {search_label}"
              f" + misc {AWS_MISC_FIXED_EUR_PER_MONTH:.2f})"
              f"  + {MISC_VARIABLE_EUR_PER_USER:.2f} €/user variable")
        for n, c in infra_table(phase).items():
            print(f"  {n:>4} users -> {c:.3f} €/user/month")
    print()


if __name__ == "__main__":
    print_infra_table()
    print_unit_costs()
    print_llm_breakdown()
    print_tier_scenarios()
    print_trial_coverage()
