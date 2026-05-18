import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useRef,
  useState,
} from "react";
import { Platform } from "react-native";
import * as Linking from "expo-linking";
import { useRouter } from "expo-router";
import { useAuth } from "./AuthContext";
import {
  validateShareIntentPayload,
  getShareIntentErrorMessage,
  extractUrlFromSharedText,
} from "../lib/urlValidation";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import type { IngestUrlResponse } from "../types/media";

export type ShareIntakeStatus =
  | "idle"
  | "validating"
  | "invalid"
  | "ready"
  | "submitting"
  | "success"
  | "error";

export interface ShareIntakeState {
  status: ShareIntakeStatus;
  url: string | null;
  rawText: string | null;
  message: string | null;
  response: IngestUrlResponse | null;
}

interface ShareIntentContextValue {
  intake: ShareIntakeState;
  submitUrl: () => Promise<void>;
  dismiss: () => void;
  retry: () => void;
}

const INITIAL_STATE: ShareIntakeState = {
  status: "idle",
  url: null,
  rawText: null,
  message: null,
  response: null,
};

const ShareIntentContext = createContext<ShareIntentContextValue | null>(null);

/**
 * Provider that listens for Android share intents at the app level.
 * When a valid URL is shared, navigates to the share-confirmation screen.
 *
 * Handles two scenarios:
 * 1. User is authenticated: processes intent immediately and navigates.
 * 2. User is not authenticated: stores the pending text and processes it
 *    once authentication completes.
 *
 * Must be placed inside AuthProvider (for useAuth) and within the navigation
 * container (expo-router Stack provides this).
 */
export function ShareIntentProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [intake, setIntake] = useState<ShareIntakeState>(INITIAL_STATE);
  const processedRef = useRef<Set<string>>(new Set());
  const hasNavigatedRef = useRef(false);
  const pendingTextRef = useRef<string | null>(null);

  /**
   * Process a raw text payload from a share intent.
   */
  const processIncomingText = useCallback(
    (text: string) => {
      if (!text || text.trim().length === 0) return;

      const key = text.trim();
      if (processedRef.current.has(key)) return;
      processedRef.current.add(key);

      // Expire dedup guard after 5 seconds to allow re-sharing
      setTimeout(() => {
        processedRef.current.delete(key);
      }, 5000);

      const result = validateShareIntentPayload(text);

      if (!result.valid) {
        setIntake({
          status: "invalid",
          url: null,
          rawText: text,
          message: getShareIntentErrorMessage(result.reason),
          response: null,
        });
      } else {
        setIntake({
          status: "ready",
          url: result.url,
          rawText: text,
          message: null,
          response: null,
        });
      }

      // Navigate to share confirmation screen
      if (!hasNavigatedRef.current) {
        hasNavigatedRef.current = true;
        setTimeout(() => {
          router.push("/share-confirmation");
          hasNavigatedRef.current = false;
        }, 0);
      }
    },
    [router],
  );

  /**
   * Extract shared text from an incoming URL event (Android intent).
   * Handles various intent formats.
   */
  const parseIntentUrl = useCallback(
    (url: string): string | null => {
      try {
        const parsed = Linking.parse(url);

        // Android SEND intents pass text in query params
        if (parsed.queryParams?.text) {
          return String(parsed.queryParams.text);
        }

        // Some launchers pass EXTRA_TEXT
        if (parsed.queryParams?.["android.intent.extra.TEXT"]) {
          return String(parsed.queryParams["android.intent.extra.TEXT"]);
        }

        // The entire URL is a plain http(s) link being shared
        if (url.startsWith("http://") || url.startsWith("https://")) {
          return url;
        }

        // Last resort: extract URL from raw string
        return extractUrlFromSharedText(url);
      } catch {
        return extractUrlFromSharedText(url);
      }
    },
    [],
  );

  /**
   * Handle an incoming URL event.
   */
  const handleIncomingUrl = useCallback(
    (url: string | null) => {
      if (!url) return;
      if (Platform.OS !== "android") return;

      const text = parseIntentUrl(url);
      if (!text) return;

      if (!isAuthenticated) {
        // Store for later processing after login
        pendingTextRef.current = text;
        return;
      }

      processIncomingText(text);
    },
    [isAuthenticated, processIncomingText, parseIntentUrl],
  );

  // Process pending intent after authentication completes
  useEffect(() => {
    if (isAuthenticated && !isLoading && pendingTextRef.current) {
      const text = pendingTextRef.current;
      pendingTextRef.current = null;
      processIncomingText(text);
    }
  }, [isAuthenticated, isLoading, processIncomingText]);

  // Check initial URL on mount (cold start from share intent)
  useEffect(() => {
    if (Platform.OS !== "android") return;
    if (isLoading) return;

    const checkInitial = async () => {
      const initialUrl = await Linking.getInitialURL();
      if (initialUrl) {
        handleIncomingUrl(initialUrl);
      }
    };

    checkInitial();
  }, [isLoading, handleIncomingUrl]);

  // Listen for URL events (warm start: app already running)
  useEffect(() => {
    if (Platform.OS !== "android") return;

    const subscription = Linking.addEventListener("url", (event) => {
      handleIncomingUrl(event.url);
    });

    return () => {
      subscription.remove();
    };
  }, [handleIncomingUrl]);

  /**
   * Submit the validated URL to the backend.
   */
  const submitUrl = useCallback(async () => {
    if (intake.status !== "ready" || !intake.url) return;
    if (!token) {
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message: "You must be signed in to save links.",
      }));
      return;
    }

    const url = intake.url;
    setIntake((prev) => ({ ...prev, status: "submitting" }));

    try {
      const response = await MediaService.ingestUrl(token, {
        url,
        source_app: "android_share",
      });

      setIntake({
        status: "success",
        url,
        rawText: intake.rawText,
        message: null,
        response,
      });
    } catch (error) {
      const message = getFriendlyErrorMessage(error, {
        fallback: "Failed to save the link. Please try again.",
      });
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
      }));
    }
  }, [intake, token]);

  /**
   * Dismiss the share intent and reset state.
   */
  const dismiss = useCallback(() => {
    setIntake(INITIAL_STATE);
  }, []);

  /**
   * Retry after an error - go back to ready state.
   */
  const retry = useCallback(() => {
    if (intake.status === "error" && intake.url) {
      setIntake((prev) => ({
        ...prev,
        status: "ready",
        message: null,
      }));
    }
  }, [intake]);

  const value: ShareIntentContextValue = {
    intake,
    submitUrl,
    dismiss,
    retry,
  };

  return (
    <ShareIntentContext.Provider value={value}>
      {children}
    </ShareIntentContext.Provider>
  );
}

/**
 * Hook to access the share intent context.
 */
export function useShareIntake(): ShareIntentContextValue {
  const context = useContext(ShareIntentContext);
  if (!context) {
    throw new Error("useShareIntake must be used within ShareIntentProvider");
  }
  return context;
}
