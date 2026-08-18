---
owner_decision: pending
---

# Benchmark: a consumption model for an ingestion bill that is part per-minute and part per-item

## Owner Validation

**Decision**: _(a remplir par l'owner apres relecture - texte libre decrivant la decision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes precises de correction a integrer au prochain passage)_
**Validated at**: _(date ISO a remplir par l'owner)_

---

## Recommendation

**Meter one thing: minutes. Make everything that is not transcription unlimited.**

The measured rate card (section 1) says the same thing three different ways: transcription costs
**0.00664 EUR per minute** and has no upper bound, while every other path costs between
**0.0000 and 0.011 EUR per item** and cannot run away. A YouTube transcript costs 0.0043 EUR
whether the video is 2 minutes or 3 hours. A TikTok costs 0.0009 EUR. A web article costs
nothing at all. One minute of podcast costs more than seven TikToks.

So the honest model is not "one unit that absorbs both cost shapes with fair conversion rates".
It is: **price the shape that can bankrupt you, give away the shape that cannot.**

| | |
| --- | --- |
| **The unit** | 1 minute. Internally 1 minute = 0.00664 EUR of provider budget (the measured Deepgram rate), so the monthly cap is a hard euro bound by construction. |
| **The gauge** | One number on the Account tab, the one that is already there: `212 of 300 minutes left - resets Sep 12`. Nothing else is ever counted on screen. |
| **The rule the user learns** | "Podcasts, voice notes and reels use their real length. A video with subtitles counts as one minute, whatever its length. PDFs count a minute per five pages. Articles, web pages and short clips are free." |
| **The ladder** | Reader **60 min** (3 EUR) - Mix **300 min** (5 EUR) - Audio-Heavy **720 min** (9 EUR). Prices unchanged, Mix unchanged, Audio-Heavy comes down from 900, Reader stops being zero. |
| **What is unlimited on every tier** | Articles, web pages, TikToks, Instagram photo posts, and every AI generation over a single item. |
| **What separates the tiers** | Exactly one axis - the minute allowance - which is exactly the axis the gauge shows. |
| **The safety net** | Three layers, one visible: the cap (visible, and provably below net revenue), a burst guard that queues instead of refusing (invisible), and a global provider-pool circuit breaker (owner-facing alarm). |
| **What gets deleted** | The four category counters, the per-category caps, the tier audio gating, the per-user euro ceiling, the phantom `throttle_*` actions, and two of the four mobile quota error codes. |

Four consequences worth stating up front, because they are what makes this more than a
renaming of the existing counter:

1. **The cap becomes the safety net.** 720 minutes x 0.00664 = **4.78 EUR** against **6.375 EUR**
   of net revenue on Audio-Heavy. Because *every* euro of variable cost debits the same meter -
   including LLM generations over collections - a user who spends their whole allowance still
   pays for themselves. The current euro ceiling is set *above* net revenue in all three tiers
   (3.50 vs 2.125, 6.00 vs 3.542, 10.00 vs 6.375): it certifies the loss instead of preventing it.
   Under the recommended model there is nothing left for a per-user euro ceiling to do, so it goes.
2. **Reader gets minutes.** Not as a gift: under an all-inclusive meter a Reader user does consume
   the unit (YouTube videos, PDFs, collection generations), so "0 audio minutes" is no longer
   expressible. 60 minutes costs 0.40 EUR against 2.125 EUR of net revenue, deletes the entire
   "tier audio gating" gate and the `includesAudioMinutes` mobile branch, and turns the tier
   boundary into "you ran out" - the healthiest upgrade prompt there is.
3. **Audio-Heavy's 900 minutes do not survive.** 900 x 0.00664 = 5.98 EUR against 6.375 EUR of
   net revenue: break-even before a single generation, negative after. 900 was never our number -
   it is Snipd's (section 4), and Snipd serves most transcripts from an already-transcribed shared
   library, so their marginal cost per member is near zero where ours is 0.00664 EUR/min.
   **720 minutes (12 h)** restores the same ~1.5 EUR of contribution margin the other two tiers have.
4. **The risk that actually needs new machinery is not the runaway user.** Apify's credit is a
   *shared, non-rolling* pool: 5 USD on the Free plan is 1 160 YouTube transcripts **for the whole
   platform**, and exhausting it blocks YouTube ingestion for everybody until the next cycle.
   No per-user quota can see that. That is layer 3, and it is new.

Full arithmetic in section 3.2, the candidate comparison in section 2, the defect-by-defect answer
in section 3.7.

---

## 1. What ingestion actually costs today

### 1.1 Method

Three kinds of evidence, kept separate on purpose:

- **Published rates** - fetched from the provider pricing pages on 2026-08-18, quoted with URL and date.
- **Measured code behaviour** - which provider actually runs for which platform, read from the real
  `-dev` DynamoDB tables (`processing_jobs-dev`, `media_artifacts-dev`, `user_usage_monthly-dev`) and
  from the actor inputs the workers build.
- **Measured spend** - the AWS bill via Cost Explorer for 2026-06 to 2026-08.

FX rate used everywhere: **USD to EUR 0.86259**, published 2026-08-17
(`https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR`). Every EUR figure below is a USD
list price times that rate; nothing is rounded before the last step.

### 1.2 Provider rate card

| Provider / line item | Published price | EUR | Date | Source |
| --- | --- | --- | --- | --- |
| Deepgram Nova-3 monolingual, pay-as-you-go, **list** | $0.0077 / min | **0.006642 / min** | 2026-08-18 | https://deepgram.com/pricing |
| Deepgram Nova-3 monolingual, current promotional rate | $0.0048 / min | 0.004140 / min | 2026-08-18 | https://deepgram.com/pricing |
| Deepgram Nova-3 multilingual, list | $0.0092 / min | 0.007936 / min | 2026-08-18 | https://deepgram.com/pricing |
| Deepgram speaker diarization add-on (**not enabled**) | $0.0020 / min | 0.001725 / min | 2026-08-18 | https://deepgram.com/pricing |
| Apify `starvibe/youtube-video-transcript` - the configured YouTube actor | $5.00 / 1 000 results | **0.004313 / video** | 2026-08-18 | https://apify.com/starvibe/youtube-video-transcript |
| Apify `scrape-creators/best-tiktok-transcripts-scraper` | $1.00 / 1 000 results | **0.000863 / video** | 2026-08-18 | https://apify.com/scrape-creators/best-tiktok-transcripts-scraper |
| Apify `apify/instagram-reel-scraper` - Free plan rate | $2.60 / 1 000 results | 0.002243 / reel | 2026-08-18 | https://apify.com/apify/instagram-reel-scraper |
| Apify `apify/instagram-reel-scraper` - Starter plan rate | $2.30 / 1 000 results | **0.001984 / reel** | 2026-08-18 | https://apify.com/apify/instagram-reel-scraper |
| Apify `apify/instagram-post-scraper` - Free / Starter | $2.70 / $2.30 per 1 000 | 0.002329 / 0.001984 | 2026-08-18 | https://apify.com/apify/instagram-post-scraper |
| Apify platform plans (the credit the per-result fees are drawn from) | Free $0 / $5 credit - Starter $29 - Scale $199 - Business $999 | - | 2026-08-18 | https://apify.com/pricing |
| OpenAI `gpt-5-nano` (summary_short) | $0.05 / $0.005 / $0.40 per 1M in / cached / out | - | in repo | `media_summarizer/core/services/llm_pricing.py` |
| OpenAI `gpt-5.4-nano` (detailed, notes, flashcards, quiz) | $0.20 / $0.02 / $1.25 per 1M in / cached / out | - | in repo | `media_summarizer/core/services/llm_pricing.py` |
| LlamaParse credits | $1.25 / 1 000 credits, at least 1 credit per page | at least 0.001078 / page | 2026-08-18 | https://www.llamaindex.ai/pricing |
| LlamaParse plans | Free 10 000 credits/mo (HTTP 402 when exhausted) - Starter $50 / 40 000 - Pro $500 / 400 000 | - | 2026-08-18 | https://developers.llamaindex.ai/python/cloud/llamaparse/usage_data |

Three facts about this card matter more than the individual numbers:

- **Apify per-result fees are drawn from the monthly platform credit, and unused credit does not
  roll over** - "unused usage credits are not rolled over to the next billing cycle, and they expire
  at the end of the billing cycle", and on the Free plan "you'll be blocked until the next billing
  cycle" once it is spent (https://apify.com/pricing, 2026-08-18). Apify is therefore a **fixed**
  monthly cost with a **shared** ceiling, not a per-user variable cost. The current model has no
  concept for either.
- **LlamaParse has the same shape**: 10 000 free credits a month, then a 50 USD plan. Also fixed,
  also shared, also invisible to the per-user accounting.
- **Deepgram is the only provider whose cost is unbounded per user**, because it is the only one
  billed by duration.

### 1.3 The 0.003 / 0.008 contradiction, resolved

The codebase records two different Deepgram rates, and neither is right.

| Where | Value | Verdict |
| --- | --- | --- |
| `pricing_config_service.DEFAULT_PRICING_CONFIG["providers"]["transcription"]["cost_per_minute_eur"]` | 0.003 EUR/min | **Wrong by 2.21x.** It matches no published Deepgram rate: not the list rate (0.006642), not the current promotional rate (0.004140), not the multilingual rate (0.007936). |
| `quota_enforcer._AUDIO_COST_EUR_PER_MINUTE` | 0.008 EUR/min | **Right by accident.** Its comment decomposes it as "Deepgram nova-3 (~0.003 EUR/min) plus downstream LLM processing", i.e. 0.005 EUR of LLM *per minute of audio* - which is off by roughly 20x: a 45-minute transcript generates ~0.003 EUR of LLM cost in total (section 1.5), about 0.00007 EUR/min. The two errors cancel: 0.008 lands 20 % above the true all-in figure. |

**The correct planning figure is 0.00664 EUR per transcribed minute** (Nova-3 monolingual, pay-as-you-go
list rate, $0.0077/min at USD to EUR 0.86259), with LLM cost accounted separately per generation rather
than per minute.

Why the list rate and not the 0.0048 promotional rate: the pricing page carries exactly one promotional
note, and it reads "*Limited-time promotional rates on streaming*"
(https://deepgram.com/pricing, 2026-08-18). We use pre-recorded, and a price ladder built on a
limited-time rate breaks when the promotion ends. If the promotional rate does apply to pre-recorded and
holds, everything in section 3.2 gets 38 % cheaper and the caps could be more generous - that is
upside, not a plan.

Why monolingual and not multilingual, given `DEEPGRAM_DETECT_LANGUAGE` defaults to `true`: the language
detection docs describe detection as identifying "the dominant language spoken in submitted audio" via
a model precedence chain (`Nova-3 -> Nova-2 -> Nova-1 -> Enhanced -> Base`), and nowhere state that the
flag bills at the multilingual rate (https://developers.deepgram.com/docs/language-detection,
2026-08-18). Monolingual is therefore the base case and multilingual is a **sensitivity case**: at
0.007936 EUR/min the recommended caps must shrink ~16 % (60 / 250 / 600) to hold the same margins.
This is the single figure most worth confirming against a real invoice.

Diarization would add 0.001725 EUR/min (+26 %) but is not purchased: `DEEPGRAM_DIARIZE` defaults to
`false` in `deepgram_worker`.

### 1.4 Cost per ingestion path

Provider fees only, at the rates above, at the Apify Starter tier. "Measured" means the provider chain
was read from real `processing_jobs-dev` records, not inferred from the code.

| Path | Provider chain (measured) | Cost formula | 1 min | 3 min | 25 min | 45 min |
| --- | --- | --- | --- | --- | --- | --- |
| Podcast / RSS / Spotify / audio upload | Deepgram only | 0.006642 x min | 0.0066 | 0.0199 | 0.1661 | 0.2989 |
| WhatsApp voice note | Deepgram only | 0.006642 x min | 0.0066 | 0.0199 | - | - |
| **YouTube with captions** (100 % of completed YouTube jobs in dev) | Apify `starvibe` per result | **0.004313 flat** | 0.0043 | 0.0043 | 0.0043 | 0.0043 |
| YouTube without captions (IP-blocked / caption miss) | Deepgram via resolved media URL; Apify bills nothing for an empty result | 0.006642 x min | 0.0066 | 0.0199 | 0.1661 | 0.2989 |
| Instagram reel | Apify reel-scraper per result **plus Deepgram on the reel audio** | 0.001984 + 0.006642 x min | 0.0086 | 0.0219 | - | - |
| Instagram photo post | Apify post-scraper per result | 0.001984 flat | - | - | - | - |
| TikTok | Apify transcript actor per result | **0.000863 flat** | 0.0009 | 0.0009 | - | - |
| Web article | trafilatura inside Lambda | **0.000000** | 0 | 0 | 0 | 0 |
| PDF / DOCX | LlamaParse (primary), Unstructured (fallback) | at least 0.001078 x pages | 10 pages = 0.0108 | | | |

The two shapes, side by side: **a 45-minute podcast costs 69x a 45-minute YouTube video**
(0.2989 vs 0.0043). Any model that meters both by duration is wrong by that factor in one direction;
any model that meters both per item is wrong by that factor in the other. This is the whole problem
in one line, and it is why section 2 rejects both the pure-minutes and the pure-item models.

"Failed requests do not count towards your usage" on the YouTube actor
(https://apify.com/starvibe/youtube-video-transcript, 2026-08-18) - so a caption miss costs the Apify
fee **zero**, and the double-debit of defect 3 has no cost justification whatsoever.

The Instagram reel input built by `instagram_apify_resolver.build_apify_input` is
`{"username": [url], "resultsLimit": 1}` - neither `includeTranscript` nor `includeDownloadedVideo` is
set, so the reel cost is the base result fee plus our own Deepgram call, exactly as tabulated. Those
two add-on events (billed per audio minute and per MB respectively) would change the figure if ever
enabled.

### 1.5 Cost per AI generation, measured

Generations are **not** produced at ingestion: they are user-initiated (`POST` on the artifacts
endpoint, gated separately by `check_artifact_generation_allowed`). So they are a second per-item cost
axis, and today they are invisible in the minutes story too. Measured from `media_artifacts-dev`
(`llm_usage.cost_eur`, written by `llm_pricing.estimate_llm_cost_eur` from OpenAI's own usage block):

| Artifact | Scope | Measured cost EUR | Prompt / completion tokens |
| --- | --- | --- | --- |
| `summary_short` (gpt-5-nano) | 1 source | 0.000459 - 0.000492 | 478-642 / 1 276-1 303 |
| `quiz` (gpt-5.4-nano) | 1 source | 0.001017 | 732 / 829 |

Modelled from the same price table for the cases dev has not yet exercised: a 45-minute podcast
transcript (~9 000 prompt tokens, 1 500 completion, gpt-5.4-nano) is **0.0032 EUR**; a collection
generation over the 25-source ceiling is **0.05 - 0.08 EUR**. A single-item generation is therefore
worth **less than one tenth of a minute** of transcription, and a collection generation is worth
**8 to 12 minutes**. That asymmetry is why the recommendation charges nothing for the former and
charges the latter in the same unit.

### 1.6 The fixed monthly costs nobody meters

Measured AWS spend, Cost Explorer, unblended USD including tax:

| Month | Total USD | Composition |
| --- | --- | --- |
| 2026-06 | 5.93 | SQS 2.37 - CloudWatch 2.23 - Secrets Manager 0.30 - DynamoDB 0.01 - ECR 0.01 - tax 0.99 |
| 2026-07 | 8.11 | SQS 3.30 - CloudWatch 3.00 - Secrets Manager 0.40 - tax 1.35 |
| 2026-08 (to the 18th) | 4.90 | SQS 1.74 - CloudWatch 1.73 - Secrets Manager 0.37 - ECR 0.06 - S3 0.01 - tax 0.82 |

Lambda, DynamoDB and S3 are effectively free at this volume; **SQS polling and CloudWatch logs are the
entire AWS bill**, and both are fixed rather than per-user. Two corrections to task-65 follow: its
infra baseline models an EC2 `t4g.small` at 10.55 EUR/month, which the Lambda migration (task-105)
removed; and its per-user infra allocation (0.145 EUR/user at 100 users) is roughly 2x too high.

The real fixed floor, once the free tiers are gone:

| Line | USD / month | EUR / month |
| --- | --- | --- |
| AWS (measured, ~8 USD) | 8.00 | 6.90 |
| Apify Starter (required past 1 160 YouTube transcripts) | 29.00 | 25.01 |
| LlamaParse (Free 10 000 credits = 10 000 pages covers early volume) | 0.00 | 0.00 |
| **Total** | **37.00** | **31.91** |

**Break-even is ~20 subscribers at full quota usage** (contribution margin 1.55 - 1.73 EUR/user,
section 3.2) and ~10 at the usage actually measured. But at 10 subscribers the fixed floor is
3.19 EUR/user - larger than the entire variable cost of a Mix user at cap. **At this scale the fixed
provider plan minimums, not the runaway user, are the dominant cost risk**, and the instrument the
current design spends its complexity on (a per-user euro ceiling) addresses the smaller of the two.

### 1.7 What the counters recorded versus what actually ran

The most useful measurement in this benchmark. For the dev account with real traffic, period 2026-08,
`processing_jobs-dev` versus `user_usage_monthly-dev`:

| What ran (from job records) | Deepgram minutes actually billed |
| --- | --- |
| 6 Instagram reels, provider `deepgram`, durations 1.45 / 1.77 / 2.07 / 2.15 / 2.33 / 3.95 | **13.72** |
| 4 WhatsApp voice notes, provider `deepgram`, durations 0.97 / 1.68 / 2.15 / 2.23 | **7.03** |
| 1 Spotify episode, provider `deepgram` | **4.28** |
| **Total transcribed** | **25.03 minutes** |

| What the meter recorded | Value |
| --- | --- |
| `audio_minutes_used` | **2** |
| `articles_count` | 8 |
| `youtube_count` | 8 |
| `documents_count` | 3 |
| `collection_source_units` | 7 |
| `cost_eur_estimated` | 0.113 |
| `settled_jobs` - job-level gate tokens | exactly **1** (`...:gate`) |
| `settled_jobs` - job-level settle tokens | **0** |

**8 % of the minutes that were transcribed reached the counter the user is shown, and settlement never
ran once in the month.** Real provider spend for that account was about 0.166 (Deepgram) + 0.022
(5 YouTube Apify results) + 0.002 (1 reel scrape) + 0.004 (4 LlamaParse documents) + 0.002 (5
generations) = **0.196 EUR**, against 0.113 EUR booked - the euro ceiling, the last line of defence,
undercounts by 1.7x on a *benign* mix and by ~5x on a reel-heavy one.

Also measured, and it settles the premise of the task: **every completed YouTube job used Apify**
(5 of 5, provider `apify_transcript`, actor `starvibe~youtube-video-transcript`), 2 more failed, and
none used a native-caption or yt-dlp path. task-65's assumption that 95 % of YouTube ingestions get
free captions is falsified: the correct assumption is 100 % paid.

---

## 2. Five candidate models, compared

Scored on the question the task poses: what does the user have to hold in their head to answer
"how much have I got left", and does the safety net fire before the user costs more than their tier's
net revenue. Net revenue per tier (price TTC / 1.20 VAT x 0.85 store commission):
**Reader 2.125 - Mix 3.542 - Audio-Heavy 6.375 EUR**.

| | A. Status quo, defects fixed | B. All-inclusive minutes **(recommended)** | C. Abstract credits | D. Item count + duration band | E. No counter, fair use |
| --- | --- | --- | --- | --- | --- |
| Numbers the user must hold | **4** (only 1 is shown) | **1** | 1 + a conversion table where nothing is intuitive | **1** | **0** |
| Predictable before importing? | No - 3 of the 4 walls are invisible | Yes for audio (its length), yes for the rest (free / 1) | Only with the table open | Yes | Not applicable |
| Worst mispricing of a path | 69x (YouTube vs podcast, both flat) | 1.5x (YouTube charged 1 min, costs 0.65) | 1.5x (same, by construction) | 69x | - |
| Cost-following as providers change | No - a new provider means a new counter | Yes - a new provider maps to the same unit | Yes | No | Yes |
| Safety net level | invisible per-user euro ceiling | **the visible cap itself** | the visible cap | the visible cap | invisible cost ceiling + human review |
| Worst monthly provider cost reachable on Audio-Heavy | **about 15.7 EUR = 2.5x net revenue** | **4.78 EUR = 0.75x net revenue** | 4.78 EUR | 39.9 EUR = 6.3x | 3.83 EUR ceiling, but fires on genuine users |
| Mobile cost | low (nothing changes, which is the problem) | medium (1 card, 1 paywall, 2 fewer error codes, 1 banner) | medium + a help screen nobody reads | low | lowest |
| Verdict | **Reject** | **Adopt** | Reject - B is C with the unit chosen so the table is almost never needed | Reject | Reject for audio, **adopt for text** |

### A. Status quo with the four defects fixed

**On screen:** `300 AUDIO MIN LEFT`. Nothing else, ever - the article, document and YouTube counters
exist and refuse submissions but are never displayed.

**What the user holds:** four numbers, three of which they cannot see. A Reader user who saves their
501st article is refused with "Monthly article quota reached" and no gauge anywhere in the app that
was moving towards it.

**Safety net and figures:** the per-user euro ceiling. It fails twice over. First it is set above net
revenue in all three tiers (3.50 / 6.00 / 10.00 against 2.125 / 3.542 / 6.375), so reaching it means
the loss already happened. Second, it undercounts: composing a legal Audio-Heavy month of
900 audio minutes (7.20 EUR booked, 5.98 real) plus 560 reels at the flat 0.005 EUR (2.80 EUR booked,
**9.70 EUR real**) reaches the 10 EUR ceiling at **about 15.7 EUR of real provider cost = 2.5x net
revenue** - and that is with the ceiling working exactly as designed. Fixing the four defects fixes
the undercount but not the placement: the ceiling would still have to be lowered to ~0.6x net revenue
to protect anything, at which point it becomes an invisible wall that fires on paying users with no
explanation.

**Why reject:** it is four dials with three of them hidden, which is worse than five dials shown.

### B. All-inclusive minutes - recommended

**On screen:** `212 of 300 minutes left - resets Sep 12`, one thin progress bar, one banner at 80 %.

**What the user holds:** one number, plus an intuition that is true - *audio costs time, reading is
free*. The conversion legend has four lines and lives on the paywall and one help sheet; it is not a
set of dials, because none of its lines is a separate balance. In the measured dev month, 25 of 34
units (74 %) would have come from audio duration alone, so the model the user actually forms -
"minutes of listening" - is the correct one.

**Safety net and figures:** the cap **is** the net. Because every euro of variable cost debits the
same meter, the maximum monthly provider cost a user can incur is `cap x 0.00664`:
**0.40 / 1.99 / 4.78 EUR against 2.125 / 3.542 / 6.375 EUR of net revenue** - 19 %, 56 % and 75 %.
No invisible ceiling is needed, and none can fire on a paying user, because the wall they hit is the
one they were watching.

### C. Abstract credits, the ElevenLabs shape

**On screen:** `1 780 credits left`.

**What the user holds:** one number plus a table - "a podcast minute is 7 credits, a YouTube video is
7 credits, a PDF page is 1.5 credits, a collection summary is 60 credits". ElevenLabs ships exactly
this and publishes exactly such a table (1 credit per character for TTS, **330 credits per minute**
for speech-to-text, 200 credits per sound effect - https://elevenlabs.io/pricing, 2026-08-18), which
proves a single abstract unit *can* absorb per-minute and per-item cost in one pool. It also proves
the cost: the unit means nothing on its own, so every estimate requires arithmetic.

**Safety net and figures:** identical to B by construction - the credit allowance is a euro bound.

**Why reject:** B is this model with the scale factor chosen so that the unit is already familiar
(a minute), the dominant term needs no conversion at all (audio charges its own length), and every
small term rounds to zero or one. Credits buy flexibility we do not need and spend legibility we
cannot spare.

### D. Item count with a duration band

**On screen:** `68 of 100 imports left this month - audio up to 60 min each`.

**What the user holds:** one number, and it is the most intuitive unit in the survey - Recall meters
"10 AI summaries per month" and Snipd "2 episodes per week" (section 4).

**Safety net and figures:** it does not exist. 100 imports x 60 minutes = 6 000 minutes =
**39.9 EUR = 6.3x the Audio-Heavy net revenue**. To bound cost at 0.75x net revenue the way B does,
either the allowance falls to **16 imports/month** at 60 minutes each, or the per-import ceiling falls
to **5 minutes** at 100 imports. Both destroy the product: the first makes a podcast app that allows
two podcasts a week, the second bans podcasts.

**Why reject:** the unit is uncorrelated with the only cost that can run away.

### E. No counter at all, fair use - the model that abandons counter-and-cap

**On screen:** `Import as much as you like.` Nothing else. This is Readwise (no usage limit shown
anywhere on the pricing page) and Recall ("unlimited saves and AI summaries for typical use", with a
clause reserving the right to "pause, review, or adjust a subscription" - section 4).

**What the user holds:** nothing. Perfect legibility, zero support surface, no gauge to build, no
paywall arithmetic. It is genuinely the best answer to the question the task asks - if the cost
structure allows it.

**Safety net and figures:** an invisible per-account cost ceiling plus throttle and human review. Set
it at 0.6 x net revenue (3.83 EUR on Audio-Heavy) and it fires at **576 transcribed minutes**. A
normal heavy podcast listener - two hours a day - reaches **3 600 minutes/month = 23.9 EUR = 3.75x net
revenue**, and trips that ceiling on **day 5** of every month. The people the tier is *for* are the
people it would silently throttle, every month, with no number anywhere to explain why.

**Why reject for audio, and adopt for everything else:** unlimited is unaffordable only where marginal
cost is unbounded. Articles cost 0.0000 EUR, TikToks 0.0009, Instagram posts 0.0020, single-item
generations 0.0005 - a user saving 500 articles and 200 TikToks a month costs **0.17 EUR**, well
inside every tier. So E is the right model for those paths, and B applies it: they are unlimited,
bounded only by the invisible burst guard. **The recommendation is B for transcription and E for
everything else** - which is why it can afford to have only one gauge.

---

## 3. The recommended model in detail

### 3.1 The unit and its conversion rules

**1 minute = 0.00664 EUR of provider budget.** The internal debit for any action is
`round(real_cost / 0.00664)` with a floor of zero, which yields these rules:

| Action | Real cost EUR | Exact units | **Charged** | User-facing wording |
| --- | --- | --- | --- | --- |
| Audio transcribed by Deepgram (podcast, upload, RSS, Spotify, WhatsApp voice note, reel audio, YouTube caption miss) | 0.006642 / min | 1.00 / min | **its length in minutes** | "uses its real length" |
| YouTube video with captions (Apify) | 0.004313 | 0.65 | **1** | "counts as one minute, whatever its length" |
| PDF / DOCX | 0.001078 / page | 0.162 / page | **1 per 5 pages, min 1** | "a minute per five pages" |
| AI generation over one item | 0.0005 - 0.0032 | 0.08 - 0.48 | **0** | free |
| AI generation over a collection | 0.002 - 0.08 | 0.3 - 12 | **1 per 5 sources** | "a collection summary uses a few minutes" |
| Web article / web page | 0.000000 | 0 | **0** | free |
| TikTok | 0.000863 | 0.13 | **0** | free |
| Instagram photo post | 0.001984 | 0.30 | **0** | free |
| Instagram reel scrape fee (on top of its audio) | 0.001984 | 0.30 | **0** | absorbed |

Maximum mispricing across the whole table is **1.5x** (YouTube), against 69x under any single-shape
model. Two design choices worth defending explicitly:

- **Rounding dust down to zero is deliberate.** Charging 1 unit for a TikTok would over-bill it 7.7x
  and would tax the cheapest path in the product; charging 0 costs at most 0.0009 EUR per item and is
  bounded by the burst guard, not by the meter.
- **The meter follows the provider call, not the URL.** An Instagram reel debits the minutes Deepgram
  actually transcribed because Deepgram actually ran, and the same reel would debit nothing if it were
  ever served from a cached transcript. This single sentence is what makes defects 1-4 unrepresentable
  (section 3.7).

### 3.2 The ladder, and whether current prices survive

**Verdict: the three prices survive, the three-tier shape survives, Mix survives untouched.
Audio-Heavy's 900 minutes do not, and Reader's zero does not.**

Net revenue and the cost of a *full* allowance, all-inclusive, at 0.00664 EUR/unit, with the fixed
floor of section 1.6 shared over 100 subscribers (0.32 EUR/user):

| Tier | Price TTC | Net revenue | Recommended cap | Variable cost at cap | + fixed share | **Margin at cap** | Margin % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Reader | 3 EUR | 2.125 | **60 min (1 h)** | 0.398 | 0.718 | **+1.407** | 66 % |
| Mix | 5 EUR | 3.542 | **300 min (5 h)** | 1.993 | 2.313 | **+1.229** | 35 % |
| Audio-Heavy | 9 EUR | 6.375 | **720 min (12 h)** | 4.782 | 5.102 | **+1.273** | 20 % |

Contribution margin before fixed costs: 1.73 / 1.55 / 1.59 EUR per user - deliberately flat across the
ladder, so no tier subsidises another and no tier is a trap. **Break-even is about 20 subscribers** at
full usage of every account.

Why 900 fails and 720 works:

| Audio-Heavy option | Variable cost at cap | + fixed | vs 6.375 net |
| --- | --- | --- | --- |
| 900 min, transcription only | 5.978 | 6.298 | **+0.077 (1.2 %)** - break-even |
| 900 min, incl. a realistic generation load (20 items x 4 artefacts = 0.24) | 6.218 | 6.538 | **-0.163** - loss-making |
| **720 min, all-inclusive** | 4.782 | 5.102 | **+1.273 (20 %)** |
| 900 min at the Deepgram promotional rate (0.00414) | 3.726 | 4.046 | +2.329 - only if the promotion holds |

This is the task-250 owner note, closed with a number: `audio_heavy` is loss-making at full usage, and
it is loss-making because 900 was imported from a competitor comparison in task-65, not derived from
our cost. Snipd sells 900 minutes at $6.99 (section 4) because most of its transcripts come from a
shared library of "1M+ processed episodes" - its marginal cost per member approaches zero; ours is
0.00664 EUR/min every time.

Sensitivity, for the owner to decide against:

| Scenario | Reader / Mix / Audio-Heavy caps holding ~20 %+ margin |
| --- | --- |
| Deepgram monolingual list 0.00664 (recommended basis) | 60 / 300 / 720 |
| Deepgram multilingual list 0.00794 (if `detect_language` bills multilingual) | 60 / 250 / 600 |
| Deepgram promotional 0.00414 (if it applies to pre-recorded and holds) | 90 / 450 / 1 080 |
| Diarization enabled (+0.00173) | 50 / 240 / 570 |

For calibration, the heaviest *real* account measured in section 1.7 consumed **34 units in a month**
(25 audio minutes + 8 YouTube + 3 documents, articles free) - 11 % of the Mix allowance. That is dev
traffic rather than reading behaviour, so it is a floor, not a forecast; but it says the caps are
generous where it counts and the margins above are worst-case, not expected.

**Reset policy:** monthly, on the subscription anniversary already returned as `period_end`, **no
rollover**. Otter states its minute pool has "no rollover"; ElevenLabs rolls up to 2x and caps the
balance at 3x. Rollover would let a user spend 3 x 720 = 2 160 units (14.3 EUR) inside one calendar
month, breaking the single-month euro bound that makes this model safe - cumulatively fine, but the
bound is the whole point. Keep it simple: no rollover.

### 3.3 Where the safety net sits - three layers, one visible

**Layer 1 - visible, and it is the cap itself.** 0.40 / 1.99 / 4.78 EUR of maximum variable cost
against 2.125 / 3.542 / 6.375 EUR of net revenue. Nothing invisible fires before it because nothing
invisible needs to. The per-user euro ceiling (`cost_monitoring.warning_eur` /
`cost_monitoring.hard_block_eur`) and the `cost_hard_block` refusal are **deleted**: they exist only
because the old meter could not see most of the bill.

**Layer 2 - invisible, and it queues instead of refusing.** The cap bounds the month; nothing bounds
the hour. A burst can exhaust provider rate limits, pile up SQS depth, and - for the free paths - run
LlamaParse pages or Lambda invocations without touching the meter. Sizes, set well above measured
honest usage (34 units and 25 items in the heaviest measured month):

| Guard | Value | Why it cannot bite a real user |
| --- | --- | --- |
| Units per rolling 24 h | 150 | 21 % of the largest monthly allowance in a single day |
| Free-path items per 24 h (articles, TikToks, IG posts) | 60 | 2.4x the heaviest measured month, per day |
| Documents per 24 h / pages per 24 h | 40 / 400 | 13x the heaviest measured month |
| Single-item generations per 24 h | 50 | unchanged from today's `ai_generations_per_day` |

Enforcement is the **graduated throttle that `pricing_config` has been declaring and never
implementing** (`throttle_5_imports_per_day`, `throttle_1_audio_per_hour`,
`throttle_and_contact_owner`, all read, logged, then hard-blocked anyway). It becomes real and it
becomes silent: over the guard, the submission is **accepted and queued** to the next window, the item
appears in the library with the existing processing chip, and no refusal reaches the user. Only an
account that trips the same guard on three consecutive days gets a visible message and an owner alarm.
That removes `daily_rate_limit` from the user-visible vocabulary entirely.

**Layer 3 - global, new, and the one the current design has no concept for.** Apify's credit is a
shared non-rolling pool, so exhaustion is a *platform* outage, not a user's problem:

| Pool | Capacity | Per-user cap allows | Over-subscription at 100 subscribers |
| --- | --- | --- | --- |
| Apify Free, $5 | 1 160 YouTube results | Mix: 300 | 26x |
| Apify Starter, $29 | 6 730 YouTube results | Mix: 300 | 4.5x |
| LlamaParse Free, 10 000 credits | ~10 000 pages | 400 pages/day/user | - |

Required: a monthly counter of Apify and LlamaParse spend across all users, a CloudWatch alarm at
60 % of the plan credit, and at 90 % a **degrade rather than fail** mode - new YouTube imports route
to the Deepgram path (0.00664/min, inside the user's own budget and inside the user's own visible
gauge) instead of the Apify actor, or queue to the next cycle. Sizing rule for the owner:
Apify plan at least `subscribers x expected YouTube imports x $0.005`, i.e. Starter to ~100
subscribers, Scale ($199, 46 000 results) to ~500.

### 3.4 What the user sees, and when

| Moment | What is shown |
| --- | --- |
| Account tab, always | One tile: `212` over the label `MINUTES LEFT`, a thin bar, and `RESETS Sep 12` on the neighbouring tile as today. No other counter anywhere in the app. |
| At 80 % of the allowance, once | An inline banner at the top of the inbox: `You've used 80% of this month's minutes. They reset on Sep 12.` with a `See plans` link. Not a modal, not repeated, dismissible. |
| Importing something long | Optional phase 2: a confirmation instead of a refusal - `This is 4 h 12 and will use 252 of your 300 minutes. Import anyway?` This turns today's `audio_too_long` wall into a decision the user makes with full information. |
| At the wall | **The content is never lost.** The item is saved with its title and link, tagged with a `Waiting for minutes` chip, and processes automatically at the reset or immediately on upgrade. Copy: `Saved. You're out of minutes until Sep 12 - upgrade to process it now.` Buttons: `See plans` / `OK`. |
| On a tier that cannot afford one item | The same wall, with the real numbers: `That podcast is 45 minutes and you have 12 left this month.` There is no separate "your plan has no audio" concept, because there is no tier with zero minutes. |

The wall behaviour is the largest product change in the recommendation and the one that most needs the
owner's opinion: it converts a 403 into a deferred job. It is also the reason the meter can be strict -
a cap that never destroys content can sit at 75 % of net revenue without being hostile.

### 3.5 Paywall copy - what separates Mix from Audio-Heavy, in one sentence

> **"Mix covers about five hours of listening a month; Audio-Heavy covers twelve - everything you read stays unlimited on both."**

And the legend, once, under the three cards:

> "Minutes cover audio and video we transcribe. A video with subtitles counts as one minute whatever
> its length, a PDF counts a minute per five pages, and articles, web pages and short clips are free."

### 3.6 Mobile and API consequences

| File / surface | Change |
| --- | --- |
| `GET /api/v1/entitlements/status` | Replace the single derived `minutes_remaining` (currently `audio_minutes_cap - audio_minutes_used`) with `minutes_included`, `minutes_used`, `minutes_remaining`, `resets_at`, `warning_threshold_reached`. |
| `entitlements.OFFERINGS_CONFIG` | `minutes_per_month`: 0 becomes **60**, 300 stays **300**, 900 becomes **720**. Feature bullets: drop "YouTube with captions" as a Reader differentiator (all tiers have it), add "Unlimited articles, PDFs and short clips" to all three. |
| `mobile/src/components/SubscriptionStatusCard.tsx` | Metric label `AUDIO MIN LEFT` becomes `MINUTES LEFT`; add the progress bar fed by `minutes_included`; **delete** the `includesAudioMinutes` hint block ("Reader covers text only, so it comes without audio minutes."), which becomes false. |
| `mobile/src/lib/subscriptionDisplay.ts` | **Delete** `includesAudioMinutes`. `TIER_LABELS` unchanged (Reader / Mix / Audio-Heavy survive). |
| `mobile/app/paywall.tsx` | `TIER_INFO.minutes`: `0 min audio` becomes `60 min (1 h)`, `300 min audio (5h)` becomes `300 min (5 h)`, `900 min audio (15h)` becomes `720 min (12 h)`; feature bullets per above; add the legend paragraph of section 3.5. |
| `mobile/src/lib/quotaError.ts` | Four codes become **two**: `out_of_minutes` (title "Out of minutes", offers upgrade) and `item_too_long` (title "Too long for one import", does not offer upgrade). **Delete** `daily_rate_limit` (layer 2 queues silently now) and `cost_hard_block` (the per-user euro ceiling is gone). `quotaErrorOffersUpgrade` returns true only for `out_of_minutes`. |
| `mobile/src/contexts/PurchasesContext.tsx` | `EntitlementStatus` gains the four new fields above. |
| New: inbox banner | One component, rendered at `warning_threshold_reached`, dismissible per period. |
| Media card | Reuse the existing processing chip with a `Waiting for minutes` state. |
| Backend refusal copy | There is no i18n layer in mobile and `getQuotaErrorMessage` surfaces the backend detail **verbatim**, while `AudioGateDecision.failure_message` currently formats the error code into the message. Every refusal string becomes product copy, in English, with the figures inline - no error codes in user-visible text. |

Nothing in RevenueCat changes: the three products, their prices and their entitlements are untouched.
Only the `minutes_per_month` metadata the backend serves and the copy the app renders move.

### 3.7 The four accounting defects

**1. Instagram reels transcribed by Deepgram and charged to nobody - *fixed*.** The meter is debited
by the transcription event, keyed on the Deepgram job, not on the submission's platform label. There
is no `classify_media_type`, no four categories, and therefore no `article` bucket for a reel to hide
in. `estimate_submission_cost`'s flat 0.005 EUR disappears with the per-category model; the reel's
scrape fee (0.30 units) is absorbed and its audio is charged at its real length. Measured scale of the
leak this closes: 25.03 minutes transcribed, 2 recorded, zero settlements in the month (section 1.7).

**2. The comment citing a task-250 decision that says the opposite - *meaningless*.** There is no
platform-to-category map left to justify, so there is no exemption to inherit and no comment to
correct. The rule that replaces the map is one sentence: *the meter follows the provider call, not the
URL's domain.* task-250's actual reasoning ("no Deepgram path today - nothing to gate") was correct
when written and is now falsified by measurement (six reels transcribed by Deepgram in a single dev
month); under this model the question cannot arise, because a Deepgram call is always metered
wherever it comes from.

**3. A YouTube video without captions counted twice - *meaningless*.** One meter, debited by the
provider events that actually happened. Captions hit: 1 unit (one Apify result, 0.0043 EUR).
Captions miss: the Deepgram minutes, and **zero** Apify units, because the actor bills only
successfully processed videos. The submission-time debit becomes an explicit *hold* that the
settlement replaces - precisely the gate/settle machinery task-250 already built and the artifact
worker already generalises (artifact-cost tokens sit alongside job gate tokens in `settled_jobs`
today). The double debit was two budgets pretending to be one; there is now one.

**4. Short video has no budget of its own - *meaningless*.** There are no per-category budgets to
belong to. TikTok (0.13 units) and Instagram photo posts (0.30 units) are free, exactly like
articles, and bounded by layer 2 rather than by a counter. The `articles_count` counter - which
stopped measuring articles the moment reels fell into it - is deleted rather than fixed.

**And the fifth, from the task description: the declared throttle that does not exist.** The three
`throttle_*` action strings in `cost_monitoring` are read, logged, and then hard-blocked regardless.
Under this model the graduated throttle is layer 2 and it is real: queue, retry, stay silent. The
`cost_monitoring` block itself moves from per-user (where it protected nothing) to global (where the
actual shared-pool risk lives).

### 3.8 What this deletes

Nothing is deployed and there are no users, so this is a deletion list, not a migration plan:

- `audio_minutes_used`, `articles_count`, `documents_count`, `youtube_count` become one `minutes_used`.
- `hard_caps` per category becomes one `minutes_per_month` per tier.
- `classify_media_type`, `_AUDIO_PLATFORMS`, `_YOUTUBE_PLATFORMS`, `_DOCUMENT_PLATFORMS`,
  `QUOTA_CATEGORY_*` - gone.
- `estimate_submission_cost`'s flat 0.005 EUR and `_AUDIO_COST_EUR_PER_MINUTE = 0.008` become one rate
  constant, sourced from the pricing config, 0.00664.
- `providers.transcription.cost_per_minute_eur = 0.003` becomes 0.00664, and it becomes the single
  source of truth (no second hardcoded copy in the enforcer).
- Tier audio gating (the "this tier has no audio" gate) - gone; Reader simply has fewer minutes.
- Per-user `cost_monitoring` and `cost_hard_block` - gone, replaced by global provider-pool monitoring.
- `daily_rate_limit` as a user-visible refusal - gone, replaced by silent queueing.
- `includesAudioMinutes` in mobile - gone.
- `cost_eur_estimated` - **kept**, but as observability only. It stops gating anything and becomes the
  number the owner watches to check that 0.00664 is still right.

### 3.9 Open questions for the owner

1. **Is the wall-defers-instead-of-refusing behaviour in scope?** It is what lets the cap be strict.
   If not, the cap should be looser (Audio-Heavy 800) and the refusal copy has to carry the whole
   burden.
2. **720 or 900 on Audio-Heavy?** 900 is defensible *only* on the Deepgram promotional rate. Keeping
   900 at the list rate is a deliberate choice to run the top tier at break-even as a positioning
   play.
3. **Minute top-ups?** Both Descript and Castmagic sell them ("Buy more hours anytime"). A
   1.99 EUR / 150-minute consumable costs 1.00 EUR and yields ~50 % margin, and it is a better answer
   at the wall than an upgrade for a user who overshot once. It needs a non-subscription product in
   RevenueCat and both stores, so it is a separate task.
4. **Confirm the Deepgram line on a real invoice.** The whole ladder scales linearly with one number,
   and the difference between the monolingual list rate and the multilingual list rate is 16 % of
   every cap in section 3.2.
5. **YouTube at 0.0043 EUR per result is 65 % of a whole Deepgram minute.** Worth a separate look at a
   cheaper actor or a non-Lambda egress path, since it is the single largest per-item fee we pay and
   it carries 100 % of YouTube traffic.

---

## 4. What comparable products show, and what they meter behind it

All figures fetched 2026-08-18.

| Product | Price | What the user sees | What is actually metered | Lesson |
| --- | --- | --- | --- | --- |
| **Descript** (https://www.descript.com/pricing) | Free - $16-24 Hobbyist - $24-35 Creator - $50-65 Business | "media hours / month" (60 min free, 10 h, 30 h, 40 h) **and** "AI credits" (100 one-time, 400, 800, 1 500) | Minutes of media *imported or recorded*, explicitly "regardless of whether they're transcribed"; AI credits track Underlord, Studio Sound, avatars | The closest analogue to our problem, and it meters **the input, not the vendor call** - which is exactly the recommendation. It also shows the cost of not unifying: two dials and a FAQ to explain them. |
| **Otter** (https://otter.ai/pricing) | Free - $16.99 Pro - $30/$24 Business | "minutes per user / month" (300 / 1 200 / 6 000), a per-conversation ceiling (30 / 90 / 240 min), **and** "AI Chat" counts (20 / 50 / 200) | Transcription minutes from a shared pool, "no rollover" | Today's model, one product-generation ahead: they too ended up with a second dial for AI and a per-item duration ceiling. The per-conversation ceiling is worth copying; the second dial is not. |
| **Snipd** (https://www.snipd.com/pricing) | Free - **$6.99** Premium | "900 min/month" of AI processing; Free is "2 episodes per week" | Transcription - but mostly served from a shared library of "1M+ processed episodes" | **Where our 900 came from.** Their marginal cost per member is near zero; ours is 0.00664 EUR/min. Their cap is not a benchmark for ours. |
| **ElevenLabs** (https://elevenlabs.io/pricing) | Free - $6 - $22 - $99 - $299 | **One credit balance** (10 k / 30 k / 121 k / 600 k / 1.8 M) | One pool for every product, with published rates: 1 credit/char TTS, **330 credits/min STT**, 200 credits/sound effect, 1 000 credits/min voice changer; rollover up to 2 months | Proof a single abstract unit absorbs per-minute *and* per-item cost. Also proof it needs a conversion table - and their per-item line (200 per sound effect) is exactly our YouTube case. |
| **Zapier** (https://zapier.com/pricing) | Free 100 tasks - $19.99 to $3 389 by task tier | **"Tasks"**, one number | 1 per successful action, 2 per MCP call, **0** for built-in tools; overage at 2.5x (monthly) or 1.25x (annual), hard stop at 3x the subscription | The purest single-unit precedent: heterogeneous work, one counter, and some actions deliberately priced at **zero** to keep the unit legible. That is the licence for "articles are free". |
| **Recall** (https://www.recall.it/pricing) | Free - $10 Plus - $38 Max | "10 AI summaries per month" (free), then **"Unlimited"** | Nothing visible; "unlimited saves and AI summaries for typical use" plus a clause reserving the right to "pause, review, or adjust a subscription" | The no-counter model, viable because their marginal cost is text-sized. Our free paths behave exactly like theirs; our audio path does not. |
| **Readwise / Reader** (https://readwise.io/pricing) | $5.59 Lite - $9.99 Full | **No usage limit shown anywhere** | Nothing | Flat fee is the endpoint for pure-text products. It is why the recommendation makes every text path unlimited. |
| **Castmagic** (https://www.castmagic.io/pricing) | $19 Hobby - $48 Starter - $139 Team | "Transcribed hours - **library total**" (30 / 100 / 400), "buy more hours anytime" | Minutes of transcription, as a lifetime balance rather than a monthly reset | An alternative reset policy worth knowing about: a lifetime balance removes the monthly-reset explanation entirely, at the cost of making the subscription feel like a prepaid card. |

Across the survey: **every product whose cost is per-minute meters minutes; nobody shows more than
two dials; and the products with genuinely heterogeneous costs either publish a conversion table
(ElevenLabs, Zapier) or hide everything behind fair use (Recall, Readwise).** No comparable product
shows a per-source counter, which is the strongest external support for the constraint the task
imposed.

---

## 5. Sources

Provider pricing, all fetched 2026-08-18:

- Deepgram pricing (Nova-3 mono/multilingual, add-ons, PAYG terms): https://deepgram.com/pricing
- Deepgram language detection semantics: https://developers.deepgram.com/docs/language-detection
- Apify platform plans and credit expiry: https://apify.com/pricing
- Apify YouTube transcript actor ($5.00/1 000, failures not billed): https://apify.com/starvibe/youtube-video-transcript
- Apify TikTok transcript actor ($1.00/1 000): https://apify.com/scrape-creators/best-tiktok-transcripts-scraper
- Apify Instagram reel scraper ($2.60/$2.30 per 1 000, transcript and video add-ons): https://apify.com/apify/instagram-reel-scraper
- Apify Instagram post scraper: https://apify.com/apify/instagram-post-scraper
- LlamaParse plans and credit rate: https://www.llamaindex.ai/pricing
- LlamaParse credit accounting and 402 behaviour: https://developers.llamaindex.ai/python/cloud/llamaparse/usage_data
- FX USD to EUR 0.86259 (2026-08-17): https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR

Note on a documentation gap: LlamaParse publishes the credit price and the plan allowances, but the
per-parse-mode credit cost (balanced vs premium) was not reachable on any of its live pages on
2026-08-18. The figure used here is the floor of at least 1 credit per page; a premium-mode parse
costs a multiple of it, which is why the recommended rule charges 1 unit per 5 pages rather than
per page.

Comparable products, all fetched 2026-08-18: https://www.descript.com/pricing -
https://otter.ai/pricing - https://www.snipd.com/pricing - https://elevenlabs.io/pricing -
https://zapier.com/pricing - https://www.recall.it/pricing - https://readwise.io/pricing -
https://www.castmagic.io/pricing

Internal, read for this benchmark:

- `docs/research/task-65-pricing-v1-benchmark/README.md` and its `README.owner-rejected-*.md` files
  (source of the 3/5/9 ladder, the three personas, the 95 %-free-captions assumption now falsified,
  and the EC2-based infra baseline now stale)
- `docs/research/task-250-audio-minutes-quota-accuracy/README.md` (gate/settle machinery, the
  Instagram "no Deepgram path today" reasoning, the owner note deferring the rate correction here)
- `media_summarizer/core/services/quota_enforcer.py`, `pricing_config_service.py`,
  `llm_pricing.py`, `audio_quota_gate.py`, `artifact_service.py`
- `media_summarizer/api/endpoints/entitlements.py`, `media.py`, `artifacts.py`
- `media_summarizer/workers/transcription/deepgram_worker.py`,
  `workers/youtube_ingestion_worker.py`, `workers/instagram_ingestion_worker.py`,
  `infrastructure/apify_adapter.py`, `infrastructure/resolvers/instagram_apify_resolver.py`
- `mobile/src/components/SubscriptionStatusCard.tsx`, `mobile/src/lib/subscriptionDisplay.ts`,
  `mobile/src/lib/quotaError.ts`, `mobile/app/paywall.tsx`, `mobile/src/contexts/PurchasesContext.tsx`

Measurements (read-only, `-dev` environment, 2026-08-18): `processing_jobs-dev` (28 jobs - provider
chain per platform, real transcription durations), `media_artifacts-dev` (5 artifacts - real
`llm_usage.cost_eur`), `user_usage_monthly-dev` (counters and settlement tokens per period),
`user_media-dev` (11 items - platform mix), AWS Cost Explorer 2026-06 to 2026-08. Only aggregates are
reported here; no account identifier from those tables appears in this document.
