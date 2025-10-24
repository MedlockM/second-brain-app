import { useState, useEffect } from "react";
import AuthForm from "./components/AuthForm";
import Dashboard from "./components/Dashboard";
import OAuthCallback from "./components/OAuthCallback";
import { AuthService } from "./services/authService";

function App() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOAuthCallback, setIsOAuthCallback] = useState(false);

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

    const savedToken = AuthService.getToken();
    if (savedToken) {
      setToken(savedToken);
    } else {
      setToken("preview-mode-token");
    }
    setLoading(false);
  }, []);

  const handleAuthSuccess = (newToken: string) => {
    console.log("[App] handleAuthSuccess called with token");
    setToken(newToken);
    setIsOAuthCallback(false);
  };

  const handleLogout = () => {
    setToken(null);
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

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-gray-50 flex items-center justify-center p-4">
        <AuthForm onSuccess={handleAuthSuccess} />
      </div>
    );
  }

  return <Dashboard token={token} onLogout={handleLogout} />;
}

export default App;
