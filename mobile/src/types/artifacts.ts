/**
 * Wire types of the scope-addressed artifact API.
 *
 * Artifacts are an append-only history per scope: a scope holds several entries
 * of the same type, each carrying the snapshot of the sources it was generated
 * over. There is no "current artifact of type X" anywhere in these shapes, which
 * is the whole point — the concept stopped existing backend-side too.
 *
 * A new entry only appears when the set of sources differs from every entry
 * already stored (task-322): a media item therefore holds one entry per type for
 * good, and a collection gains one each time its contents change. The `sources`
 * snapshot of an entry is what a screen compares against the collection's
 * current contents to know whether generating again would produce anything.
 */

import type { ArtifactStatus, ArtifactType } from "./media";

/** What a generation was run over. "folder" is what the UI calls a collection. */
export type ArtifactScope = "media" | "folder";

export interface GenerateArtifactRequest {
  scope: ArtifactScope;
  scope_id: string;
  artifact_type: ArtifactType;
  parameters?: Record<string, unknown>;
}

/**
 * One source of an entry's immutable snapshot. `excluded` marks a source that
 * was in the scope but carried no usable transcript: recorded, not dropped, so
 * the entry stays honest about what it could not read.
 */
export interface ArtifactSource {
  media_item_id: string;
  title?: string | null;
  language?: string | null;
  excluded: boolean;
  excluded_reason?: string | null;
}

/** One row of a scope's artifact history. */
export interface ArtifactSummary {
  artifact_id: string;
  artifact_type: ArtifactType;
  status: ArtifactStatus;
  /** Written by the model, which is what tells two entries of the same type apart. */
  title?: string | null;
  source_count: number;
  created_at: string;
  completed_at?: string | null;
  error_code?: string | null;
}

export interface ArtifactDetail extends ArtifactSummary {
  scope: ArtifactScope;
  scope_id: string;
  sources: ArtifactSource[];
  s3_key?: string | null;
}

/**
 * What a generation request actually did, as the API names it.
 *
 * - `created`: a generation was queued over these sources.
 * - `retried`: an entry that had failed over these sources was rerun.
 * - `reused`: an artifact already covered these sources; nothing was queued and
 *   no minute was charged. This is the normal answer to a second request on a
 *   media item, and to a collection whose sources have not changed.
 * - `collapsed`: two concurrent taps, and this one lost the race; the entry
 *   returned is the one already in flight.
 */
export type ArtifactGenerationOutcome =
  | "created"
  | "retried"
  | "reused"
  | "collapsed";

/** The answer to `POST /api/artifacts`: the entry, plus what the call did. */
export interface ArtifactCreateResult extends ArtifactDetail {
  generation_outcome: ArtifactGenerationOutcome;
}

export interface ArtifactListResponse {
  scope: ArtifactScope;
  scope_id: string;
  artifacts: ArtifactSummary[];
  next_cursor?: string | null;
}

export interface ArtifactContentResponse {
  artifact_id: string;
  artifact_type: ArtifactType;
  scope: ArtifactScope;
  scope_id: string;
  status: ArtifactStatus;
  /** Parsed JSON payload (shape depends on artifact_type). */
  content: Record<string, unknown>;
}
