/**
 * PurchasesContext provides subscription state to the entire app.
 *
 * Handles RevenueCat initialization, user identification, and
 * exposes subscription status for paywall gating.
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { CustomerInfo } from "react-native-purchases";
import {
  initializePurchases,
  identifyUser,
  logOutUser,
  getCustomerInfo,
  hasActiveEntitlement,
} from "../services/purchaseService";
import { useAuth } from "./AuthContext";
import { apiRequest } from "../services/apiClient";

/**
 * What `GET /api/entitlements/status` returns: the caller's own state, and
 * nothing about what a plan costs or includes — that is `GET /api/pricing`,
 * read by `src/services/pricingService.ts`. The endpoint used to append an
 * `offerings_config` / `minutes_legend` pair for callers without a plan, which
 * this app declared and never read; it is gone (task-299).
 *
 * Minutes are the only metered unit, so the gauge is one number over one total.
 * `resets_at` is the end of the period it describes: the renewal anniversary on
 * a subscription, the trial's close during the free trial, after which nothing
 * refills at all.
 */
export interface EntitlementStatus {
  user_id: string;
  subscription_tier: "S" | "M" | "L" | null;
  subscription_status: string | null;
  is_active: boolean;
  is_free_trial: boolean;
  auto_renew_status: boolean | null;
  /** Minutes the plan includes for the current period. */
  minutes_included: number;
  /** Minutes already spent in the current period. */
  minutes_used: number;
  /** Minutes left, never negative. */
  minutes_remaining: number;
  /** Longest single import this plan accepts, in minutes. */
  max_minutes_per_item: number;
  /** When the allowance refills. Nothing rolls over. */
  resets_at: string | null;
  /** Backend-owned threshold (80%): time to warn the user. */
  warning_threshold_reached: boolean;
}

interface PurchasesContextValue {
  /** Whether RevenueCat has been initialized */
  isInitialized: boolean;
  /** Current customer info from RevenueCat */
  customerInfo: CustomerInfo | null;
  /** Backend entitlement status */
  entitlementStatus: EntitlementStatus | null;
  /** Whether the user has an active subscription */
  isSubscribed: boolean;
  /** Loading state for subscription checks */
  isLoading: boolean;
  /** Refresh entitlement status from backend */
  refreshEntitlements: () => Promise<void>;
}

const PurchasesContext = createContext<PurchasesContextValue | null>(null);

export function PurchasesProvider({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [isInitialized, setIsInitialized] = useState(false);
  const [customerInfo, setCustomerInfo] = useState<CustomerInfo | null>(null);
  const [entitlementStatus, setEntitlementStatus] =
    useState<EntitlementStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize RevenueCat on mount
  useEffect(() => {
    const init = async () => {
      try {
        await initializePurchases();
        setIsInitialized(true);
      } catch (error) {
        console.error("[PurchasesContext] Failed to initialize RevenueCat:", error);
      }
    };
    init();
  }, []);

  // Identify user with RevenueCat after authentication
  useEffect(() => {
    if (!isInitialized || !isAuthenticated || !user?.id) return;

    const identify = async () => {
      try {
        const info = await identifyUser(user.id);
        setCustomerInfo(info);
      } catch (error) {
        console.error("[PurchasesContext] Failed to identify user:", error);
      }
    };
    identify();
  }, [isInitialized, isAuthenticated, user?.id]);

  // Log out from RevenueCat when user logs out
  useEffect(() => {
    if (!isInitialized || isAuthenticated) return;

    const logout = async () => {
      try {
        await logOutUser();
        setCustomerInfo(null);
        setEntitlementStatus(null);
      } catch (error) {
        // Ignore logout errors
      }
    };
    logout();
  }, [isInitialized, isAuthenticated]);

  // Fetch backend entitlement status
  const refreshEntitlements = useCallback(async () => {
    if (!isAuthenticated) return;

    await Promise.resolve();
    setIsLoading(true);
    try {
      const status = await apiRequest<EntitlementStatus>(
        "/api/entitlements/status",
      );
      setEntitlementStatus(status);
    } catch (error) {
      console.error("[PurchasesContext] Failed to fetch entitlements:", error);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Refresh entitlements when auth changes
  useEffect(() => {
    if (isAuthenticated) {
      const timer = setTimeout(() => void refreshEntitlements(), 0);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, refreshEntitlements]);

  // Also refresh RevenueCat customer info periodically
  useEffect(() => {
    if (!isInitialized || !isAuthenticated) return;

    const refreshCustomerInfo = async () => {
      try {
        const info = await getCustomerInfo();
        setCustomerInfo(info);
      } catch (error) {
        // Non-critical, ignore
      }
    };

    // Refresh on focus or after purchase
    refreshCustomerInfo();
  }, [isInitialized, isAuthenticated]);

  const isSubscribed =
    entitlementStatus?.is_active === true ||
    (customerInfo !== null && hasActiveEntitlement(customerInfo));

  const value: PurchasesContextValue = {
    isInitialized,
    customerInfo,
    entitlementStatus,
    isSubscribed,
    isLoading,
    refreshEntitlements,
  };

  return (
    <PurchasesContext.Provider value={value}>
      {children}
    </PurchasesContext.Provider>
  );
}

/**
 * Hook to access purchases/subscription context. Must be used within PurchasesProvider.
 */
export function usePurchases(): PurchasesContextValue {
  const context = useContext(PurchasesContext);
  if (!context) {
    throw new Error("usePurchases must be used within a PurchasesProvider");
  }
  return context;
}
