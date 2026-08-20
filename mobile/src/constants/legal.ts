/**
 * The legal surfaces the app has to link to, in one place.
 *
 * Apple's guideline 3.1.2 and Google Play's subscription policy both require the
 * **purchase screen itself** to carry working links to the terms of use and the
 * privacy policy — metadata entered in App Store Connect or the Play Console does
 * not satisfy it, and a paywall missing them is one of the most common rejection
 * reasons. They were nowhere in the binary before, which is why they live here
 * rather than inline: the paywall and the deletion screen must point at the same
 * addresses.
 *
 * The URLs are the ones already registered as canonical in
 * `docs/compliance/CHECKLIST.md` and the store-listing docs. OWNER NOTE: both
 * pages still have to be publicly reachable before the first submission — a link
 * that 404s is rejected exactly like a missing one.
 */
import { Platform } from "react-native";

export const TERMS_URL = "https://mediasummarizer.com/terms";

export const PRIVACY_POLICY_URL = "https://mediasummarizer.com/privacy";

/**
 * Where a subscription is actually cancelled. The app cannot cancel one itself —
 * only the store can — so every "cancel anytime" sentence points here.
 */
export const STORE_SUBSCRIPTIONS_URL =
  Platform.OS === "ios"
    ? "https://apps.apple.com/account/subscriptions"
    : "https://play.google.com/store/account/subscriptions";

/** The store that bills the subscription, for copy that has to name it. */
export const STORE_NAME = Platform.OS === "ios" ? "App Store" : "Play Store";

/**
 * Same address as the "Access / Portability" section of the privacy policy: the
 * app has no self-service export, so this is the only route to a data copy and
 * the two must not drift.
 */
export const PRIVACY_CONTACT_EMAIL = "privacy@mediasummarizer.com";
