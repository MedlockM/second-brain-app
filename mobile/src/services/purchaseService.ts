/**
 * RevenueCat purchase service for managing in-app subscriptions.
 *
 * Wraps react-native-purchases SDK to provide a clean interface
 * for subscription management in the mobile app.
 *
 * **Nothing here wraps the SDK's restore call, deliberately** (task-336). The
 * wrapper that used to sit here claimed to be "required by Apple App Store
 * guidelines", which misread 3.1.1 — a "should", asking for *a* restore
 * mechanism. The mechanism here is the account: `identifyUser()` below binds the
 * RevenueCat customer to the backend user id, and entitlements are read from
 * `GET /api/entitlements/status`, so signing in on a new device is the restore.
 * Restoring on an App User ID that already owns the purchase changes no state,
 * therefore emits no webhook, and would leave the backend as it found it.
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

/**
 * Why a purchase did not go through, in the terms a buyer can act on.
 *
 * Five outcomes out of the SDK's thirty-odd error codes, because five is how many
 * different things there are to do about it: wait for the network, wait for the
 * store, lift a device restriction, fix a payment method, or nothing at all
 * because the subscription is already owned. Everything else is one of ours and
 * reads the same. `getFriendlyErrorMessage` maps each to its sentence.
 */
export type PurchaseFailureCode =
  | "PURCHASE_NETWORK"
  | "PURCHASE_STORE_PROBLEM"
  | "PURCHASE_NOT_ALLOWED"
  | "PURCHASE_PAYMENT_INVALID"
  | "PURCHASE_ALREADY_OWNED"
  | "PURCHASE_FAILED";

export type PurchaseResult =
  | { status: "success"; customerInfo: CustomerInfo }
  | { status: "cancelled" }
  | { status: "pending" }
  | { status: "error"; code: PurchaseFailureCode };

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

/** The SDK's error code, narrowed to the outcomes worth telling apart. */
const PURCHASE_FAILURE_CODES: Partial<
  Record<PURCHASES_ERROR_CODE, PurchaseFailureCode>
> = {
  [PURCHASES_ERROR_CODE.NETWORK_ERROR]: "PURCHASE_NETWORK",
  [PURCHASES_ERROR_CODE.OFFLINE_CONNECTION_ERROR]: "PURCHASE_NETWORK",
  [PURCHASES_ERROR_CODE.STORE_PROBLEM_ERROR]: "PURCHASE_STORE_PROBLEM",
  [PURCHASES_ERROR_CODE.PRODUCT_REQUEST_TIMED_OUT_ERROR]:
    "PURCHASE_STORE_PROBLEM",
  [PURCHASES_ERROR_CODE.PURCHASE_NOT_ALLOWED_ERROR]: "PURCHASE_NOT_ALLOWED",
  [PURCHASES_ERROR_CODE.PURCHASE_INVALID_ERROR]: "PURCHASE_PAYMENT_INVALID",
  [PURCHASES_ERROR_CODE.PRODUCT_ALREADY_PURCHASED_ERROR]:
    "PURCHASE_ALREADY_OWNED",
  [PURCHASES_ERROR_CODE.RECEIPT_ALREADY_IN_USE_ERROR]: "PURCHASE_ALREADY_OWNED",
};

/**
 * Trigger the native purchase flow for a given package.
 * Handles success, cancellation, pending (Ask to Buy), and errors.
 *
 * A failure comes back as a code, never as `error.message`. The SDK's message is
 * written for a developer — it quotes the store's own diagnostics, and on Android
 * it has been known to name the billing library — so the paywall would have put
 * that in an alert under "Purchase failed".
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

    console.error("[PurchaseService] Purchase error:", error);
    return {
      status: "error",
      code: PURCHASE_FAILURE_CODES[error.code as PURCHASES_ERROR_CODE] ??
        "PURCHASE_FAILED",
    };
  }
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
