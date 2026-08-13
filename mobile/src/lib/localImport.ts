/**
 * The two device-side gestures that start an import (task-264): browsing for a
 * file, and taking a photo. Both end on a `LocalUploadFile` that the share
 * confirmation screen can display and submit.
 *
 * Kept out of the screens so the inbox stays presentational and the same two
 * entry points can be reused from any other surface.
 */

import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import {
  UPLOAD_PICKER_MIME_TYPES,
  prepareLocalUploadFile,
  type LocalUploadFile,
} from "../types/upload";

/**
 * Outcome of a picking gesture.
 * - `cancelled`: the user backed out; the caller shows nothing.
 * - `file`: accepted, ready to confirm and send.
 * - `error`: refused (unsupported format, too large, permission denied, …) with
 *   a message that names the reason.
 */
export type LocalImportResult =
  | { status: "cancelled" }
  | { status: "file"; file: LocalUploadFile }
  | { status: "error"; title: string; message: string };

/**
 * Open the system file browser, filtered to the formats the backend accepts.
 *
 * The filter is advisory on some providers, so the picked result is validated
 * again: an unsupported extension or an oversized file is refused here, with no
 * network call.
 */
export async function pickFileToImport(): Promise<LocalImportResult> {
  let result: DocumentPicker.DocumentPickerResult;
  try {
    result = await DocumentPicker.getDocumentAsync({
      type: [...UPLOAD_PICKER_MIME_TYPES],
      copyToCacheDirectory: true,
      multiple: false,
    });
  } catch {
    return {
      status: "error",
      title: "Could not open your files",
      message: "The file browser could not be opened. Please try again.",
    };
  }

  if (result.canceled || !result.assets || result.assets.length === 0) {
    return { status: "cancelled" };
  }

  const asset = result.assets[0];
  const prepared = prepareLocalUploadFile({
    uri: asset.uri,
    name: asset.name || "file",
    mimeType: asset.mimeType,
    size: asset.size ?? null,
  });

  if ("rejection" in prepared) {
    return {
      status: "error",
      title:
        prepared.rejection.reason === "too_large"
          ? "File too large"
          : "Format not supported",
      message: prepared.rejection.message,
    };
  }

  return { status: "file", file: prepared.file };
}

/**
 * Ask for the camera, take one photo, and hand it back ready to confirm.
 *
 * A denied permission is a normal outcome, not a crash: it returns an `error`
 * result explaining how to grant it, and the app stays usable.
 */
export async function capturePhotoToImport(): Promise<LocalImportResult> {
  let permission: ImagePicker.PermissionResponse;
  try {
    permission = await ImagePicker.requestCameraPermissionsAsync();
  } catch {
    return {
      status: "error",
      title: "Camera unavailable",
      message: "The camera could not be started on this device.",
    };
  }

  if (!permission.granted) {
    return {
      status: "error",
      title: "Camera access needed",
      message: permission.canAskAgain
        ? "Allow camera access to capture a document or a page you want to import."
        : "Camera access is turned off. Enable it for this app in your device settings to capture a document.",
    };
  }

  let result: ImagePicker.ImagePickerResult;
  try {
    result = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      quality: 0.8,
      // One shot, straight to the confirmation screen: no editor, no gallery
      // round-trip, no second selection.
      allowsEditing: false,
    });
  } catch {
    return {
      status: "error",
      title: "Camera unavailable",
      message: "The camera could not be started on this device.",
    };
  }

  if (result.canceled || !result.assets || result.assets.length === 0) {
    return { status: "cancelled" };
  }

  const asset = result.assets[0];
  const prepared = prepareLocalUploadFile({
    uri: asset.uri,
    name: asset.fileName || defaultPhotoName(asset.uri, asset.mimeType),
    mimeType: asset.mimeType,
    size: asset.fileSize ?? null,
  });

  if ("rejection" in prepared) {
    return {
      status: "error",
      title:
        prepared.rejection.reason === "too_large"
          ? "Photo too large"
          : "Photo not supported",
      message: prepared.rejection.message,
    };
  }

  return { status: "file", file: prepared.file };
}

/**
 * Camera assets often come back without a file name. The extension is what the
 * backend routes on, so it is derived from the captured URI (or the MIME type)
 * rather than guessed as jpg unconditionally.
 */
function defaultPhotoName(uri: string, mimeType?: string | null): string {
  const fromUri = uri.split("?")[0].split("/").pop() ?? "";
  if (fromUri.includes(".")) {
    return fromUri;
  }
  const subtype = (mimeType ?? "").split("/")[1]?.toLowerCase();
  const extension =
    subtype === "png" || subtype === "heic" || subtype === "heif"
      ? subtype
      : "jpg";
  return `photo-${Date.now()}.${extension}`;
}
