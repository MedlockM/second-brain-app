import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { AuthProvider } from "../src/contexts/AuthContext";
import { ShareIntentProvider } from "../src/contexts/ShareIntentContext";
import { InboxProvider } from "../src/contexts/InboxContext";
import { Colors } from "../src/constants/theme";
import { ShareIntentHandler } from "../src/components/ShareIntentHandler";

// Keep splash screen visible while we initialize auth
SplashScreen.preventAutoHideAsync();

/**
 * Root layout - wraps the entire app with AuthProvider, ShareIntentProvider (Android),
 * and InboxProvider (iOS share extension).
 * Expo Router uses this as the entry point for all navigation.
 *
 * The share-confirmation screen is presented as a modal so the user can
 * quickly save a link and return to the source app.
 */
export default function RootLayout() {
  return (
    <AuthProvider>
      <ShareIntentProvider>
        <InboxProvider>
          <ShareIntentHandler />
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
          </Stack>
        </InboxProvider>
      </ShareIntentProvider>
    </AuthProvider>
  );
}
