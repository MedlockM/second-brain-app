import { useCallback, useEffect, useState } from "react";
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
import { LOCALE_ENDONYMS, t, useTranslation } from "../../src/i18n";
import { fetchPublicPricing } from "../../src/services/pricingService";
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
  const { user, isAuthenticated, logout } = useAuth();
  // Subscribes the screen to the interface language, so switching it in the
  // settings redraws this menu instead of leaving it in the previous one.
  const { locale } = useTranslation();
  const { readingLanguage } = useUserPreferences();
  const {
    isSubscribed,
    entitlementStatus,
    isLoading: isEntitlementLoading,
    refreshEntitlements,
  } = usePurchases();
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [trialTierName, setTrialTierName] = useState<string | null>(null);
  const router = useRouter();

  // The entitlement payload says a trial is running but not which tier it
  // grants: the trial's terms live in the pricing config, served by the public
  // `GET /api/pricing`. Fetched only for a trial — a subscriber's tier is on the
  // payload already — and silent on failure, since the card names the trial with
  // or without it. The name is gated on `isFreeTrial` where it is passed down
  // rather than cleared here, so a trial that ends cannot leave its tier behind.
  const isFreeTrial = entitlementStatus?.is_free_trial === true;
  useEffect(() => {
    if (!isFreeTrial) return;
    let isCurrent = true;
    void fetchPublicPricing()
      .then((pricing) => {
        if (!isCurrent) return;
        const trialTierId = pricing.free_trial?.enabled
          ? pricing.free_trial.tier
          : null;
        const tier = pricing.tiers.find((entry) => entry.id === trialTierId);
        setTrialTierName(tier?.name ?? null);
      })
      .catch(() => {
        if (isCurrent) setTrialTierName(null);
      });
    return () => {
      isCurrent = false;
    };
  }, [isFreeTrial]);

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
    ? t("account.subscription.manage")
    : isSubscriptionStateUnknown
      ? t("account.subscription.viewPlans")
      : t("account.subscription.upgrade");
  const subscriptionSubtitle = isSubscribed
    ? t("account.subscription.manageHint")
    : isSubscriptionStateUnknown
      ? t("account.subscription.viewPlansHint")
      : t("account.subscription.upgradeHint");

  // Get display label for current reading language
  const readingLanguageLabel =
    V1_READING_LANGUAGES.find((l) => l.code === readingLanguage)?.label ??
    t("account.notSet");

  const handleBugReport = () => {
    router.push("/bug-report");
  };

  const handleLogout = () => {
    // The confirmation label is unique app-wide: "Sign Out" alone also matches
    // the menu item and the alert title, which makes the tap ambiguous on iOS.
    Alert.alert(t("account.signOut"), t("account.signOutConfirm"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("account.signOutAction"),
        style: "destructive",
        onPress: () => logout(),
      },
    ]);
  };

  const openFeedbackFallback = async (): Promise<void> => {
    const fallbackUrl = FeedbackService.getFallbackUrl();
    if (!fallbackUrl) {
      Alert.alert(
        t("account.feedbackUnavailable"),
        t("account.feedbackUnavailableBody"),
      );
      return;
    }
    await WebBrowser.openBrowserAsync(fallbackUrl);
  };

  const handleFeedback = async () => {
    setIsFeedbackLoading(true);
    try {
      if (isAuthenticated) {
        const url = await FeedbackService.getFeedbackUrl();
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
        <Text style={styles.title}>{t("account.title")}</Text>
      </View>

      {/* `contentInsetAdjustmentBehavior` is set by hand, not left to
          `NativeTabs`. The tab bar insets the screen's scroll view itself, but
          only the one it can find: react-native-screens walks the first-subview
          chain down from the screen
          (`RNSScrollViewFinder.findScrollViewInFirstDescendantChainFrom`) and
          flips the first `UIScrollView` it meets from `never` to `automatic`
          (`RNSScrollViewHelper`). The header above is the screen root's first
          child, so that walk dead-ends in a `Text` and this list would never be
          inset for the floating bar. `automatic` is the very value the native
          helper would have set, so the last row clears the glass. */}
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
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
          trialTierName={isFreeTrial ? trialTierName : null}
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
            label={t("readingLanguage.title")}
            subtitle={readingLanguageLabel}
            onPress={() => router.push("/settings/reading-language")}
          />
          {/* The interface language, a separate axis from the reading language
              above: this one never leaves the device, the other one travels to
              the backend and decides what the summaries are written in. It took
              the slot of an inert "Settings" row that navigated nowhere. */}
          <MenuItem
            icon="globe-outline"
            label={t("uiLanguage.title")}
            subtitle={LOCALE_ENDONYMS[locale]}
            onPress={() => router.push("/settings/interface-language")}
          />
          <MenuItem
            icon="bulb-outline"
            label={t("account.featureRequests")}
            onPress={handleFeedback}
            isLoading={isFeedbackLoading}
          />
          <MenuItem
            icon="bug-outline"
            label={t("account.reportBug")}
            onPress={handleBugReport}
          />
          <View style={styles.menuDivider} />
          <TouchableOpacity
            testID="account-sign-out-button"
            style={styles.menuItem}
            onPress={handleLogout}
            activeOpacity={0.7}
            accessibilityLabel={t("account.signOut")}
            accessibilityRole="button"
          >
            <View style={[styles.menuIcon, styles.menuIconDanger]}>
              <Ionicons name="log-out-outline" size={18} color={Colors.error} />
            </View>
            <Text
              style={[styles.menuLabel, styles.menuLabelDanger, { flex: 1 }]}
            >
              {t("account.signOut")}
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
            accessibilityLabel={t("deleteAccount.title")}
            accessibilityRole="button"
          >
            <View style={[styles.menuIcon, styles.menuIconDanger]}>
              <Ionicons name="trash-outline" size={18} color={Colors.error} />
            </View>
            <Text
              style={[styles.menuLabel, styles.menuLabelDanger, { flex: 1 }]}
            >
              {t("deleteAccount.title")}
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
    marginEnd: Spacing.sm + 4,
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
    marginEnd: Spacing.sm + 4,
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
    marginStart: Spacing.sm,
  },
  menuDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: Colors.outlineVariant,
    marginHorizontal: Spacing.md,
  },
});
