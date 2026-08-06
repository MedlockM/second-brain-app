import { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import Constants from "expo-constants";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  TouchTarget,
} from "../src/constants/theme";
import { useAuth } from "../src/contexts/AuthContext";
import {
  BugReportService,
  isAllowedExtension,
  isAllowedMimeType,
  isWithinSizeLimit,
  formatFileSize,
  MAX_FILE_SIZE_BYTES,
  ALLOWED_EXTENSIONS,
} from "../src/services/bugReportService";

type SubmitState = "idle" | "uploading" | "submitting" | "success" | "error";

interface SelectedFile {
  uri: string;
  name: string;
  mimeType: string;
  size: number;
}

/**
 * Bug Report screen — allows users to submit bug reports with an optional
 * file attachment. Accessible from the Account tab.
 *
 * Design: Amber Clarity system — warm surfaces, no hard borders, amber accents.
 */
export default function BugReportScreen() {
  const router = useRouter();
  const { token } = useAuth();

  // Form state
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(null);

  // Animations
  const [successOpacity] = useState(() => new Animated.Value(0));
  const [successScale] = useState(() => new Animated.Value(0.8));

  const isFormValid = subject.trim().length > 0 && description.trim().length > 0;
  const isSubmitting = submitState === "uploading" || submitState === "submitting";

  const handleClose = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace("/(tabs)/account");
    }
  }, [router]);

  const handlePickDocument = useCallback(async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "image/jpeg",
          "image/png",
          "image/heic",
          "image/heif",
          "video/mp4",
          "video/quicktime",
          "application/pdf",
          "application/zip",
        ],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }

      const asset = result.assets[0];
      const fileName = asset.name || "attachment";
      const mimeType = asset.mimeType || "application/octet-stream";
      const size = asset.size || 0;

      // Validate extension
      if (!isAllowedExtension(fileName)) {
        Alert.alert(
          "File type not allowed",
          `Accepted file types: ${ALLOWED_EXTENSIONS.join(", ")}`,
        );
        return;
      }

      // Validate MIME type
      if (!isAllowedMimeType(mimeType)) {
        Alert.alert(
          "File type not allowed",
          `The selected file type (${mimeType}) is not accepted.`,
        );
        return;
      }

      // Validate size
      if (!isWithinSizeLimit(size)) {
        Alert.alert(
          "File too large",
          `Maximum file size is ${formatFileSize(MAX_FILE_SIZE_BYTES)}. Your file is ${formatFileSize(size)}.`,
        );
        return;
      }

      setSelectedFile({
        uri: asset.uri,
        name: fileName,
        mimeType,
        size,
      });
    } catch (error) {
      Alert.alert("Error", "Failed to select file. Please try again.");
    }
  }, []);

  const handlePickImage = useCallback(async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images", "videos"],
        quality: 0.8,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }

      const asset = result.assets[0];
      const fileName = asset.fileName || `capture.${asset.type === "video" ? "mp4" : "jpg"}`;
      const mimeType = asset.mimeType || (asset.type === "video" ? "video/mp4" : "image/jpeg");
      const size = asset.fileSize || 0;

      // Validate size
      if (size > 0 && !isWithinSizeLimit(size)) {
        Alert.alert(
          "File too large",
          `Maximum file size is ${formatFileSize(MAX_FILE_SIZE_BYTES)}. Your file is ${formatFileSize(size)}.`,
        );
        return;
      }

      setSelectedFile({
        uri: asset.uri,
        name: fileName,
        mimeType,
        size,
      });
    } catch (error) {
      Alert.alert("Error", "Failed to select image. Please try again.");
    }
  }, []);

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  const handleAttach = useCallback(() => {
    Alert.alert("Attach File", "Choose a source", [
      { text: "Photo Library", onPress: handlePickImage },
      { text: "Files", onPress: handlePickDocument },
      { text: "Cancel", style: "cancel" },
    ]);
  }, [handlePickImage, handlePickDocument]);

  const handleSubmit = useCallback(async () => {
    if (!isFormValid || !token) return;

    setSubmitState("uploading");
    setErrorMessage(null);

    try {
      let attachmentKey: string | null = null;

      // Upload attachment if selected
      if (selectedFile) {
        setSubmitState("uploading");

        // Request presigned URL
        const uploadUrlResponse = await BugReportService.requestUploadUrl(token, {
          filename: selectedFile.name,
          content_type: selectedFile.mimeType,
          file_size: selectedFile.size,
        });

        // Upload to S3
        await BugReportService.uploadFileToS3(
          uploadUrlResponse.upload_url,
          selectedFile.uri,
          selectedFile.mimeType,
        );

        attachmentKey = uploadUrlResponse.attachment_key;
      }

      // Submit the bug report
      setSubmitState("submitting");

      const appVersion = Constants.expoConfig?.version || "unknown";
      const platform = Platform.OS;

      const response = await BugReportService.createBugReport(token, {
        subject: subject.trim(),
        description: description.trim(),
        attachment_key: attachmentKey,
        source_app_version: appVersion,
        source_platform: platform,
      });

      setTicketId(response.id);
      setSubmitState("success");

      // Animate success
      Animated.parallel([
        Animated.timing(successOpacity, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.spring(successScale, {
          toValue: 1,
          friction: 5,
          useNativeDriver: true,
        }),
      ]).start();
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to submit bug report. Please try again.";
      setErrorMessage(message);
      setSubmitState("error");
    }
  }, [
    isFormValid,
    token,
    selectedFile,
    subject,
    description,
    successOpacity,
    successScale,
  ]);

  // Success state — full screen confirmation
  if (submitState === "success") {
    return (
      <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
        <Animated.View
          style={[
            styles.successContainer,
            {
              opacity: successOpacity,
              transform: [{ scale: successScale }],
            },
          ]}
        >
          <View style={styles.successIconContainer}>
            <Ionicons name="checkmark-circle" size={72} color={Colors.primary} />
          </View>
          <Text style={styles.successTitle}>Report Submitted</Text>
          <Text style={styles.successMessage}>
            Thank you for reporting this issue. Our team will investigate it
            shortly.
          </Text>
          {ticketId && (
            <View style={styles.ticketIdContainer}>
              <Text style={styles.ticketIdLabel}>Ticket ID</Text>
              <Text style={styles.ticketIdValue}>{ticketId}</Text>
            </View>
          )}
          <Pressable
            style={styles.doneButton}
            onPress={handleClose}
            accessibilityLabel="Done, return to account"
            accessibilityRole="button"
          >
            <Text style={styles.doneButtonText}>Done</Text>
          </Pressable>
        </Animated.View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        {/* Header */}
        <View style={styles.header}>
          <Pressable
            style={styles.closeButton}
            onPress={handleClose}
            accessibilityLabel="Close bug report form"
            accessibilityRole="button"
          >
            <Ionicons name="close" size={22} color={Colors.textMain} />
          </Pressable>

          <Text style={styles.headerTitle}>Report a Bug</Text>

          <Pressable
            style={[
              styles.submitButton,
              (!isFormValid || isSubmitting) && styles.submitButtonDisabled,
            ]}
            onPress={handleSubmit}
            disabled={!isFormValid || isSubmitting}
            accessibilityLabel="Submit bug report"
            accessibilityRole="button"
          >
            {isSubmitting ? (
              <ActivityIndicator size="small" color={Colors.onPrimary} />
            ) : (
              <Text style={styles.submitButtonText}>Submit</Text>
            )}
          </Pressable>
        </View>

        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Subject field */}
          <View style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>Subject</Text>
            <TextInput
              style={styles.subjectInput}
              placeholder="Brief summary of the issue"
              placeholderTextColor={Colors.textMuted}
              value={subject}
              onChangeText={setSubject}
              maxLength={200}
              returnKeyType="next"
              editable={!isSubmitting}
              accessibilityLabel="Bug report subject"
            />
          </View>

          {/* Description field */}
          <View style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>Description</Text>
            <TextInput
              style={styles.descriptionInput}
              placeholder="Steps to reproduce, what you expected, what happened instead..."
              placeholderTextColor={Colors.textMuted}
              value={description}
              onChangeText={setDescription}
              maxLength={5000}
              multiline
              textAlignVertical="top"
              editable={!isSubmitting}
              accessibilityLabel="Bug report description"
            />
          </View>

          {/* Attachment section */}
          <View style={styles.fieldContainer}>
            <Text style={styles.fieldLabel}>Attachment (optional)</Text>
            <Text style={styles.fieldHint}>
              Image, video, PDF, or ZIP — max {formatFileSize(MAX_FILE_SIZE_BYTES)}
            </Text>

            {selectedFile ? (
              <View style={styles.attachmentPreview}>
                <View style={styles.attachmentInfo}>
                  <Ionicons
                    name={getFileIcon(selectedFile.mimeType)}
                    size={24}
                    color={Colors.primary}
                  />
                  <View style={styles.attachmentTextContainer}>
                    <Text style={styles.attachmentName} numberOfLines={1}>
                      {selectedFile.name}
                    </Text>
                    <Text style={styles.attachmentSize}>
                      {formatFileSize(selectedFile.size)}
                    </Text>
                  </View>
                </View>
                <Pressable
                  style={styles.removeFileButton}
                  onPress={handleRemoveFile}
                  accessibilityLabel="Remove attached file"
                  accessibilityRole="button"
                >
                  <Ionicons
                    name="close-circle"
                    size={24}
                    color={Colors.textMuted}
                  />
                </Pressable>
              </View>
            ) : (
              <Pressable
                style={styles.attachButton}
                onPress={handleAttach}
                disabled={isSubmitting}
                accessibilityLabel="Attach a file to the bug report"
                accessibilityRole="button"
              >
                <Ionicons
                  name="attach-outline"
                  size={22}
                  color={Colors.primary}
                />
                <Text style={styles.attachButtonText}>Attach File</Text>
              </Pressable>
            )}
          </View>

          {/* Error banner */}
          {submitState === "error" && errorMessage && (
            <View style={styles.errorBanner}>
              <Ionicons
                name="alert-circle-outline"
                size={18}
                color={Colors.error}
              />
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          )}

          {/* Upload progress indicator */}
          {submitState === "uploading" && (
            <View style={styles.progressBanner}>
              <ActivityIndicator size="small" color={Colors.primary} />
              <Text style={styles.progressText}>Uploading attachment...</Text>
            </View>
          )}
          {submitState === "submitting" && (
            <View style={styles.progressBanner}>
              <ActivityIndicator size="small" color={Colors.primary} />
              <Text style={styles.progressText}>Submitting report...</Text>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/**
 * Get an Ionicons name for a MIME type.
 */
function getFileIcon(
  mimeType: string,
): React.ComponentProps<typeof Ionicons>["name"] {
  if (mimeType.startsWith("image/")) return "image-outline";
  if (mimeType.startsWith("video/")) return "videocam-outline";
  if (mimeType === "application/pdf") return "document-text-outline";
  if (mimeType.includes("zip")) return "archive-outline";
  return "document-outline";
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  closeButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceContainerHigh,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: Typography.headline.fontSize,
    fontWeight: Typography.headline.fontWeight,
    color: Colors.textMain,
  },
  submitButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    minWidth: 80,
    minHeight: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  submitButtonDisabled: {
    opacity: 0.5,
  },
  submitButtonText: {
    fontSize: Typography.label.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  fieldContainer: {
    marginBottom: Spacing.lg,
  },
  fieldLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
    marginBottom: Spacing.sm,
  },
  fieldHint: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginBottom: Spacing.sm,
  },
  subjectInput: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    minHeight: TouchTarget.minimum,
  },
  descriptionInput: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
    minHeight: 160,
    lineHeight: Typography.body.lineHeight,
  },
  attachButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    minHeight: TouchTarget.minimum,
  },
  attachButtonText: {
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
    color: Colors.primary,
  },
  attachmentPreview: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    minHeight: TouchTarget.minimum,
  },
  attachmentInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    flex: 1,
  },
  attachmentTextContainer: {
    flex: 1,
  },
  attachmentName: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  attachmentSize: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  removeFileButton: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.errorContainer,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
  },
  errorText: {
    flex: 1,
    fontSize: Typography.small.fontSize,
    color: Colors.error,
  },
  progressBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
  },
  progressText: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
  },
  // Success screen
  successContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: Spacing.xl,
  },
  successIconContainer: {
    marginBottom: Spacing.lg,
  },
  successTitle: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    textAlign: "center",
    marginBottom: Spacing.md,
  },
  successMessage: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    textAlign: "center",
    lineHeight: Typography.body.lineHeight,
    marginBottom: Spacing.lg,
  },
  ticketIdContainer: {
    backgroundColor: Colors.surfaceContainerLow,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    alignItems: "center",
    marginBottom: Spacing.xl,
  },
  ticketIdLabel: {
    fontSize: Typography.small.fontSize,
    color: Colors.textMuted,
    marginBottom: Spacing.xs,
  },
  ticketIdValue: {
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
    color: Colors.textMain,
  },
  doneButton: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    minHeight: TouchTarget.comfortable,
    alignItems: "center",
    justifyContent: "center",
    ...Shadows.soft,
  },
  doneButtonText: {
    fontSize: Typography.body.fontSize,
    fontWeight: "700",
    color: Colors.onPrimary,
  },
});
