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
import { useAuth } from "../../src/contexts/AuthContext";
import { OrganizationService } from "../../src/services/organizationService";
import type { Tag } from "../../src/types/organization";

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
  const router = useRouter();
  const params = useLocalSearchParams<{
    mediaItemId?: string;
    currentTags?: string;
  }>();

  const { token } = useAuth();
  const inputRef = useRef<TextInput>(null);

  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Parse initial tags from params
  useEffect(() => {
    if (params.currentTags) {
      try {
        const parsed = JSON.parse(params.currentTags);
        if (Array.isArray(parsed)) {
          setSelectedTags(parsed);
        }
      } catch {
        // ignore parse error
      }
    }
  }, [params.currentTags]);

  // Fetch user's tags
  useEffect(() => {
    if (!token) return;

    const fetchTags = async () => {
      try {
        setIsLoading(true);
        const tags = await OrganizationService.getUserTags(token);
        setAllTags(tags);
      } catch {
        setError("Failed to load tags");
      } finally {
        setIsLoading(false);
      }
    };

    fetchTags();
  }, [token]);

  // Filter tags based on search text
  const filteredTags = allTags.filter((tag) =>
    tag.name.toLowerCase().includes(searchText.toLowerCase()),
  );

  // Check if search text matches an existing tag exactly
  const exactMatch = allTags.some(
    (tag) => tag.name.toLowerCase() === searchText.toLowerCase(),
  );

  const handleToggleTag = useCallback((tagName: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagName)
        ? prev.filter((t) => t !== tagName)
        : [...prev, tagName],
    );
  }, []);

  const handleCreateAndAddTag = useCallback(() => {
    const trimmed = searchText.trim();
    if (!trimmed) return;

    // Add to selected tags if not already there
    setSelectedTags((prev) =>
      prev.includes(trimmed) ? prev : [...prev, trimmed],
    );

    // Add to allTags list so it appears in the list
    setAllTags((prev) => {
      if (prev.some((t) => t.name.toLowerCase() === trimmed.toLowerCase())) {
        return prev;
      }
      return [...prev, { id: `new-${trimmed}`, name: trimmed, count: 0 }];
    });

    setSearchText("");
    Keyboard.dismiss();
  }, [searchText]);

  const handleBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    }
  }, [router]);

  const handleSave = useCallback(async () => {
    if (!token || !params.mediaItemId) {
      handleBack();
      return;
    }

    try {
      setIsSaving(true);
      await OrganizationService.updateMediaTags(
        token,
        params.mediaItemId,
        selectedTags,
      );
      handleBack();
    } catch {
      setError("Failed to save tags");
      setIsSaving(false);
    }
  }, [token, params.mediaItemId, selectedTags, handleBack]);

  const renderTagItem = useCallback(
    ({ item }: { item: Tag }) => {
      const isSelected = selectedTags.includes(item.name);
      return (
        <TouchableOpacity
          style={[styles.tagRow, isSelected && styles.tagRowSelected]}
          onPress={() => handleToggleTag(item.name)}
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
    [selectedTags, handleToggleTag],
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
          accessibilityLabel="Go back"
          accessibilityRole="button"
        >
          <Ionicons name="arrow-back" size={22} color={Colors.textMain} />
        </TouchableOpacity>

        <Text style={styles.headerTitle}>
          {selectedTags.length} tag{selectedTags.length !== 1 ? "s" : ""}
        </Text>

        <TouchableOpacity
          style={[styles.saveButton, isSaving && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={isSaving}
          accessibilityLabel="Save tags"
          accessibilityRole="button"
        >
          {isSaving ? (
            <ActivityIndicator size="small" color={Colors.primary} />
          ) : (
            <Text style={styles.saveButtonText}>Done</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Selected tags chips */}
      {selectedTags.length > 0 && (
        <View style={styles.selectedChipsContainer}>
          {selectedTags.map((tagName) => (
            <View key={tagName} style={styles.chip}>
              <Text style={styles.chipText}>{tagName}</Text>
              <TouchableOpacity
                onPress={() => handleToggleTag(tagName)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityLabel={`Remove ${tagName}`}
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
          placeholder="Ajouter un tag"
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
            accessibilityLabel={`Create tag "${searchText}"`}
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
            <Text style={styles.sectionLabel}>AUTRES</Text>
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
    paddingLeft: Spacing.md,
    paddingRight: Spacing.md,
    ...Shadows.soft,
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  inputAccent: {
    width: 2,
    height: 20,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.full,
    marginRight: Spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    padding: 0,
  },
  createButton: {
    marginLeft: Spacing.sm,
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
