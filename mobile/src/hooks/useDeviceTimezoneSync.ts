/**
 * Keeps the account's stored IANA time zone in step with the device.
 *
 * The Digest notifies at 18:30 *local* time (daily) and Monday 09:30 local
 * (weekly), so the backend needs the zone. Nothing about it is ever asked of the
 * user and there is no setting for it: the OS already knows, and a question
 * would only be a worse source of the same answer.
 *
 * It re-reads on every return to the foreground rather than only at sign-up, so
 * a user who flies to New York gets their Digest at 18:30 New York time without
 * doing anything. The `AppState` listener is what makes that work — a state
 * change alone would not, because the device zone can move while the app sits in
 * the background and the *stored* value has not changed, so no prop moves.
 *
 * A write only leaves when the value actually differs, so the common case (a
 * user who never travels, opening the app several times a day) costs nothing.
 */

import { useCallback, useEffect, useRef } from "react";
import { AppState } from "react-native";
import { getDeviceTimezone } from "../lib/deviceTimezone";
import { UserPreferencesService } from "../services/userPreferencesService";

interface DeviceTimezoneSyncInput {
  /** `null` when signed out — nothing to report a zone for. */
  userId: string | null;
  /** The zone the backend holds, or `null` when it holds none yet. */
  storedTimezone: string | null;
}

export function useDeviceTimezoneSync({
  userId,
  storedTimezone,
}: DeviceTimezoneSyncInput): void {
  // What was last accepted by the backend, keyed by account. Keyed, because the
  // provider outlives a sign-out: without the id, a second account signing in on
  // the same device with a different stored zone would be skipped as "already
  // sent". It covers the window between a successful PATCH and the next /me,
  // during which `storedTimezone` still carries the old value.
  const sentRef = useRef<{ userId: string; zone: string } | null>(null);
  const isSendingRef = useRef(false);

  const syncDeviceTimezone = useCallback(async () => {
    if (!userId || isSendingRef.current) return;

    const deviceZone = getDeviceTimezone();
    // No zone to report. The field stays empty rather than falling back to UTC:
    // an unknown zone is a valid state, and the Digest waits for it.
    if (!deviceZone) return;

    const alreadySent =
      sentRef.current?.userId === userId &&
      sentRef.current?.zone === deviceZone;
    if (storedTimezone === deviceZone || alreadySent) return;

    isSendingRef.current = true;
    try {
      const updated = await UserPreferencesService.updateTimezone(deviceZone);
      sentRef.current = {
        userId,
        zone: updated.iana_timezone ?? deviceZone,
      };
    } catch {
      // Offline, or a zone the backend refused. Silent on purpose: there is no
      // UI for this and nothing the user could do about it. The next foreground
      // pass tries again, and `sentRef` is left untouched so it will.
    } finally {
      isSendingRef.current = false;
    }
  }, [userId, storedTimezone]);

  // Sign-in, and the moment /me lands on a cold start.
  useEffect(() => {
    void syncDeviceTimezone();
  }, [syncDeviceTimezone]);

  // The travelling case: same account, same stored value, different device zone.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState !== "active") return;
      void syncDeviceTimezone();
    });
    return () => subscription.remove();
  }, [syncDeviceTimezone]);
}
