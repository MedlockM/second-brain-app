import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { ArrowLeft, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { EpisodesService, Episode } from "../services/episodesService";
import { PodcastService, Job } from "../services/podcastService";
import EpisodeCard from "./EpisodeCard";
import { useMinutes } from "../contexts/MinutesContext";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";

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

/**
 * Some backends may attach extra optional fields to Job objects (feed_id, podcast_id, podcast_image).
 * We don't want to change the canonical `Job` interface, so model the extended shape as an intersection
 * with Partial<> to avoid TypeScript incompatibility issues.
 */
type ExtendedJob = Job &
  Partial<{
    feed_id: number;
    podcast_id: string;
    podcast_image: string;
    episode_image: string;
  }>;



export default function MyQuizzesAndSummaries({
  token,
  onBack,
}: MyQuizzesAndSummariesProps) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [allJobs, setAllJobs] = useState<ExtendedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("recent");
  const [selectedPodcast, setSelectedPodcast] = useState<string | null>(null);
  const { refreshMinutes } = useMinutes();

  // We'll track initial load so poll errors don't spam the UI after the first successful load.
  const initialLoadRef = useRef(true);

  // Fetch active jobs and episodes
  const loadData = useCallback(async (showErrors = false) => {
    try {
      setError(null);
      if (!token) {
        console.warn("MyQuizzesAndSummaries: No token provided");
        setLoading(false);
        return;
      }

      const [episodesResp, jobsResp] = await Promise.all([
        EpisodesService.getMyEpisodes(token),
        PodcastService.getUserJobs(token),
      ]);

      setEpisodes(episodesResp.episodes || []);

      // Store all jobs (both active and completed)
      const jobs = jobsResp.jobs || [];
      console.log('Jobs fetched:', jobs);
      const activeJobsList = jobs.filter((j) => j.status !== "completed" && j.status !== "failed");
      console.log('Active jobs:', activeJobsList);
      setAllJobs(jobs as ExtendedJob[]);

      if (activeJobsList.length > 0) {
        refreshMinutes();
      }
    } catch (err) {
      console.error("Failed to load data:", err);
      const status = (err as { status?: number }).status;
      const code = (err as { code?: string }).code;
      const isSessionExpired =
        status === 401 || code === "SESSION_EXPIRED";
      if (initialLoadRef.current || showErrors || isSessionExpired) {
        setError(getFriendlyErrorMessage(err));
      }
    } finally {
      setLoading(false);
      initialLoadRef.current = false;
    }
  }, [token, refreshMinutes]);

  const didInitRef = useRef(false);

  useEffect(() => {
    if (!token || didInitRef.current) return;

    didInitRef.current = true;
    setLoading(true);
    loadData();
  }, [token, loadData]);

  // Separate active and completed/failed jobs
  const activeJobs = useMemo(
    () => allJobs.filter((j) => j.status !== "completed" && j.status !== "failed"),
    [allJobs]
  );



  // Build a pseudo-episode for each active job and compute combined list
  const combinedEpisodes = useMemo(() => {
    const pseudoFromJob = activeJobs.map((job) => {
      const j = job;
      // Use feed_id if available to group by podcast; otherwise fall back to job.podcast_id (if present) or podcast title
      const podcastId = j.feed_id ? String(j.feed_id) : j.podcast_id || "";

      const createdAt =
        // job.created_at comes from the backend as an ISO string in PodcastService.Job
        // Convert to unix timestamp (seconds) as EpisodesService.Episode expects.
        j.created_at ? Math.floor(new Date(j.created_at).getTime() / 1000) : 0;

      const pseudo: Episode & {
        // additional runtime-only fields to render processing state
        status?: Job["status"];
        progress?: number;
        isJob?: boolean;
      } = {
        job_id: j.job_id,
        podcast_title: j.podcast_title || "Unknown Podcast",
        podcast_id: podcastId,
        episode_title: j.episode_title || "Processing...",
        episode_image: j.episode_image || j.podcast_image || "",
        episode_date_published: j.episode_date_published || 0,
        created_at: createdAt,
        summary: {
          main_topics: [],
          key_points: [],
          notable_quotes: [],
          conclusion: "",
        },
        quiz: {
          id: "",
          language: "",
          questions: [],
        },
        // runtime-only
        status: j.status,
        progress: j.progress,
        isJob: true,
      };

      return pseudo as Episode;
    });

    // Combine pseudo episodes (jobs) with real episodes (from EpisodesService)
    // and sort by created_at DESC so recent items appear first.
    const combined = [...pseudoFromJob, ...episodes];
    combined.sort((a, b) => b.created_at - a.created_at);
    return combined;
  }, [episodes, activeJobs]);

  // Group combined episodes by podcast for the "By Podcast" view
  const podcastGroups = useMemo(() => {
    const groups: Record<string, PodcastGroup> = {};

    combinedEpisodes.forEach((item) => {
      const key = item.podcast_id || item.podcast_title || "Processing";

      if (!groups[key]) {
        groups[key] = {
          podcast_id: key,
          podcast_title: item.podcast_title,
          podcast_image: item.episode_image,
          episodes: [],
        };
      }
      groups[key].episodes.push(item);
    });

    // Sort episodes in each group by created_at desc
    Object.values(groups).forEach((g) =>
      g.episodes.sort((a, b) => b.created_at - a.created_at),
    );

    // Return sorted list of groups by title
    return Object.values(groups).sort((a, b) =>
      a.podcast_title.localeCompare(b.podcast_title),
    );
  }, [combinedEpisodes]);

  const filteredEpisodes = useMemo(() => {
    if (!selectedPodcast) return [];
    const group = podcastGroups.find((g) => g.podcast_id === selectedPodcast);
    return group ? group.episodes : [];
  }, [selectedPodcast, podcastGroups]);


  // UI
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <button
                onClick={
                  selectedPodcast ? () => setSelectedPodcast(null) : onBack
                }
                className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>{selectedPodcast ? "Back to podcasts" : "Back"}</span>
              </button>
              <h1 className="text-xl font-bold text-gray-900">
                {selectedPodcast
                  ? podcastGroups.find((g) => g.podcast_id === selectedPodcast)
                    ?.podcast_title
                  : "My Quizzes & Summaries"}
              </h1>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={loadData}
                disabled={loading}
                className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh episodes"
              >
                <RefreshCw
                  className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                />
                <span>Refresh</span>
              </button>

              {!selectedPodcast && (episodes.length > 0 || podcastGroups.length > 1) && (
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
                onClick={() => loadData(true)}
                className="mt-3 text-sm text-red-700 underline hover:text-red-900"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {!loading && !error && activeJobs.length === 0 && episodes.length === 0 && (
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

        {!loading && !error && combinedEpisodes.length > 0 && (
          <>
            {viewMode === "recent" && !selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {combinedEpisodes.length} item
                    {combinedEpisodes.length > 1 ? "s" : ""} found
                    {activeJobs.length > 0 && (
                      <span className="ml-2 text-blue-600">
                        ({activeJobs.length} in progress)
                      </span>
                    )}
                  </p>
                </div>
                <div className="space-y-6">
                  {combinedEpisodes.map((episode) => {
                    const anyEp = episode as any;
                    const status: 'processing' | 'completed' | 'failed' = anyEp.status === 'failed'
                      ? 'failed'
                      : anyEp.status && anyEp.status !== 'completed'
                        ? 'processing'
                        : 'completed';
                    const progress = typeof anyEp.progress === 'number' ? anyEp.progress : 0;
                    return (
                      <EpisodeCard key={episode.job_id} episode={episode} status={status} progress={progress} />
                    );
                  })}
                </div>
              </div>
            )}

            {viewMode === "by-podcast" && !selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {podcastGroups.length} podcast
                    {podcastGroups.length > 1 ? "s" : ""}
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
                            {group.episodes.length} episode
                            {group.episodes.length > 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectedPodcast && (
              <div>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {filteredEpisodes.length} episode
                    {filteredEpisodes.length > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="space-y-6">
                  {filteredEpisodes.map((episode) => {
                    const anyEp = episode as any;
                    const status: 'processing' | 'completed' | 'failed' = anyEp.status === 'failed'
                      ? 'failed'
                      : anyEp.status && anyEp.status !== 'completed'
                        ? 'processing'
                        : 'completed';
                    const progress = typeof anyEp.progress === 'number' ? anyEp.progress : 0;
                    return (
                      <EpisodeCard key={episode.job_id} episode={episode} status={status} progress={progress} />
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
