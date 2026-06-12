import React, { createContext, useContext, useState, useCallback } from "react";
import {
  UserPreferencesService,
  ReadingLanguageCode,
} from "../services/userPreferencesService";
import { useAuth } from "./AuthContext";

interface UserPreferencesContextValue {
  /** Current reading language (ISO 639-1) or null if not set */
  readingLanguage: string | null;
  /** Whether onboarding language selection is needed (user has no reading_language set) */
  needsLanguageOnboarding: boolean;
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
  const { user, token } = useAuth();
  const [isUpdating, setIsUpdating] = useState(false);
  const [localReadingLanguage, setLocalReadingLanguage] = useState<
    string | null
  >(null);

  // reading_language comes from the user object (populated by AuthContext from /me response)
  // or from local state after a successful update
  const readingLanguage = localReadingLanguage ?? user?.reading_language ?? null;
  const needsLanguageOnboarding = !readingLanguage;

  const updateReadingLanguage = useCallback(
    async (language: ReadingLanguageCode) => {
      if (!token) {
        throw new Error("Not authenticated");
      }
      setIsUpdating(true);
      try {
        const updatedUser =
          await UserPreferencesService.updateReadingLanguage(token, language);
        setLocalReadingLanguage(updatedUser.reading_language ?? language);
      } finally {
        setIsUpdating(false);
      }
    },
    [token],
  );

  const value: UserPreferencesContextValue = {
    readingLanguage,
    needsLanguageOnboarding,
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
