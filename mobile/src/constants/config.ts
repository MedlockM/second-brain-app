import Constants from "expo-constants";

/**
 * Application configuration derived from app.config.ts extra field.
 * Uses Expo Constants instead of import.meta.env.
 */
const extra = Constants.expoConfig?.extra ?? {};

/**
 * The API host every request is addressed to, with **no fallback**.
 *
 * It used to default to the `api.` host of `mediasummarizer.com`, a domain the
 * project does not own: a build or an update produced without
 * `EXPO_PUBLIC_API_BASE_URL` would have sent authenticated requests — access
 * tokens included — to a host controlled by someone else, and nothing would have
 * said so. A missing configuration has to be loud, so it throws.
 *
 * Reaching this throw takes a manifest with no `extra.apiBaseUrl`, which
 * app.config.ts now refuses to produce (it fails config resolution instead) and
 * which `scripts/mobile_ota_manifest_check.sh` fails the release on.
 */
function requireApiBaseUrl(): string {
  const value =
    typeof extra.apiBaseUrl === "string" ? extra.apiBaseUrl.trim() : "";
  if (!value) {
    throw new Error(
      "No API base URL in this build: expoConfig.extra.apiBaseUrl is empty. " +
        "It was produced without EXPO_PUBLIC_API_BASE_URL, and there is no " +
        "fallback host. Republish with the variable set (mobile/eas.json, the " +
        "build profile's env block).",
    );
  }
  return value;
}

export const Config = {
  API_BASE_URL: requireApiBaseUrl(),
  GOOGLE_CLIENT_ID_WEB: (extra.googleClientIdWeb as string) || "",
  GOOGLE_CLIENT_ID_IOS: (extra.googleClientIdIos as string) || "",
  REVENUCAT_APPLE_KEY: (extra.revenueCatAppleKey as string) || "",
  REVENUCAT_GOOGLE_KEY: (extra.revenueCatGoogleKey as string) || "",
  FEEDBACK_URL: (extra.feedbackUrl as string) || "",
  /**
   * The EAS project this binary belongs to, which `getExpoPushTokenAsync` needs
   * in order to ask Expo for a push token (`pushNotificationService.ts`).
   *
   * Read from the manifest rather than hardcoded a third time: app.config.ts
   * already writes the same constant into `extra.eas.projectId` and into
   * `updates.url`, and a copy here could only ever drift from those.
   *
   * Empty rather than throwing, unlike the API host above: a build with no
   * project id registers no device and the app works exactly as it does for
   * someone who declined the permission — whereas a build with no API host can
   * do nothing at all.
   */
  EAS_PROJECT_ID: (extra.eas?.projectId as string) || "",
} as const;
