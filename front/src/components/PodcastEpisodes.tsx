import { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, Mic } from 'lucide-react';
import { Podcast, PodcastEpisode } from '../types/podcast';
import { PodcastService } from '../services/podcastService';
import PodcastEpisodeCard from './PodcastEpisodeCard';

interface PodcastEpisodesProps {
  podcast: Podcast;
  token: string;
  onBack: () => void;
  onEpisodeClick?: (episode: PodcastEpisode) => void;
}

export default function PodcastEpisodes({ podcast, token, onBack, onEpisodeClick }: PodcastEpisodesProps) {
  const [episodes, setEpisodes] = useState<PodcastEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadEpisodes();
  }, [podcast.id]);

  const loadEpisodes = async () => {
    setLoading(true);
    setError(null);

    try {
      const feedId = parseInt(podcast.id, 10);
      const response = await PodcastService.getPodcastEpisodes(feedId, token);
      setEpisodes(response.episodes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load episodes');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black">
      {/* Header */}
      <div className="bg-white dark:bg-gray-900 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-6 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Back to search</span>
          </button>

          {/* Podcast info */}
          <div className="flex items-start gap-6">
            <div className="w-32 h-32 flex-shrink-0 rounded-lg overflow-hidden bg-gray-100">
              {podcast.image ? (
                <img
                  src={podcast.image}
                  alt={podcast.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <Mic className="h-12 w-12 text-gray-400" />
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                {podcast.title}
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mb-2">{podcast.author}</p>
              {podcast.description && (
                <p className="text-sm text-gray-500 dark:text-gray-500 line-clamp-3">
                  {podcast.description}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Episodes grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Episodes ({episodes.length})
        </h2>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {!loading && !error && episodes.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No episodes found</p>
          </div>
        )}

        {!loading && episodes.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {episodes.map((episode) => (
              <PodcastEpisodeCard
                key={episode.guid}
                episode={episode}
                onClick={onEpisodeClick}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
