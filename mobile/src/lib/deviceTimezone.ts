/**
 * The device's IANA time zone, as the OS reports it.
 *
 * The Digest notifies at 18:30 *local* time, so the backend has to know which
 * local that is. What it stores is the IANA name ("Europe/Paris"), never a UTC
 * offset: a stored "+02:00" is wrong six months a year, while the name carries
 * its own DST rules.
 *
 * `expo-localization` was already a dependency — `src/i18n/index.tsx` reads
 * `getLocales()` from it for the interface language — so this needs no new
 * package, and therefore no new native build: the change ships over the air.
 */

import { getCalendars } from "expo-localization";

/**
 * Whether the OS gave a zone *name* rather than a UTC offset.
 *
 * Not a theoretical guard: `getCalendars()[0].timeZone` is the IANA identifier
 * on iOS and Android, but Expo documents `'GMT+1'` as a possible answer too, and
 * an offset is precisely what must never be stored — "+02:00" is wrong six
 * months a year. The backend refuses one, so sending it would also mean a failed
 * request on every single foreground pass, forever.
 *
 * A zone name either carries a region path ("Europe/Paris", "Etc/GMT+2") or is
 * purely alphabetic ("UTC", "GMT"). Every offset spelling — "+02:00", "-0500",
 * "GMT+1", "UTC+2" — is neither.
 */
function looksLikeZoneName(zone: string): boolean {
  return zone.includes("/") ? /^[A-Za-z]/.test(zone) : /^[A-Za-z]+$/.test(zone);
}

/**
 * The IANA zone name of the device, or `null` when it cannot be established.
 *
 * `null` is a legitimate answer, not a failure to paper over: the field stays
 * empty server-side rather than being back-filled to UTC, because a Digest that
 * rings at 20:30 is worse than one that waits for the zone to be known.
 */
export function getDeviceTimezone(): string | null {
  try {
    const zone = getCalendars()[0]?.timeZone?.trim();
    if (!zone || !looksLikeZoneName(zone)) return null;
    return zone;
  } catch {
    // Never let reading a calendar be the reason a foreground pass throws.
    return null;
  }
}
