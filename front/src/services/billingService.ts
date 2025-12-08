const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export interface MinutesInfo {
    total_free: number;
    by_source: {
        rollover: number;
        subscription: number;
        packs: number;
    };
}

export class BillingService {
    private static getHeaders(token: string): HeadersInit {
        return {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        };
    }

    /**
     * Get available minutes for the current user
     */
    static async getAvailableMinutes(token: string): Promise<number> {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/billing/me`, {
                method: "GET",
                credentials: "include",
                headers: this.getHeaders(token),
            });

            if (!response.ok) {
                console.error("Failed to fetch minutes:", response.status);
                return 0;
            }

            const data = await response.json();
            return data.minutes?.total_free || 0;
        } catch (error) {
            console.error("Error fetching available minutes:", error);
            return 0;
        }
    }

    /**
     * Get detailed minutes breakdown
     */
    static async getMinutesBreakdown(token: string): Promise<MinutesInfo | null> {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/billing/me`, {
                method: "GET",
                credentials: "include",
                headers: this.getHeaders(token),
            });

            if (!response.ok) {
                console.error("Failed to fetch minutes breakdown:", response.status);
                return null;
            }

            const data = await response.json();
            return data.minutes || null;
        } catch (error) {
            console.error("Error fetching minutes breakdown:", error);
            return null;
        }
    }
}
