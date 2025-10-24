import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { PodcastService } from '../services/podcastService';
import { Podcast } from '../types/podcast';
import PodcastCard from './PodcastCard';

interface PodcastSearchProps {
  token: string;
}

export default function PodcastSearch({ token }: PodcastSearchProps) {
  const [query, setQuery] = useState('');
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      return;
    }

    setLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await PodcastService.searchPodcasts(query, token);
      setPodcasts(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search podcasts');
      setPodcasts([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex justify-center">
        <form onSubmit={handleSearch} className="w-full max-w-3xl">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for podcasts..."
              className="w-full px-6 py-4 pr-14 text-lg border border-gray-300 rounded-full shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Search className="h-5 w-5" />
              )}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="max-w-3xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {hasSearched && !loading && podcasts.length === 0 && !error && (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No podcasts found for "{query}"</p>
        </div>
      )}

      {podcasts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {podcasts.map((podcast) => (
            <PodcastCard key={podcast.id} podcast={podcast} />
          ))}
        </div>
      )}
    </div>
  );
}
