import { useState, useEffect } from "react";
import { ArrowLeft, Loader2, Music, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";
import { SpotifyService } from "../services/spotifyService";

interface SpotifyPlaylistsProps {
  token: string;
  onBack: () => void;
}

interface Playlist {
  id: string;
  name: string;
  images: Array<{ url: string; height: number; width: number }>;
  tracks_total: number;
  owner_name: string;
  collaborative: boolean;
  public: boolean | null;
  enabled: boolean;
}

export default function SpotifyPlaylists({ token, onBack }: SpotifyPlaylistsProps) {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<"success" | "error">("success");
  const [processingPlaylistId, setProcessingPlaylistId] = useState<string | null>(null);

  useEffect(() => {
    const abortController = new AbortController();
    loadPlaylists(abortController.signal);
    return () => abortController.abort();
  }, []);

  const loadPlaylists = async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setError(null);
      const data = await SpotifyService.getPlaylists(token, signal);
      if (signal?.aborted) return;
      setPlaylists(data);
    } catch (err) {
      if (signal?.aborted) return;
      if (err instanceof Error && err.name === 'AbortError') return;

      setError(err instanceof Error ? err.message : "Failed to load playlists");
      setPlaylists([]);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  const handleToggle = async (playlistId: string, currentState: boolean) => {
    const newState = !currentState;
    setProcessingPlaylistId(playlistId);

    try {
      const result = await SpotifyService.updateSubscription(token, playlistId, newState);

      // Update local state
      setPlaylists(prev =>
        prev.map(pl =>
          pl.id === playlistId ? { ...pl, enabled: result.enabled } : pl
        )
      );

      if (newState) {
        // Fetch sync result to show how many episodes were enqueued
        // Note: The subscription endpoint triggers sync automatically
        showToast("Synchronization started successfully!", "success");
      } else {
        showToast("Tracking disabled", "success");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update playlist");
      showToast("Error updating playlist", "error");
    } finally {
      setProcessingPlaylistId(null);
    }
  };

  const showToast = (message: string, type: "success" | "error") => {
    setToastMessage(message);
    setToastType(type);
    setTimeout(() => setToastMessage(null), 5000);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-50">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-blue-800 font-medium animate-pulse">
          Searching for your Spotify playlists containing podcast episodes...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={onBack}
              className="flex items-center space-x-2 text-gray-700 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
              <span className="font-medium">Back to Dashboard</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Informational header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold text-gray-900">
              Track Your Podcast Playlists
            </h1>
            <button
              onClick={() => loadPlaylists()}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>

          {/* Explanation card */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-blue-900 mb-3">
              📚 How it works
            </h2>
            <div className="space-y-3 text-blue-800">
              <p className="text-sm">
                <strong>Only playlists containing podcast episodes are displayed here.</strong> Music-only playlists are automatically filtered out.
              </p>
              <p className="text-sm">
                <strong>To get started:</strong>
              </p>
              <ol className="text-sm space-y-2 ml-4 list-decimal">
                <li>Create a dedicated playlist in Spotify for the podcast episodes you want to track</li>
                <li>Add the podcast episodes you wish to have summarized to this playlist</li>
                <li>Enable tracking for the playlist using the toggle below</li>
                <li>Listen to the episodes in your playlist</li>
              </ol>
              <p className="text-sm">
                <strong>🎯 Automatic processing:</strong> Once you've listened to more than 80% of an episode, we'll automatically generate a personalized quiz and summary for you!
              </p>
            </div>
          </div>
        </div>

        {error && playlists.length > 0 && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {playlists.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-lg p-12 text-center max-w-2xl mx-auto">
            <Music className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-3">
              No podcast playlists found
            </h3>
            <div className="text-gray-600 space-y-4 text-left">
              <p>
                We couldn't find any playlists containing podcast episodes in your Spotify account.
              </p>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="font-semibold text-gray-900 mb-2">
                  📝 To create a trackable podcast playlist:
                </p>
                <ol className="text-sm space-y-2 ml-4 list-decimal">
                  <li>Open Spotify and create a new playlist</li>
                  <li>Add podcast episodes (not music tracks) to this playlist</li>
                  <li>
                    <button
                      onClick={() => loadPlaylists()}
                      className="text-blue-600 hover:text-blue-800 font-medium inline-flex items-center"
                    >
                      Click here to refresh the list
                    </button>
                  </li>
                  <li>Enable tracking for your new playlist</li>
                </ol>
              </div>
              <p className="text-sm text-center">
                Your new playlist will appear here once it contains at least one podcast episode.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {playlists.map((playlist) => (
              <div
                key={playlist.id}
                className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden"
              >
                {/* Playlist image */}
                <div className="relative h-48 bg-gradient-to-br from-green-400 to-blue-500">
                  {playlist.images.length > 0 ? (
                    <img
                      src={playlist.images[0].url}
                      alt={playlist.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Music className="h-16 w-16 text-white opacity-50" />
                    </div>
                  )}
                </div>

                {/* Playlist info */}
                <div className="p-4">
                  <h3 className="font-semibold text-gray-900 mb-1 truncate">
                    {playlist.name}
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">
                    {playlist.tracks_total} tracks
                  </p>

                  {/* iOS-style toggle */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">
                      Tracking
                    </span>
                    <button
                      onClick={() => handleToggle(playlist.id, playlist.enabled)}
                      disabled={processingPlaylistId === playlist.id}
                      className={`
                        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                        ${playlist.enabled ? "bg-green-500" : "bg-gray-300"}
                        ${processingPlaylistId === playlist.id ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
                      `}
                    >
                      <span
                        className={`
                          inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                          ${playlist.enabled ? "translate-x-6" : "translate-x-1"}
                        `}
                      />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Toast notification */}
      {toastMessage && (
        <div className={`
          fixed bottom-8 right-8 rounded-lg p-4 shadow-lg max-w-md z-30 flex items-start space-x-3
          ${toastType === "success" ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}
        `}>
          {toastType === "success" ? (
            <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
          )}
          <p className={`text-sm ${toastType === "success" ? "text-green-800" : "text-red-800"}`}>
            {toastMessage}
          </p>
        </div>
      )}
    </div>
  );
}
