/**
 * The behaviour behind the long-press menu of a collection tile in Library: what
 * "Rename" writes, and what "Delete" actually takes with it.
 *
 * The sibling of `useMediaActions`, deliberately shaped the same way and feeding
 * the same two surfaces — `AnchoredContextMenu` for the menu,`RenameDialog` for
 * the field. Two rows here where a media has three: a collection has no "Move",
 * because moving one to another parent is a different gesture with a different
 * picker, and offering it as a row would promise a destination this menu has no
 * way to ask for.
 *
 * The default collection never reaches this hook. The backend refuses to rename
 * or delete it (`folder_service.update_folder` / `delete_folder` both raise on
 * `is_default`), so the tile does not carry a long press at all — a menu whose
 * two rows would both fail is worse than no menu.
 */

import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { OrganizationService } from "../services/organizationService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { DEFAULT_COLLECTION_LABEL, type CollectionNode } from "../lib/collectionTree";
import { t, tCount } from "../i18n";
import type {
  AnchoredContextMenuProps,
  AnchorRect,
} from "../components/AnchoredContextMenu";
import type { RenameDialogProps } from "../components/RenameDialog";

/**
 * The server's own ceiling (`MAX_FOLDER_NAME_LENGTH` in
 * `media_summarizer/core/models/folder.py`, which `UpdateFolderRequest` states),
 * mirrored here so the field stops accepting characters the `PUT` would reject.
 * Twice the media title bound: a collection name is written by hand, not derived.
 */
const MAX_COLLECTION_NAME_LENGTH = 255;

/** The one collection the open menu is about. */
interface CollectionActionTarget {
  id: string;
  name: string;
  /**
   * Sub-collections that would be deleted along with it, at any depth.
   *
   * Counted from the tree the screen already holds rather than asked of the
   * backend: the confirmation has to be worded before anything is sent, and the
   * delete endpoint only reports what it did once it has done it.
   */
  descendantCount: number;
  /** Kept whole so the menu can redraw the tile it was opened from. */
  node: CollectionNode;
}

/** What the surface spreads onto the menu, minus what only it can answer. */
type MenuProps = Omit<AnchoredContextMenuProps<CollectionNode>, "renderPreview">;

export interface CollectionActionsController {
  /**
   * Long-press handler to hand to a collection tile, with the window rect of the
   * tile that was pressed — the menu is anchored to it.
   */
  open: (collection: CollectionNode, anchor: AnchorRect) => void;
  /** Spread onto `<AnchoredContextMenu />`, alongside a `renderPreview`. */
  menuProps: MenuProps;
  /** Spread onto `<RenameDialog />`. */
  renameProps: RenameDialogProps;
}

/** Every collection under this one, at any depth. */
function countDescendants(node: CollectionNode): number {
  return node.children.reduce(
    (total, child) => total + 1 + countDescendants(child),
    0,
  );
}

export function useCollectionActions(options: {
  /**
   * Called once the backend has confirmed the deletion, never before: a tile must
   * not leave the grid while the collection may still exist. The sub-collections
   * and the media that moved are the caller's business — it refetches.
   */
  onDeleted: (collectionId: string) => void;
  /**
   * Called with the name the server stored, so the tile shows it without waiting
   * for a refetch. Same rule: only after the `PUT` has answered, so the grid never
   * displays a name the backend does not hold.
   */
  onRenamed: (collectionId: string, name: string) => void;
}): CollectionActionsController {
  const { onDeleted, onRenamed } = options;

  // Visibility is tracked apart from the target on purpose: the menu defers the
  // rename until it has finished dismissing, so that handler runs after
  // `onClose` — clearing the target there would leave it with nothing to act on.
  const [target, setTarget] = useState<CollectionActionTarget | null>(null);
  const [anchor, setAnchor] = useState<AnchorRect | null>(null);
  const [isMenuVisible, setIsMenuVisible] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [isRenameVisible, setIsRenameVisible] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  // Held here rather than inside the dialog: it is seeded from the target when
  // the dialog opens, which is a thing only this hook knows.
  const [renameDraft, setRenameDraft] = useState("");

  const open = useCallback((collection: CollectionNode, rect: AnchorRect) => {
    setTarget({
      id: collection.id,
      name: collection.name,
      descendantCount: countDescendants(collection),
      node: collection,
    });
    setAnchor(rect);
    setIsMenuVisible(true);
  }, []);

  const closeMenu = useCallback(() => {
    // A deletion in flight owns the menu: dismissing it would strand the spinner
    // and leave the user unsure whether the call went out.
    if (isDeleting) return;
    setIsMenuVisible(false);
  }, [isDeleting]);

  const handleRename = useCallback(() => {
    if (!target) return;
    setRenameError(null);
    setRenameDraft(target.name);
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
    (name: string) => {
      if (!target || isRenaming) return;
      const collection = target;

      // Nothing to write and nothing to report: closing is the honest answer to
      // "rename it to exactly what it is called".
      if (name === collection.name) {
        setIsRenameVisible(false);
        return;
      }

      setIsRenaming(true);
      setRenameError(null);
      void (async () => {
        try {
          const updated = await OrganizationService.renameCollection(
            collection.id,
            name,
          );
          // The server trims and collapses whitespace, so what it answers is the
          // name the library holds — showing the raw input instead would display
          // a name that is stored nowhere.
          const stored = updated.name.trim() || name;
          setTarget((current) =>
            current && current.id === collection.id
              ? { ...current, name: stored }
              : current,
          );
          setIsRenameVisible(false);
          onRenamed(collection.id, stored);
        } catch (err) {
          // The dialog stays open with the typed name intact, and the tile keeps
          // the name the backend still holds: a grid showing a name the `PUT`
          // refused would be lying about what was saved.
          setRenameError(
            getFriendlyErrorMessage(err, {
              fallback: t("collectionActions.renameFailed"),
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
    async (collection: CollectionActionTarget) => {
      setIsDeleting(true);
      try {
        await OrganizationService.deleteCollection(collection.id);
        setIsMenuVisible(false);
        onDeleted(collection.id);
      } catch (err) {
        // The tile stays exactly where it is: the collection is still there, and
        // a grid that hides it would be lying about what the backend holds.
        //
        // The menu stays open too, and not only so the user can try again: on iOS
        // an alert is presented by the top-most view controller, which is the
        // menu's — closing it in the same frame would dismiss the alert along
        // with it, and the failure would go unreported.
        Alert.alert(
          t("common.error"),
          getFriendlyErrorMessage(err, {
            fallback: t("collectionActions.deleteFailed"),
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
    const collection = target;

    // What the confirmation has to say, because deleting a collection is not
    // deleting what is in it: the sources move to the default collection and none
    // of them is destroyed. The sub-collections *are*, so when there are any they
    // are counted — "and its 3 sub-collections" is the part a user cannot see from
    // a tile that shows only a folder glyph and a name.
    const body = [
      t("collectionActions.deleteBody", {
        name: collection.name,
        unsorted: DEFAULT_COLLECTION_LABEL,
      }),
      collection.descendantCount > 0
        ? tCount(
            "collectionActions.deleteSubCollections",
            collection.descendantCount,
            { unsorted: DEFAULT_COLLECTION_LABEL },
          )
        : null,
    ]
      .filter((part): part is string => part !== null)
      .join(" ");

    Alert.alert(t("collectionActions.deleteTitle"), body, [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("common.delete"),
        style: "destructive",
        onPress: () => {
          void runDelete(collection);
        },
      },
    ]);
  }, [target, isDeleting, runDelete]);

  return {
    open,
    menuProps: {
      visible: isMenuVisible,
      target: target?.node ?? null,
      anchor,
      actions: [
        {
          key: "rename",
          icon: "pencil-outline",
          label: t("collectionActions.rename.label"),
          onPress: handleRename,
          closesMenu: true,
          testID: "collection-actions-rename",
        },
        {
          key: "delete",
          icon: "trash-outline",
          label: t("collectionActions.delete.label"),
          onPress: handleDelete,
          destructive: true,
          isBusy: isDeleting,
          // The confirmation and the spinner both live in the menu, so it stays.
          closesMenu: false,
          testID: "collection-actions-delete",
        },
      ],
      isBusy: isDeleting,
      onClose: closeMenu,
      testIDPrefix: "collection-actions",
    },
    renameProps: {
      visible: isRenameVisible,
      heading: t("collectionActions.rename.title"),
      placeholder: t("collectionActions.rename.placeholder"),
      maxLength: MAX_COLLECTION_NAME_LENGTH,
      value: renameDraft,
      onChangeText: changeRenameDraft,
      isSaving: isRenaming,
      errorMessage: renameError,
      onClose: closeRename,
      onSubmit: submitRename,
      testIDPrefix: "collection-rename",
    },
  };
}
