/**
 * Digest types for the mobile app.
 * Used by the daily and weekly digest screens.
 */

export interface DigestMediaItem {
  media_item_id: string;
  title: string;
  source_platform: string;
  media_type: string;
  summary_excerpt: string;
  processed_at: string;
  /**
   * Cover image, resolved into a fetchable URL by the API. Absent for the three
   * sources that can never have one (shared text, documents, audio files).
   */
  thumbnail_url?: string;
  /** Publisher of the media: a channel, a show, a site, an account. */
  creator_name?: string;
  /** Estimated reading time in minutes */
  read_time_minutes?: number;
}

export interface DailyDigest {
  date: string;
  stats: {
    media_count: number;
    total_minutes: number;
  };
  insights: string[];
  media_items: DigestMediaItem[];
}

export interface WeeklyDigest {
  week_start: string;
  week_end: string;
  stats: {
    media_count: number;
    total_minutes: number;
    by_type: Record<string, number>;
  };
  themes: string[];
  top_items: DigestMediaItem[];
}
