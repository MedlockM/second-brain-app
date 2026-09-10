/**
 * Reading a file off the device and handing its bytes to S3 — the two halves of
 * every upload in this app, and the one place that knows a local URI is not a URL
 * you can `fetch`.
 *
 * `fetch(uri)` followed by `.blob()` was how both callers read a picked or shared
 * file. It is an anti-pattern, and a TestFlight report on build 9 (iOS 26.6.1)
 * caught it: a note exported as Markdown and shared to the app produced
 *
 *     stage=read_file · type=text/plain · uri=file · cause=TypeError: Network request failed
 *
 * Nothing had been sent when that appeared — `POST /api/media/upload-url` had not
 * even been called. And that sentence is a constant, not a finding: whatwg-fetch's
 * `xhr.onerror` handler reads `reject(new TypeError('Network request failed'))`
 * and takes no argument, so *every* transport failure arrives under that one
 * message and the real reason is discarded on the way. On iOS the real reason came
 * from `RCTFileRequestHandler`, which stats the path with
 * `attributesOfItemAtPath:` and then reads it with `dataWithContentsOfURL:`; both
 * produce an `NSError` saying exactly what went wrong, and neither ever reached
 * the screen. No amount of instrumentation on that call could have named the
 * cause, because the cause was thrown away one layer below the instrumentation.
 *
 * Android read the same bytes by another route — `BlobModule` registers a
 * `UriHandler` for every non-http scheme and goes through the content resolver —
 * so the failure surfaced on iOS first. The blind spot is shared, and so is the
 * correction.
 *
 * Two `expo-file-system` primitives replace it:
 *
 * - `new File(uri)` normalises the URI through the WHATWG URL parser Expo
 *   installs (`whatwg-url-minimum`, `expo/src/winter`): a raw space becomes
 *   `%20`, an accented character becomes its UTF-8 percent triplets, and a URI
 *   that already carries escapes is left exactly as it is. On the native side the
 *   string is then converted by expo-modules-core's own `URL` convertible, which
 *   falls back to `URL(fileURLWithPath:)` and to percent-encoding before giving
 *   up. Above all, a failure at any of these steps throws *its own* error, with
 *   its own message, instead of being flattened into a sentence about a network.
 * - `uploadAsync(…, BINARY_CONTENT)` streams the file from disk natively
 *   (`URLSession.uploadTask(with:fromFile:)` on iOS, OkHttp `asRequestBody` on
 *   Android), so the bytes never enter the JavaScript heap. That matters at this
 *   app's 50 MB ceiling: reading the file into a `Uint8Array` and letting `fetch`
 *   send it costs three copies of the file (the array, whatwg-fetch's clone, and
 *   the base64 string `convertRequestBody` builds), where the old blob at least
 *   stayed native.
 *
 * Nothing here narrows what is readable. On iOS `expo-file-system` resolves
 * permissions by `FileSystemUtilities.permissions`, which grants read and write on
 * the cache and document directories *and on the app group containers* — where the
 * share extension puts what it copies — and otherwise defers to the OS for any
 * other `file://` path. It is a superset of what `RCTFileRequestHandler` allowed.
 *
 * No native module is added by any of this: `expo-file-system` ships as a
 * dependency of `expo` itself and is already autolinked, so the fix is
 * deliverable over the air.
 */

import { File as FsFile, Paths } from "expo-file-system";
import {
  FileSystemSessionType,
  FileSystemUploadType,
  uploadAsync,
} from "expo-file-system/legacy";

/**
 * Everything a native error may name that must not be shown, in the order it has
 * to be removed — earlier matches contain the slashes and dots later rules would
 * otherwise chew on.
 *
 * 1. **A URL.** A presigned one carries `X-Amz-Signature` in its query string and
 *    is a bearer credential for the object. The iOS upload rejects with `Unable to
 *    upload the file: '<NSError description>'`, and an `NSError` from `URLSession`
 *    prints its `userInfo`, `NSErrorFailingURLKey` included.
 * 2. **A quoted run.** Cocoa's own sentence is *The file “Ma note.md” couldn't be
 *    opened because there is no such file*, and that title belongs to the user, on
 *    a screen that ends up as a screenshot in App Store Connect. Straight single
 *    quotes are deliberately *not* delimiters: they are the apostrophe in
 *    "couldn't", and what native modules put between them is a URI or a path,
 *    which rules 1 and 3 already take. Curly `’` is excluded for the same reason.
 * 3. **A path.** It names the file even unquoted. Two segments are required so
 *    that an "and/or" in prose is left alone.
 * 4. **Anything still shaped like `name.ext`,** because rules 1 and 3 stop at a
 *    space and a note is often called `Compte rendu 12 mai.md`. Up to five words
 *    before the extension go with it. `[` and `]` are excluded from the run so it
 *    cannot swallow the markers the rules above just left behind.
 *
 * Losing the extension here costs nothing: it is reported on its own as `ext=`.
 * And over-redacting is the safe direction — a sentence with a hole in it still
 * says which step failed and which `NSError` domain and code came back, while a
 * leaked note title cannot be taken back.
 */
const REDACTIONS: readonly (readonly [RegExp, string])[] = [
  [/\b[a-z][a-z0-9+.-]*:\/\/\S+/gi, "[url]"],
  [/["“‘«][^"“”‘’«»]{1,200}["”’»]/g, "[name]"],
  [/\/[^\s/]+(?:\/[^\s/]+)+/g, "[path]"],
  [/[^\s[\]]+(?: [^\s[\]]+){0,4}\.[A-Za-z0-9]{1,8}\b/g, "[file]"],
];

/** Remove from a message everything that identifies a file or authenticates. */
export function redactSensitive(text: string): string {
  return REDACTIONS.reduce(
    (redacted, [pattern, replacement]) =>
      redacted.replace(pattern, replacement),
    text,
  );
}

/** True when any code unit is outside ASCII. Spelled out to avoid a regex whose
 * character class would have to name control characters. */
function hasNonAscii(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    if (value.charCodeAt(index) > 127) return true;
  }
  return false;
}

/**
 * What a local URI *looks like*, as flags — never any part of its value.
 *
 * The path of a shared file is user content: it is the title of their note, the
 * name of their document. It cannot be put on a failure screen, because that
 * screen is what gets screenshotted into App Store Connect. But the shape of the
 * path is exactly what decides whether a URI survives being parsed, so the flags
 * are what makes a persisting read failure conclusive: `space` and `nonascii`
 * say the URI needed encoding, `pctenc` says it already had some.
 */
const URI_SHAPE_FLAGS: readonly {
  flag: string;
  test: (uri: string) => boolean;
}[] = [
  { flag: "space", test: (uri) => uri.includes(" ") },
  { flag: "nonascii", test: hasNonAscii },
  { flag: "pctenc", test: (uri) => /%[0-9A-Fa-f]{2}/.test(uri) },
];

/** One token joining the flags that apply, or `plain` when none do. */
export function describeUriShape(uri: string): string {
  const flags = URI_SHAPE_FLAGS.filter(({ test }) => test(uri)).map(
    ({ flag }) => flag,
  );
  return flags.length > 0 ? flags.join("+") : "plain";
}

/** The local file is not there, or the app cannot read it. */
export class LocalFileUnavailableError extends Error {
  constructor() {
    super("not found or not readable");
    this.name = "LocalFileUnavailable";
  }
}

/** The transfer never came back with a response. Message already redacted. */
export class LocalFileTransferError extends Error {
  constructor(cause: unknown) {
    super(
      redactSensitive(cause instanceof Error ? cause.message : String(cause)),
    );
    this.name = "LocalFileTransferError";
  }
}

/** A local file resolved to something the native upload can stream from. */
export interface StagedLocalFile {
  /** Percent-encoded `file://` URI, normalised from whatever the picker gave. */
  fileUri: string;
  /** Size on disk, from a stat — the file itself was not read to obtain it. */
  bytes: number;
  /**
   * Drops whatever staging had to create, and nothing else: the file the user
   * picked or shared is never deleted. No-op when nothing was created, never
   * throws, safe to call more than once.
   */
  release: () => void;
}

const NOTHING_TO_RELEASE = (): void => {};

/** A single path segment for the cache copy, with a sane extension or none. */
function cacheCopyName(source: FsFile): string {
  const extension = source.extension.replace(/[^a-zA-Z0-9.]/g, "").slice(0, 12);
  const token = Math.random().toString(36).slice(2, 8);
  return `upload-${Date.now()}-${token}${extension}`;
}

/**
 * Resolve a local URI to a readable file, and report its size.
 *
 * `exists` is checked before `size` for two reasons. It answers `false` rather
 * than throwing when the file is missing or unreadable, which is the case worth
 * expecting here and which then produces a diagnostic naming that and nothing
 * else — where `size` on a missing file throws Cocoa's *The file “…” couldn't be
 * opened*, whose quoted half is the user's own note title.
 *
 * @throws {LocalFileUnavailableError} when the URI resolves to nothing readable.
 * @throws Error the native module's own, when the stat or the copy fails. Callers
 *   put those through `redactSensitive` before showing them.
 */
export async function stageLocalFile(uri: string): Promise<StagedLocalFile> {
  const source = new FsFile(uri);
  if (!source.exists) {
    throw new LocalFileUnavailableError();
  }
  const bytes = source.size;

  if (source.uri.startsWith("file:")) {
    return { fileUri: source.uri, bytes, release: NOTHING_TO_RELEASE };
  }

  // A `content://` URI — what the Android share intent falls back to when it
  // cannot resolve an absolute path for a document provider — has no path a
  // native upload can stream from (`Uri.toFile()` refuses any scheme but
  // `file`). So it is copied into the cache first. This is the one branch that
  // does put the whole file in the JavaScript heap; `expo-file-system` offers no
  // native copy from a SAF source, and it is the rare branch of the two.
  const copy = new FsFile(Paths.cache, cacheCopyName(source));
  copy.write(await source.bytes());
  return {
    fileUri: copy.uri,
    bytes: copy.size || bytes,
    release: () => {
      try {
        copy.delete();
      } catch {
        // A leftover in the cache directory is the system's to reclaim; failing
        // to clean up must not turn a finished upload into an error.
      }
    },
  };
}

/** What the server answered a staged PUT with. */
export interface LocalFilePutResult {
  status: number;
  /** The response body, or `null` when the platform returned none readable. */
  body: string | null;
}

/**
 * PUT a staged local file to a URL, in one attempt.
 *
 * A non-2xx is *returned*, not thrown: the status and the body are what tell a
 * refusal apart from a transport failure, and only the caller knows what to make
 * of them.
 *
 * @throws {LocalFileTransferError} when no response ever arrived.
 */
export async function putLocalFileToUrl(params: {
  url: string;
  fileUri: string;
  contentType: string;
}): Promise<LocalFilePutResult> {
  try {
    const result = await uploadAsync(params.url, params.fileUri, {
      httpMethod: "PUT",
      uploadType: FileSystemUploadType.BINARY_CONTENT,
      // iOS only, and deliberate: a background session "continues retrying until
      // the task succeeds or is canceled", which is an automatic retry nobody
      // asked for and the exact thing task-371 kept out. One attempt stays one
      // attempt, and "Retry" stays the user's tap.
      sessionType: FileSystemSessionType.FOREGROUND,
      headers: { "Content-Type": params.contentType },
    });
    return {
      status: result.status,
      body: typeof result.body === "string" ? result.body : null,
    };
  } catch (error) {
    throw new LocalFileTransferError(error);
  }
}
