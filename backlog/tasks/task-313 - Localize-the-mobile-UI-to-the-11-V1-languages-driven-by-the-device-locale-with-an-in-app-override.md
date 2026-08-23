---
id: task-313
title: >-
  Localize the mobile UI to the 11 V1 languages, driven by the device locale
  with an in-app override
status: Done
assignee: []
created_date: '2026-08-21 03:48'
updated_date: '2026-08-23 12:00'
labels:
  - mobile
  - i18n
  - feature
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Measured on `main` at `a2dafa5` on 2026-08-21.

The app has **no i18n layer at all**. Every user-facing string is an English literal
inlined in a component: 332 `<Text>` elements, 103 `accessibilityLabel`s and 18
`Alert.alert` calls across 20 screens (`mobile/app/`) and 12 components
(`mobile/src/components/`), plus the copy modules under `mobile/src/lib/`
(`planCopy.ts`, `quotaError.ts`, `artifactRefusal.ts`, `getFriendlyErrorMessage.ts`,
`relativeTime.ts`, `subscriptionDisplay.ts`, `mediaTypeDisplay.ts`). Around 400
distinct strings. A few French leftovers survived `task-2` — e.g. `"Ajouter un tag"`
in `mobile/app/media/tags.tsx`.

`mobile/app.config.ts` declares no `locales` field, so the app is mono-locale at the
native level too: the app name and the two permission prompts
(`NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`) are English-only in
every install.

## How the OS picks the language — the mechanism to implement

Neither store imposes a language. App Store / Play **listing** localizations (title,
description, screenshots) are a separate owner-side artifact and have no effect on
the language *inside* the app. In the app, the OS chooses at launch: it intersects
the locales the binary **declares** (`CFBundleLocalizations` on iOS,
`res/values-<lang>/` on Android) with the user's ordered preferred-language list,
and falls back to the development language when nothing matches. "The app opens in
the user's language" is therefore a consequence of declaring the locales and
shipping the catalogues — nothing is requested from a store.

Both OSes also expose a per-app language override (iOS 13+, Android 13+ via
`localeConfig`), and apps add an in-app selector on top because the native one is
not discoverable.

## Two axes, deliberately separate

`reading_language` (task-189/190, `V1_READING_LANGUAGES` in
`mobile/src/services/userPreferencesService.ts`) drives the language of the
**generated content** — summaries, transcript translation, digests. It is
server-side and stays exactly as it is.

The **interface** language is a second, independent axis: it defaults to the device
locale, is overridable in Settings, and is stored on the device only — the backend
never needs to know it. A French speaker who wants English summaries must be able to
have both.

## Scope

**Locale set.** The same 11 as `V1_READING_LANGUAGES`: en, fr, es, de, it, pt, nl,
ja, zh, ar, hi. `en` is the fallback. `ar` means RTL.

**Foundation.** Add `expo-localization` plus a translation runtime. One catalogue
per locale under `mobile/src/i18n/`, `en` being the reference. Key type-safety
matters: a key missing from a catalogue must be a `tsc` error, not a runtime
`"screen.title"` on screen.

**Delete `mobile/src/lib/getDeviceLanguageCode.ts`.** It hand-rolls locale detection
through `NativeModules.SettingsManager` / `I18nManager` with an `Intl` fallback —
exactly what `expo-localization`'s `getLocales()` returns properly (ordered list,
region, RTL flag). Its one caller (`mobile/app/onboarding/language.tsx`) switches to
the new resolver. No compatibility shim: nothing is deployed.

**Extraction.** Every user-facing literal moves to the catalogues, including
`accessibilityLabel` / `accessibilityHint` (screen-reader text is UI text) and the
`Alert.alert` titles and bodies. Plurals go through the runtime's plural rules, not
concatenation — `${count} items` (`inbox.tsx:348`) and `${daysLeft} days`
(`FreeTrialNotice.tsx:61`) are the known cases, and Arabic has six plural categories.

**Locale-aware formatting.** Two date helpers hardcode `"en-US"`:
`mobile/app/(tabs)/search.tsx:129` and `mobile/app/media/[id].tsx:602`.
`relativeTime.ts:22`, `subscriptionDisplay.ts:47` and the `Intl.NumberFormat` in
`planCopy.ts:75` pass `undefined`, which resolves to the **system** locale — wrong
once an in-app override exists. All five take the active UI locale explicitly. The
time-of-day greeting in `inbox.tsx:552-556` becomes three keys, not a computed
English word.

**RTL.** `ar` requires `I18nManager`. RTL takes effect after a reload, so switching
to or from Arabic in the selector needs an explicit restart prompt. Screens use
physical `left`/`right` layout properties in places; they need auditing for the
logical equivalents (`marginStart`/`paddingEnd`/…) so the mirroring is real rather
than half-applied.

**Native strings.** Declare the 11 locales in `app.config.ts` through the `locales`
field, so the app name and the two `infoPlist` permission strings are localized and
`CFBundleLocalizations` actually lists them. Without this the OS treats the app as
English-only whatever the JS bundle contains.

**Reading-language labels.** `V1_READING_LANGUAGES` currently mixes
ASCII-stripped endonyms (`"Francais"`, `"Espanol"`, `"Portugues"`) with English
exonyms (`"Japanese"`, `"Chinese"`, `"Arabic"`, `"Hindi"`). A language picker names
languages in their own script: `Français`, `Español`, `Português`, `日本語`, `中文`,
`العربية`, `हिन्दी`.

**Backend — quota refusals are the one English string the client cannot translate.**
`quota_enforcer.py:402-418` builds the refusal sentence server-side with the figures
baked in ("This import needs 12 minutes and you have 3 left until Sep 4"), the API
returns it as `detail` (`media.py:756`, `artifacts.py:244`), and the client relays it
verbatim (`quotaError.ts`, `artifactRefusal.ts`). Replace the prose with typed
figures: `QuotaCheckResult` carries a `params` dict (`minutes_needed`,
`minutes_remaining`, `max_minutes_per_item`, `period_end` as ISO), the endpoints
serialize it into the error body alongside the existing `X-Quota-Error-Code` header,
and the client builds the sentence from its catalogue. `_out_of_minutes_message`,
`_item_too_long_message` and `_NO_PLAN_MESSAGE` are then deleted, not kept as a
fallback.

Everything else the API returns and the app displays is either user content (titles,
transcripts, artifacts — already governed by `reading_language`) or a typed code the
client already words itself (`getFriendlyErrorMessage.ts`).

## Not in scope

The `reading_language` pipeline itself. Store listing localizations (owner note
below). Adding locales beyond the 11.

## Owner notes (not acceptance criteria)

1. **Store listings are yours to fill.** App Store Connect and Play Console take one
   localized listing per language, independently of the binary. Shipping 11 in-app
   locales with an English-only listing is coherent but leaves reach on the table.
2. **Maestro asserts English text** (`"Welcome back"`, `"Inbox"`, `"Good .*"`). The
   flows keep passing as long as the simulator/emulator locale stays English and `en`
   is the fallback. Setting a CI device to another locale will break them — expected,
   not a regression.
3. **Translation quality.** The catalogues will be machine-produced. Have a native
   speaker skim at least fr/es/de before store submission; the paywall and the
   refusal sentences are where a bad translation costs money.
4. **After the deploy on `main`**, drive a refusal on dev (submit past the minute
   allowance) and confirm the app shows the rebuilt sentence with the right figures —
   that path changed shape on both sides.
5. **Visual check on device** for `ar`: RTL mirroring is the part a grep cannot
   validate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 mobile/src/i18n/ holds one catalogue per locale for the 11 V1 languages (en, fr, es, de, it, pt, nl, ja, zh, ar, hi) with en as the fallback, and a key missing from a non-en catalogue is a tsc --noEmit error rather than a runtime miss
- [x] #2 No user-facing string literal remains in mobile/app/ or mobile/src/components/: every <Text> body, placeholder, accessibilityLabel, accessibilityHint and Alert.alert argument resolves through the i18n runtime
- [x] #3 mobile/src/lib/getDeviceLanguageCode.ts is deleted and grep -rn "getDeviceLanguageCode" mobile/src mobile/app returns zero results; the UI locale is resolved from expo-localization getLocales() intersected with the 11 supported locales, falling back to en
- [x] #4 A Settings screen lets the user override the UI locale independently of reading_language, the choice is persisted on the device across restarts, and the backend is never told about it
- [x] #5 grep -rn '"en-US"' mobile/app mobile/src returns zero results, and every toLocaleDateString / Intl.NumberFormat call site is passed the active UI locale instead of undefined or a hardcoded tag
- [x] #6 No user-facing plural is built by concatenating a count with a fixed suffix: mobile/app/(tabs)/inbox.tsx and mobile/src/components/FreeTrialNotice.tsx both go through plural-aware catalogue keys
- [x] #7 RTL is enabled through I18nManager when the active locale is ar, switching to or from ar prompts for the restart I18nManager requires, and the screens under mobile/app/ use logical layout properties (marginStart/marginEnd/paddingStart/paddingEnd) wherever a physical left/right property drove the reading direction
- [x] #8 mobile/app.config.ts declares the 11 locales through the locales field, and the app name plus NSCameraUsageDescription and NSPhotoLibraryUsageDescription are supplied per locale
- [x] #9 V1_READING_LANGUAGES labels are endonyms in their own script with correct diacritics (Francais -> Francais with cedilla, Espanol with tilde, Portugues with circumflex, and the CJK/Arabic/Devanagari names replacing the English exonyms); no ASCII-stripped or English-named entry remains
- [x] #10 grep -n "_out_of_minutes_message\|_item_too_long_message\|_NO_PLAN_MESSAGE" media_summarizer/core/services/quota_enforcer.py returns zero results; QuotaCheckResult carries the typed figures instead, the refusal endpoints in media.py and artifacts.py serialize them into the error body, and mobile builds the refusal sentence from its catalogue
- [x] #11 The en catalogue contains no non-English string: the task-2 leftovers such as "Ajouter un tag" in mobile/app/media/tags.tsx are keyed and worded in English
- [x] #12 npm run typecheck and npm run lint are clean in mobile/, and make lint is clean on media_summarizer/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Le runtime

Quatre fichiers sous `mobile/src/i18n/`, plus onze catalogues :

- **`locales.ts`** — les 11 locales, `LOCALE_ENDONYMS` (chaque langue dans sa propre écriture) et `RTL_LOCALES`. N'importe rien, donc importable de partout sans cycle.
- **`runtime.ts`** — `t`, `tCount`, `formatDate`, `formatNumber`, et les types. La locale active est tenue **hors de React**, dans une variable de module. C'est ce qui permet aux modules de copy de `src/lib/` (`planCopy`, `quotaError`, `artifactRefusal`, `getFriendlyErrorMessage`, `relativeTime`, `subscriptionDisplay`) de traduire sans devenir des composants : ce sont des fonctions pures appelées depuis des rendus, des handlers et des callbacks d'`Alert` indifféremment, et leur faire passer un `t` aurait mis une préoccupation React dans du code qui n'a aucune autre raison de connaître React.
- **`index.tsx`** — `I18nProvider`, `useTranslation`, `resolveDeviceLocale`, et la persistance de l'override.
- **`catalogs.ts`** — les onze catalogues groupés.

**Aucune bibliothèque i18n n'a été ajoutée.** `i18next` + `react-i18next` pèse ~40 kB pour un besoin qui tient en trois fonctions : interpolation `{name}`, choix de catégorie via `Intl.PluralRules`, lookup avec repli sur `en`. La seule dépendance nouvelle est `expo-localization@~55.0.18`, que l'AC #3 impose et qu'on ne peut pas écrire soi-même (elle lit la liste ordonnée de préférences de l'OS).

### La type-safety des clés (AC #1)

`TranslationKey = keyof typeof en` et `Catalog = Record<TranslationKey, string> & Record<string, string>`. La moitié `Record<TranslationKey, string>` rend toute clé manquante fatale ; l'index signature laisse une langue ajouter les catégories de pluriel qui lui sont propres. **Vérifié en retirant `common.ok` de `fr.ts`** :

```
src/i18n/fr.ts(11,14): error TS2322: ... Property '"common.ok"' is missing in type ... but required in type 'Record<"common.ok" | ... 529 more ..., string>'
```

### Les pluriels

`tCount(base, count)` demande la catégorie à `Intl.PluralRules(activeLocale)` et lit `<base>.<catégorie>`, avec repli sur `<base>.other`. Les bases sont dérivées du type : `PluralKey` extrait tout `X` tel que `X.other` existe dans `en`, donc on ne peut pas passer à `tCount` une clé qui n'est pas une famille de pluriel. **L'arabe déclare ses six catégories** (`zero`, `one`, `two`, `few`, `many`, `other`) sur les 17 familles — d'où ses 608 clés contre 540 ailleurs. Japonais et chinois n'ont que `other` ; leur `.one` porte le même texte parce que le type l'exige, et n'est jamais lu.

## Les deux axes de langue

Ils restent séparés, comme la description l'exigeait :

| | Langue de lecture | Langue d'interface |
|---|---|---|
| Ce qu'elle décide | résumés, transcriptions traduites, digests | le texte de l'app |
| Où elle vit | compte, `PATCH /api/auth/me` | **appareil uniquement**, `SecureStore` clé `ui_locale` |
| Écran | `settings/reading-language` | `settings/interface-language` (nouveau) |

Le nouvel écran a pris la place d'une entrée « Settings » morte du menu Compte (`onPress={() => {}}`, elle ne naviguait nulle part). Sa première ligne, « Match my device », rend l'état par défaut visible et nomme la langue vers laquelle il résout.

**`V1_READING_LANGUAGES` lit désormais ses libellés dans `LOCALE_ENDONYMS`** plutôt que de les retaper : les deux listes couvrent les mêmes onze langues, et une seconde orthographe de « Português » n'aurait pu que diverger. Ça règle aussi le mélange que l'AC #9 visait (endonymes dépouillés de leurs accents à côté d'exonymes anglais).

## Ce que le backend n'envoie plus

`QuotaCheckResult.message` est remplacé par `params: Dict[str, Any]`, et `error_body()` sérialise `{error_code, **params}` à plat — même forme que les refus typés que `artifacts.py` envoyait déjà (`source_count`, `max_sources`), que l'app lit directement sur `HttpError.details`. Cinq sites de refus basculent (`media.py` ×4, `artifacts.py`, `podcasts.py`, `media_submission.py`).

Les paramètres :

| Code | Clés |
|---|---|
| `out_of_minutes` (sans plan) | `has_plan: false` |
| `out_of_minutes` (quota épuisé) | `has_plan: true`, `minutes_needed`, `minutes_remaining`, `period_end` (ISO 8601, **absent** si inconnu) |
| `item_too_long` | `minutes_needed`, `max_minutes_per_item` |

`period_end` est absent plutôt que `null` : l'app a une phrase plus courte pour ce cas, et c'est elle — pas le serveur — qui sait dans quel calendrier et quelle langue écrire une date. Côté mobile, `getQuotaErrorMessage` reconstruit les six variantes depuis son catalogue, avec une forme dégradée pour chaque chiffre absent.

### Le chemin worker, et ce qu'il perd

`audio_quota_gate` tourne dans un worker, longtemps après la requête, et écrit dans `ProcessingJob.error_message` — une colonne libre que l'app affiche telle quelle. Comme les trois fonctions de prose sont supprimées, `failure_message` retourne désormais **une phrase fixe sans chiffres** (`"This import could not be processed."`, qui était déjà son repli). C'est une perte réelle : l'écran de détail d'un média refusé sur quota ne cite plus les minutes en cause. Le chemin synchrone, lui, est complet. Rendre ce chemin traduisible demanderait de faire voyager le code d'erreur sur la ligne de job et de le mapper côté client — hors du périmètre de cette tâche, et un champ qui contiendrait tantôt un code tantôt une phrase serait ambigu pour les autres producteurs d'erreurs du pipeline.

## Deux points où la description était en avance sur le code

Mesurée sur `a2dafa5`, elle citait deux cas de pluriel par concaténation :

- **`inbox.tsx:552-556`, le salut selon l'heure** — supprimé depuis par task-307 ; le fichier porte encore le commentaire « previously carried by the greeting header that used to sit here ». Rien à extraire.
- **`inbox.tsx:348`, `${count} items`** — déplacé dans `HomeTile` par la même tâche. C'est là qu'il est passé sous `tCount("common.itemCount")`.

L'AC #6 est satisfaite via ces deux fichiers (`inbox.tsx` l'appelle pour le compteur du digest, `FreeTrialNotice` pour son décompte de jours).

## Ce qui n'est délibérément pas traduit

- **Les noms de plans** (`Reader`, `Mix`, `Audio-Heavy` dans `subscriptionDisplay.ts`) : ce sont les noms produits que portent la config de pricing, les deux fiches de store et `GET /api/pricing`. Un plan acheté sous le nom « Reader » doit s'appeler Reader dans toutes les langues.
- **Les noms de plateformes** (`YouTube`, `Spotify`, `WhatsApp`, `TikTok`…) et le nom de l'app.
- **Le testID `artifact-tile-generate-*`**, qui portait le libellé et l'aurait suivi d'une langue à l'autre : il est désormais construit sur le `type` de l'artefact. Aucun flow Maestro ne le référençait.

## Les tables évaluées à l'import

Quatre constantes de module portaient des libellés résolus, ce qui aurait figé la langue de lancement : `ARTIFACT_TILES`, `ScreenTab`, `ERASED_ITEMS` (delete-account), `TOP_BAR_TITLES` (share-confirmation), plus les tables de `getFriendlyErrorMessage`. Toutes portent maintenant une `TranslationKey` résolue au rendu.

## Chaînes natives

`mobile/locales/<code>.json` × 11, déclarés via le champ `locales` d'`app.config.ts`, plus le plugin `expo-localization`. **Vérifié sur la config résolue** (`npx expo config --type public --json`) : `locales` liste bien les onze codes, le plugin est présent, et `ios.infoPlist` porte les deux clés d'usage. Sans ce champ, l'OS considère le binaire comme anglophone quel que soit le contenu du bundle JS, et iOS n'offre même pas le réglage de langue par app.

## RTL

`I18nManager.allowRTL` / `forceRTL` sont appelés par `setLocale`, qui retourne s'il faut redémarrer et déclenche alors une alerte le demandant explicitement (l'app n'embarque pas `expo-updates`, donc aucun rechargement programmatique n'est possible). L'audit des propriétés physiques a converti **11 fichiers** : `marginLeft/Right` → `marginStart/End`, `paddingLeft/Right` → `paddingStart/End`. Les `left`/`right` du positionnement absolu sont laissés : ils vont par paires symétriques (`left: md, right: md`) et ne portent aucune direction de lecture. Un seul cas résiste, le prix des cartes de tarif : `textAlign` n'a pas de valeur logique en React Native, donc le côté est lu sur `I18nManager.isRTL`.

## Vérifications

- `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport (`digest.tsx` `CARD_WIDTH`, `purchaseService.ts` `any`).
- `make lint` : `ruff` clean, `mypy` — 173 fichiers, aucun problème.
- **Onze catalogues complets**, comparés clé à clé au catalogue de référence : 540 partout, 608 pour `ar` (ses catégories de pluriel supplémentaires), zéro clé manquante, zéro clé en trop.
- **Zéro littéral visible restant** : un scan de `app/**` et `src/**` sur les corps de `<Text>`, `accessibilityLabel`, `accessibilityHint`, `placeholder`, les arguments d'`Alert.alert` et les `fallback:` retourne 0.
- `grep '"en-US"'`, `grep getDeviceLanguageCode`, `grep '_out_of_minutes_message\|_item_too_long_message\|_NO_PLAN_MESSAGE'` : zéro occurrence.
- Aucun `toLocaleDateString(undefined)` ni `Intl.*Format(undefined)` ne subsiste.

## Non vérifiable depuis le worktree

- **Le rendu RTL en arabe** — miroir de la mise en page, alerte de redémarrage. C'est la note owner n° 5.
- **Le refus de quota bout en bout** après déploiement : le chemin a changé de forme des deux côtés (note owner n° 4).
- **La qualité des traductions.** Les onze catalogues sont produits à la machine ; la note owner n° 3 demande une relecture native au moins sur fr/es/de avant soumission. Le paywall et les phrases de refus sont les endroits où une mauvaise traduction coûte de l'argent.
<!-- SECTION:NOTES:END -->
