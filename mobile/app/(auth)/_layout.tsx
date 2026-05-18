import { Redirect, Stack } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { Colors } from "../../src/constants/theme";

/**
 * Auth group layout.
 * Redirects to main app if already authenticated.
 */
export default function AuthLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  // If already authenticated, redirect to main app
  if (!isLoading && isAuthenticated) {
    return <Redirect href="/(tabs)/inbox" />;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: Colors.background },
        animation: "slide_from_right",
      }}
    />
  );
}
