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
import { Ionicons } from "@expo/vector-icons";
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
  buildPlanHighlights,
  buildPlanIncludes,
} from "../src/lib/planCopy";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../src/constants/theme";

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
  // Which plan the CTA buys. `null` until the pricing lands, then the tier the
  // free trial grants — the one the user is already living in, so the default is
  // "keep what you have" rather than a guess at what they can afford.
  const [selectedTierId, setSelectedTierId] = useState<string | null>(null);
  // The exhaustive list is one tap away, never in the way.
  const [isDetailOpen, setIsDetailOpen] = useState(false);
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
  const highlights = buildPlanHighlights();
  const isInTrial = entitlementStatus?.is_free_trial === true;

  // The selection defaults to the trial's tier, and falls back to the first card
  // when the config marks none — the CTA must always have something to buy.
  const defaultTierId =
    planCards.find((card) => card.isTrialTier)?.id ?? planCards[0]?.id ?? null;
  const activeTierId =
    selectedTierId !== null &&
    planCards.some((card) => card.id === selectedTierId)
      ? selectedTierId
      : defaultTierId;
  const selectedCard =
    planCards.find((card) => card.id === activeTierId) ?? null;
  const selectedPackage =
    selectedCard === null ? undefined : getTierPackage(selectedCard.id);
  // The store's own price string when it is loaded, the configured one as a
  // stand-in, and no price at all rather than a made-up one.
  const selectedPrice = selectedPackage
    ? `${selectedPackage.product.priceString}/mo`
    : (selectedCard?.configuredPrice ?? null);
  const ctaLabel =
    selectedPackage && selectedCard
      ? selectedPrice === null
        ? `Start with ${selectedCard.name}`
        : `Start with ${selectedCard.name} — ${selectedPrice}`
      : "Unavailable";

  // Without the top inset the Close button sits at y=16..64, underneath the
  // Dynamic Island, where the system swallows the tap: unreachable on any recent
  // iPhone. Every other screen already insets the same way.
  return (
    // The bottom inset comes with the sticky footer: without it the CTA sits
    // under the home indicator on any recent iPhone.
    <SafeAreaView
      style={styles.container}
      edges={["top", "bottom"]}
      testID="paywall-screen"
    >
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
          Everything the app does is in every plan. What changes is how much we
          transcribe for you.
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

            {/* What every plan does, above the prices: the four lines almost
                everyone reads, in the order a newcomer meets the product. The
                exhaustive version is one tap below, not in the way. */}
            <View testID="paywall-highlights" style={styles.highlightBlock}>
              {highlights.map((highlight) => (
                <View
                  key={highlight.id}
                  testID={`paywall-highlight-${highlight.id}`}
                  style={styles.highlightRow}
                >
                  <Ionicons
                    name="checkmark-circle"
                    size={20}
                    color={Colors.primary}
                  />
                  <Text style={styles.highlightText}>{highlight.text}</Text>
                </View>
              ))}

              <TouchableOpacity
                testID="paywall-includes-toggle"
                style={styles.detailToggle}
                onPress={() => setIsDetailOpen((open) => !open)}
                accessibilityRole="button"
                accessibilityState={{ expanded: isDetailOpen }}
              >
                <Text style={styles.detailToggleText}>
                  {isDetailOpen ? "Hide the details" : "See exactly what is included"}
                </Text>
                <Ionicons
                  name={isDetailOpen ? "chevron-up" : "chevron-down"}
                  size={16}
                  color={Colors.textMain}
                />
              </TouchableOpacity>

              {isDetailOpen && (
                <View testID="paywall-includes">
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
              )}
            </View>

            {/* The only thing left to decide, named as such. */}
            <Text style={styles.selectorLabel}>
              Pick how much we transcribe for you
            </Text>

            {planCards.map((card) => {
              const pkg = getTierPackage(card.id);
              const priceLabel = pkg
                ? pkg.product.priceString + "/mo"
                : card.configuredPrice;
              const isSelected = card.id === activeTierId;

              return (
                <TouchableOpacity
                  key={card.id}
                  testID={`paywall-tier-${card.id}`}
                  style={[styles.tierCard, isSelected && styles.tierCardSelected]}
                  onPress={() => setSelectedTierId(card.id)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: isSelected }}
                  accessibilityLabel={`${card.name}, ${priceLabel ?? "price unavailable"}`}
                >
                  <View style={styles.tierRadioColumn}>
                    <Ionicons
                      name={isSelected ? "radio-button-on" : "radio-button-off"}
                      size={22}
                      color={isSelected ? Colors.textMain : Colors.outlineVariant}
                    />
                  </View>

                  <View style={styles.tierBody}>
                    <View style={styles.tierTitleRow}>
                      <Text style={styles.tierName}>{card.name}</Text>
                      {/* Only true for someone the backend reports as being in
                          the trial. The tier is still the default selection for
                          everyone else, but a badge claiming a trial they never
                          had would be a lie, and "popular" is a claim we cannot
                          make with no users. */}
                      {card.isTrialTier && isInTrial && (
                        <View style={styles.tierBadge}>
                          <Text style={styles.tierBadgeText}>YOUR TRIAL TIER</Text>
                        </View>
                      )}
                    </View>

                    {card.allowance !== null && (
                      <Text style={styles.tierFigure}>{card.allowance}</Text>
                    )}
                    {card.perImportLimit !== null && (
                      <Text style={styles.tierFigureMuted}>
                        {card.perImportLimit}
                      </Text>
                    )}
                    {!pkg && (
                      <Text style={styles.tierUnavailable}>Unavailable</Text>
                    )}
                  </View>

                  {priceLabel !== null && (
                    <Text style={styles.tierPrice}>{priceLabel}</Text>
                  )}
                </TouchableOpacity>
              );
            })}

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

      {/* One CTA, in a footer that never scrolls away, naming what it buys and
          what it costs — per-card buttons turned the screen into three identical
          decisions, and a price only visible on a row that can be scrolled off
          is a price the stores consider hidden. */}
      {!isLoading && pricing !== null && (
        <View style={styles.footer}>
          <TouchableOpacity
            testID="paywall-subscribe-button"
            style={[
              styles.purchaseButton,
              (isPurchasing || !selectedPackage) && styles.purchaseButtonDisabled,
            ]}
            onPress={() => selectedPackage && handlePurchase(selectedPackage)}
            disabled={isPurchasing || !selectedPackage}
            accessibilityRole="button"
            accessibilityLabel={ctaLabel}
          >
            {isPurchasing ? (
              <ActivityIndicator size="small" color={Colors.onPrimary} />
            ) : (
              <Text style={styles.purchaseButtonText}>{ctaLabel}</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
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
  // Selection lives in the fill, not a stroke: the design system asks for tonal
  // shifts over 1px borders for anything structural.
  tierCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    minHeight: TouchTarget.comfortable,
  },
  tierCardSelected: {
    backgroundColor: Colors.highlight,
  },
  tierRadioColumn: {
    justifyContent: "center",
  },
  tierBody: {
    flex: 1,
  },
  tierTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  tierName: {
    ...Typography.headline,
    color: Colors.textMain,
  },
  tierBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  tierBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
    color: Colors.textMain,
  },
  tierFigure: {
    ...Typography.label,
    color: Colors.textMain,
    marginTop: Spacing.xs,
  },
  tierFigureMuted: {
    ...Typography.small,
    color: Colors.textMuted,
  },
  tierUnavailable: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.error,
    marginTop: Spacing.xs,
  },
  tierPrice: {
    ...Typography.headline,
    color: Colors.textMain,
    textAlign: "right",
  },
  selectorLabel: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    marginTop: Spacing.lg,
  },
  highlightBlock: {
    marginTop: Spacing.md,
    padding: Spacing.md,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surface,
    ...Shadows.soft,
  },
  highlightRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  highlightText: {
    ...Typography.small,
    flex: 1,
    color: Colors.textMain,
    lineHeight: 18,
  },
  detailToggle: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.xs,
    minHeight: TouchTarget.minimum,
  },
  detailToggleText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    textDecorationLine: "underline",
  },
  // Sits on the background rather than floating: the design system asks for
  // tonal separation over strokes, and a shadow here would fight the card above.
  footer: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
    backgroundColor: Colors.background,
  },
  purchaseButton: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.md,
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.comfortable,
  },
  purchaseButtonDisabled: {
    opacity: 0.5,
  },
  purchaseButtonText: {
    ...Typography.headline,
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
