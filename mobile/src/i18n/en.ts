/**
 * The reference catalogue.
 *
 * `en` is the app's development language and its fallback, and it is what the
 * `TranslationKey` type is derived from: a key that is not here cannot be
 * passed to `t`, and a key that is here has to be present in all ten other
 * catalogues. Keys are flat and dot-namespaced by the screen or component that
 * owns them, with `common.*` for the words that recur everywhere.
 *
 * Plural families are spelled out as `<base>.one` / `<base>.other` and read
 * through `tCount`, which picks the category with `Intl.PluralRules` — never by
 * gluing a count onto a fixed suffix. A catalogue whose language needs more
 * categories (Arabic has six) simply declares them alongside.
 */
export const en = {
  // --- Words that belong to no single screen ---
  "common.ok": "OK",
  "common.cancel": "Cancel",
  "common.retry": "Retry",
  "common.delete": "Delete",
  "common.save": "Save",
  "common.done": "Done",
  "common.close": "Close",
  "common.dismiss": "Dismiss",
  "common.loading": "Loading...",
  "common.continue": "Continue",
  "common.back": "Back",
  "common.error": "Error",
  "common.untitled": "Untitled",
  "common.somethingWentWrong": "Something went wrong",
  "common.itemCount.one": "{count} item",
  "common.itemCount.other": "{count} items",

  // --- Free trial notice ---
  "trial.badge": "Free Trial",
  "trial.lastDay": "Free Trial - last day",
  "trial.daysLeft.one": "Free Trial - {count} day left",
  "trial.daysLeft.other": "Free Trial - {count} days left",

  // --- Home tiles ---
  "home.tile.saving": "Saving…",
  "home.tile.saveFailed": "Could not be saved",
  "home.tile.a11yCollection": "Collection {name}, {count}",
  "home.tile.a11ySaving": "{url}, being saved",
  "home.tile.a11ySaveFailed": "{url} could not be saved",
  "home.tile.a11yByCreator": "{title} by {creator}",

  // --- Minutes warning ---
  "quota.warning.trial":
    "You've used {percent}% of your free trial minutes.",
  "quota.warning.trialWithDate":
    "You've used {percent}% of your free trial minutes. They do not refill — your trial ends on {date}.",
  "quota.warning.monthly": "You've used {percent}% of this month's minutes.",
  "quota.warning.monthlyWithDate":
    "You've used {percent}% of this month's minutes. They reset on {date}.",
  "quota.seePlans": "See plans",
  "quota.dismissWarning": "Dismiss the minutes warning",

  // --- AI artifacts, shared between the media and collection scopes ---
  "artifacts.sourceCount.one": "{count} source",
  "artifacts.sourceCount.other": "{count} sources",
  "artifacts.status.queued": "Queued",
  "artifacts.status.generating": "Generating...",
  "artifacts.status.failed": "Failed",
  // Shown where the "Generate" button was, once an artifact covers the current
  // sources: there is nothing left to ask for on this type.
  "artifacts.status.generated": "Generated",
  "artifacts.history.a11yRow": "{type}: {title}",
  // --- Media type badges ---
  "mediaType.podcast": "PODCAST",
  "mediaType.article": "ARTICLE",
  "mediaType.video": "VIDEO",
  "mediaType.short": "SHORT",
  "mediaType.audio": "AUDIO",
  "mediaType.text": "TEXT",
  "mediaType.document": "DOC",
  "mediaType.link": "LINK",
  "mediaCard.a11yByCreator": "{title} by {creator}, {type}",
  "mediaCard.a11yFromDomain": "{title}, {type} from {domain}",
  "mediaCard.longPressHint": "Double tap and hold to move or delete this source",

  // --- Long-press actions on a media vignette in Library ---
  "mediaActions.eyebrow": "Manage source",
  "mediaActions.move.label": "Move",
  "mediaActions.move.description": "Put this source in another collection.",
  "mediaActions.delete.label": "Delete",
  "mediaActions.delete.description": "Remove this source from your library.",
  "mediaActions.deleteTitle": "Delete this source?",
  "mediaActions.deleteBody":
    "“{title}” will be removed from your library. This cannot be undone.",
  "mediaActions.deleteFailed":
    "This source could not be deleted. It is still in your library.",

  // --- Add-source sheet ---
  "addSource.title": "Add to your inbox",
  "addSource.importFile.label": "Import a file",
  "addSource.importFile.description":
    "A PDF, an Office document, an image or an audio file from your phone.",
  "addSource.importPhoto.label": "Import a photo",
  "addSource.importPhoto.description":
    "Pick a shot you already have in your gallery.",

  // --- Social sign-in ---
  "auth.or": "or",
  "auth.continueWithGoogle": "Continue with Google",
  "auth.signInWithApple": "Sign in with Apple",
  "auth.google.notCompleted":
    "Google sign-in was not completed. Please try again.",
  "auth.google.noIdToken": "Failed to obtain Google ID token. Please try again.",
  "auth.google.failed":
    "Google sign-in could not be completed. Please try again.",
  "auth.apple.noIdentityToken":
    "Failed to obtain Apple identity token. Please try again.",

  // --- Artifact tiles and panel ---
  "artifacts.type.summaryShort": "Summary",
  "artifacts.type.summaryDetailed": "Detailed summary",
  "artifacts.type.notes": "Learning notes",
  "artifacts.type.flashcards": "Flashcards",
  "artifacts.type.quiz": "Quiz",
  "artifacts.generate": "Generate",
  "artifacts.a11yGenerate": "Generate {label}",
  "artifacts.processing": "Processing...",
  "artifacts.panel.generateHeading": "Generate",
  "artifacts.panel.generatedHeading": "Generated",
  "artifacts.panel.retryA11y": "Retry loading generated content",
  "artifacts.panel.empty":
    "Nothing generated yet. Pick a format above to create one.",
  // --- Durations and relative time ---
  "duration.minutes.one": "{count} min",
  "duration.minutes.other": "{count} min",
  "duration.hours.one": "{count} h",
  "duration.hours.other": "{count} h",
  "duration.hoursMinutes": "{hours} {minutes}",
  "time.justNow": "Just now",
  "time.minutesAgo.one": "{count}m ago",
  "time.minutesAgo.other": "{count}m ago",
  "time.hoursAgo.one": "{count}h ago",
  "time.hoursAgo.other": "{count}h ago",
  "time.yesterday": "Yesterday",
  "time.today": "Today",
  "time.daysAgo.one": "{count}d ago",
  "time.daysAgo.other": "{count}d ago",

  // --- Subscription state ---
  "subscription.resetLabel.trialEnds": "FREE TRIAL ENDS",
  "subscription.resetLabel.resets": "RESETS",
  "subscription.resetLabel.ends": "ENDS",
  "subscription.resetLabel.periodEnds": "PERIOD ENDS",
  "subscription.status.paymentIssue": "Payment issue",
  "subscription.status.cancelled": "Cancelled",

  // --- Errors, worded from a code or a matched pattern ---
  "error.sessionExpired": "Your session has expired. Please sign in again.",
  "error.invalidCredentials": "Invalid email or password. Please try again.",
  "error.emailNotVerified":
    "Please verify your email address before signing in.",
  "error.emailAlreadyExists": "An account with this email already exists.",
  "error.invalidVerificationToken":
    "Invalid verification link. Please request a new one.",
  "error.userNotFound":
    "No account found with this email address. Please check the email or create a new account.",
  "error.notAuthorized": "You don't have permission to perform this action.",
  "error.notFound": "Content not found. Please try searching for something else.",
  "error.mediaNotFound": "This media item was not found or is no longer available.",
  "error.artifactNotFound": "This artifact was not found or is no longer available.",
  "error.invalidUrl": "This link is invalid. Please try another URL.",
  "error.unsupportedUrl": "This link is not supported yet. Please try another source.",
  "error.validation": "Please fill in all required fields.",
  "error.rateLimited": "Too many requests. Please wait a moment and try again.",
  "error.conflict":
    "This action conflicts with existing data. Please refresh and try again.",
  "error.badRequest": "Please check your input and try again.",
  "error.invalidEmail": "Please enter a valid email address.",
  "error.passwordTooShort": "Password must be at least 8 characters long.",
  "error.passwordsDoNotMatch": "Passwords do not match. Please try again.",
  "error.network": "Network error. Please check your connection and try again.",
  "error.timeout": "Request timed out. Please try again.",
  "error.outOfMinutes":
    "You're out of minutes for this period. Upgrade to keep importing audio and video.",

  // --- Quota refusals, worded from the figures the backend sends ---
  "quota.title.outOfMinutes": "Out of minutes",
  "quota.title.itemTooLong": "Too long for one import",
  "quota.refusal.noPlan":
    "Your plan has ended. Subscribe to keep saving to your library.",
  "quota.refusal.outOfMinutes":
    "You're out of minutes for this period. Upgrade to process this now.",
  "quota.refusal.outOfMinutesUntil":
    "You're out of minutes until {date}. Upgrade to process this now.",
  "quota.refusal.needsMore":
    "This import needs {needed} and you have {remaining} left until {date}. Upgrade to process it now.",
  "quota.refusal.needsMoreNoDate":
    "This import needs {needed} and you have {remaining} left. Upgrade to process it now.",
  "quota.refusal.itemTooLong":
    "This is {duration} long, over the {max} a single import can use on your plan. Split it into shorter parts.",
  "quota.refusal.itemTooLongGeneric":
    "This is too long for a single import on your plan. Split it into shorter parts.",

  // --- Artifact refusals ---
  "artifacts.refusal.collectionEmpty":
    "This collection has no source with a transcript yet. Add media, or wait for the ones you saved to finish processing.",
  "artifacts.refusal.mediaEmpty":
    "This item has no transcript yet, so there is nothing to generate from.",
  "artifacts.refusal.tooManySources":
    "This collection has {count} sources, over the {max} a single generation can read. Generate on a smaller sub-collection instead.",
  "artifacts.refusal.tooMuchText":
    "There is too much text here for one generation. Generate on a smaller sub-collection instead.",
  "artifacts.refusal.sourcesPending.one":
    "{count} source is still being prepared. Try again in a moment.",
  "artifacts.refusal.sourcesPending.other":
    "{count} sources are still being prepared. Try again in a moment.",
  "artifacts.refusal.transcriptPending":
    "The transcript is still being prepared. Try again in a moment.",
  "artifacts.refusal.generic": "Unable to start this generation. Please try again.",

  // --- Plans and paywall copy ---
  "plan.hourlyRate": "≈ {price} an hour",
  "plan.card.allowance": "{duration} of audio and video",
  "plan.card.perImport": "up to {duration} in one import",
  "plan.rec.cappedLargest":
    "You used up all {duration} this period. {plan} is the largest plan we offer.",
  "plan.rec.cappedNextUp":
    "You used up all {duration} this period. {plan} is the next size up.",
  "plan.rec.overLargest":
    "You've used {duration} this period — more than any plan includes. {plan} is the largest we offer.",
  "plan.rec.trialFloor":
    "You've used {duration} of your trial so far. {plan} keeps you on the plan you're already using.",
  "plan.rec.covering":
    "You've used {duration} this period. {plan} is the smallest plan that covers that.",
  "plan.badge.recommended": "RECOMMENDED FOR YOU",
  "plan.badge.yourTrial": "YOUR TRIAL PLAN",
  "plan.badge.bestValue": "BEST VALUE",
  "paywall.reason.trialOut":
    "Your trial minutes are spent, and they do not refill. Pick a plan to keep importing audio and video.",
  "paywall.reason.outNoDate":
    "You're out of minutes for this period. A larger plan gives you more now.",
  "paywall.reason.outWithDate":
    "You're out of minutes until {date}. A larger plan gives you more now.",
  "paywall.reason.trialLow":
    "{left} left in your trial, and trial minutes do not refill.",
  "paywall.reason.lowNoDate": "{left} left this period.",
  "paywall.reason.lowWithDate": "{left} left until {date}.",
  "plan.minutesRule":
    "Minutes cover audio and video we transcribe. Reading your library is unlimited.",
  "plan.legend.realLength":
    "Audio and video count their real length, minute for minute.",
  "plan.legend.captions":
    "A video that already has subtitles we can buy costs {duration}, however long it is.",
  "plan.legend.documents":
    "A PDF, an Office document or a photo we read the text off costs 1 min per {pages} pages.",
  "plan.legend.collections":
    "A generation over a whole collection costs 1 min per {sources} items in it. On a single item it is free.",
  "plan.legend.free":
    "Articles, web pages, TikToks and Instagram photo posts cost nothing at all: they are not transcribed.",
  "plan.legend.overLimit":
    "Past a plan's single-import maximum, an import is refused rather than billed — split it into shorter parts.",
  "plan.list.separator": ", ",
  "plan.list.lastConjunction": "{list} and {last}",
  "plan.highlight.capture":
    "Save from any app: YouTube, podcasts, TikTok, Instagram, X, articles, PDFs, documents, photos and audio files",
  "plan.highlight.read":
    "Read the full transcript, translated into your reading language",
  "plan.highlight.generate":
    "Generate {list} on demand, per item or per collection",
  "plan.highlight.organise":
    "Organise in collections and tags, search everything, daily digest",
  "plan.includes.capture.title": "Save anything, from any app",
  "plan.includes.capture.links":
    "Share a link from any app, or paste one: YouTube videos, podcast episodes from Apple Podcasts, Spotify, Deezer or any RSS feed, TikToks, Instagram reels and photo posts, X posts, news articles and any web page.",
  "plan.includes.capture.files":
    "Send a file from your phone: PDF, Word, PowerPoint and Excel documents, photos and screenshots we read the text off, and audio recordings (MP3, M4A, WAV, FLAC, AAC, OGG, Opus).",
  "plan.includes.read.title": "Read it, whatever it was",
  "plan.includes.read.transcripts":
    "Audio and video come back as full text, transcribed word for word, so an episode you have no time to listen to is one you can read, skim or search instead.",
  "plan.includes.read.translation":
    "Transcripts are translated into your reading language, {count} to choose from, and you can change it whenever you like.",
  "plan.includes.generate.title": "Turn it into something you keep",
  "plan.includes.generate.onDemand": "On any item, on demand: {list}.",
  "plan.includes.generate.collection":
    "Run the same generations across a whole collection to get one synthesis of everything you filed in it.",
  "plan.includes.generate.kept":
    "Every generation is kept, so you can come back to it or ask for a fresh one later.",
  "plan.includes.organise.title": "Find it again months later",
  "plan.includes.organise.file":
    "File anything into collections and tags, at the moment you save it or any time after.",
  "plan.includes.organise.search":
    "Full-text search across everything you have ever saved, transcripts included.",
  "plan.includes.organise.digest":
    "A daily and a weekly digest of what came in and what is worth going back to.",
  "plan.includes.minutes.title": "What the monthly minutes count",
  "plan.trial.accessFull": "full access",
  "plan.trial.accessTier": "{tier} access",
  "plan.trial.generic":
    "Your free trial is running: {access}, at no charge and nothing to cancel.",
  "plan.trial.genericWithDate":
    "Your free trial is running: {access} until {date}, at no charge and nothing to cancel.",
  "plan.trial.days":
    "Your {days}-day free trial is running: {access}, at no charge and nothing to cancel.",
  "plan.trial.daysWithDate":
    "Your {days}-day free trial is running: {access} until {date}, at no charge and nothing to cancel.",
  // --- Account: plan card ---
  "account.plan.heading": "YOUR PLAN",
  "account.plan.checking": "Checking your plan...",
  "account.plan.unavailable": "Plan status unavailable",
  "account.plan.unavailableHint":
    "We could not load your subscription details. Your plan itself is unaffected.",
  "account.plan.retryA11y": "Retry loading plan details",
  "account.plan.none": "No active plan",
  "account.plan.noneHint":
    "Your minutes and reset date appear here once a subscription is active.",
  "account.plan.freeTrial": "Free trial",
  "account.plan.active": "Active plan",
  "account.plan.minutesLeft": "MINUTES LEFT",
  "account.plan.minutesLeftA11y":
    "{remaining} of {included} minutes left this period",
  "account.plan.unknownDate": "Unknown",
  "account.plan.resetDateA11y": "{label} {date}",
  "account.plan.resetDateUnknownA11y": "Reset date unknown",
  "account.plan.minutesRuleTrial": "{rule} Trial minutes do not refill.",
  // --- Transcript reader ---
  "transcript.heading": "Transcript",
  "transcript.empty": "No transcript available yet.",
  "transcript.emptyHint": "Transcript will appear once processing completes.",
  "transcript.status.pending": "Transcript processing will start soon.",
  "transcript.status.extracting": "Extracting audio content...",
  "transcript.status.transcribing": "Transcribing audio to text...",
  "transcript.status.ready": "Transcript is ready.",
  "transcript.status.failed": "Transcript processing failed.",
  "transcript.paragraphCount.one": "{count} paragraph",
  "transcript.paragraphCount.other": "{count} paragraphs",
  "transcript.loading": "Loading transcript…",
  "transcript.notAvailable": "Transcript content is not available for this item.",
  "transcript.retryA11y": "Retry loading transcript",
  // --- Sign in / sign up ---
  "auth.email": "Email",
  "auth.password": "Password",
  "auth.emailPlaceholder": "you@example.com",
  "login.title": "Welcome back",
  "login.subtitle": "Sign in to access your media library",
  "login.passwordPlaceholder": "Your password",
  "login.submit": "Sign In",
  "login.submitA11y": "Sign in with email",
  "login.noAccount": "Don't have an account?",
  "login.signUpLink": "Sign Up",
  "register.title": "Create account",
  "register.subtitle": "Start building your media knowledge base",
  "register.passwordPlaceholder": "At least 6 characters",
  "register.submit": "Create Account",
  "register.submitA11y": "Create account with email",
  "register.hasAccount": "Already have an account?",
  "register.signInLink": "Sign In",
  // --- Reading language setting ---
  "common.goBack": "Go back",
  "readingLanguage.title": "Reading Language",
  "readingLanguage.selectA11y": "Select {language} as reading language",
  "readingLanguage.disclaimer":
    "Changing this setting affects future content only. Existing summaries and translations will not be re-processed.",
  "readingLanguage.saved": "Language updated successfully",
  "readingLanguage.saveA11y": "Save reading language",

  // --- Delete account ---
  "deleteAccount.title": "Delete Account",
  "deleteAccount.warningTitle": "This cannot be undone",
  "deleteAccount.warningBody":
    "Deleting your account erases it permanently, along with everything you saved. We cannot restore it afterwards, not even on request.",
  "deleteAccount.erasedHeading": "What gets erased",
  "deleteAccount.erased.library": "Your library, folders and tags",
  "deleteAccount.erased.artifacts":
    "Every transcript, summary, note and flashcard",
  "deleteAccount.erased.schedule": "Your review schedule and digests",
  "deleteAccount.erased.search": "Your search results across the app",
  "deleteAccount.erased.identity": "Your email address and sign-in details",
  "deleteAccount.subscriptionHeading": "Your subscription",
  "deleteAccount.subscriptionBodyApple":
    "Deleting your account does not cancel your subscription. Apple keeps billing you until you cancel it in your store settings, so cancel there first.",
  "deleteAccount.subscriptionBodyGoogle":
    "Deleting your account does not cancel your subscription. Google keeps billing you until you cancel it in your store settings, so cancel there first.",
  "deleteAccount.manageApple": "Manage subscription in the App Store",
  "deleteAccount.manageGoogle": "Manage subscription in the Play Store",
  "deleteAccount.copyHeading": "Want a copy first?",
  "deleteAccount.copyBody":
    "Email us before you delete and we will send you a copy of your data within one month.",
  "deleteAccount.emailA11y": "Email {address}",
  "deleteAccount.acknowledge":
    "I understand my account and all my data will be erased permanently.",
  "deleteAccount.acknowledgeA11y": "I understand this cannot be undone",
  "deleteAccount.submit": "Delete My Account",
  "deleteAccount.submitA11y": "Delete my account",
  "deleteAccount.confirmTitle": "Delete account?",
  "deleteAccount.confirmBody":
    "This permanently erases your account and everything in it. This cannot be undone.",
  "deleteAccount.confirmAction": "Delete forever",
  // --- Account tab ---
  "account.title": "Account",
  "account.notSet": "Not set",
  "account.subscription.manage": "Manage subscription",
  "account.subscription.manageHint": "Change plan or restore a purchase",
  "account.subscription.viewPlans": "View plans",
  "account.subscription.viewPlansHint": "See what each subscription includes",
  "account.subscription.upgrade": "Upgrade",
  "account.subscription.upgradeHint": "Unlock more minutes of audio and video",
  "account.featureRequests": "Feature Requests",
  "account.reportBug": "Report a Bug",
  "account.signOut": "Sign Out",
  "account.signOutConfirm": "Are you sure you want to sign out?",
  "account.signOutAction": "Yes, sign out",
  "account.feedbackUnavailable": "Feedback unavailable",
  "account.feedbackUnavailableBody":
    "The feedback board is not configured yet. Please try again later.",

  // --- Interface language setting ---
  "uiLanguage.title": "App Language",
  "uiLanguage.disclaimer":
    "This is the language of the app itself. What your summaries and transcripts are written in is the reading language, set separately.",
  "uiLanguage.followDevice": "Match my device",
  "uiLanguage.selectA11y": "Use {language} for the app",
  "settings.uiLanguage.restartTitle": "Restart to finish switching",
  "settings.uiLanguage.restartBody":
    "This language is read right to left, so the app has to restart before the layout follows. Close it and open it again.",
  // --- Onboarding: reading language ---
  "onboarding.language.title": "Choose your reading language",
  "onboarding.language.subtitle":
    "Content will be translated to this language when needed.",
  "onboarding.language.continueA11y": "Continue with selected language",
  // --- Library / search tab ---
  "mediaType.unknownSource": "Unknown",
  "search.placeholder": "Search your library...",
  "search.clearA11y": "Clear search query",
  "search.collections": "Collections",
  "search.allMedia": "All media",
  "search.noCollections":
    "No collections yet. Organize media into collections when you save them.",
  "search.openCollectionA11y": "Open collection {name}",
  "search.resultCount.one": "{count} result",
  "search.resultCount.other": "{count} results",
  "search.endOfResults": "End of results",
  "search.noResultsTitle": "No results found",
  "search.noMatches": "No matches for \"{query}\". Try different keywords.",
  "search.emptyLibrary": "Your library is empty",
  "search.emptyLibraryHint":
    "Share a link from any app, or import a file from the Inbox, and it shows up here.",
  "search.failed": "Search failed",
  "search.collectionsLoadFailed": "Unable to load your collections.",
  "search.libraryLoadFailed": "Unable to load your library.",
  "search.retryLibraryA11y": "Retry loading your library",
  "search.retryCollectionsA11y": "Retry loading collections",
  "search.retrySearchA11y": "Retry the search",
  // --- Bottom tab bar ---
  "tabs.home": "Home",
  "tabs.search": "Search",
  "tabs.digest": "Digest",
  // --- Home tab ---
  "home.loading": "Loading your inbox...",
  "home.retryA11y": "Retry loading inbox",
  "home.continueLearning": "Continue learning",
  "home.recentlyAdded": "Recently added",
  "home.takePhotoA11y": "Take a photo",
  "home.digest": "Daily Digest",
  "home.digestA11y": "Open Daily Digest",
  "home.digestA11yWithCount": "Open Daily Digest, {count}",
  "home.empty": "Your shared media will appear here.",
  "home.emptyHint":
    "Share a link from any app, or tap + to import a file or take a photo.",
  "home.untitledCollection": "Collection",
  // --- Digest tab ---
  "digest.daily": "Daily",
  "digest.weekly": "Weekly",
  "digest.dailyTitle": "Your Day in Review",
  "digest.weeklyTitle": "Your Week in Review",
  "digest.dailySubtitle.one": "{count} insight from today",
  "digest.dailySubtitle.other": "{count} insights from today",
  "digest.weeklySubtitle.one": "{count} insight ready for review",
  "digest.weeklySubtitle.other": "{count} insights ready for review",
  "digest.loadFailed": "Failed to load digest",
  "digest.tryAgain": "Try Again",
  "digest.emptyDaily": "No insights yet today",
  "digest.emptyWeekly": "No insights this week",
  "digest.emptyDailyHint":
    "Share media to your library and check back later for your personalized digest.",
  "digest.emptyWeeklyHint":
    "Process some media throughout the week to see your weekly summary here.",
  "digest.readTime.one": "{count}m read",
  "digest.readTime.other": "{count}m read",
  "digest.type.podcast": "Podcast",
  "digest.type.article": "Article",
  "digest.type.youtube": "YouTube",
  "digest.type.video": "Video",
  "digest.type.audio": "Audio",
  "digest.type.text": "Text",
  // --- Tag picker ---
  "tags.selectedCount.one": "{count} tag",
  "tags.selectedCount.other": "{count} tags",
  "tags.saveA11y": "Save tags",
  "tags.removeA11y": "Remove {name}",
  "tags.addPlaceholder": "Add a tag",
  "tags.createA11y": "Create tag \"{name}\"",
  "tags.otherHeading": "OTHERS",
  "tags.loadFailed": "Failed to load tags",
  "tags.createFailed": "Failed to create tag",
  "tags.saveFailed": "Failed to save tags",
  // --- Collection picker (modal) ---
  "collectionPicker.title": "Collection",
  "collectionPicker.saveA11y": "Save selection",
  "collectionPicker.searchPlaceholder": "Search",
  "collectionPicker.unsorted": "Unsorted",
  "collectionPicker.myCollections": "My collections",
  "collectionPicker.createA11y": "Create new collection",
  "collectionPicker.namePlaceholder": "Collection name",
  "collectionPicker.confirm": "Confirm",
  "collectionPicker.collapse": "Collapse",
  "collectionPicker.expand": "Expand",
  "collectionPicker.noMatches": "No collections match your search",
  "collectionPicker.loadFailed": "Failed to load collections",
  "collectionPicker.saveFailed": "Failed to save collection",
  "collectionPicker.createFailed": "Failed to create collection",

  // --- Collections explorer ---
  "collections.loading": "Loading collections...",
  "collections.loadFailed": "Unable to load your collections. Please try again.",
  "collections.empty": "No collections yet",
  "collections.emptyHint":
    "Organize media into collections when you save them to find them here.",
  "collections.emptyFolder": "Empty",
  "collections.childCount.one": "{count} collection",
  "collections.childCount.other": "{count} collections",
  // --- Media detail ---
  "media.tab.reader": "Reader",
  "media.tab.ai": "AI",
  "media.sectionsA11y": "Media sections",
  "media.loadFailed": "Unable to load media details.",
  "media.retryA11y": "Retry loading media details",
  "media.processingHint": "This usually takes less than a minute.",
  "media.timeoutTitle": "This is taking longer than usual.",
  "media.timeoutHint": "Pull down to refresh or come back later.",
  "media.refresh": "Refresh",
  "media.refreshA11y": "Refresh media status",
  "media.failedTitle": "Processing failed",
  "media.failedFallback": "An unexpected error occurred.",
  "media.processingFailed": "Processing failed. Please try again later.",
  "media.processing.audio": "Transcribing audio...",
  "media.processing.video": "Transcribing video...",
  "media.processing.extracting": "Extracting content...",
  "media.processing.generating": "Generating text...",
  "media.transcriptLoadFailed": "Unable to load the transcript right now.",
  "media.movedToNamed": "Moved to \"{name}\"",
  "media.movedToCollection": "Moved to collection",
  "media.removedFromCollection": "Removed from collection",
  "media.openFailed": "Couldn't open {host}",
  "media.moveToCollectionA11y": "Move to collection",
  "media.shareA11y": "Share",

  // --- Collection detail ---
  "collection.tab.sources": "Sources",
  "collection.tab.ai": "AI",
  "collection.sectionsA11y": "Collection sections",
  "collection.loadFailed": "Unable to load this collection. Please try again.",
  "collection.retryA11y": "Retry loading collection",
  "collection.artifactsLoadFailed":
    "Unable to load generated content. Please try again.",
  "collection.empty": "This collection is empty",
  "collection.emptyHint":
    "Media you save into this collection will show up here.",
  // --- Bug report ---
  "bugReport.subject": "Subject",
  "bugReport.subjectPlaceholder": "Brief summary of the issue",
  "bugReport.subjectA11y": "Bug report subject",
  "bugReport.description": "Description",
  "bugReport.descriptionPlaceholder":
    "Steps to reproduce, what you expected, what happened instead...",
  "bugReport.descriptionA11y": "Bug report description",
  "bugReport.attachment": "Attachment (optional)",
  "bugReport.attach": "Attach File",
  "bugReport.attachA11y": "Attach a file to the bug report",
  "bugReport.attachChoose": "Choose a source",
  "bugReport.photoLibrary": "Photo Library",
  "bugReport.files": "Files",
  "bugReport.removeFileA11y": "Remove attached file",
  "bugReport.submit": "Submit",
  "bugReport.submitA11y": "Submit bug report",
  "bugReport.submitting": "Submitting report...",
  "bugReport.uploading": "Uploading attachment...",
  "bugReport.submitted": "Report Submitted",
  "bugReport.ticketId": "Ticket ID",
  "bugReport.doneA11y": "Done, return to account",
  "bugReport.closeA11y": "Close bug report form",
  "bugReport.submitFailed": "Failed to submit bug report. Please try again.",
  "bugReport.pickFileFailed": "Failed to select file. Please try again.",
  "bugReport.pickImageFailed": "Failed to select image. Please try again.",
  "bugReport.fileTypeTitle": "File type not allowed",
  "bugReport.fileTypeAccepted": "Accepted file types: {list}",
  "bugReport.fileTypeRejected": "The selected file type ({type}) is not accepted.",
  "bugReport.fileTooLargeTitle": "File too large",
  "bugReport.fileTooLarge": "Maximum file size is {max}. Your file is {size}.",
  // --- Paywall screen ---
  "paywall.title": "Choose Your Plan",
  "paywall.plansLoadFailed":
    "We could not load the plans. Check your connection and try again.",
  "paywall.tryAgain": "Try again",
  "paywall.pricesUnavailable":
    "Prices are unavailable — the {store} is not offering these subscriptions right now.",
  "paywall.selectorLabel": "Pick your monthly transcription time",
  "paywall.selectorLabelReadOnly": "What each plan gives you",
  "paywall.priceUnavailableA11y": "price unavailable",
  "paywall.pricePerMonthA11y": "{price} per month",
  "paywall.includedHeading": "Included in every plan",
  "paywall.showDetails": "See exactly what is included",
  "paywall.hideDetails": "Hide the details",
  "paywall.ctaChoose": "Choose a plan",
  "paywall.ctaStart": "Start with {plan} — {price}/mo",
  "paywall.restore": "Restore Purchases",
  "paywall.restoreA11y": "Restore purchases",
  "paywall.restored": "Purchases Restored",
  "paywall.restoredBody": "Your previous purchases have been restored.",
  "paywall.nothingToRestore": "Nothing to Restore",
  "paywall.nothingToRestoreBody":
    "We found no previous subscription on this {store} account.",
  "paywall.restoreFailed": "Restore Failed",
  "paywall.restoreFailedBody":
    "Could not restore purchases. Please try again later.",
  "paywall.purchaseSuccess": "Purchase Successful",
  "paywall.purchaseSuccessBody": "Your subscription is now active. Enjoy!",
  "paywall.purchasePending": "Purchase Pending",
  "paywall.purchasePendingBody":
    "Your purchase is awaiting approval. You will be notified when it is complete.",
  "paywall.purchaseFailed": "Purchase Failed",
  "paywall.unexpectedError": "An unexpected error occurred. Please try again.",
  "paywall.renewalTerms":
    "Payment is charged to your {store} account at confirmation of purchase. The subscription renews monthly unless it is cancelled at least 24 hours before the end of the current period, and your account is charged for the renewal within the 24 hours before it.",
  "paywall.terms": "Terms of Use",
  "paywall.privacy": "Privacy Policy",
  "paywall.cancelAnytime": "Cancel anytime in your {store} account.",
  // --- Artifact detail ---
  "artifact.loadFailed": "Unable to load this artifact.",
  "artifact.failedTitle": "Unable to load",
  "artifact.retryA11y": "Retry loading artifact",
  "artifact.notReady": "Not ready yet",
  "artifact.refreshA11y": "Refresh artifact",
  "artifact.anotherLanguage": "another language",
  "artifact.translatedFrom": "Translated from {language}",
  "artifact.translationFailed": "Translation unavailable — shown in {language}",
  "artifact.translationFailedA11y":
    "Translation unavailable. This content is shown in its original language, {language}.",
  "artifact.section.keyPoints": "Key points",
  "artifact.section.takeaway": "Takeaway",
  "artifact.section.context": "Context",
  "artifact.section.mainTopics": "Main topics",
  "artifact.section.quotes": "Notable quotes",
  "artifact.section.conclusion": "Conclusion",
  "artifact.section.objectives": "Objectives",
  "artifact.section.concepts": "Concepts",
  "artifact.section.actionItems": "Action items",
  "artifact.section.glossary": "Glossary",
  "artifact.noFlashcards": "No flashcards in this artifact.",
  "artifact.cardCount.one": "{count} card",
  "artifact.cardCount.other": "{count} cards",
  "artifact.question": "QUESTION",
  "artifact.answer": "ANSWER",
  "artifact.tapToReveal": "Tap to reveal",
  "artifact.revealAnswerA11y": "Tap to reveal the answer",
  "artifact.hideAnswer": "Hide answer",
  "artifact.noQuestions": "No questions in this artifact.",
  "artifact.quizProgress": "Quiz progress",
  "artifact.questionPosition": "Question {index} of {total}",
  "artifact.quizComplete": "Quiz complete",
  "artifact.explanation": "EXPLANATION",
  "artifact.optionA11y": "Option {label}: {text}{state}",
  // --- Share confirmation ---
  "share.title.url": "Save Link",
  "share.title.text": "Save Text",
  "share.title.audio": "Save Audio",
  "share.title.file": "Import File",
  "share.title.photo": "Save Photo",
  "share.processing": "Processing shared content...",
  "share.invalid": "Cannot save this content",
  "share.saved": "Saved!",
  "share.saveFailed": "Save failed",
  "share.saving": "Saving...",
  "share.uploadingAudio": "Uploading audio...",
  "share.uploadingFile": "Uploading file...",
  "share.whatsappText": "WhatsApp text message",
  "share.tags": "Tags",
  "share.chooseCollection": "Choose collection",
  "share.chooseTags": "Choose tags",
  "share.success.duplicate": "This content was already in your inbox.",
  "share.success.audio": "Audio saved. Transcription will begin shortly.",
  "share.success.text": "Text saved to your inbox.",
  "share.success.photo": "Photo imported. Text extraction will begin shortly.",
  "share.success.audioFile":
    "Audio file imported. Transcription will begin shortly.",
  "share.success.file": "File imported. Processing will begin shortly.",
  "share.success.url": "Link added to your inbox. Processing will begin shortly.",
  // --- Local import (file picker, camera, gallery) ---
  "import.filesUnavailable": "Could not open your files",
  "import.filesUnavailableBody":
    "The file browser could not be opened. Please try again.",
  "import.formatNotSupported": "Format not supported",
  "import.cameraUnavailable": "Camera unavailable",
  "import.cameraUnavailableBody":
    "The camera could not be started on this device.",
  "import.cameraPermission": "Camera access needed",
  "import.cameraPermissionAsk":
    "Allow camera access to capture a document or a page you want to import.",
  "import.cameraPermissionSettings":
    "Camera access is turned off. Enable it for this app in your device settings to capture a document.",
  "import.galleryUnavailable": "Gallery unavailable",
  "import.galleryUnavailableBody":
    "Your photo gallery could not be opened. Please try again.",
  "import.photoTooLarge": "Photo too large",
  "import.photoNotSupported": "Photo not supported",
  "upload.reject.extension":
    "Files with the .{extension} extension cannot be imported. Supported formats: {formats}.",
  "upload.reject.noExtension":
    "This file has no recognizable extension. Supported formats: {formats}.",
  "upload.reject.empty": "This file is empty, so there is nothing to import.",
  "upload.reject.tooLarge":
    "This file is {size}, over the {max} limit for a single import.",
  "home.loadFailed": "Unable to load your inbox. Please try again.",
  "share.unsupportedFile": "This file type is not supported yet.",
  "share.signInLinks": "You must be signed in to save links.",
  "share.signInContent": "You must be signed in to save content.",
  "share.signInFiles": "You must be signed in to import files.",
  "transcript.translating": "Translating transcript...",
  "transcript.translationFailed":
    "Translation failed. Showing original transcript.",
  "paywall.subtitle":
    "Every plan does all of it. Only the monthly transcription time changes.",
} as const;
