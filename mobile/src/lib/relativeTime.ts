/**
 * Short relative timestamps ("3h ago", "11d ago").
 *
 * Extracted so the artifact history and the media vignettes read the same
 * wording from one place — and so that adding a date library for this stays
 * unnecessary: the whole need is six branches over a millisecond difference.
 */

import { formatDate, t, tCount } from "../i18n";

export function getRelativeTime(isoDate: string): string {
  const now = Date.now();
  const date = new Date(isoDate).getTime();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return t("time.justNow");
  if (diffMins < 60) return tCount("time.minutesAgo", diffMins);
  if (diffHours < 24) return tCount("time.hoursAgo", diffHours);
  if (diffDays === 1) return t("time.yesterday");
  if (diffDays < 7) return tCount("time.daysAgo", diffDays);
  // The active UI locale, not `undefined`: that resolves to the system locale,
  // which the in-app override is allowed to disagree with.
  return formatDate(new Date(isoDate), {
    month: "short",
    day: "numeric",
  });
}
