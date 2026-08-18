import { apiRequest } from "./apiClient";
import { AuthUser } from "../types/auth";

/**
 * V1 supported reading languages (ISO 639-1 codes).
 * Aligned with task-189 benchmark owner decision.
 */
export const V1_READING_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fr", label: "Francais" },
  { code: "es", label: "Espanol" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Portugues" },
  { code: "nl", label: "Nederlands" },
  { code: "ja", label: "Japanese" },
  { code: "zh", label: "Chinese" },
  { code: "ar", label: "Arabic" },
  { code: "hi", label: "Hindi" },
] as const;

export type ReadingLanguageCode = (typeof V1_READING_LANGUAGES)[number]["code"];

/**
 * Service for managing user preferences via the API.
 */
export class UserPreferencesService {
  /**
   * Update the user's reading language preference.
   * Calls PATCH /api/auth/me with the new reading_language value.
   */
  static async updateReadingLanguage(
    token: string,
    language: ReadingLanguageCode,
  ): Promise<AuthUser> {
    return apiRequest<AuthUser>("/api/auth/me", {
      method: "PATCH",
      token,
      body: { reading_language: language },
    });
  }
}
