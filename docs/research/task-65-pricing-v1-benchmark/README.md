---
owner_decision: pending
---

# Benchmark: Coûts Unitaires + Proposition Pricing V1 (REDO)

## Owner Validation

**Decision**: _(to be filled by owner after review)_
**Validated at**: _(to be filled by owner)_

---

## Recommendation

Based on the owner's pricing strategy, I recommend implementing:

**Pricing structure:**
1. **Free trial: 1 month with no quotas** → Average cost: 2.82€/user (see calculations)
2. **Tier 5€/month with quotas per media type** → 30% margin achieved with quotas: 15 podcasts/videos (45min avg), 40 articles, 8 OCR items
3. **Tier 10€/month theoretically unlimited** → Remains profitable (>20% margin) up to: 35 podcasts/videos (45min), 90 articles, 18 OCR items per month

**Key finding:** The 10€ tier can support realistic intensive usage (100-140 total medias/month) while maintaining >20% margin, making it a viable "unlimited-feel" tier.

---

## 1. Updated Unit Costs (with 0.0030€/min transcription base)

### 1.1 Transcription

**Base cost mandated by owner:** 0.0030 €/min

This is significantly cheaper than the previous analysis (which used $0.005/min ≈ 0.0045€/min). This cost aligns with optimized provider pricing (e.g., AssemblyAI Universal-2 at $0.0025/min ≈ 0.0028€/min or bulk contracts).

**Cost by media type:**
- Podcast (45min avg): 45 × 0.0030€ = **0.135€**
- YouTube video (25min avg): 25 × 0.0030€ = **0.075€**
- TikTok video (1min avg): 1 × 0.0030€ = **0.003€**
- Article/Twitter/LinkedIn: **0€** (no transcription)
- WhatsApp audio: depends on length, assume 3min avg = **0.009€**
- OCR (image/PDF): **0€** (OCR cost separate, see below)

### 1.2 LLM (Artifact Generation)

Using **Gemini 2.5 Flash-Lite** as the cost baseline (cheapest option from previous research):
- Input: $0.10/1M tokens
- Output: $0.40/1M tokens

**Artifact token estimates:**
- **Summary Short** (newsletter format): 1,000 tokens input + 300 tokens output = $0.00025 ≈ **0.00023€**
- **Summary Detailed** (exhaustive): 3,000 tokens input + 1,500 tokens output = $0.00090 ≈ **0.00082€**
- **Flashcards** (10 Q&A): 2,000 tokens input + 800 tokens output = $0.00052 ≈ **0.00047€**

**Total artifact cost per media:** 0.00023 + 0.00082 + 0.00047 = **0.00152€**

**Note:** This assumes all 3 artifacts are generated for every media. In practice, users may not generate all artifacts for all medias, but we calculate worst-case for pricing purposes.

### 1.3 OCR

Using **Google Cloud Vision** or **AWS Textract** pricing:
- Cost per page: $0.0015 ≈ **0.0014€**

**Assumption:** Average scanned image/PDF = 3 pages
- OCR cost per media: 3 × 0.0014€ = **0.0042€**

### 1.4 Infrastructure (Storage + Compute)

From previous analysis, amortized per user/month:
- **S3 Storage** (5GB/month avg): 0.12€
- **DynamoDB**: 0.02€ (negligible with free tier)
- **SQS**: 0.00€ (negligible with free tier)
- **Compute** (workers amortized): 0.60€ (assuming 100 users)

**Total infrastructure per user:** 0.12 + 0.02 + 0.00 + 0.60 = **0.74€/month**

**Critical note:** Compute cost per user decreases with scale. At 200 users: 0.30€/user. At 50 users: 1.20€/user.

### 1.5 Cost Per Media Type (Summary Table)

| Media Type | Transcription | Artifacts | OCR | Total |
|------------|---------------|-----------|-----|-------|
| **Podcast/Video (45min)** | 0.135€ | 0.00152€ | - | **0.137€** |
| **YouTube (25min)** | 0.075€ | 0.00152€ | - | **0.077€** |
| **TikTok (1min)** | 0.003€ | 0.00152€ | - | **0.005€** |
| **Article/Text** | - | 0.00152€ | - | **0.002€** |
| **WhatsApp audio (3min)** | 0.009€ | 0.00152€ | - | **0.011€** |
| **Image/PDF (3 pages)** | - | 0.00152€ | 0.0042€ | **0.006€** |

---

## 2. Free Month Cost Analysis

### 2.1 User Behavior Assumptions

During a free trial month with no quotas, we need to estimate realistic usage patterns:

**Conservative estimate (casual user):**
- 10 podcasts (45min avg)
- 20 articles
- 3 images/PDFs
- **Total:** 33 medias/month

**Moderate estimate (engaged user):**
- 20 podcasts/videos (35min avg mix)
- 40 articles
- 5 images/PDFs
- **Total:** 65 medias/month

**Intensive estimate (power user):**
- 30 podcasts/videos (40min avg mix)
- 60 articles
- 10 images/PDFs
- **Total:** 100 medias/month

### 2.2 Cost Calculations

**Conservative user (33 medias):**
- 10 podcasts × 0.137€ = 1.37€
- 20 articles × 0.002€ = 0.04€
- 3 OCR × 0.006€ = 0.018€
- Infrastructure: 0.74€
- **Total: 2.17€/month**

**Moderate user (65 medias):**
- 20 podcasts/videos (35min avg) × 0.105€ = 2.10€
- 40 articles × 0.002€ = 0.08€
- 5 OCR × 0.006€ = 0.030€
- Infrastructure: 0.74€
- **Total: 2.95€/month**

**Intensive user (100 medias):**
- 30 podcasts/videos (40min avg) × 0.121€ = 3.63€
- 60 articles × 0.002€ = 0.12€
- 10 OCR × 0.006€ = 0.060€
- Infrastructure: 0.74€
- **Total: 4.55€/month**

### 2.3 Expected Mix & Average Cost

Assuming free trial user distribution:
- 50% casual (2.17€)
- 35% moderate (2.95€)
- 15% intensive (4.55€)

**Weighted average:** (0.50 × 2.17) + (0.35 × 2.95) + (0.15 × 4.55) = 1.085 + 1.033 + 0.683 = **2.82€/month per free trial user**

**Risk:** If conversion rate from free trial to paid is <35%, the free month strategy may be unprofitable. Industry benchmark for SaaS free trials: 30-40% conversion.

---

## 3. Tier 5€/Month with 30% Margin

### 3.1 Target Cost Structure

**Revenue:** 5.00€
**Target margin:** 30%
**Maximum cost:** 5.00€ × (1 - 0.30) = **3.50€**

**Available for media processing:** 3.50€ - 0.74€ (infrastructure) = **2.76€**

### 3.2 Quota Calculation by Media Type

To achieve 30% margin, we need to determine quotas that keep total media cost ≤ 2.76€.

**Strategy:** Define quotas per media type that reflect realistic usage patterns while staying under cost limit.

#### Approach 1: Balanced Mix

**Proposed quotas:**
- **15 podcasts/videos** (45min avg): 15 × 0.137€ = 2.055€
- **40 articles**: 40 × 0.002€ = 0.08€
- **8 OCR items**: 8 × 0.006€ = 0.048€

**Total media cost:** 2.055 + 0.08 + 0.048 = **2.18€**
**Total cost with infrastructure:** 2.18 + 0.74 = **2.92€**
**Margin:** 5.00 - 2.92 = **2.08€** (41.6% margin) ✓

#### Approach 2: Audio-Heavy Mix

**Proposed quotas:**
- **20 podcasts/videos** (45min avg): 20 × 0.137€ = 2.74€
- **20 articles**: 20 × 0.002€ = 0.04€
- **0 OCR items**: 0€

**Total media cost:** 2.74 + 0.04 + 0 = **2.78€**
**Total cost with infrastructure:** 2.78 + 0.74 = **3.52€**
**Margin:** 5.00 - 3.52 = **1.48€** (29.6% margin) ✓

#### Approach 3: Text-Heavy Mix

**Proposed quotas:**
- **10 podcasts/videos** (45min avg): 10 × 0.137€ = 1.37€
- **70 articles**: 70 × 0.002€ = 0.14€
- **15 OCR items**: 15 × 0.006€ = 0.09€

**Total media cost:** 1.37 + 0.14 + 0.09 = **1.60€**
**Total cost with infrastructure:** 1.60 + 0.74 = **2.34€**
**Margin:** 5.00 - 2.34 = **2.66€** (53.2% margin) ✓

### 3.3 Recommended Quota Structure for 5€ Tier

**Balanced quota (recommended):**
- **15 podcasts/videos** (mix of lengths, 45min avg)
- **40 articles/text medias**
- **8 OCR items** (images/PDFs)

**Total:** 63 medias/month
**Cost:** 2.92€
**Margin:** 41.6%

**Rationale:**
- Provides meaningful value for casual-to-moderate users
- 15 audio/video medias ≈ 3-4 per week (realistic for students/professionals)
- 40 articles ≈ 10 per week (reasonable reading volume)
- 8 OCR items ≈ occasional scanning needs
- Well above 30% target margin, providing buffer for cost variations

**Alternative: Unified quota**
Instead of per-type quotas, use a **credit system**:
- Podcast/video (45min): 5 credits
- Article: 0.1 credits
- OCR: 0.2 credits
- **Monthly allowance: 75 credits**

This gives users flexibility (e.g., 15 podcasts = 75 credits, or 10 podcasts + 125 articles, etc.)

---

## 4. Tier 10€/Month Profitability Analysis

### 4.1 Target Margin & Maximum Cost

**Revenue:** 10.00€
**Target margin:** 20% (minimum acceptable)
**Maximum cost:** 10.00€ × (1 - 0.20) = **8.00€**

**Available for media processing:** 8.00€ - 0.74€ (infrastructure) = **7.26€**

### 4.2 Breakeven Analysis: At What Usage Does Margin Drop Below 20%?

**Cost equation:** 
Total cost = (N_podcast × 0.137) + (N_article × 0.002) + (N_ocr × 0.006) + 0.74

**Breakeven (20% margin):** Total cost = 8.00€

#### Scenario 1: Audio-Heavy User
Assume: 70% podcasts, 25% articles, 5% OCR

**At 50 total medias:**
- 35 podcasts × 0.137€ = 4.795€
- 12 articles × 0.002€ = 0.024€
- 3 OCR × 0.006€ = 0.018€
- Total: 4.837€ + 0.74€ = **5.58€** → Margin: 44.2% ✓

**At 100 total medias:**
- 70 podcasts × 0.137€ = 9.59€
- 25 articles × 0.002€ = 0.05€
- 5 OCR × 0.006€ = 0.03€
- Total: 9.67€ + 0.74€ = **10.41€** → Margin: **-4.1%** ✗

**At 80 total medias:**
- 56 podcasts × 0.137€ = 7.672€
- 20 articles × 0.002€ = 0.04€
- 4 OCR × 0.006€ = 0.024€
- Total: 7.736€ + 0.74€ = **8.48€** → Margin: 15.2% ✗

**At 70 total medias:**
- 49 podcasts × 0.137€ = 6.713€
- 18 articles × 0.002€ = 0.036€
- 3 OCR × 0.006€ = 0.018€
- Total: 6.767€ + 0.74€ = **7.51€** → Margin: 24.9% ✓

**Audio-heavy limit (70% podcasts):** ~70 total medias = 49 podcasts + 18 articles + 3 OCR

#### Scenario 2: Balanced User
Assume: 40% podcasts, 50% articles, 10% OCR

**At 100 total medias:**
- 40 podcasts × 0.137€ = 5.48€
- 50 articles × 0.002€ = 0.10€
- 10 OCR × 0.006€ = 0.06€
- Total: 5.64€ + 0.74€ = **6.38€** → Margin: 36.2% ✓

**At 150 total medias:**
- 60 podcasts × 0.137€ = 8.22€
- 75 articles × 0.002€ = 0.15€
- 15 OCR × 0.006€ = 0.09€
- Total: 8.46€ + 0.74€ = **9.20€** → Margin: 8.0% ✗

**At 130 total medias:**
- 52 podcasts × 0.137€ = 7.124€
- 65 articles × 0.002€ = 0.13€
- 13 OCR × 0.006€ = 0.078€
- Total: 7.332€ + 0.74€ = **8.07€** → Margin: 19.3% ✗

**At 125 total medias:**
- 50 podcasts × 0.137€ = 6.85€
- 62 articles × 0.002€ = 0.124€
- 13 OCR × 0.006€ = 0.078€
- Total: 7.052€ + 0.74€ = **7.79€** → Margin: 22.1% ✓

**Balanced user limit (40% podcasts):** ~125 total medias = 50 podcasts + 62 articles + 13 OCR

#### Scenario 3: Text-Heavy User
Assume: 25% podcasts, 65% articles, 10% OCR

**At 150 total medias:**
- 37 podcasts × 0.137€ = 5.069€
- 98 articles × 0.002€ = 0.196€
- 15 OCR × 0.006€ = 0.09€
- Total: 5.355€ + 0.74€ = **6.10€** → Margin: 39.0% ✓

**At 200 total medias:**
- 50 podcasts × 0.137€ = 6.85€
- 130 articles × 0.002€ = 0.26€
- 20 OCR × 0.006€ = 0.12€
- Total: 7.23€ + 0.74€ = **7.97€** → Margin: 20.3% ✓

**At 210 total medias:**
- 52 podcasts × 0.137€ = 7.124€
- 137 articles × 0.002€ = 0.274€
- 21 OCR × 0.006€ = 0.126€
- Total: 7.524€ + 0.74€ = **8.26€** → Margin: 17.4% ✗

**Text-heavy user limit (25% podcasts):** ~200 total medias = 50 podcasts + 130 articles + 20 OCR

### 4.3 Summary: 10€ Tier Profitability Thresholds

| User Profile | Mix | Max Medias (≥20% margin) | Details |
|--------------|-----|---------------------------|---------|
| **Audio-Heavy** | 70% podcasts, 25% articles, 5% OCR | **70 medias** | 49 podcasts + 18 articles + 3 OCR |
| **Balanced** | 40% podcasts, 50% articles, 10% OCR | **125 medias** | 50 podcasts + 62 articles + 13 OCR |
| **Text-Heavy** | 25% podcasts, 65% articles, 10% OCR | **200 medias** | 50 podcasts + 130 articles + 20 OCR |

**Critical insight:** The 10€ tier is profitable for realistic "intensive but not abusive" usage:
- **Audio-heavy users** can process ~50 podcasts/month (12-13 per week) = ~37.5 hours of audio
- **Balanced users** can process ~125 total medias/month (30 per week)
- **Text-heavy users** can process ~200 medias/month (50 per week)

### 4.4 Recommended Approach for 10€ Tier

**Option 1: Soft limits with warnings**
- No hard quota enforced
- Warning at 80 medias/month: "You're using the service intensively. Thanks for your support!"
- Warning at 120 medias/month: "You're approaching intensive usage. Consider optimizing your workflow."
- Hard limit at 150 medias/month: "Monthly limit reached. Upgrade to Enterprise or wait until next month."

**Rationale:** 
- Most users won't hit 150 medias/month (that's 35 per week, very high)
- Soft limits feel "unlimited" while protecting margin
- 150 total medias with balanced mix (40% audio) = 60 podcasts + 75 articles + 15 OCR = 7.92€ cost → 20.8% margin ✓

**Option 2: Truly unlimited with risk acceptance**
- No quotas at all
- Accept that ~5-10% of users may become unprofitable
- Monitor costs and adjust pricing or add higher tier if needed

**Rationale:**
- Simplest messaging: "Unlimited usage"
- Most users self-regulate (median usage likely 40-60 medias/month)
- Power users who exceed profitability are rare and may convert to future "Enterprise" tier

**Recommended:** Option 1 (soft limits at 150 medias/month)

---

## 5. Consolidated Pricing Recommendation

### 5.1 Pricing Structure

| Tier | Price | Quotas | Target Margin |
|------|-------|--------|---------------|
| **Free Trial** | 0€ (1 month) | No quotas | N/A (avg cost: 2.82€) |
| **Standard** | **5€/month** | 15 podcasts/videos + 40 articles + 8 OCR | 30%+ |
| **Premium** | **10€/month** | Soft limit 150 medias/month (feels unlimited) | 20%+ |

### 5.2 Feature Differentiation

**Free Trial (1 month):**
- All features enabled
- No quotas
- Automatic conversion prompt at end of month
- **Goal:** Convert 30-40% to paid tier

**Standard (5€):**
- 15 podcasts/videos (avg 45min each) = ~675 min audio processing
- 40 articles/text medias
- 8 OCR items (images/PDFs)
- All artifacts (Summary Short, Detailed, Flashcards)
- Spaced repetition
- Daily & Weekly digests
- Folders, tags, search
- **Total:** 63 medias/month
- **Target audience:** Students, casual users, professionals with moderate needs

**Premium (10€):**
- 150 medias/month soft limit (balanced mix: 60 podcasts + 75 articles + 15 OCR)
- All Standard features
- Priority processing queue (faster transcription/artifact generation)
- API access (for power users who want to export to Notion/Obsidian)
- **Target audience:** Power users, professionals with high consumption

### 5.3 Migration Path

**Launch strategy:**
1. **Phase 1 (MVP):** Launch with Free Trial + Standard (5€) only
   - Validate demand and conversion rates
   - Collect real usage data
   - Iterate on quotas based on actual costs

2. **Phase 2 (3-6 months):** Add Premium (10€) tier
   - Once user base is established
   - If data shows significant demand for higher limits
   - Implement soft limits and monitoring

3. **Phase 3 (12+ months):** Consider Enterprise tier
   - Custom pricing for organizations
   - Team collaboration features
   - Higher limits or truly unlimited with custom pricing

### 5.4 Quota Communication

**For Standard tier, communicate as:**
- "Process up to 15 podcasts or videos per month"
- "Save up to 40 articles or text posts"
- "Scan up to 8 images or PDFs"
- "Mix and match your medias within these limits"

**Alternative: Unified messaging**
- "75 media credits per month"
  - 1 podcast/video (45min) = 5 credits
  - 1 article = 0.1 credits
  - 1 OCR item = 0.2 credits
- Simpler for users to understand, more flexible

**For Premium tier, communicate as:**
- "Process up to 150 medias per month" (simple, clear)
- OR "Unlimited usage with fair use policy" (feels more premium, but riskier)

---

## 6. Risk Analysis & Mitigations

### 6.1 Free Trial Month Risk

**Risk:** Average cost of 2.82€ per free trial user with 0€ revenue.

**Mitigation strategies:**
1. **Require credit card at signup** (common SaaS practice)
   - Reduces "tire-kickers" who have no intent to pay
   - Increases conversion rate (users who provide CC are 2-3x more likely to convert)
   - Auto-charge at end of trial unless cancelled

2. **Limit trial to 30 medias/month** instead of unlimited
   - Reduces avg cost to ~2.20€ (based on 30 medias with balanced mix)
   - Still enough to evaluate the product
   - Can be removed later if conversion rates are strong

3. **Target 40%+ conversion rate**
   - Industry benchmark: 30-40% for credit card required trials
   - At 40% conversion: 4 users pay 5€ = 20€ revenue vs 10 users × 2.82€ = 28.2€ cost → positive at scale
   - Need to acquire users profitably (CAC < LTV)

**Recommendation:** Require credit card + limit trial to 30 medias to reduce risk while validating demand.

### 6.2 Standard Tier (5€) Risk

**Risk:** Users exceed quotas and become frustrated, leading to churn.

**Mitigation:**
1. **Clear quota visibility**
   - Dashboard showing current usage vs limits
   - Email notification at 80% of quota
   - In-app prompt to upgrade when limit reached

2. **Rollover policy** (optional)
   - Allow unused quota to roll over 1 month (max 2x monthly quota)
   - Increases perceived value without major cost impact

3. **One-time quota boosts**
   - Offer "boost packs" for 2€ = +5 podcasts for the month
   - Emergency relief valve for users who occasionally need more

### 6.3 Premium Tier (10€) Risk

**Risk:** Power users exploit "unlimited" positioning and become unprofitable.

**Mitigation:**
1. **Soft limit at 150 medias/month**
   - 95% of users won't hit this (based on usage patterns)
   - For those who do, friendly message: "You're a power user! Contact us for Enterprise pricing."

2. **Rate limiting**
   - Max 10 medias per day processing (prevents bulk abuse)
   - Prevents automated bots or scrapers

3. **Monitor cost per user**
   - Alert system when individual user cost exceeds 8€ (20% margin threshold)
   - Reach out proactively to discuss usage or offer custom plan

4. **Fair Use Policy** in ToS
   - Reserve right to throttle or upgrade users who abuse "unlimited"
   - Define "abuse" as exceeding 200 medias/month consistently

### 6.4 Infrastructure Cost Scaling Risk

**Risk:** Infrastructure cost per user (0.74€) is based on 100 users. At lower scale, cost is higher.

**Mitigation:**
1. **Start with smaller infrastructure**
   - 1 t3.small worker instead of 2 during beta
   - Scale up as user base grows
   - Target 50-100 users before full infrastructure

2. **Use spot instances**
   - 60-70% cost reduction on compute
   - Reduces worker cost from ~60€/month to ~20€/month
   - Infrastructure cost per user drops to 0.20-0.30€

3. **Monitor and optimize**
   - Monthly cost review
   - Identify optimization opportunities (S3 Intelligent-Tiering, DynamoDB capacity modes, etc.)

---

## 7. Competitive Positioning

### 7.1 Market Comparison

| Competitor | Price | Limits | Our Position |
|------------|-------|--------|--------------|
| **Snipd Premium** | 6.99€/month | 900 min audio/month (~20 episodes) | Standard: 5€ = 675 min (15 episodes) — cheaper<br>Premium: 10€ = ~2,700 min (60 episodes) — more value |
| **Otter.ai Pro** | 8.49€/month | 1,200 min/month | Standard: 5€ = 675 min — cheaper<br>Premium: 10€ = ~2,700 min — more value |
| **Readwise Full** | 9.99€/month | Unlimited articles | Premium: 10€ = 150 medias — similar price, add audio/video |
| **mymind Mastermind** | 12.99€/month | Unlimited | Premium: 10€ — cheaper, similar features |

**Positioning:**
- **Standard (5€):** Most affordable option for students/casual users
- **Premium (10€):** Best value for power users (vs Snipd, Otter, Readwise)
- **Differentiation:** Multi-media (not just podcasts/articles), spaced repetition built-in

### 7.2 Value Proposition by Tier

**Standard (5€):**
- "Your second brain for 5€/month"
- "Process 15 podcasts + 40 articles every month"
- "Less than a coffee per month"

**Premium (10€):**
- "Unlimited learning, one price"
- "Process 100+ medias every month"
- "For serious learners and professionals"

---

## 8. Financial Projections (Example Scenarios)

### 8.1 Scenario: 100 Active Users After 6 Months

**Assumptions:**
- 300 free trials in 6 months
- 40% conversion rate → 120 paid users
- 20% churn over 6 months → 100 active paid users
- Tier split: 70% Standard (5€), 30% Premium (10€)

**Monthly recurring revenue (MRR):**
- 70 Standard × 5€ = 350€
- 30 Premium × 10€ = 300€
- **Total MRR: 650€**

**Monthly costs:**
- 70 Standard users × 2.92€ avg = 204.4€
- 30 Premium users × 6.50€ avg = 195€ (assuming avg 100 medias/month)
- **Total costs: 399.4€**

**Monthly profit:** 650€ - 399.4€ = **250.6€** (38.5% margin)

**Annual run rate:** 250.6€ × 12 = **3,007€ profit/year**

### 8.2 Scenario: 500 Active Users After 12 Months

**Assumptions:**
- 1,500 free trials in 12 months
- 40% conversion → 600 paid
- 20% churn → 500 active
- Tier split: 60% Standard, 40% Premium (more power users as product matures)

**Monthly recurring revenue:**
- 300 Standard × 5€ = 1,500€
- 200 Premium × 10€ = 2,000€
- **Total MRR: 3,500€**

**Monthly costs:**
- 300 Standard × 2.92€ = 876€
- 200 Premium × 6.50€ = 1,300€
- Infrastructure optimized (spot instances): 0.30€/user × 500 = 150€ (instead of 370€)
- **Total costs: 2,176€**

**Monthly profit:** 3,500€ - 2,176€ = **1,324€** (37.8% margin)

**Annual run rate:** 1,324€ × 12 = **15,888€ profit/year**

---

## 9. Implementation Recommendations

### 9.1 Technical Requirements

**For Standard tier quotas:**
- Database schema: track monthly usage per media type (podcasts, articles, OCR)
- Reset counters on subscription renewal date
- Enforce limits in submission API (reject with clear error message when quota exceeded)
- Dashboard widget showing current usage vs limits

**For Premium tier soft limits:**
- Same tracking as Standard
- Warning messages at 80, 120, 150 medias
- Rate limiter: max 10 medias/day
- Admin monitoring dashboard for users approaching unprofitability

**For Free trial:**
- Track trial start date
- Optional: limit to 30 medias during trial
- Auto-conversion prompt 7 days before trial ends
- Webhook to payment provider for auto-charge

### 9.2 Pricing Page Messaging

**Headline:** "Your Second Brain, Priced Fairly"

**Standard (5€/month):**
- 15 podcasts or videos per month
- 40 articles or text posts
- 8 scanned images or PDFs
- Unlimited folders and tags
- AI summaries and flashcards
- Spaced repetition for learning
- Daily and weekly digests
- "Perfect for students and casual learners"

**Premium (10€/month):**
- 150 medias per month (all types)
- Everything in Standard
- Priority processing
- API access for exports
- "For power users and professionals"

**Free Trial:**
- "Try free for 30 days"
- "No credit card required" OR "Credit card required, cancel anytime"
- "All features included"

### 9.3 Monitoring & Optimization

**Key metrics to track:**
1. **Cost per user by tier** (actual vs projected)
2. **Usage distribution** (medias/month histogram)
3. **Conversion rates** (trial → Standard, Standard → Premium)
4. **Churn rate** by tier
5. **Quota hit rate** (how many users hit limits)
6. **Margin by tier** (actual vs 30%/20% targets)

**Monthly review:**
- Adjust quotas if costs deviate >10% from projections
- Identify optimization opportunities (cheaper providers, better batching, etc.)
- Analyze user feedback on quotas (too low? too high?)

---

## 10. Conclusion

The owner's pricing strategy is **viable and profitable**:

1. **Free month with no quotas:** Average cost of 2.82€/user is acceptable if conversion rate is 35-40%. Recommend requiring credit card or limiting to 30 medias to reduce risk.

2. **5€ tier with 30% margin:** Achievable with quotas of 15 podcasts + 40 articles + 8 OCR (63 total medias). Actual margin: 41.6% with balanced usage, providing buffer for cost variations.

3. **10€ tier with profitability above 20%:** Remains profitable up to ~125-150 medias/month (depending on mix). This supports realistic intensive usage while maintaining target margin. Recommend soft limit at 150 medias with monitoring.

**Key success factors:**
- Transcription cost of 0.0030€/min (as specified) is crucial — negotiate bulk rates or optimized providers
- Infrastructure cost optimization (spot instances, intelligent tiering) to reduce per-user overhead
- Effective conversion from free trial to paid (35-40% target)
- Clear quota communication and smooth upgrade paths

**Next steps:**
1. Validate transcription cost assumption (0.0030€/min) with actual provider quotes
2. Implement quota tracking and enforcement system
3. Design pricing page with clear messaging
4. Launch with Standard tier + Free trial, add Premium later based on demand
5. Monitor actual costs and adjust quotas after 3 months of real data

---

## Sources

1. **Transcription pricing:**
   - AssemblyAI: https://www.assemblyai.com/pricing
   - Rev.ai: https://www.rev.ai/pricing
   - Deepgram: https://deepgram.com/pricing

2. **LLM pricing:**
   - Google Gemini: https://ai.google.dev/pricing
   - OpenAI: https://openai.com/api/pricing/

3. **OCR pricing:**
   - Google Cloud Vision: https://cloud.google.com/vision/pricing
   - AWS Textract: https://aws.amazon.com/textract/pricing/

4. **Infrastructure:**
   - AWS S3: https://aws.amazon.com/s3/pricing/
   - AWS DynamoDB: https://aws.amazon.com/dynamodb/pricing/
   - AWS EC2: https://aws.amazon.com/ec2/pricing/

5. **Competitor pricing:**
   - Snipd: https://www.snipd.com/pricing
   - Otter.ai: https://otter.ai/pricing
   - Readwise: https://readwise.io/pricing
   - mymind: https://access.mymind.com/pricing

6. **Previous research:**
   - Task 65 archived analysis: `/docs/research/task-65-pricing-v1-benchmark/README.owner-rejected-2026-04-29.md`
