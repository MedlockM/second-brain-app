/**
 * Glyph for a media type.
 *
 * One mapping for every surface that shows a media row — the inbox vignette, the
 * media detail header, the Sources tab of a collection. Three private copies of
 * this switch had drifted apart before it was extracted; a source that changes
 * icon between two screens is a bug the user notices.
 */

import type { Ionicons } from "@expo/vector-icons";
import type { MediaType } from "../types/media";

export function getMediaTypeIcon(
  type: MediaType,
): keyof typeof Ionicons.glyphMap {
  switch (type) {
    case "podcast_episode":
      return "headset-outline";
    case "article":
      return "document-text-outline";
    case "youtube_video":
    case "short_video":
      return "play-circle-outline";
    case "audio_file":
    case "audio":
      return "musical-notes-outline";
    case "shared_text":
      return "text-outline";
    case "document":
      return "document-attach-outline";
    default:
      return "link-outline";
  }
}
