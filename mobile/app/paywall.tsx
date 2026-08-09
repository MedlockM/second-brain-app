/**
 * Paywall screen showing the 3 subscription tiers with native purchase buttons.
 *
 * Displays RevenueCat offerings and handles the purchase flow including
 * success, cancellation, pending (Ask to Buy), and error states.
 */
import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { PurchasesOfferings, PurchasesPackage } from "react-native-purchases";
import {
  getOfferings,
  purchasePackage,
  restorePurchases,
} from "../src/services/purchaseService";
import { usePurchases } from "../src/contexts/PurchasesContext";
import { Colors, Typography, Spacing, BorderRadius, TouchTarget } from "../src/constants/theme";

// Tier display metadata (fallback when offerings not loaded yet)
const TIER_INFO = [
  {
    identifier: "text_only",
    name: "Reader",
    price: "3 EUR/mo",
    minutes: "0 min audio",
    highlight: false,
    features: [
      "Unlimited articles & web content",
      "PDF & document processing",
      "YouTube with captions",
      "Flashcards, notes & summaries",
    ],
  },
  {
    identifier: "mix",
    name: "Mix",
    price: "5 EUR/mo",
    minutes: "300 min audio (5h)",
    highlight: true,
    features: [
      "Everything in Reader",
      "5h podcast transcription/month",
      "Podcast import & processing",
      "Audio file uploads",
    ],
  },
  {
    identifier: "audio_heavy",
    name: "Audio-Heavy",
    price: "9 EUR/mo",
    minutes: "900 min audio (15h)",
    highlight: false,
    features: [
      "Everything in Mix",
      "15h podcast transcription/month",
      "Priority processing",
      "Higher daily import limits",
    ],
  },
];

export default function PaywallScreen() {
  const router = useRouter();
  const { refreshEntitlements } = usePurchases();
  const [offerings, setOfferings] = useState<PurchasesOfferings | null>(null);
  const [isLoadingOfferings, setIsLoadingOfferings] = useState(true);
  const [isPurchasing, setIsPurchasing] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  useEffect(() => {
    const loadOfferings = async () => {
      setIsLoadingOfferings(true);
      const result = await getOfferings();
      setOfferings(result);
      setIsLoadingOfferings(false);
    };
    loadOfferings();
  }, []);

  const handlePurchase = async (pkg: PurchasesPackage) => {
    setIsPurchasing(true);
    try {
      const result = await purchasePackage(pkg);

      switch (result.status) {
        case "success":
          // Refresh entitlements from backend
          await refreshEntitlements();
          Alert.alert(
            "Purchase Successful",
            "Your subscription is now active. Enjoy!",
            [{ text: "OK", onPress: () => router.back() }],
          );
          break;
        case "cancelled":
          // User cancelled, do nothing
          break;
        case "pending":
          Alert.alert(
            "Purchase Pending",
            "Your purchase is awaiting approval. You will be notified when it is complete.",
          );
          break;
        case "error":
          Alert.alert("Purchase Failed", result.message);
          break;
      }
    } catch (error: any) {
      Alert.alert("Error", "An unexpected error occurred. Please try again.");
    } finally {
      setIsPurchasing(false);
    }
  };

  const handleRestore = async () => {
    setIsRestoring(true);
    try {
      await restorePurchases();
      await refreshEntitlements();
      Alert.alert(
        "Purchases Restored",
        "Your previous purchases have been restored.",
        [{ text: "OK", onPress: () => router.back() }],
      );
    } catch (error: any) {
      Alert.alert(
        "Restore Failed",
        "Could not restore purchases. Please try again later.",
      );
    } finally {
      setIsRestoring(false);
    }
  };

  // Get packages from the default offering
  const packages = offerings?.current?.availablePackages ?? [];

  // Map packages to tier info for display
  const getTierPackage = (tierIdentifier: string): PurchasesPackage | undefined => {
    return packages.find(
      (pkg) =>
        pkg.identifier.toLowerCase().includes(tierIdentifier) ||
        pkg.product.identifier.toLowerCase().includes(tierIdentifier),
    );
  };

  return (
    <View style={styles.container} testID="paywall-screen">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          testID="paywall-close-button"
          onPress={() => router.back()}
          style={styles.closeButton}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Text style={styles.closeText}>Close</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Choose Your Plan</Text>
        <Text style={styles.subtitle}>
          Unlock the full power of your second brain
        </Text>
      </View>

      {/* Tier Cards */}
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {isLoadingOfferings ? (
          <ActivityIndicator
            size="large"
            color={Colors.primary}
            style={styles.loader}
          />
        ) : (
          TIER_INFO.map((tier) => {
            const pkg = getTierPackage(tier.identifier);
            const priceLabel = pkg
              ? pkg.product.priceString + "/mo"
              : tier.price;

            return (
              <View
                key={tier.identifier}
                testID={`paywall-tier-${tier.identifier}`}
                style={[
                  styles.tierCard,
                  tier.highlight && styles.tierCardHighlight,
                ]}
              >
                {tier.highlight && (
                  <View style={styles.popularBadge}>
                    <Text style={styles.popularText}>Most Popular</Text>
                  </View>
                )}

                <Text style={styles.tierName}>{tier.name}</Text>
                <Text style={styles.tierPrice}>{priceLabel}</Text>
                <Text style={styles.tierMinutes}>{tier.minutes}</Text>

                <View style={styles.featureList}>
                  {tier.features.map((feature, idx) => (
                    <View key={idx} style={styles.featureRow}>
                      <Text style={styles.featureCheck}>+</Text>
                      <Text style={styles.featureText}>{feature}</Text>
                    </View>
                  ))}
                </View>

                <TouchableOpacity
                  style={[
                    styles.purchaseButton,
                    tier.highlight && styles.purchaseButtonHighlight,
                    (isPurchasing || !pkg) && styles.purchaseButtonDisabled,
                  ]}
                  onPress={() => pkg && handlePurchase(pkg)}
                  disabled={isPurchasing || !pkg}
                >
                  {isPurchasing ? (
                    <ActivityIndicator size="small" color={Colors.onPrimary} />
                  ) : (
                    <Text
                      style={[
                        styles.purchaseButtonText,
                        tier.highlight && styles.purchaseButtonTextHighlight,
                      ]}
                    >
                      {pkg ? "Subscribe" : "Unavailable"}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            );
          })
        )}

        {/* Restore Purchases */}
        <TouchableOpacity
          style={styles.restoreButton}
          onPress={handleRestore}
          disabled={isRestoring}
        >
          {isRestoring ? (
            <ActivityIndicator size="small" color={Colors.textMuted} />
          ) : (
            <Text style={styles.restoreText}>Restore Purchases</Text>
          )}
        </TouchableOpacity>

        {/* Legal text */}
        <Text style={styles.legalText}>
          {Platform.OS === "ios"
            ? "Payment will be charged to your Apple ID account at the confirmation of purchase. " +
              "Subscription automatically renews unless it is canceled at least 24 hours before " +
              "the end of the current period. Your account will be charged for renewal within " +
              "24 hours prior to the end of the current period."
            : "Payment will be charged to your Google Play account at the confirmation of purchase. " +
              "Subscription automatically renews unless it is canceled at least 24 hours before " +
              "the end of the current period."}
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingTop: Spacing.xl,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
    alignItems: "center",
  },
  closeButton: {
    position: "absolute",
    top: Spacing.md,
    right: Spacing.lg,
    minHeight: TouchTarget.minimum,
    minWidth: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  closeText: {
    ...Typography.label,
    color: Colors.textMuted,
  },
  title: {
    ...Typography.display,
    color: Colors.textMain,
    marginTop: Spacing.md,
  },
  subtitle: {
    ...Typography.body,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
    textAlign: "center",
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  loader: {
    marginTop: Spacing.xxl,
  },
  tierCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    marginTop: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
  },
  tierCardHighlight: {
    borderColor: Colors.primary,
    borderWidth: 2,
  },
  popularBadge: {
    position: "absolute",
    top: -12,
    alignSelf: "center",
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
  },
  popularText: {
    ...Typography.small,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
  tierName: {
    ...Typography.headline,
    color: Colors.textMain,
    marginTop: Spacing.xs,
  },
  tierPrice: {
    ...Typography.display,
    color: Colors.textMain,
    marginTop: Spacing.xs,
  },
  tierMinutes: {
    ...Typography.label,
    color: Colors.textMuted,
    marginTop: Spacing.xs,
  },
  featureList: {
    marginTop: Spacing.md,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: Spacing.xs,
  },
  featureCheck: {
    ...Typography.body,
    color: Colors.primary,
    fontWeight: "700",
    marginRight: Spacing.sm,
    width: 16,
  },
  featureText: {
    ...Typography.body,
    color: Colors.textMain,
    flex: 1,
  },
  purchaseButton: {
    marginTop: Spacing.md,
    backgroundColor: Colors.surfaceContainer,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.md,
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.comfortable,
  },
  purchaseButtonHighlight: {
    backgroundColor: Colors.primary,
  },
  purchaseButtonDisabled: {
    opacity: 0.5,
  },
  purchaseButtonText: {
    ...Typography.label,
    color: Colors.textMain,
    fontWeight: "600",
  },
  purchaseButtonTextHighlight: {
    color: Colors.onPrimary,
    fontWeight: "700",
  },
  restoreButton: {
    marginTop: Spacing.lg,
    alignItems: "center",
    paddingVertical: Spacing.md,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
  },
  restoreText: {
    ...Typography.label,
    color: Colors.textMuted,
    textDecorationLine: "underline",
  },
  legalText: {
    ...Typography.small,
    color: Colors.textMuted,
    textAlign: "center",
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
    lineHeight: 18,
  },
});
