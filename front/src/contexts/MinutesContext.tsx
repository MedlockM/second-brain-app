import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { BillingService } from "../services/billingService";

interface MinutesContextType {
    availableMinutes: number;
    loadingMinutes: boolean;
    refreshMinutes: () => Promise<void>;
}

const MinutesContext = createContext<MinutesContextType | undefined>(undefined);

export function useMinutes() {
    const context = useContext(MinutesContext);
    if (!context) {
        throw new Error("useMinutes must be used within MinutesProvider");
    }
    return context;
}

interface MinutesProviderProps {
    token: string;
    children: ReactNode;
}

export function MinutesProvider({ token, children }: MinutesProviderProps) {
    const [availableMinutes, setAvailableMinutes] = useState<number>(0);
    const [loadingMinutes, setLoadingMinutes] = useState(true);

    const refreshMinutes = async () => {
        try {
            const minutes = await BillingService.getAvailableMinutes(token);
            setAvailableMinutes(minutes);
        } catch (error) {
            console.error("Failed to load minutes:", error);
        } finally {
            setLoadingMinutes(false);
        }
    };

    // Load minutes initially and set up periodic refresh
    useEffect(() => {
        if (!token) return;

        // Initial load
        refreshMinutes();

        // Refresh every 30 seconds
        const interval = setInterval(refreshMinutes, 30000);

        return () => clearInterval(interval);
    }, [token]);

    return (
        <MinutesContext.Provider
            value={{ availableMinutes, loadingMinutes, refreshMinutes }}
        >
            {children}
        </MinutesContext.Provider>
    );
}
