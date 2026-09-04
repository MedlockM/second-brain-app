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
/**
 * The EAS project id, declared once for the whole file.
 *
 * It is read twice — `extra.eas.projectId`, which is what links the checkout to
 * the Expo project, and the `updates.url` an OTA-capable binary polls
 * (`https://u.expo.dev/<projectId>`, the shape `eas update:configure` would have
 * written into a static `app.json`; it cannot write into a dynamic
 * `app.config.ts` and only prints what to add). Two literal copies of the UUID
 * is one copy that can go stale, and a stale `updates.url` is silent: the binary
 * polls a project that publishes nothing and simply never updates.
 */
const easProjectId = "fad6e877-590d-4143-bbaa-fdd013b01c43";

/** The launcher label, modulo the `locales/*.json` overrides. */
const appName = "Media Summarizer";

/**
 * The label under the icon in the iOS share sheet: expo-share-intent writes this
 * string verbatim into the extension's `CFBundleDisplayName`
 * (`writeIosShareExtensionFiles.js`). It used to read "ShareMedia", a name that
 * appears nowhere else in the product, so the row was unfindable even when iOS
 * did offer it (task-347) — hence a label that starts with the app's name.
 *
 * **It must never strip down to the app's own Xcode target name.** The same
 * option also names the native target and the generated `ios/<Name>/` directory,
 * with non-alphanumerics removed (`getShareExtensionName`, .../ios/constants.js),
 * and EAS resolves iOS build credentials *per target name*. task-347 set this to
 * `appName`, which strips to `MediaSummarizer` — identical to the app target — so
 * the app target got handed the extension's provisioning profile and its
 * entitlements. iOS build 5 died on it (`XCODE_BUILD_ERROR`: profile app ID
 * `…core.share-extension` "does not match the bundle ID com.secondbrainlabs.core",
 * plus a vanished Sign In with Apple capability). The failure is invisible locally
 * and costs a full EAS build slot, so keep the stripped forms distinct:
 * "Media Summarizer Share" → `MediaSummarizerShare` ≠ `MediaSummarizer`.
 *
 * The extension's bundle id derives from the app's (`<appId>.share-extension`) and
 * not from this string, so a rename needs no new App ID and no new profile.
 */
const iosShareExtensionName = "Media Summarizer Share";

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
  // Google's browser sign-in flow — iOS only — redirects to the reversed client
  // ID of the iOS OAuth client (see src/lib/googleOAuth.ts). That scheme has to be
  // declared for the callback to re-enter the app, and it is derived from the same
  // env var the runtime reads so a client rotation cannot desynchronise the two.
  // Android has no equivalent: it signs in through Credential Manager, with no
  // redirect and therefore no scheme.
  //
  // Declared through `ios.scheme` rather than `ios.infoPlist.CFBundleURLTypes`:
  // that field is *merged* into the generated CFBundleURLTypes by
  // @expo/config-plugins, whereas setting `ios.infoPlist.CFBundleURLTypes`
  // directly makes the plugin skip the abstract `scheme` property altogether and
  // would silently drop `media-summarizer`.
  const googleIosScheme = googleReservedClientScheme(
    process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS,
  );

  // The API every request of the app is addressed to, and the single place it is
  // read from the environment: it goes into `extra.apiBaseUrl` below, which the
  // app reads through `Constants.expoConfig` (src/constants/config.ts).
  //
  // **No fallback, on purpose.** This used to default to the `api.` host of
  // `mediasummarizer.com`, a domain the project does not own (no delegated zone
  // at all — MOBILE_CI_CD.md) — so a missing variable would silently have sent
  // authenticated requests, access tokens included, to a host controlled by
  // someone else. A missing configuration has to be loud, so config resolution
  // fails outright: no bundle, no build, no update can be produced without it.
  //
  // Nothing legitimate resolves this config without it: `eas build` and
  // `eas update` take it from the build profile's `env` block in eas.json, a
  // local `expo start` from mobile/.env, and mobile-e2e-maestro.yml sets it on
  // every job that prebuilds.
  const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (!apiBaseUrl) {
    throw new Error(
      "EXPO_PUBLIC_API_BASE_URL is not set and there is no fallback host. " +
        "Set it in the build profile's `env` block in mobile/eas.json (that is " +
        "what CI reads), or in mobile/.env for a local run.",
    );
  }

  const expoConfig: ExpoConfig = {
    ...config,
    name: appName,
    slug: "media-summarizer",
    version: "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "light",
    scheme: "media-summarizer",
    // EAS Update (task-340). Two fields, and the second one is the mechanism.
    //
    // `updates.url` is where the installed binary asks for a newer JS bundle.
    // `runtimeVersion` is what stops it from accepting one it cannot run: the
    // `fingerprint` policy makes the runtime version a hash of the *native*
    // project — every autolinked native module, the local
    // `modules/google-credential-manager` module, the share-extension target,
    // the intent filters, the plugin list. An update is only ever served to a
    // binary whose fingerprint matches the one it was published under, so a JS
    // bundle that calls into a native module the installed app does not have can
    // never reach it.
    //
    // That is also what makes "build only when a build is needed" decidable in
    // CI: the fingerprint either moved or it did not. See
    // .github/workflows/mobile-ota-or-build.yml and MOBILE_CI_CD.md.
    //
    // It is independent of `version` above and of the `autoIncrement` build
    // numbers in eas.json, which is why a fingerprint runtime version and
    // `appVersionSource: "remote"` coexist without interfering.
    updates: {
      url: `https://u.expo.dev/${easProjectId}`,
    },
    runtimeVersion: {
      policy: "fingerprint",
    },
    // The eleven V1 locales, declared at the *native* level.
    //
    // This is what makes the OS treat the app as multilingual: the picker
    // intersects the locales the binary declares (`CFBundleLocalizations` on
    // iOS, `res/values-<lang>/` on Android) with the user's ordered preferred
    // languages. Without it the app is English-only to the system whatever the
    // JS bundle contains — the app name and the two permission prompts would
    // stay English on a French phone, and iOS would not offer the per-app
    // language control at all.
    //
    // The files carry the app name (a brand, identical in every locale) and the
    // two `infoPlist` permission strings, which is everything the OS renders
    // outside the JS bundle.
    //
    // Each file is split into `ios` and `android` sections, and that split is
    // load-bearing. Expo writes whatever keys it finds straight into the native
    // resources without renaming them (`@expo/config-plugins`,
    // `android/Locales.js`), and only keys outside those two sections go to both
    // platforms. Left flat, the three iOS keys landed in
    // `res/values-b+<lang>/strings.xml` where none of them means anything, and
    // none of them exists in `res/values/strings.xml` — so `lintVitalRelease`
    // failed the Android release build with 33 `ExtraTranslation` errors
    // (11 locales x 3 keys) and no AAB could be produced. Android's half is
    // `app_name`, the one string the platform actually renders as the launcher
    // label, and it exists in the default locale, so lint is satisfied.
    locales: {
      en: "./locales/en.json",
      fr: "./locales/fr.json",
      es: "./locales/es.json",
      de: "./locales/de.json",
      it: "./locales/it.json",
      pt: "./locales/pt.json",
      nl: "./locales/nl.json",
      ja: "./locales/ja.json",
      zh: "./locales/zh.json",
      ar: "./locales/ar.json",
      hi: "./locales/hi.json",
    },
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
      config: {
        // Writes ITSAppUsesNonExemptEncryption=false into the ipa's Info.plist.
        // The app only ever uses platform TLS (HTTPS to the API, Google/Apple
        // OAuth, RevenueCat) — no proprietary cryptography — which is exempt
        // under Apple's export rules. Declared here rather than answered at the
        // prompt: without it `eas build` asks "iOS app only uses
        // standard/exempt encryption?" on every interactive run, and App Store
        // Connect asks for the export-compliance tick on every TestFlight
        // upload. Set it to `true` only if real non-exempt crypto ever ships.
        usesNonExemptEncryption: false,
      },
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
      // No `scheme` for Google here, deliberately. Google refuses a custom URI
      // scheme `redirect_uri` for an Android OAuth client — `Error 400:
      // invalid_request`, "Custom URI scheme is not enabled for your Android
      // client", with no setting to turn it on — so `com.secondbrainlabs.core:/`
      // was an intent filter nothing could ever call back into. Android now signs
      // in through Credential Manager (`modules/google-credential-manager`),
      // which needs no redirect at all.
      // Camera capture as an ingestion entry point (task-264). The runtime
      // request is made by expo-image-picker; the manifest entry is what makes
      // that request grantable.
      permissions: ["android.permission.CAMERA"],
    },
    plugins: [
      "expo-router",
      "expo-secure-store",
      "expo-localization",
      "expo-apple-authentication",
      "expo-font",
      // Media covers (task-304). The config plugin is what wires SDWebImage on
      // iOS and Glide on Android; without it `expo-image` falls back to a
      // JS-side loader with no disk cache, which is the whole reason it was
      // chosen over React Native's `Image`.
      "expo-image",
      [
        "expo-share-intent",
        {
          // Share-sheet label *and* native target name. See the constant: the
          // stripped form must not collide with the app target.
          iosShareExtensionName,
          // These predicates *are* the share sheet: iOS evaluates them against
          // the items being shared and only renders the row when one matches
          // (they become the `NSExtensionActivationRule` of the generated
          // ShareExtension-Info.plist). A missing key is a whole class of
          // content the app is invisible for.
          //
          // `…SupportsImage…` is what covers a screenshot or a photo: the
          // screenshot editor and Photos hand over a `public.image` attachment,
          // which `…SupportsFile…` does not match — without it the app simply
          // did not exist in the share sheet of a screenshot (task-347).
          //
          // No `NSExtensionActivationSupportsMovieWithMaxCount`, deliberately:
          // video has no backend route, so claiming it would put the app in the
          // share sheet for content it can only refuse.
          iosActivationRules: {
            NSExtensionActivationSupportsWebURLWithMaxCount: 1,
            NSExtensionActivationSupportsText: true,
            NSExtensionActivationSupportsImageWithMaxCount: 1,
            NSExtensionActivationSupportsFileWithMaxCount: 1,
          },
          // Android SEND intent filters for share intents. Declared here rather than
          // in `android.intentFilters` so there's a single source of truth and the
          // plugin doesn't add its default `["text/*"]`. Specific MIME types rather
          // than `application/*` so the app only appears for files it can handle
          // (PDF, Office docs, images, audio), not for arbitrary application files
          // (.zip, executables, etc.) that would be refused anyway. The handler
          // (ShareIntentContext) validates extensions and enforces the 50 MB ceiling.
          androidIntentFilters: [
            "text/*",
            "audio/*",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "image/*",
          ],
        },
      ],
    ],
    extra: {
      apiBaseUrl,
      googleClientIdWeb: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB || "",
      googleClientIdIos: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS || "",
      // No Android client ID: Credential Manager takes the *Web* client ID as
      // `serverClientId`. The Android OAuth client still has to exist on Google's
      // side (it is matched on package name + signing fingerprint), but its ID
      // never reaches the app.
      revenueCatAppleKey: process.env.EXPO_PUBLIC_REVENUCAT_APPLE_KEY || "",
      revenueCatGoogleKey: process.env.EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY || "",
      feedbackUrl: process.env.EXPO_PUBLIC_FEEDBACK_URL || "",
      eas: {
        projectId: easProjectId,
      },
    },
  };

  return process.env.E2E_EMBED_DEBUG_BUNDLE === "1"
    ? withEmbeddedDebugBundle(expoConfig)
    : expoConfig;
};
