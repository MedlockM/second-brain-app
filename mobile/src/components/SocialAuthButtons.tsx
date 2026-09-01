import { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
  ActivityIndicator,
} from "react-native";
import * as AppleAuthentication from "expo-apple-authentication";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useAuth } from "../contexts/AuthContext";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { t } from "../i18n";
import { useGoogleSignIn } from "../hooks/useGoogleSignIn";
import { POST_AUTH_ENTRY_POINT } from "../constants/routes";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../constants/theme";

interface SocialAuthButtonsProps {
  onError: (message: string) => void;
  disabled?: boolean;
}

/**
 * Social authentication buttons for Google and Apple sign-in.
 * - Google: visible on both iOS and Android
 * - Apple: visible only on iOS (App Store requirement)
 *
 * The Google flow itself is platform-specific and lives in `useGoogleSignIn`:
 * a browser authorization flow on iOS and web, the system Credential Manager
 * sheet on Android. This component only maps the outcome to a message.
 */
export function SocialAuthButtons({ onError, disabled }: SocialAuthButtonsProps) {
  const { loginWithGoogle, loginWithApple } = useAuth();
  const { signInAsync: googleSignInAsync } = useGoogleSignIn();
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [isAppleLoading, setIsAppleLoading] = useState(false);

  const isLoading = isGoogleLoading || isAppleLoading;

  const handleGoogleSignIn = async () => {
    if (disabled || isLoading) return;
    setIsGoogleLoading(true);
    try {
      const outcome = await googleSignInAsync();

      switch (outcome.type) {
        // The user backed out: stay silent and just drop the loading state.
        case "cancelled":
          return;
        case "noGoogleAccount":
          onError(t("auth.google.noGoogleAccount"));
          return;
        case "noIdToken":
          onError(t("auth.google.noIdToken"));
          return;
        case "notCompleted":
          onError(t("auth.google.notCompleted"));
          return;
      }

      await loginWithGoogle(outcome.idToken);
      router.replace(POST_AUTH_ENTRY_POINT);
    } catch (err) {
      onError(
        getFriendlyErrorMessage(err, {
          fallback: t("auth.google.failed"),
        }),
      );
    } finally {
      setIsGoogleLoading(false);
    }
  };

  const handleAppleSignIn = async () => {
    if (disabled || isLoading) return;
    setIsAppleLoading(true);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });

      const identityToken = credential.identityToken;
      if (!identityToken) {
        onError(t("auth.apple.noIdentityToken"));
        return;
      }

      await loginWithApple(identityToken, {
        email: credential.email ?? undefined,
        fullName: credential.fullName
          ? {
              givenName: credential.fullName.givenName ?? undefined,
              familyName: credential.fullName.familyName ?? undefined,
            }
          : undefined,
      });
      router.replace(POST_AUTH_ENTRY_POINT);
    } catch (err: unknown) {
      // Apple sign-in cancellation has a specific error code
      if (
        err &&
        typeof err === "object" &&
        "code" in err &&
        (err as { code: string }).code === "ERR_REQUEST_CANCELED"
      ) {
        // User cancelled - no error to show
      } else {
        onError(getFriendlyErrorMessage(err));
      }
    } finally {
      setIsAppleLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.divider}>
        <View style={styles.dividerLine} />
        <Text style={styles.dividerText}>{t("auth.or")}</Text>
        <View style={styles.dividerLine} />
      </View>

      {/* Google button - visible on all platforms */}
      <TouchableOpacity
        style={[styles.socialButton, styles.googleButton, (disabled || isLoading) && styles.buttonDisabled]}
        onPress={handleGoogleSignIn}
        disabled={disabled || isLoading}
        activeOpacity={0.8}
        accessibilityLabel={t("auth.continueWithGoogle")}
        accessibilityRole="button"
      >
        {isGoogleLoading ? (
          <ActivityIndicator color={Colors.textMain} />
        ) : (
          <>
            <Ionicons name="logo-google" size={20} color={Colors.textMain} />
            <Text style={styles.googleButtonText}>
              {t("auth.continueWithGoogle")}
            </Text>
          </>
        )}
      </TouchableOpacity>

      {/* Apple button - iOS only */}
      {Platform.OS === "ios" && (
        <TouchableOpacity
          style={[styles.socialButton, styles.appleButton, (disabled || isLoading) && styles.appleButtonDisabled]}
          onPress={handleAppleSignIn}
          disabled={disabled || isLoading}
          activeOpacity={0.8}
          accessibilityLabel={t("auth.signInWithApple")}
          accessibilityRole="button"
        >
          {isAppleLoading ? (
            <ActivityIndicator color={Colors.surface} />
          ) : (
            <>
              <Ionicons name="logo-apple" size={20} color={Colors.surface} />
              <Text style={styles.appleButtonText}>
                {t("auth.signInWithApple")}
              </Text>
            </>
          )}
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.surfaceContainerHigh,
  },
  dividerText: {
    color: Colors.textMuted,
    fontSize: Typography.small.fontSize,
    fontWeight: Typography.small.fontWeight,
  },
  socialButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    borderRadius: BorderRadius.md,
    minHeight: TouchTarget.minimum,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.lg,
  },
  googleButton: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
  },
  googleButtonText: {
    color: Colors.textMain,
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
  },
  appleButton: {
    backgroundColor: Colors.textMain,
  },
  appleButtonText: {
    color: Colors.surface,
    fontSize: Typography.body.fontSize,
    fontWeight: "500",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  appleButtonDisabled: {
    opacity: 0.6,
  },
});
