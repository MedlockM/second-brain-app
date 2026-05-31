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
import {
  SharedContentService,
  SharedContentValidationError,
} from "../services/sharedContentService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import type { IngestUrlResponse } from "../types/media";
import type { SharedFileAttachment } from "../types/sharedContent";
import type { ShareContentType } from "../services/shareIntentService";

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
  /** Extracted URL (for URL shares) */
  url: string | null;
  /** Raw text from the share intent */
  rawText: string | null;
  /** User-facing message (error or info) */
  message: string | null;
  /** Response from the ingest endpoint */
  response: IngestUrlResponse | null;
  /** The type of content being shared */
  contentType: ShareContentType;
  /** Audio file attachment (for audio shares) */
  audioFile: SharedFileAttachment | null;
}

interface ShareIntentContextValue {
  intake: ShareIntakeState;
  submitUrl: () => Promise<void>;
  submitSharedContent: () => Promise<void>;
  dismiss: () => void;
  retry: () => void;
}

const INITIAL_STATE: ShareIntakeState = {
  status: "idle",
  url: null,
  rawText: null,
  message: null,
  response: null,
  contentType: "url",
  audioFile: null,
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
   * Now supports three paths: URL (existing), plain text (WhatsApp), audio (WhatsApp).
   */
  const processIncomingText = useCallback(
    (text: string, overrideContentType?: ShareContentType) => {
      if (!text || text.trim().length === 0) return;

      const key = text.trim();
      if (processedRef.current.has(key)) return;
      processedRef.current.add(key);

      // Expire dedup guard after 5 seconds to allow re-sharing
      setTimeout(() => {
        processedRef.current.delete(key);
      }, 5000);

      // If caller explicitly says this is text-only (no URL), skip URL extraction
      if (overrideContentType === "text") {
        setIntake({
          status: "ready",
          url: null,
          rawText: text,
          message: null,
          response: null,
          contentType: "text",
          audioFile: null,
        });
      } else {
        // Try to extract a URL (existing behavior)
        const result = validateShareIntentPayload(text);

        if (!result.valid) {
          // No URL found -- treat as shared text (WhatsApp text without URL)
          if (result.reason === "no_url_found") {
            setIntake({
              status: "ready",
              url: null,
              rawText: text,
              message: null,
              response: null,
              contentType: "text",
              audioFile: null,
            });
          } else {
            setIntake({
              status: "invalid",
              url: null,
              rawText: text,
              message: getShareIntentErrorMessage(result.reason),
              response: null,
              contentType: "url",
              audioFile: null,
            });
          }
        } else {
          setIntake({
            status: "ready",
            url: result.url,
            rawText: text,
            message: null,
            response: null,
            contentType: "url",
            audioFile: null,
          });
        }
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
   * Process an incoming audio file from a share intent (WhatsApp voice message).
   */
  const processIncomingAudioFile = useCallback(
    (file: SharedFileAttachment) => {
      const key = `audio:${file.uri}`;
      if (processedRef.current.has(key)) return;
      processedRef.current.add(key);

      // Expire dedup guard after 5 seconds
      setTimeout(() => {
        processedRef.current.delete(key);
      }, 5000);

      setIntake({
        status: "ready",
        url: null,
        rawText: null,
        message: null,
        response: null,
        contentType: "audio",
        audioFile: file,
      });

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
    (url: string): { text: string | null; contentType?: ShareContentType } => {
      try {
        const parsed = Linking.parse(url);

        // Check for audio file shared via our custom scheme
        if (parsed.queryParams?.contentType === "audio" && parsed.queryParams?.fileUri) {
          // Audio file intent: will be handled separately
          return { text: null, contentType: "audio" };
        }

        // Check for explicit text-only content type
        if (parsed.queryParams?.contentType === "text" && parsed.queryParams?.text) {
          return { text: String(parsed.queryParams.text), contentType: "text" };
        }

        // Android SEND intents pass text in query params
        if (parsed.queryParams?.text) {
          return { text: String(parsed.queryParams.text) };
        }

        // Some launchers pass EXTRA_TEXT
        if (parsed.queryParams?.["android.intent.extra.TEXT"]) {
          return { text: String(parsed.queryParams["android.intent.extra.TEXT"]) };
        }

        // The entire URL is a plain http(s) link being shared
        if (url.startsWith("http://") || url.startsWith("https://")) {
          return { text: url };
        }

        // Last resort: extract URL from raw string
        return { text: extractUrlFromSharedText(url) };
      } catch {
        return { text: extractUrlFromSharedText(url) };
      }
    },
    [],
  );

  /**
   * Handle an incoming URL event (Android intent or iOS custom scheme).
   */
  const handleIncomingUrl = useCallback(
    (url: string | null) => {
      if (!url) return;

      // iOS share extension passes data via custom scheme
      if (url.startsWith("media-summarizer://")) {
        const parsed = Linking.parse(url);

        // Handle audio file from iOS share extension
        if (parsed.queryParams?.contentType === "audio" && parsed.queryParams?.fileUri) {
          const file: SharedFileAttachment = {
            uri: decodeURIComponent(String(parsed.queryParams.fileUri)),
            mimeType: String(parsed.queryParams.mimeType ?? "audio/mp4"),
            fileName: parsed.queryParams.fileName
              ? String(parsed.queryParams.fileName)
              : null,
            fileSize: parsed.queryParams.fileSize
              ? Number(parsed.queryParams.fileSize)
              : null,
          };

          if (!isAuthenticated) {
            pendingTextRef.current = `__audio__:${JSON.stringify(file)}`;
            return;
          }

          processIncomingAudioFile(file);
          return;
        }

        // Handle text-only from iOS share extension
        if (parsed.queryParams?.contentType === "text" && parsed.queryParams?.text) {
          const text = String(parsed.queryParams.text);
          if (!isAuthenticated) {
            pendingTextRef.current = `__text__:${text}`;
            return;
          }
          processIncomingText(text, "text");
          return;
        }
      }

      if (Platform.OS !== "android" && !url.startsWith("media-summarizer://")) return;

      const result = parseIntentUrl(url);
      if (!result.text) return;

      if (!isAuthenticated) {
        // Store for later processing after login
        if (result.contentType === "text") {
          pendingTextRef.current = `__text__:${result.text}`;
        } else {
          pendingTextRef.current = result.text;
        }
        return;
      }

      processIncomingText(result.text, result.contentType);
    },
    [isAuthenticated, processIncomingText, processIncomingAudioFile, parseIntentUrl],
  );

  // Process pending intent after authentication completes
  useEffect(() => {
    if (isAuthenticated && !isLoading && pendingTextRef.current) {
      const pending = pendingTextRef.current;
      pendingTextRef.current = null;

      // Check for special prefixes indicating content type
      if (pending.startsWith("__audio__:")) {
        try {
          const file = JSON.parse(pending.slice("__audio__:".length)) as SharedFileAttachment;
          processIncomingAudioFile(file);
        } catch {
          // Malformed audio payload, ignore
        }
      } else if (pending.startsWith("__text__:")) {
        processIncomingText(pending.slice("__text__:".length), "text");
      } else {
        processIncomingText(pending);
      }
    }
  }, [isAuthenticated, isLoading, processIncomingText, processIncomingAudioFile]);

  // Check initial URL on mount (cold start from share intent)
  useEffect(() => {
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
        contentType: "url",
        audioFile: null,
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
   * Submit shared content (text or audio) to the backend via ingest-shared-content.
   */
  const submitSharedContent = useCallback(async () => {
    if (intake.status !== "ready") return;
    if (!token) {
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message: "You must be signed in to save content.",
      }));
      return;
    }

    setIntake((prev) => ({ ...prev, status: "submitting" }));

    try {
      if (intake.contentType === "text" && intake.rawText) {
        const response = await SharedContentService.ingestSharedText(
          token,
          intake.rawText,
          {
            sourceApp:
              Platform.OS === "ios"
                ? "ios-share-extension"
                : "android-share-intent",
          },
        );

        setIntake({
          status: "success",
          url: null,
          rawText: intake.rawText,
          message: null,
          response: {
            media_item: {
              media_item_id: response.media_item_id,
              media_key: "",
              original_url: "",
              normalized_url: "",
              media_type: "shared_text",
              source_platform: "whatsapp",
              status: "processing",
              transcript: { status: "pending" },
              artifact_statuses: {},
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            processing_job: {
              job_id: response.media_item_id,
              status: "pending",
              progress: { percentage: 0, stage: "pending" },
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            deduplicated: response.deduplicated ?? false,
          },
          contentType: "text",
          audioFile: null,
        });
      } else if (intake.contentType === "audio" && intake.audioFile) {
        const response = await SharedContentService.ingestSharedAudio(
          token,
          intake.audioFile,
          {
            sourceApp:
              Platform.OS === "ios"
                ? "ios-share-extension"
                : "android-share-intent",
          },
        );

        setIntake({
          status: "success",
          url: null,
          rawText: null,
          message: null,
          response: {
            media_item: {
              media_item_id: response.media_item_id,
              media_key: "",
              original_url: "",
              normalized_url: "",
              media_type: "audio_file",
              source_platform: "whatsapp",
              status: "processing",
              transcript: { status: "pending" },
              artifact_statuses: {},
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            processing_job: {
              job_id: response.media_item_id,
              status: "pending",
              progress: { percentage: 0, stage: "pending" },
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            deduplicated: response.deduplicated ?? false,
          },
          contentType: "audio",
          audioFile: intake.audioFile,
        });
      }
    } catch (error) {
      let message: string;
      if (error instanceof SharedContentValidationError) {
        message = error.message;
      } else {
        message = getFriendlyErrorMessage(error, {
          fallback: "Failed to save the content. Please try again.",
        });
      }
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
    if (intake.status === "error") {
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
    submitSharedContent,
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
