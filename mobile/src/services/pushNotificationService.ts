/**
 * Device registration for Digest push notifications — the client half of the
 * delivery path task-368 settled on: **Expo Push Service, one token per device**.
 *
 * The app's entire role is to obtain that token and hand it to the backend. It
 * never sends a notification, never schedules one locally and never polls: the
 * decision of *when* a Digest is worth announcing belongs to
 * `workers/digest/scheduler.py`, which knows the account's time zone and the
 * contents of the period.
 *
 * **A refusal is a normal outcome, not a failure.** Every path here resolves to
 * one of three outcomes, none of them throws at the caller for a permission
 * reason, and nothing in the interface changes when the answer is no: the app is
 * fully usable without notifications, there is no explanatory modal, no banner
 * inviting the user to reconsider and no deep link into the system settings. The
 * OS prompt is shown **at most once per process**, and never at all once the OS
 * says the question is closed — see `ensurePermission`.
 *
 * **The token is a credential.** Anyone holding it can push to that device. It is
 * never logged, never put in a route param, never rendered, and the only copy the
 * app keeps is the module-level memo below — which exists for exactly one reason:
 * sign-out has to be able to name the row it is deleting.
 */

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { apiRequest } from "./apiClient";
import { Config } from "../constants/config";
import { t } from "../i18n";

/**
 * What one registration attempt concluded.
 *
 * `unavailable` and `denied` are deliberately distinct even though the app
 * behaves identically in both: only the second one means the user was asked.
 */
export type PushRegistrationOutcome = "registered" | "denied" | "unavailable";

/**
 * The Android notification channel every Digest notification belongs to.
 *
 * The same string is `ANDROID_CHANNEL_ID` in
 * `media_summarizer/workers/push_notification_worker.py`, which puts it in the
 * `channelId` of the Expo payload. A channel id Android does not know falls back
 * to expo-notifications' own "Miscellaneous" channel, so a mismatch would not
 * lose the notification — it would file it under a category the user cannot
 * recognise, and the per-category mute Android offers would stop working as a way
 * to mute the Digest.
 */
const ANDROID_CHANNEL_ID = "digest";

/**
 * The token this process registered, or null.
 *
 * Module scope rather than React state because it outlives every component that
 * could hold it and is read from `AuthContext.logout`, which is not a screen.
 */
let registeredToken: string | null = null;

/**
 * Whether the OS permission prompt has already been shown in this process.
 *
 * This is what "no insistent re-prompt" is made of. `canAskAgain` alone is not
 * enough: on Android the system allows a second request before it locks the
 * answer, so a hook that retries on every return to the foreground would ask
 * twice. Once per process, and the retries past that only ever *read* the
 * permission — which is what still lets a user who granted it later, in the
 * system settings, get registered on their next foreground pass.
 */
let hasRequestedPermission = false;

/**
 * How a notification arriving while the app is open should behave.
 *
 * Set at import time, before anything can arrive. Shown, because a Digest that
 * lands while the user is in the app is the same information as one that lands on
 * the lock screen, and tapping it is how they get to it. Silent and badgeless: it
 * is a daily summary, not a message, and nothing in this app ever sets a badge
 * count — so asking for the badge permission would be asking for something unused.
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

/** The platform value the backend records, or null off a real device platform. */
function devicePlatform(): "ios" | "android" | null {
  if (Platform.OS === "ios") return "ios";
  if (Platform.OS === "android") return "android";
  return null;
}

/**
 * Create the Digest channel on Android. A no-op everywhere else.
 *
 * Before the token is ever requested, so no notification can reach the device
 * ahead of the channel it names. Creating a channel that already exists is how
 * the platform expects the call to be made — only the name and the description of
 * an existing channel can change afterwards, everything else the user owns from
 * then on, which is why importance is set once and never adjusted.
 */
async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    // The category label in Android's per-app notification settings. Reuses the
    // tab's own name so the user recognises what they are muting.
    name: t("tabs.digest"),
    // DEFAULT, not HIGH: a Digest belongs in the shade, not in a heads-up banner
    // over whatever the person is doing.
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

/** Whether this app may post notifications, asking at most once. */
async function ensurePermission(): Promise<boolean> {
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;
  if (hasRequestedPermission || !current.canAskAgain) return false;

  hasRequestedPermission = true;
  const requested = await Notifications.requestPermissionsAsync({
    // No `allowBadge`: nothing in this app sets a badge count, and a permission
    // asked for and never used is one the user was asked for under false
    // pretences.
    ios: { allowAlert: true, allowSound: true },
  });
  return requested.granted;
}

/**
 * Register this device for the signed-in account.
 *
 * Throws only on a failure of the API call itself — a network error, or a session
 * the backend refused. The caller treats that as "not registered yet" and tries
 * again on the next return to the foreground.
 */
export async function registerForPushNotifications(): Promise<PushRegistrationOutcome> {
  const platform = devicePlatform();
  if (!platform || !Config.EAS_PROJECT_ID) return "unavailable";

  await ensureAndroidChannel();

  if (!(await ensurePermission())) return "denied";

  let token: string;
  try {
    const result = await Notifications.getExpoPushTokenAsync({
      projectId: Config.EAS_PROJECT_ID,
    });
    token = result.data;
  } catch {
    // No push capability behind this JS bundle. A simulator with no APNs
    // registration is the everyday case, an Expo Go run or a device that could
    // not reach Expo's servers are the others — all three mean "there is no token
    // to send", and none of them is an error the user should ever hear about.
    return "unavailable";
  }

  await apiRequest<void>("/api/push-token", {
    method: "POST",
    body: { expo_push_token: token, platform },
  });
  registeredToken = token;
  return "registered";
}

/**
 * Forget this device on the way out of an account.
 *
 * Called from `AuthContext.logout` *before* the session is torn down, because it
 * needs that session to authenticate. Skipping it would leave the device
 * registered under the account that signed out: a second account signing in on
 * the same phone would register the same token again, and the first account's
 * Digest notification would then land on a screen the second one is looking at.
 *
 * The memo is cleared before the call rather than after, so a DELETE that fails
 * offline still leaves the app in the honest state — this process no longer
 * claims to hold a registration — and the next sign-in re-registers cleanly.
 */
export async function unregisterCurrentDevice(): Promise<void> {
  const token = registeredToken;
  if (!token) return;
  registeredToken = null;

  await apiRequest<void>("/api/push-token", {
    method: "DELETE",
    body: { expo_push_token: token },
  });
}
