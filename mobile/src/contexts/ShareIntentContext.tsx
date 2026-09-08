import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useRef,
  useState,
} from "react";
import { Platform } from "react-native";
import { t } from "../i18n";
import { useRouter, usePathname } from "expo-router";
import { useShareIntentContext } from "expo-share-intent";
import type { ShareIntent } from "expo-share-intent";
import { useAuth } from "./AuthContext";
import {
  validateShareIntentPayload,
  getShareIntentErrorMessage,
} from "../lib/urlValidation";
import { MediaService } from "../services/mediaService";
import { OrganizationService } from "../services/organizationService";
import {
  SharedContentService,
  SharedContentValidationError,
} from "../services/sharedContentService";
import { DirectUploadError } from "../services/presignedUpload";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import {
  getQuotaErrorCode,
  getQuotaErrorMessage,
  type QuotaErrorCode,
} from "../lib/quotaError";
import { UploadService } from "../services/uploadService";
import type { SharedFileAttachment } from "../types/sharedContent";
import type { LocalUploadFile } from "../types/upload";
import {
  classifyUploadFile,
  isImageUpload,
  prepareLocalUploadFile,
  resolveUploadFileName,
} from "../types/upload";

/**
 * The type of content being confirmed before ingestion.
 * - "url": Text containing a URL (existing flow)
 * - "text": Plain text with no URL (WhatsApp text message)
 * - "audio": Audio file attachment (WhatsApp voice message)
 * - "file": Document imported from the device (task-264) or shared to the app
 * - "photo": Picture — a camera capture (task-264), a gallery pick, or an image
 *   shared from the system share sheet (a screenshot, task-347)
 *
 * The last two split on presentation, not on plumbing: both submit through the
 * upload endpoints, and only a picture is shown as one. Either can start from a
 * gesture inside the app or from a share intent, and both reuse the confirmation
 * screen so every source picks its folder the same way.
 */
export type ShareContentType = "url" | "text" | "audio" | "file" | "photo";

/**
 * Where an intake came from, and therefore what the two buttons of the
 * confirmation screen mean (task-378).
 *
 * - "share": the user picked this app in the system share sheet. The ingestion
 *   starts on arrival, so Save only *confirms* the save and the close button
 *   deletes it.
 * - "local": a file picked or a photo taken inside the app. Save is still what
 *   submits it, and closing submits nothing and deletes nothing.
 */
export type ShareIntakeOrigin = "share" | "local";

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
  /** Which of the two journeys this intake belongs to. */
  origin: ShareIntakeOrigin;
  /** Extracted URL (for URL shares) */
  url: string | null;
  /** Raw text from the share intent */
  rawText: string | null;
  /** User-facing message (error or info) */
  message: string | null;
  /** The type of content being shared */
  contentType: ShareContentType;
  /** Audio file attachment (for audio shares) */
  audioFile: SharedFileAttachment | null;
  /**
   * The save the accepted submission created — the one the close button deletes
   * and the one a folder picked during processing is applied to. Optional so a
   * fresh intake, written as a whole object, cannot inherit the previous save.
   */
  mediaItemId?: string | null;
  /** True when the backend recognised content it had already processed. */
  deduplicated?: boolean;
  /**
   * Device file being imported (for "file" and "photo" intakes). Optional so the
   * share-intent branches, which cannot produce one, stay unchanged: omitting it
   * clears any previous import.
   */
  uploadFile?: LocalUploadFile | null;
  /**
   * Set when the backend refused the submission through the quota enforcer.
   * Drives the quota-specific error card, including whether the paywall is
   * offered. Null/undefined for any other failure.
   */
  quotaErrorCode?: QuotaErrorCode | null;
  /**
   * One technical line describing a failed direct-to-S3 transfer (task-371):
   * the step that failed, the status S3 answered, its error code, the bytes and
   * MIME type sent. Set only for a `DirectUploadError`, whose sentence is the
   * same for all three ways the transfer can die.
   *
   * It travels in the state because there is no telemetry channel: the failure
   * screen is the only place this can be read from, so the tester reads it there
   * and quotes it in a bug report.
   */
  uploadDiagnostics?: string | null;
}

export interface ShareSelectedFolder {
  id: string;
  path: string;
}

/**
 * Where the removal of a cancelled share stands.
 *
 * It is tracked apart from the intake status because it is not a step of the
 * ingestion: the save may be halfway through processing, or already processed,
 * when the user closes the modal.
 */
export type ShareCancellationStatus = "idle" | "pending" | "failed";

export interface ShareCancellation {
  status: ShareCancellationStatus;
  /** Why the removal failed, so the screen can say it and offer a retry. */
  message: string | null;
}

/** What `confirmIntake` answers, so the screen knows whether it may close. */
export interface ShareConfirmResult {
  /** True when everything the user chose is on the server and the modal may go. */
  ok: boolean;
  /**
   * A failure to surface, or null when the screen already shows it — a refused
   * submission has its own card and needs no alert on top of it.
   */
  message: string | null;
}

interface ShareIntentContextValue {
  intake: ShareIntakeState;
  cancellation: ShareCancellation;
  selectedFolder: ShareSelectedFolder | null;
  setSelectedFolder: (folder: ShareSelectedFolder | null) => void;
  /**
   * Open the confirmation screen on a file picked or captured on the device.
   * Used by the inbox "add" gesture (task-264).
   */
  startLocalUpload: (
    file: LocalUploadFile,
    contentType: Extract<ShareContentType, "file" | "photo">,
  ) => void;
  /** Preserve the open confirmation state while authentication is restored. */
  parkCurrentIntakeForAuth: () => void;
  /**
   * Send the pending intake to the endpoint its content type belongs to. Fired
   * automatically on a share, and by Save on a local import.
   */
  submitIntake: () => Promise<void>;
  /** Keep the save: finish applying the user's choices, then let the modal go. */
  confirmIntake: () => Promise<ShareConfirmResult>;
  /**
   * Close the modal. A share, which was ingested on arrival, has its save
   * deleted; a local import, which Save alone submits, is only dismissed.
   * Resolves to whether the screen may leave.
   */
  cancelIntake: () => Promise<boolean>;
  retry: () => void;
}

type PendingIntake =
  | { kind: "share"; intent: ShareIntent }
  | {
      kind: "local";
      file: LocalUploadFile;
      contentType: Extract<ShareContentType, "file" | "photo">;
    }
  | { kind: "current" };

/**
 * Everything about the submission of the current reception that must not be read
 * through a stale render closure: whether it already went out, what it created,
 * and whether the user has since asked for it to be removed.
 *
 * One mutable object rather than eight refs, because these fields are only ever
 * read together and none of them may drive a render.
 */
interface ShareSubmissionTracking {
  /** Bumped for every reception, which is what makes one reception submit once. */
  receptionId: number;
  /** The reception the automatic submission already fired for. */
  autoSubmittedId: number | null;
  /** The submission in flight, resolving to the save it created, or null. */
  inFlight: Promise<string | null> | null;
  /** True once a submission was accepted, even if its id came back empty. */
  saveCreated: boolean;
  /** The save that submission created. */
  mediaItemId: string | null;
  /** The user closed the modal: nothing may be applied to the save any more. */
  cancelRequested: boolean;
  /** The folder the user wants the save in. */
  desiredFolderId: string | null;
  /** The folder the server holds — sent with the submission, or patched since. */
  appliedFolderId: string | null;
  /** Serializes the folder patches so only the last choice survives. */
  folderSync: Promise<void> | null;
}

function freshTracking(receptionId: number): ShareSubmissionTracking {
  return {
    receptionId,
    autoSubmittedId: null,
    inFlight: null,
    saveCreated: false,
    mediaItemId: null,
    cancelRequested: false,
    desiredFolderId: null,
    appliedFolderId: null,
    folderSync: null,
  };
}

const INITIAL_STATE: ShareIntakeState = {
  status: "idle",
  // Nothing has been received yet: the neutral origin is the one whose close
  // button deletes nothing.
  origin: "local",
  url: null,
  rawText: null,
  message: null,
  contentType: "url",
  audioFile: null,
  mediaItemId: null,
  deduplicated: false,
  uploadFile: null,
  quotaErrorCode: null,
  uploadDiagnostics: null,
};

const NO_CANCELLATION: ShareCancellation = { status: "idle", message: null };

const ShareIntentContext = createContext<ShareIntentContextValue | null>(null);

function shareIntentKey(intent: ShareIntent): string {
  return JSON.stringify({
    type: intent.type,
    text: intent.text,
    webUrl: intent.webUrl,
    files: intent.files?.map((file) => file.path),
  });
}

/** Which app the submission reports as its source, per platform. */
function shareSourceApp(): string {
  return Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent";
}

/**
 * Whether the intake may be sent. A failed one may: that is the retry, and it is
 * the state a user comes back to after subscribing on the paywall — the content
 * is still there, only the refusal has to be replaced.
 */
function isSubmittable(status: ShareIntakeStatus): boolean {
  return status === "ready" || status === "error";
}

/**
 * Build the error half of the intake state from a failed submission.
 *
 * A consumption refusal keeps the backend wording: it is the only text that
 * carries the figures ("This import needs 45 minutes and you have 12 left until
 * Sep 12"), and getFriendlyErrorMessage would collapse it into the generic
 * out-of-minutes sentence, dropping every number the user needs.
 *
 * A failed transfer to S3 keeps its own wording too, for the opposite reason: it
 * arrives already translated, and getFriendlyErrorMessage flattens anything that
 * mentions S3 into the generic error sentence (task-345). It is also the only
 * failure that hands back a technical line, since it is the only one that left no
 * server-side trace to look up afterwards (task-371).
 */
function toSubmissionError(
  error: unknown,
  fallback: string,
): {
  message: string;
  quotaErrorCode: QuotaErrorCode | null;
  uploadDiagnostics: string | null;
} {
  const quotaErrorCode = getQuotaErrorCode(error);
  if (quotaErrorCode) {
    return {
      message: getQuotaErrorMessage(error, quotaErrorCode),
      quotaErrorCode,
      uploadDiagnostics: null,
    };
  }
  if (error instanceof DirectUploadError) {
    return {
      message: error.message,
      quotaErrorCode: null,
      uploadDiagnostics: error.detail,
    };
  }
  if (error instanceof SharedContentValidationError) {
    return {
      message: error.message,
      quotaErrorCode: null,
      uploadDiagnostics: null,
    };
  }
  return {
    message: getFriendlyErrorMessage(error, { fallback }),
    quotaErrorCode: null,
    uploadDiagnostics: null,
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
 * Since task-378 a share is submitted the moment it is mapped, not when the user
 * presses Save: the seconds spent picking a folder are seconds of processing
 * already under way. The confirmation screen therefore confirms or removes a save
 * that already exists, which is why deletion and folder patching live here too —
 * both must survive the screen being closed while a call is still in flight.
 *
 * Must be placed inside AuthProvider and the package's ShareIntentProvider.
 */
export function ShareIntentProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading, revalidateSession } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  const [intake, setIntake] = useState<ShareIntakeState>(INITIAL_STATE);
  const [cancellation, setCancellation] =
    useState<ShareCancellation>(NO_CANCELLATION);
  const [selectedFolder, setSelectedFolder] =
    useState<ShareSelectedFolder | null>(null);
  const hasNavigatedRef = useRef(false);
  const lastProcessedKeyRef = useRef<string | null>(null);
  const lastGuardedIntentKeyRef = useRef<string | null>(null);
  const pendingIntakeRef = useRef<PendingIntake | null>(null);
  const replayInFlightRef = useRef<Promise<void> | null>(null);
  const trackingRef = useRef<ShareSubmissionTracking>(freshTracking(0));

  // Consume the official expo-share-intent package context
  const { hasShareIntent, shareIntent, resetShareIntent } =
    useShareIntentContext();

  useEffect(() => {
    pathnameRef.current = pathname;
  }, [pathname]);

  const navigateToConfirmation = useCallback(() => {
    if (
      hasNavigatedRef.current ||
      pathnameRef.current === "/share-confirmation"
    ) {
      return;
    }
    hasNavigatedRef.current = true;
    setTimeout(() => {
      if (pathnameRef.current !== "/share-confirmation") {
        router.push("/share-confirmation");
      }
      hasNavigatedRef.current = false;
    }, 0);
  }, [router]);

  /**
   * Start tracking a new reception.
   *
   * A submission still in flight from the previous reception is let go rather
   * than cancelled: its content was accepted and its save is legitimate — the
   * user simply shared something else before answering for it.
   */
  const beginReception = useCallback(() => {
    trackingRef.current = freshTracking(trackingRef.current.receptionId + 1);
    setCancellation(NO_CANCELLATION);
    setSelectedFolder(null);
  }, []);

  const applyLocalUpload = useCallback(
    (
      file: LocalUploadFile,
      contentType: Extract<ShareContentType, "file" | "photo">,
      origin: ShareIntakeOrigin,
    ) => {
      beginReception();
      setIntake({
        status: "ready",
        origin,
        url: null,
        rawText: null,
        message: null,
        contentType,
        audioFile: null,
        uploadFile: file,
      });
      navigateToConfirmation();
    },
    [beginReception, navigateToConfirmation],
  );

  /**
   * Map an expo-share-intent ShareIntent object to our ShareIntakeState
   * and navigate to the confirmation screen.
   */
  const processShareIntent = useCallback(
    (intent: ShareIntent) => {
      // Deduplication: build a key from the intent content
      const intentKey = shareIntentKey(intent);
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
            origin: "share",
            url: null,
            rawText: intent.webUrl,
            message: getShareIntentErrorMessage(result.reason),
            contentType: "url",
            audioFile: null,
          });
        } else {
          setIntake({
            status: "ready",
            origin: "share",
            url: result.url,
            rawText: intent.text ?? intent.webUrl,
            message: null,
            contentType: "url",
            audioFile: null,
          });
        }
        mapped = true;
      } else if (intent.type === "file" || intent.type === "media") {
        const file = intent.files?.[0];
        if (file && file.mimeType?.startsWith("audio/")) {
          // Audio files keep using the WhatsApp-specific path (ingest-shared-content)
          const audioFile: SharedFileAttachment = {
            uri: file.path,
            mimeType: file.mimeType,
            fileName: file.fileName ?? null,
            fileSize: file.size ?? null,
          };
          setIntake({
            status: "ready",
            origin: "share",
            url: null,
            rawText: null,
            message: null,
            contentType: "audio",
            audioFile,
          });
          mapped = true;
        } else if (file) {
          // Non-audio file: classify and route through the upload path.
          //
          // The reported name is not always usable — a screenshot shared as raw
          // image data reaches us with no name, and the extension is the only
          // thing the backend routes on — so it is resolved against the copied
          // file's path and MIME type first (task-347).
          const fileName = resolveUploadFileName({
            fileName: file.fileName,
            path: file.path,
            mimeType: file.mimeType,
          });
          const classification = classifyUploadFile(fileName);

          if (classification) {
            // File is supported, prepare it
            const result = prepareLocalUploadFile({
              uri: file.path,
              name: fileName,
              mimeType: file.mimeType,
              size: file.size,
            });

            if ("file" in result) {
              // File is accepted, route through upload path. An image is shown
              // as a picture rather than as a file card, which is the whole
              // difference between the two content types here. The origin stays
              // "share": it arrived from another app, so it ingests on arrival.
              // applyLocalUpload starts the reception and navigates, so return early.
              applyLocalUpload(
                result.file,
                isImageUpload(result.file) ? "photo" : "file",
                "share",
              );
              return;
            } else {
              // File is rejected (too large, empty, etc.)
              setIntake({
                status: "invalid",
                origin: "share",
                url: null,
                rawText: null,
                message: result.rejection.message,
                contentType: "url",
                audioFile: null,
              });
              mapped = true;
            }
          } else {
            // File extension is not supported
            setIntake({
              status: "invalid",
              origin: "share",
              url: null,
              rawText: null,
              message: t("share.unsupportedFile"),
              contentType: "url",
              audioFile: null,
            });
            mapped = true;
          }
        }
      } else if (intent.type === "text" && intent.text) {
        // Plain text share - check if it contains a URL
        const result = validateShareIntentPayload(intent.text);
        if (result.valid) {
          // Text contains a URL
          setIntake({
            status: "ready",
            origin: "share",
            url: result.url,
            rawText: intent.text,
            message: null,
            contentType: "url",
            audioFile: null,
          });
        } else if (result.reason === "no_url_found") {
          // Pure text share (WhatsApp text message without URL)
          setIntake({
            status: "ready",
            origin: "share",
            url: null,
            rawText: intent.text,
            message: null,
            contentType: "text",
            audioFile: null,
          });
        } else {
          setIntake({
            status: "invalid",
            origin: "share",
            url: null,
            rawText: intent.text,
            message: getShareIntentErrorMessage(result.reason),
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

      // A mapped reception is a new one: whatever the previous share created is
      // no longer this modal's business.
      beginReception();

      // Navigate to share confirmation screen — but skip the push when we're
      // already on it (e.g. cold start where +native-intent.tsx redirected
      // there before the provider mounted), otherwise the screen stacks twice.
      navigateToConfirmation();
    },
    [
      applyLocalUpload,
      beginReception,
      navigateToConfirmation,
      resetShareIntent,
    ],
  );

  const resumePendingIntake = useCallback((): Promise<void> => {
    if (replayInFlightRef.current) {
      return replayInFlightRef.current;
    }

    const operation = (async () => {
      const valid = await revalidateSession();
      if (!valid) {
        router.replace("/(auth)/login");
        return;
      }

      const pending = pendingIntakeRef.current;
      pendingIntakeRef.current = null;
      if (!pending) return;

      if (pending.kind === "share") {
        processShareIntent(pending.intent);
      } else if (pending.kind === "local") {
        // Only the inbox "add" gesture parks a file, so this replay is always a
        // local import — a shared file is mapped by processShareIntent above.
        applyLocalUpload(pending.file, pending.contentType, "local");
      } else {
        navigateToConfirmation();
      }
    })();

    replayInFlightRef.current = operation;
    void operation.finally(() => {
      if (replayInFlightRef.current === operation) {
        replayInFlightRef.current = null;
      }
    });
    return operation;
  }, [applyLocalUpload, navigateToConfirmation, processShareIntent, revalidateSession, router]);

  /**
   * React to share intent changes from the package.
   * Always revalidate SecureStore before navigation. A dead warm session is
   * indistinguishable from a healthy one in the in-memory boolean alone.
   */
  useEffect(() => {
    if (!hasShareIntent) {
      lastGuardedIntentKeyRef.current = null;
      return;
    }
    if (isLoading) return;

    const intentKey = shareIntentKey(shareIntent);
    if (lastGuardedIntentKeyRef.current === intentKey) return;
    lastGuardedIntentKeyRef.current = intentKey;

    pendingIntakeRef.current = {
      kind: "share",
      intent: { ...shareIntent },
    };
    const timer = setTimeout(() => {
      void resumePendingIntake();
    }, 0);
    return () => clearTimeout(timer);
  }, [hasShareIntent, shareIntent, isLoading, resumePendingIntake]);

  /**
   * Process pending intent after authentication completes.
   */
  useEffect(() => {
    if (isAuthenticated && !isLoading && pendingIntakeRef.current) {
      const timer = setTimeout(() => {
        void resumePendingIntake();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isLoading, resumePendingIntake]);

  /**
   * Put the folder the user picked on the save the submission created.
   *
   * The submission carries the folder it knew about, so this has work to do only
   * when the choice was made while the ingestion was already running — which is
   * now the normal case. Calls are chained rather than fired in parallel: the
   * user can keep moving between folders while a patch is in flight, and only
   * the last choice may survive.
   *
   * A failure leaves `appliedFolderId` behind, which *is* the memory of the
   * pending choice: the next call retries it, and Save awaits this before
   * closing so the failure is reported rather than swallowed.
   */
  const syncFolder = useCallback((): Promise<void> => {
    const apply = async (): Promise<void> => {
      const tracking = trackingRef.current;
      if (tracking.cancelRequested) return;
      const mediaItemId = tracking.mediaItemId;
      if (!mediaItemId) return;
      const desired = tracking.desiredFolderId;
      if (desired === tracking.appliedFolderId) return;
      await OrganizationService.setMediaFolder(mediaItemId, desired);
      tracking.appliedFolderId = desired;
    };

    const previous = trackingRef.current.folderSync ?? Promise.resolve();
    const operation = previous.then(apply);
    // The chain head must never be a rejected promise, or every later choice
    // would inherit a failure that has already been reported.
    trackingRef.current.folderSync = operation.catch(() => undefined);
    return operation;
  }, []);

  /**
   * Record the save a submission created: what the close button deletes, and
   * what a folder picked during processing is applied to.
   */
  const registerSave = useCallback(
    (mediaItemId: string, submittedFolderId: string | null) => {
      const tracking = trackingRef.current;
      tracking.saveCreated = true;
      tracking.mediaItemId = mediaItemId || null;
      tracking.appliedFolderId = submittedFolderId;
      void syncFolder().catch(() => undefined);
    },
    [syncFolder],
  );

  const selectFolder = useCallback(
    (folder: ShareSelectedFolder | null) => {
      setSelectedFolder(folder);
      trackingRef.current.desiredFolderId = folder?.id ?? null;
      // Applied straight away when the save already exists, so the choice lands
      // even if the user walks away from the modal.
      void syncFolder().catch(() => undefined);
    },
    [syncFolder],
  );

  /**
   * Submit the validated URL to the backend.
   */
  const submitUrl = useCallback(async (): Promise<string | null> => {
    if (!isSubmittable(intake.status) || !intake.url) return null;
    if (!isAuthenticated) {
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message: t("share.signInLinks"),
      }));
      return null;
    }

    const url = intake.url;
    const folderId = selectedFolder?.id ?? null;
    setIntake((prev) => ({ ...prev, status: "submitting" }));

    try {
      const response = await MediaService.ingestUrl({
        url,
        source_app: shareSourceApp(),
        folder_id: folderId,
      });

      registerSave(response.media_item_id, folderId);
      setIntake((prev) => ({
        ...prev,
        status: "success",
        message: null,
        mediaItemId: response.media_item_id,
        deduplicated: false,
        quotaErrorCode: null,
        uploadDiagnostics: null,
      }));
      return response.media_item_id;
    } catch (error) {
      const { message, quotaErrorCode, uploadDiagnostics } = toSubmissionError(
        error,
        "Failed to save the link. Please try again.",
      );
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
        quotaErrorCode,
        uploadDiagnostics,
      }));
      return null;
    }
  }, [intake, isAuthenticated, registerSave, selectedFolder]);

  /**
   * Submit shared content (text or audio) to the backend via ingest-shared-content.
   */
  const submitSharedContent = useCallback(async (): Promise<string | null> => {
    if (!isSubmittable(intake.status)) return null;
    if (!isAuthenticated) {
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message: t("share.signInContent"),
      }));
      return null;
    }

    // Checked before anything is announced: a "submitting" the caller can never
    // see the end of is worse than not starting at all, and Save now waits on the
    // submission in flight rather than firing its own.
    const isText = intake.contentType === "text" && intake.rawText;
    const isAudio = intake.contentType === "audio" && intake.audioFile;
    if (!isText && !isAudio) return null;

    const folderId = selectedFolder?.id ?? null;
    setIntake((prev) => ({ ...prev, status: "submitting" }));

    try {
      const response = isText
        ? await SharedContentService.ingestSharedText(intake.rawText!, {
            sourceApp: shareSourceApp(),
            folderId,
          })
        : await SharedContentService.ingestSharedAudio(intake.audioFile!, {
            sourceApp: shareSourceApp(),
            folderId,
          });

      registerSave(response.media_item_id, folderId);
      setIntake((prev) => ({
        ...prev,
        status: "success",
        message: null,
        mediaItemId: response.media_item_id,
        deduplicated: response.deduplicated ?? false,
        quotaErrorCode: null,
        uploadDiagnostics: null,
      }));
      return response.media_item_id;
    } catch (error) {
      const { message, quotaErrorCode, uploadDiagnostics } = toSubmissionError(
        error,
        "Failed to save the content. Please try again.",
      );
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
        quotaErrorCode,
        uploadDiagnostics,
      }));
      return null;
    }
  }, [intake, isAuthenticated, registerSave, selectedFolder]);

  /**
   * Upload the pending device file. The extension decided which endpoint it
   * belongs to when it was picked, so this only has to carry the organization.
   */
  const submitUpload = useCallback(async (): Promise<string | null> => {
    if (!isSubmittable(intake.status)) return null;
    const file = intake.uploadFile;
    if (!file) return null;
    if (!isAuthenticated) {
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message: t("share.signInFiles"),
      }));
      return null;
    }

    const folderId = selectedFolder?.id ?? null;
    setIntake((prev) => ({ ...prev, status: "submitting" }));

    try {
      const response = await UploadService.upload(file, { folderId });

      registerSave(response.media_item_id, folderId);
      setIntake((prev) => ({
        ...prev,
        status: "success",
        message: null,
        mediaItemId: response.media_item_id,
        deduplicated: false,
        quotaErrorCode: null,
        uploadDiagnostics: null,
      }));
      return response.media_item_id;
    } catch (error) {
      const { message, quotaErrorCode, uploadDiagnostics } = toSubmissionError(
        error,
        "Failed to import this file. Please try again.",
      );
      setIntake((prev) => ({
        ...prev,
        status: "error",
        message,
        quotaErrorCode,
        uploadDiagnostics,
      }));
      return null;
    }
  }, [intake, isAuthenticated, registerSave, selectedFolder]);

  /**
   * Send the intake to the endpoint its content type belongs to.
   *
   * One reception submits once: the in-flight guard is what makes the automatic
   * start, a screen remount, a return from the login screen and a tap on Save
   * add up to a single save. A voluntary retry after a failure goes through
   * `retry`, which reopens the door on purpose.
   */
  const submitIntake = useCallback(async (): Promise<void> => {
    const tracking = trackingRef.current;
    if (tracking.inFlight) {
      await tracking.inFlight;
      return;
    }
    if (!isSubmittable(intake.status) || tracking.cancelRequested) return;

    const operation =
      intake.contentType === "url"
        ? submitUrl()
        : intake.contentType === "file" || intake.contentType === "photo"
          ? submitUpload()
          : submitSharedContent();

    tracking.inFlight = operation;
    void operation.finally(() => {
      if (trackingRef.current.inFlight === operation) {
        trackingRef.current.inFlight = null;
      }
    });
    await operation;
  }, [intake, submitSharedContent, submitUpload, submitUrl]);

  /**
   * Start processing the moment the share is understood (task-378).
   *
   * The session was revalidated before the intake was mapped
   * (`resumePendingIntake`) and the content was validated while mapping it, so
   * "ready" on a share means every gate before the submission has been passed
   * and the only thing left to wait for would be a tap on Save. A local import
   * is untouched: Save is still what sends it.
   */
  useEffect(() => {
    if (intake.origin !== "share" || intake.status !== "ready") return;
    const tracking = trackingRef.current;
    if (tracking.autoSubmittedId === tracking.receptionId) return;
    if (tracking.cancelRequested) return;
    tracking.autoSubmittedId = tracking.receptionId;
    void submitIntake();
  }, [intake.origin, intake.status, submitIntake]);

  /**
   * Start an import from a file picked or captured on the device (task-264).
   *
   * The confirmation screen is opened right away: a photo goes from the shutter
   * to the folder step with nothing in between, and the actual upload only
   * happens when the user hits Save.
   */
  const startLocalUpload = useCallback(
    (
      file: LocalUploadFile,
      contentType: Extract<ShareContentType, "file" | "photo">,
    ) => {
      pendingIntakeRef.current = { kind: "local", file, contentType };
      void resumePendingIntake();
    },
    [resumePendingIntake],
  );

  const parkCurrentIntakeForAuth = useCallback(() => {
    if (intake.status !== "idle") {
      pendingIntakeRef.current = { kind: "current" };
    }
  }, [intake.status]);

  /**
   * Drop the intake and clear the native module's stored intent so the same
   * share is not handed back on the next cycle.
   */
  const dismiss = useCallback(() => {
    setIntake(INITIAL_STATE);
    setSelectedFolder(null);
    setCancellation(NO_CANCELLATION);
    trackingRef.current = freshTracking(trackingRef.current.receptionId + 1);
    lastProcessedKeyRef.current = null;
    resetShareIntent();
  }, [resetShareIntent]);

  const confirmIntake = useCallback(async (): Promise<ShareConfirmResult> => {
    const tracking = trackingRef.current;
    // Save after a failed removal means "keep it after all".
    tracking.cancelRequested = false;
    setCancellation(NO_CANCELLATION);

    // Pressing Save while the ingestion is still going out is an answer, not a
    // second submission: wait for the one in flight rather than starting one.
    const inFlight = tracking.inFlight;
    if (inFlight) {
      const mediaItemId = await inFlight;
      if (mediaItemId === null && !trackingRef.current.saveCreated) {
        // The submission was refused. Its card is already on screen and says
        // more than any alert could.
        return { ok: false, message: null };
      }
    }

    try {
      await syncFolder();
    } catch (error) {
      return {
        ok: false,
        message: getFriendlyErrorMessage(error, {
          fallback: t("share.folderFailed"),
        }),
      };
    }

    dismiss();
    return { ok: true, message: null };
  }, [dismiss, syncFolder]);

  const cancelIntake = useCallback(async (): Promise<boolean> => {
    const tracking = trackingRef.current;
    tracking.cancelRequested = true;

    // A local import is submitted by Save alone, so closing has nothing to undo.
    // Neither has a share that was refused, or one whose content never made it
    // past validation.
    if (
      intake.origin !== "share" ||
      (!tracking.inFlight && !tracking.saveCreated)
    ) {
      dismiss();
      return true;
    }

    setCancellation({ status: "pending", message: null });
    try {
      // A close during the submission itself has to wait for the id: the save
      // exists on the server whether or not the modal is still open, so the
      // late answer is what tells us which one to delete.
      const inFlight = tracking.inFlight;
      const mediaItemId = inFlight ? await inFlight : tracking.mediaItemId;

      if (mediaItemId) {
        // The canonical deletion: the row leaves the library and its search
        // records go with it, whether processing is still running or done.
        // Idempotent server-side, so a retry after a flaky network is safe.
        await MediaService.deleteMedia(mediaItemId);
      } else if (trackingRef.current.saveCreated) {
        // Accepted, but nothing in the answer named the save it created. There is
        // no id to delete, and reporting a removal would be a lie.
        setCancellation({
          status: "failed",
          message: t("share.cancel.failed"),
        });
        return false;
      }
      // Nothing else to undo: a submission that was refused while the modal was
      // closing created no save.

      dismiss();
      return true;
    } catch (error) {
      setCancellation({
        status: "failed",
        message: getFriendlyErrorMessage(error, {
          fallback: t("share.cancel.failed"),
        }),
      });
      return false;
    }
  }, [dismiss, intake.origin]);

  /**
   * Retry after an error - go back to ready state.
   *
   * The reception's submission guard is reopened, so a share submits again on
   * its own and a local import waits for Save, exactly as they do on arrival.
   */
  const retry = useCallback(() => {
    if (intake.status === "error") {
      trackingRef.current.autoSubmittedId = null;
      trackingRef.current.cancelRequested = false;
      setIntake((prev) => ({
        ...prev,
        status: "ready",
        message: null,
        quotaErrorCode: null,
        uploadDiagnostics: null,
      }));
    }
  }, [intake]);

  const value: ShareIntentContextValue = {
    intake,
    cancellation,
    selectedFolder,
    setSelectedFolder: selectFolder,
    startLocalUpload,
    parkCurrentIntakeForAuth,
    submitIntake,
    confirmIntake,
    cancelIntake,
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
