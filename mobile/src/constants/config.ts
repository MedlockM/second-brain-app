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
} as const;
