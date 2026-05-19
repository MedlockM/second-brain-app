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

export interface EntitlementStatus {
  user_id: string;
  subscription_tier: "S" | "M" | "L" | null;
  subscription_status: string | null;
  is_active: boolean;
  period_end: string | null;
  auto_renew_status: boolean | null;
  minutes_remaining: number;
  breakdown: {
    subscription: number;
    pack: number;
    rollover: number;
    migration: number;
  };
  offerings_config?: Array<{
    tier: string;
    name: string;
    display_name: string;
    price_eur: number;
    minutes_per_month: number;
    description: string;
    features: string[];
  }>;
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
  const { user, token, isAuthenticated } = useAuth();
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
    if (!token) return;

    setIsLoading(true);
    try {
      const status = await apiRequest<EntitlementStatus>(
        "/api/v1/entitlements/status",
        { token },
      );
      setEntitlementStatus(status);
    } catch (error) {
      console.error("[PurchasesContext] Failed to fetch entitlements:", error);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // Refresh entitlements when auth changes
  useEffect(() => {
    if (isAuthenticated && token) {
      refreshEntitlements();
    }
  }, [isAuthenticated, token, refreshEntitlements]);

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
