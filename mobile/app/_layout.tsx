import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { AuthProvider } from "../src/contexts/AuthContext";
import { InboxProvider } from "../src/contexts/InboxContext";
import { Colors } from "../src/constants/theme";
import { ShareIntentHandler } from "../src/components/ShareIntentHandler";

// Keep splash screen visible while we initialize auth
SplashScreen.preventAutoHideAsync();

/**
 * Root layout - wraps the entire app with AuthProvider and InboxProvider.
 * Expo Router uses this as the entry point for all navigation.
 * The ShareIntentHandler listens for incoming share intents.
 */
export default function RootLayout() {
  return (
    <AuthProvider>
      <InboxProvider>
        <ShareIntentHandler />
        <StatusBar style="dark" backgroundColor={Colors.background} />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: Colors.background },
          }}
        >
          <Stack.Screen
            name="share-confirm"
            options={{
              presentation: "modal",
              animation: "slide_from_bottom",
            }}
          />
        </Stack>
      </InboxProvider>
    </AuthProvider>
  );
}
