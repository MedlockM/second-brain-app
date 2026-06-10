---
id: task-157
title: Fix PodcastIndex resolver — episode_not_found when matching Apple Podcasts ?i= to feed episodes
status: Done
assignee: []
created_date: '2026-06-10 00:30'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

After task-148 (URL classification), task-155 (credentials loading), and task-150 (Apple normalization), the PodcastIndex resolver now successfully:

1. Receives the Apple Podcasts URL with `source_platform=apple_podcasts`
2. Authenticates against PodcastIndex.org API
3. Searches and finds **multiple candidate feeds** for the show's iTunes ID
4. Retrieves episode lists for each feed (e.g. 100, 30, 10, 5 episodes per feed)

**But it fails at the final matching step** — the worker can't match the Apple Podcasts `?i=<episode_id>` query-string value (`1000771893347` for the test fixture) to any of the retrieved PodcastIndex episode entries:

```
"Retrieved 100 episodes for feed ID: 6684243"
"Retrieved 30 episodes for feed ID: 6681611"
"Retrieved 10 episodes for feed ID: 6492637"
"Retrieved 5 episodes for feed ID: 4691281"
"Podcast URL could not be resolved. code=episode_not_found"
```

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` times out at `rss_resolving` (progress 10%).

CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution` shows the resolver retrieves episodes for 4 candidate feeds but none of them yields a matching episode for the Apple `?i=1000771893347` parameter.

## Root cause hypotheses

The resolver matches Apple's `?i=<episode_id>` against some field of PodcastIndex's episode records. The match is failing for one of these reasons:

1. **Wrong field**: Apple's `i=1000771893347` is the iTunes episode ID. PodcastIndex episodes have an `id` field but it's PodcastIndex's internal numeric ID, NOT iTunes'. The right Apple→PodcastIndex correlation is usually via the **GUID** (`feedItem.guid`) or via fuzzy title+published_at match.
2. **Right feed not picked**: 4 candidate feeds are retrieved but the resolver may stop searching after N retrievals. The actual feed of "Pépite" might not be in the first 4. Or the show titled "Pépite — Ils ont le bracelet" may not be indexed by PodcastIndex at all (PodcastIndex relies on RSS submissions; smaller French shows may be missing).
3. **Episode older than retrieval window**: PodcastIndex's `episodes/byfeedid` endpoint defaults to the most recent 10 episodes (or N configurable). If the target episode is older than the window, it's never seen.
4. **iTunes ID format mismatch**: Apple's `i=` is a 13-digit number. PodcastIndex stores `itunesId` separately. The resolver may compare `1000771893347` against the wrong field.

## Investigation step (do FIRST)

```bash
# 1. Find where the matching happens in the worker code
grep -rnE "episode_not_found|byfeedid|matching|i=1000|episode_id" \
  media_summarizer/workers/podcast_platform_resolvers.py \
  media_summarizer/workers/podcastindex_resolution_worker.py \
  media_summarizer/core/services/podcast_matching.py | head -20

# 2. Test PodcastIndex API directly with the fixture to see what the worker is comparing
curl -s "https://api.podcastindex.org/api/1.0/episodes/byitunesid?id=1000771893347" \
  -H "User-Agent: media-summarizer/dev" \
  -H "X-Auth-Key: ${PODCASTINDEXORG_API_KEY}" \
  -H "X-Auth-Date: $(date +%s)" \
  -H "Authorization: <signature>" | jq

# (or use the worker's PodcastIndex client to reproduce)

# 3. If episodes/byitunesid doesn't return the episode, the problem is upstream:
#    PodcastIndex doesn't index this specific episode. Need to fall back to
#    fuzzy matching by show + episode published_at + title.
```

## Fix candidates

- **A. Add an iTunes-ID-based lookup**: PodcastIndex has `episodes/byitunesid?id=<apple_episode_id>` which directly maps Apple's episode ID to PodcastIndex's record. If this endpoint returns the episode, use that instead of feed-search-then-match.
- **B. Increase the byfeedid retrieval window**: bump from 10 to 100 or 1000 episodes per feed if the worker truncates today.
- **C. Add fuzzy fallback**: if iTunes ID doesn't match, query Apple's oEmbed for the episode title+published_at, then search PodcastIndex for the closest match.
- **D. Surface graceful failure**: if the episode genuinely isn't in PodcastIndex, raise a user-facing message ("Cette plateforme ne prend pas en charge ce podcast") rather than a generic resolution error.

Recommend **A** first — direct iTunes ID lookup is the cleanest and most likely to work for any user-pasted Apple URL. **D** as a safety net.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex -v
```

Wait at `rss_resolving` 10%. CloudWatch shows the 4 feed retrievals followed by `episode_not_found`.

## Out of scope

- Adding new podcast index providers (Listen Notes etc.)
- Changing the Apple URL normalization (task-148 / task-150 already done)
- Authentication issues (task-155 already done)

## References

- task-148 (URL classification)
- task-150 (URL normalization for Apple format)
- task-155 (credentials loading)
- `media_summarizer/workers/podcastindex_resolution_worker.py`
- `media_summarizer/workers/podcast_platform_resolvers.py`
- `media_summarizer/core/services/podcast_matching.py:30` (`best_match_episode`)
- PodcastIndex API docs: https://podcastindex-org.github.io/docs-api/
- CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution` 2026-06-10 ~00:25 UTC
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`
- Test fixture URL: `https://podcasts.apple.com/fr/podcast/p%C3%A9pite-ils-ont-le-bracelet-ils-mangent-tout-az-d%C3%A9teste/id369369012?i=1000771893347`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Investigation done: which of the 4 hypotheses applies, with evidence (curl results from PodcastIndex API)
- [ ] #2 Targeted fix applied; recommended approach is fix A (use `episodes/byitunesid` endpoint) but other approach is fine if justified
- [ ] #3 Lambda image rebuilt + `media-summarizer-worker-podcastindex_resolution` redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` passes (job reaches `completed`)
- [ ] #5 Document graceful-failure UX for cases where the episode genuinely isn't in PodcastIndex
- [ ] #6 No regression on the 12 already-passing tests
<!-- AC:END -->
