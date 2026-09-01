import { useEffect } from "react";
import { Redirect } from "expo-router";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import * as SplashScreen from "expo-splash-screen";
import { useAuth } from "../src/contexts/AuthContext";
import { useUserPreferences } from "../src/contexts/UserPreferencesContext";
import { LANGUAGE_ONBOARDING_ROUTE } from "../src/constants/routes";
import { Colors } from "../src/constants/theme";

/**
 * Root index route — the single entry point of every authenticated path, and the
 * only route allowed to choose where a session lands. Login, registration and
 * both social flows navigate here (`POST_AUTH_ENTRY_POINT`) instead of naming a
 * tab, so the destination is decided once, from one place.
 *
 * Shows a loading indicator during session restoration.
 *
 * Routing logic:
 * 1. Not authenticated -> login
 * 2. Authenticated, no reading language -> onboarding language selection
 * 3. Authenticated with a reading language -> inbox
 *
 * Case 2 is the fast path, not the guarantee: this route only redirects while it
 * is focused, so it cannot be what *enforces* the language gate. Enforcement
 * lives in `app/(tabs)/_layout.tsx`, the mandatory passage of all four tabs. The
 * two read the same `needsLanguageOnboarding` from `UserPreferencesContext`, and
 * that boolean is the single definition of the rule — neither restates it.
 */
export default function Index() {
  const { isLoading, isAuthenticated } = useAuth();
  const { needsLanguageOnboarding } = useUserPreferences();

  useEffect(() => {
    if (!isLoading) {
      SplashScreen.hideAsync();
    }
  }, [isLoading]);

  if (isLoading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (isAuthenticated) {
    if (needsLanguageOnboarding) {
      return <Redirect href={LANGUAGE_ONBOARDING_ROUTE} />;
    }
    return <Redirect href="/(tabs)/inbox" />;
  }

  return <Redirect href="/(auth)/login" />;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Colors.background,
  },
});
