---
owner_decision: pending
---

# Benchmark : Instagram Content Extraction Services for V1 Ingestion

## Owner Validation

**Decision**: _(to be filled by the owner after review — free-text describing the final decision: accept recommendation X, reject because Y, accept with modifications Z, or redo instructions)_
**Validated at**: _(ISO date to be filled by the owner)_

---

## Recommendation

**Primary recommendation: Apify (Instagram Reel Scraper + Instagram Post Scraper + Instagram Comment Scraper)**

Apify is recommended as the single-platform solution covering all four V1 content dimensions:

1. **Reels/Videos** — The Instagram Reel Scraper provides hosted MP4 download URLs (`downloadedVideo` field) that are directly feedable to Deepgram for transcription. It also returns the original CDN `videoUrl`. This satisfies the blocking criterion.
2. **Posts/Images** — The Instagram Post Scraper returns `displayUrl` and `images` arrays with high-resolution image URLs for single posts and carousels (`childPosts` field for sidecar content).
3. **Captions** — Both scrapers return full `caption` text.
4. **Comments** — The dedicated Instagram Comment Scraper returns full comment threads with pagination support.

**Why not stay on getinsaver?** GetInSaver covers Reels extraction adequately and is cheaper at low volumes, but it cannot extract images (it rejects `type: "image"` posts), does not return captions, and has no comment extraction capability. Expanding Instagram scope to cover all four content types makes getinsaver insufficient as the sole provider.

**Hybrid fallback**: Keep getinsaver as a fallback for Reels-only extraction (it is already integrated, is free at low volumes, and requires no infra). Use Apify as primary for all content types.

**Estimated monthly cost for V1**: $5-15/month on Apify Free/Starter plan (see Cost Projection section below).

---

## Comparative Table

### Content Capabilities (Axis 1)

| Provider | Reels Video URL (BLOCKING) | Posts/Images (hi-res) | Caption/Text | Comments | Stories/Highlights |
|----------|:---:|:---:|:---:|:---:|:---:|
| **GetInSaver** (incumbent) | PASS — returns `downloads[].url` with MP4 | FAIL — explicitly rejects image-type posts | FAIL — not returned by API | FAIL — not supported | Partial — `/download/story` endpoint |
| **Apify Reel Scraper** | PASS — `downloadedVideo` (hosted 3-day MP4) + `videoUrl` (CDN) | N/A (reel-focused) | PASS — `caption` field | Partial — `latestComments` (10 max) | N/A |
| **Apify Post Scraper** | PASS — `videoUrl` for video posts | PASS — `displayUrl` + `images` array, carousel via `childPosts` | PASS — `caption` field | Partial — `latestComments` | N/A |
| **Apify Comment Scraper** | N/A | N/A | N/A | PASS — full threads with replies, pagination | N/A |
| **Bright Data Instagram** | FAIL — metadata only (URL, description, likes, views); no video download URL | Partial — "Photos" field listed but not confirmed in output | PASS — `description` field | PASS — dedicated comments scraper | N/A |
| **Instaloader** (self-hosted) | PASS — downloads video files directly to disk | PASS — downloads images at full resolution | PASS — saves captions as sidecar `.txt` | PASS — `--comments` flag | PASS — `--stories --highlights` |
| **yt-dlp** (self-hosted) | PASS (fragile) — Instagram extractor works but has known audio-missing issues and requires login | FAIL — video/audio download tool only | Partial — metadata in info_dict | FAIL — not supported | Partial — `instagram:story` extractor |
| **HikerAPI** | Unconfirmed — docs mention "Posts and Reels API" but no explicit video URL field documented | Unconfirmed | Unconfirmed | PASS — endpoint listed | Partial |
| **RapidAPI (various)** | Likely PASS — download-focused APIs typically return media URLs | Likely PASS | Likely PASS | Varies by provider | Varies |

### Pricing (Axis 2)

| Provider | Model | Reels cost | Posts cost | Comments cost | Monthly minimum |
|----------|-------|-----------|-----------|---------------|-----------------|
| **GetInSaver** | Tiered subscription | Free (1,000 req/day) | N/A (unsupported) | N/A | $0 (free tier) / $29 (Basic) |
| **Apify** | Pay-per-result + platform credits | $1.00-2.60/1K reels | $1.00-2.70/1K posts | $1.90-2.30/1K comments | $0 (free: $5 credit/mo) / $29 (Starter) |
| **Bright Data** | Pay-per-result | $1.50/1K records | $1.50/1K records | $1.50/1K records | $0 (1K trial, 1 week) / PAYG from $1.50/1K |
| **Instaloader** | Open source (infra cost) | $0 (compute only) | $0 (compute only) | $0 (compute only) | ~$5-20 (Lambda/ECS compute) |
| **yt-dlp** | Open source (infra cost) | $0 (compute only) | N/A | N/A | ~$5-10 (Lambda/ECS compute) |
| **HikerAPI** | Pay-per-request prepaid | From $0.0006/req | From $0.0006/req | From $0.0006/req | $0 (100 free requests) |
| **RapidAPI (various)** | Subscription tiers | $0-30/mo depending on provider | Varies | Varies | $0 (limited free) / $10-30 |

### Free Tier (Axis 3)

| Provider | Free tier exists? | Limits | Suitable for dev/QA? | Suitable for V1 launch? |
|----------|:-:|-----------|:-:|:-:|
| **GetInSaver** | Yes | 1,000 req/day, 100 req/hour | Yes | Yes (Reels only) |
| **Apify** | Yes | $5/month in credits (~2,000 reels or ~1,850 posts) | Yes | Marginal — may need Starter at $29/mo |
| **Bright Data** | Trial only | 1,000 records, 1 week, one-time | Dev only | No |
| **Instaloader** | N/A (OSS) | Rate-limited by Instagram (unclear limits, risk of IP ban) | Risky | Risky |
| **yt-dlp** | N/A (OSS) | Rate-limited by Instagram | Risky | Risky |
| **HikerAPI** | Yes | 100 requests (one-time, not monthly) | Barely | No |
| **RapidAPI** | Yes (varies) | 100-500 req/month typical | Barely | No (most require paid tier) |

### Reputation and Reliability (Axis 4)

| Provider | Age/Maturity | User base | Stability vs IG changes | TOS Compliance | Support/Docs quality |
|----------|-------------|-----------|:---:|:---:|:---:|
| **GetInSaver** | ~2-3 years | Small, niche | Medium — single provider, opaque maintenance | Gray zone (scraping) | Basic API docs, email-only support |
| **Apify** | 10+ years (founded 2015) | 50K+ devs, established platform | High — dedicated team maintains scrapers, updates within days of IG changes | Gray zone (scraping public data) | Excellent — full docs, Python/JS SDKs, community, chat support |
| **Bright Data** | 10+ years (founded 2014) | Enterprise-grade, Fortune 500 clients | High — large engineering team | Best-in-class compliance program, legal team | Excellent — enterprise docs, account managers |
| **Instaloader** | 7+ years, 12.4K GitHub stars | Large OSS community | Medium — community-maintained, 144 releases, active | Low — direct Instagram scraping, account ban risk | Good OSS docs, community-only support |
| **yt-dlp** | 4+ years, 100K+ GitHub stars | Massive OSS community | Low for Instagram — known issues, "instagram:user" marked as broken | Low — requires login cookies | Good general docs, but Instagram-specific support is limited |
| **HikerAPI** | 2-3 years | Small | Unknown — insufficient data | Unknown | Minimal docs |
| **RapidAPI (various)** | Varies (1-5 years per provider) | Varies | Low-Medium — individual developers, may abandon | Varies | Varies widely |

---

## Blocking Criterion Assessment: Reels Media URL for Deepgram

For Deepgram transcription, we need either:
- A direct HTTP(S) URL to an audio file (mp3, m4a, wav, etc.)
- A direct HTTP(S) URL to a video file (mp4, webm) from which Deepgram can extract audio

**Assessment per provider:**

| Provider | Verdict | Details |
|----------|:-------:|---------|
| **GetInSaver** | PASS | Returns video MP4 URL in `downloads[].url`. Already proven in production. |
| **Apify Reel Scraper** | PASS | Returns `downloadedVideo` (hosted MP4, 3-day TTL) and `videoUrl` (CDN MP4). Both are direct HTTP URLs. |
| **Apify Post Scraper** | PASS | Returns `videoUrl` for video-type posts. |
| **Bright Data** | FAIL | Reels scraper returns metadata only (URL, description, views, likes). No video download URL in output. **ELIMINATED.** |
| **Instaloader** | PASS (conditional) | Downloads video to disk. Would need to upload to S3 then pass S3 URL/key to Deepgram. Adds complexity + storage cost. |
| **yt-dlp** | PASS (fragile) | Can extract video URL/download video. But known issues: missing audio on music reels, login required, "instagram:user" marked broken. Not reliable enough as primary. |
| **HikerAPI** | UNCONFIRMED | Insufficient documentation to verify video URL availability. **ELIMINATED due to risk.** |
| **RapidAPI** | UNCONFIRMED (varies) | Some providers likely return URLs, but no single verified provider with documented reliability. **NOT recommended as primary.** |

### Eliminated from shortlist:
- **Bright Data** — Does not return video download URLs for Reels. Metadata-only output fails the blocking criterion.
- **HikerAPI** — Insufficient documentation; cannot confirm blocking criterion pass. Also has a nearly non-existent free tier (100 requests total).
- **RapidAPI marketplace** — No single provider with sufficient documentation and reliability track record. Too fragmented, risk of provider abandonment.

---

## Shortlisted Candidates (Detailed Analysis)

### 1. Apify (Recommended Primary)

**Strengths:**
- Complete coverage of all 4 content types through specialized scrapers (Reel + Post + Comment)
- Hosted video downloads (`downloadedVideo`) eliminate CDN expiry issues
- Mature platform (10+ years), well-maintained scrapers with fast updates after Instagram changes
- Excellent developer experience: Python SDK, async API, webhooks, scheduled runs
- Generous free tier ($5/month = ~2,000 reel extractions) sufficient for dev/QA
- Returns `transcript` field for reels (bonus — could serve as native caption/subtitle)

**Weaknesses:**
- Requires 3 separate scraper invocations for full content (reel + comments in separate calls)
- Video download links expire after 3 days (must download or pass to Deepgram promptly)
- Residential proxy costs add up for high volumes
- Scraping platform — subject to same Instagram TOS risks as all candidates

**Integration pattern:**
```
User shares IG URL → Classify (reel vs post) → Apify API call
  ├─ If reel: Reel Scraper → downloadedVideo URL → Deepgram transcription queue
  ├─ If image post: Post Scraper → displayUrl/images → OCR/Vision queue
  └─ Caption + Comments: extracted in same call or Comment Scraper follow-up
```

### 2. GetInSaver (Recommended Fallback for Reels)

**Strengths:**
- Already integrated and production-proven
- Very generous free tier (1,000 req/day = 30K/month)
- Simple API — single endpoint, fast response
- Zero additional integration work needed for Reels

**Weaknesses:**
- Reels-only coverage — explicitly rejects image posts
- No caption extraction
- No comment extraction
- Opaque service — no public status page, small team, unclear maintenance cadence
- Single point of failure with no advertised SLA

**Role in recommended architecture:** Fallback for Reels extraction if Apify is down or rate-limited. Already integrated, costs nothing incremental.

### 3. Instaloader (Considered, Not Recommended as Primary)

**Strengths:**
- Full feature coverage (reels, posts, images, comments, captions, stories)
- Free (open source, MIT license)
- Active maintenance (latest release March 2026)
- Python library — can be called programmatically

**Weaknesses:**
- Requires Instagram login session for reliable access (risk of account ban)
- Downloads files to disk — needs upload-to-S3 step before Deepgram
- Rate limiting by Instagram is undocumented and aggressive
- Direct scraping = highest TOS violation risk
- Account ban would take down entire ingestion pipeline
- No hosted infrastructure — must run on our compute
- Latency unpredictable — depends on Instagram's rate limiting

**Verdict:** Too risky as primary provider due to account ban risk and operational overhead. Could serve as emergency fallback or for batch historical extraction.

### 4. yt-dlp (Considered, Not Recommended)

**Strengths:**
- Already used in codebase for TikTok extraction
- Can extract Instagram Reels audio/video
- Free, open source, massive community

**Weaknesses:**
- Instagram extractor marked as partially broken ("instagram:user" is broken)
- Known issue: "Instagram downloads missing audio (music reels)"
- Requires login cookies for most content
- Frequent breakage when Instagram updates
- Only handles video/audio — no images, captions, or comments
- Not suitable as sole Instagram solution

**Verdict:** Not recommended. Instagram support is unreliable and limited to video only.

---

## Cost Projection for V1

### Assumptions

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Monthly Instagram submissions | 500-1,000 | Early V1 user base (50-100 users, 10 shares/month average) |
| Content mix | 60% Reels, 30% Image posts, 10% Carousels | Based on typical Instagram sharing patterns |
| Comments retrieved per post | ~50% of submissions need comments | Not all use cases require comments |
| Average comments per post | 20-50 | Most shared posts are popular content |

### Apify Cost Estimate (Recommended)

| Operation | Volume/month | Unit cost (Free plan) | Monthly cost |
|-----------|-------------|----------------------|--------------|
| Reel Scraper | 600 reels | $2.60/1K | $1.56 |
| Post Scraper | 400 posts | $2.70/1K | $1.08 |
| Comment Scraper | 250 posts x 30 comments | 7,500 comments at $2.30/1K | $17.25 |
| **Total (low volume, 500 subs)** | | | **~$4.64** (without comments) or **~$19.89** (with comments) |

At 1,000 submissions/month:
| Operation | Volume/month | Unit cost (Starter $29/mo) | Monthly cost |
|-----------|-------------|---------------------------|--------------|
| Reel Scraper | 600 reels | $2.30/1K | $1.38 |
| Post Scraper | 400 posts | $2.30/1K | $0.92 |
| Comment Scraper | 500 posts x 30 comments | 15,000 comments at $1.90/1K | $28.50 |
| Platform fee | — | — | $29.00 |
| **Total (Starter plan)** | | | **$29** (credits cover reels+posts; comments may push over) |

**Conclusion:** At V1 launch volumes (500-1K submissions/month), the Apify **Free plan ($5/month credit)** likely covers Reels + Posts extraction. Comments add significant cost. If comments are deprioritized initially, total cost stays under $5/month. The Starter plan ($29/month) provides comfortable headroom for growth.

### GetInSaver Cost (Current/Fallback)

| Volume | Tier | Monthly cost |
|--------|------|-------------|
| < 1,000/day (30K/month) | Free | $0 |
| 1,000-10,000/day | Basic | $29/month |

At V1 volumes (< 1,000 total/month), getinsaver remains completely free.

---

## Migration Plan from GetInSaver

If the recommendation is validated, the migration would proceed as follows:

### Phase 1: Add Apify as primary resolver (Week 1-2)
1. Add Apify Python SDK dependency (`apify-client`)
2. Implement `ApifyInstagramResolver` class alongside existing `InstagramResolver`
3. Configure content-type routing:
   - Reels/Videos → Apify Reel Scraper → extract `downloadedVideo` URL → Deepgram queue
   - Image posts → Apify Post Scraper → extract `images` URLs → OCR/Vision queue (new)
   - Caption → extracted in both scraper responses → store in metadata
4. Add environment variables: `APIFY_API_TOKEN`, `APIFY_INSTAGRAM_REEL_ACTOR_ID`, `APIFY_INSTAGRAM_POST_ACTOR_ID`

### Phase 2: Content classification enhancement (Week 2-3)
1. Extend `_instagram_content_type_from_url()` to differentiate between video and image posts
2. Add `MediaType.IMAGE_POST` or similar for image-only content routing
3. Implement OCR/vision worker queue dispatch for image posts

### Phase 3: Comments extraction (Week 3-4, optional for V1)
1. Implement Apify Comment Scraper integration
2. Add comment storage to media artifacts
3. Configure as async post-processing (not blocking transcription)

### Phase 4: Fallback configuration (Week 2)
1. Keep `InstagramResolver` (getinsaver) as fallback
2. Implement circuit breaker: if Apify fails 3x consecutively → fall back to getinsaver for Reels
3. Image posts have no getinsaver fallback (degrade gracefully with error message)

### Rollback plan
- Feature flag `INSTAGRAM_PROVIDER=apify|getinsaver` to switch back instantly
- GetInSaver integration remains in codebase, unchanged

---

## Risks and Plan B

### Risk 1: Apify scraper breakage after Instagram update
- **Likelihood:** Medium (happens 2-4x/year based on community reports)
- **Impact:** Temporary inability to extract new Instagram content
- **Mitigation:**
  - GetInSaver fallback for Reels (instant switch via feature flag)
  - Apify team typically fixes within 24-72 hours
  - Queue-based architecture means submissions are retried automatically

### Risk 2: Instagram TOS enforcement / legal action
- **Likelihood:** Low (Apify operates legally in EU, public data doctrine)
- **Impact:** Service discontinuation
- **Mitigation:**
  - All candidates face this risk equally (except official Instagram Graph API, which requires business account auth and does not support content download)
  - Apify has legal team and compliance program
  - Plan B: Switch to Instaloader self-hosted (higher operational burden but no third-party dependency)

### Risk 3: Cost escalation at scale
- **Likelihood:** Low at V1 volumes, medium at scale (10K+ submissions/month)
- **Impact:** Margin compression
- **Mitigation:**
  - Comments extraction is optional and can be disabled to reduce costs by 60-80%
  - Negotiate volume pricing with Apify at Scale tier ($199/month for 128K records included at $1.30/1K)
  - Plan B at high volume: Migrate Reels extraction to yt-dlp/Instaloader self-hosted (trade cost for operational complexity)

### Risk 4: Apify video URL expiration (3-day TTL)
- **Likelihood:** Low (processing is near-real-time)
- **Impact:** Failed transcription if Deepgram queue is backed up > 3 days
- **Mitigation:**
  - Process immediately upon extraction (current architecture already does this)
  - Use CDN `videoUrl` as secondary option
  - Download and stage to S3 if queue backlog exceeds 1 hour (defensive measure)

### Risk 5: GetInSaver service disappearance
- **Likelihood:** Medium (small, opaque service)
- **Impact:** Loss of free fallback for Reels
- **Mitigation:**
  - With Apify as primary, getinsaver loss is non-critical
  - yt-dlp can serve as emergency Reels fallback (already in codebase)

---

## Sources

- GetInSaver API documentation: https://getinsaver.com/api/
- Apify Instagram Reel Scraper: https://apify.com/apify/instagram-reel-scraper
- Apify Instagram Post Scraper: https://apify.com/apify/instagram-post-scraper
- Apify Instagram Comment Scraper: https://apify.com/apify/instagram-comment-scraper
- Apify Pricing: https://apify.com/pricing
- Bright Data Instagram Scraper: https://brightdata.com/products/web-scraper/instagram
- Bright Data Instagram Reels: https://brightdata.com/products/web-scraper/instagram/reels
- Instaloader GitHub: https://github.com/instaloader/instaloader
- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp
- yt-dlp Supported Sites: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
- yt-dlp Instagram Issues: https://github.com/yt-dlp/yt-dlp/issues?q=instagram
- HikerAPI: https://hikerapi.com
- HikerAPI Pricing: https://hikerapi.com/pricing
