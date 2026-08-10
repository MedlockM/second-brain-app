import { ExpoConfig, ConfigContext } from "expo/config";
import {
  ConfigPlugin,
  withAppBuildGradle,
  withAppDelegate,
} from "expo/config-plugins";

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
      infoPlist: {
        NSPhotoLibraryUsageDescription:
          "Used to attach images to media entries.",
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
