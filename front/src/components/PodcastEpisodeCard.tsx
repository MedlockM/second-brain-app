import { PodcastEpisode } from '../types/podcast';
import { Calendar, Clock, Mic } from 'lucide-react';

interface PodcastEpisodeCardProps {
  episode: PodcastEpisode;
  onClick?: (episode: PodcastEpisode) => void;
}

export default function PodcastEpisodeCard({ episode, onClick }: PodcastEpisodeCardProps) {
  const formatDate = (timestamp: number) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}min`;
    }
    return `${minutes} min`;
  };

  return (
    <div
      className={`bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow ${onClick ? 'cursor-pointer' : ''}`}
      onClick={() => onClick?.(episode)}
    >
      <div className="aspect-square relative bg-gray-100">
        {episode.image || episode.feed_image ? (
          <img
            src={episode.image || episode.feed_image}
            alt={episode.title}
            className="w-full h-full object-cover"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23e5e7eb'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%239ca3af'%3ENo Image%3C/text%3E%3C/svg%3E";
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Mic className="h-16 w-16 text-gray-400" />
          </div>
        )}
      </div>

      <div className="p-4">
        <h3 className="font-semibold text-gray-900 text-sm mb-2 line-clamp-2">
          {episode.title}
        </h3>

        <div className="flex items-center gap-3 text-xs text-gray-500">
          {episode.date_published > 0 && (
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>{formatDate(episode.date_published)}</span>
            </div>
          )}
          {formatDuration(episode.duration) && (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{formatDuration(episode.duration)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
