import { useEffect } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { ShareIntentProvider as ExpoShareIntentProvider } from "expo-share-intent";
import { I18nProvider } from "../src/i18n";
import { AuthProvider, useAuth } from "../src/contexts/AuthContext";
import { UserPreferencesProvider } from "../src/contexts/UserPreferencesContext";
import { ShareIntentProvider } from "../src/contexts/ShareIntentContext";
import { InboxProvider } from "../src/contexts/InboxContext";
import { PurchasesProvider } from "../src/contexts/PurchasesContext";
import { Colors } from "../src/constants/theme";

// Hold the native splash screen for the whole life of the process: it covers the
// bootstrap whatever the process was started for. `SplashGate` below is the one
// thing that gives it back.
void SplashScreen.preventAutoHideAsync().catch(() => {
  // Nothing left to prevent (the splash was already dismissed): not a failure.
});

// The frame underneath the splash is a real screen on `Colors.background`, so
// fading out reads as the app arriving rather than as a cut.
SplashScreen.setOptions({ duration: 250, fade: true });

/**
 * Gives the native splash screen back once the bootstrap it covers is resolved.
 *
 * It lives in the provider tree rather than in a route, and that is the whole
 * point. The splash is held from module scope — for every entry point at once —
 * so whatever hides it has to be mounted for every entry point too. The `/` route
 * was not: a cold start driven by a share never mounts it, because
 * `+native-intent.tsx` rewrites the share URL to `/(tabs)/inbox`. The splash then
 * stayed attached for good; the share modal was presented above it and saved
 * correctly, and closing the modal dropped the user back onto a root view still
 * hidden behind the splash, with no way out (iOS beta feedback on build 4).
 *
 * Two gates decide when there is something to show, and both sit above this
 * component: `I18nProvider` renders null until the stored interface language is
 * read, and `AuthProvider` starts out loading. Past those, every route renders a
 * surface of its own — content, a redirect, or its spinner on
 * `Colors.background` — and the effect only runs once that render is committed,
 * so nothing blank can appear in the handover.
 */
function SplashGate(): null {
  const { isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    void SplashScreen.hideAsync().catch(() => {
      // Already hidden, e.g. after a Metro reload: nothing owed.
    });
  }, [isLoading]);

  return null;
}

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
 * `SplashGate` is mounted right under AuthProvider, the shallowest place that has
 * everything it needs to know the bootstrap is over.
 *
 * Expo Router uses this as the entry point for all navigation.
 */
export default function RootLayout() {
  return (
    <ExpoShareIntentProvider options={{ debug: false, resetOnBackground: true, scheme: "media-summarizer" }}>
      <I18nProvider>
      <AuthProvider>
        <SplashGate />
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
                {/* Unsorted review — two deliberate departures from every other
                    modal in this file.
                    `fullScreenModal` rather than `modal`: the iOS card modal
                    insets its content and rounds its corners, which cuts a
                    full-width horizontal pager in half at both ends and makes
                    the page boundaries impossible to feel.
                    `gestureEnabled: false`: this screen's whole business is
                    swiping, and a vertical dismiss gesture layered on top of it
                    turns a slightly-off swipe into an accidental exit mid-triage.
                    The close button in the header is the way out. */}
                <Stack.Screen
                  name="media/unsorted-review"
                  options={{
                    presentation: "fullScreenModal",
                    animation: "slide_from_bottom",
                    gestureEnabled: false,
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
