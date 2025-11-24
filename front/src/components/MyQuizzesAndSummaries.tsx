import { useState, useEffect, useMemo } from "react";
import { ArrowLeft, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { EpisodesService, Episode } from "../services/episodesService";
import EpisodeCard from "./EpisodeCard";

interface MyQuizzesAndSummariesProps {
  token: string;
  onBack: () => void;
}

type ViewMode = "recent" | "by-podcast";

interface PodcastGroup {
  podcast_id: string;
  podcast_title: string;
  podcast_image: string;
  episodes: Episode[];
}

export default function MyQuizzesAndSummaries({
  token,
  onBack,
}: MyQuizzesAndSummariesProps) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("recent");
  const [selectedPodcast, setSelectedPodcast] = useState<string | null>(null);

  useEffect(() => {
    loadEpisodes();
  }, [token]);

  const loadEpisodes = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await EpisodesService.getMyEpisodes(token);
      setEpisodes(response.episodes);
    } catch (err) {
      console.error("Failed to load episodes:", err);
      setError(
        err instanceof Error ? err.message : "Failed to load episodes"
      );
    } finally {
      setLoading(false);
    }
  };

  // Group episodes by podcast
  const podcastGroups = useMemo(() => {
    const groups: Record<string, PodcastGroup> = {};

    episodes.forEach((episode) => {
      const key = episode.podcast_id || episode.podcast_title;

      if (!groups[key]) {
        groups[key] = {
          podcast_id: key,
          podcast_title: episode.podcast_title,
          podcast_image: episode.episode_image,
          episodes: [],
        };
      }
      groups[key].episodes.push(episode);
    });

    // Sort episodes within each group by created_at DESC
    Object.values(groups).forEach((group) => {
      group.episodes.sort((a, b) => b.created_at - a.created_at);
    });

    return Object.values(groups).sort((a, b) =>
      a.podcast_title.localeCompare(b.podcast_title)
    );
  }, [episodes]);

  // Get filtered episodes for selected podcast
  const filteredEpisodes = useMemo(() => {
    if (!selectedPodcast) return [];

    const group = podcastGroups.find(
      (g) => g.podcast_id === selectedPodcast
    );

    return group ? group.episodes : [];
  }, [selectedPodcast, podcastGroups]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <button
                onClick={selectedPodcast ? () => setSelectedPodcast(null) : onBack}
                className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>{selectedPodcast ? "Back to podcasts" : "Back"}</span>
              </button>
              <h1 className="text-xl font-bold text-gray-900">
                {selectedPodcast
                  ? podcastGroups.find((g) => g.podcast_id === selectedPodcast)?.podcast_title
                  : "My Quizzes & Summaries"}
              </h1>
            </div>

            <div className="flex items-center space-x-3">
              {/* Refresh Button */}
              <button
                onClick={loadEpisodes}
                disabled={loading}
                className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh episodes"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>

              {/* View Toggle */}
              {!selectedPodcast && episodes.length > 0 && (
                <div className="flex items-center space-x-2 bg-gray-100 p-1 rounded-lg">
                  <button
                    onClick={() => setViewMode("recent")}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${viewMode === "recent"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                      }`}
                  >
                    Recent
                  </button>
                  <button
                    onClick={() => setViewMode("by-podcast")}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${viewMode === "by-podcast"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-600 hover:text-gray-900"
                      }`}
                  >
                    By Podcast
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Loading your episodes...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-red-800 mb-1">
                Loading error
              </h3>
              <p className="text-sm text-red-700">{error}</p>
              <button
                onClick={loadEpisodes}
                className="mt-3 text-sm text-red-700 underline hover:text-red-900"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {!loading && !error && episodes.length === 0 && (
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
              <svg
                className="w-8 h-8 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No episodes available
            </h3>
            <p className="text-gray-600 mb-6">
              You don't have any episodes with quizzes and summaries yet.
            </p>
            <button
              onClick={onBack}
              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Search for podcasts
            </button>
          </div>
        )}

        {!loading && !error && episodes.length > 0 && (
          <>
            {/* Recent View */}
            {viewMode === "recent" && !selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {episodes.length} episode{episodes.length > 1 ? "s" : ""} found
                  </p>
                </div>
                <div className="space-y-6">
                  {episodes.map((episode) => (
                    <EpisodeCard key={episode.job_id} episode={episode} />
                  ))}
                </div>
              </div>
            )}

            {/* By Podcast View - Podcast List */}
            {viewMode === "by-podcast" && !selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {podcastGroups.length} podcast{podcastGroups.length > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {podcastGroups.map((group) => (
                    <button
                      key={group.podcast_id}
                      onClick={() => setSelectedPodcast(group.podcast_id)}
                      className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-6 text-left"
                    >
                      <div className="flex items-start space-x-4">
                        <div className="w-20 h-20 flex-shrink-0">
                          {group.podcast_image ? (
                            <img
                              src={group.podcast_image}
                              alt={group.podcast_title}
                              className="w-full h-full object-cover rounded-lg"
                              onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                target.src =
                                  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80'%3E%3Crect width='80' height='80' fill='%23e5e7eb'/%3E%3C/svg%3E";
                              }}
                            />
                          ) : (
                            <div className="w-full h-full bg-gray-200 rounded-lg" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-lg font-semibold text-gray-900 mb-1 truncate">
                            {group.podcast_title}
                          </h3>
                          <p className="text-sm text-gray-600">
                            {group.episodes.length} episode{group.episodes.length > 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* By Podcast View - Episode List */}
            {selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {filteredEpisodes.length} episode{filteredEpisodes.length > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="space-y-6">
                  {filteredEpisodes.map((episode) => (
                    <EpisodeCard key={episode.job_id} episode={episode} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
