---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark : refonte disruptive de l'écran d'abonnement

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Parti pris A — « la carte porte le chiffre, la vitrine porte les noms, et plus rien de décisif n'est derrière un dépliant ».** Le dépliant `paywall-includes-toggle` est supprimé, pas raccourci. Ce qu'il cachait est remplacé par deux blocs plats et scannables : une **vitrine de noms propres** (une pastille par plateforme et par format, aucune phrase) et un **tableau de coût de quatre lignes**. Les quatre lignes de bénéfices (`buildPlanHighlights`) et les cinq sections du détail (`buildPlanIncludes`, `buildMinutesLegend`) disparaissent au profit d'**une seule phrase de promesse**. Le mot « transcription » quitte l'écran ; il est remplacé par ce que l'utilisateur reconnaît, « audio et vidéo », mot déjà traduit dans les onze catalogues (`plan.minutesRule`).

Cinq arguments, dans l'ordre de force.

1. **Le gain est mesuré, pas invoqué.** Aujourd'hui, atteindre la liste des sources acceptées et le coût réel d'un import demande **1 tap de plus** et met le lecteur devant **574 mots en français** (219 replié + 355 déplié, §1). Le parti pris A met **la même information à zéro tap** pour ≈ **225 unités de lecture** (≈ 195 mots de phrases + ≈ 30 noms propres scannés), soit **−61 %** — et il supprime au passage les **15 mots d'anglais non traduits** codés en dur dans `paywall.tsx:291-294`, servis tels quels aux onze locales.

2. **Trois implémentations de référence consultées refusent la matrice comparative et font exactement ce que A fait.** Google One nomme la formule par sa quantité (« Basic (100 GB) », « Standard (200 GB) ») et libelle l'unité par son usage (« 200 GB total storage for Google Photos, Drive & Gmail »), pas par son mécanisme. Spotify Premium met **une** liste partagée « All Premium plans include: » (5 items) au-dessus de cartes qui ne portent que ce qui diffère. Apple One garde des cartes par formule avec un dépliant de **prix**, jamais de dépliant de **capacités**. Aucune des trois n'aligne des lignes de fonctionnalités sur des colonnes de formules (§3).

3. **La vitrine par pastilles est la seule forme qui survive à l'arabe.** `plan.includes.capture.links` en `ar.ts:221` enchâsse huit noms latins dans une phrase RTL, et le résultat est déjà cassé : la conjonction se colle au nom (`وReels`, `وSpotify`) parce qu'un run LTR au milieu d'un run RTL n'a pas d'espace de séparation garanti. Une pastille par nom = un run bidi par boîte = plus aucun réordonnancement à arbitrer. Le même argument vaut pour l'allemand : « PowerPoint », « Sprachnachricht » élargissent leur propre pastille au lieu de faire déborder un paragraphe (§7).

4. **La vitrine devient exacte par construction, et non par relecture.** La liste des plateformes n'est plus une prose retapée onze fois : elle est **servie par le backend**, dérivée de la table qui décide déjà de l'acceptation (`SourcePlatform` + les hôtes de `classifiers.py`), exactement comme les chiffres arrivent de `GET /api/pricing`. Les noms de marque et les extensions de fichier ne se traduisent pas : la vitrine ne coûte donc **aucune clé i18n** et ne peut pas dériver comme elle a dérivé (l'écran vend aujourd'hui les publications photo Instagram, que le worker refuse avec `IMAGE_POST_UNSUPPORTED`) (§6).

5. **Le tableau de coût est l'argument de vente que l'écran cachait.** Une vidéo YouTube coûte **1 minute quelle que soit sa durée** — `record_captions_purchase` n'est appelé que par `youtube_ingestion_worker.py:895`, au tarif plat `captions_minutes`. Un épisode de podcast dont le flux porte une balise Podcasting 2.0 coûte **zéro** (court-circuit inline dans `podcastindex_resolution_worker.py:140`). C'est aujourd'hui écrit en petit dans `plan.legend.captions`, derrière un dépliant, sous un titre qui annonce une contrainte (« Ce que comptent les minutes mensuelles ») au lieu d'un avantage. Le remonter à plat, en quatre lignes chiffrées interpolées depuis `unit_conversion`, rend l'allocation compréhensible sans arithmétique mentale.

**Compromis explicitement acceptés :**

- **L'écran devient plus long en pixels qu'il ne l'est replié aujourd'hui**, tout en étant plus court que son état déplié. On échange un tap contre du défilement. C'est le bon échange ici : le tap est une porte que le lecteur ne sait pas devoir ouvrir, le défilement est un geste qu'il fait de toute façon. Le prix reste au-dessus du pli et la CTA reste dans un pied collant, donc aucune des deux contraintes de store n'est touchée.
- **Aucun logo tiers.** La vitrine se lit en noms. Ce n'est pas un choix esthétique mais la seule position défendable : Apple exige une licence écrite pour tout logo Apple, TikTok exige une permission écrite préalable, WhatsApp interdit le verrouillage de sa marque avec une autre marque, et Spotify interdit le co-branding et le voisinage avec des services similaires — c'est-à-dire précisément une rangée de logos (§5).
- **Une phrase de promesse au lieu de quatre lignes de bénéfices.** Le risque est de sous-décrire au sens de la guideline 3.1.2(c) d'Apple (« you should clearly describe what the user will get for the price »). Il est couvert autrement, et mieux : la vitrine et le tableau de coût sont *sur* l'écran, sans dépliant, ce que quatre lignes de bénéfices doublées d'un dépliant ne faisaient pas.
- **Deux écrans, pas un.** L'onglet Compte reste la surface de consultation, le paywall devient l'offre seule. La frontière bouge, le nombre d'écrans non (§8).

---

## 1. État des lieux chiffré (AC#1)

### 1.1 Méthode

Les onze catalogues de `mobile/src/i18n/` ont été parsés clé par clé. Un `{placeholder}` est compté comme un mot (il rend toujours au moins une valeur) et retiré du compte de caractères. Les deux métriques sont données parce qu'un compte de mots seul mentirait sur `ja` et `zh`, qui n'ont pas d'espaces. Contrôle de la méthode : le total `plan.*` + `paywall.*` de `fr.ts` sort à **869 mots** et le bloc déplié à **355 mots**, soit exactement les « ~870 » et « ~355 » de la description de la tâche.

Les 75 clés `plan.*` + `paywall.*` existent dans les onze fichiers (le type `Catalog` en fait une erreur `tsc` sinon). Total par locale, toutes clés confondues, y compris celles qui ne s'affichent jamais simultanément :

| en | fr | es | de | it | pt | nl | ja | zh | ar | hi |
|---|---|---|---|---|---|---|---|---|---|---|
| 779 | **869** | — | 757 | — | — | 782 | 152 | **144** | 677 | **907** |

### 1.2 Ce qui est réellement à l'écran

Deux états, mesurés bloc par bloc. Le pied de page collant et le bloc légal sont comptés parce qu'ils s'affichent toujours. La ligne `paywall-reason` et la note d'essai sont **exclues** : elles ne rendent que sur un compte à court de minutes ou en essai. Les 15 mots / 77 caractères de l'accroche anglaise codée en dur (`paywall.tsx:291-294`) sont comptés dans les onze locales, puisqu'elle n'est pas traduite.

| bloc | en | fr | de | nl | ar | ja | zh | hi |
|---|---|---|---|---|---|---|---|---|
| en-tête (`title` + `subtitle`) | 15 | 14 | 13 | 12 | 16 | 2 | 2 | 17 |
| accroche codée en dur (anglais) | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 |
| `paywall.selectorLabel` | 5 | 6 | 4 | 4 | 6 | 1 | 1 | 6 |
| 3 cartes (allocation, tarif horaire, plafond, badge) | 41 | 35 | 34 | 32 | 41 | 25 | 19 | 35 |
| `plan.minutesRule` | 20 | 26 | 21 | 21 | 20 | 1 | 1 | 27 |
| bloc « Inclus dans chaque formule » (4 lignes) | 47 | 53 | 45 | 46 | 49 | 6 | 5 | 53 |
| libellé du dépliant | 5 | 6 | 5 | 5 | 6 | 1 | 1 | 7 |
| légal + CTA + « résiliez à tout moment » | 60 | 64 | 53 | 58 | 50 | 15 | 17 | 69 |
| **état replié, total mots** | **208** | **219** | **190** | **193** | **203** | **66** | **61** | **229** |
| **état replié, total caractères** | **1 120** | **1 295** | **1 193** | **1 164** | **1 006** | **578** | **419** | **1 124** |

| section du dépliant | en | fr | de | nl | ar | ja | zh | hi |
|---|---|---|---|---|---|---|---|---|
| `capture` (les sources acceptées) | 71 | 79 | 63 | 62 | 64 | 11 | 16 | 78 |
| `read` | 55 | 56 | 51 | 56 | 41 | 4 | 5 | 64 |
| `generate` | 48 | 53 | 46 | 45 | 37 | 4 | 4 | 50 |
| `organise` | 48 | 51 | 46 | 53 | 40 | 4 | 4 | 48 |
| `minutes` (ce qui coûte, ce qui est gratuit) | 104 | 116 | 100 | 105 | 89 | 24 | 21 | 126 |
| **dépliant, total mots** | **326** | **355** | **306** | **321** | **271** | **47** | **50** | **366** |
| **état déplié, total mots** | **534** | **574** | **496** | **514** | **474** | **113** | **111** | **595** |
| **état déplié, total caractères** | **2 871** | **3 431** | **3 178** | **3 093** | **2 510** | **1 441** | **1 072** | **2 904** |

**Locale la plus courte : `zh`** — 61 mots repliés, 111 dépliés, 1 072 caractères. **Locale la plus longue : `hi` en mots** (229 / 595) et **`fr` en caractères** (1 295 / 3 431). Le français est donc la contrainte de mise en page, le hindi la contrainte de lecture.

### 1.3 Gestes pour atteindre chaque information

Les taps sont comptés depuis le code. Les défilements sont **estimés** : `375 × 667` pt (iPhone SE 3ᵉ génération, le plus petit appareil visé), largeur de contenu `375 − 2 × Spacing.lg = 327` pt, `Typography.small` = 13 pt → ≈ 46 caractères par ligne, `lineHeight` 18. En-tête ≈ 184 pt, pied collant ≈ 108 pt, donc fenêtre de défilement ≈ **355 pt**. Ces estimations ne sont **pas vérifiées sur appareil** — l'agent n'en a pas.

| information | taps depuis l'app ouverte | défilements estimés (fr) | où elle vit |
|---|---|---|---|
| minutes restantes, date de recharge | 1 (onglet Compte) | 0 | `SubscriptionStatusCard` |
| la règle des minutes, version courte | 1 | 0 | `minutesRule()` sous la jauge |
| les trois prix | 2 (+ « Gérer l'abonnement ») | 0 à 1 (la 3ᵉ carte est sous le pli) | `paywall-tier-*` |
| l'allocation de chaque formule | 2 | 0 à 1 | `plan.card.allowance` |
| le plafond par import | 2 | 0 à 1 | `plan.card.perImport` |
| les 4 lignes de bénéfices | 2 | ≈ 1 | `paywall-highlights` |
| conditions de renouvellement, CGU, confidentialité | 2 | ≈ 2 | `legalBlock` |
| **la liste des sources acceptées** | **3** (+ « Voir exactement ce qui est inclus ») | **≈ 3** | `plan.includes.capture.*` |
| **ce qu'une minute achète, et ce qui est gratuit** | **3** | **≈ 5** | `plan.legend.*`, dernière section |

Contenu défilable estimé : ≈ **798 pt replié** (2,2 écrans) et ≈ **1 828 pt déplié** (5,1 écrans). Autrement dit : les deux informations que la description appelle « décisives » sont les **deux dernières** que l'écran consent à montrer.

### 1.4 Défauts d'exactitude relevés au passage, tous prouvables

Ils ne sont pas cosmétiques : la refonte doit les corriger, sinon elle réécrit des affirmations fausses.

| affirmation à l'écran | réalité dans le code | preuve |
|---|---|---|
| « reels **et publications photo** Instagram » (`plan.includes.capture.links`) | une publication photo échoue en `IMAGE_POST_UNSUPPORTED` : « no OCR/vision pipeline exists » | `workers/instagram_ingestion_worker.py:19,365`, `core/models/failure_codes.py:44` |
| « les TikToks … ne coûtent rien du tout : ils ne sont pas transcrits » (`plan.legend.free`) | vrai seulement si yt-dlp trouve des sous-titres natifs ; sinon Deepgram et débit de la **durée réelle** via `gate_audio_transcription` | `workers/tiktok_ingestion_worker.py:1017`, `core/services/audio_quota_gate.py` |
| « publications X » sans réserve | **texte du post uniquement** ; une vidéo attachée n'est pas traitée en V1 | `workers/x_ingestion_worker.py:1-9`, `docs/INGESTION_WORKERS_PROVIDERS.md` |
| « Organisez en collections **et en tags** » (`plan.highlight.organise`, `plan.includes.organise.file`) | task-372 supprime les tags de bout en bout, task-373 renomme « collection » en « dossier » | `backlog/tasks/task-372`, `task-373`, dépendances de task-377 |
| accroche « Save anything worth coming back to… » | **codée en dur en anglais**, servie identiquement aux onze locales | `mobile/app/paywall.tsx:291-294` |
| suffixe de période `/mo` sur chaque prix | **codé en dur en anglais** lui aussi | `mobile/app/paywall.tsx:473` |
| aucune mention de WhatsApp | `SourcePlatform.WHATSAPP` existe, le partage texte **et** la note vocale Opus sont implémentés, `share.whatsappText` est traduit dans les onze catalogues | `core/media_ingestion/domain.py`, `mobile/src/types/sharedContent.ts:59,71`, `docs/whatsapp-share-payload-shapes.md` |

---

## 2. Ce que l'app sait vraiment ingérer (AC#2)

Liste dressée depuis le code, jamais de mémoire. `SourcePlatform` compte **onze membres** dont deux techniques (`WEB`, `DIRECT_URL`) et un sentinelle (`UNKNOWN`) : `media_summarizer/core/media_ingestion/domain.py:31-43`.

### 2.1 Les URL partageables, une ligne par sous-cas

| source | ce que le classifieur accepte | hôtes reconnus | chaîne de traitement | coût en minutes | preuve |
|---|---|---|---|---|---|
| Podcast Spotify | ≥ 2 segments et `segments[0] ∈ {episode, show}` | `open.spotify.com`, `www.open.spotify.com` | résolution PodcastIndex → transcript RSS si présent, sinon Deepgram `nova-3` | **0** si l'épisode publie un `<podcast:transcript>` Podcasting 2.0, sinon la durée réelle | `classifiers.py` `_SPOTIFY_HOSTS`, `podcastindex_resolution_worker.py:140,342` |
| Podcast Apple Podcasts | `"podcast"` présent dans les segments | `podcasts.apple.com`, `www.podcasts.apple.com` | idem | idem | `classifiers.py` `_APPLE_HOSTS` |
| Podcast Deezer | `"show"` ou `"episode"` dans les segments | `deezer.com`, `www.deezer.com` | idem | idem | `classifiers.py` `_DEEZER_HOSTS` |
| Flux RSS quelconque | chemin en `.rss`/`.xml` ou segment `feed`, **ou** hôte commençant par `feeds.`/`rss.` | n'importe quel domaine | idem | idem | `classifiers.py` `_path_looks_like_rss`, `_host_looks_like_rss`, `_RSS_HOST_HINT_PREFIXES` |
| Vidéo YouTube | tout chemin sur un hôte court, `/watch?v=…` non vide, `/shorts/`, `/live/`, `/embed/` | `youtube.com`, `www.`, `m.`, **`music.youtube.com`**, `youtu.be`, `www.youtu.be` | acteur Apify de transcription | **1 minute forfaitaire**, quelle que soit la durée | `classifiers.py` `_YOUTUBE_HOSTS`, `_is_youtube_video_path` ; `youtube_ingestion_worker.py:895` → `record_captions_purchase` → `quota_enforcer.py:182` `_conversion("captions_minutes", 1)` |
| Reel / IGTV Instagram | `/reel/`, `/p/`, `/tv/` | `instagram.com`, `www.instagram.com` | Apify puis Deepgram en `push` | durée réelle | `classifiers.py` `_is_instagram_video_path` |
| **Publication photo Instagram** | acceptée au classement (`/p/` passe), **refusée par le worker** | idem | échec `IMAGE_POST_UNSUPPORTED` : « no OCR/vision pipeline exists » | — | `instagram_ingestion_worker.py:19,365`, `failure_codes.py:44` |
| Publication X | `/i/status/{chiffres}`, `/i/web/status/{chiffres}`, ou `{compte}/status/{chiffres}` | `x.com`, `www.x.com`, **`twitter.com`**, `www.twitter.com` | X API v2 lookup, **texte du post seul** | **0** | `classifiers.py` `_X_HOSTS`, `_is_x_post_path` ; `x_ingestion_worker.py:1-9` |
| Vidéo TikTok | tout chemin sur un hôte court, `/@compte/video/…`, `/t/…` | `tiktok.com`, `www.`, `m.`, **`vm.tiktok.com`**, **`vt.tiktok.com`** | sous-titres natifs yt-dlp → Apify si l'IP est bloquée → Deepgram sinon | **0** avec sous-titres natifs, sinon la durée réelle | `classifiers.py` `_TIKTOK_HOSTS`, `_TIKTOK_SHORT_HOSTS` ; `tiktok_ingestion_worker.py:1017` |
| **Publication photo TikTok** | **refusée au classement** : `/@compte/photo/…` | idem | `UnsupportedUrlError` : « TikTok photo posts are not supported yet. » | — | `classifiers.py` `_is_tiktok_photo_path`, `_UNSUPPORTED_TIKTOK_PHOTO_MESSAGE` |
| URL audio directe | chemin finissant par une extension audio | n'importe quel domaine | Deepgram `nova-3` | durée réelle | `classifiers.py` `_path_looks_like_audio`, `SourcePlatform.DIRECT_URL` |
| Article ou page web quelconque | **tout le reste** — c'est le cas par défaut | n'importe quel domaine | trafilatura, sans repli | **0** | `classifiers.py` cas terminal `MediaFamily.ARTICLE` / `SourcePlatform.WEB` ; `docs/INGESTION_WORKERS_PROVIDERS.md` |

Restrictions transverses du classifieur, valables pour toutes les lignes ci-dessus : schémas `http` et `https` seulement, longueur maximale d'URL **2 048** caractères, `localhost` et les hôtes privés refusés, listes `INGEST_URL_BLOCKED_DOMAINS` / `INGEST_URL_ALLOWED_DOMAINS` en surcharge (`classifiers.py` `_SUPPORTED_SCHEMES`, `_MAX_URL_LENGTH`, `_FORBIDDEN_HOSTS`).

### 2.2 Les fichiers et les partages

| source | formats | plafond | chaîne | coût | preuve |
|---|---|---|---|---|---|
| Document | `pdf docx pptx xlsx` | 50 Mo | LlamaParse, repli Unstructured | **1 minute par 5 pages**, minimum 1 | `DocumentFormat.supported_extensions()` (`core/ports/document_parser.py:53`), `UPLOAD_PICKER_MIME_TYPES` (`mobile/src/types/upload.ts`), `quota_enforcer.py` `record_document_parse` |
| Image / photo de page | `jpg jpeg png tiff tif bmp heif heic` | 50 Mo | idem (OCR par le parseur de documents) | idem | `DocumentFormat.from_extension`, `IMAGE_UPLOAD_EXTENSIONS` |
| Fichier audio | `mp3 m4a aac ogg wav flac opus` | 50 Mo | Deepgram `nova-3` | durée réelle | `AUDIO_UPLOAD_EXTENSIONS`, `MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024` |
| **Message texte WhatsApp** | texte partagé | — | traité comme du texte, aucune transcription | **0** | `SourcePlatform.WHATSAPP`, `mobile/src/types/sharedContent.ts:59,71`, clé `share.whatsappText` traduite dans les onze catalogues |
| **Note vocale WhatsApp** | Android : `audio/ogg` Opus, `PTT-YYYYMMDD-WAxxxx.opus` ; iOS : transcodée en `.m4a` (`audio/mp4`, `com.apple.m4a-audio`) | 50 Mo | Deepgram `nova-3` | durée réelle | `docs/whatsapp-share-payload-shapes.md` (tableau comparatif lignes 149-151) |

### 2.3 Ce que l'écran actuel ne montre pas, alors que le code le fait

C'est la section que l'AC#2 demande à part. Chaque ligne est un argument de vente déjà payé en ingénierie et jamais affiché.

1. **WhatsApp, texte et note vocale.** Le mot « WhatsApp » n'apparaît dans aucune clé `plan.*` ni `paywall.*`, dans aucune des onze locales. C'est la capacité la plus quotidienne du produit : on transfère un vocal à l'app comme on le transfère à un contact.
2. **`music.youtube.com`** et les liens courts **`youtu.be`** — le détail dit « vidéos YouTube » sans dire que le lien de partage court et YouTube Music passent.
3. **`twitter.com`** — un lien ancien fonctionne, personne ne le sait.
4. **`vm.tiktok.com` / `vt.tiktok.com`** — c'est exactement la forme que l'application TikTok met dans le presse-papier.
5. **Un épisode Podcasting 2.0 coûte zéro minute.** Le court-circuit transcript RSS est un avantage tarifaire réel, invisible.
6. **Une vidéo YouTube coûte 1 minute forfaitaire**, qu'elle dure trois minutes ou trois heures. C'est l'argument le plus fort de la grille et il est enfoui dans la dernière puce du dépliant.
7. **L'URL audio directe** — n'importe quel `.mp3` en ligne. Aucune mention.
8. **Les formats de fichiers ne sont jamais énumérés** : le détail dit « fichiers » sans dire `pdf docx pptx xlsx` ni les sept conteneurs audio.

Et ce que l'écran montre à tort : les publications photo Instagram (échec worker), « les TikToks ne coûtent rien du tout » (faux sans sous-titres natifs), les publications X sans préciser « texte seulement », et les tags (supprimés par task-372).

---

## 3. Quatre partis pris de présentation (AC#3)

### 3.0 Ce que les références consultées disent réellement

Toutes les pages ci-dessous ont été **ouvertes depuis cet environnement** ; celles qui ont échoué sont listées en §9.

| référence | ce qui a été observé | ce que j'en retiens |
|---|---|---|
| **Google One** (`one.google.com/about/plans`) | trois cartes nommées **par le quota** — « Basic (100 GB) » 1,99 €, « Standard (200 GB) » 2,99 €, « Google AI Plus (2 TB) » 9,99 € ; libellés d'avantages formulés en résultat, une carte « Recommended » ; **aucune matrice comparative** | le chiffre appartient au **nom** de la formule, pas à une ligne de bénéfice |
| **Spotify Premium** (`spotify.com/premium`) | quatre cartes, puis **une seule** liste partagée « All Premium plans include: » de cinq lignes ; un quota exprimé « 15 hours/month of listening time » ; **aucune matrice** | ce qui est commun se dit **une fois**, hors des cartes |
| **Apple One** (`apple.com/apple-one`) | trois cartes, un dépliant « See price breakdown » ; les services sont désignés par **leur nom de produit** ; **aucune matrice** | le seul dépliant admis porte sur le **calcul du prix**, pas sur ce qu'on achète |
| **Readwise Reader** (`readwise.io/read`) | huit tuiles à pictogramme : « Web highlighting / RSS / PDFs / YouTube / Twitter threads / Read-it-later / EPUBs / Newsletters » ; les logos n'apparaissent que pour les **destinations d'export** ; le prix vit dans la FAQ | la vitrine de sources en **tuiles nominatives** est une forme éprouvée sur un produit du même métier |
| **Snipd** (`snipd.com/pricing`) | une matrice Free/Premium à deux colonnes ; évite « transcription » : « AI processing (900min/month) », « 2 episodes per week » | même un concurrent direct **ne vend pas le mot « transcription »** |
| **RevenueCat, Paywalls** (`revenuecat.com/docs/tools/paywalls`) | distingue « Single screen » et « Multipage flow » ; **aucun gabarit nommé, aucune consigne de longueur de texte** | le fournisseur ne tranche pas la densité : il n'y a pas d'autorité à citer là-dessus |
| **RevenueCat, State of Subscription Apps 2025** (`revenuecat.com/state-of-subscription-apps-2025`) | paywall dur : 12,11 % de conversion à J35 contre 2,18 % en freemium ; essai de 14 j ≈ ×8 de RPI ; remboursements 5,8 % contre 3,4 % ; 82 % des essais démarrent le jour de l'installation ; essais de 17-32 j retenus à 45,7 % contre 26,8 % | **aucun chiffre sur le nombre de formules affichées ni sur la longueur des textes** : la densité n'est pas arbitrable par les données publiques |

Conclusion transversale, et elle est nette : **aucune des cinq implémentations consultées n'affiche de matrice comparative** sur son écran d'offre principal, et la seule qui en affiche une (Snipd) n'a que deux colonnes. La forme « tableau à N colonnes » n'est pas la norme du métier ; la forme « cartes + une liste commune » l'est.

### 3.1 Parti pris A — « la carte porte le chiffre, la vitrine porte les noms »

Le dépliant est **supprimé**, pas raccourci. Ce qu'il contenait remonte sous deux formes non textuelles : une **vitrine de puces nominatives** (une plateforme par puce) et un **tableau de coût à quatre lignes**. Les quatre lignes de bénéfices et les cinq sections de détail fusionnent en **une phrase de promesse**.

```
┌─────────────────────────────────────────┐
│ ✕                                       │
│ Écoutez, lisez, retenez.                │  ← paywall.title (traduit)
│ Tout ce que vous partagez devient       │  ← 1 phrase, ~14 mots
│ du texte que vous pouvez relire.        │
├─────────────────────────────────────────┤
│  ○ Reader     3,00 €/mois   1 h /mois   │  ← prix : product.priceString
│  ● Mix        5,00 €/mois   5 h /mois   │  ← allocation : GET /api/pricing
│  ○ Audio-Heavy 9,00 €/mois 12 h /mois  │
│                                         │
│  Recommandé pour commencer              │  ← paywall-recommendation
├─────────────────────────────────────────┤
│ CE QUE VOUS POUVEZ ENVOYER              │  ← 1 clé i18n
│ ┌──────┐┌────────┐┌───────────┐         │
│ │YouTube││TikTok  ││Instagram  │        │  ← noms propres, 0 clé i18n
│ └──────┘└────────┘└───────────┘         │
│ ┌────────┐┌───────┐┌──────┐┌──────┐     │
│ │Spotify ││Apple  ││Deezer││RSS   │     │
│ └────────┘└───────┘└──────┘└──────┘     │
│ ┌────┐┌────────┐┌──────────────────┐    │
│ │ X  ││WhatsApp││Articles & web    │    │
│ └────┘└────────┘└──────────────────┘    │
│ ┌───────────────┐┌────────────────┐     │
│ │PDF DOCX PPTX  ││MP3 M4A OPUS WAV│     │
│ └───────────────┘└────────────────┘     │
├─────────────────────────────────────────┤
│ CE QUE ÇA CONSOMME                      │  ← 1 clé i18n
│ Articles, pages web, posts X ····· 0    │  ← 4 lignes, valeurs du backend
│ Vidéo YouTube ················ 1 min    │
│ Podcast avec transcript ·········· 0    │
│ Audio, vidéo, reel ······ sa durée      │
│ Document ············ 1 min / 5 pages   │
├─────────────────────────────────────────┤
│ Renouvelé chaque mois jusqu'à           │  ← paywall.renewalTerms
│ résiliation.  CGU · Confidentialité     │
└─────────────────────────────────────────┘
│  [   Commencer avec Mix   ]           │  ← pied collant
│  Résiliez à tout moment                 │
```

**Référence** : Google One pour le chiffre dans la carte, Spotify pour la liste commune unique, Readwise Reader pour la vitrine de sources en tuiles.

### 3.2 Parti pris B — la matrice comparative

Un tableau à quatre colonnes (Gratuit + trois formules) et une dizaine de lignes de capacités.

```
                    Gratuit  Reader   Mix   Audio-Heavy
Articles, pages web    ✓        ✓      ✓      ✓
Podcasts               —        ✓      ✓      ✓
YouTube, TikTok        —        ✓      ✓      ✓
WhatsApp               —        ✓      ✓      ✓
Documents              —        ✓      ✓      ✓
Temps mensuel          —      2 h    6 h   12 h
Plafond par envoi      —     30 m    1 h    2 h
Prix                   —    3,00 € 5,00 € 9,00 €
```

**Référence** : Snipd (deux colonnes). **Disqualifié** : quatre colonnes sur 327 pt de large laissent ≈ 60 pt par colonne ; en allemand « Plafond par envoi » devient `Obergrenze pro Übertragung` et casse la grille ; en arabe la matrice doit s'inverser colonne par colonne. Et le tableau est presque vide de contraste utile — **toutes les formules font tout**, seul le temps change (`paywall.subtitle` le dit déjà). Une matrice dont neuf lignes sur dix sont identiques vend l'idée inverse de la vérité produit.

### 3.3 Parti pris C — le parcours en plusieurs pages

Trois écrans successifs : (1) ce que fait l'app, (2) ce que vous pouvez envoyer, (3) les prix.

**Référence** : RevenueCat, gabarit « Multipage flow » (`revenuecat.com/docs/tools/paywalls`) — la seule des deux formes que le fournisseur nomme. **Écarté** : il déplace le prix hors du premier écran, alors que l'écran est atteint depuis une ligne « Gérer l'abonnement » — l'utilisateur qui vient là **sait déjà** qu'il s'agit de payer, et lui faire traverser deux écrans avant le chiffre allonge le chemin au lieu de le raccourcir. Le grief de l'owner est « trop lent à lire » : trois pages, c'est deux gestes de plus, pas moins.

### 3.4 Parti pris D — garder le dépliant, le raccourcir

On conserve `paywall-includes-toggle` et on réécrit les cinq sections en deux. **Écarté** : c'est exactement l'arbitrage que la description demande de **rejuger**. Le commentaire d'en-tête de `planCopy.ts` justifie le dépliant par « the wall of text every paywall study says nobody reads » — le raisonnement est bon et la conclusion fausse : la réponse à « personne ne lit un mur de texte » n'est pas « cachons le mur », c'est **« n'écrivons pas un mur »**. Une puce `YouTube` n'est pas du texte à lire, c'est un objet à reconnaître. Aucune des cinq références consultées ne met sa liste de capacités derrière un dépliant.

### 3.5 Comparaison

| critère | A (vitrine + tableau de coût) | B (matrice) | C (multi-pages) | D (dépliant raccourci) |
|---|---|---|---|---|
| unités de texte à 0 tap (fr) | **≈ 225** | ≈ 190 | ≈ 90 sur la page 1 | ≈ 219 |
| taps pour la liste des sources | **0** | 0 | 1 | 1 |
| taps pour les règles de coût | **0** | 0 | 2 | 1 |
| prix visible sans geste | oui | oui, en dernière ligne | **non** | oui |
| tient en arabe RTL | **oui** (une puce = un run bidi) | non (grille à inverser) | oui | non (`ar.ts:221` colle `وSpotify`) |
| tient en allemand / néerlandais | **oui** (la puce s'élargit seule) | non | oui | risqué |
| clés i18n pour la liste des plateformes | **0** (noms propres) | 0 | 0 | ≈ 12 × 11 locales |
| référence consultable | Google One, Spotify, Readwise | Snipd | RevenueCat | aucune |
| risque de dérive (task-299) | **nul** (dérivé du backend) | nul | nul | élevé |

