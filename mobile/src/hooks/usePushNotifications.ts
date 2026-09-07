/**
 * The two things the app owes the Digest notification path: a registered device,
 * and somewhere to land when a notification is opened.
 *
 * Registration is attempted once per signed-in account, and retried on every
 * return to the foreground until it succeeds. The retry costs one permission
 * *read* — it can never re-prompt, the service holds that invariant — and it is
 * what recovers the two everyday failures: the device was offline when the
 * account signed in, and the user granted the permission afterwards in the system
 * settings. Same shape and same reasons as `useDeviceTimezoneSync`.
 *
 * A refusal ends the attempt and nothing else. No state is exposed, no screen
 * reads this hook, and there is no interface anywhere that behaves differently
 * for a user who said no.
 */

import { useCallback, useEffect, useRef } from "react";
import { AppState } from "react-native";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";
import { registerForPushNotifications } from "../services/pushNotificationService";

export function usePushNotifications(userId: string | null): void {
  const router = useRouter();

  // Which account this device is registered for. Keyed by id, because the
  // provider outlives a sign-out: a second account signing in on the same phone
  // has to register the same token under its own id.
  const registeredForRef = useRef<string | null>(null);
  const isRegisteringRef = useRef(false);
  // The notification whose tap has already been routed. `useLastNotificationResponse`
  // keeps returning the same response for the life of the process, so without this
  // every re-render would navigate again.
  const handledResponseRef = useRef<string | null>(null);

  const register = useCallback(async () => {
    if (!userId || isRegisteringRef.current) return;
    if (registeredForRef.current === userId) return;

    isRegisteringRef.current = true;
    try {
      if ((await registerForPushNotifications()) === "registered") {
        registeredForRef.current = userId;
      }
      // Any other outcome leaves the ref untouched on purpose: `denied` and
      // `unavailable` are both states the next foreground pass may find changed.
    } catch {
      // The API call failed — offline, or a session the backend refused. Silent:
      // there is no UI for this and nothing the user could do about it.
    } finally {
      isRegisteringRef.current = false;
    }
  }, [userId]);

  // Sign-in, and the moment the session is restored on a cold start.
  useEffect(() => {
    void register();
  }, [register]);

  // Permission granted in the system settings, or connectivity coming back.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState !== "active") return;
      void register();
    });
    return () => subscription.remove();
  }, [register]);

  // The notification that was opened, if any. `undefined` while expo-notifications
  // is still working out whether there is one; `null` when there is none.
  const lastResponse = Notifications.useLastNotificationResponse();

  useEffect(() => {
    // Only for a signed-in account: on a cold start driven by a notification tap
    // the session is still being restored, and navigating to a protected tab
    // before it lands would be undone by the auth redirect. The effect re-runs
    // when `userId` arrives, which is when the navigation actually happens.
    if (!userId || !lastResponse) return;
    // A tap on the notification body, not on a custom action. The app declares
    // none, so anything else is not ours to route.
    if (lastResponse.actionIdentifier !== Notifications.DEFAULT_ACTION_IDENTIFIER) {
      return;
    }

    const { identifier, content } = lastResponse.notification.request;
    if (handledResponseRef.current === identifier) return;
    handledResponseRef.current = identifier;

    // `data.digest_type` is written by `workers/digest/scheduler.py`. Anything
    // that is not the weekly Digest opens the daily one — the tab has to open on
    // something, and the daily is what the screen already defaults to.
    const tab = content.data?.digest_type === "weekly" ? "weekly" : "daily";

    // Deferred by a tick, exactly as `ShareIntentContext` defers its own: this
    // hook is mounted above the navigator, and on a cold start the effect can run
    // before the root navigation state exists.
    const timer = setTimeout(() => {
      router.navigate({ pathname: "/(tabs)/digest", params: { tab } });
    }, 0);
    return () => clearTimeout(timer);
  }, [lastResponse, router, userId]);
}
