/**
 * "Which collection?" for the unsorted-review triage, presented as a sheet.
 *
 * The body is `CollectionPickerView` — the same search, the same tree, the same
 * inline creation the share flow and the media detail screen open. The one
 * deliberate omission is the "Unsorted" destination: every card in the triage
 * queue already sits in the default folder, so offering to put it back there
 * would be a no-op dressed as a decision. Everything else about the picker is
 * shared, and a change to it lands in all three places at once.
 *
 * A plain RN `<Modal transparent animationType="slide">` on the `AddSourceSheet`
 * pattern, deliberately not a router screen. It is rendered *from inside* a
 * full-screen route modal, and a React Native modal is presented above whatever
 * is on screen without a navigator having to nest one presentation inside
 * another — which is exactly what makes this shape available to a screen that is
 * itself a modal. The panel takes nearly the full height so the list has the
 * same room it has as a screen.
 *
 * Unlike the picker's screen host, a tap here *is* the answer: the assignment
 * goes out immediately and the sheet closes. There is no Save button because
 * there is nothing to come back to — the media leaves the queue.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  BorderRadius,
  Colors,
  Shadows,
  Spacing,
} from "../constants/theme";
import { t } from "../i18n";
import { CollectionPickerView } from "./CollectionPickerView";
import { ScreenHeader, HeaderIconButton } from "./ScreenHeader";
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

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // A fresh opening starts clean: no stale failure from the previous media.
  // Deferred by a tick, the shape the rest of the app uses — `setState` reached
  // synchronously from an effect cascades a render, and the lint rule that says
  // so is on.
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(() => {
      setError(null);
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

  const handleSelect = useCallback(
    (collectionId: string | null) => {
      // The picker runs here without its "Unsorted" row, so a null selection
      // cannot be reached; filing into the default folder is not a destination.
      if (collectionId === null) return;
      void assign(collectionId);
    },
    [assign],
  );

  const handleCollectionCreated = useCallback(
    (created: Collection) => {
      onCollectionCreated(created);
      // Create *then* select, without a second tap: someone who had to invent a
      // collection has already told us where the media goes.
      void assign(created.id);
    },
    [assign, onCollectionCreated],
  );

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
          style={[styles.sheet, { paddingBottom: insets.bottom }]}
        >
          <View style={styles.handle} />

          {/* The picker's screen header, minus the Save button it has no use
              for: the trailing slot carries the saving spinner instead. */}
          <ScreenHeader
            title={t("collectionPicker.title")}
            titleStyle={styles.headerTitle}
            leading={
              <HeaderIconButton
                icon="arrow-back"
                onPress={onClose}
                testID="collection-save-sheet-close"
                accessibilityLabel={t("common.goBack")}
              />
            }
            trailing={
              <View style={styles.headerAction}>
                {isSaving ? <ActivityIndicator color={Colors.primary} /> : null}
              </View>
            }
          />

          <CollectionPickerView
            collections={collections}
            selectedId={null}
            showUnsorted={false}
            busy={isSaving}
            error={error}
            onSelect={handleSelect}
            onCollectionCreated={handleCollectionCreated}
            onCreateFailed={setError}
          />
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
  // Tall on purpose: the picker is a browsable tree, not a three-item menu, and
  // the sliver of the screen left above it is what says a sheet can be dismissed.
  sheet: {
    height: "94%",
    backgroundColor: Colors.surface,
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    paddingTop: Spacing.sm,
    ...Shadows.soft,
  },
  handle: {
    alignSelf: "center",
    width: Spacing.xl,
    height: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    marginTop: Spacing.sm,
  },
  // Only the colour departs from the shared header's title.
  headerTitle: {
    color: Colors.primary,
  },
  headerAction: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
});
