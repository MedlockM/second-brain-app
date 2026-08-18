import { ExpoConfig, ConfigContext } from "expo/config";
import {
  ConfigPlugin,
  withAppBuildGradle,
  withAppDelegate,
} from "expo/config-plugins";

/**
 * Google's reserved custom URL scheme for an OAuth client ID: the client ID with
 * its `.apps.googleusercontent.com` suffix moved to the front.
 *
 * `123-abc.apps.googleusercontent.com` -> `com.googleusercontent.apps.123-abc`
 *
 * Kept inline rather than imported from `src/lib/googleOAuth.ts` (its runtime
 * counterpart, which builds the matching `redirect_uri`): `@expo/config`
 * transpiles this file alone, so a relative `.ts` import fails to resolve. Both
 * sides derive from the same `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS`, so they cannot
 * point at different clients — only this transformation is duplicated.
 *
 * Returns `null` when the env var is missing, so a build without it declares no
 * scheme rather than a broken one.
 */
const googleReservedClientScheme = (clientId?: string): string | null => {
  const suffix = ".apps.googleusercontent.com";
  const trimmed = clientId?.trim();
  if (!trimmed || !trimmed.endsWith(suffix)) {
    return null;
  }
  const guid = trimmed.slice(0, -suffix.length);
  return guid ? `com.googleusercontent.apps.${guid}` : null;
};

const withEmbeddedDebugBundle: ConfigPlugin = (config) => {
  config = withAppBuildGradle(config, (gradleConfig) => {
    if (gradleConfig.modResults.language !== "groovy") {
      return gradleConfig;
    }

    const marker =
      "    debuggableVariants = [] // E2E: embed JS in the debug APK";
    if (!gradleConfig.modResults.contents.includes(marker)) {
      gradleConfig.modResults.contents =
        gradleConfig.modResults.contents.replace(
          "react {\n",
          `react {\n${marker}\n`,
        );
    }

    return gradleConfig;
  });

  return withAppDelegate(config, (appDelegateConfig) => {
    if (appDelegateConfig.modResults.language !== "swift") {
      return appDelegateConfig;
    }

    appDelegateConfig.modResults.contents =
      appDelegateConfig.modResults.contents.replace(
        /#if DEBUG\s+return RCTBundleURLProvider[\s\S]*?#else\s+return Bundle\.main\.url\(forResource: "main", withExtension: "jsbundle"\)\s+#endif/,
        'return Bundle.main.url(forResource: "main", withExtension: "jsbundle") // E2E: use embedded debug bundle',
      );

    return appDelegateConfig;
  });
};

export default ({ config }: ConfigContext): ExpoConfig => {
  // Google's native sign-in flow redirects to the reversed client ID of the iOS
  // OAuth client (see src/lib/googleOAuth.ts). That scheme has to be declared for
  // the callback to re-enter the app, and it is derived from the same env var the
  // runtime reads so a client rotation cannot desynchronise the two.
  //
  // Declared through `ios.scheme` / `android.scheme` rather than
  // `ios.infoPlist.CFBundleURLTypes`: those fields are *merged* into the generated
  // CFBundleURLTypes / intent filters by @expo/config-plugins, whereas setting
  // `ios.infoPlist.CFBundleURLTypes` directly makes the plugin skip the abstract
  // `scheme` property altogether and would silently drop `media-summarizer`.
  const googleIosScheme = googleReservedClientScheme(
    process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS,
  );

  const expoConfig: ExpoConfig = {
    ...config,
    name: "Media Summarizer",
    slug: "media-summarizer",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "light",
    scheme: "media-summarizer",
    splash: {
      image: "./assets/splash.png",
      resizeMode: "contain",
      backgroundColor: "#fcf9f6",
    },
    ios: {
      supportsTablet: false,
      bundleIdentifier: "com.secondbrainlabs.core",
      usesAppleSignIn: true,
      // Merged with the top-level `scheme` into CFBundleURLTypes at prebuild, so
      // `media-summarizer` (expo-router deep links) keeps working untouched.
      scheme: googleIosScheme ? [googleIosScheme] : [],
      infoPlist: {
        NSPhotoLibraryUsageDescription:
          "Used to attach images to media entries.",
        // Camera capture as an ingestion entry point (task-264): the photo is
        // sent to your library right after the shot. Declared here rather than
        // through the expo-image-picker plugin so the string stays next to the
        // photo library one and shows up in the resolved config.
        NSCameraUsageDescription:
          "Used to take a photo of a document or a page and import it into your library.",
      },
      // App Groups for sharing data between the main app and the share extension
      entitlements: {
        "com.apple.security.application-groups": [
          "group.com.secondbrainlabs.core",
        ],
      },
    },
    android: {
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#fcf9f6",
      },
      package: "com.secondbrainlabs.core",
      // Google validates an Android OAuth client on package name + signing
      // fingerprint, and documents `<package>:/oauthredirect` as its custom-scheme
      // redirect — which is exactly what expo-auth-session already builds from
      // `Application.applicationId`. Only the scheme was missing: on Android the
      // callback comes back through a Linking deep link (there is no native
      // ASWebAuthenticationSession), so it needs an intent filter to re-enter the
      // app. Merged with the top-level `scheme`, not replacing it.
      scheme: ["com.secondbrainlabs.core"],
      // Camera capture as an ingestion entry point (task-264). The runtime
      // request is made by expo-image-picker; the manifest entry is what makes
      // that request grantable.
      permissions: ["android.permission.CAMERA"],
      intentFilters: [
        {
          action: "SEND",
          category: ["DEFAULT"],
          data: [{ mimeType: "text/plain" }],
        },
        {
          action: "SEND",
          category: ["DEFAULT"],
          data: [{ mimeType: "audio/*" }],
        },
      ],
    },
    plugins: [
      "expo-router",
      "expo-secure-store",
      "expo-apple-authentication",
      "expo-font",
      [
        "expo-share-intent",
        {
          iosShareExtensionName: "ShareMedia",
          iosActivationRules: {
            NSExtensionActivationSupportsWebURLWithMaxCount: 1,
            NSExtensionActivationSupportsText: true,
            NSExtensionActivationSupportsFileWithMaxCount: 1,
          },
        },
      ],
    ],
    extra: {
      apiBaseUrl:
        process.env.EXPO_PUBLIC_API_BASE_URL ||
        "https://api.mediasummarizer.com",
      googleClientIdWeb: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB || "",
      googleClientIdIos: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS || "",
      googleClientIdAndroid:
        process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID || "",
      revenueCatAppleKey: process.env.EXPO_PUBLIC_REVENUCAT_APPLE_KEY || "",
      revenueCatGoogleKey: process.env.EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY || "",
      feedbackUrl: process.env.EXPO_PUBLIC_FEEDBACK_URL || "",
      eas: {
        projectId: "fad6e877-590d-4143-bbaa-fdd013b01c43",
      },
    },
  };

  return process.env.E2E_EMBED_DEBUG_BUNDLE === "1"
    ? withEmbeddedDebugBundle(expoConfig)
    : expoConfig;
};
