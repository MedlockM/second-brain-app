---
id: task-238
title: Provision Google Play subscriptions and connect the Android app to RevenueCat
status: To Do
assignee: []
created_date: '2026-08-09 21:05'
updated_date: '2026-08-20 03:11'
labels:
  - phase-6
  - mobile
  - release
  - android
  - revenuecat
  - iap
dependencies:
  - task-163
  - task-262
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.** Verrouillée par
> `dispatchable: false` le 2026-09-02, quand `task-163` est passée `Done` et a cessé de la
> retenir par dépendance. Six ACs sur sept sont closes ; la seule qui reste est la moitié
> *restore* de l'AC#7 — un rachat en license tester puis un **Restore Purchases** sur le
> device physique de l'owner (voir « What is left » en fin de notes). Aucun agent ne peut
> toucher un téléphone ni la Play Console. Ne pas retirer ce verrou pour « avancer » la
> tâche : il n'y a rien à y coder.

Complete the production-like Android billing configuration that is intentionally absent today. The Android application must exist in Google Play Console and RevenueCat, expose the three validated V1 monthly tiers through the current offering, and use a real Google Play public SDK key instead of the Test Store key or the current placeholder. This work involves owner-controlled Google Play Console credentials and billing setup; an agent may automate verifiable RevenueCat/API portions but must not handle or expose private service-account material.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Google Play application for package com.secondbrainlabs.core exists and is eligible for Internal Testing
- [x] #2 A Google Play app is connected in the RevenueCat project and its Google service credentials validate successfully
- [x] #3 The Text-Only, Mix, and Audio-Heavy monthly subscriptions exist in Google Play with the validated V1 prices and active base plans
- [x] #4 All three Google Play products are imported into RevenueCat, attached to their matching tier entitlement from task-262 (tier_text_only, tier_mix, tier_audio_heavy), and mapped to packages text_only, mix and audio_heavy in the current offering
- [x] #5 The real RevenueCat Google public SDK key is configured securely for Android development, preview, CI, and production profiles, while the Test Store key remains restricted to tests
- [x] #6 An Internal Testing build fetches all three packages through Google Play without configuration errors
- [ ] #7 A Google Play license tester completes a sandbox purchase and restore, and RevenueCat Customer Info reports the matching tier entitlement as active
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Progress — 2026-08-20 (owner session, no code involved)

Where the Android/RevenueCat wiring actually stands, and why it stops where it does.

**Done**

- Google Play developer account exists. Its setup is **not finished** — Play Console still shows the "finish setting up your developer account" banner, which gates publishing.
- Google Cloud service account created with the two roles RevenueCat requires (Pub/Sub Editor, Monitoring Viewer), JSON key generated, and the account invited in Play Console under **Users & permissions** with the app-information (read-only), financial-data and orders-and-subscriptions permissions. Its email, its GCP project id and the key id are deliberately not recorded here (public repo) — read them back from the RevenueCat app's Service credentials panel.
- Play Store app created in the RevenueCat project: `appb253c0f75a`, package `com.secondbrainlabs.core`. Service account JSON uploaded.
- Because RevenueCat mints a public SDK key at app creation, the real `goog_` key exists independently of everything below, and it is **set in `mobile/.env`** — the `your_revenucat_google_api_key_here` placeholder is gone, so Android now configures the SDK for real. Local builds only, though — `mobile/.env` is gitignored, so no EAS cloud build saw it until the three EAS environments were fixed on 2026-09-01 (see AC#5 below).

**Blocked, and the ordering this reveals (AC#2)**

RevenueCat authenticates against the credentials without trouble, then fails all three checks with *"the Google Play package name was not found"*. Cause: a package name only exists for the Google Play Developer API once a **signed bundle carrying that applicationId has been uploaded to a test track**. Creating the app in Play Console is not enough — at creation you supply an app *name*, and the package name is fixed by the first AAB.

So AC#2 cannot pass before AC#1, and AC#1 needs the Android build of `task-163`. The real order is: `task-163` → AC#1 → AC#2 → AC#3-4 → AC#5-7. Nothing between them can be done out of sequence.

**Two practical notes for whoever runs AC#1**

- `mobile/eas.json` profile `preview` builds an **APK** (`buildType: "apk"`), which Play Console refuses for a new app — new applications only accept **AAB**. Use `production` (`app-bundle`) or add a dedicated profile.
- The bundle needs to be neither functional nor public. An internal or closed track is enough to make the package name exist, which is all AC#2 is waiting on.

**Deferred until the credentials validate**

Connect **Google developer notifications** (Pub/Sub topic) on the RevenueCat Play Store app, so Android purchase events reach `media_summarizer/api/endpoints/revenucat_webhook.py` in real time rather than by polling. RevenueCat surfaces it on the same app settings page and recommends it strongly.

## Progress — 2026-08-31 (owner session in Play Console, per the `task-260` runbook)

**AC#1 is unblocked on the console side.** The "finish setting up your developer account"
banner that line 47 above describes as gating publishing no longer does: the owner
confirmed physical-Android-device access through the Play Console mobile app and validated
the contact phone number, and the **Create application** button went from greyed out to
active. Three of the seven account eligibility gates are now closed (device, contact
phone, identity). Note that an active button is not a right to publish — see below.

**AC#3 carries a hard blocker that nobody had written down: there is no Google Play
merchant account.** The distinction matters and cost a wrong instruction earlier the same
day. Google has two separate objects:

- the **payments profile** (the *payer* — it settled the $25). It exists, and its identity
  is verified: name and address both validated 2026-06-02, account type *Particulier*.
- the **merchant account** (the *payee* — tax information plus bank details). Opening
  `payments.google.com/gp/w/home/settings` on 2026-08-31 showed **no tax section, no bank
  section, no payout surface at all**. Not "pending" — nonexistent.

No merchant account means no Play subscription product can be created, so **AC#3 cannot
pass**, and consequently neither can AC#4 (nothing to import), AC#6 or AC#7. AC#2 is
unaffected: validating the service credentials only needs the package name to exist.

**Correction, same day, from Google's own documentation.** It was first written here that
the merchant account could only be created after an app exists. That was an inference from
the missing *Payments* menu entry, and it is **wrong**. Play Console Help
(`answer/7161426`, read 2026-08-31) conditions payments-profile creation on **no app at
all** — it is an account-level settings task, reachable at **Play Console → Settings →
Payments profile → Create payments profile**. There is no top-level *Payments* menu entry;
that is why it looked absent.

So the payments work **runs in parallel** with everything below, starting immediately. The
ordering of line 56 becomes two independent tracks that only meet at AC#3:

- **Track A (calendar-bound):** `task-163` → AAB → AC#1 → AC#2
- **Track B (starts now, no dependency):** payments profile → bank details + tax info →
  Google processing delay
- AC#3 needs **both**; then AC#4 → AC#5-7.

Google's docs do not spell out the bank-account and tax-form sub-steps, so their individual
delays are unknown — they surface inside the flow. Two constraints the docs do state: the
profile address may **not** be a PO box, and the **country is locked after submission**,
with the payout bank account having to be registered in that same country.

**A build blocker for AC#1, now resolved.** Extending the note on line 60: no existing EAS
profile could produce the AAB that AC#1 needs. `preview` builds an APK, refused by Play for
a new app. `production` builds an app bundle but sets
`EXPO_PUBLIC_API_BASE_URL=https://api.mediasummarizer.com`, and that hostname **does not
resolve in DNS** (checked 2026-08-31) — the resulting app would be network-dead, and
`extra` values are frozen at build time so it could not be pointed elsewhere afterwards.
An **`internal` build profile** was therefore added to `mobile/eas.json` on 2026-08-31:
`"buildType": "app-bundle"` plus `autoIncrement`, pointing at the **dev** API base URL, with
a matching `submit.internal` profile on `track: "internal"`. The sequence for AC#1/AC#2 is
`eas build -p android --profile internal` then `eas submit -p android --profile internal`.
It will switch to `production` once `task-252` provisions the prod API hostname.

**The Play application was created on 2026-08-31.** Track A has started. The owner filled
the *Créer une application* form and the app now exists in the console. Field-by-field
reversibility was checked against Play Console Help the same day, before submitting:

| Field | Verdict | Source |
|---|---|---|
| App name, default language, app-or-game | editable later | `answer/9859152` — « Vous pourrez modifier ce choix ultérieurement » |
| Free or paid | one-way after publication | `answer/6334373` — « une fois que vous avez défini l'application comme étant sans frais, vous ne pouvez plus la rendre payante » |
| **Package name** | **permanent** | « Les noms de package pour les fichiers d'application sont uniques et permanents… Vous ne pourrez pas les supprimer ni les réutiliser par la suite. » |

**Declared *Sans frais* (free), which is the correct declaration for this app** and worth
recording because it looks counter-intuitive next to a paid subscription. Play's "paid"
flag prices the *download*, not the monetisation: `answer/6334373` lists the two operations
separately (« les utilisateurs peuvent télécharger des applications payantes **et**
effectuer des achats via une application »), and the monetisation policy (`answer/9858738`)
puts « Services sur abonnement » under *achats via les applications*, explicitly alongside
« de nouvelles fonctionnalités non disponibles dans la version gratuite ». RevenueCat is
invisible to Play — it is a layer over Google Play Billing, not a payment channel — so it
has no bearing on this field. Declaring the app paid would have charged for the install on
top of the subscription and produced no in-app purchase for RevenueCat to observe.

**AC#2 diagnosed on evidence, 2026-09-01 — the artifact really is the missing piece.**
Line 54 above inferred that an uploaded bundle was required; RevenueCat's *Debug error*
panel now proves it and rules out everything else. Two of its three checks pass — « Can read
the Google Play in-app product catalog » and « Can read the Google Play subscription catalog
and base plans » — so the credentials authenticate, the Google Cloud APIs are enabled and
the Play Console permissions are sufficient. Only the third fails: « Could not validate
access to Google Play subscription purchases because the Google Play package name was not
found ». That is the *purchases* endpoint, which RevenueCat's own docs gate on an artifact:
« verify that you have uploaded your signed APK or Android App Bundle and have completed all
the steps to approve the release ». Creating the app in the console with an explicit package
name is **not** enough. The 24-to-36-hour credential propagation window is not a factor
either — the credentials date from 2026-08-20.

Practical consequence for whoever finishes AC#1: use the **internal test track and upload
the AAB by hand**. `eas submit` is a dead end today — `mobile/google-services-key.json` is
gitignored and absent locally, and the service account holds no release-to-track permission,
so granting one would restart the 24-36 h propagation for nothing.

**Superseded the same evening (2026-09-01).** `eas submit` is no longer a dead end, and the
propagation argument above was wrong. A dedicated service account
(`eas-play-publisher`, no IAM role) was created, granted the six publishing permissions in
Play Console, and its key uploaded to the EAS servers through `eas credentials` — so no
local file and no `serviceAccountKeyPath` are involved. `eas submit --profile internal`
then pushed `versionCode` 6 to the internal track **minutes after the invitation**, first
try. Whatever the 24-36 h window applies to, it is not the release-to-track permissions.
Full state in `mobile/MOBILE_CI_CD.md`, section *Google Play Service Account Key*.

**The Android release build was broken, and it had nothing to do with Play.** The first two
`internal` builds (2026-08-31 16:21, 2026-09-01 08:08) both died in `RUN_GRADLEW` with
`EAS_BUILD_UNKNOWN_GRADLE_ERROR`, which hides the real message. The log says:
`Execution failed for task ':app:lintVitalRelease' > Lint found fatal errors while
assembling a release target`, then 33 `ExtraTranslation` errors — 11 locales x 3 keys.

Cause: `app.config.ts` declared `locales` as flat files holding the three iOS keys
(`CFBundleDisplayName`, `NSPhotoLibraryUsageDescription`, `NSCameraUsageDescription`), and
Expo copies locale keys into the native resources **verbatim, without renaming**
(`@expo/config-plugins/build/android/Locales.js`). So Android got three strings that mean
nothing to the platform and that are absent from `res/values/strings.xml`; `lintVitalRelease`
is fatal on Release, so no AAB could ever be produced — on any profile, `production`
included. Fixed by splitting each `locales/<lang>.json` into `ios` and `android` sections
(the resolver honours them: `@expo/config-plugins/build/utils/locales.js`), Android's half
being the single `app_name` key, which is what the launcher label actually reads and which
does exist in the default locale. iOS output is byte-for-byte unchanged; the eleven
`values-b+<lang>/` folders are still generated, so the OS still sees a multilingual app.

**First Android app bundle ever produced: 2026-09-01**, profile `internal`, `versionCode` 4,
signed with the EAS-managed keystore `aRG08ty5Ek`, pointing at the dev API. It is the
artifact AC#1 and AC#2 are waiting on. Two things it is *not*: not a release candidate (dev
backend), and not yet uploaded — the upload to the internal test track is an owner step in
the console.

**AC#1 and AC#2 closed on 2026-09-01.** The owner uploaded the bundle to the internal test
track and RevenueCat's Service credentials panel switched to **`Valid credentials`** —
immediately, with none of the 24-to-36-hour wait the docs warn about. That confirms the
diagnosis above end to end: the only thing ever missing was an artifact. Track A is done.

**Now unblocked, and worth doing before the products exist:** the *Google developer
notifications* section on this same RevenueCat page is live and empty (« Choose a topic ID
and click Connect to Google »). This is the deferred item from the 2026-08-20 notes below.
It needs no Play product, so it can be wired now rather than after AC#3.

**Merchant account created 2026-08-31 — Track B has moved.** The blocker described above
("no tax section, no bank section, no payout surface at all") is partly lifted: the owner
created the Google Play merchant account the same day, and the payee screen now exists
(payee `Google Play Apps`, monthly payout, threshold 1,00 €, no transaction yet). The IBAN
was deposited on 2026-08-31; Google will send a **micro-deposit** to that account whose
amount the owner must report back in the console to validate it (documented at ≤3 business
days, under 1 USD converted to EUR). Bank verification is therefore *in progress*, not
absent. Full state and owner steps in the `task-260` runbook, étape 2, section « Compte
marchand créé ».

**The tax section is not a blocker — correction, 2026-09-01.** An earlier line here said
everything left on this task sat behind it. The tax center was opened the next day and it
holds exactly two jurisdiction cards, **Taiwan** and **United States**, both empty and
**neither in an error or blocking state**. Taiwan asks for a Taiwanese VAT number and
concerns developers *established* there (`answer/138000`), so it does not apply; the United
States card is the W-8BEN certificate of foreign status, which `answer/7161649` frames as an
*exemption* from US tax reporting rather than a prerequisite for selling. There is no France
or EU card at all — Google carries the VAT. So the single thing gating AC#3 is the bank
account: the merchant screen's blocking banner is « Validez votre compte … pour pouvoir payer
ou être payé », and nothing else.

**Track B is complete — 2026-09-01. AC#3 is unblocked.** All three volets of the merchant
account are closed: payee identity verified (2026-06-02), **US tax information approved**
(W-8BEN, 0 % on copyright royalties under Article 12 §1 of the France–US treaty as amended by
the 2009 protocol, valid to 2029-12-31), and the **bank account validated and set as
`Principal`** — that last step matters, an account left on `Aucun` receives nothing. Nothing
on the Google Play side now stands between this task and the three subscriptions.

## AC#3, AC#4 and AC#5 closed — 2026-09-01

**The three Play subscriptions exist, each with one activated monthly base plan `monthly`.**
Prices from `docs/research/task-65-pricing-v1-benchmark/README.md` (`owner_decision: ok`).

| Tier | Play subscription ID | Base plan | Price seen in France | RevenueCat store identifier |
|---|---|---|---|---|
| Reader / Text-Only | `text_only_monthly` | `monthly` | 3,00 € TTC | `text_only_monthly:monthly` |
| Mix | `mix_monthly` | `monthly` | 5,00 € TTC | `mix_monthly:monthly` |
| Audio-Heavy | `audio_heavy_monthly` | `monthly` | 9,00 € TTC | `audio_heavy_monthly:monthly` |

**A Play store identifier is `subscriptionId:basePlanId`, not the bare subscription ID.**
RevenueCat's docs only say « you will need to add both the subscription ID and the base plan
ID » without showing the separator, so the products were brought in through the dashboard's
**Import Products** rather than typed by hand — the import produced the `:`-joined form above.
Anything that has to name a Play product must use that full form.

**Regional prices: the bulk field is tax-exclusive, the table column is tax-inclusive.**
Entering 9,00 EUR in the multi-country dialog produced **10,99 €** on the France row: 9 × 1,20
(French VAT) = 10,80 €, then Play's magic price rounded to the local `X,99` pattern. Play's
magic price « ne s'applique que lorsque le système calcule les prix pour le compte des
développeurs », so the fix is a manual entry per row: **the France row was set to 7,50 / 4,17 /
2,50 EUR excl. tax**, which displays exactly 9,00 / 5,00 / 3,00 € incl. tax. Every other
region keeps its auto-converted magic price — deliberately, since nothing is sold outside
France yet and a regional price is editable at any time with no subscriber to protect.

**AC#4, done by API and read back.** Nine calls with `REVENUCAT_API_KEY` as bearer, following
`docs/REVENUECAT_ENTITLEMENTS.md` § "Adding a store product": import (dashboard) then
`attach_products` on the three tier entitlements and the three packages of offering `default`,
all HTTP 200. Verified on the endpoints the AC names — every `entitlements/<id>/products` and
every `packages/<id>/products` now lists three store identifiers, one per store (App Store,
Play Store, Test Store).

**AC#5 closed, and it was hiding a defect that made the Android build billing-dead.** The real
`goog_` key existed only in `mobile/.env` (gitignored); all three EAS environments —
`production`, `preview`, `development` — still held the literal string
`your_revenucat_google_api_key_here`. Since the `internal` build profile resolves the
`production` environment and `EXPO_PUBLIC_*` values are inlined at build time, **the AAB with
`versionCode` 4 that sat on the internal test track carried the placeholder** and could never
have resolved an offering, whatever the state of RevenueCat. Fixed with `eas env:update` on the
three environments; CI is untouched and still injects only the Test Store key
(`mobile-e2e-maestro.yml:140` and `:349`), which is the other half of this AC. Verified in the
artifact, not in the log: the `versionCode` 5 bundle was downloaded, unzipped, and
`base/assets/app.config` carries the real `goog_ssGn…` key with zero occurrences of the
placeholder.

**Why these IDs are NOT the iOS ones — Play caps product IDs at 40 characters.** `answer/140504`
(read 2026-09-01): « cet identifiant doit commencer par une lettre minuscule ou un chiffre et ne
doit pas dépasser **40 caractères** ». The `task-261` identifiers are longer:
`com.secondbrainlabs.core.text_only_monthly` is **42** and
`com.secondbrainlabs.core.audio_heavy_monthly` is **44**; only `…mix_monthly` (36) would fit.
Reusing the iOS IDs on Play is therefore impossible for two of the three tiers, and a
half-matching set would be worse than none. Play needs no reverse-DNS prefix — the package name
already scopes the products — so the bare tier IDs above are used.

This costs nothing architecturally: `task-262` deleted the product-ID map, the backend resolves
the tier from the **entitlement**, and `mobile/app/paywall.tsx` looks products up by **package**
key (`text_only` / `mix` / `audio_heavy`). RevenueCat products are per-app, so the Android rows
simply carry different store identifiers than the iOS rows while pointing at the same
entitlements and packages. Nothing in the code reads a store product identifier.

## AC#6 closed — 2026-09-01

`versionCode` 5 (profile `internal`, dev API, keystore `aRG08ty5Ek`) installed from the internal
test track and the paywall rendered the three tiers with their prices: Reader 3,00 €/mois · 1 h,
Mix 5,00 €/mois · 5 h (« VOTRE FORMULE D'ESSAI » selected), Audio-Heavy 9,00 €/mois · 12 h
(« MEILLEUR PRIX »), an active CTA « Commencer avec Mix — 5,00 €/mois » and the notice
« Résiliez à tout moment dans votre compte Play Store ».

**Those visible prices are the proof, not just a good sign.** `mobile/app/paywall.tsx` derives a
price from `pkg.product.priceString` and nowhere else — no package, no price, and the card
renders without one. Three prices on screen therefore means the Play Billing SDK resolved the
offering, matched all three packages, and read them back from Google Play. The build being an
AAB resigned by Play App Signing, this exercises the real distribution path.

The earlier « Une erreur s'est produite de notre côté » on install is gone. The two candidate
causes were the tester list on **Tests internes → onglet Testeurs** (a different list from
**Paramètres → Test de licence**; being on the second grants free purchases, not the right to
install) and the documented multi-hour propagation delay of a channel's first publication. Which
of the two it was was not isolated, and no longer matters.

The account was reached with **email/password**, not Google: the Android Google sign-in is dead
for an unrelated reason — `expo-auth-session` builds a custom-scheme redirect Google no longer
accepts on Android — tracked in `task-325`. It does not touch billing.

## The full Android subscription lifecycle ran end to end — 2026-09-01

License testing was configured with the list `beta-testeurs`, « Réponse de la licence » left on
`RESPOND_NORMALLY` (that field belongs to Google Play *Licensing*, the anti-piracy check for paid
apps, not to Play Billing — this app is free and links no LVL, so it has no effect either way).
A license tester bought **Audio-Heavy** and the 5-minute renewal clock
(`developer.android.com/google/play/billing/test`) compressed six months of billing into 43
minutes. Every event reached the backend. Read back from `revenucat_events-dev` (eu-west-3):

| Event | `processed_at` |
|---|---|
| `INITIAL_PURCHASE` | 16:54:31 |
| `RENEWAL` | 17:00:57 |
| `RENEWAL` | 17:07:21 |
| `RENEWAL` | 17:13:08 |
| `RENEWAL` | 17:21:02 |
| `RENEWAL` | 17:29:02 |
| `CANCELLATION` | 17:37:00 |
| `EXPIRATION` | 17:37:00 |

Six paid periods then the automatic stop, exactly the documented license-tester behaviour. The
`revenucat_events-dev` table went from 1 item (a `TEST` ping from 2026-08-13) to 9. **This is the
first time the Android billing circuit has ever run, and the first `RENEWAL` the backend has ever
processed on any platform.**

**What each hop proves, since the whole chain was untested until now:**

- **Play → RevenueCat.** `GET /v2/.../customers/<id>/subscriptions` returns
  `subGps71ab95a86198da46a7ff9e60de80dce9`: `store: play_store`, `environment: sandbox`,
  `ownership: purchased`, `product_id: proda57a23a69e` (= `audio_heavy_monthly:monthly`),
  `store_subscription_identifier: GPA.3335-6339-1997-53484..5`, `country: FR`. The Google
  developer-notifications path that `line 65` above deferred is therefore live enough to carry
  renewals — RevenueCat saw all six within seconds.
- **The presented offering was the real one.** `presented_offering_id: ofrng2c876c3f17` — the
  `default` offering, not the Test Store. Combined with AC#6's prices, that closes any doubt
  about which catalogue the binary talked to.
- **The webhook signature check passes in production conditions.** Nine stored events means nine
  requests that got past the `REVENUCAT_WEBHOOK_SECRET` comparison; an unsigned `POST` answers
  `401`. The value in RevenueCat → Integrations → Webhooks does match `.env` and
  `media-summarizer-runtime-dev`, which the v2 API could not tell us (`404`) and which
  `task-261` OWNER GATE 5 still lists as unconfirmed. **It is confirmed now, for the shared
  secret at least** — the Android event flow uses the same webhook endpoint and the same secret
  as iOS will.
- **Entitlement-driven tier resolution works on a Play product.** `subscriptions-dev` carries
  `tier: L`, `platform: android`, `revenucat_product_id: audio_heavy_monthly:monthly`. The only
  way `_resolve_tier()` can produce `L` is `tier_audio_heavy` appearing in the event's
  `entitlement_ids` (`media_summarizer/api/endpoints/revenucat_webhook.py:141-148` maps nothing
  else, and returns `None` otherwise). So `task-262`'s layout held on a second store, and
  `revenucat.tier_unresolved` never fired.
- **Cancellation and expiry are handled distinctly.** The row ends at `status: expired`,
  `auto_renew_status: false`, `cancel_at_period_end: true`, `current_period_end` 17:29:13 —
  `CANCELLATION` flipped the renewal flag while leaving access until the period end, then
  `EXPIRATION` closed it. Access is correctly gone now (`gives_access: false`).

**Two readings to not misinterpret later.** The subscription reports
`total_revenue_in_usd.gross: 62.77` (six periods at ~10.46 USD): sandbox money, no cash moved,
`environment: sandbox` is the field that says so. And
`GET /v2/projects/proj879a771a/subscriptions/<id>/entitlements` returns an **empty list** even
though the tier resolved from `tier_audio_heavy` — the entitlement was certainly in the payload,
so this is a v2 reporting quirk on an expired subscription, not a missing attachment. Don't go
re-attaching products on the strength of that endpoint.

## What is left: the restore half of AC#7

AC#7 asks for « a sandbox purchase **and restore** ». The purchase half is closed well beyond
what the AC asked. The restore was not observed, and it cannot be tested against this
subscription any more — it is expired, so `restorePurchases()` would legitimately return no
entitlement. It needs an active one: buy any tier again as the license tester (free, and the
first renewal lands 5 minutes later), then force-stop the app or clear its data, sign back in and
hit **Restore Purchases**. What must come back is the tier entitlement active, and no new
`INITIAL_PURCHASE` in `revenucat_events-dev` — a restore syncs, it does not re-buy.

That is worth the two minutes: it is the reinstall path every real user hits, and it is the one
place where a purchase can exist in Play while the app shows nothing.

One trap documented on the same Google page, for that run: « a purchase is refunded after
3 minutes if your app does not acknowledge the purchase ». So an entitlement that appears then
vanishes is an acknowledgement problem, not a webhook one. Enabling real payment methods
« loses all other license tester features » — leave them off.

Internal app sharing is **not** a shortcut worth taking, and it is moot now that the internal
track installs: it signs with a generated test certificate (« Tous les APK sont signés avec ce
certificat de test »), so the fingerprint differs from the Play App Signing one that the future
Credential Manager sign-in (`task-325`) will have Play services verify.
<!-- SECTION:NOTES:END -->
