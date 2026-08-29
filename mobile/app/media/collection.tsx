import { useState, useEffect, useCallback } from "react";
import { Text, TouchableOpacity, StyleSheet, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
} from "../../src/constants/theme";
import { t, useTranslation } from "../../src/i18n";
import { ScreenHeader, HeaderIconButton } from "../../src/components/ScreenHeader";
import { CollectionPickerView } from "../../src/components/CollectionPickerView";
import { flattenCollectionPaths } from "../../src/lib/collectionTree";
import { useAuth } from "../../src/contexts/AuthContext";
import { useShareIntake } from "../../src/contexts/ShareIntentContext";
import { OrganizationService } from "../../src/services/organizationService";
import type { Collection } from "../../src/types/organization";

/**
 * Collection Selection Screen.
 * Presented as a modal from media detail or share confirmation.
 *
 * Design ref: mobile-design-mockups/s_lection_de_collection/
 *
 * Layout:
 * - Header: back button | "Collection" title | "Save" button
 * - The picker itself (`CollectionPickerView`): search, "Unsorted", the tree and
 *   inline creation, shared with the unsorted-review triage sheet.
 *
 * Two modes. In share mode a tap on a destination *is* the answer: it lands in
 * the share intake and the screen closes. Otherwise the pick is held until Save,
 * which writes it on the media.
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

  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(
    isShareMode ? selectedFolder?.id ?? null : params.currentCollectionId ?? null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch collections
  useEffect(() => {
    if (!isAuthenticated) return;

    const fetchCollections = async () => {
      try {
        setIsLoading(true);
        const data = await OrganizationService.getUserCollections();
        setCollections(data);
      } catch {
        setError(t("collectionPicker.loadFailed"));
      } finally {
        setIsLoading(false);
      }
    };

    fetchCollections();
  }, [isAuthenticated]);

  const handleBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    }
  }, [router]);

  const handleSelect = useCallback(
    (collectionId: string | null) => {
      setSelectedId(collectionId);
      if (!isShareMode) return;
      if (collectionId === null) {
        setSelectedFolder(null);
      } else {
        const path = flattenCollectionPaths(collections).find(
          (entry) => entry.id === collectionId,
        );
        setSelectedFolder({
          id: collectionId,
          path: path?.path ?? collectionId,
        });
      }
      router.back();
    },
    [collections, isShareMode, router, setSelectedFolder],
  );

  const handleCollectionCreated = useCallback(
    (created: Collection) => {
      setCollections((prev) => [...prev, created]);
      setSelectedId(created.id);
      if (isShareMode) {
        setSelectedFolder({ id: created.id, path: created.name });
        router.back();
      }
    },
    [isShareMode, router, setSelectedFolder],
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

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      {/* Header */}
      <ScreenHeader
        title={t("collectionPicker.title")}
        titleStyle={styles.headerTitle}
        leading={
          <HeaderIconButton
            icon="arrow-back"
            onPress={handleBack}
            accessibilityLabel={t("common.goBack")}
          />
        }
        // Share mode has no action: the header balances the back button on its
        // own, which is what the hard-coded 88pt placeholder used to attempt.
        trailing={
          isShareMode ? undefined : (
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
          )
        }
      />

      <CollectionPickerView
        collections={collections}
        selectedId={selectedId}
        isLoading={isLoading}
        busy={isSaving}
        error={error}
        onSelect={handleSelect}
        onCollectionCreated={handleCollectionCreated}
        onCreateFailed={setError}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surface,
  },
  // Only the colour departs from the shared header's title.
  headerTitle: {
    color: Colors.primary,
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
});
