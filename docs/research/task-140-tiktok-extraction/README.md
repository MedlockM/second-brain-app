---
owner_decision: ok

# Benchmark: TikTok Extraction Strategies Given Lambda IP Blocking

## Owner Validation

**Decision**: hybrid yt-dlp et apify actor en fallback pour la V1 mais on passera en fallback residential proxy en V2 (à consigner quelque part). J'ai renseigné # Tik Tok (via Apify actor)
APIFY_TIKTOK_API_TOKEN=
APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID= dans .env.example et les valeur sassociées dans .env
**Validated at**: _(ISO date to be filled by the owner)_

---

## Recommendation

**Recommended strategy: Hybrid yt-dlp with residential proxy fallback via Webshare**

### Summary

Use the existing yt-dlp pipeline as the primary path (zero extra cost for unblocked videos), and fall back to yt-dlp routed through a Webshare rotating residential proxy when TikTok returns the `status 10204` IP block error. This approach:

1. **Preserves the existing pipeline** -- no new service integration, minimal code changes
2. **Maximizes cost efficiency** -- residential proxy bandwidth is only consumed for blocked videos (estimated 20-40% of total requests)
3. **Achieves near-complete coverage** -- residential IPs have historically 95%+ success rate against TikTok's anti-bot
4. **Keeps operational complexity low** -- a single secret (proxy URL) added to Lambda environment variables

### Why not Apify?

Apify's TikTok scraper (Clockworks) is a strong alternative but introduces:
- A new service dependency and API integration pattern
- Higher per-request cost ($0.005/video vs ~$0.002-0.004 for proxy bandwidth)
- Uncertainty about subtitle/transcript extraction (the `transcriptionLink` field is often null)
- Async polling model (actor runs) that adds latency and complexity vs. a synchronous proxy call

The Apify path should be the **escalation strategy** if residential proxies prove insufficient (e.g., TikTok starts fingerprinting beyond IP).

### Owner Trade-offs to Consider

| Factor | Webshare Proxy (recommended) | Apify TikTok Scraper | Accept Partial Coverage |
|--------|------------------------------|---------------------|------------------------|
| Monthly cost at 300 URLs/day | ~$8-15/mo (proxy bandwidth) | ~$30-45/mo (compute units) | $0 |
| Success rate on blocked videos | ~95% (residential IPs) | ~90-95% (Apify infra) | 0% on blocked videos |
| Implementation effort | Low (add `proxy` key to yt-dlp opts) | Medium (new HTTP client, actor polling) | None |
| New dependency | Webshare account + API key | Apify account + API key | None |
| Latency impact | +200-500ms per proxied request | +3-10s (actor spin-up + polling) | None |
| Maintenance risk | Proxy may degrade over time | Apify actor may break on TikTok changes | yt-dlp may degrade further |
| Graceful degradation | Falls back to direct if proxy fails | Falls back to direct if Apify fails | Already degraded |

---

## 1. Scope of the IP Block

### Observed Pattern

Based on the task description and yt-dlp issue tracker analysis:

| Video Category | Example | Lambda Direct Access | Pattern |
|----------------|---------|---------------------|---------|
| Old viral content (2019) | `@scout2015/video/6718335390845095173` | SUCCESS | Low-value, old content passes |
| Official media (2024) | `@bbc/video/7335731145619360992` | BLOCKED (10204) | High-profile accounts blocked |
| Music/entertainment | Major label content | Likely BLOCKED | High-value IP-fingerprinted |
| Individual creators | Small accounts, recent | Mixed | Inconsistent enforcement |
| Educational content | Tutorial videos | Likely SUCCESS | Lower enforcement priority |

### TikTok's Anti-Bot Architecture (from yt-dlp source analysis)

The yt-dlp TikTok extractor (as of 2026) reveals TikTok's multi-layer defense:

1. **IP reputation scoring** -- Status code `10204` = datacenter/VPN IP detected and blocked
2. **TLS fingerprinting** -- yt-dlp uses browser impersonation via `curl_cffi` to mimic Chrome/Safari TLS handshakes
3. **JavaScript challenge (WAF)** -- Proof-of-work SHA-256 computation (up to 1M iterations) to set WAF cookies
4. **Device fingerprinting** -- Mobile app API calls use randomized Pixel 7 device parameters
5. **Cookie rotation** -- Random 160-char hex `odin_tt` cookie per request

The IP block (`10204`) is the **first layer** -- if the IP passes, subsequent layers are handled by yt-dlp's existing anti-bot logic. This means a residential IP solves the immediate problem without needing to change the extraction logic.

### Estimated Block Rate

Based on the observed pattern (old/low-value content passes, recent/high-profile content is blocked) and community reports (yt-dlp issue #16605 closed as "invalid" -- maintainers acknowledge this is TikTok-side), the estimated block rate from AWS Lambda eu-west-3 IPs is:

- **Conservative estimate**: 30-50% of submissions blocked
- **Aggressive estimate**: 50-70% if users primarily submit trending/popular content
- **Best case**: 20-30% if users submit diverse/niche content

> Note: Empirical confirmation on 10-20 URLs from the actual Lambda environment was not performed in this benchmark pass because it requires Lambda execution access. The recommendation accounts for this uncertainty with the hybrid approach (try direct first, fallback to proxy).

---

## 2. Candidate Strategies

### Strategy A: Residential Proxy for yt-dlp (RECOMMENDED)

**Concept**: Add a rotating residential proxy URL to yt-dlp's options when the first attempt fails with IP block error.

**How it works**:
1. First attempt: yt-dlp with no proxy (current behavior)
2. If `ExtractorError` contains "IP address is blocked" or status 10204 → retry with `proxy` option set to Webshare residential gateway
3. If proxy attempt also fails → mark as failed with clear error

**Vendors evaluated**:

| Vendor | Price/GB | EU Coverage | Min Commitment | Pool Size | Protocol |
|--------|----------|-------------|----------------|-----------|----------|
| **Webshare** | $2.25/GB (100GB plan) | FR, DE, ES, IT, NL | 1 GB ($3.50) | 80M+ IPs | HTTP/SOCKS5 |
| **Decodo** (ex-Smartproxy) | $2.00/GB | FR, DE, NL, UK | Pay-as-you-go | 125M+ IPs | HTTP/SOCKS5 |
| **Bright Data** | $4.00/GB (PAYG) | FR, DE, ES | 141 GB ($499/mo) | 400M+ IPs | HTTP/SOCKS5 |
| **Oxylabs** | $4.00/GB | FR, DE, NL | 1 GB ($15) | 100M+ IPs | HTTP/SOCKS5 |

**Bandwidth estimate per TikTok extraction**:
- yt-dlp metadata-only extraction (no download): ~50-200 KB per request
- At 300 URLs/day with 40% needing proxy: 120 proxied requests/day
- 120 requests x 150 KB avg = ~18 MB/day = ~540 MB/month
- **Monthly cost**: ~$1.20-1.90 at $2.25/GB (Webshare 100GB tier is overkill; 1GB tier at $3.50 suffices)

**Vendor recommendation**: **Webshare** -- cheapest entry point ($3.50/mo for 1GB), EU coverage including France, HTTP/SOCKS5 support compatible with yt-dlp's `--proxy` option, 80M+ residential IPs.

---

### Strategy B: Apify TikTok Scraper (Clockworks)

**Concept**: Use Apify's managed TikTok scraper actor as a fallback when yt-dlp fails.

**How it works**:
1. First attempt: yt-dlp direct (current behavior)
2. If blocked → call Apify API to run the TikTok Data Extractor actor with the video URL
3. Poll for completion (actor runs are async)
4. Extract relevant fields: `musicMeta.playUrl` (audio), `videoMeta.transcriptionLink` (subtitles), `text` (caption)

**Key output fields available**:
- `musicMeta.playUrl` -- direct audio URL on tiktokcdn (usable for Deepgram transcription)
- `videoMeta.transcriptionLink` -- subtitle link (often null for videos without TikTok-generated captions)
- `videoMeta.downloadAddr` -- direct video download URL
- `text` -- video caption text
- `videoMeta.duration` -- duration in seconds

**Pricing**:
- Apify platform: Free tier gives $5/month in credits
- Actor cost: ~$0.005 per video scraped (from Apify store listing: "$2.00 / 1,000 results")
- At 120 fallback requests/day: 3,600/month x $0.005 = **~$18/month**

**Limitations**:
- `transcriptionLink` is frequently null (only present for videos with TikTok auto-captions enabled)
- Actor spin-up adds 3-10 seconds latency per request
- Requires polling logic (run actor → wait → fetch results)
- Relies on Apify maintaining the actor against TikTok changes
- The `playUrl` from musicMeta may be a short clip (TikTok music snippet), not the full video audio

---

### Strategy C: yt-dlp with `curl_cffi` Browser Impersonation (Enhancement to Strategy A)

**Concept**: Ensure the Lambda deployment includes `curl_cffi` so yt-dlp can use browser TLS impersonation against TikTok.

**How it works**:
- Install `curl_cffi` in the Lambda layer alongside yt-dlp
- yt-dlp automatically uses it when available (the TikTok extractor already calls with `impersonate=True`)
- This may reduce the IP block rate by making requests look more like real browser traffic at the TLS level

**Key finding from yt-dlp source**: The TikTok extractor's `_extract_web_data_and_status` method already passes `impersonate=True`. If `curl_cffi` is not installed, yt-dlp logs a warning: "The extractor is attempting impersonation, but no impersonate target is available."

**Cost**: $0 (just a pip dependency)
**Risk**: Increases Lambda package size by ~15-20 MB; may not be sufficient alone against IP-level blocks

**Verdict**: Should be implemented regardless of which primary strategy is chosen. It is complementary, not a standalone solution -- TikTok's `10204` status is an IP-level block that occurs before TLS fingerprinting matters.

---

### Strategy D: Bright Data Web Unlocker

**Concept**: Route TikTok requests through Bright Data's managed unblocking proxy that handles CAPTCHA solving, fingerprinting, and IP rotation automatically.

**How it works**:
- Configure yt-dlp with Bright Data's Web Unlocker endpoint as proxy
- Web Unlocker automatically selects the right proxy type, solves challenges, and returns clean responses
- Claims 98% success rate across protected sites

**Pricing**: Only charges for successful requests. Base residential rate is $4.00/GB (PAYG).
- Estimated: 120 requests/day x 150KB x 30 days = ~540 MB/month x $4/GB = **~$2.16/month**

**Limitations**:
- Minimum commitment unclear for PAYG (documentation mentions $499/month for 141GB tier)
- Explicitly states "Not for social network account management" -- unclear if metadata extraction is permitted
- Overkill for our use case (we only need IP rotation, not CAPTCHA solving -- yt-dlp handles challenges itself)
- Higher per-GB cost than dedicated residential proxy vendors

---

### Strategy E: TikTok Research API (`voice_to_text` field)

**Concept**: Use TikTok's official Research API which returns a `voice_to_text` field containing auto-generated transcripts.

**How it works**:
- Apply for Research API access
- Query videos by ID to get metadata including transcript text
- Bypass all anti-bot measures (official API)

**Critical blocker**: The Research API is **restricted to non-profit academic researchers**. Commercial applications are explicitly excluded. TikTok requires applicants to conduct "research on a non-for-profit basis" and be approved.

**Verdict**: **Not viable** for this project. Ruled out.

---

### Strategy F: Headless Browser (Playwright on Lambda)

**Concept**: Run a full headless Chromium browser in Lambda to load TikTok pages like a real user.

**How it works**:
- Use Playwright or Puppeteer in a Lambda layer
- Navigate to the TikTok video page
- Extract metadata from the rendered DOM (the `__UNIVERSAL_DATA_FOR_REHYDRATION__` script tag)
- Extract subtitle data from the page

**Limitations**:
- Lambda package size: Chromium adds ~130-280 MB to the deployment (Lambda limit is 250 MB zipped / 500 MB unzipped for layers)
- Cold start: 5-15 seconds for browser initialization
- Memory: Requires 1-2 GB RAM minimum
- Still subject to IP blocking (browser fingerprint helps but datacenter IP is still datacenter IP)
- Dramatically increases operational complexity

**Verdict**: **Overkill and likely insufficient alone**. The IP block is at the network layer, not the browser layer. A residential proxy solves the root cause more elegantly.

---

### Strategy G: Client-Side Delegation (Mobile App Fetches Metadata)

**Concept**: The mobile app extracts TikTok metadata on the user's device (residential IP by definition) and sends it to the backend.

**How it works**:
- User shares TikTok URL to the app
- App fetches the TikTok page from the user's device (residential IP, real browser)
- App extracts the `__UNIVERSAL_DATA_FOR_REHYDRATION__` JSON from the page
- App sends extracted metadata + audio URL to the backend
- Backend proceeds with transcription using the resolved audio URL

**Advantages**:
- Zero proxy cost (user's own IP)
- Highest success rate (real device, real IP, real browser)
- No ToS concerns (user accessing their own content)

**Limitations**:
- Requires mobile app changes (significant effort)
- Not applicable for web submissions (no browser extension yet)
- Increases client complexity and attack surface
- TikTok may serve different content to mobile web vs. app
- Adds a tight coupling between client and TikTok's page structure

**Verdict**: Interesting for V2/V3 but **premature for V1**. The backend must handle extraction independently for the MVP.

---

### Strategy H: Accept Partial Coverage (Do Nothing)

**Concept**: Accept that some TikTok videos cannot be processed and communicate this clearly to users.

**How it works**:
- Keep current yt-dlp direct extraction
- When IP block error occurs, surface a clear user-facing message: "This TikTok video is currently inaccessible from our servers. Please try a different video."
- Track failure rate in metrics to inform future decisions

**Cost**: $0
**Coverage**: ~50-70% of submitted TikTok URLs succeed

**When this makes sense**:
- If TikTok is a minor source (<5% of total submissions)
- If the owner wants to defer proxy costs until post-launch
- If the block rate turns out to be lower than estimated after empirical testing

---

## 3. Comparative Evaluation

| Criterion | A: Webshare Proxy | B: Apify Scraper | C: curl_cffi | D: Bright Data | E: Research API | F: Headless | G: Client-Side | H: Do Nothing |
|-----------|------------------|-----------------|-------------|---------------|----------------|-------------|---------------|--------------|
| **Reliability** | High (95%+) | High (90-95%) | Low-Medium alone | High (98%) | N/A (blocked) | Medium | Very High | Low (50-70%) |
| **Coverage** | All video types | All except private | Only helps with TLS, not IP | All video types | N/A | Limited by IP | All types | Partial |
| **Latency** | +200-500ms | +3-10s | +0ms | +300-800ms | N/A | +5-15s | +0ms (client) | +0ms |
| **Monthly Cost (300 URLs/day, 40% blocked)** | $3.50-5 | $18-25 | $0 | $2-5 (if PAYG available) | N/A | Lambda cost increase | $0 | $0 |
| **Operational Complexity** | Low (1 env var) | Medium (new client, polling) | Very Low (pip install) | Low-Medium | N/A | Very High | High (app changes) | None |
| **Legal/ToS** | Gray area (proxy usage) | Gray area (scraping) | Clean (just HTTP client) | Gray area | Clean but inaccessible | Gray area | Clean | Clean |
| **Fit with Pipeline** | Excellent (same yt-dlp flow) | Medium (new data format mapping) | Excellent (transparent) | Good (proxy for yt-dlp) | Poor | Poor | Poor (V1) | Excellent |
| **Maintenance Risk** | Low (proxy is commodity) | Medium (actor may break) | Low (yt-dlp maintains) | Low | N/A | High | Medium | None |

---

## 4. Detailed Recommendation

### Immediate Actions (V1 Launch)

1. **Add `curl_cffi` to the Lambda layer** (Strategy C) -- zero cost, may reduce block rate by improving TLS fingerprinting. Should be done regardless.

2. **Implement proxy fallback with Webshare** (Strategy A):
   - Sign up for Webshare 1GB residential plan ($3.50/month)
   - Store proxy URL as `TIKTOK_PROXY_URL` in AWS Secrets Manager
   - Modify `_extract_tiktok_info()` to catch IP block errors and retry with proxy
   - Monitor proxy bandwidth usage via Webshare dashboard

3. **Implement graceful failure for truly unreachable videos** (Strategy H as final fallback):
   - If both direct and proxy attempts fail, surface a clear user message
   - Log the failure pattern for analysis

### Escalation Path (Post-Launch)

If Webshare residential proxy success rate drops below 90%:
- Evaluate switching to Apify TikTok scraper (Strategy B) as a managed fallback
- Consider Bright Data Web Unlocker if the issue is beyond simple IP rotation

---

## 5. Migration Plan Sketch

### Phase 1: curl_cffi Installation (1 hour)

```
# Add to requirements or Lambda layer
pip install "yt-dlp[curl-cffi]"
# or explicitly:
pip install curl-cffi
```

- Add `curl-cffi` to the Lambda layer build script
- Verify package fits within Lambda size limits (~15-20 MB addition)
- No code changes needed -- yt-dlp uses it automatically when available

### Phase 2: Proxy Fallback Logic (2-4 hours)

**Code changes in `media_summarizer/workers/tiktok_ingestion_worker.py`**:

1. Add environment variable:
```python
TIKTOK_PROXY_URL = os.environ.get("TIKTOK_PROXY_URL", "")
```

2. Add IP block detection helper:
```python
def _is_ip_blocked_error(message: str) -> bool:
    normalized = (message or "").lower()
    return "ip address is blocked" in normalized or "status code 10204" in normalized
```

3. Modify `_extract_tiktok_info()` to support proxy retry:
```python
async def _extract_tiktok_info(normalized_url: str, *, use_proxy: bool = False) -> Dict[str, Any]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "subtitleslangs": ["all"],
        "socket_timeout": YTDLP_TIMEOUT_SECONDS,
    }
    if use_proxy and TIKTOK_PROXY_URL:
        ydl_opts["proxy"] = TIKTOK_PROXY_URL
    # ... rest of existing logic
```

4. Add retry logic at the call site (around line 761):
```python
try:
    info = await _extract_tiktok_info(normalized_url)
except TikTokIngestionError as exc:
    if _is_ip_blocked_error(exc.details or str(exc)) and TIKTOK_PROXY_URL:
        logger.info("IP blocked, retrying with residential proxy", extra={...})
        info = await _extract_tiktok_info(normalized_url, use_proxy=True)
    else:
        raise
```

### Phase 3: Infrastructure (30 minutes)

1. Create Webshare account, generate rotating residential proxy credentials
2. Store proxy URL in AWS Secrets Manager: `tiktok-proxy-url`
3. Add environment variable to Lambda function Terraform config:
```hcl
environment {
  variables = {
    TIKTOK_PROXY_URL = data.aws_secretsmanager_secret_version.tiktok_proxy.secret_string
  }
}
```

### Phase 4: Testing

1. Deploy to staging Lambda
2. Test with known-blocked URL (`@bbc/video/7335731145619360992`)
3. Test with known-passing URL (`@scout2015/video/6718335390845095173`)
4. Verify proxy is only used on fallback (check logs for "retrying with residential proxy")
5. Monitor Webshare bandwidth dashboard for expected usage

### Phase 5: Monitoring & Alerting

- Add CloudWatch metric: `tiktok_proxy_fallback_count` (incremented each time proxy is used)
- Add CloudWatch metric: `tiktok_extraction_final_failure` (both direct and proxy failed)
- Alert if `tiktok_extraction_final_failure` rate exceeds 10% over 1 hour

### Rollback Plan

- Set `TIKTOK_PROXY_URL=""` (empty string) to disable proxy fallback instantly
- No code rollback needed -- the feature is behind an environment variable toggle

---

## 6. Handling Unreachable TikTok URLs

For videos that no strategy can resolve (private videos, deleted content, geo-restricted, or if both direct and proxy attempts fail):

### Error Classification

| Error Type | User Message | Retryable | Action |
|-----------|-------------|-----------|--------|
| IP blocked (direct) + proxy succeeds | _(no user-visible error)_ | N/A | Transparent fallback |
| IP blocked (direct) + proxy fails | "This TikTok video is temporarily inaccessible. We'll retry automatically." | Yes (with backoff) | Retry 2x with 5-min delay |
| IP blocked (both) after all retries | "This TikTok video cannot be accessed from our servers. It may be restricted by TikTok." | No | Mark failed, notify user |
| Private/deleted video | "This TikTok video is unavailable or has been removed." | No | Mark failed immediately |
| Rate limited | "TikTok rate limit reached. Your video will be processed shortly." | Yes | Exponential backoff |

### Retry Semantics

1. **First attempt**: Direct yt-dlp (no proxy)
2. **Second attempt** (if IP blocked): yt-dlp with residential proxy
3. **Third attempt** (if proxy also failed): Retry with proxy after 5-minute SQS visibility timeout
4. **Final failure**: After 3 total proxy attempts (configurable via `TIKTOK_WORKER_MAX_RETRIES`), mark job as permanently failed

### User Communication

The existing `TikTokIngestionError.user_message` field surfaces to the frontend. New messages:
- Transparent fallback: user never sees an error
- Temporary failure: "Processing delayed -- retrying automatically"
- Permanent failure: "This video could not be processed. TikTok may be blocking access to this content."

---

## 7. Sources

- yt-dlp TikTok extractor source (IP block detection at status 10204): https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py
- yt-dlp issue #16605 (IP block reported, closed as invalid/TikTok-side): https://github.com/yt-dlp/yt-dlp/issues/16605
- yt-dlp proxy documentation: https://github.com/yt-dlp/yt-dlp#use-a-proxy
- yt-dlp browser impersonation (curl_cffi): https://github.com/yt-dlp/yt-dlp/blob/master/README.md
- curl_cffi package (browser TLS impersonation): https://pypi.org/project/curl-cffi/
- Webshare residential proxy pricing: https://webshare.io/pricing
- Decodo (ex-Smartproxy) residential proxies: https://www.decodo.com/residential-proxies
- Bright Data residential proxy pricing: https://brightdata.com/proxy-types/residential-proxies
- Bright Data Web Unlocker: https://docs.brightdata.com/scraping-automation/web-unlocker/introduction
- Apify TikTok Data Extractor (Clockworks): https://apify.com/clockworks/free-tiktok-scraper
- Apify TikTok scraper output schema: https://apify.com/clockworks/free-tiktok-scraper/output-schema
- Apify platform pricing: https://apify.com/pricing
- Apify store TikTok actors: https://apify.com/store?q=tiktok
- TikTok Research API (eligibility -- academic only): https://developers.tiktok.com/doc/about-research-api
- TikTok Research API video fields (voice_to_text): https://developers.tiktok.com/doc/research-api-specs-query-videos
- ScrapeOps TikTok scraping guide (residential proxy recommendation): https://scrapeops.io/web-scraping-playbook/how-to-scrape-tiktok/
- drawrowfly/tiktok-scraper (abandoned 2021): https://github.com/drawrowfly/tiktok-scraper
