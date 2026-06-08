import { apiRequest } from "./apiClient";
import { Config } from "../constants/config";

/**
 * Response shape from GET /api/v1/feedback/token.
 */
interface FeedbackTokenResponse {
  url: string;
  sso_token: string;
  board_token: string;
}

/**
 * Service for interacting with the Canny feedback board.
 *
 * The primary flow is:
 * 1. Call getFeedbackUrl() with the user's auth token
 * 2. Backend generates a Canny SSO JWT and returns the full WebView URL
 * 3. Open the URL in the system browser (expo-web-browser)
 *
 * Fallback: if the backend is unavailable, open the board URL directly
 * (user will need to authenticate manually on Canny).
 */
export class FeedbackService {
  /**
   * Get the feedback board URL with SSO authentication.
   * The backend signs a Canny JWT so the user is auto-identified.
   *
   * @param token - The user's access token for API authentication
   * @returns The full Canny WebView URL with SSO token embedded
   */
  static async getFeedbackUrl(token: string): Promise<string> {
    const response = await apiRequest<FeedbackTokenResponse>(
      "/api/v1/feedback/token",
      { token },
    );
    return response.url;
  }

  /**
   * Get the fallback feedback URL (no SSO, user may need to log in on Canny).
   * Used when the SSO endpoint is unavailable or errors out.
   *
   * Returns null if EXPO_PUBLIC_FEEDBACK_URL is not configured — callers must
   * handle this and surface a user-visible error instead of opening "".
   */
  static getFallbackUrl(): string | null {
    return Config.FEEDBACK_URL || null;
  }
}
