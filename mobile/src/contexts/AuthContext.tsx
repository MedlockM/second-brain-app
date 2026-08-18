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
  loginWithGoogle: (idToken: string) => Promise<void>;
  loginWithApple: (identityToken: string, user?: { email?: string; fullName?: { givenName?: string; familyName?: string } }) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-read SecureStore and refresh the access token when needed. */
  revalidateSession: () => Promise<boolean>;
  clearSessionError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Buffer before token expiry to trigger proactive refresh (in ms).
 */
const REFRESH_BUFFER_MS = 5000;

async function scheduleTokenRefresh(
  timerRef: { current: ReturnType<typeof setTimeout> | null },
  setAuthState: React.Dispatch<React.SetStateAction<AuthState>>,
): Promise<void> {
  if (timerRef.current) {
    clearTimeout(timerRef.current);
    timerRef.current = null;
  }

  const expiry = await TokenStorage.getTokenExpiry();
  if (!expiry) return;

  const delayMs = Math.max(0, expiry - Date.now() - REFRESH_BUFFER_MS);

  timerRef.current = setTimeout(async () => {
    try {
      const response = await AuthService.refresh();
      setAuthState((previous) => ({
        ...previous,
        token: response.access_token,
        user: response.user,
      }));
      await scheduleTokenRefresh(timerRef, setAuthState);
    } catch {
      setAuthState({
        user: null,
        token: null,
        isLoading: false,
        isAuthenticated: false,
        sessionError: "Your session has expired. Please sign in again.",
      });
    }
  }, delayMs);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
    isAuthenticated: false,
    sessionError: null,
  });

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const revalidationRef = useRef<Promise<boolean> | null>(null);
  const initStartedRef = useRef(false);

  // Schedule proactive token refresh before expiry
  const scheduleRefresh = useCallback(async () => {
    await scheduleTokenRefresh(refreshTimerRef, setState);
  }, []);

  const revalidateSession = useCallback((): Promise<boolean> => {
    if (revalidationRef.current) {
      return revalidationRef.current;
    }

    const operation = (async () => {
      try {
        const validToken = await AuthService.getValidToken();
        if (!validToken) {
          if (refreshTimerRef.current) {
            clearTimeout(refreshTimerRef.current);
            refreshTimerRef.current = null;
          }
          await TokenStorage.clearAll();
          setState({
            user: null,
            token: null,
            isLoading: false,
            isAuthenticated: false,
            sessionError: "Your session has expired. Please sign in again.",
          });
          return false;
        }

        setState((previous) => ({
          ...previous,
          token: validToken,
          isLoading: false,
          isAuthenticated: true,
          sessionError: null,
        }));
        await scheduleRefresh();
        return true;
      } catch {
        if (refreshTimerRef.current) {
          clearTimeout(refreshTimerRef.current);
          refreshTimerRef.current = null;
        }
        await TokenStorage.clearAll();
        setState({
          user: null,
          token: null,
          isLoading: false,
          isAuthenticated: false,
          sessionError: "Your session has expired. Please sign in again.",
        });
        return false;
      }
    })();

    revalidationRef.current = operation;
    void operation.finally(() => {
      if (revalidationRef.current === operation) {
        revalidationRef.current = null;
      }
    });
    return operation;
  }, [scheduleRefresh]);

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

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      const response = await AuthService.loginWithGoogleNative(idToken);
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

  const loginWithApple = useCallback(
    async (
      identityToken: string,
      user?: { email?: string; fullName?: { givenName?: string; familyName?: string } },
    ) => {
      const response = await AuthService.loginWithAppleNative(identityToken, user);
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
    loginWithGoogle,
    loginWithApple,
    logout,
    revalidateSession,
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
