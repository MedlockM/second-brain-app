import {
  RegisterRequest,
  LoginRequest,
  TokenVerificationResponse,
  NativeAuthResponse,
  AuthUser,
} from "../types/auth";
import { Config } from "../constants/config";
import { createHttpError, parseErrorResponse } from "../lib/httpError";
import { apiRequest } from "./apiClient";
import { TokenStorage } from "./tokenStorage";
import { SessionManager } from "./sessionManager";

/**
 * Authentication endpoints for mobile.
 *
 * These are the calls that open or close a session. Everything about keeping one
 * alive — rotating the tokens, deciding what a failure means, purging the
 * keychain — belongs to SessionManager, which is the only caller of the refresh
 * endpoint. There is no refresh entry point here for a screen to reach for.
 *
 * Key differences from the web frontend:
 * - expo-secure-store instead of localStorage/sessionStorage
 * - the refresh token is stored explicitly: the API returns it in the JSON body
 *   of register/login/refresh, since a mobile client cannot read an httpOnly
 *   cookie
 * - all storage operations are async
 */
export class AuthService {
  private static async postUnauthenticated<T>(
    path: string,
    body: unknown,
    fallbackMessage: string,
  ): Promise<T> {
    const response = await fetch(`${Config.API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const { message, code } = await parseErrorResponse(
        response,
        fallbackMessage,
      );
      throw createHttpError(message, response.status, code);
    }

    return (await response.json()) as T;
  }

  static async register(
    data: RegisterRequest,
  ): Promise<TokenVerificationResponse> {
    // Registration opens the session itself: same body as login, refresh token
    // included, so there is nothing left to establish with a second call.
    const result = await this.postUnauthenticated<TokenVerificationResponse>(
      "/api/auth/register",
      data,
      "Registration failed",
    );
    await SessionManager.persistSession(result);
    return result;
  }

  static async login(data: LoginRequest): Promise<TokenVerificationResponse> {
    const result = await this.postUnauthenticated<TokenVerificationResponse>(
      "/api/auth/login",
      data,
      "Login failed",
    );
    await SessionManager.persistSession(result);
    return result;
  }

  /**
   * Authenticate with Google using a native ID token.
   * The backend verifies the token and returns access + refresh tokens.
   */
  static async loginWithGoogleNative(
    idToken: string,
  ): Promise<NativeAuthResponse> {
    const result = await this.postUnauthenticated<NativeAuthResponse>(
      "/api/auth/google/native",
      { id_token: idToken },
      "Google sign-in failed",
    );
    await SessionManager.persistSession(result);
    return result;
  }

  /**
   * Authenticate with Apple using a native identity token.
   * The backend verifies the token and returns access + refresh tokens.
   */
  static async loginWithAppleNative(
    identityToken: string,
    user?: {
      email?: string;
      fullName?: { givenName?: string; familyName?: string };
    },
  ): Promise<NativeAuthResponse> {
    const result = await this.postUnauthenticated<NativeAuthResponse>(
      "/api/auth/apple/native",
      {
        identity_token: identityToken,
        user: user?.email ? { email: user.email } : undefined,
      },
      "Apple sign-in failed",
    );
    await SessionManager.persistSession(result);
    return result;
  }

  /** The signed-in profile. GET /api/auth/me */
  static async getCurrentUser(): Promise<AuthUser> {
    return apiRequest<AuthUser>("/api/auth/me");
  }

  /**
   * Close the session on the backend, then locally.
   *
   * The tokens are read here rather than passed in: nothing outside this layer
   * holds them, and the local session is dropped whatever the call answers — a
   * logout the network swallowed must still sign the user out of the device.
   *
   * Log out this device only: the access token says who is signing out, the
   * refresh token says from which device, and the server revokes just that token
   * lineage — so signing out here leaves the account's other devices signed in.
   * With no refresh token stored there is no lineage to close server side, so
   * the local wipe is all that is left to do.
   */
  static async logout(): Promise<void> {
    const accessToken = await TokenStorage.getAccessToken();
    const refreshToken = await TokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await fetch(`${Config.API_BASE_URL}/api/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Ignore network errors during logout - we clear tokens regardless
      }
    }
    await SessionManager.clearSession();
  }
}
