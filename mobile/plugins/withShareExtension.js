/**
 * Expo config plugin to configure the iOS share extension.
 *
 * This plugin modifies the iOS project during `expo prebuild` to:
 * 1. Add the App Groups entitlement to both the main app and the share extension.
 * 2. Register the custom URL scheme for receiving shared content.
 *
 * The actual share extension target is managed by the expo-share-intent plugin.
 * This plugin provides additional configuration on top of it.
 */
const { withInfoPlist, withEntitlementsPlist } = require("expo/config-plugins");

function withShareExtension(config) {
  // Add App Groups entitlement to the main app target
  config = withEntitlementsPlist(config, (modConfig) => {
    modConfig.modResults["com.apple.security.application-groups"] = [
      "group.com.mediasummarizer.app",
    ];
    return modConfig;
  });

  // Ensure the custom URL scheme is registered in Info.plist
  config = withInfoPlist(config, (modConfig) => {
    const existingSchemes = modConfig.modResults.CFBundleURLTypes || [];
    const hasScheme = existingSchemes.some(
      (entry) =>
        entry.CFBundleURLSchemes &&
        entry.CFBundleURLSchemes.includes("media-summarizer"),
    );

    if (!hasScheme) {
      existingSchemes.push({
        CFBundleURLSchemes: ["media-summarizer"],
        CFBundleURLName: "com.mediasummarizer.app",
      });
      modConfig.modResults.CFBundleURLTypes = existingSchemes;
    }

    return modConfig;
  });

  return config;
}

module.exports = withShareExtension;
