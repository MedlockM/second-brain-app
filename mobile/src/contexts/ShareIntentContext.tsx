import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useRef,
  useState,
} from "react";
import { Alert, Platform } from "react-native";
import { t } from "../i18n";
import { useRouter, usePathname } from "expo-router";
import { useShareIntentContext } from "expo-share-intent";
import type { ShareIntent, ShareIntentFile } from "expo-share-intent";
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
import { validateSharedNoteText } from "../types/sharedContent";
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
 * - "text": Plain text with no URL — a note, whatever app it came from, since no
 *   platform names that app (task-380)
 * - "audio": Audio file attachment (a WhatsApp voice message)
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
 * Where an intake came from — a fact about the save, not a branch in its
 * handling (task-389).
 *
 * - "share": the user picked this app in the system share sheet.
 * - "url-entry": the user typed or pasted the URL in the app, from the "+" menu
 *   of the Home screen (task-379).
 * - "local": a file picked or a photo taken inside the app.
 *
 * All three start their ingestion the moment the content is understood, so none
 * of them changes what the confirmation modal does: it says the save is under
 * way and asks whether to file it. The value survives because
 * `sourceAppFor` reports it to the backend — the same link reaching us from the
 * share sheet and from the "+" menu are two different facts about how the
 * product is used.
 */
export type ShareIntakeOrigin = "share" | "url-entry" | "local";

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
   * The save the accepted submission created — the one a folder picked during
   * processing is applied to. Optional so a fresh intake, written as a whole
   * object, cannot inherit the previous save.
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

interface ShareIntentContextValue {
  intake: ShareIntakeState;
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
  /**
   * Send a URL the user typed or pasted in the app (task-379). The caller has
   * already extracted it with `urlValidation`, so this only has the session left
   * to check before the ingestion starts on its own.
   */
  startUrlEntry: (url: string) => void;
  /** Preserve the open confirmation state while authentication is restored. */
  parkCurrentIntakeForAuth: () => void;
  /**
   * Let go of the current intake: the modal is done with it. Nothing is deleted
   * — the save exists and stays (task-389) — and the native module's stored
   * intent is cleared so the same content can be shared again.
   */
  dismissIntake: () => void;
  retry: () => void;
}

type PendingIntake =
  | { kind: "share"; intent: ShareIntent }
  | { kind: "url"; url: string }
  | {
      kind: "local";
      file: LocalUploadFile;
      contentType: Extract<ShareContentType, "file" | "photo">;
    }
  | { kind: "current" };

/**
 * Everything about the submission of the current reception that must not be read
 * through a stale render closure: whether it already went out, and what it
 * created.
 *
 * One mutable object rather than seven refs, because these fields are only ever
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
    desiredFolderId: null,
    appliedFolderId: null,
    folderSync: null,
  };
}

const INITIAL_STATE: ShareIntakeState = {
  status: "idle",
  // Nothing has been received yet. Any of the three would do — the origin only
  // labels the source of a save that exists.
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

const ShareIntentContext = createContext<ShareIntentContextValue | null>(null);

function shareIntentKey(intent: ShareIntent): string {
  return JSON.stringify({
    type: intent.type,
    text: intent.text,
    webUrl: intent.webUrl,
    files: intent.files?.map((file) => file.path),
  });
}

/**
 * The one item to keep out of a share, and why a choice has to be made at all
 * (task-380).
 *
 * A share sheet can hand over several items in one go — a note exported with its
 * attachments, a multi-select in Files, a batch of screenshots — and this app
 * saves one thing per confirmation. Reading `files[0]` picked whatever the
 * platform happened to enumerate first, which for a note carrying a photo was the
 * photo, and for anything with no backend route was a screen that closed itself.
 *
 * So the pick is deliberate and ordered:
 * 1. an audio item, the only kind with its own ingestion path;
 * 2. the first item the backend has a route for, which is what makes a note
 *    exported as `.txt` win over the image sitting next to it;
 * 3. failing both, the first item with a path — kept on purpose, so an
 *    unsupported share reaches its refusal instead of disappearing.
 */
function selectShareIntentFile(
  files: ShareIntentFile[] | null | undefined,
): ShareIntentFile | null {
  const candidates = (files ?? []).filter((file) => Boolean(file?.path));
  if (candidates.length === 0) return null;

  const audio = candidates.find((file) => file.mimeType?.startsWith("audio/"));
  if (audio) return audio;

  const routable = candidates.find((file) =>
    classifyUploadFile(
      resolveUploadFileName({
        fileName: file.fileName,
        path: file.path,
        mimeType: file.mimeType,
      }),
    ),
  );
  return routable ?? candidates[0];
}

/**
 * What the submission reports as its source, so the origin of a save stays
 * readable in the data.
 *
 * A share is named after the platform mechanism that carried it, and those two
 * values are part of the API contract — they are not to be renamed. A URL typed in
 * the app is neither of them, and gets a value of its own (task-379): the same
 * link reaching us from the share sheet and from the "+" menu are two different
 * facts about how the product is used.
 */
function sourceAppFor(origin: ShareIntakeOrigin): string {
  if (origin === "url-entry") return "app-url-entry";
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
 * Since task-378 a reception is submitted the moment it is mapped, and since
 * task-389 that holds for all three of them, local imports included: the seconds
 * the user spends answering the modal are seconds of processing already under
 * way. The confirmation screen therefore stands in front of a save that already
 * exists and asks one thing, whether to file it — which is why folder patching
 * lives here: it must survive the screen being closed while a call is still in
 * flight.
 *
 * Since task-379 it also holds the third way a URL can arrive: typed or pasted in
 * the app, from the "+" menu of the Home screen. It goes through this provider
 * rather than straight to `MediaService` so it inherits the whole of the above —
 * the auth replay, the automatic start, the folder patching — and differs from a
 * share in exactly one thing, the `source_app` it reports.
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
   * Open the confirmation screen on a URL the user typed in (task-379).
   *
   * The URL arrives already extracted and validated by the dialog that collected
   * it, so the intake is "ready" from the first frame — which is what makes the
   * automatic submission below fire on the frame the modal opens.
   */
  const applyUrlEntry = useCallback(
    (url: string) => {
      beginReception();
      setIntake({
        status: "ready",
        origin: "url-entry",
        url,
        rawText: null,
        message: null,
        contentType: "url",
        audioFile: null,
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
      // any branch produced a meaningful state.
      //
      // Two different situations used to end the same way, and only one of them
      // should (task-380):
      //
      // - the intent carries no `type` at all: nothing was shared, the native
      //   module surfaced a leftover blob from the App Group on cold start. This
      //   one stays silent — resetting and staying put is correct.
      // - the intent announces a type but nothing usable came with it: a locked
      //   note hands over an empty string, a note holding only a drawing hands
      //   over no text either, a multi-item share can arrive with no readable
      //   item. Closing the screen on those is a dead end with no reason given,
      //   so every branch below ends in either a ready intake or an "invalid"
      //   one carrying the sentence that says why.
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
        const file = selectShareIntentFile(intent.files);
        if (file && file.mimeType?.startsWith("audio/")) {
          // Audio keeps its own path (ingest-shared-content, source `whatsapp`):
          // a voice note is what that endpoint's audio half exists for.
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
        } else {
          // A file share whose items all came through without a path. Announced
          // and empty is not the same as never announced: say so instead of
          // closing.
          setIntake({
            status: "invalid",
            origin: "share",
            url: null,
            rawText: null,
            message: t("share.reject.nothingToSave"),
            contentType: "url",
            audioFile: null,
          });
          mapped = true;
        }
      } else if (intent.type === "text") {
        // Plain text share - check if it contains a URL
        const sharedText = intent.text ?? "";
        const result = validateShareIntentPayload(sharedText);
        if (result.valid) {
          // Text contains a URL
          setIntake({
            status: "ready",
            origin: "share",
            url: result.url,
            rawText: sharedText,
            message: null,
            contentType: "url",
            audioFile: null,
          });
        } else if (result.reason === "no_url_found") {
          // A note: text with no link in it. Nothing here names the app it came
          // from — no platform tells us — so it is saved as a note (task-380).
          //
          // The same validator the submission uses runs first, so a locked note
          // (which hands over an empty string) and a note past the server's
          // ceiling get their reason on screen rather than a screen that closes.
          const note = validateSharedNoteText(sharedText);
          setIntake(
            "rejection" in note
              ? {
                  status: "invalid",
                  origin: "share",
                  url: null,
                  rawText: sharedText,
                  message: note.rejection.message,
                  contentType: "text",
                  audioFile: null,
                }
              : {
                  status: "ready",
                  origin: "share",
                  url: null,
                  rawText: note.text,
                  message: null,
                  contentType: "text",
                  audioFile: null,
                },
          );
        } else {
          setIntake({
            status: "invalid",
            origin: "share",
            url: null,
            rawText: sharedText,
            message: getShareIntentErrorMessage(result.reason),
            contentType: "url",
            audioFile: null,
          });
        }
        mapped = true;
      } else if (intent.type !== null) {
        // A type we have no branch for. It was still an intentional share, so it
        // gets a sentence rather than the silent reset below.
        setIntake({
          status: "invalid",
          origin: "share",
          url: null,
          rawText: intent.text ?? null,
          message: t("share.reject.nothingToSave"),
          contentType: "url",
          audioFile: null,
        });
        mapped = true;
      }

      if (!mapped) {
        // No type at all: a stale/empty intent surfaced by the native module —
        // clear it so the package doesn't hand it back on the next cycle, and
        // stay put. This is the one case where saying nothing is right.
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
      } else if (pending.kind === "url") {
        applyUrlEntry(pending.url);
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
  }, [
    applyLocalUpload,
    applyUrlEntry,
    navigateToConfirmation,
    processShareIntent,
    revalidateSession,
    router,
  ]);

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
   * pending choice: the next call retries it. It is also said out loud —
   * `reportFolderFailure` below — because the modal is normally gone by then.
   */
  const syncFolder = useCallback((): Promise<void> => {
    const apply = async (): Promise<void> => {
      const tracking = trackingRef.current;
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
   * Say that a folder could not be put on the save.
   *
   * An alert, from the provider, because there is no screen left to say it on:
   * the whole point of applying the choice from here is that it outlives the
   * modal, and the modal closes as soon as a destination is tapped (task-389).
   * The user is told, and the item is still theirs to file from the library.
   */
  const reportFolderFailure = useCallback((error: unknown) => {
    Alert.alert(
      t("common.error"),
      getFriendlyErrorMessage(error, { fallback: t("share.folderFailed") }),
    );
  }, []);

  /**
   * Record the save a submission created: what a folder picked during processing
   * is applied to.
   */
  const registerSave = useCallback(
    (mediaItemId: string, submittedFolderId: string | null) => {
      const tracking = trackingRef.current;
      tracking.saveCreated = true;
      tracking.mediaItemId = mediaItemId || null;
      tracking.appliedFolderId = submittedFolderId;
      // The choice may have been made while this submission was still going out,
      // in which case this is what puts it on the save it just created.
      void syncFolder().catch(reportFolderFailure);
    },
    [reportFolderFailure, syncFolder],
  );

  const selectFolder = useCallback(
    (folder: ShareSelectedFolder | null) => {
      setSelectedFolder(folder);
      trackingRef.current.desiredFolderId = folder?.id ?? null;
      // Applied straight away when the save already exists, so the choice lands
      // even if the user walks away from the modal.
      void syncFolder().catch(reportFolderFailure);
    },
    [reportFolderFailure, syncFolder],
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
        source_app: sourceAppFor(intake.origin),
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
            sourceApp: sourceAppFor(intake.origin),
            folderId,
          })
        : await SharedContentService.ingestSharedAudio(intake.audioFile!, {
            sourceApp: sourceAppFor(intake.origin),
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
   * start, a screen remount and a return from the login screen add up to a
   * single save. A voluntary retry after a failure goes through `retry`, which
   * reopens the door on purpose.
   */
  const submitIntake = useCallback(async (): Promise<void> => {
    const tracking = trackingRef.current;
    if (tracking.inFlight) {
      await tracking.inFlight;
      return;
    }
    if (!isSubmittable(intake.status)) return;

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
   * Start processing the moment the content is understood (task-378, task-379,
   * task-389).
   *
   * The session was revalidated before the intake was mapped
   * (`resumePendingIntake`) and the content was validated while mapping it — or,
   * for a typed URL, by the dialog that collected it — so "ready" means every
   * gate before the submission has been passed and there is nothing left to wait
   * for. The origin is not consulted: a file picked in the app goes out on
   * arrival like the rest, which is what makes the modal's "your media is being
   * saved" true on all three journeys.
   */
  useEffect(() => {
    if (intake.status !== "ready") return;
    const tracking = trackingRef.current;
    if (tracking.autoSubmittedId === tracking.receptionId) return;
    tracking.autoSubmittedId = tracking.receptionId;
    void submitIntake();
  }, [intake.status, submitIntake]);

  /**
   * Start an import from a file picked or captured on the device (task-264).
   *
   * The confirmation screen is opened right away and the upload leaves with it: a
   * photo goes from the shutter to the folder question with nothing in between.
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

  /**
   * Start an ingestion from a URL typed or pasted in the app (task-379).
   *
   * Parked the same way a picked file is, so the one guard that matters is shared:
   * an expired session sends the user to sign in and the URL is applied on the way
   * back rather than lost. The submission itself is fired by the effect above, not
   * from here — which is what keeps a return from the login screen from adding a
   * second save.
   */
  const startUrlEntry = useCallback(
    (url: string) => {
      pendingIntakeRef.current = { kind: "url", url };
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
   * Let the modal go, and clear the native module's stored intent so the same
   * share is not handed back on the next cycle.
   *
   * Nothing is deleted and nothing is awaited (task-389). The question the modal
   * asks is about filing, so neither answer means "throw it away" — a media
   * shared by mistake is removed from the inbox like any other. A submission
   * still in flight keeps its tracking too: it is `beginReception` that starts a
   * fresh one, so the folder patch that follows still lands on the right save.
   */
  const dismissIntake = useCallback(() => {
    setIntake(INITIAL_STATE);
    setSelectedFolder(null);
    lastProcessedKeyRef.current = null;
    resetShareIntent();
  }, [resetShareIntent]);

  /**
   * Retry after an error - go back to ready state.
   *
   * The reception's submission guard is reopened, so the effect above sends the
   * content again exactly as it did on arrival.
   */
  const retry = useCallback(() => {
    if (intake.status === "error") {
      trackingRef.current.autoSubmittedId = null;
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
    selectedFolder,
    setSelectedFolder: selectFolder,
    startLocalUpload,
    startUrlEntry,
    parkCurrentIntakeForAuth,
    dismissIntake,
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
