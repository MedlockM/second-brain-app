import React, { createContext, useContext, useState, useCallback } from "react";
import {
  UserPreferencesService,
  ReadingLanguageCode,
} from "../services/userPreferencesService";
import { useDeviceTimezoneSync } from "../hooks/useDeviceTimezoneSync";
import { useAuth } from "./AuthContext";

interface UserPreferencesContextValue {
  /** Current reading language (ISO 639-1) or null if not set */
  readingLanguage: string | null;
  /** Whether onboarding language selection is needed (user has no reading_language set) */
  needsLanguageOnboarding: boolean;
  /**
   * ISO 8601 instant at which the reading language may be changed again, or null
   * when a change is possible now. The backend allows one change per month and
   * hands this date back on every profile it serves, so the settings screen can
   * say when instead of letting the reader run into a refusal.
   */
  readingLanguageChangeAvailableAt: string | null;
  /** Update the reading language preference via the API */
  updateReadingLanguage: (language: ReadingLanguageCode) => Promise<void>;
  /** Whether an update is currently in progress */
  isUpdating: boolean;
}

const UserPreferencesContext = createContext<UserPreferencesContextValue | null>(
  null,
);

export function UserPreferencesProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  const [isUpdating, setIsUpdating] = useState(false);
  const [localReadingLanguage, setLocalReadingLanguage] = useState<
    string | null
  >(null);
  // Held alongside the language for the same reason: the profile in AuthContext
  // is the one the session was opened with, so a change made in this session
  // would otherwise leave the guard-rail invisible until the next sign-in.
  const [localChangeAvailableAt, setLocalChangeAvailableAt] = useState<
    string | null
  >(null);

  // reading_language comes from the user object (populated by AuthContext from /me response)
  // or from local state after a successful update
  const readingLanguage = localReadingLanguage ?? user?.reading_language ?? null;
  const needsLanguageOnboarding = !readingLanguage;
  const readingLanguageChangeAvailableAt =
    localChangeAvailableAt ??
    user?.reading_language_change_available_at ??
    null;

  // The device's time zone is the other account preference the backend stores,
  // and the only one the user is never asked about: the OS knows it, so it is
  // reported silently on every foreground pass. Exposed through no context value
  // on purpose — nothing in the interface reads it, only the Digest schedule
  // does, server-side.
  useDeviceTimezoneSync({
    userId: user?.id ?? null,
    storedTimezone: user?.iana_timezone ?? null,
  });

  const updateReadingLanguage = useCallback(
    async (language: ReadingLanguageCode) => {
      setIsUpdating(true);
      try {
        const updatedUser =
          await UserPreferencesService.updateReadingLanguage(language);
        setLocalReadingLanguage(updatedUser.reading_language ?? language);
        setLocalChangeAvailableAt(
          updatedUser.reading_language_change_available_at ?? null,
        );
      } finally {
        setIsUpdating(false);
      }
    },
    [],
  );

  const value: UserPreferencesContextValue = {
    readingLanguage,
    needsLanguageOnboarding,
    readingLanguageChangeAvailableAt,
    updateReadingLanguage,
    isUpdating,
  };

  return (
    <UserPreferencesContext.Provider value={value}>
      {children}
    </UserPreferencesContext.Provider>
  );
}

/**
 * Hook to access user preferences context. Must be used within UserPreferencesProvider.
 */
export function useUserPreferences(): UserPreferencesContextValue {
  const context = useContext(UserPreferencesContext);
  if (!context) {
    throw new Error(
      "useUserPreferences must be used within a UserPreferencesProvider",
    );
  }
  return context;
}
