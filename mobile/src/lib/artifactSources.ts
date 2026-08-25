/**
 * Comparing what an artifact was generated over with what a scope holds now.
 *
 * This is the whole condition behind the collection's "Generate" affordance
 * (task-322): the backend keys an artifact on its set of sources, so asking again
 * over an unchanged set answers the stored entry rather than producing a new one.
 * Offering the button in that case would promise something no request can
 * deliver, so the screen asks this question first.
 *
 * A *set*, deliberately: order carries no meaning — the backend sorts the ids
 * before hashing them — and a duplicate id would be the same source twice.
 */

/** True when both sides designate exactly the same sources, order aside. */
export function sameSourceSet(
  a: readonly string[],
  b: readonly string[],
): boolean {
  const left = new Set(a);
  const right = new Set(b);
  if (left.size !== right.size) return false;
  for (const id of left) {
    if (!right.has(id)) return false;
  }
  return true;
}
