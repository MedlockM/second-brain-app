import type { ReactNode } from "react";
import { clearStartupFailure, useStartupFailure } from "../lib/startupErrorGuard";
import { StartupErrorScreen } from "./StartupErrorScreen";

/**
 * Swaps the whole tree for `StartupErrorScreen` when the global handlers have
 * caught something fatal.
 *
 * This is the half of the guard a React error boundary cannot do. A boundary only
 * sees a render; a rejected promise or a `throw` inside an asynchronous effect
 * reaches `ErrorUtils` instead, and no component re-renders as a result. So the
 * failure recorded there is published as a store, and this is what subscribes to
 * it.
 *
 * Mounted as the outermost thing inside the root layout, above every provider —
 * including the share-intent provider — because any of them can be what failed,
 * and the fallback must not depend on a provider that is broken or was never
 * reached. Retrying drops the failure, which mounts the real tree again and
 * re-runs the bootstrap from scratch.
 */
export function StartupErrorGate({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const failure = useStartupFailure();

  if (!failure) return children;

  return (
    <StartupErrorScreen
      error={failure.error}
      origin={failure.origin}
      onRetry={clearStartupFailure}
    />
  );
}
