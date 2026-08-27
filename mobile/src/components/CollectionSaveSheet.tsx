/**
 * "Which collection?" as a bottom sheet: the flat list of the user's collections
 * as breadcrumbs, plus an inline way to create one, and nothing else.
 *
 * A plain RN `<Modal transparent animationType="slide">` on the `AddSourceSheet`
 * pattern, deliberately not a router screen. It is rendered *from inside* a
 * full-screen route modal, and a React Native modal is presented above whatever
 * is on screen without a navigator having to nest one presentation inside
 * another — which is exactly what makes this shape available to a screen that is
 * itself a modal. No third-party sheet library either: this is a scrim, a
 * rounded panel and a list.
 *
 * The list is flat and not a tree because the question is answered in two seconds
 * and does not involve browsing; the trail (`Work / Reading / AI`) is what tells
 * two identically named leaves apart.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
  TouchTarget,
  Typography,
} from "../constants/theme";
import { t } from "../i18n";
import { flattenCollectionPaths } from "../lib/collectionTree";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { OrganizationService } from "../services/organizationService";
import type { Collection } from "../types/organization";

export interface CollectionSaveSheetProps {
  visible: boolean;
  /** The media being filed. Null closes the sheet's business, not the sheet. */
  mediaItemId: string | null;
  /** Collections the host screen already holds — no fetch of our own. */
  collections: Collection[];
  onClose: () => void;
  /**
   * A collection was created here, so the host can keep its own list current
   * without refetching.
   */
  onCollectionCreated: (collection: Collection) => void;
  /**
   * The assignment went through. Called once the sheet has finished dismissing,
   * never before — see `runAfterClose`.
   */
  onSaved: (mediaItemId: string) => void;
}

export function CollectionSaveSheet({
  visible,
  mediaItemId,
  collections,
  onClose,
  onCollectionCreated,
  onSaved,
}: CollectionSaveSheetProps): React.JSX.Element {
  const insets = useSafeAreaInsets();
  const createInputRef = useRef<TextInput>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const pendingSaved = useRef<(() => void) | null>(null);

  /**
   * Run something only once this modal is really gone.
   *
   * The same deferral `AddSourceSheet` uses, for the same reason in a different
   * shape: on iOS the dismissal is animated, and the follow-up here mutates the
   * screen *underneath* — an item leaves the queue and the pager is re-anchored
   * with a non-animated `scrollTo`. Firing that while a modal is still sliding
   * away runs it against a covered view and leaves the pager between two pages.
   * It is also what lets "create, then select" land as one gesture: the creation
   * and the assignment both complete here, and only the visible consequence
   * waits for the sheet to be off screen. Android fires no `onDismiss` and its
   * modal is gone by the time the handler returns.
   */
  const runAfterClose = useCallback(
    (action: () => void) => {
      if (Platform.OS === "ios") {
        pendingSaved.current = action;
        onClose();
        return;
      }
      onClose();
      action();
    },
    [onClose],
  );

  const handleDismissed = useCallback(() => {
    const action = pendingSaved.current;
    pendingSaved.current = null;
    action?.();
  }, []);

  // A fresh opening starts clean: no stale failure, no half-typed name from the
  // previous media. Deferred by a tick, the shape the rest of the app uses —
  // `setState` reached synchronously from an effect cascades a render, and the
  // lint rule that says so is on.
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(() => {
      setError(null);
      setIsCreating(false);
      setNewName("");
      setIsSaving(false);
    }, 0);
    return () => clearTimeout(timer);
  }, [visible]);

  const assign = useCallback(
    async (collectionId: string) => {
      if (!mediaItemId || isSaving) return;
      setIsSaving(true);
      setError(null);
      try {
        await OrganizationService.setMediaCollection(mediaItemId, collectionId);
        const savedId = mediaItemId;
        runAfterClose(() => onSaved(savedId));
      } catch (err) {
        // The sheet stays open and says why: the media is still unsorted, and a
        // queue that dropped it would be lying about what the server holds. An
        // inline banner rather than an `Alert` — on iOS an alert presented over a
        // modal that is on its way out goes with it, unread.
        setError(
          getFriendlyErrorMessage(err, {
            fallback: t("collectionPicker.saveFailed"),
          }),
        );
      } finally {
        setIsSaving(false);
      }
    },
    [mediaItemId, isSaving, onSaved, runAfterClose],
  );

  const handleShowCreate = useCallback(() => {
    setIsCreating(true);
    setNewName("");
    setTimeout(() => createInputRef.current?.focus(), 100);
  }, []);

  const handleConfirmCreate = useCallback(async () => {
    const name = newName.trim();
    if (!name || isSaving) {
      setIsCreating(false);
      setNewName("");
      return;
    }
    Keyboard.dismiss();
    setIsSaving(true);
    setError(null);
    try {
      const created = await OrganizationService.createCollection(name);
      onCollectionCreated(created);
      setIsCreating(false);
      setNewName("");
      // Create *then* select, without a second tap: someone who had to invent a
      // collection has already told us where the media goes.
      if (mediaItemId) {
        await OrganizationService.setMediaCollection(mediaItemId, created.id);
        const savedId = mediaItemId;
        runAfterClose(() => onSaved(savedId));
      }
    } catch (err) {
      setError(
        getFriendlyErrorMessage(err, {
          fallback: t("collectionPicker.createFailed"),
        }),
      );
    } finally {
      setIsSaving(false);
    }
  }, [
    newName,
    isSaving,
    mediaItemId,
    onCollectionCreated,
    onSaved,
    runAfterClose,
  ]);

  const handleCancelCreate = useCallback(() => {
    setIsCreating(false);
    setNewName("");
    Keyboard.dismiss();
  }, []);

  const paths = flattenCollectionPaths(collections);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      onDismiss={handleDismissed}
      statusBarTranslucent
    >
      <View style={styles.root}>
        {/* Scrim. The design system has no scrim token, so this is textMain at
            35% — the only literal colour in this file, kept in sync with the
            add-source and media-actions sheets. */}
        <Pressable
          style={styles.backdrop}
          onPress={onClose}
          accessibilityLabel={t("common.dismiss")}
          accessibilityRole="button"
        />

        <View
          style={[styles.sheet, { paddingBottom: insets.bottom + Spacing.lg }]}
        >
          <View style={styles.handle} />

          <View style={styles.header}>
            <Text style={styles.title}>{t("unsortedReview.sheetTitle")}</Text>
            {isSaving ? <ActivityIndicator color={Colors.textMain} /> : null}
          </View>

          {error ? (
            <View style={styles.errorBanner}>
              <Ionicons
                name="alert-circle-outline"
                size={16}
                color={Colors.error}
              />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          {isCreating ? (
            <View style={styles.createRow}>
              <Ionicons name="folder-outline" size={20} color={Colors.primary} />
              <TextInput
                ref={createInputRef}
                style={styles.createInput}
                placeholder={t("collectionPicker.namePlaceholder")}
                placeholderTextColor={Colors.textMuted}
                value={newName}
                onChangeText={setNewName}
                returnKeyType="done"
                onSubmitEditing={() => void handleConfirmCreate()}
                autoCapitalize="sentences"
                editable={!isSaving}
              />
              <Pressable
                onPress={() => void handleConfirmCreate()}
                disabled={isSaving}
                style={styles.createAction}
                accessibilityLabel={t("collectionPicker.confirm")}
                accessibilityRole="button"
              >
                <Ionicons name="checkmark" size={22} color={Colors.primary} />
              </Pressable>
              <Pressable
                onPress={handleCancelCreate}
                disabled={isSaving}
                style={styles.createAction}
                accessibilityLabel={t("common.cancel")}
                accessibilityRole="button"
              >
                <Ionicons name="close" size={22} color={Colors.textMuted} />
              </Pressable>
            </View>
          ) : (
            <Pressable
              style={({ pressed }) => [
                styles.newCollectionRow,
                pressed && styles.rowPressed,
              ]}
              onPress={handleShowCreate}
              disabled={isSaving}
              testID="unsorted-review-new-collection"
              accessibilityLabel={t("collectionPicker.createA11y")}
              accessibilityRole="button"
            >
              <View style={styles.rowIcon}>
                <Ionicons name="add" size={22} color={Colors.textMain} />
              </View>
              <Text style={styles.rowLabel}>
                {t("unsortedReview.newCollection")}
              </Text>
            </Pressable>
          )}

          <ScrollView
            style={styles.list}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {paths.length === 0 ? (
              <Text style={styles.emptyText}>{t("collections.empty")}</Text>
            ) : (
              paths.map((collection) => (
                <Pressable
                  key={collection.id}
                  style={({ pressed }) => [
                    styles.collectionRow,
                    pressed && styles.rowPressed,
                    isSaving && styles.rowDisabled,
                  ]}
                  onPress={() => void assign(collection.id)}
                  disabled={isSaving}
                  accessibilityLabel={collection.path}
                  accessibilityRole="button"
                >
                  <Ionicons
                    name="folder-outline"
                    size={20}
                    color={Colors.primary}
                  />
                  <Text style={styles.collectionPath} numberOfLines={2}>
                    {collection.path}
                  </Text>
                </Pressable>
              ))
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(43, 45, 66, 0.35)",
  },
  sheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    gap: Spacing.sm,
    ...Shadows.soft,
  },
  handle: {
    alignSelf: "center",
    width: Spacing.xl,
    height: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    marginBottom: Spacing.md,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: Spacing.md,
    marginBottom: Spacing.xs,
  },
  title: {
    flex: 1,
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
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
  newCollectionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
  },
  rowIcon: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  rowLabel: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  rowPressed: {
    backgroundColor: Colors.surfaceContainerHigh,
  },
  rowDisabled: {
    opacity: 0.5,
  },
  createRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.comfortable,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.xl,
  },
  createInput: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    padding: 0,
  },
  createAction: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  // Capped so a long list cannot grow the sheet past the screen; the panel keeps
  // its own header and the list scrolls inside it.
  list: {
    maxHeight: 280,
  },
  listContent: {
    gap: Spacing.xs,
    paddingBottom: Spacing.xs,
  },
  collectionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    minHeight: TouchTarget.minimum,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surfaceContainerLow,
  },
  collectionPath: {
    flex: 1,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
  },
  emptyText: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    paddingVertical: Spacing.lg,
  },
});
