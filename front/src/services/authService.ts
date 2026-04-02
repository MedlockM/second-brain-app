import {
  RegisterRequest,
  LoginRequest,
  TokenVerificationResponse,
  AuthUser,
} from "../types/auth";
import { createHttpError, parseErrorResponse } from "../lib/httpError";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";
export const AUTH_ERROR_STORAGE_KEY = "auth_error_code";

export class AuthService {
  private static getAuthHeaders(token?: string): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  static async register(data: RegisterRequest): Promise<AuthUser> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Registration failed",
      );
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  }

  static async login(data: LoginRequest): Promise<TokenVerificationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(response, "Login failed");
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  }

  static async getCurrentUser(token: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      method: "GET",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to fetch user info",
      );
      throw createHttpError(message, response.status, code);
    }

    return response.json();
  }

  static async logout(token: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(response, "Logout failed");
      throw createHttpError(message, response.status, code);
    }
  }

  static async resendVerificationEmail(token: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/resend-verification`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to resend verification email",
      );
      throw createHttpError(message, response.status, code);
    }
  }

  static saveToken(token: string, expiresIn: number): void {
    localStorage.setItem("access_token", token);
    const expiryTime = Date.now() + expiresIn * 1000;
    localStorage.setItem("token_expiry", expiryTime.toString());
  }

  static getToken(): string | null {
    const token = localStorage.getItem("access_token");
    const expiry = localStorage.getItem("token_expiry");

    if (!token || !expiry) {
      return null;
    }

    if (Date.now() > parseInt(expiry)) {
      this.clearToken();
      return null;
    }

    return token;
  }

  static clearToken(): void {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_expiry");
  }

  static async refresh(): Promise<TokenVerificationResponse> {
    const API_BASE_URL = import.meta.env.VITE_API_URL || "";
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include", // Important: envoie les cookies (refresh token)
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      this.clearToken();
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to refresh token",
      );
      if (response.status === 401 || code === "SESSION_EXPIRED") {
        sessionStorage.setItem(AUTH_ERROR_STORAGE_KEY, code || "SESSION_EXPIRED");
      }
      throw createHttpError(message, response.status, code);
    }

    const data = await response.json();
    this.saveToken(data.access_token, data.expires_in);
    return data;
  }

  static async getValidToken(): Promise<string | null> {
    const storedToken = localStorage.getItem("access_token");
    const storedExpiry = localStorage.getItem("token_expiry");

    if (!storedToken || !storedExpiry) {
      if (storedToken || storedExpiry) {
        this.clearToken();
      }
      return null;
    }

    const expiryTime = parseInt(storedExpiry, 10);
    if (Number.isNaN(expiryTime) || Date.now() > expiryTime) {
      this.clearToken();
      try {
        const response = await this.refresh();
        return response.access_token;
      } catch (error) {
        console.error("Failed to refresh token:", error);
        return null;
      }
    }

    return storedToken;
  }
}
