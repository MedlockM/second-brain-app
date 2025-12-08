export interface Podcast {
  id: string;
  title: string;
  author: string;
  description: string;
  image: string;
  feed_url: string;
  website?: string;
  categories?: string[];
  language?: string;
  episode_count?: number;
}

export interface PodcastSearchResponse {
  results: Podcast[];
  total: number;
  page: number;
  page_size: number;
}

export interface PodcastEpisode {
  id: number;
  title: string;
  description: string;
  guid: string;
  date_published: number;
  enclosure_url: string;
  duration?: number;
  image: string;
  feed_id?: number;
  feed_title: string;
  feed_image: string;
}

export interface PodcastEpisodesResponse {
  status: string;
  episodes: PodcastEpisode[];
  count: number;
  feed_id: number;
  podcast_title: string;
}
