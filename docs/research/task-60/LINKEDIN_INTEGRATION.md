# LinkedIn Post Ingestion - V1 Integration Documentation

**Task:** task-60  
**Status:** Implemented  
**Date:** 2026-04-28

---

## Overview

LinkedIn post ingestion in V1 uses a **manual paste fallback UX** approach.
Users copy post text from LinkedIn and submit it via the
`POST /api/media/ingest-shared-content` endpoint.

This approach was chosen after exhaustive benchmarking (see
`BENCHMARK_UPDATE_2026-04-23.md`) which concluded that all automated
scraping methods violate LinkedIn ToS Section 8.2 and carry unacceptable
legal risk for a V1 product.

---

## Architecture

### URL Detection

LinkedIn post URLs are detected in the `_detect_platform()` function
(`media_summarizer/api/endpoints/media.py`):

- `linkedin.com/feed/update/urn:li:activity:*`
- `linkedin.com/posts/*`

When a LinkedIn URL is submitted to `POST /api/media/ingest-url`, the API
returns HTTP 422 with guidance to use the shared content endpoint instead.

### Resolver Module

`media_summarizer/core/resolvers/linkedin.py` provides:

- `is_linkedin_url(url)` - Boolean detection
- `validate_linkedin_url(url)` - Validation with normalization
- `LinkedInResolver.resolve_from_paste(url, text, author)` - Content resolution
- `LinkedInResolver.generate_media_key(content)` - Deduplication key

### Shared Content Endpoint

`POST /api/media/ingest-shared-content` accepts:

```json
{
  "text": "Full post content pasted by user (min 20 chars)",
  "source_url": "https://linkedin.com/posts/...",
  "source_platform": "linkedin",
  "title": "Optional title",
  "author": "Optional author name"
}
```

Response (202 Accepted):

```json
{
  "media_item_id": "uuid",
  "status": "summarizing",
  "source_platform": "linkedin",
  "media_key": "linkedin:<sha256-hash>"
}
```

### Processing Flow

1. User pastes LinkedIn post text + URL
2. API validates URL format and content length
3. Content hash generated for deduplication (`media_key`)
4. Text stored as transcript in S3 (JSON format)
5. Job routed directly to summarization queue (skips download + transcription)
6. Summary artifacts generated normally

---

## Error Handling

Stable error codes (enum `LinkedInResolverError`):

| Code | Meaning |
|------|---------|
| `linkedin_invalid_url` | URL is not a valid LinkedIn URL |
| `linkedin_unsupported_url_format` | URL does not match /feed/update/ or /posts/ patterns |
| `linkedin_empty_content` | No text content provided |
| `linkedin_content_too_short` | Text must be at least 20 characters |
| `linkedin_private_post` | Post is private (reserved for future use) |
| `linkedin_login_wall` | Login required to view (reserved for future use) |
| `linkedin_structure_changed` | Page structure changed (reserved for future use) |

---

## ToS Compliance

### What we DO:

- Accept user-pasted content (user manually copies from LinkedIn)
- Validate URL format for metadata purposes only
- Store and process text submitted by the user

### What we DO NOT do:

- No automated HTTP requests to LinkedIn
- No headless browser scraping
- No use of unofficial LinkedIn APIs
- No storage of LinkedIn authentication credentials
- No bot activity or automated data collection

### Legal Basis

Users manually sharing content they have access to is analogous to
copy-pasting into a note-taking app. This does not violate LinkedIn ToS
Section 8.2 because:

1. No automated access to LinkedIn services
2. No scraping, crawling, or bot activity
3. User initiates and controls the data transfer
4. Content is used for personal summarization (fair use)

---

## Limitations

1. **User friction**: Requires manual copy-paste action
2. **No metadata**: Author, date, likes, images not automatically extracted
3. **No validation**: Cannot verify the pasted text matches the URL
4. **Scale ceiling**: Not practical for >100 posts/month per user

---

## Post-V1 Considerations

If LinkedIn post volume exceeds 100/month:

1. **Browser extension** - Pre-fill paste dialog from page content
2. **Re-evaluate scraping** - If legal landscape changes
3. **LinkedIn Partnership** - If >$100k budget becomes available

Monitor:
- Posts submitted per month per user
- User complaints about friction
- LinkedIn API policy changes

---

## File Locations

- Resolver: `media_summarizer/core/resolvers/linkedin.py`
- URL detection: `media_summarizer/api/endpoints/media.py` (`_detect_platform()`)
- Endpoint: `media_summarizer/api/endpoints/media.py` (`ingest_shared_content()`)
- Tests: `media_summarizer/tests/unit/core/resolvers/test_linkedin.py`
- Benchmark: `docs/research/task-60/BENCHMARK_UPDATE_2026-04-23.md`
