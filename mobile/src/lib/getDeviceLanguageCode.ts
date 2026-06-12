import { Platform, NativeModules } from "react-native";

/**
 * Get the device's primary language code (ISO 639-1, lowercase).
 * Uses platform-native APIs available through React Native without additional dependencies.
 *
 * Falls back to "en" if detection fails.
 */
export function getDeviceLanguageCode(): string {
  try {
    let locale: string | undefined;

    if (Platform.OS === "ios") {
      // iOS: NativeModules.SettingsManager provides the device locale
      locale =
        NativeModules.SettingsManager?.settings?.AppleLocale ??
        NativeModules.SettingsManager?.settings?.AppleLanguages?.[0];
    } else {
      // Android: use I18nManager or Intl
      locale = NativeModules.I18nManager?.localeIdentifier;
    }

    // Fallback to Intl API (available in Hermes)
    if (!locale) {
      const intlLocales = Intl.DateTimeFormat().resolvedOptions().locale;
      locale = intlLocales;
    }

    if (!locale) return "en";

    // Extract language code: "fr-FR" -> "fr", "en_US" -> "en", "zh-Hans" -> "zh"
    const langCode = locale.split(/[-_]/)[0].toLowerCase();
    return langCode || "en";
  } catch {
    return "en";
  }
}
