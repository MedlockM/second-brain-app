/**
 * Direct-to-S3 transfer for every ingestion flow that carries a file (task-345).
 *
 * The API cannot receive the bytes: requests reach it through API Gateway, which
 * base64-encodes the body into the Lambda event, so any body past 4 718 592 raw
 * bytes is refused by the gateway itself with `Request Entity Too Large` — before
 * the API can translate anything. A 12 MB PDF or a five-minute voice memo would
 * never make it, whatever the documented 50 MB limit said.
 *
 * So the file goes straight to S3, in three steps:
 *
 * 1. `POST /api/media/upload-url` — the API checks format and size, then signs a
 *    PUT on a key namespaced under the caller's id.
 * 2. `PUT` to that URL, without the session: the signature is the credential, and
 *    the bearer must not be sent to a host that is not our API.
 * 3. the ingestion endpoint is called with the returned key, as plain JSON.
 *
 * Everything that fails between the device and S3 surfaces as `DirectUploadError`
 * with an already-translated message: S3 answers XML no user should read, and its
 * status codes describe the signature, not what the user did.
 *
 * That message alone was not enough to fix anything (task-371). The PUT does not
 * traverse API Gateway, so a transfer that dies here leaves **no server-side
 * trace at all** — on 2026-09-06 the API signed a URL, no `/api/media/upload`
 * followed, and the only record of the failure was a sentence saying "check your
 * connection", identical for all three ways this can fail. So every
 * `DirectUploadError` now carries `diagnostics`: which step was reached, the
 * status S3 answered, the S3 error code, and the bytes and MIME type that were
 * sent. There is no telemetry channel in this app, so that detail is rendered on
 * the failure screen — the only place a tester can read it from.
 *
 * Two rules govern what may go in there:
 *
 * - **Never the presigned URL, never any part of its signature, and never the
 *   file's own name.** The query string is a bearer credential for the object;
 *   the name is the title of someone's note. Captured error messages are run
 *   through `redactSensitive`, and the S3 body is never surfaced whole — only its
 *   `<Code>` element, because the `SignatureDoesNotMatch` body embeds
 *   `StringToSign`, `CanonicalRequest` and the access key id.
 * - **Stable ASCII, not translated copy.** The values are read off a screenshot
 *   by whoever fixes the bug, whatever language the reporter's interface is in.
 *
 * That instrumentation then did its job. A TestFlight report on build 9 came back
 * with `stage=read_file · cause=TypeError: Network request failed`, which named the
 * step and, in doing so, showed the message to be a lie: nothing had been sent, and
 * `POST /api/media/upload-url` had not even been called. The file was read with
 * `fetch(uri)`, and on iOS a failure anywhere in `RCTConvert NSURL:` →
 * `RCTFileRequestHandler` surfaces as that one sentence about a network. Reading a
 * local file now goes through `localFileTransfer`, which does not involve one — see
 * that module for what replaced it and why.
 *
 * The diagnostics grew by two fields in the same pass, both of them about the URI
 * the picker handed over and neither of them containing it: `shape=` says whether
 * it carried a space, a non-ASCII character, or escapes it already had, and `ext=`
 * says which extension came with the name. The path itself stays out, as it did
 * from the start — it is the title of someone's note.
 */

import { t } from "../i18n";
import { getFileExtension } from "../types/upload";
import { apiRequest } from "./apiClient";
import {
  describeUriShape,
  putLocalFileToUrl,
  redactSensitive,
  stageLocalFile,
  type LocalFilePutResult,
  type StagedLocalFile,
} from "./localFileTransfer";

/** Which ingestion flow a staged object is destined for. */
export type UploadTarget = "document" | "audio" | "shared_audio";

interface UploadUrlResponse {
  upload_url: string;
  upload_key: string;
  expires_in: number;
}

/**
 * Which step of the transfer failed.
 *
 * - `read_file` — the local file could not be opened or measured, so nothing was
 *   ever sent and the picker's URI is the suspect. `shape` and `ext` are there to
 *   say what about it.
 * - `put_network` — the PUT never came back with a response: no connectivity, a
 *   dropped socket, a request the OS killed.
 * - `put_rejected` — S3 answered, and refused. This is the one a status code and
 *   an error code actually qualify.
 */
export type UploadFailureStage = "read_file" | "put_network" | "put_rejected";

/** Everything known about a failed transfer, at the moment it failed. */
export interface UploadFailureDiagnostics {
  stage: UploadFailureStage;
  /** Scheme of the local URI (`file`, `content`, `ph`…); the path is dropped. */
  uriScheme?: string;
  /**
   * Flags describing the local URI's shape — a space, non-ASCII, existing
   * escapes — never any of its characters. This is what makes a read failure
   * conclusive, since those three are what decide whether a URI parses.
   */
  uriShape?: string;
  /** Extension of the file name, lowercased, without the dot. Not the name. */
  extension?: string;
  /** MIME type declared for the object — what the API signed the PUT for. */
  contentType?: string;
  /** Bytes handed to the PUT. Absent when the file could never be read. */
  bytes?: number;
  /** Status S3 answered with. Absent when no response ever arrived. */
  status?: number;
  /** `<Code>` extracted from S3's XML error body, when it held one. */
  s3Code?: string;
  /** Set when S3 answered but its body came back with no readable text. */
  bodyUnread?: boolean;
  /** Name and message of the thrown error, URLs stripped, truncated. */
  cause?: string;
}

/** How much of a thrown message is worth keeping on a failure screen. */
const MAX_CAUSE_LENGTH = 120;

/**
 * Name and message of a thrown error, redacted, then truncated.
 *
 * The redaction comes first and is unconditional, and it now has real work to do.
 * `fetch` rejected with a bare "Network request failed", so nothing could leak
 * through it — that was also the whole problem. The native calls that replaced it
 * report what actually happened, which means they report the presigned URL when
 * `URLSession` fails and the file's own name when Cocoa cannot open it. See
 * `redactSensitive` for what is removed and why over-removing is the safe side.
 */
function describeCause(error: unknown): string {
  const raw =
    error instanceof Error
      ? `${error.name}${error.message ? `: ${error.message}` : ""}`
      : String(error);
  return redactSensitive(raw).slice(0, MAX_CAUSE_LENGTH);
}

/** The scheme of a local URI, which is the part that says how it was obtained. */
function uriScheme(uri: string): string {
  const match = /^([a-z][a-z0-9+.-]*):/i.exec(uri);
  return match ? match[1].toLowerCase() : "none";
}

/**
 * The `<Code>` of an S3 error body — `SignatureDoesNotMatch`, `EntityTooLarge`,
 * `RequestTimeout` — and nothing else from that body, ever.
 *
 * The shape is constrained on purpose: it bounds what an unexpected body can put
 * on screen to a short identifier.
 */
function extractS3ErrorCode(body: string): string | undefined {
  const match = /<Code>\s*([A-Za-z][A-Za-z0-9_.-]{0,63})\s*<\/Code>/.exec(body);
  return match ? match[1] : undefined;
}

/** One line, meant to be read off a screenshot and typed into a bug report. */
function formatDiagnostics(diagnostics: UploadFailureDiagnostics): string {
  const parts = [`stage=${diagnostics.stage}`];
  if (diagnostics.status !== undefined) {
    parts.push(`status=${diagnostics.status}`);
    if (diagnostics.s3Code) {
      parts.push(`s3=${diagnostics.s3Code}`);
    } else {
      parts.push(diagnostics.bodyUnread ? "s3=unread" : "s3=none");
    }
  }
  if (diagnostics.bytes !== undefined) parts.push(`bytes=${diagnostics.bytes}`);
  if (diagnostics.contentType) parts.push(`type=${diagnostics.contentType}`);
  if (diagnostics.uriScheme) parts.push(`uri=${diagnostics.uriScheme}`);
  if (diagnostics.uriShape) parts.push(`shape=${diagnostics.uriShape}`);
  if (diagnostics.extension) parts.push(`ext=${diagnostics.extension}`);
  if (diagnostics.cause) parts.push(`cause=${diagnostics.cause}`);
  return parts.join(" · ");
}

/**
 * A transfer that never reached S3, or that S3 refused.
 *
 * Carries a message that is already translated, so callers must render it as-is
 * rather than pass it through `getFriendlyErrorMessage` — whose critical-pattern
 * rules would flatten anything mentioning S3 into the generic error sentence.
 *
 * `detail` is the technical half: the same sentence is shown for all three
 * failures, and this is what tells them apart. Callers render it *under* the
 * message, never in place of it.
 */
export class DirectUploadError extends Error {
  readonly diagnostics: UploadFailureDiagnostics;
  readonly detail: string;

  constructor(diagnostics: UploadFailureDiagnostics) {
    super(t("upload.transferFailed"));
    this.name = "DirectUploadError";
    this.diagnostics = diagnostics;
    this.detail = formatDiagnostics(diagnostics);
  }
}

async function putToS3(params: {
  uploadUrl: string;
  fileUri: string;
  bytes: number;
  contentType: string;
}): Promise<void> {
  const shared = { bytes: params.bytes, contentType: params.contentType };
  let result: LocalFilePutResult;
  try {
    result = await putLocalFileToUrl({
      url: params.uploadUrl,
      fileUri: params.fileUri,
      contentType: params.contentType,
    });
  } catch (error) {
    throw new DirectUploadError({
      stage: "put_network",
      ...shared,
      cause: describeCause(error),
    });
  }
  if (result.status < 200 || result.status >= 300) {
    // An expired signature reads 403 and a truncated body 400, and the answer is
    // the same "send it again" either way — but which of the two it was decides
    // what gets fixed, so the status and the S3 code are kept. Still a single
    // attempt: retrying is the user's tap, not this function's business.
    throw new DirectUploadError({
      stage: "put_rejected",
      status: result.status,
      s3Code: result.body === null ? undefined : extractS3ErrorCode(result.body),
      bodyUnread: result.body === null,
      ...shared,
    });
  }
}

/**
 * Send a local file to S3 and return the key the ingestion endpoint expects.
 *
 * `size` is what the picker reported; when it reported nothing, the size read off
 * the file is used, since the API needs a figure to check the ceiling against
 * before signing. Reading comes first for that reason — there is no point signing
 * a URL for a file that cannot be opened, and a failure at that step is the one
 * that leaves no server-side trace of any kind.
 */
export async function stageUpload(params: {
  target: UploadTarget;
  uri: string;
  fileName: string;
  mimeType: string;
  size?: number | null;
}): Promise<string> {
  let staged: StagedLocalFile;
  try {
    staged = await stageLocalFile(params.uri);
  } catch (error) {
    throw new DirectUploadError({
      stage: "read_file",
      uriScheme: uriScheme(params.uri),
      uriShape: describeUriShape(params.uri),
      extension: getFileExtension(params.fileName) || undefined,
      contentType: params.mimeType,
      cause: describeCause(error),
    });
  }

  try {
    const fileSize =
      params.size && params.size > 0 ? params.size : staged.bytes || 1;

    const issued = await apiRequest<UploadUrlResponse>(
      "/api/media/upload-url",
      {
        method: "POST",
        body: {
          target: params.target,
          filename: params.fileName,
          content_type: params.mimeType,
          file_size: fileSize,
        },
      },
    );

    await putToS3({
      uploadUrl: issued.upload_url,
      fileUri: staged.fileUri,
      bytes: staged.bytes,
      contentType: params.mimeType,
    });
    return issued.upload_key;
  } finally {
    staged.release();
  }
}
