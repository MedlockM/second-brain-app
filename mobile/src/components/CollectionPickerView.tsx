/**
 * "Which collection?" — the one answer to that question in the app.
 *
 * Search bar, the optional "Unsorted" destination, then "My collections" as a
 * navigable tree with an inline way to create one. Extracted from
 * `app/media/collection.tsx` so the share flow, the media detail screen and the
 * unsorted-review triage all ask it the same way instead of each growing its own
 * list; the screen keeps the header (back / title / save), which is the only
 * part that legitimately differs between hosts.
 *
 * The tree, and not a flat list of breadcrumbs: the picker is also how someone
 * browses what they already have, and a nested collection reads as nested here.
 *
 * Selection is reported, never applied: the host owns what "selected" means —
 * an immediate assignment in the sheet, a deferred one behind Save on the media
 * screen. Creation is the exception, since it has to hit the backend to produce
 * an id; the created collection is handed back through `onCollectionCreated` and
 * the host decides whether it becomes the selection.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  Typography,
} from "../constants/theme";
import { t } from "../i18n";
import {
  DEFAULT_COLLECTION_TINT,
  buildCollectionTree,
  type CollectionNode,
} from "../lib/collectionTree";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { OrganizationService } from "../services/organizationService";
import type { Collection } from "../types/organization";

export interface CollectionPickerViewProps {
  /** The user's folders, flat, as the backend returns them. */
  collections: Collection[];
  /** Currently picked destination; `null` is "Unsorted". */
  selectedId: string | null;
  /**
   * Whether "Unsorted" is offered as a destination. False in the triage flow,
   * where every card already sits in the default folder and putting it back
   * would be a no-op dressed as a decision.
   */
  showUnsorted?: boolean;
  /** Assignment in flight upstream: rows stop responding rather than queue up. */
  busy?: boolean;
  isLoading?: boolean;
  /** Banner shown above the list. The host owns it, including failures it caused. */
  error?: string | null;
  /** A destination was picked. `null` means "Unsorted". */
  onSelect: (collectionId: string | null) => void;
  /** A collection was created here; the host refreshes its own list from it. */
  onCollectionCreated: (collection: Collection) => void;
  /** Creation failed; the message is ready to display. */
  onCreateFailed: (message: string) => void;
}

export function CollectionPickerView({
  collections,
  selectedId,
  showUnsorted = true,
  busy = false,
  isLoading = false,
  error = null,
  onSelect,
  onCollectionCreated,
  onCreateFailed,
}: CollectionPickerViewProps): React.JSX.Element {
  const createInputRef = useRef<TextInput>(null);

  const [searchText, setSearchText] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [isSubmittingCreate, setIsSubmittingCreate] = useState(false);
  // What the user has *folded*, not what is unfolded: the tree opens fully and
  // stays that way unless someone closes a branch, so a collection three levels
  // down is visible without a hunt.
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

  const roots = useMemo(
    () => buildCollectionTree(collections).roots,
    [collections],
  );

  const handleToggleExpand = useCallback((collectionId: string) => {
    setCollapsedIds((prev) => {
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
    setTimeout(() => createInputRef.current?.focus(), 100);
  }, []);

  const handleCancelCreate = useCallback(() => {
    setIsCreating(false);
    setNewCollectionName("");
    Keyboard.dismiss();
  }, []);

  const handleConfirmCreate = useCallback(async () => {
    const name = newCollectionName.trim();
    if (!name || isSubmittingCreate) {
      handleCancelCreate();
      return;
    }
    Keyboard.dismiss();
    setIsSubmittingCreate(true);
    try {
      const created = await OrganizationService.createCollection(name);
      setIsCreating(false);
      setNewCollectionName("");
      onCollectionCreated(created);
    } catch (err) {
      onCreateFailed(
        getFriendlyErrorMessage(err, {
          fallback: t("collectionPicker.createFailed"),
        }),
      );
    } finally {
      setIsSubmittingCreate(false);
    }
  }, [
    newCollectionName,
    isSubmittingCreate,
    handleCancelCreate,
    onCollectionCreated,
    onCreateFailed,
  ]);

  const displayCollections = useMemo(
    () => filterCollections(roots, searchText),
    [roots, searchText],
  );

  const renderCollectionItem = (
    collection: CollectionNode,
    depth: number,
  ): React.ReactNode => {
    const hasChildren = collection.children.length > 0;
    const isExpanded = !collapsedIds.has(collection.id);
    const isSelected = selectedId === collection.id;

    return (
      <View key={collection.id}>
        <Pressable
          style={({ pressed }) => [
            styles.collectionRow,
            { paddingStart: Spacing.md + depth * 40 },
            isSelected && styles.collectionRowSelected,
            pressed && styles.collectionRowSelected,
            busy && styles.rowDisabled,
          ]}
          onPress={() => onSelect(collection.id)}
          disabled={busy}
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
              numberOfLines={1}
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
              <Pressable
                onPress={() => handleToggleExpand(collection.id)}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                accessibilityRole="button"
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
              </Pressable>
            )}
            {isSelected && !hasChildren && (
              <Ionicons
                name="checkmark-circle"
                size={20}
                color={Colors.primary}
              />
            )}
          </View>
        </Pressable>

        {hasChildren && isExpanded && (
          <View>
            {collection.children.map((child) =>
              renderCollectionItem(child, depth + 1),
            )}
          </View>
        )}
      </View>
    );
  };

  return (
    <>
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

      {error ? (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle-outline" size={16} color={Colors.error} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

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
          {showUnsorted && (
            <Pressable
              style={({ pressed }) => [
                styles.unsortedCard,
                selectedId === null && styles.unsortedCardSelected,
                pressed && styles.rowPressed,
                busy && styles.rowDisabled,
              ]}
              onPress={() => onSelect(null)}
              disabled={busy}
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
                <Text style={styles.unsortedLabel} numberOfLines={1}>
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
            </Pressable>
          )}

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>
              {t("collectionPicker.myCollections")}
            </Text>
            <Pressable
              style={styles.addButton}
              onPress={handleShowCreateInput}
              disabled={busy || isCreating}
              testID="collection-picker-new-collection"
              accessibilityLabel={t("collectionPicker.createA11y")}
              accessibilityRole="button"
            >
              <Ionicons name="add" size={22} color={Colors.primary} />
            </Pressable>
          </View>

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
                onSubmitEditing={() => void handleConfirmCreate()}
                autoCapitalize="sentences"
                editable={!isSubmittingCreate}
              />
              {isSubmittingCreate ? (
                <ActivityIndicator size="small" color={Colors.primary} />
              ) : (
                <>
                  <Pressable
                    onPress={() => void handleConfirmCreate()}
                    style={styles.createAction}
                    accessibilityRole="button"
                    accessibilityLabel={t("collectionPicker.confirm")}
                  >
                    <Ionicons name="checkmark" size={20} color={Colors.primary} />
                  </Pressable>
                  <Pressable
                    onPress={handleCancelCreate}
                    style={styles.createAction}
                    accessibilityRole="button"
                    accessibilityLabel={t("common.cancel")}
                  >
                    <Ionicons name="close" size={20} color={Colors.textMuted} />
                  </Pressable>
                </>
              )}
            </View>
          )}

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
    </>
  );
}

/**
 * Keep a branch when its own name matches, or when something under it does —
 * a parent that only survives through a child keeps that child's filtered
 * subtree, so the trail down to the match stays visible.
 */
function filterCollections(
  nodes: CollectionNode[],
  query: string,
): CollectionNode[] {
  if (!query.trim()) return nodes;
  const lower = query.toLowerCase();
  return nodes.reduce<CollectionNode[]>((acc, node) => {
    const nameMatch = node.name.toLowerCase().includes(lower);
    const filteredChildren = filterCollections(node.children, query);
    if (nameMatch || filteredChildren.length > 0) {
      acc.push({
        ...node,
        children: nameMatch ? node.children : filteredChildren,
      });
    }
    return acc;
  }, []);
}

const styles = StyleSheet.create({
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
    flex: 1,
  },
  unsortedLabel: {
    flexShrink: 1,
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
    // The row's left half is already `flex: 1`; this is what lets the name give
    // ground inside it instead of pushing the count and chevron off the row.
    flexShrink: 1,
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
  rowPressed: {
    opacity: 0.85,
  },
  rowDisabled: {
    opacity: 0.5,
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
  createAction: {
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
