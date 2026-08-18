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
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useAuth } from "../contexts/AuthContext";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { getGoogleIosRedirectUri } from "../lib/googleOAuth";
import { Config } from "../constants/config";
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  TouchTarget,
} from "../constants/theme";

// Required for expo-auth-session to dismiss the web browser on redirect
WebBrowser.maybeCompleteAuthSession();

/**
 * Redirect URI for the native Google flow, or `undefined` to keep the
 * expo-auth-session default.
 *
 * iOS: the library would default to `<bundleId>:/oauthredirect`, which an iOS
 * OAuth client rejects with `Error 400: redirect_uri_mismatch` — such a client
 * only accepts its reserved scheme. It is therefore derived from the configured
 * iOS client ID (never hardcoded, so rotating the client keeps it valid) and the
 * matching scheme is declared in `ios.scheme` in app.config.ts.
 *
 * Android: no override needed. Google keys an Android OAuth client on package
 * name + signing fingerprint and documents `<package>:/oauthredirect` as its
 * custom-scheme redirect, which is exactly what the library already builds from
 * `Application.applicationId`. The missing piece there was only the manifest
 * intent filter, now declared in `android.scheme`.
 *
 * Web: no override either — `makeRedirectUri` produces the right origin.
 */
const GOOGLE_REDIRECT_URI =
  Platform.OS === "ios"
    ? (getGoogleIosRedirectUri(Config.GOOGLE_CLIENT_ID_IOS) ?? undefined)
    : undefined;

interface SocialAuthButtonsProps {
  onError: (message: string) => void;
  disabled?: boolean;
}

/**
 * Social authentication buttons for Google and Apple sign-in.
 * - Google: visible on both iOS and Android
 * - Apple: visible only on iOS (App Store requirement)
 */
export function SocialAuthButtons({ onError, disabled }: SocialAuthButtonsProps) {
  const { loginWithGoogle, loginWithApple } = useAuth();
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [isAppleLoading, setIsAppleLoading] = useState(false);

  const isLoading = isGoogleLoading || isAppleLoading;

  // Google Auth Session configuration
  const [, , googlePromptAsync] = Google.useAuthRequest({
    iosClientId: Config.GOOGLE_CLIENT_ID_IOS,
    androidClientId: Config.GOOGLE_CLIENT_ID_ANDROID,
    webClientId: Config.GOOGLE_CLIENT_ID_WEB,
    redirectUri: GOOGLE_REDIRECT_URI,
  });

  const handleGoogleSignIn = async () => {
    if (disabled || isLoading) return;
    setIsGoogleLoading(true);
    try {
      const result = await googlePromptAsync();
      if (result.type === "success") {
        const idToken = result.authentication?.idToken;
        if (!idToken) {
          onError("Failed to obtain Google ID token. Please try again.");
          return;
        }
        await loginWithGoogle(idToken);
        router.replace("/(tabs)/inbox");
      } else if (result.type === "cancel") {
        // User cancelled - no error to show
      } else {
        onError("Google sign-in was not completed. Please try again.");
      }
    } catch (err) {
      onError(getFriendlyErrorMessage(err));
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
        onError("Failed to obtain Apple identity token. Please try again.");
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
      router.replace("/(tabs)/inbox");
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
        <Text style={styles.dividerText}>or</Text>
        <View style={styles.dividerLine} />
      </View>

      {/* Google button - visible on all platforms */}
      <TouchableOpacity
        style={[styles.socialButton, styles.googleButton, (disabled || isLoading) && styles.buttonDisabled]}
        onPress={handleGoogleSignIn}
        disabled={disabled || isLoading}
        activeOpacity={0.8}
        accessibilityLabel="Continue with Google"
        accessibilityRole="button"
      >
        {isGoogleLoading ? (
          <ActivityIndicator color={Colors.textMain} />
        ) : (
          <>
            <Ionicons name="logo-google" size={20} color={Colors.textMain} />
            <Text style={styles.googleButtonText}>Continue with Google</Text>
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
          accessibilityLabel="Sign in with Apple"
          accessibilityRole="button"
        >
          {isAppleLoading ? (
            <ActivityIndicator color={Colors.surface} />
          ) : (
            <>
              <Ionicons name="logo-apple" size={20} color={Colors.surface} />
              <Text style={styles.appleButtonText}>Sign in with Apple</Text>
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
