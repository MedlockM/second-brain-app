import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { Link, router } from "expo-router";
import { useAuth } from "../../src/contexts/AuthContext";
import { getFriendlyErrorMessage } from "../../src/lib/getFriendlyErrorMessage";
import {
  getEmailValidationError,
  getPasswordValidationError,
} from "../../src/lib/validation";
import { SocialAuthButtons } from "../../src/components/SocialAuthButtons";
import { Colors, Typography, Spacing, BorderRadius } from "../../src/constants/theme";

export default function LoginScreen() {
  const { login, sessionError, clearSessionError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async () => {
    setError(null);

    // Client-side validation
    const emailError = getEmailValidationError(email);
    if (emailError) {
      setError(emailError);
      return;
    }
    const passwordError = getPasswordValidationError(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      router.replace("/(tabs)/inbox");
    } catch (err) {
      setError(getFriendlyErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayError = error || sessionError;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.title}>Welcome back</Text>
          <Text style={styles.subtitle}>
            Sign in to access your media library
          </Text>
        </View>

        {displayError && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{displayError}</Text>
          </View>
        )}

        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Email</Text>
            <TextInput
              testID="login-email-input"
              style={styles.input}
              value={email}
              onChangeText={(text) => {
                setEmail(text);
                setError(null);
                if (sessionError) clearSessionError();
              }}
              placeholder="you@example.com"
              placeholderTextColor={Colors.textMuted}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              editable={!isSubmitting}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.inputLabel}>Password</Text>
            <TextInput
              testID="login-password-input"
              style={styles.input}
              value={password}
              onChangeText={(text) => {
                setPassword(text);
                setError(null);
              }}
              placeholder="Your password"
              placeholderTextColor={Colors.textMuted}
              secureTextEntry={process.env.EXPO_PUBLIC_E2E_MODE !== "true"}
              autoComplete={
                process.env.EXPO_PUBLIC_E2E_MODE === "true" ? "off" : "password"
              }
              textContentType={
                process.env.EXPO_PUBLIC_E2E_MODE === "true"
                  ? "none"
                  : "password"
              }
              editable={!isSubmitting}
            />
          </View>

          <TouchableOpacity
            testID="login-submit-button"
            style={[styles.button, isSubmitting && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={isSubmitting}
            activeOpacity={0.8}
            accessibilityLabel="Sign in with email"
            accessibilityRole="button"
          >
            {isSubmitting ? (
              <ActivityIndicator color={Colors.onPrimary} />
            ) : (
              <Text style={styles.buttonText}>Sign In</Text>
            )}
          </TouchableOpacity>
        </View>

        <SocialAuthButtons
          onError={(message) => setError(message)}
          disabled={isSubmitting}
        />

        <View style={styles.footer}>
          <Text style={styles.footerText}>Don't have an account? </Text>
          <Link href="/(auth)/register" asChild>
            <TouchableOpacity>
              <Text style={styles.footerLink}>Sign Up</Text>
            </TouchableOpacity>
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    padding: Spacing.lg,
  },
  header: {
    marginBottom: Spacing.xl,
  },
  title: {
    fontSize: Typography.display.fontSize,
    fontWeight: Typography.display.fontWeight,
    color: Colors.textMain,
    letterSpacing: Typography.display.letterSpacing,
  },
  subtitle: {
    fontSize: Typography.body.fontSize,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
  },
  errorContainer: {
    backgroundColor: Colors.errorContainer,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.md,
  },
  errorText: {
    color: Colors.error,
    fontSize: Typography.small.fontSize,
  },
  form: {
    gap: Spacing.md,
  },
  inputGroup: {
    gap: Spacing.xs,
  },
  inputLabel: {
    fontSize: Typography.label.fontSize,
    fontWeight: Typography.label.fontWeight,
    color: Colors.textMain,
  },
  input: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.outlineVariant,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: 14,
    fontSize: Typography.body.fontSize,
    color: Colors.textMain,
  },
  button: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.md,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
    marginTop: Spacing.sm,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: Colors.onPrimary,
    fontSize: Typography.body.fontSize,
    fontWeight: "600",
  },
  footer: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: Spacing.xl,
  },
  footerText: {
    color: Colors.textMuted,
    fontSize: Typography.label.fontSize,
  },
  footerLink: {
    color: Colors.textMain,
    fontSize: Typography.label.fontSize,
    fontWeight: "600",
  },
});
