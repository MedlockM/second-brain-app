import { useCallback, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Pressable,
  ScrollView,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { useUserPreferences } from "../../src/contexts/UserPreferencesContext";
import { usePurchases } from "../../src/contexts/PurchasesContext";
import { V1_READING_LANGUAGES } from "../../src/services/userPreferencesService";
import { FeedbackService } from "../../src/services/feedbackService";
import { SubscriptionStatusCard } from "../../src/components/SubscriptionStatusCard";
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
 * Shows user info, the subscription state, the paywall entry point and the
 * logout action. Full implementation (stats, integrations, appearance) deferred
 * to later tasks.
 */
export default function AccountScreen() {
  const { user, token, logout } = useAuth();
  const { readingLanguage } = useUserPreferences();
  const {
    isSubscribed,
    entitlementStatus,
    isLoading: isEntitlementLoading,
    refreshEntitlements,
  } = usePurchases();
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const router = useRouter();

  // This is the screen where the remaining minutes are read, and they move on
  // every transcribed import, so refresh on focus instead of trusting the value
  // fetched at sign-in. Also picks up a purchase made from the paywall.
  useFocusEffect(
    useCallback(() => {
      void refreshEntitlements();
    }, [refreshEntitlements]),
  );

  // Every state leads to the paywall: it is where a plan is picked, switched or
  // restored. Only the wording and the icon change. The tier itself is shown by
  // SubscriptionStatusCard, so the subtitle does not repeat it.
  // When the backend state is unknown (request failed, nothing from RevenueCat
  // either) the CTA stays neutral: promising an "Upgrade" would imply we know
  // the user is not subscribed, and we do not.
  const isSubscriptionStateUnknown = entitlementStatus === null && !isSubscribed;
  const subscriptionLabel = isSubscribed
    ? "Manage subscription"
    : isSubscriptionStateUnknown
      ? "View plans"
      : "Upgrade";
  const subscriptionSubtitle = isSubscribed
    ? "Change plan or restore a purchase"
    : isSubscriptionStateUnknown
      ? "See what each subscription includes"
      : "Unlock more minutes of audio and video";

  // Get display label for current reading language
  const readingLanguageLabel =
    V1_READING_LANGUAGES.find((l) => l.code === readingLanguage)?.label ?? "Not set";

  const handleBugReport = () => {
    router.push("/bug-report");
  };

  const handleLogout = () => {
    // The confirmation label is unique app-wide: "Sign Out" alone also matches
    // the menu item and the alert title, which makes the tap ambiguous on iOS.
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Yes, sign out",
        style: "destructive",
        onPress: () => logout(),
      },
    ]);
  };

  const openFeedbackFallback = async (): Promise<void> => {
    const fallbackUrl = FeedbackService.getFallbackUrl();
    if (!fallbackUrl) {
      Alert.alert(
        "Feedback unavailable",
        "The feedback board is not configured yet. Please try again later.",
      );
      return;
    }
    await WebBrowser.openBrowserAsync(fallbackUrl);
  };

  const handleFeedback = async () => {
    setIsFeedbackLoading(true);
    try {
      if (token) {
        const url = await FeedbackService.getFeedbackUrl(token);
        await WebBrowser.openBrowserAsync(url);
      } else {
        await openFeedbackFallback();
      }
    } catch {
      await openFeedbackFallback();
    } finally {
      setIsFeedbackLoading(false);
    }
  };

  // The menu grows past the fold on short screens, and an off-screen row is
  // untappable without any visible sign of it, so the whole body scrolls.
  return (
    <SafeAreaView testID="account-screen" style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>Account</Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Section */}
        <View style={styles.profileSection}>
          <View style={styles.avatar}>
            <Ionicons name="person" size={40} color={Colors.textMuted} />
          </View>
          <Text style={styles.email}>{user?.email ?? ""}</Text>
        </View>

        {/* Subscription state (display only, enforcement stays backend-side) */}
        <SubscriptionStatusCard
          entitlement={entitlementStatus}
          isLoading={isEntitlementLoading}
          onRetry={() => void refreshEntitlements()}
        />

        {/* Subscription entry point */}
        <Pressable
          testID="account-upgrade-button"
          style={({ pressed }) => [
            styles.subscriptionCard,
            pressed && styles.subscriptionCardPressed,
          ]}
          onPress={() => router.push("/paywall")}
          accessibilityLabel={`${subscriptionLabel}: ${subscriptionSubtitle}`}
          accessibilityRole="button"
        >
          <View style={styles.subscriptionIcon}>
            <Ionicons
              name={isSubscribed ? "shield-checkmark" : "sparkles"}
              size={20}
              color={Colors.onPrimary}
            />
          </View>
          <View style={styles.subscriptionTextContainer}>
            <Text style={styles.subscriptionLabel}>{subscriptionLabel}</Text>
            <Text style={styles.subscriptionSubtitle}>
              {subscriptionSubtitle}
            </Text>
          </View>
          <Ionicons
            name="chevron-forward"
            size={18}
            color={Colors.textMuted}
          />
        </Pressable>

        {/* Menu */}
        <View style={styles.menuCard}>
          <MenuItem
            icon="language-outline"
            label="Reading Language"
            subtitle={readingLanguageLabel}
            onPress={() => router.push("/settings/reading-language")}
          />
          <MenuItem
            icon="settings-outline"
            label="Settings"
            onPress={() => {}}
          />
          <MenuItem
            icon="bulb-outline"
            label="Feature Requests"
            onPress={handleFeedback}
            isLoading={isFeedbackLoading}
          />
          <MenuItem
            icon="bug-outline"
            label="Report a Bug"
            onPress={handleBugReport}
          />
          <View style={styles.menuDivider} />
          <TouchableOpacity
            testID="account-sign-out-button"
            style={styles.menuItem}
            onPress={handleLogout}
            activeOpacity={0.7}
            accessibilityLabel="Sign Out"
            accessibilityRole="button"
          >
            <View style={[styles.menuIcon, styles.menuIconDanger]}>
              <Ionicons name="log-out-outline" size={18} color={Colors.error} />
            </View>
            <Text
              style={[styles.menuLabel, styles.menuLabelDanger, { flex: 1 }]}
            >
              Sign Out
            </Text>
          </TouchableOpacity>
          {/*
            App Store guideline 5.1.1(v) requires deletion to be reachable from
            inside the app, so it sits here in plain sight next to Sign Out
            rather than behind a support request. The row only navigates: the
            consequences and both confirmations live on the dedicated screen.
          */}
          <TouchableOpacity
            testID="account-delete-account-button"
            style={styles.menuItem}
            onPress={() => router.push("/settings/delete-account")}
            activeOpacity={0.7}
            accessibilityLabel="Delete Account"
            accessibilityRole="button"
          >
            <View style={[styles.menuIcon, styles.menuIconDanger]}>
              <Ionicons name="trash-outline" size={18} color={Colors.error} />
            </View>
            <Text
              style={[styles.menuLabel, styles.menuLabelDanger, { flex: 1 }]}
            >
              Delete Account
            </Text>
            <Ionicons
              name="chevron-forward"
              size={18}
              color={Colors.textMuted}
              style={styles.menuChevron}
            />
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function MenuItem({
  icon,
  label,
  subtitle,
  onPress,
  isLoading,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  subtitle?: string;
  onPress: () => void;
  isLoading?: boolean;
}) {
  return (
    <TouchableOpacity
      style={styles.menuItem}
      onPress={onPress}
      activeOpacity={0.7}
      disabled={isLoading}
      accessibilityLabel={subtitle ? `${label}: ${subtitle}` : label}
      accessibilityRole="button"
    >
      <View style={styles.menuIcon}>
        <Ionicons name={icon} size={18} color={Colors.primary} />
      </View>
      <View style={styles.menuLabelContainer}>
        <Text style={styles.menuLabel}>{label}</Text>
        {subtitle && <Text style={styles.menuSubtitle}>{subtitle}</Text>}
      </View>
      {isLoading ? (
        <ActivityIndicator size="small" color={Colors.textMuted} />
      ) : (
        <Ionicons
          name="chevron-forward"
          size={18}
          color={Colors.textMuted}
          style={styles.menuChevron}
        />
      )}
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: Spacing.xxl,
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
  subscriptionCard: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    minHeight: TouchTarget.comfortable,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    ...Shadows.soft,
  },
  subscriptionCardPressed: {
    backgroundColor: Colors.surfaceContainerLow,
  },
  subscriptionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primary,
    justifyContent: "center",
    alignItems: "center",
    marginRight: Spacing.sm + 4,
  },
  subscriptionTextContainer: {
    flex: 1,
  },
  subscriptionLabel: {
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  subscriptionSubtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginTop: 2,
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
  menuLabelContainer: {
    flex: 1,
  },
  menuLabel: {
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
  },
  menuSubtitle: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginTop: 2,
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
