import { createHttpError, parseErrorResponse } from "../lib/httpError";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export interface SubscriptionInfo {
    subscription: {
        status: string;
        tier: string;
        minutes_per_period: number;
        cancel_at_period_end: boolean;
        current_period_start: string | null;
        current_period_end: string | null;
    } | null;
    minutes: {
        total_free: number;
        by_source: {
            rollover: number;
            subscription: number;
            packs: number;
        };
    };
    buckets_count: number;
}

export interface CancelSubscriptionResponse {
    status: string;
    message: string;
    subscription: {
        id: string;
        tier: string;
        cancel_at_period_end: boolean;
        current_period_end: string | null;
    };
}

export interface PortalSessionResponse {
    url: string;
}

export class SettingsService {
    private static getHeaders(token: string): HeadersInit {
        return {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        };
    }

    static async updateEmail(
        userId: string,
        newEmail: string,
        token: string,
    ): Promise<void> {
        const response = await fetch(`${API_BASE_URL}/api/v1/users/${userId}`, {
            method: "PUT",
            credentials: "include",
            headers: this.getHeaders(token),
            body: JSON.stringify({ email: newEmail }),
        });

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to update email",
            );
            throw createHttpError(message, response.status, code);
        }
    }

    static async getSubscriptionInfo(
        token: string,
    ): Promise<SubscriptionInfo> {
        const response = await fetch(`${API_BASE_URL}/api/v1/billing/me`, {
            method: "GET",
            credentials: "include",
            headers: this.getHeaders(token),
        });

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to get subscription info",
            );
            throw createHttpError(message, response.status, code);
        }

        return response.json();
    }

    static async cancelSubscription(
        token: string,
    ): Promise<CancelSubscriptionResponse> {
        const response = await fetch(
            `${API_BASE_URL}/api/v1/billing/subscriptions/cancel`,
            {
                method: "POST",
                credentials: "include",
                headers: this.getHeaders(token),
            },
        );

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to cancel subscription",
            );
            throw createHttpError(message, response.status, code);
        }

        return response.json();
    }

    static async createPortalSession(
        token: string,
    ): Promise<PortalSessionResponse> {
        const response = await fetch(`${API_BASE_URL}/api/v1/billing/portal`, {
            method: "POST",
            credentials: "include",
            headers: this.getHeaders(token),
        });

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to create portal session",
            );
            throw createHttpError(message, response.status, code);
        }

        return response.json();
    }

    static async createSubscriptionCheckout(
        token: string,
        tier: string,
    ): Promise<{ url: string }> {
        const response = await fetch(
            `${API_BASE_URL}/api/v1/billing/subscriptions/checkout`,
            {
                method: "POST",
                credentials: "include",
                headers: this.getHeaders(token),
                body: JSON.stringify({ tier }),
            },
        );

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to create subscription checkout",
            );
            throw createHttpError(message, response.status, code);
        }

        return response.json();
    }

    static async createPackCheckout(
        token: string,
        minutes: number,
    ): Promise<{ url: string }> {
        const response = await fetch(
            `${API_BASE_URL}/api/v1/billing/packs/checkout`,
            {
                method: "POST",
                credentials: "include",
                headers: this.getHeaders(token),
                body: JSON.stringify({ minutes }),
            },
        );

        if (!response.ok) {
            const { message, code } = await parseErrorResponse(
                response,
                "Failed to create pack checkout",
            );
            throw createHttpError(message, response.status, code);
        }

        return response.json();
    }
}
