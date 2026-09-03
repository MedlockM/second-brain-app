/**
 * The behaviour behind the long-press menu of a media vignette in Library:
 * which media it targets, where "Move" goes, what "Rename" writes, and what
 * "Delete" actually does.
 *
 * Lives here rather than in the menu component so the two Library surfaces —
 * the `All media` list of the library tab and the sources list inside a
 * collection — share one implementation of the destructive path and of the
 * rename instead of two that can drift apart. Each surface only supplies what it
 * alone knows: how to drop a row from the list it holds, and how to put a new
 * title on one.
 *
 * Moving is delegated whole to the existing `/media/collection` picker: it takes
 * `mediaItemId` / `currentCollectionId`, creates a collection on the fly, and
 * issues the `PATCH /api/media/:id` itself. Both callers refetch on focus, so
 * the list already reflects the move by the time the picker is popped — there is
 * nothing to report back. Renaming is the opposite case: it never leaves the
 * screen, so the new title is handed back to the surface directly.
 */

import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";
import { MediaService } from "../services/mediaService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { t } from "../i18n";
import type { MediaListItem } from "../types/media";
import type {
  AnchorRect,
  MediaContextMenuProps,
} from "../components/MediaContextMenu";
import type { MediaRenameDialogProps } from "../components/MediaRenameDialog";

/** The one media the open menu is about. */
interface MediaActionTarget {
  mediaItemId: string;
  title: string;
  /** `null` means Unsorted — what the picker preselects for such an item. */
  folderId: string | null;
  /** Kept whole so the menu can redraw the row it was opened from. */
  item: MediaListItem;
}

/** What the surfaces spread onto the menu, minus what only they can answer. */
type MenuProps = Omit<MediaContextMenuProps, "renderPreview">;

export interface MediaActionsController {
  /**
   * Long-press handler to hand to a media vignette, with the window rect of the
   * row that was pressed — the menu is anchored to it.
   */
  open: (item: MediaListItem, anchor: AnchorRect) => void;
  /** Spread onto `<MediaContextMenu />`, alongside a `renderPreview`. */
  menuProps: MenuProps;
  /** Spread onto `<MediaRenameDialog />`. */
  renameProps: MediaRenameDialogProps;
}

export function useMediaActions(options: {
  /**
   * Called once the backend has confirmed the deletion, never before: the row
   * must not leave a list while the media may still exist.
   */
  onDeleted: (mediaItemId: string) => void;
  /**
   * Called with the title the server stored, so the row shows the new name
   * without waiting for a refetch. Same rule as above: only after the `PATCH`
   * has answered, so the list never displays a name the library does not hold.
   */
  onRenamed: (mediaItemId: string, title: string) => void;
}): MediaActionsController {
  const { onDeleted, onRenamed } = options;
  const router = useRouter();

  // Visibility is tracked apart from the target on purpose. The menu defers the
  // move and the rename until it has finished dismissing, so those handlers run
  // after `onClose` — clearing the target there would leave them with nothing
  // to act on.
  const [target, setTarget] = useState<MediaActionTarget | null>(null);
  const [anchor, setAnchor] = useState<AnchorRect | null>(null);
  const [isMenuVisible, setIsMenuVisible] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [isRenameVisible, setIsRenameVisible] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  // The typed name lives here rather than inside the dialog: it is seeded from
  // the target when the dialog opens, which is a thing only this hook knows, and
  // a field owning it would have to resynchronise itself behind the props on
  // every opening.
  const [renameDraft, setRenameDraft] = useState("");

  const open = useCallback((item: MediaListItem, rect: AnchorRect) => {
    setTarget({
      mediaItemId: item.media_item_id,
      // Backend titles are never empty (task-266); the fallback is for a rename
      // field that must always start from something.
      title: item.title?.trim() || t("common.untitled"),
      folderId: item.folder_id ?? null,
      item,
    });
    setAnchor(rect);
    setIsMenuVisible(true);
  }, []);

  const closeMenu = useCallback(() => {
    // A deletion in flight owns the menu: dismissing it would strand the
    // spinner and leave the user unsure whether the call went out.
    if (isDeleting) return;
    setIsMenuVisible(false);
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

  const handleRename = useCallback(() => {
    if (!target) return;
    setRenameError(null);
    setRenameDraft(target.title);
    setIsRenameVisible(true);
  }, [target]);

  const changeRenameDraft = useCallback((next: string) => {
    setRenameDraft(next);
    // Editing answers the last failure: keeping the message under a field that
    // has since changed would report a problem with a name nobody submitted.
    setRenameError(null);
  }, []);

  const closeRename = useCallback(() => {
    if (isRenaming) return;
    setIsRenameVisible(false);
    setRenameError(null);
  }, [isRenaming]);

  const submitRename = useCallback(
    (title: string) => {
      if (!target || isRenaming) return;
      const item = target;

      // Nothing to write and nothing to report: closing is the honest answer to
      // "rename it to exactly what it is called".
      if (title === item.title) {
        setIsRenameVisible(false);
        return;
      }

      setIsRenaming(true);
      setRenameError(null);
      void (async () => {
        try {
          const response = await MediaService.renameMedia(
            item.mediaItemId,
            title,
          );
          // The server trims and collapses whitespace, so what it answers is the
          // title the library holds — displaying the raw input instead would
          // show a name that is not stored anywhere.
          const stored = response.title?.trim() || title;
          setTarget((current) =>
            current && current.mediaItemId === item.mediaItemId
              ? { ...current, title: stored }
              : current,
          );
          setIsRenameVisible(false);
          onRenamed(item.mediaItemId, stored);
        } catch (err) {
          // The dialog stays open with the typed name intact, and the row keeps
          // the title the library still holds: a list showing a name the `PATCH`
          // refused would be lying about what was saved.
          setRenameError(
            getFriendlyErrorMessage(err, {
              fallback: t("mediaActions.renameFailed"),
            }),
          );
        } finally {
          setIsRenaming(false);
        }
      })();
    },
    [target, isRenaming, onRenamed],
  );

  const runDelete = useCallback(
    async (item: MediaActionTarget) => {
      setIsDeleting(true);
      try {
        await MediaService.deleteMedia(item.mediaItemId);
        setIsMenuVisible(false);
        onDeleted(item.mediaItemId);
      } catch (err) {
        // The row stays exactly where it is: the media is still in the library,
        // and a list that hides it would be lying about what the server holds.
        //
        // The menu stays open too, and not only so the user can try again: on
        // iOS an alert is presented by the top-most view controller, which is
        // the menu's — closing it in the same frame would dismiss the alert
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
    menuProps: {
      visible: isMenuVisible,
      item: target?.item ?? null,
      anchor,
      isDeleting,
      onClose: closeMenu,
      onMove: handleMove,
      onRename: handleRename,
      onDelete: handleDelete,
    },
    renameProps: {
      visible: isRenameVisible,
      value: renameDraft,
      onChangeText: changeRenameDraft,
      isSaving: isRenaming,
      errorMessage: renameError,
      onClose: closeRename,
      onSubmit: submitRename,
    },
  };
}
