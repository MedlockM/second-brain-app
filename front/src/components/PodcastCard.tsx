import { Podcast } from '../types/podcast';
import { ExternalLink, Mic } from 'lucide-react';

interface PodcastCardProps {
  podcast: Podcast;
  onClick?: (podcast: Podcast) => void;
}

export default function PodcastCard({ podcast, onClick }: PodcastCardProps) {
  return (
    <div
      className={`bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow ${onClick ? 'cursor-pointer' : ''}`}
      onClick={() => onClick?.(podcast)}
    >
      <div className="aspect-square relative bg-gray-100">
        {podcast.image ? (
          <img
            src={podcast.image}
            alt={podcast.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Mic className="h-16 w-16 text-gray-400" />
          </div>
        )}
      </div>

      <div className="p-4">
        <h3 className="font-semibold text-gray-900 text-lg mb-1 line-clamp-2">
          {podcast.title}
        </h3>
        <p className="text-sm text-gray-600 mb-3">{podcast.author}</p>

        {podcast.description && (
          <p className="text-sm text-gray-700 line-clamp-3 mb-4">
            {podcast.description}
          </p>
        )}

        {podcast.categories && podcast.categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {podcast.categories.slice(0, 3).map((category, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-full"
              >
                {category}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-gray-200">
          {podcast.episode_count !== undefined && (
            <span className="text-sm text-gray-500">
              {podcast.episode_count} episodes
            </span>
          )}
          {podcast.website && (
            <a
              href={podcast.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
