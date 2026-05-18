import {
  RegisterRequest,
  LoginRequest,
  TokenVerificationResponse,
  AuthUser,
} from "../types/auth";
import { Config } from "../constants/config";
import { createHttpError, parseErrorResponse } from "../lib/httpError";
import { TokenStorage } from "./tokenStorage";

/**
 * Authentication service for mobile.
 * Ported from front/src/services/authService.ts.
 *
 * Key differences from web:
 * - Uses expo-secure-store instead of localStorage/sessionStorage
 * - Stores refresh token explicitly (mobile cannot rely on httpOnly cookies)
 * - All storage operations are async
 */
export class AuthService {
  private static getAuthHeaders(token?: string): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  static async register(data: RegisterRequest): Promise<TokenVerificationResponse> {
    const response = await fetch(
      `${Config.API_BASE_URL}/api/v1/auth/register`,
      {
        method: "POST",
        headers: this.getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Registration failed",
      );
      throw createHttpError(message, response.status, code);
    }

    const result: TokenVerificationResponse = await response.json();
    await this.persistTokens(result);
    return result;
  }

  static async login(data: LoginRequest): Promise<TokenVerificationResponse> {
    const response = await fetch(
      `${Config.API_BASE_URL}/api/v1/auth/login`,
      {
        method: "POST",
        headers: this.getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        "Login failed",
      );
      throw createHttpError(message, response.status, code);
    }

    const result: TokenVerificationResponse = await response.json();
    await this.persistTokens(result);
    return result;
  }

  static async getCurrentUser(token: string): Promise<AuthUser> {
    const response = await fetch(`${Config.API_BASE_URL}/api/v1/auth/me`, {
      method: "GET",
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
    try {
      await fetch(`${Config.API_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: this.getAuthHeaders(token),
      });
    } catch {
      // Ignore network errors during logout - we clear tokens regardless
    }
    await TokenStorage.clearAll();
  }

  /**
   * Refresh the access token using the stored refresh token.
   * On mobile we send the refresh token in the request body
   * (no httpOnly cookie available).
   */
  static async refresh(): Promise<TokenVerificationResponse> {
    const refreshToken = await TokenStorage.getRefreshToken();

    if (!refreshToken) {
      await TokenStorage.clearAll();
      throw createHttpError(
        "No refresh token available",
        401,
        "SESSION_EXPIRED",
      );
    }

    const response = await fetch(
      `${Config.API_BASE_URL}/api/v1/auth/refresh`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
    );

    if (!response.ok) {
      await TokenStorage.clearAll();
      const { message, code } = await parseErrorResponse(
        response,
        "Failed to refresh token",
      );
      throw createHttpError(message, response.status, code);
    }

    const result: TokenVerificationResponse = await response.json();
    await this.persistTokens(result);
    return result;
  }

  /**
   * Get a valid access token, refreshing if expired.
   * Core strategy from the web frontend's getValidToken().
   */
  static async getValidToken(): Promise<string | null> {
    const storedToken = await TokenStorage.getAccessToken();

    if (!storedToken) {
      return null;
    }

    const isExpired = await TokenStorage.isTokenExpired();

    if (!isExpired) {
      return storedToken;
    }

    // Token expired - attempt refresh
    try {
      const response = await this.refresh();
      return response.access_token;
    } catch (error) {
      console.warn("Token refresh failed:", error);
      return null;
    }
  }

  /**
   * Persist tokens after login/register/refresh.
   */
  private static async persistTokens(
    response: TokenVerificationResponse & { refresh_token?: string },
  ): Promise<void> {
    await TokenStorage.saveAccessToken(
      response.access_token,
      response.expires_in,
    );
    // If the backend returns a refresh_token in the body, store it
    if (response.refresh_token) {
      await TokenStorage.saveRefreshToken(response.refresh_token);
    }
  }
}
