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
