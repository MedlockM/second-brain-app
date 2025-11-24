import { useState, useEffect } from "react";
import AuthForm from "./components/AuthForm";
import Dashboard from "./components/Dashboard";
import OAuthCallback from "./components/OAuthCallback";
import LandingPage from "./components/LandingPage";
import PricingPage from "./components/PricingPage";
import { AuthService } from "./services/authService";

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOAuthCallback, setIsOAuthCallback] = useState(false);
  const [showAuthForm, setShowAuthForm] = useState(false);
  const [showPricing, setShowPricing] = useState(false);

  useEffect(() => {
    // Check if this is an OAuth callback
    const path = window.location.pathname;
    if (
      path.includes("/auth/callback-success") ||
      path.includes("/auth/callback-error")
    ) {
      setIsOAuthCallback(true);
      setLoading(false);
      return;
    }

    // Try to get a valid token (will refresh if expired)
    const initAuth = async () => {
      const validToken = await AuthService.getValidToken();
      if (validToken) {
        setToken(validToken);
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const handleAuthSuccess = (newToken: string) => {
    console.log("[App] handleAuthSuccess called with token");
    setToken(newToken);
    setIsOAuthCallback(false);
    setShowAuthForm(false);
    setShowPricing(false);
  };

  const handleGetStarted = () => {
    setShowAuthForm(true);
    setShowPricing(false);
  };

  const handlePricingClick = () => {
    setShowPricing(true);
    setShowAuthForm(false);
  };

  const handleBackToLanding = () => {
    setShowAuthForm(false);
    setShowPricing(false);
  };

  const handleLogout = () => {
    setToken(null);
    setShowPricing(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-pulse text-gray-600">Loading...</div>
      </div>
    );
  }

  // Handle OAuth callbacks
  if (isOAuthCallback) {
    return <OAuthCallback onSuccess={handleAuthSuccess} />;
  }

  // Show auth form or landing page for non-authenticated users
  if (!token) {
    // Show pricing page
    if (showPricing) {
      return <PricingPage onBack={handleBackToLanding} />;
    }

    if (showAuthForm) {
      return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
          <div className="relative w-full max-w-md">
            <button
              onClick={handleBackToLanding}
              className="absolute -top-12 left-0 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition-colors"
            >
              ← Back to home
            </button>
            <AuthForm onSuccess={handleAuthSuccess} />
          </div>
        </div>
      );
    }

    return (
      <LandingPage
        onGetStarted={handleGetStarted}
        onPricingClick={handlePricingClick}
      />
    );
  }

  return <Dashboard token={token} onLogout={handleLogout} />;
}

export default App;

