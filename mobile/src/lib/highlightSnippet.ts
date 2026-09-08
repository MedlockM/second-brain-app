/**
 * Parsing of the Algolia highlight snippets returned by
 * `GET /api/search/transcripts`.
 *
 * Algolia wraps every match in the tags configured server-side
 * (`highlightPreTag` / `highlightPostTag` = `<mark>` / `</mark>`, see
 * `media_summarizer/core/services/search_indexing.py`) and HTML-escapes the
 * rest of the value. React Native has no HTML renderer, so the raw string
 * cannot be displayed as-is: it must be split into plain and highlighted
 * segments, and its entities decoded.
 *
 * The snippet then has to *fit*: it is shown in a vignette bounded to a few
 * lines, and Algolia puts no bound on where the match falls inside it — the
 * backend even falls back to the whole highlighted transcript chunk when the
 * engine returns no snippet. `focusHighlightSegments` is the second half of this
 * module for that reason: parsing says what is a match, windowing makes sure the
 * match is among the characters the reader is actually shown.
 */

export interface HighlightSegment {
  text: string;
  highlighted: boolean;
}

const MARK_SPLIT_RE = /<\/?mark>/i;
const MARK_TOKEN_RE = /(<mark>|<\/mark>)/gi;

/**
 * What stands where text was cut away. A typographic mark, identical in all
 * eleven catalogues, so it is not a translatable string.
 */
const ELLIPSIS = "…";

/** Whitespace that begins a word — where a cut can be moved forward to. */
const WORD_START_RE = /\s\S/;
/** A trailing partial word — where a cut can be moved back to. */
const TRAILING_WORD_RE = /\s+\S*$/;

const HTML_ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};

/**
 * Decode the HTML entities Algolia introduces when escaping a snippet.
 */
function decodeHtmlEntities(value: string): string {
  return value.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (match, entity: string) => {
    const lower = entity.toLowerCase();

    if (lower.startsWith("#x")) {
      const code = Number.parseInt(entity.slice(2), 16);
      return Number.isNaN(code) ? match : String.fromCodePoint(code);
    }
    if (lower.startsWith("#")) {
      const code = Number.parseInt(entity.slice(1), 10);
      return Number.isNaN(code) ? match : String.fromCodePoint(code);
    }

    const named = HTML_ENTITIES[lower];
    return named ?? match;
  });
}

/**
 * Split a snippet into consecutive segments, flagging the ones Algolia
 * wrapped in `<mark>` so the UI can style them.
 *
 * Returns an empty array for an empty snippet. Unbalanced or missing tags
 * degrade gracefully to a single non-highlighted segment.
 */
export function parseHighlightSnippet(snippet: string): HighlightSegment[] {
  if (!snippet) return [];

  if (!MARK_SPLIT_RE.test(snippet)) {
    return [{ text: decodeHtmlEntities(snippet), highlighted: false }];
  }

  const segments: HighlightSegment[] = [];
  let depth = 0;

  for (const part of snippet.split(MARK_TOKEN_RE)) {
    if (!part) continue;

    const lower = part.toLowerCase();
    if (lower === "<mark>") {
      depth += 1;
      continue;
    }
    if (lower === "</mark>") {
      depth = Math.max(0, depth - 1);
      continue;
    }

    const text = decodeHtmlEntities(part);
    const highlighted = depth > 0;
    const previous = segments[segments.length - 1];

    // Merge adjacent segments of the same kind (e.g. `</mark><mark>`).
    if (previous && previous.highlighted === highlighted) {
      previous.text += text;
    } else {
      segments.push({ text, highlighted });
    }
  }

  return segments;
}

/** How the excerpt zone of a vignette wants a snippet cut down. */
export interface HighlightWindow {
  /**
   * How much context is kept *before* the first match. This is the whole point
   * of the transform: what the reader has to see is the matched words, and a
   * box bounded to a few lines truncates at its end, so a match sitting further
   * in than this is simply not on screen.
   */
  leadChars: number;
  /**
   * Ceiling on the whole excerpt. A snippet is normally a few words wide, but
   * the backend falls back to the *entire* highlighted transcript chunk when
   * Algolia returns no snippet — thousands of characters handed to a `Text` that
   * will show three lines of them.
   */
  maxChars: number;
}

/**
 * Slide a bounded window over a parsed snippet so its first match is inside it.
 *
 * Two independent cuts, and an ellipsis wherever text was dropped:
 *
 * - **the lead-in** is trimmed to `leadChars`, which is what guarantees the
 *   highlighted words are among the first ones drawn and therefore inside the
 *   lines the vignette shows. Text that survives ahead of the match is the
 *   context the reader needs to make sense of it — trimming to zero would be as
 *   useless as truncating before the match.
 * - **the tail** is capped at `maxChars`, purely so a runaway highlight cannot
 *   be measured and laid out in full for three visible lines. Whichever cut
 *   comes first — this one or the native `numberOfLines` truncation — the reader
 *   sees an ellipsis.
 *
 * Both cuts land on a word boundary: an excerpt starting mid-word reads as a
 * rendering bug rather than as an extract.
 *
 * A snippet with no match at all is shown from its start: there is nothing to
 * centre on, and the cap still applies.
 */
export function focusHighlightSegments(
  segments: HighlightSegment[],
  { leadChars, maxChars }: HighlightWindow,
): HighlightSegment[] {
  if (segments.length === 0) return segments;

  const firstMatch = segments.findIndex((segment) => segment.highlighted);
  const excessLead =
    firstMatch < 0 ? 0 : lengthBefore(segments, firstMatch) - leadChars;

  return capTail(
    excessLead > 0 ? dropLead(segments, excessLead) : segments,
    maxChars,
  );
}

function lengthBefore(segments: HighlightSegment[], index: number): number {
  let total = 0;
  for (let i = 0; i < index; i += 1) {
    total += segments[i].text.length;
  }
  return total;
}

/** Drop `count` characters off the front, then forward to the next word. */
function dropLead(
  segments: HighlightSegment[],
  count: number,
): HighlightSegment[] {
  const kept: HighlightSegment[] = [];
  let remaining = count;

  for (const segment of segments) {
    if (remaining <= 0) {
      kept.push(segment);
      continue;
    }
    if (segment.text.length <= remaining) {
      remaining -= segment.text.length;
      continue;
    }

    const cut = segment.text.slice(remaining);
    const wordStart = cut.search(WORD_START_RE);
    kept.push({
      text: `${ELLIPSIS}${wordStart >= 0 ? cut.slice(wordStart + 1) : cut}`,
      highlighted: segment.highlighted,
    });
    remaining = 0;
  }

  return kept;
}

/** Keep at most `maxChars`, ending on a word boundary. */
function capTail(
  segments: HighlightSegment[],
  maxChars: number,
): HighlightSegment[] {
  const kept: HighlightSegment[] = [];
  let used = 0;
  let dropped = false;

  for (const segment of segments) {
    const room = maxChars - used;
    if (room <= 0) {
      dropped = true;
      break;
    }
    if (segment.text.length <= room) {
      kept.push(segment);
      used += segment.text.length;
      continue;
    }

    const head = segment.text.slice(0, room);
    kept.push({
      // Backing off to the previous word boundary can empty a long unbroken
      // run (a URL, a Japanese sentence), which is then cut where it is.
      text: head.replace(TRAILING_WORD_RE, "") || head,
      highlighted: segment.highlighted,
    });
    dropped = true;
    break;
  }

  // Its own segment rather than appended to the last one: an ellipsis inside a
  // highlighted run would come out drawn on the match's amber.
  if (dropped) kept.push({ text: ELLIPSIS, highlighted: false });

  return kept;
}
