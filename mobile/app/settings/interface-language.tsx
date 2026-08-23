import { View, Text, StyleSheet, FlatList, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import {
  LOCALE_ENDONYMS,
  SUPPORTED_LOCALES,
  resolveDeviceLocale,
  t,
  useTranslation,
  type SupportedLocale,
} from "../../src/i18n";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";

/**
 * The language of the interface — a different setting from the reading
 * language, and deliberately next to it rather than merged with it.
 *
 * `reading_language` decides what the summaries and translated transcripts are
 * written in; it is an account preference and travels to the backend. This one
 * decides what the buttons say, is stored on the device only, and the backend
 * is never told about it. Wanting English summaries in a French interface is a
 * normal combination, and one setting could not express it.
 *
 * The first row hands the choice back to the device, which is the default
 * state: someone who has never opened this screen follows their phone, and the
 * row names the language that resolves to so the effect is visible before the
 * tap.
 */
const FOLLOW_DEVICE = "system" as const;

type LocaleChoice = SupportedLocale | typeof FOLLOW_DEVICE;

export default function InterfaceLanguageScreen() {
  const router = useRouter();
  const { locale, override, setLocale } = useTranslation();

  const deviceLocale = resolveDeviceLocale();
  const selected: LocaleChoice = override ?? FOLLOW_DEVICE;
  const choices: LocaleChoice[] = [FOLLOW_DEVICE, ...SUPPORTED_LOCALES];

  const handleSelect = (choice: LocaleChoice) => {
    setLocale(choice === FOLLOW_DEVICE ? null : choice);
  };

  const renderItem = ({ item }: { item: LocaleChoice }) => {
    const isSelected = item === selected;
    const isFollowDevice = item === FOLLOW_DEVICE;
    const label = isFollowDevice
      ? t("uiLanguage.followDevice")
      : LOCALE_ENDONYMS[item];
    const detail = isFollowDevice
      ? LOCALE_ENDONYMS[deviceLocale]
      : item.toUpperCase();

    return (
      <Pressable
        style={[styles.languageItem, isSelected && styles.languageItemSelected]}
        onPress={() => handleSelect(item)}
        accessibilityLabel={t("uiLanguage.selectA11y", { language: label })}
        accessibilityRole="button"
        accessibilityState={{ selected: isSelected }}
      >
        <Text
          style={[
            styles.languageLabel,
            isSelected && styles.languageLabelSelected,
          ]}
        >
          {label}
        </Text>
        <Text style={styles.languageDetail}>{detail}</Text>
        {isSelected && (
          <Ionicons name="checkmark-circle" size={24} color={Colors.primary} />
        )}
      </Pressable>
    );
  };

  return (
    <SafeAreaView
      testID="interface-language-screen"
      style={styles.container}
      edges={["top"]}
    >
      <View style={styles.header}>
        <Pressable
          style={styles.backButton}
          onPress={() => router.back()}
          accessibilityLabel={t("common.goBack")}
          accessibilityRole="button"
        >
          <Ionicons name="chevron-back" size={24} color={Colors.textMain} />
        </Pressable>
        <Text style={styles.title}>{t("uiLanguage.title")}</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={styles.disclaimer}>
        <Ionicons
          name="information-circle-outline"
          size={20}
          color={Colors.textMuted}
        />
        <Text style={styles.disclaimerText}>{t("uiLanguage.disclaimer")}</Text>
      </View>

      <FlatList
        data={choices}
        keyExtractor={(item) => item}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        extraData={locale}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backButton: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    flex: 1,
    ...Typography.headline,
    color: Colors.textMain,
    textAlign: "center",
  },
  // Balances the back button so the title stays optically centred.
  headerSpacer: {
    width: TouchTarget.minimum,
  },
  disclaimer: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
  },
  disclaimerText: {
    flex: 1,
    ...Typography.small,
    color: Colors.textMuted,
    lineHeight: Typography.body.lineHeight,
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xxl,
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
  languageDetail: {
    ...Typography.small,
    color: Colors.textMuted,
    marginEnd: Spacing.sm,
  },
});
