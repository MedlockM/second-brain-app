import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { AuthService } from "../services/authService";
import { TokenStorage } from "../services/tokenStorage";
import { AuthUser, LoginRequest, RegisterRequest } from "../types/auth";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** User-friendly error message from last auth failure, or null */
  sessionError: string | null;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearSessionError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Buffer before token expiry to trigger proactive refresh (in ms).
 */
const REFRESH_BUFFER_MS = 5000;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
    isAuthenticated: false,
    sessionError: null,
  });

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initStartedRef = useRef(false);

  // Schedule proactive token refresh before expiry
  const scheduleRefresh = useCallback(async () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    const expiry = await TokenStorage.getTokenExpiry();
    if (!expiry) return;

    const delayMs = Math.max(0, expiry - Date.now() - REFRESH_BUFFER_MS);

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const response = await AuthService.refresh();
        setState((prev) => ({
          ...prev,
          token: response.access_token,
          user: response.user,
        }));
        // Re-schedule after successful refresh
        scheduleRefresh();
      } catch {
        // Refresh failed - session expired
        setState({
          user: null,
          token: null,
          isLoading: false,
          isAuthenticated: false,
          sessionError: "Your session has expired. Please sign in again.",
        });
      }
    }, delayMs);
  }, []);

  // Initialize auth state on app start
  useEffect(() => {
    if (initStartedRef.current) return;
    initStartedRef.current = true;

    const initAuth = async () => {
      try {
        const validToken = await AuthService.getValidToken();
        if (validToken) {
          const user = await AuthService.getCurrentUser(validToken);
          setState({
            user,
            token: validToken,
            isLoading: false,
            isAuthenticated: true,
            sessionError: null,
          });
          scheduleRefresh();
        } else {
          setState((prev) => ({ ...prev, isLoading: false }));
        }
      } catch {
        await TokenStorage.clearAll();
        setState((prev) => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [scheduleRefresh]);

  const login = useCallback(
    async (data: LoginRequest) => {
      const response = await AuthService.login(data);
      setState({
        user: response.user,
        token: response.access_token,
        isLoading: false,
        isAuthenticated: true,
        sessionError: null,
      });
      scheduleRefresh();
    },
    [scheduleRefresh],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      const response = await AuthService.register(data);
      setState({
        user: response.user,
        token: response.access_token,
        isLoading: false,
        isAuthenticated: true,
        sessionError: null,
      });
      scheduleRefresh();
    },
    [scheduleRefresh],
  );

  const logout = useCallback(async () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (state.token) {
      await AuthService.logout(state.token);
    } else {
      await TokenStorage.clearAll();
    }
    setState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      sessionError: null,
    });
  }, [state.token]);

  const clearSessionError = useCallback(() => {
    setState((prev) => ({ ...prev, sessionError: null }));
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    register,
    logout,
    clearSessionError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth context. Must be used within AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
