import { en } from "./en";
import { FALLBACK_LOCALE, type SupportedLocale } from "./locales";

/**
 * Every key the app can translate, taken from the `en` catalogue.
 *
 * `en` is the reference: a key it does not declare cannot be passed to `t`,
 * and a key it declares has to appear in all ten other catalogues, which the
 * `Catalog` type below enforces at compile time. Nothing here can therefore
 * put a raw `"screen.title"` on screen the way a runtime lookup would.
 */
export type TranslationKey = keyof typeof en;

/**
 * The bases of the plural families: `inbox.itemCount` for the pair
 * `inbox.itemCount.one` / `inbox.itemCount.other`. Every language has an
 * `other` category, so it is the one the base is derived from.
 */
export type PluralKey = {
  [K in TranslationKey]: K extends `${infer Base}.other` ? Base : never;
}[TranslationKey];

/**
 * What a non-reference catalogue has to satisfy: every key of `en`, plus the
 * freedom to add the plural categories its own language needs. Arabic carries
 * six (`zero`, `one`, `two`, `few`, `many`, `other`) where English carries two,
 * so the extra keys are allowed through an index signature — while the
 * `Record<TranslationKey, string>` half keeps a *missing* key a `tsc` error.
 */
export type Catalog = Record<TranslationKey, string> & Record<string, string>;

export type TranslationParams = Record<string, string | number>;

/**
 * The active locale, held outside React on purpose.
 *
 * The copy modules under `src/lib/` (`planCopy`, `quotaError`,
 * `artifactRefusal`, `getFriendlyErrorMessage`, `relativeTime`) are plain
 * functions called from render bodies, event handlers and `Alert` callbacks
 * alike; threading a `t` through every one of them would put a React concern
 * in code that has no other reason to know about React. `I18nProvider` keeps
 * this in sync and re-renders the tree, so the two views never disagree.
 */
let activeLocale: SupportedLocale = FALLBACK_LOCALE;
let activeCatalog: Catalog = en;

export function getActiveLocale(): SupportedLocale {
  return activeLocale;
}

/**
 * The catalogue currently installed, by identity.
 *
 * `I18nProvider` compares it against the one it just derived to know whether
 * the runtime is in step: the locale alone is not enough to answer that, since
 * pseudo-localisation swaps the catalogue *without* changing the locale.
 */
export function getActiveCatalog(): Catalog {
  return activeCatalog;
}

export function setActiveCatalog(
  locale: SupportedLocale,
  catalog: Catalog,
): void {
  activeLocale = locale;
  activeCatalog = catalog;
}

/**
 * Substitute `{name}` placeholders. An unknown placeholder is left as written
 * rather than replaced by `undefined`: a visible `{count}` is a bug report,
 * where "undefined items" is a mystery.
 */
function interpolate(template: string, params?: TranslationParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

function lookup(key: string): string {
  return activeCatalog[key] ?? en[key as TranslationKey] ?? key;
}

/** Translate a key in the active locale. */
export function t(key: TranslationKey, params?: TranslationParams): string {
  return interpolate(lookup(key), params);
}

/**
 * Translate a count-dependent key through the plural rules of the active
 * locale — never by gluing a number onto a fixed suffix.
 *
 * `Intl.PluralRules` picks the category (Hermes ships it, and `Intl` is
 * already used elsewhere in the app); the catalogue supplies one string per
 * category its language actually uses. `{count}` is available to the string,
 * formatted for the locale, and languages that need the bare digit elsewhere
 * get it through `params`.
 */
export function tCount(
  key: PluralKey,
  count: number,
  params?: TranslationParams,
): string {
  let category: Intl.LDMLPluralRule = count === 1 ? "one" : "other";
  try {
    category = new Intl.PluralRules(activeLocale).select(count);
  } catch {
    // An engine without the locale data still gets a grammatical English-style
    // choice rather than a crash on a screen that only wanted to show a number.
  }

  const template =
    activeCatalog[`${key}.${category}`] ??
    activeCatalog[`${key}.other`] ??
    en[`${key}.other` as TranslationKey] ??
    key;

  return interpolate(template, {
    count: formatNumber(count),
    ...params,
  });
}

/** A number written the way the active locale writes it. */
export function formatNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  try {
    return new Intl.NumberFormat(activeLocale, options).format(value);
  } catch {
    return String(value);
  }
}

/** A date written the way the active locale writes it. */
export function formatDate(
  value: Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  try {
    return value.toLocaleDateString(activeLocale, options);
  } catch {
    return value.toDateString();
  }
}
