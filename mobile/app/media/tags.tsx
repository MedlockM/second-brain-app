import { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Keyboard,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
} from "../../src/constants/theme";
import { t, tCount, useTranslation } from "../../src/i18n";
import { useAuth } from "../../src/contexts/AuthContext";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import { OrganizationService } from "../../src/services/organizationService";
import type { Tag } from "../../src/types/organization";

function parseInitialTagIds(value?: string): string[] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed)
      ? parsed.filter((tagId): tagId is string => typeof tagId === "string")
      : [];
  } catch {
    return [];
  }
}

/**
 * Tag Management Screen.
 * Presented as a modal/bottom-sheet from media detail.
 *
 * Key UX: The keyboard does NOT appear by default.
 * Tags are shown as tappable list rows. The user can tap a tag to toggle it.
 * The text input is available for search/create but NOT autofocused.
 *
 * Design ref: mobile-design-mockups/gestion_des_tags_no_keyboard_space/
 */
export default function TagsScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{
    mode?: string;
    mediaItemId?: string;
    currentTags?: string;
  }>();

  const { isAuthenticated } = useAuth();
  const { selectedTags: shareSelectedTags, setSelectedTags } = useShareIntake();
  const isShareMode = params.mode === "share";
  const inputRef = useRef<TextInput>(null);

  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>(() =>
    isShareMode
      ? shareSelectedTags.map((tag) => tag.id)
      : parseInitialTagIds(params.currentTags),
  );
  const [searchText, setSearchText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch user's tags
  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchTags = async () => {
      try {
        setIsLoading(true);
        const tags = await OrganizationService.getUserTags();
        setAllTags(tags);
      } catch {
        setError(t("tags.loadFailed"));
      } finally {
        setIsLoading(false);
      }
    };

    fetchTags();
  }, [isAuthenticated]);

  // Filter tags based on search text
  const filteredTags = allTags.filter((tag) =>
    tag.name.toLowerCase().includes(searchText.toLowerCase()),
  );

  // Check if search text matches an existing tag exactly
  const exactMatch = allTags.some(
    (tag) => tag.name.toLowerCase() === searchText.toLowerCase(),
  );

  const syncShareTags = useCallback(
    (tagIds: string[], tags: Tag[]) => {
      if (!isShareMode) return;
      const fallbackById = new Map(
        shareSelectedTags.map((tag) => [tag.id, tag.name]),
      );
      setSelectedTags(
        tagIds.map((id) => {
          const tag = tags.find((item) => item.id === id);
          return {
            id,
            name: tag?.name ?? fallbackById.get(id) ?? id,
          };
        }),
      );
    },
    [isShareMode, setSelectedTags, shareSelectedTags],
  );

  const handleToggleTag = useCallback(
    (tagId: string) => {
      setSelectedTagIds((prev) => {
        const next = prev.includes(tagId)
          ? prev.filter((id) => id !== tagId)
          : [...prev, tagId];
        syncShareTags(next, allTags);
        return next;
      });
    },
    [allTags, syncShareTags],
  );

  const handleCreateAndAddTag = useCallback(async () => {
    const trimmed = searchText.trim();
    if (!trimmed || !isAuthenticated) return;

    const existing = allTags.find(
      (tag) => tag.name.toLowerCase() === trimmed.toLowerCase(),
    );
    if (existing) {
      setSelectedTagIds((prev) => {
        const next = prev.includes(existing.id) ? prev : [...prev, existing.id];
        syncShareTags(next, allTags);
        return next;
      });
      setSearchText("");
      Keyboard.dismiss();
      return;
    }

    try {
      const created = await OrganizationService.createTag(trimmed);
      setAllTags((prev) => {
        const nextTags = [...prev, created];
        setSelectedTagIds((selected) => {
          const nextSelected = selected.includes(created.id)
            ? selected
            : [...selected, created.id];
          syncShareTags(nextSelected, nextTags);
          return nextSelected;
        });
        return nextTags;
      });
      setSearchText("");
      Keyboard.dismiss();
    } catch {
      setError(t("tags.createFailed"));
    }
  }, [allTags, isAuthenticated, searchText, syncShareTags]);

  const selectedTagChips = selectedTagIds.map((id) => {
    const tag = allTags.find((item) => item.id === id);
    const fallback = shareSelectedTags.find((item) => item.id === id);
    return {
      id,
      name: tag?.name ?? fallback?.name ?? id,
    };
  });

  const handleRemoveSelectedTag = useCallback(
    (tagId: string) => {
      setSelectedTagIds((prev) => {
        const next = prev.filter((id) => id !== tagId);
        syncShareTags(next, allTags);
        return next;
      });
    },
    [allTags, syncShareTags],
  );

  const handleBack = useCallback(() => {
    if (isShareMode) {
      syncShareTags(selectedTagIds, allTags);
    }
    if (router.canGoBack()) {
      router.back();
    }
  }, [allTags, isShareMode, router, selectedTagIds, syncShareTags]);

  const handleSave = useCallback(async () => {
    if (isShareMode) {
      handleBack();
      return;
    }

    if (!isAuthenticated || !params.mediaItemId) {
      handleBack();
      return;
    }

    try {
      setIsSaving(true);
      await OrganizationService.updateMediaTags(
        params.mediaItemId,
        selectedTagIds,
      );
      handleBack();
    } catch {
      setError(t("tags.saveFailed"));
      setIsSaving(false);
    }
  }, [
    handleBack,
    isAuthenticated,
    isShareMode,
    params.mediaItemId,
    selectedTagIds,
  ]);

  const renderTagItem = useCallback(
    ({ item }: { item: Tag }) => {
      const isSelected = selectedTagIds.includes(item.id);
      return (
        <TouchableOpacity
          style={[styles.tagRow, isSelected && styles.tagRowSelected]}
          onPress={() => handleToggleTag(item.id)}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel={`${item.name}, ${isSelected ? "selected" : "not selected"}`}
          accessibilityState={{ selected: isSelected }}
        >
          <Text
            style={[styles.tagName, isSelected && styles.tagNameSelected]}
          >
            {item.name}
          </Text>
          <View style={styles.tagRight}>
            <Text style={styles.tagCount}>{item.count}</Text>
            {isSelected && (
              <Ionicons
                name="checkmark-circle"
                size={20}
                color={Colors.primary}
              />
            )}
          </View>
        </TouchableOpacity>
      );
    },
    [handleToggleTag, selectedTagIds],
  );

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      {/* Drag handle indicator */}
      <View style={styles.dragHandleContainer}>
        <View style={styles.dragHandle} />
      </View>

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={handleBack}
          accessibilityLabel={t("common.goBack")}
          accessibilityRole="button"
        >
          <Ionicons name="arrow-back" size={22} color={Colors.textMain} />
        </TouchableOpacity>

        <Text style={styles.headerTitle}>
          {tCount("tags.selectedCount", selectedTagIds.length)}
        </Text>

        <TouchableOpacity
          style={[styles.saveButton, isSaving && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={isSaving}
          accessibilityLabel={t("tags.saveA11y")}
          accessibilityRole="button"
        >
          {isSaving ? (
            <ActivityIndicator size="small" color={Colors.primary} />
          ) : (
            <Text style={styles.saveButtonText}>{t("common.done")}</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Selected tags chips */}
      {selectedTagChips.length > 0 && (
        <View style={styles.selectedChipsContainer}>
          {selectedTagChips.map((tag) => (
            <View key={tag.id} style={styles.chip}>
              <Text style={styles.chipText}>{tag.name}</Text>
              <TouchableOpacity
                onPress={() => handleRemoveSelectedTag(tag.id)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={t("tags.removeA11y", { name: tag.name })}
              >
                <Ionicons
                  name="close-circle"
                  size={18}
                  color={Colors.outline}
                />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}

      {/* Search/Add input - NOT autofocused (key UX constraint) */}
      <View style={styles.inputContainer}>
        <View style={styles.inputAccent} />
        <TextInput
          ref={inputRef}
          style={styles.input}
          placeholder={t("tags.addPlaceholder")}
          placeholderTextColor={Colors.outlineVariant}
          value={searchText}
          onChangeText={setSearchText}
          returnKeyType="done"
          onSubmitEditing={handleCreateAndAddTag}
          autoFocus={false}
          autoCorrect={false}
          autoCapitalize="none"
        />
        {searchText.length > 0 && !exactMatch && (
          <TouchableOpacity
            style={styles.createButton}
            onPress={handleCreateAndAddTag}
            accessibilityLabel={t("tags.createA11y", { name: searchText })}
          >
            <Ionicons name="add-circle" size={24} color={Colors.primary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Error */}
      {error && (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle-outline" size={16} color={Colors.error} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Tag list */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : (
        <>
          {filteredTags.length > 0 && (
            <Text style={styles.sectionLabel}>{t("tags.otherHeading")}</Text>
          )}
          <View style={styles.listContainer}>
            <FlatList
              data={filteredTags}
              keyExtractor={(item) => item.id}
              renderItem={renderTagItem}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={styles.listContent}
            />
          </View>
        </>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
  },
  dragHandleContainer: {
    width: "100%",
    alignItems: "center",
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  dragHandle: {
    width: 48,
    height: 6,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.outlineVariant,
    opacity: 0.5,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.3,
  },
  saveButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.primary,
  },
  selectedChipsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surfaceContainerHigh,
    borderRadius: BorderRadius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    gap: Spacing.xs,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
  },
  chipText: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  inputContainer: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    marginBottom: Spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    paddingVertical: Spacing.md,
    paddingStart: Spacing.md,
    paddingEnd: Spacing.md,
    ...Shadows.soft,
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  inputAccent: {
    width: 2,
    height: 20,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.full,
    marginEnd: Spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    padding: 0,
  },
  createButton: {
    marginStart: Spacing.sm,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.lg,
  },
  errorText: {
    flex: 1,
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  sectionLabel: {
    fontSize: Typography.small.fontSize,
    fontWeight: "700",
    color: Colors.textMuted,
    letterSpacing: 1.2,
    paddingHorizontal: Spacing.lg + Spacing.sm,
    marginBottom: Spacing.md,
  },
  listContainer: {
    flex: 1,
    marginHorizontal: Spacing.lg,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: 24,
    overflow: "hidden",
    ...Shadows.soft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.outlineVariant,
  },
  listContent: {
    paddingVertical: 0,
  },
  tagRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.outlineVariant,
  },
  tagRowSelected: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  tagName: {
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
  },
  tagNameSelected: {
    fontWeight: "600",
  },
  tagRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  tagCount: {
    fontSize: Typography.label.fontSize,
    color: Colors.outline,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});
