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
import PodcastSearch from "./PodcastSearch";
import MinutesDisplay from "./MinutesDisplay";
import { MinutesProvider, useMinutes } from "../contexts/MinutesContext";

interface DashboardProps {
  token: string;
  onLogout: () => void;
}

export default function Dashboard({ token, onLogout }: DashboardProps) {
  return (
    <MinutesProvider token={token}>
      <DashboardContent token={token} onLogout={onLogout} />
    </MinutesProvider>
  );
}

function DashboardContent({ token, onLogout }: DashboardProps) {
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

  // Get minutes from context
  const { availableMinutes, loadingMinutes } = useMinutes();

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
    return <PricingPage onBack={() => setShowPricing(false)} token={token} />;
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
        onShowPricing={() => {
          setShowSpotifyPlaylists(false);
          setShowPricing(true);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black relative">
      {/* Header with modern navigation layout */}
      <nav className="absolute top-0 right-0 left-0 z-20 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Left: Logo/Brand */}
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
                  <BookOpen className="h-5 w-5 text-white" />
                </div>
                <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  PodQuiz
                </span>
              </div>

              {/* Primary Action: My Summaries */}
              <button
                onClick={() => setShowMyEpisodes(true)}
                className="hidden md:flex items-center space-x-2 px-4 py-2 text-sm font-semibold text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                <span>My Summaries</span>
              </button>
            </div>

            {/* Right: Secondary actions and user menu */}
            <div className="flex items-center space-x-3">
              {/* Minutes Display - More compact */}
              <MinutesDisplay
                minutes={availableMinutes}
                loading={loadingMinutes}
              />

              {/* Pricing Button */}
              <button
                onClick={() => setShowPricing(true)}
                className="hidden sm:flex items-center space-x-1 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              >
                <DollarSign className="h-4 w-4" />
                <span>Pricing</span>
              </button>

              {/* User Profile Dropdown */}
              {user && (
                <AccountSettingsDropdown
                  onNavigate={(page) => setCurrentSettingsPage(page)}
                  onShowPricing={() => setShowPricing(true)}
                  onShowMySummaries={() => setShowMyEpisodes(true)}
                  onLogout={handleLogout}
                  userEmail={user.email}
                />
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main content - Spotify Integration */}
      <div className="w-full">
        {checkingSpotify ? (
          <div className="min-h-screen flex items-center justify-center">
            <Loader2 className="h-12 w-12 animate-spin text-green-600" />
          </div>
        ) : (
          <SpotifyIntegrationHome onConnect={handleSpotifyClick}>
            <div className="flex flex-col items-center gap-8 w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300 fill-mode-forwards">
              <div className="flex items-center gap-4 w-full">
                <div className="h-px bg-gray-300 dark:bg-gray-700 flex-1"></div>
                <span className="text-gray-500 dark:text-gray-400 font-medium text-lg">
                  OR
                </span>
                <div className="h-px bg-gray-300 dark:bg-gray-700 flex-1"></div>
              </div>

              <div className="w-full">
                <PodcastSearch token={token} />
              </div>
            </div>
          </SpotifyIntegrationHome>
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
