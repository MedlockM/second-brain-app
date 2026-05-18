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
    bundleIdentifier: "com.mediasummarizer.app",
    infoPlist: {
      NSPhotoLibraryUsageDescription:
        "Used to attach images to media entries.",
    },
    // App Groups for sharing data between the main app and the share extension
    entitlements: {
      "com.apple.security.application-groups": [
        "group.com.mediasummarizer.app",
      ],
    },
  },
  android: {
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: "#fcf9f6",
    },
    package: "com.mediasummarizer.app",
    intentFilters: [
      {
        action: "SEND",
        category: ["DEFAULT"],
        data: [{ mimeType: "text/plain" }],
      },
    ],
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    [
      "expo-share-intent",
      {
        iosShareExtensionName: "ShareMedia",
        iosActivationRules: {
          NSExtensionActivationSupportsWebURLWithMaxCount: 1,
          NSExtensionActivationSupportsText: true,
        },
      },
    ],
    "./plugins/withShareExtension",
  ],
  extra: {
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.mediasummarizer.com",
    eas: {
      projectId: "placeholder-project-id",
    },
  },
});
