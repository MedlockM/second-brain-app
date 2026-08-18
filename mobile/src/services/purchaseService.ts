/**
 * RevenueCat purchase service for managing in-app subscriptions.
 *
 * Wraps react-native-purchases SDK to provide a clean interface
 * for subscription management in the mobile app.
 */
import Purchases, {
  CustomerInfo,
  PurchasesOfferings,
  PurchasesPackage,
  LOG_LEVEL,
  PURCHASES_ERROR_CODE,
} from "react-native-purchases";
import { Platform } from "react-native";
import { Config } from "../constants/config";

export type PurchaseResult =
  | { status: "success"; customerInfo: CustomerInfo }
  | { status: "cancelled" }
  | { status: "pending" }
  | { status: "error"; message: string };

/**
 * Initialize RevenueCat SDK with platform-specific API keys.
 * Must be called once at app startup (after authentication).
 */
export async function initializePurchases(): Promise<void> {
  const apiKey =
    Platform.OS === "ios"
      ? Config.REVENUCAT_APPLE_KEY
      : Config.REVENUCAT_GOOGLE_KEY;

  if (!apiKey) {
    console.warn(
      "[PurchaseService] No RevenueCat API key configured for platform:",
      Platform.OS,
    );
    return;
  }

  if (__DEV__) {
    Purchases.setLogLevel(LOG_LEVEL.DEBUG);
  }

  await Purchases.configure({ apiKey });
}

/**
 * Identify the current user with RevenueCat using our backend user ID.
 * This links the RevenueCat customer with our user, enabling webhook
 * correlation with the app_user_id field.
 */
export async function identifyUser(userId: string): Promise<CustomerInfo> {
  const { customerInfo } = await Purchases.logIn(userId);
  return customerInfo;
}

/**
 * Log out the current user from RevenueCat (on app logout).
 */
export async function logOutUser(): Promise<void> {
  await Purchases.logOut();
}

/**
 * Fetch available subscription offerings from RevenueCat.
 * Returns the configured packages (tiers) available for purchase.
 */
export async function getOfferings(): Promise<PurchasesOfferings | null> {
  try {
    const offerings = await Purchases.getOfferings();
    return offerings;
  } catch (error) {
    console.error("[PurchaseService] Failed to fetch offerings:", error);
    return null;
  }
}

/**
 * Trigger the native purchase flow for a given package.
 * Handles success, cancellation, pending (Ask to Buy), and errors.
 */
export async function purchasePackage(
  pkg: PurchasesPackage,
): Promise<PurchaseResult> {
  try {
    const { customerInfo } = await Purchases.purchasePackage(pkg);
    return { status: "success", customerInfo };
  } catch (error: any) {
    if (error.userCancelled) {
      return { status: "cancelled" };
    }

    // Handle deferred/pending purchases (e.g., Ask to Buy on iOS)
    if (error.code === PURCHASES_ERROR_CODE.PAYMENT_PENDING_ERROR) {
      return { status: "pending" };
    }

    const message =
      error.message || "An error occurred during purchase. Please try again.";
    console.error("[PurchaseService] Purchase error:", error);
    return { status: "error", message };
  }
}

/**
 * Restore previous purchases (required by Apple App Store guidelines).
 * Syncs any purchases made on other devices or after reinstall.
 */
export async function restorePurchases(): Promise<CustomerInfo> {
  const customerInfo = await Purchases.restorePurchases();
  return customerInfo;
}

/**
 * Get current customer info including entitlements.
 * Useful for checking subscription status without triggering a purchase.
 */
export async function getCustomerInfo(): Promise<CustomerInfo> {
  const customerInfo = await Purchases.getCustomerInfo();
  return customerInfo;
}

/**
 * RevenueCat entitlement identifiers, one per subscription tier.
 *
 * Must stay in sync with the lookup keys of the entitlements in project
 * `proj879a771a` and with `ENTITLEMENT_TIER_MAP` in
 * `media_summarizer/api/endpoints/revenucat_webhook.py`.
 * Layout reference: `docs/REVENUECAT_ENTITLEMENTS.md`.
 */
export const TIER_ENTITLEMENT_IDS = [
  "tier_text_only",
  "tier_mix",
  "tier_audio_heavy",
] as const;

/**
 * Whether any tier entitlement is active for this customer.
 *
 * This is a boolean access gate only — it deliberately does not tell the tiers
 * apart. The tier itself comes from `GET /api/entitlements/status`, which
 * reads the subscription row the webhook writes.
 */
export function hasActiveEntitlement(customerInfo: CustomerInfo): boolean {
  return TIER_ENTITLEMENT_IDS.some((id) => {
    const entitlement = customerInfo.entitlements.active[id];
    return entitlement !== undefined && entitlement.isActive;
  });
}
