import { Redirect, Stack } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { POST_AUTH_ENTRY_POINT } from "../../src/constants/routes";
import { Colors } from "../../src/constants/theme";

/**
 * Auth group layout.
 * Hands an authenticated user back to `/`, which is the only route allowed to
 * decide where a session goes.
 */
export default function AuthLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  // Naming a destination here is what made the onboarding gate skippable: this
  // redirect and the explicit navigation of the register screen both fired on
  // the same AuthContext setState, and whichever won decided whether the
  // language gate was ever consulted. Both target `/` now, so the order no
  // longer changes the outcome — and this layout keeps its one real job, which
  // is to not leave a live session sitting on the sign-in form (a session
  // repaired in the background by revalidateSession reaches this branch with no
  // screen having navigated).
  if (!isLoading && isAuthenticated) {
    return <Redirect href={POST_AUTH_ENTRY_POINT} />;
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
