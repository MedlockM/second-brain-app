/**
 * Paywall screen showing the subscription tiers with native purchase buttons.
 *
 * Displays RevenueCat offerings and handles the purchase flow including
 * success, cancellation, pending (Ask to Buy), and error states.
 *
 * **Where the figures come from.** Nothing about a plan is written in this file.
 * The tiers, their allowances, their per-import ceilings and the trial terms are
 * fetched from `GET /api/pricing` — the backend pricing config itself — and
 * turned into sentences by `src/lib/planCopy.ts`; prices come from the store
 * package. Until task-299 the same numbers lived here, in `entitlements.py` and
 * in the config at once, and this screen was the copy that had gone stale: it
 * advertised documents and collection-wide generations as unlimited when both
 * debit minutes, and never mentioned that the longest single import a plan
 * accepts differs per tier, or that a server-side trial was already running.
 * The tiers are *not* feature-identical, and no comment here should say so
 * again — nor should any figure be quoted here, not even in prose.
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
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { PurchasesOfferings, PurchasesPackage } from "react-native-purchases";
import {
  getOfferings,
  purchasePackage,
  restorePurchases,
} from "../src/services/purchaseService";
import { usePurchases } from "../src/contexts/PurchasesContext";
import {
  fetchPublicPricing,
  type PublicPricing,
} from "../src/services/pricingService";
import {
  buildFreeTrialLine,
  buildPlanCards,
  buildPlanIncludes,
} from "../src/lib/planCopy";
import { Colors, Typography, Spacing, BorderRadius, TouchTarget } from "../src/constants/theme";

export default function PaywallScreen() {
  const router = useRouter();
  const { refreshEntitlements, entitlementStatus } = usePurchases();
  // Pushed from the Account tab or from a quota refusal, back returns to the
  // caller. Reached by deep link (media-summarizer://paywall) there is no screen
  // underneath, and router.back() is a no-op that traps the user on the paywall,
  // so fall back to the inbox.
  const dismiss = () => {
    if (router.canGoBack()) {
      router.back();
      return;
    }
    router.replace("/(tabs)");
  };
  const [offerings, setOfferings] = useState<PurchasesOfferings | null>(null);
  const [pricing, setPricing] = useState<PublicPricing | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPurchasing, setIsPurchasing] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  // Bumped by the retry button; the load lives in the effect and this is what
  // re-runs it, so there is one loading path rather than two.
  const [reloadToken, setReloadToken] = useState(0);

  // The store and the backend are asked at the same time and awaited together:
  // a card is only ever rendered once both its price and its figures exist, so
  // no tier is ever shown with an allowance the config no longer holds.
  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      const [storeOfferings, publicPricing] = await Promise.all([
        getOfferings(),
        fetchPublicPricing().catch((error: unknown) => {
          console.error("[Paywall] Failed to load pricing:", error);
          return null;
        }),
      ]);
      setOfferings(storeOfferings);
      setPricing(publicPricing);
      setIsLoading(false);
    };
    load();
  }, [reloadToken]);

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
            [{ text: "OK", onPress: () => dismiss() }],
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
        [{ text: "OK", onPress: () => dismiss() }],
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

  const planCards = pricing === null ? [] : buildPlanCards(pricing);
  const trialLine = buildFreeTrialLine(pricing, entitlementStatus);

  // Without the top inset the Close button sits at y=16..64, underneath the
  // Dynamic Island, where the system swallows the tap: unreachable on any recent
  // iPhone. Every other screen already insets the same way.
  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="paywall-screen">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          testID="paywall-close-button"
          onPress={() => dismiss()}
          style={styles.closeButton}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <Text style={styles.closeText}>Close</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Choose Your Plan</Text>
        {/* Two sentences, two jobs: what the app does at all — which the cards
            never said, and which nobody arriving from a store listing knows —
            then what separates the tiers. Neither restates a card's figures. */}
        <Text style={styles.tagline}>
          Save any video, podcast, article or document, get it back as text, and
          turn it into summaries, notes and flashcards you keep.
        </Text>
        <Text style={styles.subtitle}>
          Plans differ only by how much we transcribe for you — everything below
          is in all of them.
        </Text>
      </View>

      {/* Tier Cards */}
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <ActivityIndicator
            size="large"
            color={Colors.primary}
            style={styles.loader}
          />
        ) : pricing === null ? (
          // No figures, no cards: a plan described from numbers baked into the
          // build is exactly the drift this screen was rewritten to end.
          <View testID="paywall-pricing-error" style={styles.errorBox}>
            <Text style={styles.errorText}>
              We could not load the plans. Check your connection and try again.
            </Text>
            <TouchableOpacity
              testID="paywall-retry-button"
              style={styles.retryButton}
              onPress={() => setReloadToken((token) => token + 1)}
            >
              <Text style={styles.retryButtonText}>Try again</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Live state, not a standing offer: only a caller the backend
                reports as being in the trial window ever reads this. */}
            {trialLine !== null && (
              <Text testID="paywall-trial-note" style={styles.trialNote}>
                {trialLine}
              </Text>
            )}

            {planCards.map((card) => {
              const pkg = getTierPackage(card.id);
              const priceLabel = pkg
                ? pkg.product.priceString + "/mo"
                : card.configuredPrice;

              return (
                <View
                  key={card.id}
                  testID={`paywall-tier-${card.id}`}
                  style={[
                    styles.tierCard,
                    card.isTrialTier && styles.tierCardHighlight,
                  ]}
                >
                  <Text style={styles.tierName}>{card.name}</Text>
                  {priceLabel !== null && (
                    <Text style={styles.tierPrice}>{priceLabel}</Text>
                  )}

                  <View style={styles.featureList}>
                    {card.allowance !== null && (
                      <Text style={styles.featureText}>{card.allowance}</Text>
                    )}
                    {card.perImportLimit !== null && (
                      <Text style={styles.featureText}>
                        {card.perImportLimit}
                      </Text>
                    )}
                  </View>

                  <TouchableOpacity
                    style={[
                      styles.purchaseButton,
                      card.isTrialTier && styles.purchaseButtonHighlight,
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
                          card.isTrialTier && styles.purchaseButtonTextHighlight,
                        ]}
                      >
                        {pkg ? "Subscribe" : "Unavailable"}
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>
              );
            })}

            {/* What every plan does, once, under the cards: none of it varies
                by tier, and a reader who has never used the app cannot judge
                three allowances without it. */}
            <View testID="paywall-includes" style={styles.includesBlock}>
              <Text style={styles.includesHeading}>Included in every plan</Text>
              {buildPlanIncludes(pricing).map((section) => (
                <View
                  key={section.id}
                  testID={`paywall-includes-${section.id}`}
                  style={styles.includesSection}
                >
                  <Text style={styles.includesTitle}>{section.title}</Text>
                  {section.items.map((item, index) => (
                    <View key={index} style={styles.includesRow}>
                      <Text style={styles.includesBullet}>•</Text>
                      <Text style={styles.includesItem}>{item}</Text>
                    </View>
                  ))}
                </View>
              ))}
            </View>
          </>
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
    </SafeAreaView>
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
  tagline: {
    ...Typography.body,
    color: Colors.textMain,
    marginTop: Spacing.sm,
    textAlign: "center",
  },
  subtitle: {
    ...Typography.small,
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
  errorBox: {
    marginTop: Spacing.xl,
    padding: Spacing.lg,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surface,
    alignItems: "center",
  },
  errorText: {
    ...Typography.body,
    color: Colors.textMain,
    textAlign: "center",
  },
  retryButton: {
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.lg,
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainer,
  },
  retryButtonText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
  },
  trialNote: {
    ...Typography.small,
    color: Colors.textMain,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginTop: Spacing.md,
    lineHeight: 18,
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
  featureList: {
    marginTop: Spacing.md,
    gap: Spacing.xs,
  },
  featureText: {
    ...Typography.body,
    color: Colors.textMain,
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
  includesBlock: {
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surfaceContainerLow,
  },
  includesHeading: {
    ...Typography.label,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  includesSection: {
    marginTop: Spacing.md,
  },
  includesTitle: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    marginBottom: Spacing.xs,
  },
  // Bullet in its own column so a wrapped sentence keeps its left edge under
  // the first word rather than under the dot.
  includesRow: {
    flexDirection: "row",
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  includesBullet: {
    ...Typography.small,
    color: Colors.textMuted,
    lineHeight: 18,
  },
  includesItem: {
    ...Typography.small,
    flex: 1,
    color: Colors.textMuted,
    lineHeight: 18,
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
