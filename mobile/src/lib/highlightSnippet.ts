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
 */

export interface HighlightSegment {
  text: string;
  highlighted: boolean;
}

const MARK_SPLIT_RE = /<\/?mark>/i;
const MARK_TOKEN_RE = /(<mark>|<\/mark>)/gi;

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
