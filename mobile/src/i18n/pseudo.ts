/**
 * Pseudo-localisation: a development-only catalogue that makes text expansion
 * visible before a translator ever produces the string.
 *
 * `Save photo` becomes `[Şàvé þhótó ~~~~~~~]`, which does three things at once:
 * the accents prove the string came from the catalogue, the brackets show
 * where it starts and ends, and the padding reproduces the length a German or
 * French translation will have. One pass through the app in this mode surfaces
 * every clipped label and every collision, including the ones in languages
 * nobody on the team reads.
 *
 * Anything left in plain ASCII on screen is a string that escaped the
 * catalogue — a hard-coded literal — which is the second thing this catches.
 *
 * Deliberately *not* a `SupportedLocale`. The pseudo catalogue is a transform
 * applied on top of a real locale, so `activeLocale` stays a tag that
 * `Intl.PluralRules`, `Intl.NumberFormat` and `toLocaleDateString` understand;
 * adding a fake `en-XA` to the union would have widened the type everywhere,
 * put a joke language in the production picker, and broken plural selection on
 * the screens that count things.
 */

import type { Catalog } from "./runtime";

/**
 * One accented look-alike per ASCII letter.
 *
 * Chosen to stay readable: the point is to spot a *layout* problem, which
 * means still being able to tell which label you are looking at. Glyphs that
 * change the apparent width much (ﬁ, œ) are avoided so that the padding stays
 * the only thing driving the length.
 */
const ACCENTED: Record<string, string> = {
  a: "à", b: "ƀ", c: "ç", d: "ð", e: "é", f: "ƒ", g: "ĝ", h: "ĥ", i: "ï",
  j: "ĵ", k: "ķ", l: "ł", m: "ɱ", n: "ñ", o: "ó", p: "þ", q: "ɋ", r: "ř",
  s: "ş", t: "ŧ", u: "ú", v: "ṽ", w: "ŵ", x: "ẋ", y: "ý", z: "ž",
  A: "À", B: "Ɓ", C: "Ç", D: "Ð", E: "É", F: "Ƒ", G: "Ĝ", H: "Ĥ", I: "Ï",
  J: "Ĵ", K: "Ķ", L: "Ł", M: "Ṁ", N: "Ñ", O: "Ó", P: "Þ", Q: "Q", R: "Ř",
  S: "Ş", T: "Ŧ", U: "Ú", V: "Ṽ", W: "Ŵ", X: "Ẋ", Y: "Ý", Z: "Ž",
};

/**
 * How much longer the pseudo string is than the source.
 *
 * 40% is the upper end of what the Latin catalogues actually do to this app's
 * `en` strings (measured: fr +25%, de +23%, es/pt +20%), so a layout that
 * survives this survives all of them.
 */
const EXPANSION_RATIO = 0.4;

/**
 * Short strings get padded harder, because they are the ones that break.
 *
 * `Save` → `Enregistrer` is +175%, `Upgrade` → `Passer à une formule
 * supérieure` is +343%: a flat 40% on a four-letter button label would
 * reproduce none of it. Anything under this length is padded to at least
 * `SHORT_MIN_PAD` extra characters instead.
 */
const SHORT_STRING_LENGTH = 12;
const SHORT_MIN_PAD = 6;

/** `{count}`, `{name}`, … — left untouched so `interpolate` still matches. */
const PLACEHOLDER = /\{\w+\}/g;

function accentuate(text: string): string {
  let out = "";
  for (const char of text) {
    out += ACCENTED[char] ?? char;
  }
  return out;
}

/**
 * Accent the prose and leave the placeholders alone.
 *
 * `interpolate()` in `runtime.ts` matches `\{(\w+)\}` literally, so an
 * accented `{çóúñŧ}` would never be substituted and every counter in the app
 * would render its own template. Splitting on the placeholders keeps them
 * verbatim.
 */
function accentuateAroundPlaceholders(value: string): string {
  let out = "";
  let cursor = 0;
  PLACEHOLDER.lastIndex = 0;

  let match: RegExpExecArray | null;
  while ((match = PLACEHOLDER.exec(value)) !== null) {
    out += accentuate(value.slice(cursor, match.index));
    out += match[0];
    cursor = match.index + match[0].length;
  }

  return out + accentuate(value.slice(cursor));
}

/** One string, accented, padded and bracketed. */
export function pseudoizeValue(value: string): string {
  if (value.length === 0) return value;

  const padding =
    value.length < SHORT_STRING_LENGTH
      ? SHORT_MIN_PAD
      : Math.ceil(value.length * EXPANSION_RATIO);

  return `[${accentuateAroundPlaceholders(value)} ${"~".repeat(padding)}]`;
}

/**
 * A whole catalogue, pseudo-localised.
 *
 * Applied to whichever catalogue is active rather than to `en` only: reading
 * the app in pseudo-Japanese is how you see that a screen tuned for a language
 * that *contracts* still holds when it expands.
 */
export function pseudoize(catalog: Catalog): Catalog {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(catalog)) {
    out[key] = pseudoizeValue(value);
  }
  // Every key of the source is present, which is what `Catalog` asks for; the
  // index signature half of the type is why `Object.entries` is enough here.
  return out as Catalog;
}
