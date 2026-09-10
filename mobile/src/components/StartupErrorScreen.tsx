import { useEffect } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as SplashScreen from "expo-splash-screen";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../constants/theme";
import { t } from "../i18n";

interface StartupErrorScreenProps {
  /** Clears the failure and lets the tree mount again from scratch. */
  onRetry: () => void;
}

/**
 * What the app shows instead of dying.
 *
 * Rendered by both nets — the root `ErrorBoundary` of `app/_layout.tsx` for a
 * render error, `StartupErrorGate` for anything the global handlers catch — so it
 * has to stand entirely on its own: it is mounted *above* every provider, and
 * the thing that failed may well be one of them.
 *
 * Which is why the copy goes through the module-level `t()` rather than
 * `useTranslation()`. That runtime resolves against the catalogue `I18nProvider`
 * installed, or against `en` if nothing was installed yet, and it never throws
 * for want of a context. The only surrounding it does assume is the
 * `SafeAreaProvider` that `ExpoRoot` mounts above the root layout.
 *
 * The exception itself does not appear here. Its name, its message and its stack
 * are the trace of a bug in this app — never something the reader caused, and
 * never something they can act on — so both nets log it on the way in and this
 * screen offers the one thing that is left: start again (task-397).
 *
 * Design: Amber Clarity — warm surfaces, tonal shifts instead of rules, one
 * amber CTA.
 */
export function StartupErrorScreen({ onRetry }: StartupErrorScreenProps) {
  // `app/_layout.tsx` holds the native splash from module scope, for the whole
  // life of the process, and `SplashGate` — which is somewhere below this screen
  // and no longer mounted — is what normally gives it back. Without this the
  // fallback would render underneath a splash that never lifts, which is the
  // failure mode it exists to replace.
  useEffect(() => {
    void SplashScreen.hideAsync().catch(() => {
      // Already hidden: nothing owed.
    });
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.hero}>
          <Ionicons name="alert-circle-outline" size={72} color={Colors.error} />
        </View>

        <Text style={styles.title}>{t("startupError.title")}</Text>
        <Text style={styles.body}>{t("startupError.body")}</Text>

        <Pressable
          style={styles.retryButton}
          onPress={onRetry}
          accessibilityLabel={t("startupError.retryA11y")}
          accessibilityRole="button"
        >
          <Text style={styles.retryButtonText}>{t("common.retry")}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xl,
  },
  hero: {
    alignItems: "center",
    marginBottom: Spacing.lg,
  },
  title: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    letterSpacing: Typography.display.letterSpacing,
    color: Colors.textMain,
    textAlign: "center",
    marginBottom: Spacing.md,
  },
  body: {
    fontSize: Typography.body.fontSize,
    lineHeight: Typography.body.lineHeight,
    color: Colors.textSubtle,
    textAlign: "center",
    marginBottom: Spacing.xl,
  },
  retryButton: {
    alignSelf: "stretch",
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    minHeight: TouchTarget.comfortable,
    alignItems: "center",
    justifyContent: "center",
    ...Shadows.soft,
  },
  retryButtonText: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
});
