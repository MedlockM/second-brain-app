import { View, Text, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../../src/constants/theme";

/**
 * Account screen - skeleton following the design mockup.
 * Shows user info and logout action.
 * Full implementation (stats, integrations, appearance) deferred to later tasks.
 */
export default function AccountScreen() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign Out",
        style: "destructive",
        onPress: () => logout(),
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>Account</Text>
      </View>

      {/* Profile Section */}
      <View style={styles.profileSection}>
        <View style={styles.avatar}>
          <Ionicons name="person" size={40} color={Colors.textMuted} />
        </View>
        <Text style={styles.email}>{user?.email ?? ""}</Text>
      </View>

      {/* Menu */}
      <View style={styles.menuCard}>
        <MenuItem
          icon="settings-outline"
          label="Settings"
          onPress={() => {}}
        />
        <MenuItem
          icon="download-outline"
          label="Export Data"
          onPress={() => {}}
        />
        <View style={styles.menuDivider} />
        <TouchableOpacity
          style={styles.menuItem}
          onPress={handleLogout}
          activeOpacity={0.7}
        >
          <View style={[styles.menuIcon, styles.menuIconDanger]}>
            <Ionicons name="log-out-outline" size={18} color={Colors.error} />
          </View>
          <Text style={[styles.menuLabel, styles.menuLabelDanger]}>
            Sign Out
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function MenuItem({
  icon,
  label,
  onPress,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      style={styles.menuItem}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.menuIcon}>
        <Ionicons name={icon} size={18} color={Colors.primary} />
      </View>
      <Text style={styles.menuLabel}>{label}</Text>
      <Ionicons
        name="chevron-forward"
        size={18}
        color={Colors.textMuted}
        style={styles.menuChevron}
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    alignItems: "center",
  },
  title: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
  },
  profileSection: {
    alignItems: "center",
    paddingVertical: Spacing.lg,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.surfaceContainer,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: Spacing.md,
  },
  email: {
    fontSize: Typography.label.fontSize,
    color: Colors.textMuted,
  },
  menuCard: {
    marginHorizontal: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    ...Shadows.soft,
    overflow: "hidden",
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: Spacing.md,
    minHeight: TouchTarget.minimum,
  },
  menuIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "rgba(255, 203, 5, 0.1)",
    justifyContent: "center",
    alignItems: "center",
    marginRight: Spacing.sm + 4,
  },
  menuIconDanger: {
    backgroundColor: "rgba(186, 26, 26, 0.1)",
  },
  menuLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
  },
  menuLabelDanger: {
    color: Colors.error,
  },
  menuChevron: {
    marginLeft: Spacing.sm,
  },
  menuDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: Colors.outlineVariant,
    marginHorizontal: Spacing.md,
  },
});
