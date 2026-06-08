import { ExpoConfig, ConfigContext } from "expo/config";

export default ({ config }: ConfigContext): ExpoConfig => ({
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
        data: [
          { mimeType: "audio/*" },
        ],
      },
    ],
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    "expo-apple-authentication",
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
    "./plugins/withShareExtension",
  ],
  extra: {
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.mediasummarizer.com",
    googleClientIdWeb: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB || "",
    googleClientIdIos: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS || "",
    googleClientIdAndroid: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID || "",
    revenueCatAppleKey: process.env.EXPO_PUBLIC_REVENUCAT_APPLE_KEY || "",
    revenueCatGoogleKey: process.env.EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY || "",
    feedbackUrl: process.env.EXPO_PUBLIC_FEEDBACK_URL || "https://percole.canny.io",
    eas: {
      projectId: process.env.EAS_PROJECT_ID || "placeholder-project-id",
    },
  },
});
