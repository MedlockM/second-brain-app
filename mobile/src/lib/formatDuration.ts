/**
 * Human-readable duration used by the media hero and the transcript metadata.
 *
 * Lives here rather than inside a screen because two renderers show the same
 * value for the same item: the hero chip row and the reader's metadata line.
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins >= 60) {
    const hrs = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hrs}h ${remainMins}m`;
  }
  return `${mins}m ${secs}s`;
}
