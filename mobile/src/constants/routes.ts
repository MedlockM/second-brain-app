/**
 * Routes that carry a navigation invariant, named so that no screen has to
 * restate it.
 *
 * Everything else in the app navigates with inline paths, which is fine: a
 * detail screen pushing `/media/[id]` states nothing beyond where it goes. The
 * two below are different — they are the only entry points of the
 * post-authentication funnel, and the bug they exist to prevent (task-326) was
 * exactly a screen deciding on its own where a fresh session should land.
 */

/**
 * The one route every authenticated path must go through.
 *
 * `app/index.tsx` is the only place allowed to choose between the tabs and the
 * language onboarding, so login, registration and both social flows send the
 * user here and let it decide. An auth screen that targets a tab directly
 * bypasses the language gate.
 */
export const POST_AUTH_ENTRY_POINT = "/";

/**
 * The reading-language gate. Reached from `app/index.tsx` on a cold start, and
 * from `app/(tabs)/_layout.tsx`, which is the mandatory passage of all four tabs
 * and therefore the point that makes the gate impossible to walk past.
 */
export const LANGUAGE_ONBOARDING_ROUTE = "/onboarding/language";
