import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Alert, I18nManager } from "react-native";
import { getLocales } from "expo-localization";
import * as SecureStore from "expo-secure-store";
import { CATALOGS } from "./catalogs";
import {
  FALLBACK_LOCALE,
  isRTLLocale,
  isSupportedLocale,
  type SupportedLocale,
} from "./locales";
import {
  getActiveLocale,
  setActiveCatalog,
  t,
  tCount,
  type PluralKey,
  type TranslationKey,
  type TranslationParams,
} from "./runtime";

export { SUPPORTED_LOCALES, LOCALE_ENDONYMS, isRTLLocale } from "./locales";
export type { SupportedLocale } from "./locales";
export { formatDate, formatNumber, getActiveLocale, t, tCount } from "./runtime";
export type { TranslationKey, PluralKey } from "./runtime";

const UI_LOCALE_KEY = "ui_locale";

/**
 * The interface language the device asks for.
 *
 * `getLocales()` returns the user's *ordered* preference list, so someone whose
 * phone is set to Catalan then Spanish gets Spanish rather than the English
 * fallback — which is exactly what the hand-rolled `SettingsManager` /
 * `I18nManager` reader this replaces could not do: it only ever saw the first
 * entry, and only its language part.
 */
export function resolveDeviceLocale(): SupportedLocale {
  try {
    for (const locale of getLocales()) {
      const languageCode = locale.languageCode?.toLowerCase();
      if (languageCode && isSupportedLocale(languageCode)) {
        return languageCode;
      }
    }
  } catch {
    // Never let locale detection be the reason the app fails to start.
  }
  return FALLBACK_LOCALE;
}

/**
 * The in-app override, stored on the device and nowhere else.
 *
 * The backend has no business knowing the language of the chrome: it renders
 * none of it. `reading_language`, which it *does* need, is a different setting
 * that keeps travelling through `PATCH /api/auth/me`.
 *
 * SecureStore is the app's only key/value store (AsyncStorage was removed in
 * V1), so it holds this the same way it holds the usage-warning dismissal.
 */
const UILocalePreference = {
  async read(): Promise<SupportedLocale | null> {
    try {
      const stored = await SecureStore.getItemAsync(UI_LOCALE_KEY);
      return stored && isSupportedLocale(stored) ? stored : null;
    } catch {
      return null;
    }
  },

  async write(locale: SupportedLocale | null): Promise<void> {
    try {
      if (locale === null) {
        await SecureStore.deleteItemAsync(UI_LOCALE_KEY);
      } else {
        await SecureStore.setItemAsync(UI_LOCALE_KEY, locale);
      }
    } catch {
      // Best effort: falling back to the device locale next launch is a smaller
      // failure than crashing the settings screen on a keychain refusal.
    }
  },
} as const;

interface I18nContextValue {
  /** The locale the interface is rendered in. */
  locale: SupportedLocale;
  /** The user's explicit choice, or `null` when following the device. */
  override: SupportedLocale | null;
  /** `null` hands the choice back to the device locale. */
  setLocale: (locale: SupportedLocale | null) => void;
  isRTL: boolean;
  t: (key: TranslationKey, params?: TranslationParams) => string;
  tCount: (key: PluralKey, count: number, params?: TranslationParams) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

/**
 * Applies the locale to the layout direction.
 *
 * `I18nManager` only takes effect after the JS bundle is reloaded, which is why
 * the caller has to ask the user to restart rather than pretending the switch
 * was instant. Returns whether a restart is now owed.
 */
function applyLayoutDirection(locale: SupportedLocale): boolean {
  const shouldBeRTL = isRTLLocale(locale);
  if (I18nManager.isRTL === shouldBeRTL) return false;

  I18nManager.allowRTL(shouldBeRTL);
  I18nManager.forceRTL(shouldBeRTL);
  return true;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [override, setOverride] = useState<SupportedLocale | null>(null);
  const [deviceLocale] = useState<SupportedLocale>(resolveDeviceLocale);
  // The stored override is read asynchronously; rendering the tree before it
  // lands would show one language and then swap it under the user.
  const [isPreferenceLoaded, setIsPreferenceLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    void UILocalePreference.read().then((stored) => {
      if (!active) return;
      setOverride(stored);
      setIsPreferenceLoaded(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const locale = override ?? deviceLocale;

  // Keeps the non-React half of the runtime in step with the React half, before
  // any child renders: the copy modules under `src/lib/` read it directly.
  if (getActiveLocale() !== locale) {
    setActiveCatalog(locale, CATALOGS[locale]);
  }

  const setLocale = useCallback((next: SupportedLocale | null) => {
    setOverride(next);
    void UILocalePreference.write(next);

    const effective = next ?? resolveDeviceLocale();
    setActiveCatalog(effective, CATALOGS[effective]);

    if (applyLayoutDirection(effective)) {
      Alert.alert(t("settings.uiLanguage.restartTitle"), t("settings.uiLanguage.restartBody"), [
        { text: t("common.ok") },
      ]);
    }
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      override,
      setLocale,
      isRTL: isRTLLocale(locale),
      t,
      tCount,
    }),
    [locale, override, setLocale],
  );

  if (!isPreferenceLoaded) return null;

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }
  return context;
}
