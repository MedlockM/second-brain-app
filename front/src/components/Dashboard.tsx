import { useState, useEffect } from "react";
import { LogOut, User, Loader2 } from "lucide-react";
import { AuthService } from "../services/authService";
import { AuthUser } from "../types/auth";
import PodcastSearch from "./PodcastSearch";
import SpotifySync from "./SpotifySync";
import { SpotifyService } from "../services/spotifyService";

interface DashboardProps {
  token: string;
  onLogout: () => void;
}

export default function Dashboard({ token, onLogout }: DashboardProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [showSpotifySync, setShowSpotifySync] = useState(false);
  const [checkingSpotify, setCheckingSpotify] = useState(false);
  const [spotifyError, setSpotifyError] = useState<string | null>(null);

  useEffect(() => {
    loadUser();
  }, [token]);

  const loadUser = async () => {
    try {
      if (token === "preview-mode-token") {
        setUser({ id: "preview-user", email: "preview@example.com" });
      } else {
        const userData = await AuthService.getCurrentUser(token);
        setUser(userData);
      }
    } catch (error) {
      console.error("Failed to load user:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await AuthService.logout(token);
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      AuthService.clearToken();
      onLogout();
    }
  };

  const handleSpotifyClick = async () => {
    setCheckingSpotify(true);
    setSpotifyError(null);

    try {
      const status = await SpotifyService.checkStatus(token);

      if (status.linked) {
        setShowSpotifySync(true);
      } else {
        await SpotifyService.linkAccount(token);
      }
    } catch (error) {
      setSpotifyError(
        error instanceof Error ? error.message : "Failed to connect to Spotify",
      );
    } finally {
      setCheckingSpotify(false);
    }
  };

  const handleBackFromSpotify = () => {
    setShowSpotifySync(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (showSpotifySync) {
    return <SpotifySync token={token} onBack={handleBackFromSpotify} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <div className="flex-1">
        <nav className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  Media Summarizer
                </h1>
              </div>
              <div className="flex items-center space-x-4">
                {user && (
                  <div className="flex items-center space-x-2 text-sm text-gray-700">
                    <User className="h-5 w-5" />
                    <span>{user.email}</span>
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Logout</span>
                </button>
              </div>
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <PodcastSearch token={token} />
        </main>
      </div>

      <aside className="w-20 bg-white border-l border-gray-200 flex flex-col items-center py-8 space-y-4">
        <button
          onClick={handleSpotifyClick}
          disabled={checkingSpotify}
          className="relative group p-3 rounded-xl hover:bg-gray-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title="Spotify Integration"
        >
          {checkingSpotify ? (
            <Loader2 className="h-8 w-8 animate-spin text-green-600" />
          ) : (
            <svg
              className="w-8 h-8 text-green-600"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
            </svg>
          )}
          <span className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Spotify
          </span>
        </button>

        {spotifyError && (
          <div className="absolute top-24 right-24 bg-red-50 border border-red-200 rounded-lg p-3 shadow-lg max-w-xs">
            <p className="text-xs text-red-800">{spotifyError}</p>
          </div>
        )}
      </aside>
    </div>
  );
}
