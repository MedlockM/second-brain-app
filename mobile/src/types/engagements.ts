/**
 * Wire types of the engagement API (task-303).
 *
 * "Engagement" is deliberately narrow: the user launched a generation, or opened
 * an artifact and read it. Opening a media detail screen is not one, and neither
 * is scrolling — so nothing on this path is ever fired from a render or a scroll
 * handler.
 */

/** What was engaged with. The artifact API calls a collection a "folder". */
export type EngagementKind = "media" | "collection";

export interface RecordEngagementRequest {
  kind: EngagementKind;
  id: string;
}

/**
 * One tile of the "Continue learning" row, already render-ready: the server
 * merges media and collections, sorts them newest first, caps the list and signs
 * every cover, so the client joins nothing.
 */
export interface RecentEngagement {
  kind: EngagementKind;
  /** Media item id, or collection id — whichever `kind` says. */
  id: string;
  title?: string | null;
  engaged_at: string;
  /** Media only: publisher of the media (a channel, a show, a site, an account). */
  creator_name?: string | null;
  /** Media only: fetchable cover URL, absent when the source can never have one. */
  image_url?: string | null;
  /** Media only: drives the fallback icon when there is no cover. */
  media_type?: string | null;
  /** Collections only: items stored directly in the collection. */
  item_count?: number | null;
  /** Collections only: up to four covers of its newest items, possibly empty. */
  preview_images: string[];
}

export interface RecentEngagementsResponse {
  status: string;
  items: RecentEngagement[];
}
