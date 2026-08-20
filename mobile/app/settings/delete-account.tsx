import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Alert,
  ActivityIndicator,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import { useRouter } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { usePurchases } from "../../src/contexts/PurchasesContext";
import { AccountService } from "../../src/services/accountService";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  PRIVACY_CONTACT_EMAIL,
  STORE_SUBSCRIPTIONS_URL,
} from "../../src/constants/legal";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../../src/constants/theme";

/**
 * Account deletion, required in-app by App Store guideline 5.1.1(v) and by the
 * GDPR right to erasure.
 *
 * A dedicated screen rather than a menu row plus an alert: the consequences that
 * have to be read before confirming do not fit in an alert body — what is erased,
 * that a store subscription keeps billing regardless, and how to get a copy of
 * the data first. The destructive button stays disabled until the irreversibility
 * is explicitly acknowledged, and the native alert is the second and final gate.
 */

const ERASED_ITEMS: readonly string[] = [
  "Your library, folders and tags",
  "Every transcript, summary, note and flashcard",
  "Your review schedule and digests",
  "Your search results across the app",
  "Your email address and sign-in details",
];

export default function DeleteAccountScreen() {
  const router = useRouter();
  const { isAuthenticated, logout } = useAuth();
  const { isSubscribed } = usePurchases();
  const [hasAcknowledged, setHasAcknowledged] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runDeletion = async (): Promise<void> => {
    if (!isAuthenticated) {
      setError("Your session has expired. Please sign in again.");
      return;
    }
    setError(null);
    setIsDeleting(true);
    try {
      await AccountService.deleteAccount();
      // The backend has already revoked every session; this clears the local
      // copy and the RevenueCat login, and the replace leaves no screen behind
      // that would try to read a deleted account.
      await logout();
      router.replace("/(auth)/login");
    } catch (err) {
      setError(getFriendlyErrorMessage(err));
      setIsDeleting(false);
    }
  };

  const handleDeletePress = (): void => {
    Alert.alert(
      "Delete account?",
      "This permanently erases your account and everything in it. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete forever",
          style: "destructive",
          onPress: () => {
            void runDeletion();
          },
        },
      ],
    );
  };

  const openStoreSubscriptions = (): void => {
    void Linking.openURL(STORE_SUBSCRIPTIONS_URL);
  };

  const openPrivacyContact = (): void => {
    void Linking.openURL(
      `mailto:${PRIVACY_CONTACT_EMAIL}?subject=Data%20request`,
    );
  };

  return (
    <SafeAreaView
      testID="delete-account-screen"
      style={styles.container}
      edges={["top"]}
    >
      <View style={styles.header}>
        <Pressable
          style={styles.backButton}
          onPress={() => router.back()}
          disabled={isDeleting}
          accessibilityLabel="Go back"
          accessibilityRole="button"
        >
          <Ionicons name="chevron-back" size={24} color={Colors.textMain} />
        </Pressable>
        <Text style={styles.title}>Delete Account</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.warningCard}>
          <Ionicons name="alert-circle" size={20} color={Colors.error} />
          <View style={styles.warningTextContainer}>
            <Text style={styles.warningTitle}>This cannot be undone</Text>
            <Text style={styles.warningText}>
              Deleting your account erases it permanently, along with everything
              you saved. We cannot restore it afterwards, not even on request.
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>What gets erased</Text>
        <View style={styles.card}>
          {ERASED_ITEMS.map((item) => (
            <View key={item} style={styles.bulletRow}>
              <Ionicons
                name="close-circle-outline"
                size={16}
                color={Colors.textMuted}
              />
              <Text style={styles.bulletText}>{item}</Text>
            </View>
          ))}
        </View>

        {isSubscribed && (
          <>
            <Text style={styles.sectionTitle}>Your subscription</Text>
            <View style={styles.card}>
              <Text style={styles.cardText}>
                Deleting your account does not cancel your subscription.
                {Platform.OS === "ios" ? " Apple" : " Google"} keeps billing you
                until you cancel it in your store settings, so cancel there
                first.
              </Text>
              <Pressable
                style={styles.linkRow}
                onPress={openStoreSubscriptions}
                accessibilityLabel={
                  Platform.OS === "ios"
                    ? "Manage subscription in the App Store"
                    : "Manage subscription in the Play Store"
                }
                accessibilityRole="button"
              >
                <Ionicons name="open-outline" size={16} color={Colors.textMain} />
                <Text style={styles.linkText}>
                  {Platform.OS === "ios"
                    ? "Manage subscription in the App Store"
                    : "Manage subscription in the Play Store"}
                </Text>
              </Pressable>
            </View>
          </>
        )}

        <Text style={styles.sectionTitle}>Want a copy first?</Text>
        <View style={styles.card}>
          <Text style={styles.cardText}>
            Email us before you delete and we will send you a copy of your data
            within one month.
          </Text>
          <Pressable
            style={styles.linkRow}
            onPress={openPrivacyContact}
            accessibilityLabel={`Email ${PRIVACY_CONTACT_EMAIL}`}
            accessibilityRole="button"
          >
            <Ionicons name="mail-outline" size={16} color={Colors.textMain} />
            <Text style={styles.linkText}>{PRIVACY_CONTACT_EMAIL}</Text>
          </Pressable>
        </View>

        <Pressable
          testID="delete-account-acknowledge"
          style={styles.acknowledgeRow}
          onPress={() => setHasAcknowledged((previous) => !previous)}
          disabled={isDeleting}
          accessibilityLabel="I understand this cannot be undone"
          accessibilityRole="checkbox"
          accessibilityState={{ checked: hasAcknowledged }}
        >
          <Ionicons
            name={hasAcknowledged ? "checkbox" : "square-outline"}
            size={24}
            color={hasAcknowledged ? Colors.error : Colors.textMuted}
          />
          <Text style={styles.acknowledgeText}>
            I understand my account and all my data will be erased permanently.
          </Text>
        </Pressable>

        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          testID="delete-account-confirm-button"
          style={[
            styles.deleteButton,
            (!hasAcknowledged || isDeleting) && styles.buttonDisabled,
          ]}
          onPress={handleDeletePress}
          disabled={!hasAcknowledged || isDeleting}
          accessibilityLabel="Delete my account"
          accessibilityRole="button"
        >
          {isDeleting ? (
            <ActivityIndicator color={Colors.onError} />
          ) : (
            <Text style={styles.deleteButtonText}>Delete My Account</Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
  },
  backButton: {
    width: TouchTarget.minimum,
    height: TouchTarget.minimum,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    flex: 1,
    ...Typography.headline,
    fontWeight: "700",
    color: Colors.textMain,
    textAlign: "center",
  },
  headerSpacer: {
    width: TouchTarget.minimum,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.lg,
  },
  warningCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: Colors.errorContainer,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    gap: Spacing.sm,
  },
  warningTextContainer: {
    flex: 1,
  },
  warningTitle: {
    ...Typography.label,
    fontWeight: "700",
    color: Colors.error,
    marginBottom: Spacing.xs,
  },
  warningText: {
    ...Typography.small,
    color: Colors.textMain,
    lineHeight: 18,
  },
  sectionTitle: {
    ...Typography.label,
    fontWeight: "600",
    color: Colors.textMuted,
    marginTop: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  card: {
    backgroundColor: Colors.surfaceContainerLow,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    gap: Spacing.sm,
  },
  cardText: {
    ...Typography.small,
    color: Colors.textMain,
    lineHeight: 18,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  bulletText: {
    flex: 1,
    ...Typography.small,
    color: Colors.textMain,
  },
  linkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    minHeight: TouchTarget.minimum,
  },
  linkText: {
    flex: 1,
    ...Typography.small,
    fontWeight: "600",
    color: Colors.textMain,
  },
  acknowledgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginTop: Spacing.lg,
    paddingVertical: Spacing.sm,
    minHeight: TouchTarget.minimum,
  },
  acknowledgeText: {
    flex: 1,
    ...Typography.small,
    color: Colors.textMain,
    lineHeight: 18,
  },
  errorContainer: {
    backgroundColor: Colors.errorContainer,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.md,
  },
  errorText: {
    ...Typography.small,
    color: Colors.error,
  },
  footer: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    paddingBottom: Platform.OS === "ios" ? Spacing.md : Spacing.lg,
  },
  deleteButton: {
    backgroundColor: Colors.error,
    borderRadius: BorderRadius.md,
    alignItems: "center",
    justifyContent: "center",
    minHeight: TouchTarget.comfortable,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  deleteButtonText: {
    ...Typography.body,
    fontWeight: "600",
    color: Colors.onError,
  },
});
