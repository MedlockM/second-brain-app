import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { ShareIntentProvider as ExpoShareIntentProvider } from "expo-share-intent";
import { AuthProvider } from "../src/contexts/AuthContext";
import { UserPreferencesProvider } from "../src/contexts/UserPreferencesContext";
import { ShareIntentProvider } from "../src/contexts/ShareIntentContext";
import { InboxProvider } from "../src/contexts/InboxContext";
import { PurchasesProvider } from "../src/contexts/PurchasesContext";
import { Colors } from "../src/constants/theme";

// Keep splash screen visible while we initialize auth
SplashScreen.preventAutoHideAsync();

/**
 * Root layout - wraps the entire app with providers in this order:
 * 1. ExpoShareIntentProvider (from expo-share-intent package) - handles native
 *    module communication, URL interception, App Groups resolution on iOS.
 * 2. AuthProvider - manages authentication state.
 * 3. UserPreferencesProvider - manages reading language preference.
 * 4. PurchasesProvider - manages IAP state.
 * 5. ShareIntentProvider (our custom) - consumes the package's context, maps
 *    to our ShareIntakeState, handles auth gating and navigation.
 * 6. InboxProvider - manages inbox state.
 *
 * Expo Router uses this as the entry point for all navigation.
 */
export default function RootLayout() {
  return (
    <ExpoShareIntentProvider options={{ debug: false, resetOnBackground: true, scheme: "media-summarizer" }}>
      <AuthProvider>
        <UserPreferencesProvider>
          <PurchasesProvider>
            <ShareIntentProvider>
              <InboxProvider>
                <StatusBar style="dark" backgroundColor={Colors.background} />
                <Stack
                  screenOptions={{
                    headerShown: false,
                    contentStyle: { backgroundColor: Colors.background },
                  }}
                >
                  <Stack.Screen name="index" />
                  <Stack.Screen name="(auth)" />
                  <Stack.Screen name="(tabs)" />
                  <Stack.Screen
                    name="onboarding/language"
                    options={{
                      animation: "slide_from_right",
                      gestureEnabled: false,
                    }}
                  />
                  <Stack.Screen
                    name="paywall"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                      gestureEnabled: true,
                    }}
                  />
                  <Stack.Screen
                    name="share-confirmation"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                      gestureEnabled: true,
                    }}
                  />
                  <Stack.Screen
                    name="share-confirm"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                    }}
                  />
                  <Stack.Screen
                    name="media/[id]"
                    options={{
                      animation: "slide_from_right",
                    }}
                  />
                  <Stack.Screen
                    name="media/tags"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                      gestureEnabled: true,
                    }}
                  />
                  <Stack.Screen
                    name="media/collection"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                      gestureEnabled: true,
                    }}
                  />
                  <Stack.Screen
                    name="bug-report"
                    options={{
                      presentation: "modal",
                      animation: "slide_from_bottom",
                      gestureEnabled: true,
                    }}
                  />
                  <Stack.Screen
                    name="settings/reading-language"
                    options={{
                      animation: "slide_from_right",
                    }}
                  />
                </Stack>
              </InboxProvider>
            </ShareIntentProvider>
          </PurchasesProvider>
        </UserPreferencesProvider>
      </AuthProvider>
    </ExpoShareIntentProvider>
  );
}
