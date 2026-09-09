---
id: task-381
title: >-
  Marquer un média en échec sur ses vignettes et permettre de demander la prise
  en charge de sa source
status: To Do
assignee: []
created_date: '2026-09-08 16:23'
updated_date: '2026-09-08 17:42'
labels:
  - mobile
  - backend
  - ux
  - i18n
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

Quand une ingestion échoue, rien ne le dit dans les listes. `mobile/src/components/MediaListCard.tsx` n'affiche aucun état de traitement — son seul badge est un badge de *type* (`getMediaTypeBgColor`), et le seul échec qu'il gère est celui du chargement de la couverture (`failedCoverId`). `mobile/src/components/HomeTile.tsx` n'en affiche pas davantage. Le champ `MediaListItem.status`, que `GET /api/media` sert déjà (`pending | processing | ready | failed`, via `MediaSearchItem.status`), **n'est lu nulle part dans l'UI** — vérifié par grep sur `mobile/app/` et `mobile/src/`.

Et sur l'écran de détail, la branche `pollingState === "failed"` (`mobile/app/media/[id].tsx` l. 144-171) rend un pictogramme, `media.failedTitle`, la phrase produite par `getFriendlyErrorMessage`, et « Rafraîchir ». Elle n'offre aucun moyen de dire « j'aimerais que cette source marche ».

## Le canal d'envoi existe déjà, et il est cross-platform

Deux vérifications du 2026-09-08, dans cet ordre.

**Les canaux des stores sont en lecture seule.** L'API App Store Connect n'expose sur les feedbacks beta que **7 opérations, toutes en `GET` ou `DELETE`** — aucun `POST`, donc aucune app ne peut créer un feedback TestFlight. Le groupe `beta-testeurs` est de plus interne (`isInternalGroup: true`, `publicLinkEnabled: null`), donc il n'existe même pas de lien public `testflight.apple.com/join/…`. Google Play n'expose aucune écriture de retour testeur. Ces faits sont consignés dans `mobile/MOBILE_CI_CD.md`.

**Mais l'app a son propre canal, et il est déjà branché de bout en bout.** `POST /api/bug-reports`, monté dans `media_summarizer/api/main.py:162`, authentifié, limité à 5 rapports/h/user, persisté dans `bug_reports-dev` (hash `id`, GSI `user-index` et `status-index`, TTL actif) — la table contient déjà 2 lignes. Côté mobile, `mobile/src/services/bugReportService.ts` et `mobile/app/bug-report.tsx` existent, l'écran est atteignable depuis l'onglet Compte (`account.tsx:115`), et le client envoie déjà `source_platform: Platform.OS` et `source_app_version`.

Conséquence : **le bouton se comporte à l'identique sur iOS et sur Android**, TestFlight ne figure nulle part dans cette tâche, et rien ne repose sur une capture d'écran ni sur un OCR.

## Ce qu'on veut

**1. Un marqueur d'échec sur les vignettes** — `MediaListCard` (onglet Bibliothèque et résultats de recherche) et `HomeTile` (rangée « Récemment ajouté » de l'Accueil).

**2. Sous le message d'erreur de l'écran de détail, sur les deux plateformes**, un bloc de cette forme :

> Cette source de média n'est pas encore prise en charge.
> Si vous souhaitez qu'elle le soit à l'avenir :
>
> [ Demander cette source ]

Un tap poste le rapport et le bouton passe en confirmation. Aucun formulaire, aucun champ à remplir.

## Le bloc n'apparaît que là où sa phrase est vraie

`MediaFailureCode` (`media_summarizer/core/models/failure_codes.py`) compte 24 membres rangés en 5 familles. « Cette source n'est pas encore prise en charge » n'est vrai que pour 8 d'entre eux.

**Le bloc apparaît** : `LIVE_CONTENT_UNSUPPORTED`, `IMAGE_POST_UNSUPPORTED`, `NOT_AN_ARTICLE_PAGE`, `ARTICLE_TEXT_NOT_FOUND`, `DOCUMENT_PARSE_FAILED`, `NO_TRANSCRIBABLE_MEDIA`, `NO_TRANSCRIPT_AVAILABLE`, `POST_TEXT_EMPTY`.

**Le bloc n'apparaît pas** pour les 16 autres, et la raison compte :
- `MEDIA_UNAVAILABLE`, `GEO_RESTRICTED`, `AGE_RESTRICTED` → la source *est* prise en charge, c'est l'item qui est hors d'atteinte.
- `OUT_OF_MINUTES`, `ITEM_TOO_LONG` → le quota du testeur ou la limite de son plan : il n'y a rien à « prendre en charge ».
- `PROVIDER_*` (7 codes), `INVALID_JOB_MESSAGE`, `SUBMISSION_FAILED`, `UNEXPECTED_ERROR` → panne passagère, notre budget ou notre code : un réessai peut suffire.

Sans ce filtre, trois retours sur quatre seraient des demandes de prise en charge de sources déjà supportées, induites par une phrase fausse.

## Le backend résout l'URL lui-même, par un point-lookup

C'est le cœur de la tâche côté serveur. Le POST est authentifié, donc le serveur détient `current_user.id` ; avec le `media_item_id` dans le corps, il détient **les deux clés** de `user_media` (`user_id` en hash, `media_item_id` en range). La résolution est donc un `GetItem` via `get_media_for_user(media_item_id, current_user.id)` (`media_summarizer/api/dependencies/media_access.py:31`). **Aucun `Scan`, aucune URL affichée au testeur, aucune référence à recopier.**

Ce que le rapport porte en plus de ce qu'il porte déjà : `media_item_id`, l'`error_code` tel que le client l'a vu, et — quand la résolution aboutit — `source_url`, `media_key` et `media_type` lus sur la ligne.

**La résolution est best-effort.** `get_media_for_user` lève un 404 quand l'item est inconnu, étranger ou soft-deleted. Il ne faut **pas** perdre le rapport pour autant : il se crée quand même, avec le `media_item_id` brut enregistré et sans URL. La valeur du retour ne dépend pas de la réussite du lookup.

`error_code` est capturé dans le rapport au moment de l'envoi plutôt que relu plus tard : `processing_jobs` porte un TTL `expire_at`, et la ligne du job peut avoir disparu quand l'owner lit le rapport.

Une limite à connaître, pas à corriger : **un document téléversé n'a pas de `source_url`** — l'attribut est absent de la ligne, pas vide (vérifié par scan sur `media_type = document` dans `user_media-dev`). Sur `DOCUMENT_PARSE_FAILED` le rapport ne portera donc aucune URL, par construction ; il portera `media_key`, `media_type` et `last_job_id`, ce qui dit quel format a échoué — l'information utile.

## Ce que le bouton ne fait pas

- **Il n'ouvre pas `mobile/app/bug-report.tsx`.** Pas de formulaire, pas de sujet à taper, pas de pièce jointe : un tap, un POST, une confirmation. Le sujet et la description sont construits sur l'appareil depuis les catalogues i18n.
- **Il ne mémorise pas qu'une source a déjà été demandée.** L'état « envoyé » vit dans le composant et disparaît au démontage de l'écran ; un testeur peut re-poster en y revenant. C'est acceptable — la limite de 5/h borne le volume, et l'owner dédoublonne par `media_item_id`. **Ne pas scoper de persistance côté client ni de garde d'unicité côté serveur.**
- **Il ne déclenche aucune notification.** Le webhook Discord de `route_to_triage` n'est pas configuré (`BUG_REPORT_ROUTING_WEBHOOK` est absent de `runtime_env.tf`), donc le rapport atterrit en silence dans DynamoDB. Traité par task-382, dont cette tâche **ne dépend pas** : le bouton a sa valeur dès que les rapports sont écrits.

## Ce que l'implémenteur n'a pas à chercher

- `mediaData.processing_job.error_code` est **déjà accessible** depuis la branche d'échec : le hook expose `mediaData`, et `setMediaData(response)` (`useMediaDetailPolling.ts:104`) s'exécute avant le branchement sur le statut (`:109`). Le champ est déjà typé `error_code?: MediaFailureCode` (`mobile/src/types/media.ts:185`). **Ne pas modifier `useMediaDetailPolling.ts`.**
- Le `media_item_id` est déjà sous la main : `useLocalSearchParams<{ id: string }>()` en tête de `mobile/app/media/[id].tsx`.
- `mobile/app/media/[id].tsx` est une suite d'early returns, et le bouton a besoin d'un état (repos / envoi / envoyé / erreur) : **le bloc est donc un composant à lui, qui porte son propre `useState`.** Aucun appel de hook n'est ajouté dans `[id].tsx`.
- `getFriendlyErrorMessage` traite déjà le `429` (`getFriendlyErrorMessage.ts:232`) : un testeur qui dépasse 5 rapports/h reçoit une phrase lisible sans code nouveau.
- `apiRequest<T>(path, { method, body })` (`apiClient.ts:70`) porte déjà l'authentification ; `BugReportService.createBugReport` existe et n'a qu'à gagner des champs.
- `Colors.errorContainer` est déjà rendu par `getMediaTypeBgColor` pour `youtube_video` et `short_video` (`MediaListCard.tsx:343`). Un marqueur de la même teinte à côté d'un badge de type rouge est illisible : utiliser `Colors.error` / `Colors.onError` (`theme.ts:51-52`).
- `MediaCardItem` reçoit un `status` **optionnel** : la liste bibliothèque passe déjà `item={item}` avec un `MediaListItem` complet, donc aucun appelant de `search.tsx` ne change, et `hitToRow` (l. 356-375) ne pose pas le champ — un hit Algolia n'a pas de statut par contrat, donc pas de marqueur.
- `HomeTileItem` est une union `media | folder` : seul le variant `media` gagne le champ, en optionnel, renseigné par `buildRecentlyAdded` (`inbox.tsx` l. 605-621). Le producteur de « Continuer l'apprentissage » ne porte aucun statut par contrat et ne le renseigne pas.
- Les nouveaux champs de `BugReport` sont optionnels **parce qu'un rapport générique venu de l'onglet Compte n'a aucun média**, pas pour ménager une transition. `attachment_key` donne le motif exact à suivre dans `to_dynamodb_item`.
- Le limiteur de débit de `bug_reports.py` est un `dict` en mémoire de processus (`_rate_limit_store`), donc poreux sur Lambda où chaque conteneur a le sien. C'est une dette assumée existante et documentée : **ne pas la corriger ici.**

## Hors périmètre

- **`mobile/app/bug-report.tsx`** : l'écran de formulaire reste inchangé. Seul `bugReportService.ts` gagne des champs optionnels dans son payload.
- **L'alerte sur nouveau rapport**, et la correction de `docs/community/bug-reports.md` qui affirme à tort un routage Discord temps réel : c'est task-382.
- **La page d'échec du pager de `mobile/app/(tabs)/digest.tsx`** (l. 463-484) : même hook, autre surface, pas de bouton retry. Elle reste inchangée.
- **Le rafraîchissement de la liste.** `search.tsx` recharge sur focus (`useFocusEffect`) et au pull-to-refresh ; un média qui échoue pendant qu'on regarde la liste ne bascule pas tout seul. Ne pas ajouter de polling à la liste.
- **`mobile/app/media/unsorted-review.tsx`** et **`mobile/app/media/folders/[id].tsx`** : ni l'un ni l'autre n'utilise `MediaListCard`.

## Notes à l'owner (pas des ACs)

1. **Le POST ne répondra qu'après déploiement.** L'image Lambda se redéploie au push sur `main` ; l'implémenteur ne peut donc pas valider l'aller-retour. À faire ensuite : provoquer un échec sur un des 8 codes — le plus simple est de partager un post Instagram photo, qui donne `IMAGE_POST_UNSUPPORTED` — toucher le bouton, puis lire la ligne écrite. Attention, `AWS_REGION` vaut `us-east-1` dans le shell alors que les tables sont en `eu-west-3`, donc `--region` est obligatoire :
   ```
   aws dynamodb scan --region eu-west-3 --table-name bug_reports-dev \
     --filter-expression 'attribute_exists(media_item_id)' --output json
   ```
   Le `source_url` attendu sur cet exemple est l'URL Instagram partagée.
2. **Vérification visuelle sur les deux plateformes** : marqueur dans la Bibliothèque et sur l'Accueil, bloc et bouton sous le message d'erreur, état de confirmation après le tap.
3. **`error_code` n'apparaît volontairement pas à l'écran.** Il voyage dans le corps du POST. Ne pas « rendre service » en l'affichant au testeur.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une ligne de `MediaListCard` dont le statut de bibliothèque vaut `failed` porte un marqueur d'échec dans la rangée `styles.cardMeta`, à côté du badge de type, rendu depuis un champ `status` optionnel ajouté à `MediaCardItem` — sans modifier un seul appelant dans `mobile/app/(tabs)/search.tsx`. Sa teinte n'est pas `Colors.errorContainer`, que `getMediaTypeBgColor` rend déjà pour `youtube_video` et `short_video`.
- [ ] #2 Une ligne `pending`, `processing`, `ready` ou sans statut — un hit de recherche, dont `hitToRow` (`search.tsx` l. 356-375) ne pose pas le champ — rend une vignette inchangée, et `MediaListItem.status` reste typé `string` puisque le backend le sert `Optional[str]` et peut le laisser nul.
- [ ] #3 `HomeTile` rend le même marqueur en surimpression de la couverture pour une tuile en échec ; le champ de statut est ajouté au seul variant `kind: "media"` de `HomeTileItem`, en optionnel, et renseigné par `buildRecentlyAdded` dans `mobile/app/(tabs)/inbox.tsx`. Les tuiles de « Continuer l'apprentissage » et celles de `kind: "folder"` sont inchangées et ne gagnent aucun champ.
- [ ] #4 L'étiquette d'accessibilité d'une ligne et d'une tuile en échec annonce l'échec en plus de ce qu'elle annonce déjà, sans dupliquer `mediaCard.a11yByCreator`, `mediaCard.a11yFromDomain`, `home.tile.a11yMedia` ni `home.tile.a11yFolder`.
- [ ] #5 Sous le message d'erreur de la branche `pollingState === "failed"` de `mobile/app/media/[id].tsx`, un bloc énonce que la source n'est pas encore prise en charge et offre un bouton unique de demande. Il est rendu **identiquement sur iOS et sur Android** : aucun test sur `Platform.OS` ne garde le bloc.
- [ ] #6 Le bloc n'est rendu que pour les 8 codes où sa phrase est vraie — `LIVE_CONTENT_UNSUPPORTED`, `IMAGE_POST_UNSUPPORTED`, `NOT_AN_ARTICLE_PAGE`, `ARTICLE_TEXT_NOT_FOUND`, `DOCUMENT_PARSE_FAILED`, `NO_TRANSCRIBABLE_MEDIA`, `NO_TRANSCRIPT_AVAILABLE`, `POST_TEXT_EMPTY` — et pour aucun des 16 autres membres de `MediaFailureCode`, ni quand `error_code` est absent. La liste vit à côté de `ERROR_CODE_MESSAGES` dans `mobile/src/lib/getFriendlyErrorMessage.ts`.
- [ ] #7 Le code d'échec est lu depuis `mediaData.processing_job.error_code`, déjà exposé par le hook, et `mobile/src/hooks/useMediaDetailPolling.ts` n'est pas modifié : `git diff --stat` ne le mentionne pas.
- [ ] #8 Le bloc vit dans son propre composant sous `mobile/src/components/`, qui porte l'état du bouton (repos / envoi / envoyé / erreur) : `mobile/app/media/[id].tsx` ne gagne aucun appel de hook, et son diff n'ajoute ni `useState`, ni `useCallback`, ni `useEffect`.
- [ ] #9 Un tap sur le bouton appelle `BugReportService.createBugReport` avec le `media_item_id` de l'écran et l'`error_code` lu, un sujet et une description construits depuis les catalogues i18n ; le payload de `mobile/src/services/bugReportService.ts` gagne ces deux champs en optionnels. Ni l'URL source (`original_url` / `normalized_url`) ni le `MediaFailureCode` ne sont rendus à l'écran.
- [ ] #10 Pendant l'envoi le bouton est désactivé et montre une progression ; après un succès il passe en confirmation et n'est plus actionnable ; après un échec il affiche la phrase de `getFriendlyErrorMessage` — le `429` du limiteur de débit inclus, sans nouvelle clé pour ce cas — et redevient actionnable.
- [ ] #11 `CreateBugReportRequest` (`media_summarizer/api/endpoints/bug_reports.py`) gagne `media_item_id` et `error_code` en `Optional[str] = None`, et `create_bug_report` résout la ligne du média par `get_media_for_user(media_item_id, current_user.id)` quand `media_item_id` est fourni, pour en tirer `source_url`, `media_key` et `media_type`. Aucun `Scan` n'est écrit.
- [ ] #12 Une résolution qui échoue ne fait pas échouer le POST : le `HTTPException` 404 de `get_media_for_user` est capturé, le rapport est créé avec le `media_item_id` reçu et sans URL, et l'événement est journalisé en `warning`.
- [ ] #13 `BugReport` (`media_summarizer/core/services/bug_report_service.py`) porte les nouveaux champs en `Optional[str] = None`, et `to_dynamodb_item` ne les émet que lorsqu'ils sont renseignés — le motif exact de `attachment_key` — de sorte qu'un rapport générique venu de l'onglet Compte écrit la même ligne qu'aujourd'hui.
- [ ] #14 Les nouvelles clés d'interface — marqueur d'échec sur les vignettes et son étiquette d'accessibilité, titre du bloc, phrase d'introduction, libellé du bouton, libellé de confirmation, sujet et description du rapport — existent dans les **11** catalogues de `mobile/src/i18n/`, et aucune clé existante n'est laissée orpheline.
- [ ] #15 `mobile/package.json` ne gagne aucune dépendance et `mobile/app.config.ts` n'est pas modifié — aucune source de fingerprint touchée, donc l'OTA reste intacte sur les builds déjà installés ; `git diff --stat` ne mentionne ni l'un ni l'autre.
- [ ] #16 `mobile/MANUAL_TEST_CHECKLIST.md` décrit les cas à vérifier sur appareil — marqueur dans la Bibliothèque et sur l'Accueil après un échec, bloc présent sur un des 8 codes, bloc absent sur un code hors liste, bloc et bouton présents sur Android comme sur iOS, état de confirmation après envoi — avec les totaux de catégorie et le grand total mis à jour.
- [ ] #17 `ruff check` et `mypy` passent sur `media_summarizer/`, et `npm run lint` et `npm run typecheck` passent dans `mobile/`.
<!-- AC:END -->
