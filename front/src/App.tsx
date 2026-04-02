import { useState, useEffect, useRef } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";
import AuthForm from "./components/AuthForm";
import Dashboard from "./components/Dashboard";
import OAuthCallback from "./components/OAuthCallback";
import LandingPage from "./components/LandingPage";
import PricingPage from "./components/PricingPage";
import EmailVerification from "./components/EmailVerification";
import TermsPage from "./components/TermsPage";
import PrivacyPage from "./components/PrivacyPage";
import Footer from "./components/Footer";
import { AuthService } from "./services/authService";

// Protected Route wrapper component
function ProtectedRoute({
  token,
  children,
}: {
  token: string | null;
  children: React.ReactNode;
}) {
  const location = useLocation();

  if (!token) {
    // Redirect to login, but save the attempted location
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// Layout component that includes footer for public pages
function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1">{children}</div>
      <Footer />
    </div>
  );
}

// Main App content with routing
function AppContent() {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const initStartedRef = useRef(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (initStartedRef.current) {
      return;
    }
    initStartedRef.current = true;

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

  useEffect(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    if (!token) {
      return () => undefined;
    }

    const expiryRaw = localStorage.getItem("token_expiry");
    const expiryTime = expiryRaw ? Number(expiryRaw) : NaN;
    if (!Number.isFinite(expiryTime)) {
      return () => undefined;
    }

    const bufferMs = 2000; // refresh slightly before expiry
    const delayMs = Math.max(0, expiryTime - Date.now() - bufferMs);

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const response = await AuthService.refresh();
        setToken(response.access_token);
      } catch (error) {
        console.error("Background token refresh failed:", error);
        setToken(null);
      }
    }, delayMs);

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [token]);

  const handleAuthSuccess = (newToken: string) => {
    console.log("[App] handleAuthSuccess called with token");
    setToken(newToken);

    // Redirect to the page they were trying to access, or dashboard
    const from =
      (location.state as { from?: Location })?.from?.pathname || "/dashboard";
    navigate(from, { replace: true });
  };

  const handleLogout = () => {
    AuthService.clearToken();
    setToken(null);
    navigate("/");
  };

  const handleGetStarted = () => {
    navigate("/register");
  };

  const handleBackToLanding = () => {
    navigate("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-pulse text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/"
        element={
          token ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <LandingPage
              onGetStarted={handleGetStarted}
            />
          )
        }
      />

      <Route
        path="/login"
        element={
          token ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
              <div className="relative w-full max-w-md">
                <button
                  onClick={handleBackToLanding}
                  className="absolute -top-12 left-0 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition-colors"
                >
                  ← Back to home
                </button>
                <AuthForm onSuccess={handleAuthSuccess} initialMode="login" />
              </div>
            </div>
          )
        }
      />

      <Route
        path="/register"
        element={
          token ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
              <div className="relative w-full max-w-md">
                <button
                  onClick={handleBackToLanding}
                  className="absolute -top-12 left-0 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition-colors"
                >
                  ← Back to home
                </button>
                <AuthForm
                  onSuccess={handleAuthSuccess}
                  initialMode="register"
                />
              </div>
            </div>
          )
        }
      />

      <Route path="/verify-email" element={<EmailVerification />} />

      <Route
        path="/pricing"
        element={
          <PricingPage
            onBack={handleBackToLanding}
            token={token || undefined}
            onSignIn={handleGetStarted}
          />
        }
      />

      <Route
        path="/terms"
        element={
          <PublicLayout>
            <TermsPage onBack={handleBackToLanding} />
          </PublicLayout>
        }
      />

      <Route
        path="/privacy"
        element={
          <PublicLayout>
            <PrivacyPage />
          </PublicLayout>
        }
      />

      {/* OAuth callbacks */}
      <Route
        path="/auth/callback-success"
        element={<OAuthCallback onSuccess={handleAuthSuccess} />}
      />
      <Route
        path="/auth/callback-error"
        element={<OAuthCallback onSuccess={handleAuthSuccess} />}
      />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute token={token}>
            <Dashboard token={token!} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
