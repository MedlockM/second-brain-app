import * as SecureStore from "expo-secure-store";

const DISMISSED_RESET_DATE_KEY = "minutes_warning_dismissed_for";

/**
 * Remembers that the user closed the "80% of your minutes" banner.
 *
 * The dismissal is keyed on the period it applies to: what is stored is the
 * `resets_at` the banner was showing when it was closed. The next period carries
 * a different date, so the banner comes back on its own with no expiry logic and
 * no clock comparison — and it does not come back for the rest of the period the
 * user already acknowledged.
 *
 * SecureStore is the app's only key/value store (AsyncStorage was removed in V1).
 * It is overkill for a boolean, but writing a reset date is harmless and keeps the
 * banner quiet across app restarts, which is the whole point of "not repeated".
 */
export const UsageWarningDismissal = {
  /** Whether the banner for this reset date was already dismissed. */
  async isDismissed(resetsAt: string | null): Promise<boolean> {
    if (!resetsAt) return false;
    try {
      const stored = await SecureStore.getItemAsync(DISMISSED_RESET_DATE_KEY);
      return stored === resetsAt;
    } catch {
      // A storage failure must not hide the warning: showing it once more is a
      // smaller error than swallowing the only notice the user gets.
      return false;
    }
  },

  async dismiss(resetsAt: string | null): Promise<void> {
    if (!resetsAt) return;
    try {
      await SecureStore.setItemAsync(DISMISSED_RESET_DATE_KEY, resetsAt);
    } catch {
      // Best effort: the banner reappearing next launch is acceptable, crashing
      // the inbox because the keychain refused a write is not.
    }
  },
} as const;
