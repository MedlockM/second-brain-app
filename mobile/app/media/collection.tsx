import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
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
import { t, useTranslation } from "../../src/i18n";
import { DEFAULT_COLLECTION_TINT } from "../../src/lib/collectionTree";
import { useAuth } from "../../src/contexts/AuthContext";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import { OrganizationService } from "../../src/services/organizationService";
import type { Collection } from "../../src/types/organization";

function buildCollectionTree(collections: Collection[]): {
  treeCollections: Collection[];
  pathById: Map<string, string>;
} {
  const nodes = new Map<string, Collection>();
  const pathById = new Map<string, string>();

  for (const collection of collections) {
    if (collection.is_default) continue;
    nodes.set(collection.id, { ...collection, children: [] });
  }

  const roots: Collection[] = [];
  for (const collection of nodes.values()) {
    const parentId = collection.parent_id ?? collection.parent_folder_id ?? null;
    const parent = parentId ? nodes.get(parentId) : null;
    if (parent) {
      parent.children = [...(parent.children ?? []), collection];
    } else {
      roots.push(collection);
    }
  }

  const assignPaths = (items: Collection[], prefix?: string) => {
    for (const item of items) {
      const path = prefix ? `${prefix} / ${item.name}` : item.name;
      item.path = path;
      pathById.set(item.id, path);
      if (item.children?.length) {
        assignPaths(item.children, path);
      }
    }
  };

  assignPaths(roots);

  return { treeCollections: roots, pathById };
}

/**
 * Collection Selection Screen.
 * Presented as a modal from media detail or share confirmation.
 *
 * Design ref: mobile-design-mockups/s_lection_de_collection/
 *
 * Layout:
 * - Header: back button | "Collection" title | "Save" button
 * - Search bar
 * - "Unsorted" card (default/no-collection option)
 * - "My collections" section with hierarchical folder list
 * - "+" button to create new collection
 */
export default function CollectionScreen() {
  // Copy resolved on render: redraw when the interface language changes.
  useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{
    mode?: string;
    mediaItemId?: string;
    currentCollectionId?: string;
  }>();

  const { isAuthenticated } = useAuth();
  const { selectedFolder, setSelectedFolder } = useShareIntake();
  const isShareMode = params.mode === "share";

  const createInputRef = useRef<TextInput>(null);

  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(
    isShareMode ? selectedFolder?.id ?? null : params.currentCollectionId ?? null,
  );
  const [searchText, setSearchText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");

  // Fetch collections
  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchCollections = async () => {
      try {
        setIsLoading(true);
        const data = await OrganizationService.getUserCollections();
        setCollections(data);
        // Auto-expand collections that have children
        const expanded = new Set<string>();
        const expandWithChildren = (cols: Collection[]) => {
          for (const col of cols) {
            if (col.children && col.children.length > 0) {
              expanded.add(col.id);
              expandWithChildren(col.children);
            }
          }
        };
        expandWithChildren(buildCollectionTree(data).treeCollections);
        setExpandedIds(expanded);
      } catch {
        setError(t("collectionPicker.loadFailed"));
      } finally {
        setIsLoading(false);
      }
    };

    fetchCollections();
  }, [isAuthenticated]);

  const { treeCollections, pathById } = useMemo(
    () => buildCollectionTree(collections),
    [collections],
  );

  const handleBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    }
  }, [router]);

  const handleSelectUnsorted = useCallback(() => {
    setSelectedId(null);
    if (isShareMode) {
      setSelectedFolder(null);
      router.back();
    }
  }, [isShareMode, router, setSelectedFolder]);

  const handleSelectCollection = useCallback(
    (collection: Collection) => {
      setSelectedId(collection.id);
      if (isShareMode) {
        setSelectedFolder({
          id: collection.id,
          path: pathById.get(collection.id) ?? collection.name,
        });
        router.back();
      }
    },
    [isShareMode, pathById, router, setSelectedFolder],
  );

  const handleSave = useCallback(async () => {
    if (!isAuthenticated || !params.mediaItemId) {
      handleBack();
      return;
    }

    try {
      setIsSaving(true);
      await OrganizationService.setMediaCollection(
        params.mediaItemId,
        selectedId,
      );
      handleBack();
    } catch {
      setError(t("collectionPicker.saveFailed"));
      setIsSaving(false);
    }
  }, [isAuthenticated, params.mediaItemId, selectedId, handleBack]);

  const handleToggleExpand = useCallback((collectionId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(collectionId)) {
        next.delete(collectionId);
      } else {
        next.add(collectionId);
      }
      return next;
    });
  }, []);

  const handleShowCreateInput = useCallback(() => {
    setIsCreating(true);
    setNewCollectionName("");
    // Focus the input after render
    setTimeout(() => createInputRef.current?.focus(), 100);
  }, []);

  const handleConfirmCreate = useCallback(async () => {
    const name = newCollectionName.trim();
    if (!name || !isAuthenticated) {
      setIsCreating(false);
      setNewCollectionName("");
      return;
    }

    try {
      const newCollection = await OrganizationService.createCollection(name);
      setCollections((prev) => [...prev, newCollection]);
      setSelectedId(newCollection.id);
      if (isShareMode) {
        setSelectedFolder({
          id: newCollection.id,
          path: newCollection.name,
        });
        router.back();
      }
    } catch {
      setError(t("collectionPicker.createFailed"));
    } finally {
      setIsCreating(false);
      setNewCollectionName("");
      Keyboard.dismiss();
    }
  }, [isAuthenticated, newCollectionName, isShareMode, router, setSelectedFolder]);

  const handleCancelCreate = useCallback(() => {
    setIsCreating(false);
    setNewCollectionName("");
    Keyboard.dismiss();
  }, []);

  // Filter collections based on search
  const filterCollections = (cols: Collection[], query: string): Collection[] => {
    if (!query.trim()) return cols;
    const lower = query.toLowerCase();
    return cols.reduce<Collection[]>((acc, col) => {
      const nameMatch = col.name.toLowerCase().includes(lower);
      const filteredChildren = col.children
        ? filterCollections(col.children, query)
        : [];
      if (nameMatch || filteredChildren.length > 0) {
        acc.push({
          ...col,
          children: filteredChildren.length > 0 ? filteredChildren : col.children,
        });
      }
      return acc;
    }, []);
  };

  const displayCollections = filterCollections(treeCollections, searchText);

  const renderCollectionItem = (
    collection: Collection,
    depth: number = 0,
  ): React.ReactNode => {
    const hasChildren = collection.children && collection.children.length > 0;
    const isExpanded = expandedIds.has(collection.id);
    const isSelected = selectedId === collection.id;

    return (
      <View key={collection.id}>
        <TouchableOpacity
          style={[
            styles.collectionRow,
            { paddingStart: Spacing.md + depth * 40 },
            isSelected && styles.collectionRowSelected,
          ]}
          onPress={() => handleSelectCollection(collection)}
          activeOpacity={0.7}
          accessibilityRole="radio"
          accessibilityState={{ selected: isSelected }}
          accessibilityLabel={collection.name}
        >
          <View style={styles.collectionRowLeft}>
            <Ionicons
              name="folder"
              size={depth === 0 ? 24 : 20}
              color={Colors.primary}
              style={depth > 0 ? { opacity: 0.8 } : undefined}
            />
            <Text
              style={[
                styles.collectionName,
                isSelected && styles.collectionNameSelected,
              ]}
            >
              {collection.name}
            </Text>
          </View>
          <View style={styles.collectionRowRight}>
            {collection.media_count > 0 && (
              <Text style={styles.collectionCount}>
                {collection.media_count}
              </Text>
            )}
            {hasChildren && (
              <TouchableOpacity
                onPress={() => handleToggleExpand(collection.id)}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                accessibilityLabel={
                  isExpanded
                    ? t("collectionPicker.collapse")
                    : t("collectionPicker.expand")
                }
              >
                <Ionicons
                  name={isExpanded ? "chevron-down" : "chevron-forward"}
                  size={20}
                  color={Colors.primary}
                />
              </TouchableOpacity>
            )}
            {isSelected && !hasChildren && (
              <Ionicons
                name="checkmark-circle"
                size={20}
                color={Colors.primary}
              />
            )}
          </View>
        </TouchableOpacity>

        {/* Render children if expanded */}
        {hasChildren && isExpanded && (
          <View>
            {collection.children!.map((child) =>
              renderCollectionItem(child, depth + 1),
            )}
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
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

        <Text style={styles.headerTitle}>{t("collectionPicker.title")}</Text>

        {isShareMode ? (
          <View style={styles.headerActionPlaceholder} />
        ) : (
          <TouchableOpacity
            style={[styles.saveBtn, isSaving && styles.saveBtnDisabled]}
            onPress={handleSave}
            disabled={isSaving}
            accessibilityLabel={t("collectionPicker.saveA11y")}
            accessibilityRole="button"
          >
            {isSaving ? (
              <ActivityIndicator size="small" color={Colors.primary} />
            ) : (
              <Text style={styles.saveBtnText}>{t("common.save")}</Text>
            )}
          </TouchableOpacity>
        )}
      </View>

      {/* Search bar */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color={Colors.textMuted} />
        <TextInput
          style={styles.searchInput}
          placeholder={t("collectionPicker.searchPlaceholder")}
          placeholderTextColor={Colors.textMuted}
          value={searchText}
          onChangeText={setSearchText}
          autoFocus={false}
          autoCorrect={false}
          returnKeyType="search"
          onSubmitEditing={Keyboard.dismiss}
        />
      </View>

      {/* Error */}
      {error && (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle-outline" size={16} color={Colors.error} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : (
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Unsorted option */}
          <TouchableOpacity
            style={[
              styles.unsortedCard,
              selectedId === null && styles.unsortedCardSelected,
            ]}
            onPress={handleSelectUnsorted}
            activeOpacity={0.7}
            accessibilityRole="radio"
            accessibilityState={{ selected: selectedId === null }}
            accessibilityLabel={t("collectionPicker.unsorted")}
          >
            <View style={styles.unsortedLeft}>
              <Ionicons
                name="file-tray-outline"
                size={24}
                color={DEFAULT_COLLECTION_TINT}
              />
              <Text style={styles.unsortedLabel}>
                {t("collectionPicker.unsorted")}
              </Text>
            </View>
            <View style={styles.unsortedRight}>
              {selectedId === null && (
                <Ionicons
                  name="checkmark-circle"
                  size={20}
                  color={Colors.primary}
                />
              )}
            </View>
          </TouchableOpacity>

          {/* Collections section */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>
              {t("collectionPicker.myCollections")}
            </Text>
            <TouchableOpacity
              style={styles.addButton}
              onPress={handleShowCreateInput}
              accessibilityLabel={t("collectionPicker.createA11y")}
              accessibilityRole="button"
            >
              <Ionicons name="add" size={22} color={Colors.primary} />
            </TouchableOpacity>
          </View>

          {/* Inline create collection input */}
          {isCreating && (
            <View style={styles.createInputContainer}>
              <Ionicons name="folder-outline" size={20} color={Colors.primary} />
              <TextInput
                ref={createInputRef}
                style={styles.createInput}
                placeholder={t("collectionPicker.namePlaceholder")}
                placeholderTextColor={Colors.textMuted}
                value={newCollectionName}
                onChangeText={setNewCollectionName}
                returnKeyType="done"
                onSubmitEditing={handleConfirmCreate}
                autoCapitalize="sentences"
              />
              <TouchableOpacity
                onPress={handleConfirmCreate}
                style={styles.createConfirmBtn}
                accessibilityLabel={t("collectionPicker.confirm")}
              >
                <Ionicons name="checkmark" size={20} color={Colors.primary} />
              </TouchableOpacity>
              <TouchableOpacity
                onPress={handleCancelCreate}
                style={styles.createCancelBtn}
                accessibilityLabel={t("common.cancel")}
              >
                <Ionicons name="close" size={20} color={Colors.textMuted} />
              </TouchableOpacity>
            </View>
          )}

          {/* Collections list */}
          <View style={styles.collectionsContainer}>
            {displayCollections.length === 0 ? (
              <View style={styles.emptyState}>
                <Text style={styles.emptyText}>
                  {searchText
                    ? t("collectionPicker.noMatches")
                    : t("collections.empty")}
                </Text>
              </View>
            ) : (
              displayCollections.map((col) => renderCollectionItem(col, 0))
            )}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surface,
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
    color: Colors.primary,
    letterSpacing: -0.3,
  },
  saveBtn: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
  },
  saveBtnDisabled: {
    opacity: 0.5,
  },
  saveBtnText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.primary,
  },
  headerActionPlaceholder: {
    width: 88,
    height: 40,
  },
  searchContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.sm,
    marginBottom: Spacing.md,
    backgroundColor: Colors.surfaceContainerHigh,
    borderRadius: BorderRadius.full,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    ...Shadows.soft,
  },
  searchInput: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    marginStart: Spacing.md,
    padding: 0,
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
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  unsortedCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: Colors.surfaceContainerHigh,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.lg,
    ...Shadows.soft,
  },
  unsortedCardSelected: {
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  unsortedLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  unsortedLabel: {
    fontSize: 18,
    fontWeight: "600",
    color: Colors.textMain,
  },
  unsortedRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.md,
    paddingHorizontal: Spacing.sm,
  },
  sectionTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: "700",
    color: Colors.textMain,
    letterSpacing: -0.3,
  },
  addButton: {
    width: 32,
    height: 32,
    borderRadius: BorderRadius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  collectionsContainer: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: 24,
    overflow: "hidden",
    ...Shadows.soft,
    paddingVertical: Spacing.sm,
  },
  collectionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingEnd: Spacing.md,
    paddingVertical: 14,
    borderRadius: BorderRadius.xl,
    marginHorizontal: Spacing.sm,
  },
  collectionRowSelected: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  collectionRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    flex: 1,
  },
  collectionName: {
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.textMain,
  },
  collectionNameSelected: {
    fontWeight: "600",
    color: Colors.primary,
  },
  collectionRowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  collectionCount: {
    fontSize: Typography.label.fontSize,
    color: Colors.textMuted,
  },
  createInputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    marginBottom: Spacing.md,
    borderWidth: 2,
    borderColor: Colors.primary,
    gap: Spacing.sm,
  },
  createInput: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    padding: 0,
    paddingVertical: Spacing.sm,
  },
  createConfirmBtn: {
    padding: Spacing.xs,
  },
  createCancelBtn: {
    padding: Spacing.xs,
  },
  emptyState: {
    paddingVertical: Spacing.xl,
    alignItems: "center",
  },
  emptyText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
  },
});
