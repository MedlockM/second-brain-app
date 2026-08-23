import { apiRequest } from "./apiClient";
import { AuthUser } from "../types/auth";
import { LOCALE_ENDONYMS } from "../i18n/locales";

/**
 * The reading languages V1 offers, each named in its own script.
 *
 * Labels are taken from `LOCALE_ENDONYMS` rather than retyped: a language
 * picker names languages the way their speakers write them, and the two lists
 * cover the same eleven languages, so a second spelling of "Português" here
 * could only ever drift from the one in the app-language picker. The list
 * itself stays separate — the reading language is an account preference the
 * backend stores, the interface language never leaves the device.
 *
 * This is also what fixed the mixture the list used to carry: ASCII-stripped
 * endonyms ("Francais", "Espanol") next to English exonyms ("Japanese",
 * "Chinese", "Arabic", "Hindi").
 */
export const V1_READING_LANGUAGES = [
  { code: "en", label: LOCALE_ENDONYMS.en },
  { code: "fr", label: LOCALE_ENDONYMS.fr },
  { code: "es", label: LOCALE_ENDONYMS.es },
  { code: "de", label: LOCALE_ENDONYMS.de },
  { code: "it", label: LOCALE_ENDONYMS.it },
  { code: "pt", label: LOCALE_ENDONYMS.pt },
  { code: "nl", label: LOCALE_ENDONYMS.nl },
  { code: "ja", label: LOCALE_ENDONYMS.ja },
  { code: "zh", label: LOCALE_ENDONYMS.zh },
  { code: "ar", label: LOCALE_ENDONYMS.ar },
  { code: "hi", label: LOCALE_ENDONYMS.hi },
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
    language: ReadingLanguageCode,
  ): Promise<AuthUser> {
    return apiRequest<AuthUser>("/api/auth/me", {
      method: "PATCH",
      body: { reading_language: language },
    });
  }
}
