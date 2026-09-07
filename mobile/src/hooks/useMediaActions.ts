/**
 * The behaviour behind the actions menu of a media item: which media it targets,
 * where "Move" goes, what "Rename" writes, and what "Delete" actually does.
 *
 * Lives here rather than in the menu component so every surface offering those
 * actions shares one implementation of the destructive path and of the rename
 * instead of three that can drift apart: the `All media` list of the library tab,
 * the sources list inside a folder, and the `…` in the header of a media
 * item's own page. Each surface only supplies what it alone knows — how to drop a
 * row from the list it holds and how to put a new title on one, or, on a detail
 * screen holding no list, how to leave once the thing it shows is gone.
 *
 * `useFolderActions` is the sibling of this hook for a folder, and both
 * feed the same `AnchoredContextMenu` and the same `RenameDialog`.
 *
 * Moving is delegated whole to the existing `/media/folder` picker: it takes
 * `mediaItemId` / `currentFolderId`, creates a folder on the fly, and
 * issues the `PATCH /api/media/:id` itself. Every caller refetches on focus, so
 * the surface already reflects the move by the time the picker is popped — there
 * is nothing to report back. Renaming is the opposite case: it never leaves the
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
  AnchoredContextMenuProps,
  AnchorRect,
  ContextMenuAction,
} from "../components/AnchoredContextMenu";
import type { RenameDialogProps } from "../components/RenameDialog";

/**
 * The server's own ceiling (`MAX_TITLE_LENGTH` in
 * `media_summarizer/core/media_ingestion/title_derivation.py`), mirrored here so
 * the field stops accepting characters the `PATCH` would reject.
 */
const MAX_TITLE_LENGTH = 120;

/**
 * All this hook needs of the media it acts on: an id to write to, a name to seed
 * the rename field with, and the folder the picker should preselect.
 *
 * Both shapes the app holds satisfy it — the `MediaListItem` of a library row and
 * the `MediaItemContract` of the detail screen — which is what lets one hook serve
 * a long-pressed row and a header button without either surface converting to the
 * other's shape. The target stays a type parameter rather than being narrowed to
 * this interface, because the surface gets it back to redraw whatever it pressed.
 */
export interface MediaActionSource {
  media_item_id: string;
  title?: string | null;
  folder_id?: string | null;
}

/** The one media the open menu is about. */
interface MediaActionTarget<T> {
  mediaItemId: string;
  title: string;
  /** `null` means Unsorted — what the picker preselects for such an item. */
  folderId: string | null;
  /** Kept whole so the menu can redraw the thing it was opened from. */
  item: T;
}

/** What the surfaces spread onto the menu, minus what only they can answer. */
type MenuProps<T> = Omit<AnchoredContextMenuProps<T>, "renderPreview">;

export interface MediaActionsController<T> {
  /**
   * Opens the menu on a media, with the window rect of the view the gesture
   * landed on — the menu is anchored to it. A long press on a list row, or a tap
   * on the `…` of a header.
   */
  open: (item: T, anchor: AnchorRect) => void;
  /** Spread onto `<AnchoredContextMenu />`, alongside a `renderPreview`. */
  menuProps: MenuProps<T>;
  /** Spread onto `<RenameDialog />`. */
  renameProps: RenameDialogProps;
}

export function useMediaActions<
  T extends MediaActionSource = MediaListItem,
>(options: {
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
  /**
   * Whether the menu offers "Move". Default `true`, and `false` on exactly one
   * surface: the header of a media item's own page, whose folder button sits one
   * slot to the left of the `…` and already opens this very picker. A row
   * duplicating the control next to it would only make the menu longer.
   */
  canMove?: boolean;
}): MediaActionsController<T> {
  const { onDeleted, onRenamed, canMove = true } = options;
  const router = useRouter();

  // Visibility is tracked apart from the target on purpose. The menu defers the
  // move and the rename until it has finished dismissing, so those handlers run
  // after `onClose` — clearing the target there would leave them with nothing
  // to act on.
  const [target, setTarget] = useState<MediaActionTarget<T> | null>(null);
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

  const open = useCallback((item: T, rect: AnchorRect) => {
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
      params.set("currentFolderId", target.folderId);
    }
    router.push(`/media/folder?${params.toString()}`);
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
    async (item: MediaActionTarget<T>) => {
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

  const moveAction: ContextMenuAction = {
    key: "move",
    icon: "folder-outline",
    label: t("mediaActions.move.label"),
    onPress: handleMove,
    closesMenu: true,
    testID: "media-actions-move",
  };
  const renameAction: ContextMenuAction = {
    key: "rename",
    icon: "pencil-outline",
    label: t("mediaActions.rename.label"),
    onPress: handleRename,
    closesMenu: true,
    testID: "media-actions-rename",
  };
  const deleteAction: ContextMenuAction = {
    key: "delete",
    icon: "trash-outline",
    label: t("mediaActions.delete.label"),
    onPress: handleDelete,
    destructive: true,
    isBusy: isDeleting,
    // The confirmation and the spinner both live in the menu, so it stays.
    closesMenu: false,
    testID: "media-actions-delete",
  };

  return {
    open,
    menuProps: {
      visible: isMenuVisible,
      target: target?.item ?? null,
      anchor,
      actions: canMove
        ? [moveAction, renameAction, deleteAction]
        : [renameAction, deleteAction],
      isBusy: isDeleting,
      onClose: closeMenu,
      testIDPrefix: "media-actions",
    },
    renameProps: {
      visible: isRenameVisible,
      heading: t("mediaActions.rename.title"),
      placeholder: t("mediaActions.rename.placeholder"),
      maxLength: MAX_TITLE_LENGTH,
      value: renameDraft,
      onChangeText: changeRenameDraft,
      isSaving: isRenaming,
      errorMessage: renameError,
      onClose: closeRename,
      onSubmit: submitRename,
      testIDPrefix: "media-rename",
    },
  };
}
