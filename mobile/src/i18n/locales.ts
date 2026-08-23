/**
 * The interface languages the app ships.
 *
 * Deliberately the same eleven as `V1_READING_LANGUAGES`, and deliberately a
 * *separate axis* from it: `reading_language` picks the language of the
 * generated content (summaries, translated transcripts, digests) and lives
 * server-side, while this one picks the language of the chrome around it and
 * never leaves the device. Someone reading English summaries in a French
 * interface is a supported combination, not an inconsistency to reconcile.
 *
 * `en` is the fallback: it is the reference catalogue, the development
 * language of the binary, and what the OS falls back to when a device asks for
 * a language nothing here declares.
 */
export const SUPPORTED_LOCALES = [
  "en",
  "fr",
  "es",
  "de",
  "it",
  "pt",
  "nl",
  "ja",
  "zh",
  "ar",
  "hi",
] as const;

export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const FALLBACK_LOCALE: SupportedLocale = "en";

/**
 * Each language named in its own script, which is the only naming a language
 * picker can use: a French speaker looking for their language scans for
 * "Français", not for "French".
 */
export const LOCALE_ENDONYMS: Record<SupportedLocale, string> = {
  en: "English",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
  it: "Italiano",
  pt: "Português",
  nl: "Nederlands",
  ja: "日本語",
  zh: "中文",
  ar: "العربية",
  hi: "हिन्दी",
};

/** The locales written right-to-left, which `I18nManager` has to be told about. */
export const RTL_LOCALES: readonly SupportedLocale[] = ["ar"];

export function isRTLLocale(locale: SupportedLocale): boolean {
  return RTL_LOCALES.includes(locale);
}

export function isSupportedLocale(value: string): value is SupportedLocale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value);
}
