/**
 * Paywall screen showing the subscription tiers with native purchase buttons.
 *
 * Displays RevenueCat offerings and handles the purchase flow including
 * success, cancellation, pending (Ask to Buy), and error states.
 *
 * **Where the figures come from.** Nothing about a plan is written in this file.
 * The tiers, their allowances, their per-import ceilings and the trial terms are
 * fetched from `GET /api/pricing` — the backend pricing config itself — and
 * turned into sentences by `src/lib/planCopy.ts`; **every price comes from the
 * store package and nowhere else**. Until task-299 the same numbers lived here,
 * in `entitlements.py` and in the config at once, and this screen was the copy
 * that had gone stale. The tiers are *not* feature-identical, and no comment here
 * should say so again — nor should any figure be quoted here, not even in prose.
 *
 * **What the screen puts first.** The plans. An earlier version opened with a
 * tagline, a sub-tagline and four benefit lines — roughly 600px of argument —
 * so on a 6.1" phone the first price was below the fold and on a 4.7" one no
 * card was on screen at all. A purchase screen that hides its prices until you
 * scroll is arguing with someone who has already decided to look. The order is
 * now: one short promise, the refusal you are standing in (if any), the three
 * plans, the one rule that qualifies what their allowance meters, then what every
 * plan includes as the supporting evidence. The benefit lines still exist, below
 * the cards, where they answer a question rather than delay one.
 *
 * **What the screen may claim.** Only checkable facts. The recommended plan is
 * derived from minutes the account actually spent, "best value" is arithmetic on
 * the store's own prices, and there is no "most popular" badge because with no
 * users that would simply be false. See `buildPlanGuidance`.
 *
 * **There is no Restore Purchases button**, and adding one back would be a
 * regression (task-336). The subscription follows the *app account*, not the
 * store account: `identifyUser()` logs the user in to RevenueCat under their own
 * id, and access is read from `GET /api/entitlements/status`, so a reinstall or a
 * new device recovers it by signing in. The button could only ever restore what
 * the account already had — and it read its verdict from RevenueCat while the
 * paywall reads the backend, so it could announce "Purchases restored" on a
 * screen that then refused to close.
 */
import React, { useEffect, useState } from "react";
import {
  I18nManager,
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { PurchasesPackage } from "react-native-purchases";
import { getOfferings, purchasePackage } from "../src/services/purchaseService";
import { usePurchases } from "../src/contexts/PurchasesContext";
import {
  fetchPublicPricing,
  type PublicPricing,
} from "../src/services/pricingService";
import {
  buildFreeTrialLine,
  buildHourlyRate,
  buildPaywallReasonLine,
  buildPlanCards,
  buildPlanGuidance,
  buildPlanHighlights,
  buildPlanIncludes,
  minutesRule,
  type PaywallReason,
  type PlanCard,
} from "../src/lib/planCopy";
import {
  PRIVACY_POLICY_URL,
  STORE_NAME,
  TERMS_URL,
} from "../src/constants/legal";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../src/constants/theme";
import { t, useTranslation } from "../src/i18n";

export default function PaywallScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const { refreshEntitlements, entitlementStatus } = usePurchases();
  // Why the caller opened the paywall, when they know. The screen is reached
  // from the Account tab, the usage banner and a submission the backend just
  // refused, and looked identical from all three.
  const params = useLocalSearchParams<{ reason?: string }>();
  const reason: PaywallReason | null =
    params.reason === "out_of_minutes" || params.reason === "running_low"
      ? params.reason
      : null;
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
  const [cards, setCards] = useState<PlanCard[]>([]);
  const [packageByTier, setPackageByTier] = useState<
    Record<string, PurchasesPackage>
  >({});
  const [pricing, setPricing] = useState<PublicPricing | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPurchasing, setIsPurchasing] = useState(false);
  // Which plan the CTA buys. `null` until the pricing lands, then whatever the
  // guidance recommends — the user can always pick another.
  const [selectedTierId, setSelectedTierId] = useState<string | null>(null);
  // The exhaustive list is one tap away, never in the way.
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  // Bumped by the retry button; the load lives in the effect and this is what
  // re-runs it, so there is one loading path rather than two.
  const [reloadToken, setReloadToken] = useState(0);

  // The store and the backend are asked at the same time and awaited together,
  // then matched up. They fail independently and the screen treats them that
  // way: the backend owns what a plan *is*, the store owns what it *costs*.
  //
  // Losing the backend leaves nothing to describe, so that is the error state.
  // Losing the store only loses the prices — and the app cannot invent one, since
  // the config holds a single EUR figure while the store bills per storefront. So
  // the plans are still described, and buying is switched off until the store
  // answers. Collapsing both into one error was wrong twice over: it blamed the
  // connection for a store problem, and it hid a perfectly loaded plan list
  // behind a dead end.
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

      const packages = storeOfferings?.current?.availablePackages ?? [];
      const planCards =
        publicPricing === null ? [] : buildPlanCards(publicPricing);
      const matched: Record<string, PurchasesPackage> = {};
      for (const card of planCards) {
        const pkg = packages.find(
          (candidate) =>
            candidate.identifier.toLowerCase().includes(card.id) ||
            candidate.product.identifier.toLowerCase().includes(card.id),
        );
        if (pkg !== undefined) matched[card.id] = pkg;
      }

      // Nothing to sell is a configuration fact worth naming in the log, and the
      // two causes need different fixes: zero packages means the SDK is not
      // configured or the offering is empty, while packages whose identifiers do
      // not contain a tier id means the store products are named something the
      // pricing config does not know.
      if (planCards.length > 0 && Object.keys(matched).length === 0) {
        console.warn(
          "[Paywall] No purchasable tier. Store returned",
          packages.length,
          "package(s):",
          packages.map((pkg) => pkg.product.identifier),
          "— configured tiers:",
          planCards.map((card) => card.id),
        );
      }

      setPricing(publicPricing);
      setCards(planCards);
      setPackageByTier(matched);
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
            t("paywall.purchaseSuccess"),
            t("paywall.purchaseSuccessBody"),
            [{ text: t("common.ok"), onPress: () => dismiss() }],
          );
          break;
        case "cancelled":
          // User cancelled, do nothing
          break;
        case "pending":
          Alert.alert(
            t("paywall.purchasePending"),
            t("paywall.purchasePendingBody"),
          );
          break;
        case "error":
          Alert.alert(t("paywall.purchaseFailed"), result.message);
          break;
      }
    } catch {
      Alert.alert(t("common.error"), t("paywall.unexpectedError"));
    } finally {
      setIsPurchasing(false);
    }
  };

  const trialLine = buildFreeTrialLine(pricing, entitlementStatus);
  const reasonLine = buildPaywallReasonLine(reason, entitlementStatus);
  const highlights = buildPlanHighlights();

  // Three states, not two. `hasPlans` is about the backend: with no figures
  // there is nothing to put on screen. `canPurchase` is about the store: without
  // it the same plans are shown, priced at nothing and bought with nothing.
  const purchasableCards = cards.filter(
    (card) => packageByTier[card.id] !== undefined,
  );
  const hasPlans = cards.length > 0;
  const canPurchase = purchasableCards.length > 0;
  // A tier the store cannot sell is still worth describing, but it drops out of
  // the list as soon as its siblings *are* sellable — a row that cannot be
  // bought next to rows that can is just a dead end.
  const visibleCards = canPurchase ? purchasableCards : cards;

  const guidance = buildPlanGuidance(
    visibleCards,
    Object.fromEntries(
      purchasableCards.map((card) => [card.id, packageByTier[card.id].product.price]),
    ),
    entitlementStatus,
  );

  const defaultTierId = guidance.recommendedTierId ?? visibleCards[0]?.id ?? null;
  const activeTierId =
    selectedTierId !== null &&
    visibleCards.some((card) => card.id === selectedTierId)
      ? selectedTierId
      : defaultTierId;
  const selectedCard =
    visibleCards.find((card) => card.id === activeTierId) ?? null;
  const selectedPackage =
    selectedCard === null ? undefined : packageByTier[selectedCard.id];
  const ctaLabel =
    selectedCard === null || selectedPackage === undefined
      ? t("paywall.ctaChoose")
      : t("paywall.ctaStart", {
          plan: selectedCard.name,
          price: selectedPackage.product.priceString,
        });

  return (
    // The bottom inset comes with the sticky footer: without it the CTA sits
    // under the home indicator on any recent iPhone. Without the top one the
    // Close button sits under the Dynamic Island, where the system swallows the
    // tap. Every other screen already insets the same way.
    <SafeAreaView
      style={styles.container}
      edges={["top", "bottom"]}
      testID="paywall-screen"
    >
      {/* Header. Deliberately two short lines: what the app does, and the one
          axis that separates the plans. Everything else it used to say is now
          below the cards, where it does not push the prices off screen. */}
      <View style={styles.header}>
        <TouchableOpacity
          testID="paywall-close-button"
          onPress={() => dismiss()}
          style={styles.closeButton}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          accessibilityRole="button"
          accessibilityLabel={t("common.close")}
        >
          <Text style={styles.closeText}>{t("common.close")}</Text>
        </TouchableOpacity>
        <Text style={styles.title}>{t("paywall.title")}</Text>
        <Text style={styles.tagline}>
          Save anything worth coming back to, read it as text, keep what it
          taught you.
        </Text>
        <Text style={styles.subtitle}>
          {t("paywall.subtitle")}
        </Text>
      </View>

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
        ) : !hasPlans ? (
          // The backend is the only source of what a plan is, so without it there
          // is nothing to describe. A plan described from numbers baked into the
          // build is exactly the drift this screen was rewritten to end.
          <View testID="paywall-pricing-error" style={styles.errorBox}>
            <Text style={styles.errorText}>{t("paywall.plansLoadFailed")}</Text>
            <TouchableOpacity
              testID="paywall-retry-button"
              style={styles.retryButton}
              onPress={() => setReloadToken((token) => token + 1)}
              accessibilityRole="button"
            >
              <Text style={styles.retryButtonText}>{t("paywall.tryAgain")}</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Prices come from the store or not at all. When the store has
                nothing to offer, saying "check your connection" blames the wrong
                thing — the plans loaded fine — and hiding them helps nobody. */}
            {!canPurchase && (
              <View testID="paywall-store-notice" style={styles.noticeBox}>
                <Ionicons
                  name="information-circle-outline"
                  size={20}
                  color={Colors.textMain}
                />
                <View style={styles.noticeBody}>
                  <Text style={styles.noticeText}>
                    {t("paywall.pricesUnavailable", { store: STORE_NAME })}
                  </Text>
                  <TouchableOpacity
                    testID="paywall-retry-button"
                    style={styles.noticeRetry}
                    onPress={() => setReloadToken((token) => token + 1)}
                    accessibilityRole="button"
                  >
                    <Text style={styles.noticeRetryText}>
                      {t("paywall.tryAgain")}
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* The refusal the user is standing in, restated before the prices:
                someone who arrives mid-import should not have to re-derive why
                they are looking at plans. */}
            {reasonLine !== null && (
              <View testID="paywall-reason" style={styles.reasonBox}>
                <Ionicons
                  name="timer-outline"
                  size={20}
                  color={Colors.textMain}
                />
                <Text style={styles.reasonText}>{reasonLine}</Text>
              </View>
            )}

            {/* Live state, not a standing offer: only a caller the backend
                reports as being in the trial window ever reads this. */}
            {trialLine !== null && (
              <Text testID="paywall-trial-note" style={styles.trialNote}>
                {trialLine}
              </Text>
            )}

            {/* The only thing left to decide, named as such — and, when the
                account has spent minutes we can reason from, why one card is
                already selected. A highlighted card with no stated reason is a
                nudge; a highlighted card that shows its arithmetic is advice. */}
            <Text style={styles.selectorLabel}>
              {canPurchase
                ? t("paywall.selectorLabel")
                : t("paywall.selectorLabelReadOnly")}
            </Text>
            {guidance.recommendationLine !== null && (
              <Text
                testID="paywall-recommendation"
                style={styles.recommendationText}
              >
                {guidance.recommendationLine}
              </Text>
            )}

            <View accessibilityRole={canPurchase ? "radiogroup" : undefined}>
              {visibleCards.map((card) => {
                const pkg = packageByTier[card.id];
                const isSelected = pkg !== undefined && card.id === activeTierId;
                const badge = guidance.badges[card.id] ?? null;
                // No package, no price, and therefore no hourly rate: both are
                // the store's to state. The allowance and the ceiling are the
                // backend's, so they stay.
                const hourlyRate =
                  pkg === undefined
                    ? null
                    : buildHourlyRate(
                        pkg.product.price,
                        pkg.product.currencyCode,
                        card.minutesPerMonth,
                      );
                const meta = [hourlyRate, card.perImportLimit]
                  .filter((part): part is string => part !== null)
                  .join(" · ");

                return (
                  <TouchableOpacity
                    key={card.id}
                    testID={`paywall-tier-${card.id}`}
                    style={[
                      styles.tierCard,
                      isSelected && styles.tierCardSelected,
                    ]}
                    onPress={() => setSelectedTierId(card.id)}
                    disabled={pkg === undefined}
                    accessibilityRole={pkg === undefined ? "text" : "radio"}
                    accessibilityState={
                      pkg === undefined ? undefined : { selected: isSelected }
                    }
                    // Everything that distinguishes the plans, not just the name
                    // and the price: the allowance and the ceiling *are* the
                    // decision, and a screen reader used to get neither.
                    accessibilityLabel={[
                      card.name,
                      pkg === undefined
                        ? t("paywall.priceUnavailableA11y")
                        : t("paywall.pricePerMonthA11y", {
                            price: pkg.product.priceString,
                          }),
                      card.allowance,
                      meta.length > 0 ? meta.replace(" · ", ", ") : null,
                      badge,
                    ]
                      .filter((part): part is string => Boolean(part))
                      .join(", ")}
                  >
                    {pkg !== undefined && (
                      <View style={styles.tierRadioColumn}>
                        <Ionicons
                          name={
                            isSelected ? "radio-button-on" : "radio-button-off"
                          }
                          size={22}
                          color={isSelected ? Colors.textMain : Colors.outline}
                        />
                      </View>
                    )}

                    <View style={styles.tierBody}>
                      {badge !== null && (
                        <View style={styles.tierBadge}>
                          <Text style={styles.tierBadgeText}>{badge}</Text>
                        </View>
                      )}

                      <View style={styles.tierTitleRow}>
                        <Text style={styles.tierName} numberOfLines={1}>
                          {card.name}
                        </Text>
                        {pkg !== undefined && (
                          <Text style={styles.tierPrice} numberOfLines={1}>
                            {pkg.product.priceString}
                            <Text style={styles.tierPricePeriod}>/mo</Text>
                          </Text>
                        )}
                      </View>

                      {/* The allowance carries the card, not the name: it is the
                          only thing that differs between the tiers. */}
                      {card.allowance !== null && (
                        <Text style={styles.tierAllowance}>{card.allowance}</Text>
                      )}
                      {meta.length > 0 && (
                        <Text style={styles.tierMeta}>{meta}</Text>
                      )}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* What the allowance on those cards meters, and what it does not.
                The cards say "N h of transcription", which is the half that
                differs between them; this is the half that does not — articles
                and web pages cost no minutes — and stating it once under the
                list beats repeating it inside three cards, or leaving it behind
                the disclosure where it used to be the only place the screen
                admitted the app is not an audio-only product. Below the cards
                rather than above them so it costs nothing before the first
                price: the same sentence already frames them from the header
                ("Only the monthly transcription time changes"). */}
            <Text testID="paywall-minutes-rule" style={styles.minutesRuleText}>
              {minutesRule()}
            </Text>

            {/* What every plan does, *under* the prices: evidence for a decision
                already framed, rather than four lines standing between the
                reader and the figures. The exhaustive version stays one tap
                below — put on screen unprompted it is the wall of text every
                paywall study says nobody reads. */}
            <View testID="paywall-highlights" style={styles.highlightBlock}>
              <Text style={styles.includesHeading}>
                {t("paywall.includedHeading")}
              </Text>
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
                  {isDetailOpen
                    ? t("paywall.hideDetails")
                    : t("paywall.showDetails")}
                </Text>
                <Ionicons
                  name={isDetailOpen ? "chevron-up" : "chevron-down"}
                  size={16}
                  color={Colors.textMain}
                />
              </TouchableOpacity>

              {isDetailOpen && pricing !== null && (
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
          </>
        )}

        {/* Legal. The renewal terms are required wording on a screen that can
            actually take money, so they follow the purchase path; the two links
            are required *in the binary, on the purchase screen* by App Store
            guideline 3.1.2 and by Play's subscription policy, were absent
            entirely — one of the most common paywall rejections — and stay put
            whatever the store is doing.

            The block owns the gap that separates it from whatever precedes it,
            because what precedes it is not always the same element: the terms
            only render on the purchase path, and until task-336 the spacing came
            from a Restore Purchases button above them that no longer exists. */}
        <View style={styles.legalBlock}>
          {canPurchase && (
            <Text style={styles.legalText}>
              {t("paywall.renewalTerms", { store: STORE_NAME })}
            </Text>
          )}
          <View style={styles.legalLinks}>
            <TouchableOpacity
              testID="paywall-terms-link"
              style={styles.legalLinkButton}
              onPress={() => void Linking.openURL(TERMS_URL)}
              accessibilityRole="link"
              accessibilityLabel={t("paywall.terms")}
            >
              <Text style={styles.legalLinkText}>{t("paywall.terms")}</Text>
            </TouchableOpacity>
            <Text style={styles.legalLinkSeparator}>·</Text>
            <TouchableOpacity
              testID="paywall-privacy-link"
              style={styles.legalLinkButton}
              onPress={() => void Linking.openURL(PRIVACY_POLICY_URL)}
              accessibilityRole="link"
              accessibilityLabel={t("paywall.privacy")}
            >
              <Text style={styles.legalLinkText}>{t("paywall.privacy")}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* One CTA, in a footer that never scrolls away, naming what it buys and
          what it costs — per-card buttons turned the screen into three identical
          decisions, and a price only visible on a row that can be scrolled off
          is a price the stores consider hidden. The reassurance sits with the
          button rather than in the legal block nobody reaches. */}
      {!isLoading && canPurchase && (
        <View style={styles.footer}>
          <TouchableOpacity
            testID="paywall-subscribe-button"
            style={[
              styles.purchaseButton,
              (isPurchasing || selectedPackage === undefined) &&
                styles.purchaseButtonDisabled,
            ]}
            onPress={() =>
              selectedPackage !== undefined && handlePurchase(selectedPackage)
            }
            disabled={isPurchasing || selectedPackage === undefined}
            accessibilityRole="button"
            accessibilityLabel={ctaLabel}
          >
            {isPurchasing ? (
              <ActivityIndicator size="small" color={Colors.onPrimary} />
            ) : (
              <Text style={styles.purchaseButtonText}>{ctaLabel}</Text>
            )}
          </TouchableOpacity>
          <Text style={styles.footerNote}>
            {t("paywall.cancelAnytime", { store: STORE_NAME })}
          </Text>
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
    paddingBottom: Spacing.sm,
    alignItems: "center",
  },
  // Sits above the title's own line rather than beside it: "Choose Your Plan"
  // at 32pt is ~280px wide on a 375pt screen, which reaches under a right-hand
  // button placed on the same band.
  closeButton: {
    position: "absolute",
    top: Spacing.sm,
    // `end`, not `right`: an absolute `right` stays on the right in Arabic,
    // where the close button belongs on the other side.
    end: Spacing.lg,
    minHeight: TouchTarget.minimum,
    minWidth: TouchTarget.minimum,
    justifyContent: "center",
    alignItems: "center",
  },
  closeText: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textSubtle,
  },
  title: {
    ...Typography.display,
    color: Colors.textMain,
    marginTop: Spacing.md,
    textAlign: "center",
    // Keeps the longer translations clear of the floating close button rather
    // than relying on "~280px on a 375pt screen", which is an English number.
    paddingHorizontal: TouchTarget.minimum,
  },
  tagline: {
    ...Typography.label,
    color: Colors.textMain,
    marginTop: Spacing.xs,
    textAlign: "center",
    lineHeight: 20,
  },
  subtitle: {
    ...Typography.small,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
    textAlign: "center",
    lineHeight: 18,
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
  // A degraded state, not a failure: the plans below are real and complete, only
  // the prices are missing. Neutral surface rather than the amber used for a
  // limit the user has hit, which is about them and not about the store.
  //
  // Compact on purpose. A centred block with a full-width button underneath cost
  // ~180pt and pushed the first card to 549pt down a 852pt screen — this notice
  // was undoing the very thing the screen was rearranged to fix. Icon and text on
  // one row, retry as a link rather than a button, roughly half the height.
  noticeBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surfaceContainerLow,
  },
  noticeBody: {
    flex: 1,
  },
  noticeText: {
    ...Typography.small,
    color: Colors.textMain,
    lineHeight: 18,
  },
  noticeRetry: {
    minHeight: 40,
    justifyContent: "center",
  },
  noticeRetryText: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.textMain,
    textDecorationLine: "underline",
  },
  // The reason the user is here, in the app's own alert tone rather than an
  // error red: nothing has gone wrong, a limit was reached.
  reasonBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    backgroundColor: Colors.highlight,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginTop: Spacing.md,
  },
  reasonText: {
    ...Typography.small,
    flex: 1,
    color: Colors.textMain,
    lineHeight: 18,
  },
  trialNote: {
    ...Typography.small,
    color: Colors.textMain,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginTop: Spacing.sm,
    lineHeight: 18,
  },
  selectorLabel: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
    marginTop: Spacing.lg,
  },
  recommendationText: {
    ...Typography.small,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
    lineHeight: 18,
  },
  // A plan card carries a 2px border in both states: `surface` on `background`
  // is a 1.01:1 step, so without one the three most important controls on the
  // screen had no edge at all while the benefits block below them had a shadow.
  // The width never changes between states, only the colour, so selecting a card
  // cannot shift the layout by a pixel.
  tierCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 2,
    borderColor: Colors.outlineVariant,
    borderRadius: BorderRadius.xl,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    minHeight: TouchTarget.comfortable,
  },
  tierCardSelected: {
    backgroundColor: Colors.highlight,
    borderColor: Colors.textMain,
  },
  tierRadioColumn: {
    justifyContent: "center",
  },
  tierBody: {
    flex: 1,
  },
  tierTitleRow: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: Spacing.sm,
  },
  // The name is the label of the row, not its headline: it says "Mix", which
  // tells a newcomer nothing. The allowance and the price are the headline.
  tierName: {
    // Yields to the price rather than colliding with it: the price is the
    // number the user came for, and it is the one that must stay whole.
    flexShrink: 1,
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMain,
  },
  tierPrice: {
    flexShrink: 0,
    ...Typography.headline,
    fontWeight: "700",
    color: Colors.textMain,
    // End of the line, not "right": `textAlign` has no logical value in React
    // Native, so the side is read off the active direction instead.
    textAlign: I18nManager.isRTL ? "left" : "right",
  },
  tierPricePeriod: {
    ...Typography.small,
    fontWeight: "500",
    color: Colors.textSubtle,
  },
  tierAllowance: {
    ...Typography.headline,
    color: Colors.textMain,
    marginTop: 2,
  },
  tierMeta: {
    ...Typography.small,
    color: Colors.textSubtle,
    marginTop: Spacing.xs,
    lineHeight: 18,
  },
  // Its own line rather than beside the name: "RECOMMENDED FOR YOU" next to a
  // plan name and a price does not survive a 375pt screen.
  tierBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    marginBottom: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  tierBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
    color: Colors.textMain,
  },
  // `textMain`, not the subtle grey the other small lines here use: this one
  // qualifies the dominant line of all three cards, and at `textSubtle` on no
  // surface it reads as a legal footnote — which is how the app ended up
  // implying the allowance meters everything you save.
  minutesRuleText: {
    ...Typography.small,
    color: Colors.textMain,
    marginTop: Spacing.sm,
    lineHeight: 18,
  },
  highlightBlock: {
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surface,
    ...Shadows.soft,
  },
  includesHeading: {
    ...Typography.label,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: 0.5,
    textTransform: "uppercase",
    marginBottom: Spacing.sm,
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
    color: Colors.textSubtle,
    lineHeight: 18,
  },
  includesItem: {
    ...Typography.small,
    flex: 1,
    color: Colors.textSubtle,
    lineHeight: 18,
  },
  legalBlock: {
    marginTop: Spacing.lg,
  },
  legalText: {
    ...Typography.small,
    color: Colors.textSubtle,
    textAlign: "center",
    paddingHorizontal: Spacing.md,
    lineHeight: 18,
  },
  legalLinks: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
  },
  legalLinkButton: {
    minHeight: TouchTarget.minimum,
    justifyContent: "center",
    paddingHorizontal: Spacing.xs,
  },
  legalLinkText: {
    ...Typography.small,
    fontWeight: "600",
    color: Colors.textSubtle,
    textDecorationLine: "underline",
  },
  legalLinkSeparator: {
    ...Typography.small,
    color: Colors.textSubtle,
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
  footerNote: {
    ...Typography.small,
    color: Colors.textSubtle,
    textAlign: "center",
    marginTop: Spacing.sm,
  },
});
