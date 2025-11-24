import { useState, useEffect } from "react";
import { Loader2, BookOpen, DollarSign } from "lucide-react";
import { AuthService } from "../services/authService";
import { AuthUser } from "../types/auth";
import SpotifyIntegrationHome from "./ui/spotify-integration-home";
import SpotifyPlaylists from "./SpotifyPlaylists";
import MyQuizzesAndSummaries from "./MyQuizzesAndSummaries";
import { SpotifyService } from "../services/spotifyService";
import AccountSettingsDropdown from "./AccountSettingsDropdown";
import AccountSettings from "./AccountSettings";
import SubscriptionManagement from "./SubscriptionManagement";
import PaymentMethods from "./PaymentMethods";
import PricingPage from "./PricingPage";

interface DashboardProps {
  token: string;
  onLogout: () => void;
}

export default function Dashboard({ token, onLogout }: DashboardProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingSpotify, setCheckingSpotify] = useState(false);
  const [spotifyError, setSpotifyError] = useState<string | null>(null);
  const [showSpotifyPlaylists, setShowSpotifyPlaylists] = useState(false);
  const [showMyEpisodes, setShowMyEpisodes] = useState(false);
  const [showPricing, setShowPricing] = useState(false);
  const [currentSettingsPage, setCurrentSettingsPage] = useState<
    "account" | "subscription" | "payment" | null
  >(null);

  useEffect(() => {
    loadUser();

    // Check if user just linked Spotify
    const spotifyJustLinked = localStorage.getItem("spotify_just_linked");
    if (spotifyJustLinked === "true") {
      localStorage.removeItem("spotify_just_linked");
      setShowSpotifyPlaylists(true);
    }
  }, [token]);

  const loadUser = async () => {
    try {
      const userData = await AuthService.getCurrentUser(token);
      setUser(userData);
    } catch (error) {
      console.error("Failed to load user:", error);
      if (error instanceof Error && error.message.includes("401")) {
        AuthService.clearToken();
        onLogout();
      }
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
        // Already linked, show playlists page
        setShowSpotifyPlaylists(true);
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  // Show pricing page if requested
  if (showPricing) {
    return <PricingPage onBack={() => setShowPricing(false)} />;
  }

  // Show settings pages if requested
  if (currentSettingsPage === "account" && user) {
    return (
      <AccountSettings
        token={token}
        userEmail={user.email}
        userId={user.id}
        onBack={() => setCurrentSettingsPage(null)}
      />
    );
  }

  if (currentSettingsPage === "subscription") {
    return (
      <SubscriptionManagement
        token={token}
        onBack={() => setCurrentSettingsPage(null)}
      />
    );
  }

  if (currentSettingsPage === "payment") {
    return (
      <PaymentMethods
        token={token}
        onBack={() => setCurrentSettingsPage(null)}
      />
    );
  }

  // Show My Episodes page if requested
  if (showMyEpisodes) {
    return (
      <MyQuizzesAndSummaries
        token={token}
        onBack={() => setShowMyEpisodes(false)}
      />
    );
  }

  // Show Spotify playlists manager if requested
  if (showSpotifyPlaylists) {
    return (
      <SpotifyPlaylists
        token={token}
        onBack={() => setShowSpotifyPlaylists(false)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black relative">
      {/* Header with logout */}
      <nav className="absolute top-0 right-0 left-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-end items-center h-16">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowPricing(true)}
                className="flex items-center space-x-2 px-4 py-2 text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              >
                <DollarSign className="h-4 w-4" />
                <span>Pricing</span>
              </button>
              <button
                onClick={() => setShowMyEpisodes(true)}
                className="flex items-center space-x-2 px-4 py-2 text-sm font-semibold bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg shadow-sm hover:shadow-md transition"
              >
                <BookOpen className="h-4 w-4" />
                <span>My Quizzes & Summaries</span>
              </button>
              {user && (
                <AccountSettingsDropdown
                  onNavigate={(page) => setCurrentSettingsPage(page)}
                  onLogout={handleLogout}
                  userEmail={user.email}
                />
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main content - Spotify Integration */}
      <div onClick={handleSpotifyClick} className="cursor-pointer">
        {checkingSpotify ? (
          <div className="min-h-screen flex items-center justify-center">
            <Loader2 className="h-12 w-12 animate-spin text-green-600" />
          </div>
        ) : (
          <SpotifyIntegrationHome />
        )}
      </div>

      {/* Error message */}
      {spotifyError && (
        <div className="fixed bottom-8 right-8 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4 shadow-lg max-w-md z-30">
          <p className="text-sm text-red-800">{spotifyError}</p>
        </div>
      )}
    </div>
  );
}
