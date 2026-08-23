import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { ShareIntentProvider as ExpoShareIntentProvider } from "expo-share-intent";
import { I18nProvider } from "../src/i18n";
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
 * 2. I18nProvider - resolves the interface language (device locale, or the
 *    in-app override read from the device) before anything renders a word of
 *    it. Outermost of our own providers because every one of them can end up
 *    producing user-facing copy.
 * 3. AuthProvider - manages authentication state.
 * 4. UserPreferencesProvider - manages reading language preference.
 * 5. PurchasesProvider - manages IAP state.
 * 6. ShareIntentProvider (our custom) - consumes the package's context, maps
 *    to our ShareIntakeState, handles auth gating and navigation.
 * 7. InboxProvider - manages inbox state.
 *
 * Expo Router uses this as the entry point for all navigation.
 */
export default function RootLayout() {
  return (
    <ExpoShareIntentProvider options={{ debug: false, resetOnBackground: true, scheme: "media-summarizer" }}>
      <I18nProvider>
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
                <Stack.Screen
                  name="onboarding/language"
                  options={{
                    animation: "slide_from_right",
                    gestureEnabled: false,
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
                  name="media/[id]"
                  options={{
                    animation: "slide_from_right",
                  }}
                />
                <Stack.Screen
                  name="media/collections/index"
                  options={{
                    animation: "slide_from_right",
                  }}
                />
                <Stack.Screen
                  name="media/collections/[id]"
                  options={{
                    animation: "slide_from_right",
                  }}
                />
                <Stack.Screen
                  name="artifacts/[artifactId]"
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
                <Stack.Screen
                  name="settings/delete-account"
                  options={{
                    animation: "slide_from_right",
                  }}
                />
                <Stack.Screen
                  name="settings/interface-language"
                  options={{
                    animation: "slide_from_right",
                  }}
                />
                {/* Opened from the Account tab and from a quota refusal on the
                    share confirmation screen, so it presents over whatever
                    pushed it and dismisses back to it. */}
                <Stack.Screen
                  name="paywall"
                  options={{
                    presentation: "modal",
                    animation: "slide_from_bottom",
                    gestureEnabled: true,
                  }}
                />
              </Stack>
            </InboxProvider>
          </ShareIntentProvider>
        </PurchasesProvider>
      </UserPreferencesProvider>
      </AuthProvider>
      </I18nProvider>
    </ExpoShareIntentProvider>
  );
}
