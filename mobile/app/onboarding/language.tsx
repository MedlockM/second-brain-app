import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  ActivityIndicator,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { resolveDeviceLocale, t } from "../../src/i18n";
import { useUserPreferences } from "../../src/contexts/UserPreferencesContext";
import {
  V1_READING_LANGUAGES,
  ReadingLanguageCode,
} from "../../src/services/userPreferencesService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";

/**
 * Onboarding screen: asks the user to select their preferred reading language.
 * Reached from `app/index.tsx` on a cold start and from `app/(tabs)/_layout.tsx`,
 * which is the guard that actually makes it unskippable.
 * Pre-selects the device locale if it matches a V1 language.
 */
export default function OnboardingLanguageScreen() {
  const { updateReadingLanguage, isUpdating } = useUserPreferences();
  const [selectedLanguage, setSelectedLanguage] =
    useState<ReadingLanguageCode>(() => {
      // The device's own ordered preference list, intersected with what the app
      // supports — `expo-localization` answers that properly, where the
      // hand-rolled reader this replaced only ever saw the first entry.
      const deviceLocale = resolveDeviceLocale();
      return (
        V1_READING_LANGUAGES.find((language) => language.code === deviceLocale)
          ?.code ?? "en"
      );
    });
  const [error, setError] = useState<string | null>(null);

  const handleContinue = async () => {
    if (!selectedLanguage) return;
    setError(null);
    try {
      // Exit path, and why it cannot bounce back here: the await resolves only
      // after `updateReadingLanguage` has written `localReadingLanguage` in
      // UserPreferencesContext, so `needsLanguageOnboarding` is already false
      // when the tabs layout runs its language guard on its first render. This
      // is also why the exit stays a direct hop to the inbox rather than going
      // through `/` — the preference is settled before navigation, so there is
      // nothing left for the entry point to arbitrate, and the extra hop would
      // only add a frame of the root loading state.
      // A failed update throws instead, which keeps the user on this screen with
      // an error rather than sending them into the tabs with no language set.
      await updateReadingLanguage(selectedLanguage);
      router.replace("/(tabs)/inbox");
    } catch (err) {
      setError(getFriendlyErrorMessage(err));
    }
  };

  const renderItem = ({
    item,
  }: {
    item: (typeof V1_READING_LANGUAGES)[number];
  }) => {
    const isSelected = selectedLanguage === item.code;
    return (
      <Pressable
        style={[styles.languageItem, isSelected && styles.languageItemSelected]}
        onPress={() => setSelectedLanguage(item.code)}
        accessibilityLabel={t("readingLanguage.selectA11y", {
          language: item.label,
        })}
        accessibilityRole="button"
        accessibilityState={{ selected: isSelected }}
      >
        <Text
          style={[
            styles.languageLabel,
            isSelected && styles.languageLabelSelected,
          ]}
        >
          {item.label}
        </Text>
        <Text style={styles.languageCode}>{item.code.toUpperCase()}</Text>
        {isSelected && (
          <Ionicons name="checkmark-circle" size={24} color={Colors.primary} />
        )}
      </Pressable>
    );
  };

  return (
    <SafeAreaView
      testID="language-onboarding-screen"
      style={styles.container}
      edges={["top", "bottom"]}
    >
      <View style={styles.header}>
        <Text style={styles.title}>{t("onboarding.language.title")}</Text>
        <Text style={styles.subtitle}>
          {t("onboarding.language.subtitle")}
        </Text>
      </View>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      <FlatList
        data={V1_READING_LANGUAGES}
        keyExtractor={(item) => item.code}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />

      <View style={styles.footer}>
        <Pressable
          testID="language-onboarding-continue-button"
          style={[styles.continueButton, isUpdating && styles.buttonDisabled]}
          onPress={handleContinue}
          disabled={!selectedLanguage || isUpdating}
          accessibilityLabel={t("onboarding.language.continueA11y")}
          accessibilityRole="button"
        >
          {isUpdating ? (
            <ActivityIndicator color={Colors.onPrimary} />
          ) : (
            <Text style={styles.continueButtonText}>
              {t("common.continue")}
            </Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.md,
  },
  title: {
    ...Typography.display,
    color: Colors.textMain,
  },
  subtitle: {
    ...Typography.body,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
  },
  errorContainer: {
    backgroundColor: Colors.errorContainer,
    padding: Spacing.md,
    marginHorizontal: Spacing.lg,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.md,
  },
  errorText: {
    color: Colors.error,
    fontSize: Typography.small.fontSize,
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
  },
  languageItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.sm,
    minHeight: TouchTarget.minimum,
  },
  languageItemSelected: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  languageLabel: {
    flex: 1,
    ...Typography.body,
    fontWeight: "500",
    color: Colors.textMain,
  },
  languageLabelSelected: {
    fontWeight: "700",
  },
  languageCode: {
    ...Typography.small,
    color: Colors.textMuted,
    marginEnd: Spacing.sm,
  },
  footer: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    paddingBottom: Platform.OS === "ios" ? Spacing.md : Spacing.lg,
  },
  continueButton: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.md,
    paddingVertical: Spacing.md,
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.comfortable,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  continueButtonText: {
    color: Colors.onPrimary,
    ...Typography.body,
    fontWeight: "600",
  },
});
