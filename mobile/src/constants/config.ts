import Constants from "expo-constants";

/**
 * Application configuration derived from app.config.ts extra field.
 * Uses Expo Constants instead of import.meta.env.
 */
const extra = Constants.expoConfig?.extra ?? {};

export const Config = {
  API_BASE_URL: extra.apiBaseUrl as string || "https://api.mediasummarizer.com",
  REVENUCAT_APPLE_KEY: extra.revenueCatAppleKey as string || "",
  REVENUCAT_GOOGLE_KEY: extra.revenueCatGoogleKey as string || "",
} as const;
