import { en } from "./en";
import { fr } from "./fr";
import { es } from "./es";
import { de } from "./de";
import { it } from "./it";
import { pt } from "./pt";
import { nl } from "./nl";
import { ja } from "./ja";
import { zh } from "./zh";
import { ar } from "./ar";
import { hi } from "./hi";
import type { Catalog } from "./runtime";
import type { SupportedLocale } from "./locales";

/**
 * Every catalogue, bundled.
 *
 * Eleven catalogues of a few hundred short strings each cost a few tens of
 * kilobytes in the bundle, which buys an instant switch in the settings and no
 * network dependency for the language of the interface.
 */
export const CATALOGS: Record<SupportedLocale, Catalog> = {
  en,
  fr,
  es,
  de,
  it,
  pt,
  nl,
  ja,
  zh,
  ar,
  hi,
};
