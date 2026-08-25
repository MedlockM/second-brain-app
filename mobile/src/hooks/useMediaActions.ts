/**
 * The behaviour behind the long-press menu of a media vignette in Library:
 * which media it targets, where "Move" goes, and what "Delete" actually does.
 *
 * Lives here rather than in `MediaActionsSheet` so the two Library surfaces —
 * the `All media` list of the library tab and the sources list inside a
 * collection — share one implementation of the destructive path instead of
 * two confirmations that can drift apart. Each surface only supplies what it
 * alone knows: how to drop a row from the list it holds.
 *
 * Moving is delegated whole to the existing `/media/collection` picker: it takes
 * `mediaItemId` / `currentCollectionId`, creates a collection on the fly, and
 * issues the `PATCH /api/media/:id` itself. Both callers refetch on focus, so
 * the list already reflects the move by the time the picker is popped — there is
 * nothing to report back.
 */

import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { t } from "../i18n";
import type { MediaListItem } from "../types/media";
import type { MediaActionsSheetProps } from "../components/MediaActionsSheet";

/** The one media the open sheet is about. */
interface MediaActionTarget {
  mediaItemId: string;
  title: string;
  /** `null` means Unsorted — what the picker preselects for such an item. */
  folderId: string | null;
}

export interface MediaActionsController {
  /** Long-press handler to hand to a media vignette. */
  open: (item: MediaListItem) => void;
  /** Spread onto `<MediaActionsSheet />`. */
  sheetProps: MediaActionsSheetProps;
}

export function useMediaActions(options: {
  /**
   * Called once the backend has confirmed the deletion, never before: the row
   * must not leave a list while the media may still exist.
   */
  onDeleted: (mediaItemId: string) => void;
}): MediaActionsController {
  const { onDeleted } = options;
  const router = useRouter();

  // Visibility is tracked apart from the target on purpose. The sheet defers the
  // move navigation until it has finished dismissing, so the handler runs after
  // `onClose` — clearing the target there would leave it with nothing to move.
  const [target, setTarget] = useState<MediaActionTarget | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const open = useCallback((item: MediaListItem) => {
    setTarget({
      mediaItemId: item.media_item_id,
      // Backend titles are never empty (task-266); the fallback is for the
      // header of a sheet that must always name something.
      title: item.title?.trim() || t("common.untitled"),
      folderId: item.folder_id ?? null,
    });
    setIsVisible(true);
  }, []);

  const close = useCallback(() => {
    // A deletion in flight owns the sheet: dismissing it would strand the
    // spinner and leave the user unsure whether the call went out.
    if (isDeleting) return;
    setIsVisible(false);
  }, [isDeleting]);

  const handleMove = useCallback(() => {
    if (!target) return;
    const params = new URLSearchParams();
    params.set("mode", "move");
    params.set("mediaItemId", target.mediaItemId);
    if (target.folderId) {
      params.set("currentCollectionId", target.folderId);
    }
    router.push(`/media/collection?${params.toString()}`);
  }, [router, target]);

  const runDelete = useCallback(
    async (item: MediaActionTarget) => {
      setIsDeleting(true);
      try {
        await MediaService.deleteMedia(item.mediaItemId);
        setIsVisible(false);
        onDeleted(item.mediaItemId);
      } catch (err) {
        // The row stays exactly where it is: the media is still in the library,
        // and a list that hides it would be lying about what the server holds.
        //
        // The sheet stays open too, and not only so the user can try again: on
        // iOS an alert is presented by the top-most view controller, which is
        // the sheet's — closing it in the same frame would dismiss the alert
        // along with it, and the failure would go unreported.
        Alert.alert(
          t("common.error"),
          getFriendlyErrorMessage(err, {
            fallback: t("mediaActions.deleteFailed"),
          }),
        );
      } finally {
        setIsDeleting(false);
      }
    },
    [onDeleted],
  );

  const handleDelete = useCallback(() => {
    if (!target || isDeleting) return;
    const item = target;
    // Nothing leaves the device before this is answered. The confirmation names
    // the media and says the deletion cannot be taken back — the grace window
    // is a support affordance, not an undo the UI can offer.
    Alert.alert(
      t("mediaActions.deleteTitle"),
      t("mediaActions.deleteBody", { title: item.title }),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("common.delete"),
          style: "destructive",
          onPress: () => {
            void runDelete(item);
          },
        },
      ],
    );
  }, [target, isDeleting, runDelete]);

  return {
    open,
    sheetProps: {
      visible: isVisible,
      title: target?.title ?? "",
      isDeleting,
      onClose: close,
      onMove: handleMove,
      onDelete: handleDelete,
    },
  };
}
