import { Redirect } from "expo-router";
import { NativeTabs } from "expo-router/unstable-native-tabs";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../src/contexts/AuthContext";
import { useUserPreferences } from "../../src/contexts/UserPreferencesContext";
import { LANGUAGE_ONBOARDING_ROUTE } from "../../src/constants/routes";
import { Colors } from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";
import { ActivityIndicator, View, StyleSheet } from "react-native";

/**
 * Protected tabs layout, and the enforcement point of the two invariants that
 * hold for every tab: a session, and a reading language.
 *
 * Both guards are checked in order, and both replace the tab bar entirely rather
 * than rendering it alongside a redirect — that is what makes them impossible to
 * walk past. `app/index.tsx` checks the same two things on a cold start, but it
 * is a route like any other: expo-router's `Redirect` only fires from a focus
 * effect, so an unfocused `index` keeps an unconsumed redirect armed and fires
 * it whenever it regains focus. That is how a fresh account used to reach the
 * tabs first and get the language screen thrown at it later, on an arbitrary tap
 * (task-326). Here there is nothing to arm: no tab exists until both guards pass.
 *
 * Tab bar follows the mockup navigation pattern (Home, Search, Digest, Account).
 *
 * The bar itself is no longer drawn here (task-350). `NativeTabs` hands the four
 * items to `UITabBarController` on iOS and to Material's bottom navigation on
 * Android, and that is the whole of what buys the iOS 26 floating glass capsule:
 * a detached, fully rounded bar inset from the screen edges, translucent, with
 * the content passing under it and the selected item in a filled pill. It is not
 * a design to redraw — it *is* the system bar — and it arrives with the
 * scroll-edge effect, Dynamic Type, the minimize behaviours and next year's
 * appearance, none of which a JS bar would ever stop owing.
 *
 * The price is that the background stops being ours to set: under Liquid Glass
 * the system owns it, and `backgroundColor`, `blurEffect`, `shadowColor` and
 * `disableTransparentOnScrollEdge` apply on iOS 18 and earlier only. So none of
 * them is passed, and on an iOS 18 device the classic opaque bar is the expected
 * rendering rather than a regression.
 *
 * `NativeTabs` is alpha and its API is stated as subject to change. Two known
 * upstream bugs surface here and are not local ones, so they are named rather
 * than chased: expo/expo#44029 (`labelStyle` colours not applying on iOS, which
 * is why the labels take their colour from `tintColor` and nothing sets
 * `labelStyle`) and expo/expo#39930 (icon tint not refreshing over light/dark
 * content on iOS 26).
 */
export default function TabsLayout() {
  const { isAuthenticated, isLoading } = useAuth();
  const { needsLanguageOnboarding } = useUserPreferences();
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

  // Strictly after the two guards above: `needsLanguageOnboarding` is derived
  // from the profile, and a profile still being restored reads as "no reading
  // language", which would send a returning user to the onboarding screen every
  // cold start.
  if (needsLanguageOnboarding) {
    return <Redirect href={LANGUAGE_ONBOARDING_ROUTE} />;
  }

  return (
    <NativeTabs
      // The bar's two colours, and the whole of them. `tintColor` carries the
      // selected item (glyph and label alike); `iconColor` states both states
      // explicitly so an unselected glyph is never left to a system default.
      tintColor={Colors.tabActive}
      iconColor={{ default: Colors.tabInactive, selected: Colors.tabActive }}
      // The bar stays put. Both reference screens show a bar that does not
      // shrink away, and this is an app people switch tabs in rather than read
      // in one long scroll — a bar that minimizes on scroll would spend the
      // gesture hiding the way out of the screen.
      minimizeBehavior="never"
    >
      {/* `sf` serves iOS and `src` serves Android (iOS priority is
          `sf` > `xcasset` > `src`), so each item names an SF Symbol *and* keeps
          today's Ionicon. That is what leaves Android on exactly the glyphs it
          already had, and adds no icon asset to the bundle. */}
      <NativeTabs.Trigger name="inbox">
        <NativeTabs.Trigger.Icon
          sf="tray"
          src={
            <NativeTabs.Trigger.VectorIcon
              family={Ionicons}
              name="file-tray-outline"
            />
          }
        />
        <NativeTabs.Trigger.Label>{t("tabs.home")}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>

      {/* The screen file stays `search`: only the label has ever moved. task-306
          labelled this tab for its content ("Library") because the screen holds
          every collection and every saved item; task-315 put it back on the
          action, so the two labels now name what the user does — go Home, or
          Search — rather than what each screen contains.

          No `role="search"`, deliberately: iOS 26 pulls a search-role tab out to
          the trailing edge of the bar for a genuine search *field*, and this tab
          is the library, which carries its own floating pill. The role also has
          an open badge-clipping bug (expo/expo#41573). */}
      <NativeTabs.Trigger name="search">
        <NativeTabs.Trigger.Icon
          sf="books.vertical"
          src={
            <NativeTabs.Trigger.VectorIcon
              family={Ionicons}
              name="library-outline"
            />
          }
        />
        <NativeTabs.Trigger.Label>{t("tabs.search")}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="digest">
        <NativeTabs.Trigger.Icon
          sf="sparkles"
          src={
            <NativeTabs.Trigger.VectorIcon
              family={Ionicons}
              name="sparkles-outline"
            />
          }
        />
        <NativeTabs.Trigger.Label>{t("tabs.digest")}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="account">
        <NativeTabs.Trigger.Icon
          sf="person.crop.circle"
          src={
            <NativeTabs.Trigger.VectorIcon
              family={Ionicons}
              name="person-outline"
            />
          }
        />
        <NativeTabs.Trigger.Label>
          {t("account.title")}
        </NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
    </NativeTabs>
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
