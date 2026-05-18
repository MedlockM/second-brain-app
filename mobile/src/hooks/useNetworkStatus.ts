import { useState, useEffect, useCallback } from "react";
import NetInfo, {
  NetInfoState,
  NetInfoSubscription,
} from "@react-native-community/netinfo";

export interface NetworkStatus {
  /** Whether the device currently has a network connection */
  isConnected: boolean;
  /** Whether the connection is an "expensive" connection (e.g. cellular) */
  isExpensive: boolean;
  /** Connection type (wifi, cellular, none, unknown) */
  connectionType: string;
  /** Whether a connectivity check has completed at least once */
  isReady: boolean;
}

/**
 * Hook that monitors network connectivity status.
 *
 * Uses @react-native-community/netinfo for reliable connectivity detection
 * on both iOS and Android. Falls back to a simple online/offline model
 * if NetInfo is not available (e.g., in Expo Go without native module).
 *
 * Returns current network status including connection type and
 * whether the connection is metered/expensive.
 */
export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isConnected: true,
    isExpensive: false,
    connectionType: "unknown",
    isReady: false,
  });

  useEffect(() => {
    let subscription: NetInfoSubscription | null = null;

    const handleStateChange = (state: NetInfoState) => {
      setStatus({
        isConnected: state.isConnected ?? true,
        isExpensive:
          state.type === "cellular" ||
          (state.details as { isConnectionExpensive?: boolean })
            ?.isConnectionExpensive === true,
        connectionType: state.type ?? "unknown",
        isReady: true,
      });
    };

    try {
      // Fetch initial state
      NetInfo.fetch().then(handleStateChange).catch(() => {
        // NetInfo not available - assume online
        setStatus((prev) => ({ ...prev, isReady: true }));
      });

      // Subscribe to changes
      subscription = NetInfo.addEventListener(handleStateChange);
    } catch {
      // Module not available (e.g. Expo Go without native modules)
      setStatus({
        isConnected: true,
        isExpensive: false,
        connectionType: "unknown",
        isReady: true,
      });
    }

    return () => {
      subscription?.();
    };
  }, []);

  return status;
}

/**
 * Simplified hook that just returns whether the device is online.
 */
export function useIsOnline(): boolean {
  const { isConnected } = useNetworkStatus();
  return isConnected;
}
