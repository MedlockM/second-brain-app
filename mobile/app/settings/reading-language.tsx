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
import { useRouter } from "expo-router";
import { useUserPreferences } from "../../src/contexts/UserPreferencesContext";
import {
  V1_READING_LANGUAGES,
  ReadingLanguageCode,
} from "../../src/services/userPreferencesService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import { t } from "../../src/i18n";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";
import { ScreenHeader, HeaderIconButton } from "../../src/components/ScreenHeader";

/**
 * Settings screen for changing reading language preference.
 * Accessible from the Account screen.
 * Includes a disclaimer about existing content not being re-translated.
 */
export default function ReadingLanguageSettingsScreen() {
  const router = useRouter();
  const { readingLanguage, updateReadingLanguage, isUpdating } =
    useUserPreferences();
  const [selectedLanguage, setSelectedLanguage] =
    useState<ReadingLanguageCode | null>(
      (readingLanguage as ReadingLanguageCode) ?? null,
    );
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasChanged = selectedLanguage !== readingLanguage;

  const handleSave = async () => {
    if (!selectedLanguage || !hasChanged) return;
    setError(null);
    setSuccess(false);
    try {
      await updateReadingLanguage(selectedLanguage);
      setSuccess(true);
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
        onPress={() => {
          setSelectedLanguage(item.code);
          setSuccess(false);
        }}
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
    <SafeAreaView style={styles.container} edges={["top"]}>
      {/* Header with back button */}
      <ScreenHeader
        title={t("readingLanguage.title")}
        leading={
          <HeaderIconButton
            icon="chevron-back"
            variant="plain"
            onPress={() => router.back()}
            accessibilityLabel={t("common.goBack")}
          />
        }
      />

      {/* Disclaimer */}
      <View style={styles.disclaimer}>
        <Ionicons
          name="information-circle-outline"
          size={20}
          color={Colors.textMuted}
        />
        <Text style={styles.disclaimerText}>
          {t("readingLanguage.disclaimer")}
        </Text>
      </View>

      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {success && (
        <View style={styles.successContainer}>
          <Ionicons name="checkmark-circle" size={16} color={Colors.primary} />
          <Text style={styles.successText}>{t("readingLanguage.saved")}</Text>
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
          style={[
            styles.saveButton,
            (!hasChanged || isUpdating) && styles.buttonDisabled,
          ]}
          onPress={handleSave}
          disabled={!hasChanged || isUpdating}
          accessibilityLabel={t("readingLanguage.saveA11y")}
          accessibilityRole="button"
        >
          {isUpdating ? (
            <ActivityIndicator color={Colors.onPrimary} />
          ) : (
            <Text style={styles.saveButtonText}>{t("common.save")}</Text>
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
  disclaimer: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: Colors.surfaceContainerLow,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    gap: Spacing.sm,
  },
  disclaimerText: {
    flex: 1,
    ...Typography.small,
    color: Colors.textMuted,
    lineHeight: 18,
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
  successContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
  },
  successText: {
    ...Typography.small,
    color: Colors.textMain,
    fontWeight: "500",
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
  saveButton: {
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
  saveButtonText: {
    color: Colors.onPrimary,
    ...Typography.body,
    fontWeight: "600",
  },
});
