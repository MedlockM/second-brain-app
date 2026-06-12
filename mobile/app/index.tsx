import { useEffect } from "react";
import { Redirect } from "expo-router";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import * as SplashScreen from "expo-splash-screen";
import { useAuth } from "../src/contexts/AuthContext";
import { useUserPreferences } from "../src/contexts/UserPreferencesContext";
import { Colors } from "../src/constants/theme";

/**
 * Root index route - redirects based on auth state and onboarding completion.
 * Shows loading indicator during session restoration.
 *
 * Routing logic:
 * 1. Not authenticated -> login
 * 2. Authenticated but no reading_language set -> onboarding language selection
 * 3. Authenticated with reading_language -> inbox
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
      return <Redirect href="/onboarding/language" />;
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
