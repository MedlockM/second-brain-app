import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  Switch,
} from "react-native";
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
import { ScreenHeader, HeaderIconButton } from "../../src/components/ScreenHeader";

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
  const { locale, override, setLocale, pseudo, setPseudo } = useTranslation();

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

  /**
   * The pseudo-localisation switch, in development builds only.
   *
   * Its copy is hard-coded English rather than catalogue keys: a key would be
   * pseudo-localised along with everything else, which would make the one
   * control you need in order to turn the mode *off* the least readable thing
   * on the screen.
   */
  const renderDevTools = () => {
    if (!__DEV__) return null;

    return (
      <View style={styles.devSection}>
        <Text style={styles.devHeading}>DEVELOPMENT</Text>
        <View style={styles.devRow}>
          <View style={styles.devRowText}>
            <Text style={styles.devLabel}>Pseudo-localisation</Text>
            <Text style={styles.devHint}>
              Accents every string and pads it by ~40% to expose layouts that
              break when a translation runs long. Screens already on the stack
              repaint when you navigate away and back.
            </Text>
          </View>
          <Switch value={pseudo} onValueChange={setPseudo} />
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView
      testID="interface-language-screen"
      style={styles.container}
      edges={["top"]}
    >
      <ScreenHeader
        title={t("uiLanguage.title")}
        leading={
          <HeaderIconButton
            icon="chevron-back"
            variant="plain"
            onPress={() => router.back()}
            accessibilityLabel={t("common.goBack")}
          />
        }
      />

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
        ListFooterComponent={renderDevTools}
      />
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
  devSection: {
    marginTop: Spacing.xl,
    gap: Spacing.sm,
  },
  devHeading: {
    ...Typography.small,
    color: Colors.textMuted,
    letterSpacing: 1,
  },
  devRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
  },
  devRowText: {
    flex: 1,
    gap: Spacing.xs,
  },
  devLabel: {
    ...Typography.body,
    color: Colors.textMain,
  },
  devHint: {
    ...Typography.small,
    color: Colors.textMuted,
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
