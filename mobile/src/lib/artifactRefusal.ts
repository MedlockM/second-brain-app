/**
 * Turn a refused generation into a sentence the user can act on.
 *
 * Every refusal the artifact API returns is typed and carries its numbers, so
 * neither AI tab has to fall back on a spinner that never ends or an error that
 * says nothing. Shared between the media tab and the collection tab: the same
 * refusals reach both, and they should read the same.
 */

import { getFriendlyErrorMessage } from "./getFriendlyErrorMessage";
import type { HttpError } from "./httpError";
import { getQuotaErrorCode, getQuotaErrorMessage } from "./quotaError";

export function describeArtifactRefusal(
  err: unknown,
  options?: { scope?: "media" | "folder" },
): string {
  const httpError = err as HttpError | undefined;
  const details = httpError?.details ?? {};
  const code = httpError?.code ?? httpError?.quotaErrorCode;
  const isCollection = options?.scope === "folder";

  // A generation over a single item is free, so only a collection can ever run
  // into the minute allowance. The backend sentence already carries the figures
  // (how many minutes this needs, how many are left, when they reset), so it is
  // repeated verbatim instead of being flattened into a generic quota line.
  const quotaCode = getQuotaErrorCode(err);
  if (quotaCode) {
    return getQuotaErrorMessage(err, quotaCode);
  }

  switch (code) {
    case "scope_empty":
      return isCollection
        ? "This collection has no source with a transcript yet. Add media, or wait for the ones you saved to finish processing."
        : "This item has no transcript yet, so there is nothing to generate from.";
    case "scope_too_large": {
      const sourceCount = Number(details.source_count ?? 0);
      const maxSources = Number(details.max_sources ?? 0);
      if (sourceCount > 0 && maxSources > 0 && sourceCount > maxSources) {
        return `This collection has ${sourceCount} sources, over the ${maxSources} a single generation can read. Generate on a smaller sub-collection instead.`;
      }
      return "There is too much text here for one generation. Generate on a smaller sub-collection instead.";
    }
    case "sources_not_ready": {
      const pending = Number(details.pending_count ?? 0);
      if (isCollection && pending > 0) {
        return `${pending} ${pending === 1 ? "source is" : "sources are"} still being prepared. Try again in a moment.`;
      }
      return "The transcript is still being prepared. Try again in a moment.";
    }
    default:
      return getFriendlyErrorMessage(err, {
        fallback: "Unable to start this generation. Please try again.",
      });
  }
}
