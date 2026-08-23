import { Redirect, Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { Colors, TouchTarget } from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";
import { ActivityIndicator, View, StyleSheet } from "react-native";

/**
 * Protected tabs layout.
 * Navigation guard: redirects to login if not authenticated.
 * Tab bar follows the mockup navigation pattern (Home, Search, Digest, Account).
 */
export default function TabsLayout() {
  const { isAuthenticated, isLoading } = useAuth();
  // The four labels are resolved on render, so the bar has to redraw when the
  // interface language changes.
  useTranslation();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/login" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: Colors.tabActive,
        tabBarInactiveTintColor: Colors.tabInactive,
        tabBarStyle: {
          backgroundColor: Colors.surface,
          borderTopColor: Colors.outlineVariant,
          borderTopWidth: StyleSheet.hairlineWidth,
          paddingTop: 4,
          height: TouchTarget.large,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "500",
          letterSpacing: 0.3,
        },
      }}
    >
      <Tabs.Screen
        name="inbox"
        options={{
          title: t("tabs.home"),
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="file-tray-outline" size={size} color={color} />
          ),
        }}
      />
      {/* The screen file stays `search`, and so does its test id: only the
          label has ever moved. task-306 labelled this tab for its content
          ("Library") because the screen holds every collection and every saved
          item; task-315 put it back on the action, so the two labels now name
          what the user does — go Home, or Search — rather than what each screen
          contains. */}
      <Tabs.Screen
        name="search"
        options={{
          title: t("tabs.search"),
          tabBarButtonTestID: "search-tab-button",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="library-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="digest"
        options={{
          title: t("tabs.digest"),
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="sparkles-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="account"
        options={{
          title: t("account.title"),
          tabBarButtonTestID: "account-tab-button",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Colors.background,
  },
});
