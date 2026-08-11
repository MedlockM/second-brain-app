import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useRef,
  useState,
} from "react";
import { Platform } from "react-native";
import { useRouter, usePathname } from "expo-router";
import { useShareIntentContext } from "expo-share-intent";
import type { ShareIntent } from "expo-share-intent";
import { useAuth } from "./AuthContext";
import {
  validateShareIntentPayload,
  getShareIntentErrorMessage,
} from "../lib/urlValidation";
import { MediaService } from "../services/mediaService";
import {
  SharedContentService,
  SharedContentValidationError,
} from "../services/sharedContentService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import {
  getQuotaErrorCode,
  getQuotaErrorMessage,
  type QuotaErrorCode,
} from "../lib/quotaError";
import type { IngestUrlResponse } from "../types/media";
import type { SharedFileAttachment } from "../types/sharedContent";

/**
 * The type of content being shared.
 * - "url": Text containing a URL (existing flow)
 * - "text": Plain text with no URL (WhatsApp text message)
 * - "audio": Audio file attachment (WhatsApp voice message)
 */
export type ShareContentType = "url" | "text" | "audio";

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
  /**
   * Set when the backend refused the submission through the quota enforcer.
   * Drives the quota-specific error card, including whether the paywall is
   * offered. Null/undefined for any other failure.
   */
  quotaErrorCode?: QuotaErrorCode | null;
}

export interface ShareSelectedFolder {
  id: string;
  path: string;
}

export interface ShareSelectedTag {
  id: string;
  name: string;
}

interface ShareIntentContextValue {
  intake: ShareIntakeState;
  selectedFolder: ShareSelectedFolder | null;
  selectedTags: ShareSelectedTag[];
  setSelectedFolder: (folder: ShareSelectedFolder | null) => void;
  setSelectedTags: (tags: ShareSelectedTag[]) => void;
  clearOrganization: () => void;
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
  quotaErrorCode: null,
};

const ShareIntentContext = createContext<ShareIntentContextValue | null>(null);

/**
 * Build the error half of the intake state from a failed submission.
 *
 * A quota refusal keeps the backend wording: it is the only text that names the
 * limit that was hit, and getFriendlyErrorMessage would collapse it into a
 * generic "You need more minutes or credits to continue."
 */
function toSubmissionError(
  error: unknown,
  fallback: string,
): { message: string; quotaErrorCode: QuotaErrorCode | null } {
  const quotaErrorCode = getQuotaErrorCode(error);
  if (quotaErrorCode) {
    return {
      message: getQuotaErrorMessage(error, quotaErrorCode),
      quotaErrorCode,
    };
  }
  if (error instanceof SharedContentValidationError) {
    return { message: error.message, quotaErrorCode: null };
  }
  return {
    message: getFriendlyErrorMessage(error, { fallback }),
    quotaErrorCode: null,
  };
}

/**
 * Provider that consumes the official expo-share-intent package context
 * and maps its resolved ShareIntent data to our app's ShareIntakeState.
 *
 * The expo-share-intent package handles:
 * - Intercepting scheme URLs (media-summarizer://dataUrl=<key>?nonce=...)
 * - Resolving data from iOS App Groups via the native module
 * - Listening for Android intent data
 * - App state transitions (foreground/background reset)
 *
 * This provider handles:
 * - Auth gating (queues intent while unauthenticated)
 * - Mapping the package's ShareIntent shape to our ShareIntakeState
 * - Navigation to the share-confirmation screen
 * - Submission logic (ingest URL, text, or audio to backend)
 *
 * Must be placed inside AuthProvider and the package's ShareIntentProvider.
 */
export function ShareIntentProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  const [intake, setIntake] = useState<ShareIntakeState>(INITIAL_STATE);
  const [selectedFolder, setSelectedFolder] =
    useState<ShareSelectedFolder | null>(null);
  const [selectedTags, setSelectedTags] = useState<ShareSelectedTag[]>([]);
  const hasNavigatedRef = useRef(false);
  const lastProcessedKeyRef = useRef<string | null>(null);
  const pendingIntentRef = useRef<ShareIntent | null>(null);

  // Consume the official expo-share-intent package context
  const { hasShareIntent, shareIntent, resetShareIntent } =
    useShareIntentContext();

  useEffect(() => {
    pathnameRef.current = pathname;
  }, [pathname]);

  /**
   * Map an expo-share-intent ShareIntent object to our ShareIntakeState
   * and navigate to the confirmation screen.
   */
  const processShareIntent = useCallback(
    (intent: ShareIntent) => {
      // Deduplication: build a key from the intent content
      const intentKey = JSON.stringify({
        type: intent.type,
        text: intent.text,
        webUrl: intent.webUrl,
        files: intent.files?.map((f) => f.path),
      });
      if (lastProcessedKeyRef.current === intentKey) return;
      lastProcessedKeyRef.current = intentKey;

      // Clear dedup after 5 seconds to allow re-sharing the same content
      setTimeout(() => {
        if (lastProcessedKeyRef.current === intentKey) {
          lastProcessedKeyRef.current = null;
        }
      }, 5000);

      // Map the package ShareIntent to our ShareIntakeState. We track whether
      // any branch produced a meaningful state — if none did (intent is empty
      // or stale, which can happen on cold start when the native module still
      // holds a leftover blob in the App Group), we must NOT navigate to
      // share-confirmation, otherwise the user sees an empty "Processing
      // shared content…" spinner with no real share to act on.
      let mapped = false;

      if (intent.type === "weburl" && intent.webUrl) {
        // Web URL share (Safari, Instagram Reel, etc.)
        const result = validateShareIntentPayload(intent.webUrl);
        if (!result.valid) {
          setIntake({
            status: "invalid",
            url: null,
            rawText: intent.webUrl,
            message: getShareIntentErrorMessage(result.reason),
            response: null,
            contentType: "url",
            audioFile: null,
          });
        } else {
          setIntake({
            status: "ready",
            url: result.url,
            rawText: intent.text ?? intent.webUrl,
            message: null,
            response: null,
            contentType: "url",
            audioFile: null,
          });
        }
        mapped = true;
      } else if (intent.type === "file" || intent.type === "media") {
        // File share - check if audio
        const file = intent.files?.[0];
        if (file && file.mimeType?.startsWith("audio/")) {
          const audioFile: SharedFileAttachment = {
            uri: file.path,
            mimeType: file.mimeType,
            fileName: file.fileName ?? null,
            fileSize: file.size ?? null,
          };
          setIntake({
            status: "ready",
            url: null,
            rawText: null,
            message: null,
            response: null,
            contentType: "audio",
            audioFile,
          });
          mapped = true;
        } else if (file) {
          // Non-audio file - not currently supported
          setIntake({
            status: "invalid",
            url: null,
            rawText: null,
            message: "This file type is not supported yet.",
            response: null,
            contentType: "url",
            audioFile: null,
          });
          mapped = true;
        }
      } else if (intent.type === "text" && intent.text) {
        // Plain text share - check if it contains a URL
        const result = validateShareIntentPayload(intent.text);
        if (result.valid) {
          // Text contains a URL
          setIntake({
            status: "ready",
            url: result.url,
            rawText: intent.text,
            message: null,
            response: null,
            contentType: "url",
            audioFile: null,
          });
        } else if (result.reason === "no_url_found") {
          // Pure text share (WhatsApp text message without URL)
          setIntake({
            status: "ready",
            url: null,
            rawText: intent.text,
            message: null,
            response: null,
            contentType: "text",
            audioFile: null,
          });
        } else {
          setIntake({
            status: "invalid",
            url: null,
            rawText: intent.text,
            message: getShareIntentErrorMessage(result.reason),
            response: null,
            contentType: "url",
            audioFile: null,
          });
        }
        mapped = true;
      }

      if (!mapped) {
        // Stale/empty intent surfaced by the native module — clear it so the
        // package doesn't hand it back on the next cycle, and stay put.
        resetShareIntent();
        return;
      }

      setSelectedFolder(null);
      setSelectedTags([]);

      // Navigate to share confirmation screen — but skip the push when we're
      // already on it (e.g. cold start where +native-intent.tsx redirected
      // there before the provider mounted), otherwise the screen stacks twice.
      if (
        !hasNavigatedRef.current &&
        pathnameRef.current !== "/share-confirmation"
      ) {
        hasNavigatedRef.current = true;
        setTimeout(() => {
          if (pathnameRef.current !== "/share-confirmation") {
            router.push("/share-confirmation");
          }
          hasNavigatedRef.current = false;
        }, 0);
      }
    },
    [router, resetShareIntent],
  );

  /**
   * React to share intent changes from the package.
   * If authenticated, process immediately. Otherwise, queue for later.
   */
  useEffect(() => {
    if (!hasShareIntent) return;
    if (isLoading) return;

    if (!isAuthenticated) {
      // Store pending intent for processing after auth
      pendingIntentRef.current = { ...shareIntent };
      return;
    }

    const timer = setTimeout(() => processShareIntent(shareIntent), 0);
    return () => clearTimeout(timer);
  }, [hasShareIntent, shareIntent, isAuthenticated, isLoading, processShareIntent]);

  /**
   * Process pending intent after authentication completes.
   */
  useEffect(() => {
    if (isAuthenticated && !isLoading && pendingIntentRef.current) {
      const pending = pendingIntentRef.current;
      pendingIntentRef.current = null;
      const timer = setTimeout(() => processShareIntent(pending), 0);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isLoading, processShareIntent]);

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
        source_app:
          Platform.OS === "ios"
            ? "ios-share-extension"
            : "android-share-intent",
        folder_id: selectedFolder?.id ?? null,
        tag_ids: selectedTags.map((tag) => tag.id),
      });

      setIntake({
        status: "success",
        url,
        rawText: intake.rawText,
        message: null,
        response,
        contentType: "url",
        audioFile: null,
        quotaErrorCode: null,
      });
    } catch (error) {
      const { message, quotaErrorCode } = toSubmissionError(
        error,
        "Failed to save the link. Please try again.",
      );
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
        quotaErrorCode,
      }));
    }
  }, [intake, token, selectedFolder, selectedTags]);

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
            folderId: selectedFolder?.id ?? null,
            tagIds: selectedTags.map((tag) => tag.id),
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
          quotaErrorCode: null,
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
            folderId: selectedFolder?.id ?? null,
            tagIds: selectedTags.map((tag) => tag.id),
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
          quotaErrorCode: null,
        });
      }
    } catch (error) {
      const { message, quotaErrorCode } = toSubmissionError(
        error,
        "Failed to save the content. Please try again.",
      );
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
        quotaErrorCode,
      }));
    }
  }, [intake, token, selectedFolder, selectedTags]);

  /**
   * Dismiss the share intent and reset state.
   * Also clears the native module's stored intent to prevent re-processing.
   */
  const dismiss = useCallback(() => {
    setIntake(INITIAL_STATE);
    setSelectedFolder(null);
    setSelectedTags([]);
    lastProcessedKeyRef.current = null;
    resetShareIntent();
  }, [resetShareIntent]);

  const clearOrganization = useCallback(() => {
    setSelectedFolder(null);
    setSelectedTags([]);
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
        quotaErrorCode: null,
      }));
    }
  }, [intake]);

  const value: ShareIntentContextValue = {
    intake,
    selectedFolder,
    selectedTags,
    setSelectedFolder,
    setSelectedTags,
    clearOrganization,
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
