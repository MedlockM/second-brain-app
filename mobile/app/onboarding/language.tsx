import { useState, useEffect } from "react";
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
import { getDeviceLanguageCode } from "../../src/lib/getDeviceLanguageCode";
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
 * Shown after registration when reading_language is not yet set.
 * Pre-selects the device locale if it matches a V1 language.
 */
export default function OnboardingLanguageScreen() {
  const { updateReadingLanguage, isUpdating } = useUserPreferences();
  const [selectedLanguage, setSelectedLanguage] =
    useState<ReadingLanguageCode | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Pre-select device locale on mount
  useEffect(() => {
    const deviceLang = getDeviceLanguageCode();
    const matchedLang = V1_READING_LANGUAGES.find(
      (l) => l.code === deviceLang,
    );
    if (matchedLang) {
      setSelectedLanguage(matchedLang.code);
    } else {
      // Default to English if device locale is not in V1 list
      setSelectedLanguage("en");
    }
  }, []);

  const handleContinue = async () => {
    if (!selectedLanguage) return;
    setError(null);
    try {
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
        accessibilityLabel={`Select ${item.label} as reading language`}
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
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <Text style={styles.title}>Choose your reading language</Text>
        <Text style={styles.subtitle}>
          Content will be translated to this language when needed.
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
          style={[styles.continueButton, isUpdating && styles.buttonDisabled]}
          onPress={handleContinue}
          disabled={!selectedLanguage || isUpdating}
          accessibilityLabel="Continue with selected language"
          accessibilityRole="button"
        >
          {isUpdating ? (
            <ActivityIndicator color={Colors.onPrimary} />
          ) : (
            <Text style={styles.continueButtonText}>Continue</Text>
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
    marginRight: Spacing.sm,
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
