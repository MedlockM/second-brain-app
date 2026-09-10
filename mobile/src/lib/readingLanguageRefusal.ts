/**
 * The once-a-month reading-language guard-rail, put into words.
 *
 * Changing the reading language re-translates every media the reader opens
 * next, so the backend allows one change per month and per account. It refuses
 * the second one with the stable code `reading_language_change_too_soon` and the
 * instant the guard lifts — never a sentence, which it could not word in the
 * reader's interface language anyway (task-359). The sentence is built here,
 * from this app's catalogue, the same way `quotaError.ts` builds a refused
 * import's.
 *
 * Both halves of the feature share this module: the *notice* the settings screen
 * shows before anything is tapped, and the *refusal* returned to a save that
 * went through anyway (a stale availability date, a second device, any client at
 * all). One sentence covers both — "once a month, next change on X" is as true
 * before the attempt as after it.
 */

import { formatDate, t } from "../i18n";
import type { HttpError } from "./httpError";

export const READING_LANGUAGE_CHANGE_TOO_SOON =
  "reading_language_change_too_soon";

/** Whether a failed language save is the monthly guard-rail talking. */
export function isReadingLanguageChangeTooSoon(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  return (error as HttpError).code === READING_LANGUAGE_CHANGE_TOO_SOON;
}

/**
 * The unlock instant written for the active locale, or `null` when there is
 * nothing to wait for — no date at all, an unparseable one, or one already past.
 * A date in the past means the guard has lifted since the value was read, and
 * announcing it would be worse than saying nothing.
 */
function formatUnlockDate(availableAt: unknown): string | null {
  if (typeof availableAt !== "string") return null;
  const timestamp = new Date(availableAt).getTime();
  if (Number.isNaN(timestamp) || timestamp <= Date.now()) return null;
  const date = new Date(timestamp);
  const isCurrentYear = date.getFullYear() === new Date().getFullYear();
  return formatDate(date, {
    month: "long",
    day: "numeric",
    ...(isCurrentYear ? {} : { year: "numeric" }),
  });
}

/**
 * The notice to show while the guard-rail holds, or `null` when a change is
 * possible right now. `availableAt` is `AuthUser.reading_language_change_available_at`.
 */
export function describeReadingLanguageLimit(
  availableAt: string | null | undefined,
): string | null {
  const date = formatUnlockDate(availableAt);
  return date === null ? null : t("readingLanguage.changeLimit", { date });
}

/**
 * The refusal, worded from the date the backend sent. Falls back to the dateless
 * sentence when the refusal reaches the app without its body: a shorter true
 * sentence beats one with a hole where a date should be.
 */
export function describeReadingLanguageRefusal(error: unknown): string {
  const details = (error as HttpError | undefined)?.details ?? {};
  const date = formatUnlockDate(details.available_at);
  return date === null
    ? t("readingLanguage.changeLimitNoDate")
    : t("readingLanguage.changeLimit", { date });
}
