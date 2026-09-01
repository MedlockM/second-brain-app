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
import { formatNumber, t, tCount } from "../i18n";

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
        ? t("artifacts.refusal.collectionEmpty")
        : t("artifacts.refusal.mediaEmpty");
    case "scope_too_large": {
      const sourceCount = Number(details.source_count ?? 0);
      const maxSources = Number(details.max_sources ?? 0);
      if (sourceCount > 0 && maxSources > 0 && sourceCount > maxSources) {
        return t("artifacts.refusal.tooManySources", {
          count: formatNumber(sourceCount),
          max: formatNumber(maxSources),
        });
      }
      return t("artifacts.refusal.tooMuchText");
    }
    case "sources_not_ready": {
      const pending = Number(details.pending_count ?? 0);
      if (isCollection && pending > 0) {
        return tCount("artifacts.refusal.sourcesPending", pending);
      }
      return t("artifacts.refusal.transcriptPending");
    }
    // The other 409, and the opposite instruction: the translation this needed
    // was refused by the provider for a reason a retry cannot change, so the
    // sentence says so instead of sending the reader back in a moment. The
    // response carries `terminal: true` for the same reason.
    case "translation_failed": {
      const failed = Number(details.failed_count ?? 0);
      if (isCollection && failed > 0) {
        return tCount("artifacts.refusal.sourcesTranslationFailed", failed);
      }
      return t("artifacts.refusal.translationFailed");
    }
    default:
      return getFriendlyErrorMessage(err, {
        fallback: t("artifacts.refusal.generic"),
      });
  }
}
