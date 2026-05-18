import { useShareIntent } from "../hooks/useShareIntent";

/**
 * Component that activates share intent listening.
 * Renders nothing - purely a side-effect component that hooks into
 * the navigation system to handle incoming share intents.
 *
 * Placed in the root layout so it is always active when the app is running.
 */
export function ShareIntentHandler(): null {
  useShareIntent();
  return null;
}
