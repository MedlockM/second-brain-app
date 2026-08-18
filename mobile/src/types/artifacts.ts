/**
 * Wire types of the scope-addressed artifact API.
 *
 * Artifacts are an append-only history per scope: a scope holds several entries
 * of the same type, each carrying the snapshot of the sources it was generated
 * over. There is no "current artifact of type X" anywhere in these shapes, which
 * is the whole point — the concept stopped existing backend-side too.
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
