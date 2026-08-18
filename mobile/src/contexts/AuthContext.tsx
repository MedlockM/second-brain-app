import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { AppState } from "react-native";
import { AuthService } from "../services/authService";
import { SessionManager } from "../services/sessionManager";
import { TokenStorage } from "../services/tokenStorage";
import { AuthUser, LoginRequest, RegisterRequest } from "../types/auth";

interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /**
   * The session is held but the API could not be reached on the last attempt.
   * The user stays in the app: requests will fail with network errors until it
   * comes back, and the next foreground or retry repairs the session.
   */
  isOffline: boolean;
  /** User-friendly error message from last auth failure, or null */
  sessionError: string | null;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  loginWithApple: (identityToken: string, user?: { email?: string; fullName?: { givenName?: string; familyName?: string } }) => Promise<void>;
  logout: () => Promise<void>;
  /**
   * Re-read the keychain and rotate the access token when needed.
   *
   * Resolves false only when the session is definitively gone — a refresh token
   * the backend refused, or none at all. A network failure resolves true: the
   * session is still the user's, so callers must not send them to the login
   * screen for it.
   */
  revalidateSession: () => Promise<boolean>;
  clearSessionError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * How long to wait before retrying a refresh that failed on transport grounds.
 * SessionManager already burned its own short backoff by then, so this is the
 * slow lane: it only has to catch connectivity coming back while the app is open.
 */
const OFFLINE_RETRY_DELAY_MS = 60_000;

const SIGNED_OUT_STATE: AuthState = {
  user: null,
  isLoading: false,
  isAuthenticated: false,
  isOffline: false,
  sessionError: null,
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    isOffline: false,
    sessionError: null,
  });

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const revalidationRef = useRef<Promise<boolean> | null>(null);
  const initStartedRef = useRef(false);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  /**
   * Arm the proactive refresh. Fire and forget on purpose: the outcome comes back
   * as a session event, which is what updates the state and re-arms this timer.
   *
   * A timer alone cannot be trusted — iOS and Android do not run it while the app
   * is backgrounded — which is why the AppState listener below revalidates on
   * every return to the foreground. This only covers a session left in front of
   * the user long enough for its access token to expire.
   */
  const scheduleRefresh = useCallback(
    async (delayOverrideMs?: number) => {
      clearRefreshTimer();
      const delayMs =
        delayOverrideMs ?? (await SessionManager.millisUntilProactiveRefresh());
      if (delayMs === null) return;

      refreshTimerRef.current = setTimeout(() => {
        void SessionManager.refreshAccessToken().catch(() => {
          // Already reported through the session events.
        });
      }, delayMs);
    },
    [clearRefreshTimer],
  );

  /**
   * The session is gone for good. Only ever reached from an authentication
   * rejection of the refresh token — never from a network failure.
   */
  const applyExpiredSession = useCallback(() => {
    clearRefreshTimer();
    setState((previous) =>
      previous.isAuthenticated
        ? {
            ...SIGNED_OUT_STATE,
            sessionError: SessionManager.SESSION_EXPIRED_MESSAGE,
          }
        : previous,
    );
  }, [clearRefreshTimer]);

  // Follow the session from wherever it was rotated: the timer above, the 401
  // interceptor in apiClient, or a revalidation. React state trails the keychain
  // instead of trying to own it.
  useEffect(() => {
    return SessionManager.subscribe((event) => {
      if (event.type === "refreshed") {
        setState((previous) =>
          previous.isAuthenticated
            ? {
                ...previous,
                user: event.user,
                isOffline: false,
                sessionError: null,
              }
            : previous,
        );
        void scheduleRefresh();
        return;
      }

      if (event.type === "unreachable") {
        setState((previous) =>
          previous.isAuthenticated ? { ...previous, isOffline: true } : previous,
        );
        void scheduleRefresh(OFFLINE_RETRY_DELAY_MS);
        return;
      }

      applyExpiredSession();
    });
  }, [applyExpiredSession, scheduleRefresh]);

  const revalidateSession = useCallback((): Promise<boolean> => {
    if (revalidationRef.current) {
      return revalidationRef.current;
    }

    const operation = (async () => {
      const status = await SessionManager.revalidate();

      if (status === "expired") {
        applyExpiredSession();
        return false;
      }

      if (status === "unreachable") {
        // Tokens kept, user kept. The retry lane takes over from here.
        setState((previous) => ({
          ...previous,
          isLoading: false,
          isOffline: true,
        }));
        await scheduleRefresh(OFFLINE_RETRY_DELAY_MS);
        return true;
      }

      // A live access token, so the session is usable — but it still needs a
      // profile to render with, and React may have none (a start that fell back
      // to signed-out while the API was unreachable). The keychain keeps one next
      // to the tokens, rewritten on every rotation, so it is never staler than
      // what React holds.
      let user = await TokenStorage.getUser();
      if (!user) {
        try {
          user = await AuthService.getCurrentUser();
          await TokenStorage.saveUser(user);
        } catch {
          // A live token with no identity behind it: the tokens stay, but there
          // is no session to show, so the caller routes to the login screen.
        }
      }

      if (!user) {
        setState(SIGNED_OUT_STATE);
        return false;
      }

      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
        isOffline: false,
        sessionError: null,
      });
      await scheduleRefresh();
      return true;
    })();

    revalidationRef.current = operation;
    void operation.finally(() => {
      if (revalidationRef.current === operation) {
        revalidationRef.current = null;
      }
    });
    return operation;
  }, [applyExpiredSession, scheduleRefresh]);

  // Restore the session on app start
  useEffect(() => {
    if (initStartedRef.current) return;
    initStartedRef.current = true;

    const initAuth = async () => {
      const status = await SessionManager.revalidate();

      if (status === "expired") {
        // No session to restore. Nothing expired under the user's feet, so the
        // login screen stays quiet.
        setState(SIGNED_OUT_STATE);
        return;
      }

      // The profile stored with the tokens is what makes an offline start work:
      // it is refreshed from /api/auth/me whenever the API answers.
      let user = await TokenStorage.getUser();
      if (status === "active") {
        try {
          user = await AuthService.getCurrentUser();
          await TokenStorage.saveUser(user);
        } catch (error) {
          if (SessionManager.isSessionRejection(error)) {
            setState({
              ...SIGNED_OUT_STATE,
              sessionError: SessionManager.SESSION_EXPIRED_MESSAGE,
            });
            return;
          }
          // Transient: keep whatever the keychain remembers.
        }
      }

      if (!user) {
        // Tokens without a profile and no way to fetch one: nothing to render a
        // session with. The tokens stay, so the next start restores it.
        setState(SIGNED_OUT_STATE);
        return;
      }

      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
        isOffline: status === "unreachable",
        sessionError: null,
      });
      await scheduleRefresh(
        status === "unreachable" ? OFFLINE_RETRY_DELAY_MS : undefined,
      );
    };

    void initAuth();
  }, [scheduleRefresh]);

  // Revalidate on every return to the foreground, independently of the timer:
  // a night in the background is the case the timer cannot cover.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState !== "active") return;
      void revalidateSession();
    });
    return () => subscription.remove();
  }, [revalidateSession]);

  useEffect(() => clearRefreshTimer, [clearRefreshTimer]);

  const login = useCallback(
    async (data: LoginRequest) => {
      const response = await AuthService.login(data);
      setState({
        user: response.user,
        isLoading: false,
        isAuthenticated: true,
        isOffline: false,
        sessionError: null,
      });
      await scheduleRefresh();
    },
    [scheduleRefresh],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      const response = await AuthService.register(data);
      setState({
        user: response.user,
        isLoading: false,
        isAuthenticated: true,
        isOffline: false,
        sessionError: null,
      });
      await scheduleRefresh();
    },
    [scheduleRefresh],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      const response = await AuthService.loginWithGoogleNative(idToken);
      setState({
        user: response.user,
        isLoading: false,
        isAuthenticated: true,
        isOffline: false,
        sessionError: null,
      });
      await scheduleRefresh();
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
        isLoading: false,
        isAuthenticated: true,
        isOffline: false,
        sessionError: null,
      });
      await scheduleRefresh();
    },
    [scheduleRefresh],
  );

  const logout = useCallback(async () => {
    clearRefreshTimer();
    await AuthService.logout();
    setState(SIGNED_OUT_STATE);
  }, [clearRefreshTimer]);

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
