import { useSyncExternalStore } from "react";

/**
 * The net under a JavaScript error that happens outside a React render.
 *
 * A React error boundary only ever sees what breaks *while rendering*. Everything
 * else — a `throw` in a timer or a native callback, a rejected promise, a `throw`
 * inside an asynchronous effect — reaches React Native's global handler instead,
 * and that handler's release behaviour for a *fatal* error is to call through to
 * `ExceptionsManager` → `RCTFatal`, which aborts the process. That is the
 * `SIGABRT` in the crash report attached to a beta feedback on build 1.0.0 (6): a
 * process iOS had prewarmed in the background, with no interface role, that lived
 * a minute and then aborted from the exception bridge. Nobody saw it, because
 * there was no window — but the system counts those crashes and prewarms an app
 * that keeps aborting less often, which is paid back as latency the next time the
 * share sheet has to open.
 *
 * Two hooks are installed, because they see different things:
 *
 * 1. `ErrorUtils.setGlobalHandler` — every uncaught throw that reaches the
 *    runtime. A fatal one is recorded here and *not* forwarded in a release
 *    build, so `StartupErrorGate` can swap the tree for a readable fallback
 *    instead of the process dying.
 * 2. Hermes' promise rejection tracker — rejections nobody handled. React Native
 *    installs this one itself, but only under `__DEV__`
 *    (`Libraries/Core/polyfillPromise.js`), so in a release build an unhandled
 *    rejection is entirely silent today. `@sentry/react-native` reaches for the
 *    same two hooks, in the same order, for the same reason.
 *
 * **A rejection is logged, never shown.** It does not end the process, and the
 * app is full of deliberate fire-and-forget calls whose failure is recoverable:
 * `AuthContext` schedules a token refresh with `void scheduleRefresh()`, which
 * reads the keychain, and a keychain read is exactly what a *locked* device
 * refuses — the state the observed prewarm was in. Turning that into a
 * full-screen error the user meets on their next launch would be a worse bug than
 * the one this module fixes. So the fallback is reserved for the errors that
 * would otherwise kill the process, and the rejections go to the log, which is
 * more than they had before.
 *
 * Installed from the module scope of `app/_layout.tsx`, next to the splash hold,
 * so it is armed before any provider mounts and for every entry point at once —
 * including a cold start driven by a share, which `+native-intent.tsx` rewrites
 * to `/(tabs)/inbox` and which therefore never mounts the `/` route.
 */

/** Which of the three nets caught the failure. Diagnostic, so never translated. */
export type StartupFailureOrigin =
  | "render"
  | "fatal-error"
  | "unhandled-rejection";

export interface StartupFailure {
  error: Error;
  origin: StartupFailureOrigin;
}

let failure: StartupFailure | null = null;
let installed = false;

const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): StartupFailure | null {
  return failure;
}

/** The failure the tree should be showing instead of itself, if any. */
export function useStartupFailure(): StartupFailure | null {
  return useSyncExternalStore(subscribe, getSnapshot);
}

function describe(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value) ?? String(value);
  } catch {
    return "a thrown value that could not be described";
  }
}

/** Anything can be thrown in JavaScript; the fallback screen wants an `Error`. */
function asError(value: unknown): Error {
  return value instanceof Error ? value : new Error(describe(value));
}

/**
 * The diagnostic channel: one line per caught failure, whether or not it ends up
 * on screen. `console.error` is what reaches the device log in a release build,
 * and the LogBox in development.
 */
export function logStartupFailure(
  value: unknown,
  origin: StartupFailureOrigin,
): void {
  console.error(`[startup-guard] caught ${origin}:`, value);
}

/**
 * Records a failure for the tree to render instead of itself.
 *
 * Only the first one is kept: what follows a fatal error is fallout, and the
 * cause is the thing worth showing.
 */
export function reportStartupFailure(
  value: unknown,
  origin: StartupFailureOrigin,
): void {
  if (failure) return;
  failure = { error: asError(value), origin };
  emit();
}

/** Drops the failure, which puts the real tree back and re-runs the bootstrap. */
export function clearStartupFailure(): void {
  if (!failure) return;
  failure = null;
  emit();
}

function installFatalErrorHandler(): void {
  const previous = ErrorUtils.getGlobalHandler();

  ErrorUtils.setGlobalHandler((error: unknown, isFatal?: boolean) => {
    // A non-fatal error is already handled gracefully by the runtime — reported,
    // then execution continues — so it passes straight through, unlogged here to
    // avoid saying the same thing twice, and without taking the screen over.
    if (!isFatal) {
      forward(previous, error, isFatal);
      return;
    }

    logStartupFailure(error, "fatal-error");
    reportStartupFailure(error, "fatal-error");

    // Development keeps the redbox: it carries the component stack and
    // source-mapped frames, which no in-app screen can match. A release build
    // deliberately stops here — calling through is what aborts the process.
    if (__DEV__) {
      forward(previous, error, isFatal);
    }
  });
}

/** The previous handler must never be the reason the guard itself dies. */
function forward(
  handler: (error: unknown, isFatal?: boolean) => void,
  error: unknown,
  isFatal?: boolean,
): void {
  try {
    handler(error, isFatal);
  } catch {
    // Nothing to do about a handler that throws while reporting a throw.
  }
}

type RejectionTrackingOptions = {
  allRejections: boolean;
  onUnhandled: (id: number, rejection: unknown) => void;
};

type HermesRuntime = {
  enablePromiseRejectionTracker?: (options: RejectionTrackingOptions) => void;
};

function installRejectionTracker(): void {
  // Hermes is the engine both platforms ship, and the tracker is its own hook —
  // an engine without it simply gets the fatal handler above.
  const hermes = (globalThis as { HermesInternal?: HermesRuntime | null })
    .HermesInternal;
  if (!hermes?.enablePromiseRejectionTracker) return;

  // React Native and `@expo/metro-runtime` both install this tracker themselves,
  // and both do it under `__DEV__` only. So this is the only one in a release
  // build, and in development it replaces theirs: an unhandled rejection then
  // surfaces as this `console.error` rather than as their own report. Same
  // information, one channel.
  hermes.enablePromiseRejectionTracker({
    allRejections: true,
    onUnhandled: (_id, rejection) => {
      logStartupFailure(rejection, "unhandled-rejection");
    },
  });
}

/** Arms both global handlers. Idempotent, so a fast refresh cannot stack them. */
export function installStartupErrorGuard(): void {
  if (installed) return;
  installed = true;
  installFatalErrorHandler();
  installRejectionTracker();
}
