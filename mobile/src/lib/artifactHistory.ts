/**
 * Folding a single artifact entry into a scope's history.
 *
 * `POST /api/artifacts` answers the entry it just created, so the screens have
 * everything the history needs without a second request. That matters twice
 * over: the list endpoint reads the `scope-index` GSI, which is always
 * eventually consistent, so a GET fired right after the write can come back
 * *without* the new entry — the tile would fall back to "Generate" while a
 * generation is actually running.
 *
 * The POST does not always create, either: a request whose sources already
 * produced an artifact answers that artifact, which may already be `ready` or
 * `failed` and is already in the history. So the merge is keyed on `artifact_id`
 * and replaces in place; only a genuinely new entry is prepended, which keeps the
 * list newest-first the way the API returns it and the way the tiles read it.
 */

import type { ArtifactSummary } from "../types/artifacts";

export function mergeArtifactIntoHistory(
  history: readonly ArtifactSummary[],
  entry: ArtifactSummary,
): ArtifactSummary[] {
  const index = history.findIndex(
    (artifact) => artifact.artifact_id === entry.artifact_id,
  );
  if (index === -1) return [entry, ...history];

  const next = [...history];
  next[index] = entry;
  return next;
}
