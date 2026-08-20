import { Redirect, Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { Colors, TouchTarget } from "../../src/constants/theme";
import { ActivityIndicator, View, StyleSheet } from "react-native";

/**
 * Protected tabs layout.
 * Navigation guard: redirects to login if not authenticated.
 * Tab bar follows the mockup navigation pattern (Inbox, Library, Digest, Account).
 */
export default function TabsLayout() {
  const { isAuthenticated, isLoading } = useAuth();

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
          title: "Inbox",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="file-tray-outline" size={size} color={color} />
          ),
        }}
      />
      {/* The screen file stays `search`, and so does its test id: what changed
          is what the tab holds. It is the library — every collection and every
          saved media item — with the search over it in a pill at the top, so it
          is labelled for the content and not for one of the two ways to reach
          it (task-306). */}
      <Tabs.Screen
        name="search"
        options={{
          title: "Library",
          tabBarButtonTestID: "search-tab-button",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="library-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="digest"
        options={{
          title: "Digest",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="sparkles-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="account"
        options={{
          title: "Account",
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
