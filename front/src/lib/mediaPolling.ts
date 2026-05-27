import type {
  ArtifactStatus,
  ArtifactStatusSnapshot,
  ArtifactType,
  MediaStatusResponse,
  ProcessingJobLifecycleStatus,
} from "../types/media";

const TERMINAL_PROCESSING_STATUSES = new Set<ProcessingJobLifecycleStatus>([
  "ready_for_artifacts",
  "completed",
  "failed",
  "cancelled",
]);

const TERMINAL_ARTIFACT_STATUSES = new Set<ArtifactStatus>(["ready", "failed"]);
const ACTIVE_ARTIFACT_STATUSES = new Set<ArtifactStatus>(["queued", "generating"]);

export function isTerminalProcessingStatus(
  status: ProcessingJobLifecycleStatus,
): boolean {
  return TERMINAL_PROCESSING_STATUSES.has(status);
}

export function isTerminalArtifactStatus(status: ArtifactStatus): boolean {
  return TERMINAL_ARTIFACT_STATUSES.has(status);
}

export function isActiveArtifactStatus(status: ArtifactStatus): boolean {
  return ACTIVE_ARTIFACT_STATUSES.has(status);
}

export function getArtifactSnapshot(
  response: MediaStatusResponse,
  artifactType: ArtifactType,
): ArtifactStatusSnapshot | undefined {
  return response.media_item.artifact_statuses[artifactType];
}

export function getActiveArtifactTypes(
  response: MediaStatusResponse,
): ArtifactType[] {
  return (Object.entries(response.media_item.artifact_statuses) as Array<
    [ArtifactType, ArtifactStatusSnapshot | undefined]
  >)
    .filter(([, snapshot]) => snapshot && isActiveArtifactStatus(snapshot.status))
    .map(([artifactType]) => artifactType);
}

export function shouldPollMediaStatus(
  response: MediaStatusResponse,
  trackedArtifactTypes: ArtifactType[] = [],
): boolean {
  if (!isTerminalProcessingStatus(response.processing_job.status)) {
    return true;
  }

  const artifactTypes =
    trackedArtifactTypes.length > 0
      ? trackedArtifactTypes
      : (Object.keys(response.media_item.artifact_statuses) as ArtifactType[]);

  return artifactTypes.some((artifactType) => {
    const snapshot = getArtifactSnapshot(response, artifactType);
    if (!snapshot) {
      return trackedArtifactTypes.length > 0;
    }
    return !isTerminalArtifactStatus(snapshot.status);
  });
}
