import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { ShareIntentProvider as ExpoShareIntentProvider } from "expo-share-intent";
import { AuthProvider } from "../src/contexts/AuthContext";
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
 * 3. PurchasesProvider - manages IAP state.
 * 4. ShareIntentProvider (our custom) - consumes the package's context, maps
 *    to our ShareIntakeState, handles auth gating and navigation.
 * 5. InboxProvider - manages inbox state.
 *
 * Expo Router uses this as the entry point for all navigation.
 */
export default function RootLayout() {
  return (
    <ExpoShareIntentProvider options={{ debug: false, resetOnBackground: true, scheme: "media-summarizer" }}>
      <AuthProvider>
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
              </Stack>
            </InboxProvider>
          </ShareIntentProvider>
        </PurchasesProvider>
      </AuthProvider>
    </ExpoShareIntentProvider>
  );
}
