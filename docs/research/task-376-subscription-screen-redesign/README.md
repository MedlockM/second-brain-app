---
owner_decision: ok   # pending | ok | abandoned | redo | more
---

# Benchmark : refonte disruptive de l'écran d'abonnement

## Owner Validation

**Decision**: le parti pris A
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Parti pris A — « la carte porte le chiffre, la vitrine porte les noms, et plus rien de décisif n'est derrière un dépliant ».** Le dépliant `paywall-includes-toggle` est supprimé, pas raccourci. Ce qu'il cachait est remplacé par deux blocs plats et scannables : une **vitrine de noms propres** (une pastille par plateforme et par format, aucune phrase) et un **tableau de coût de quatre lignes**. Les quatre lignes de bénéfices (`buildPlanHighlights`) et les cinq sections du détail (`buildPlanIncludes`, `buildMinutesLegend`) disparaissent au profit d'**une seule phrase de promesse**. Le mot « transcription » quitte l'écran ; il est remplacé par ce que l'utilisateur reconnaît, « audio et vidéo », mot déjà traduit dans les onze catalogues (`plan.minutesRule`).

Cinq arguments, dans l'ordre de force.

1. **Le gain est mesuré, pas invoqué.** Aujourd'hui, atteindre la liste des sources acceptées et le coût réel d'un import demande **1 tap de plus** et met le lecteur devant **568 mots en français** (216 replié + 352 déplié, §1, arbre courant). Le parti pris A met **la même information à zéro tap** pour ≈ **225 unités de lecture** (≈ 195 mots de phrases + ≈ 30 noms propres scannés), soit **−60 %** — et il supprime au passage les **15 mots d'anglais non traduits** codés en dur dans `paywall.tsx:291-294`, servis tels quels aux onze locales.

2. **Trois implémentations de référence consultées refusent la matrice comparative et font exactement ce que A fait.** Google One nomme la formule par sa quantité (« Basic (100 GB) », « Standard (200 GB) ») et libelle l'unité par son usage (« 200 GB total storage for Google Photos, Drive & Gmail »), pas par son mécanisme. Spotify Premium met **une** liste partagée « All Premium plans include: » (5 items) au-dessus de cartes qui ne portent que ce qui diffère. Apple One garde des cartes par formule avec un dépliant de **prix**, jamais de dépliant de **capacités**. Aucune des trois n'aligne des lignes de fonctionnalités sur des colonnes de formules (§3).

3. **La vitrine par pastilles est la seule forme qui survive à l'arabe.** `plan.includes.capture.links` en `ar.ts:221` enchâsse huit noms latins dans une phrase RTL, et le résultat est déjà cassé : la conjonction se colle au nom (`وReels`, `وSpotify`) parce qu'un run LTR au milieu d'un run RTL n'a pas d'espace de séparation garanti. Une pastille par nom = un run bidi par boîte = plus aucun réordonnancement à arbitrer. Le même argument vaut pour l'allemand : « PowerPoint », « Sprachnachricht » élargissent leur propre pastille au lieu de faire déborder un paragraphe (§7).

4. **La vitrine devient exacte par construction, et non par relecture.** La liste des plateformes n'est plus une prose retapée onze fois : elle est **servie par le backend**, dérivée de la table qui décide déjà de l'acceptation (`SourcePlatform` + les hôtes de `classifiers.py`), exactement comme les chiffres arrivent de `GET /api/pricing`. Les noms de marque et les extensions de fichier ne se traduisent pas : la vitrine ne coûte donc **aucune clé i18n** et ne peut pas dériver comme elle a dérivé (l'écran vend aujourd'hui les publications photo Instagram, que le worker refuse avec `IMAGE_POST_UNSUPPORTED`) (§6).

5. **Le tableau de coût est l'argument de vente que l'écran cachait.** Une vidéo YouTube coûte **1 minute quelle que soit sa durée** — `record_captions_purchase` n'est appelé que par `youtube_ingestion_worker.py:895`, au tarif plat `captions_minutes`. Un épisode de podcast dont le flux porte une balise Podcasting 2.0 coûte **zéro** (court-circuit inline dans `podcastindex_resolution_worker.py:140`). C'est aujourd'hui écrit en petit dans `plan.legend.captions`, derrière un dépliant, sous un titre qui annonce une contrainte (« Ce que comptent les minutes mensuelles ») au lieu d'un avantage. Le remonter à plat, en quatre lignes chiffrées interpolées depuis `unit_conversion`, rend l'allocation compréhensible sans arithmétique mentale.

**Compromis explicitement acceptés :**

- **L'écran devient plus long en pixels qu'il ne l'est replié aujourd'hui**, tout en étant plus court que son état déplié. On échange un tap contre du défilement. C'est le bon échange ici : le tap est une porte que le lecteur ne sait pas devoir ouvrir, le défilement est un geste qu'il fait de toute façon. Le prix reste au-dessus du pli et la CTA reste dans un pied collant, donc aucune des deux contraintes de store n'est touchée.
- **Aucun logo tiers.** La vitrine se lit en noms. Ce n'est pas un choix esthétique mais la seule position défendable : Apple exige une licence écrite pour tout logo Apple, TikTok exige une permission écrite préalable, WhatsApp interdit le verrouillage de sa marque avec une autre marque, et Spotify interdit le co-branding et le voisinage avec des services similaires — c'est-à-dire précisément une rangée de logos (§5).
- **Une phrase de promesse au lieu de quatre lignes de bénéfices.** Le risque est de sous-décrire au sens de la guideline 3.1.2(c) d'Apple (« you should clearly describe what the user will get for the price »). Il est couvert autrement, et mieux : la vitrine et le tableau de coût sont *sur* l'écran, sans dépliant, ce que quatre lignes de bénéfices doublées d'un dépliant ne faisaient pas.
- **Deux écrans, pas un.** L'onglet Compte reste la surface de consultation, le paywall devient l'offre seule. La frontière bouge, le nombre d'écrans non (§8).

**Où lire quoi**, pour la relecture : AC#1 → §1 · AC#2 → §2 · AC#3 → §3 · AC#4 → §4 · AC#5 → §5 · AC#6 → §6 · AC#7 → §7 · AC#8 → §8 · AC#9 → ce fichier, `owner_decision: pending`, aucun fichier de `mobile/` ni de `media_summarizer/` modifié. Ce qui n'a pas pu être vérifié est isolé au §9, les sources au §10, et le §11 résume ce que task-377 aurait à faire.

---

## 1. État des lieux chiffré (AC#1)

### 1.1 Méthode

Les onze catalogues de `mobile/src/i18n/` ont été parsés clé par clé, **sur l'arbre courant** — c'est-à-dire après task-372 (suppression des tags) et task-373 (« collection » → « dossier »), toutes deux mergées. Un `{placeholder}` compte pour un mot (il rend toujours au moins une valeur) et sort du compte de caractères. Les deux métriques sont données parce qu'un compte de mots seul mentirait sur `ja` et `zh`, qui n'ont pas d'espaces.

Contrôle de la méthode : la description de la tâche annonce « ~870 mots » de `plan.*` + `paywall.*` en français et « ~355 » pour le détail déplié. Sur l'arbre d'alors, la mesure sortait exactement à **869** et **355**. Sur l'arbre courant elle sort à **863** et **352** : task-372 a retiré la promesse des tags de `plan.highlight.organise` et de `plan.includes.organise.file`, ce qui vaut **−3 mots en français** dans chacun des deux blocs. Le constat de l'owner est donc intact — six mots de moins ne changent rien à un écran de 568 mots.

Les **75 clés** `plan.*` + `paywall.*` existent dans les onze fichiers (le type `Catalog` en fait une erreur `tsc` sinon). Total par locale, toutes clés confondues, y compris celles qui ne s'affichent jamais simultanément :

| en | fr | es | de | it | pt | nl | ja | zh | ar | hi |
|---|---|---|---|---|---|---|---|---|---|---|
| 775 | 863 | 846 | 753 | 813 | 823 | 778 | 152 | **144** | 675 | **903** |

### 1.2 Ce qui est réellement à l'écran

Deux états, mesurés bloc par bloc, sur les onze locales. Le pied de page collant et le bloc légal sont comptés parce qu'ils s'affichent toujours. La ligne `paywall-reason` et la note d'essai sont **exclues** : elles ne rendent que sur un compte à court de minutes ou en essai. Les **15 mots / 77 caractères** de l'accroche anglaise codée en dur (`paywall.tsx:291-294`) sont comptés dans les onze locales, puisqu'elle n'est pas traduite.

**État replié, en mots :**

| bloc | en | fr | es | de | it | pt | nl | ja | zh | ar | hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| en-tête (`title` + `subtitle`) | 15 | 14 | 16 | 13 | 15 | 16 | 12 | 2 | 2 | 16 | 17 |
| accroche codée en dur (anglais) | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 | 15 |
| `paywall.selectorLabel` | 5 | 6 | 6 | 4 | 7 | 7 | 4 | 1 | 1 | 6 | 6 |
| 3 cartes (allocation, tarif horaire, plafond, badge) | 41 | 35 | 35 | 34 | 35 | 35 | 32 | 25 | 19 | 41 | 35 |
| `plan.minutesRule` | 20 | 26 | 26 | 21 | 24 | 26 | 21 | 1 | 1 | 20 | 27 |
| bloc « Inclus dans chaque formule » (4 lignes) | 45 | 50 | 49 | 43 | 47 | 52 | 44 | 6 | 5 | 48 | 51 |
| libellé du dépliant | 5 | 6 | 4 | 5 | 5 | 6 | 5 | 1 | 1 | 6 | 7 |
| légal + CTA + « résiliez à tout moment » | 60 | 64 | 65 | 53 | 58 | 61 | 58 | 15 | 17 | 50 | 69 |
| **total mots** | **206** | **216** | **216** | **188** | **206** | **218** | **191** | **66** | **61** | **202** | **227** |
| **total caractères** | **1 103** | **1 278** | **1 184** | **1 188** | **1 179** | **1 153** | **1 146** | **571** | **416** | **997** | **1 119** |

**Le dépliant, en mots :**

| section du dépliant | en | fr | es | de | it | pt | nl | ja | zh | ar | hi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `capture` (les sources acceptées) | 71 | 79 | 81 | 63 | 76 | 84 | 62 | 11 | 16 | 64 | 78 |
| `read` | 55 | 56 | 53 | 51 | 50 | 55 | 56 | 4 | 5 | 41 | 64 |
| `generate` | 48 | 53 | 48 | 46 | 43 | 46 | 45 | 4 | 4 | 37 | 50 |
| `organise` | 46 | 48 | 47 | 44 | 46 | 45 | 51 | 4 | 4 | 39 | 46 |
| `minutes` (ce qui coûte, ce qui est gratuit) | 104 | 116 | 117 | 100 | 101 | 114 | 105 | 24 | 21 | 89 | 126 |
| **dépliant, total mots** | **324** | **352** | **346** | **304** | **316** | **344** | **319** | **47** | **50** | **270** | **364** |
| **état déplié, total mots** | **530** | **568** | **562** | **492** | **522** | **562** | **510** | **113** | **111** | **472** | **591** |
| **état déplié, total caractères** | **2 833** | **3 388** | **3 182** | **3 161** | **3 115** | **3 039** | **3 051** | **1 425** | **1 066** | **2 486** | **2 895** |

**Locale la plus courte : `zh`** — 61 mots repliés, 111 dépliés, 1 066 caractères dépliés. **Locale la plus longue en mots : `hi`** (227 / 591). **Locale la plus longue en caractères : `fr`** (1 278 / 3 388), suivie de près par `de` (1 188 / 3 161). Le français est donc la contrainte de mise en page, le hindi la contrainte de lecture, et l'allemand la contrainte de largeur de mot (§7).

### 1.3 Gestes pour atteindre chaque information

Les taps sont comptés depuis le code. Les défilements sont **estimés** : `375 × 667` pt (iPhone SE 3ᵉ génération, le plus petit appareil visé), largeur de contenu `375 − 2 × Spacing.lg = 327` pt, `Typography.small` = 13 pt → ≈ 46 caractères par ligne, `lineHeight` 18. En-tête ≈ 184 pt, pied collant ≈ 108 pt, donc fenêtre de défilement ≈ **355 pt**. Ces estimations ne sont **pas vérifiées sur appareil** — l'agent n'en a pas ; c'est la note de l'owner en fin de description de tâche.

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

Contenu défilable estimé : ≈ **790 pt replié** (2,2 écrans) et ≈ **1 805 pt déplié** (5,1 écrans). Autrement dit : les deux informations que la description appelle « décisives » sont les **deux dernières** que l'écran consent à montrer.

### 1.4 Défauts d'exactitude relevés au passage, tous prouvables

Ils ne sont pas cosmétiques : la refonte doit les corriger, sinon elle réécrit des affirmations fausses. Ils ont été revérifiés sur l'arbre courant, après task-372 et task-373.

| affirmation à l'écran | réalité dans le code | preuve |
|---|---|---|
| « reels **et publications photo** Instagram » (`plan.includes.capture.links`) | une publication photo échoue en `IMAGE_POST_UNSUPPORTED` : « no OCR/vision pipeline exists » | `workers/instagram_ingestion_worker.py:19,365`, `core/models/failure_codes.py:44` |
| « les TikToks … ne coûtent rien du tout : ils ne sont pas transcrits » (`plan.legend.free`) | vrai seulement si yt-dlp trouve des sous-titres natifs ; sinon Deepgram et débit de la **durée réelle** via `gate_audio_transcription` | `workers/tiktok_ingestion_worker.py:1017`, `core/services/audio_quota_gate.py` |
| « publications X » sans réserve | **texte du post uniquement** ; une vidéo attachée n'est pas traitée en V1 | `workers/x_ingestion_worker.py:1-9`, `docs/INGESTION_WORKERS_PROVIDERS.md` |
| accroche « Save anything worth coming back to… » | **codée en dur en anglais**, servie identiquement aux onze locales | `mobile/app/paywall.tsx:291-294` |
| suffixe de période `/mo` sur chaque prix | **codé en dur en anglais** lui aussi | `mobile/app/paywall.tsx:473` |
| aucune mention de WhatsApp | `SourcePlatform.WHATSAPP` existe, le partage texte **et** la note vocale Opus sont implémentés, `share.whatsappText` est traduit dans les onze catalogues | `core/media_ingestion/domain.py:39`, `mobile/src/types/sharedContent.ts:59,71`, `docs/whatsapp-share-payload-shapes.md` |

**Deux défauts ont disparu pendant la rédaction de ce benchmark, et n'ont donc pas à être traités par task-377 :** l'écran promettait « Organisez en collections **et en tags** » (`plan.highlight.organise`) et « Classez n'importe quoi en collections et en tags » (`plan.includes.organise.file`). task-372 a supprimé les tags de bout en bout et task-373 a renommé « collection » en « dossier » : les deux clés disent aujourd'hui « Organisez en **dossiers**, cherchez dans tout, digest quotidien » et « Classez n'importe quoi en **dossiers**, au moment de l'enregistrer ou plus tard ». Les clés `plan.legend.collections` et `plan.includes.generate.collection` s'appellent désormais `plan.legend.folders` et `plan.includes.generate.folder`. **Aucune recommandation de ce README ne s'appuie sur les tags**, et le vocabulaire retenu au §4 emploie « dossier » au sens de task-373.

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

Et ce que l'écran montre à tort, sur l'arbre courant : les publications photo Instagram (le worker les refuse), « les TikToks ne coûtent rien du tout » (faux dès qu'il n'y a pas de sous-titres natifs), et les publications X sans préciser « texte seulement ».

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

Trois pages successives dans le même écran modal : (1) ce que fait l'app, (2) ce que vous pouvez envoyer, (3) les prix.

```
   page 1 / 3              page 2 / 3              page 3 / 3
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ ✕            │        │ ✕        ← │          │ ✕        ←   │
│              │        │              │        │              │
│  [pictogramme]│       │ VOUS ENVOYEZ │        │ ○ Reader 3 € │
│              │        │ ┌────┐┌────┐ │        │ ● Mix    5 € │
│ Tout ce que  │        │ │YT  ││TikT│ │        │ ○ Audio  9 € │
│ vous partagez│        │ └────┘└────┘ │        │              │
│ devient du   │        │ ┌────┐┌────┐ │        │ Renouvelé …  │
│ texte.       │        │ │Spot││What│ │        │ CGU · Confid.│
│              │        │ └────┘└────┘ │        │              │
│   ● ○ ○      │        │   ○ ● ○      │        │   ○ ○ ●      │
├──────────────┤        ├──────────────┤        ├──────────────┤
│ [ Suivant  ] │        │ [ Suivant  ] │        │ [Commencer ] │
└──────────────┘        └──────────────┘        └──────────────┘
```

**Référence** : RevenueCat, gabarit « Multipage flow » (`revenuecat.com/docs/tools/paywalls`) — l'une des deux seules formes que le fournisseur nomme. **Écarté** : il déplace le prix hors du premier écran, alors que l'écran est atteint depuis une ligne « Gérer l'abonnement » — l'utilisateur qui vient là **sait déjà** qu'il s'agit de payer, et lui faire traverser deux pages avant le chiffre allonge le chemin au lieu de le raccourcir. Le grief de l'owner est « trop lent à lire » : trois pages, ce sont deux gestes de plus, pas moins. Il ajoute en prime un état de navigation interne à un écran qui doit rester lisible dans les trois états de chargement (§7.5).

### 3.4 Parti pris D — garder le dépliant, le raccourcir

On conserve `paywall-includes-toggle` et on réécrit les cinq sections de `buildPlanIncludes` en deux.

```
├─────────────────────────────────────────┤
│ INCLUS DANS CHAQUE FORMULE              │
│ • Enregistrez depuis n'importe quelle   │
│   app : YouTube, podcasts, TikTok…      │
│ • Lisez le texte intégral, traduit      │
│ • Générez résumés et notes              │
│ • Organisez en dossiers, cherchez       │
│                                         │
│   Voir exactement ce qui est inclus  ▾  │  ← le dépliant reste
├─────────────────────────────────────────┤
│  (déplié) Ce que vous pouvez envoyer    │
│  Partagez un lien depuis n'importe      │
│  quelle app, ou collez-le : vidéos      │
│  YouTube, épisodes de podcast depuis    │
│  Apple Podcasts, Spotify, Deezer ou …   │  ← toujours de la prose
│  (déplié) Ce que comptent les minutes   │
│  L'audio et la vidéo comptent leur …    │
└─────────────────────────────────────────┘
```

**Écarté** : c'est exactement l'arbitrage que la description demande de **rejuger**. Le commentaire d'en-tête de `planCopy.ts` justifie le dépliant par « the wall of text every paywall study says nobody reads » — le raisonnement est juste et la conclusion fausse : la réponse à « personne ne lit un mur de texte » n'est pas « cachons le mur », c'est **« n'écrivons pas un mur »**. Une pastille `YouTube` n'est pas du texte à lire, c'est un objet à reconnaître. Aucune des cinq références consultées ne met sa liste de capacités derrière un dépliant. Et D ne corrige aucun des défauts d'exactitude du §1.4 : la prose reste écrite à la main dans onze catalogues, donc elle redérivera.

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


---

## 4. Lexique de remplacement, onze locales (AC#4)

### 4.1 Le principe : supprimer le nom de l'unité, pas lui chercher un synonyme

Chercher un synonyme de « transcription » est une impasse : tout candidat est soit du jargon (« mise en texte », « speech-to-text »), soit un néologisme qu'il faut inventer dans onze langues, soit faux (le quota paie aussi la lecture des documents, qui ne sont pas « transcrits »).

La sortie est grammaticale. Aujourd'hui la carte écrit **« 5 h *de transcription* »** : elle nomme le procédé pour qualifier une quantité de temps. Google One écrit **« Standard (200 GB) »**, pas « 200 GB of file storage and photo backup » — la carte porte la **quantité**, et ce que la quantité achète se dit **ailleurs**, une fois. Le parti pris A rend ce déplacement possible parce qu'il pose juste dessous un tableau de coût de quatre lignes qui répond, chiffre à l'appui, à « une heure, ça me paie quoi ? ».

Conséquence : **le mot « transcription » n'a pas de remplaçant, il a un emplacement en moins**. Les neuf clés qui le portent aujourd'hui dans chaque locale (`paywall.selectorLabel`, `paywall.subtitle`, `plan.card.allowance`, `plan.highlight.read`, `plan.includes.organise.search`, `plan.includes.read.transcripts`, `plan.includes.read.translation`, `plan.legend.free`, `plan.minutesRule`) se réduisent à deux emplacements dans la refonte, et ces deux-là n'en ont pas besoin.

### 4.2 Le lexique, dérivé des catalogues plutôt qu'inventé

Chaque ligne indique d'où vient la formulation. **« repris »** = la chaîne existe déjà dans le catalogue de cette locale, à la clé citée ; **« nouveau »** = formulation proposée, à relire par un locuteur avant intégration par task-377.

**a) `plan.card.allowance` — « {duration} de transcription » → la quantité seule.** Repris de `paywall.pricePerMonthA11y`, qui porte déjà « par mois » dans les onze catalogues.

| locale | proposé | origine |
|---|---|---|
| en | `{duration} per month` | repris de `paywall.pricePerMonthA11y` |
| fr | `{duration} par mois` | repris |
| es | `{duration} al mes` | repris |
| de | `{duration} pro Monat` | repris |
| it | `{duration} al mese` | repris |
| pt | `{duration} por mês` | repris |
| nl | `{duration} per maand` | repris |
| ja | `毎月 {duration}` | **nouveau** — le catalogue porte `月額 {price}`, qui est monétaire ; pour une durée il faut `毎月` |
| zh | `每月 {duration}` | repris |
| ar | `{duration} شهريًا` | repris |
| hi | `हर महीने {duration}` | **nouveau** — le catalogue porte `{price} प्रति माह` (postposé, registre financier) ; antéposé se lit mieux sur une carte |

**b) « ce que le temps achète » — la phrase unique, sous les cartes.** Le fragment « audio et vidéo » existe déjà, traduit, dans `plan.minutesRule` des onze catalogues : il est **repris tel quel**, ce qui rend cette ligne gratuite à traduire.

| locale | fragment déjà traduit dans `plan.minutesRule` |
|---|---|
| en | `audio and video` |
| fr | `l'audio et la vidéo` |
| es | `el audio y el vídeo` |
| de | `Audio und Video` |
| it | `l'audio e il video` |
| pt | `o áudio e o vídeo` |
| nl | `de audio en video` |
| ja | `音声と動画` |
| zh | `音频和视频` |
| ar | `الصوت والفيديو` |
| hi | `ऑडियो और वीडियो` |

**c) « import » → « envoi ».** « Import » est un mot d'informaticien ; l'utilisateur *partage* ou *envoie*. Le verbe « partager » est déjà traduit onze fois dans `plan.includes.capture.links` (« Partagez un lien depuis n'importe quelle app », « Deel een link vanuit elke app », « 从任意应用分享链接 »…).

| locale | actuel (`plan.card.perImport`) | proposé | statut |
|---|---|---|---|
| en | `up to {duration} in one import` | `up to {duration} at a time` | nouveau |
| fr | `jusqu'à {duration} par import` | `jusqu'à {duration} par envoi` | nouveau |
| es | `hasta {duration} por importación` | `hasta {duration} por envío` | nouveau |
| de | `bis zu {duration} pro Import` | `bis zu {duration} pro Sendung` | nouveau |
| it | `fino a {duration} per importazione` | `fino a {duration} per invio` | nouveau |
| pt | `até {duration} por importação` | `até {duration} por envio` | nouveau |
| nl | `tot {duration} per import` | `tot {duration} per keer` | nouveau |
| ja | `1 回の取り込みで最大 {duration}` | `1 回あたり最大 {duration}` | nouveau |
| zh | `单次导入最多 {duration}` | `每次最多 {duration}` | nouveau |
| ar | `حتى {duration} في الاستيراد الواحد` | `حتى {duration} في كل مرة` | nouveau |
| hi | `एक इम्पोर्ट में {duration} तक` | `एक बार में {duration} तक` | nouveau |

**d) « minutes ».** À conserver **comme unité** (« 1 min par 5 pages » est une valeur, pas du jargon), à supprimer **comme nom de monnaie** : « vos minutes », « ce que comptent les minutes mensuelles » personnifient un budget que personne n'a demandé. Le tableau de coût du §3.1 n'a pas de titre du genre « Ce que comptent les minutes » ; il a un titre qui promet un renseignement — « Ce que ça consomme ».

**e) « formule » (fr) / « plan » (en).** **À conserver.** Ce n'est pas du jargon : c'est le mot des deux stores (`Subscriptions` chez Apple comme chez Google) et celui des références (Google One « plans », Spotify « plans »). En revanche il apparaît aujourd'hui dans quatre clés (`paywall.title`, `plan.badge.yourTrial`, `paywall.ctaChoose`, `account.plan.heading`) ; la refonte n'en garde qu'une, le titre.

**f) « essai ».** **À conserver, et à ne jamais écrire côté store.** Le mois offert sur `Mix` est accordé **côté serveur par ancienneté de compte** (`free_trial` dans `pricing_config_service.py`, lu par `quota_enforcer._is_free_trial_active`) : ce n'est pas une *introductory offer* App Store. `docs/store-listing/app-store-connect.md` § « Do NOT add an introductory offer » explique pourquoi en ajouter une distribuerait un second mois gratuit, celui-là facturé. Côté Play, la contrainte est symétrique et documentée : les **Benefits** d'un abonnement ne doivent mentionner ni prix ni essai gratuit.

### 4.3 Coût du désalignement avec les fiches store, chiffré

Les Display Names et Descriptions d'abonnement d'App Store Connect sont **visibles par l'acheteur** — feuille d'achat système et Réglages → Abonnements (`docs/store-listing/app-store-connect.md`). Si l'app cesse de dire « transcription » et que la fiche continue, l'acheteur lit dans la feuille d'achat un mot qu'il n'a vu nulle part dans l'app.

| surface | ce qui porte « transcription » | volume à modifier | remarque |
|---|---|---|---|
| **App Store Connect — Description d'abonnement** | les 3 produits × les localisations | **39 champs** = 3 abonnements × **13 entrées** | Apple n'a **ni espagnol ni portugais génériques** : `Spanish (Spain)` *et* `Spanish (Mexico)`, `Portuguese (Brazil)` *et* `Portuguese (Portugal)`, sinon les vitrines latino-américaines retombent sur l'anglais |
| **App Store Connect — Display Name** | rien | **0** | `Reader`, `Mix`, `Audio-Heavy` : noms de produit, jamais traduits |
| **Google Play — Subscription Name / Benefits** | rien à ce jour | **0** | `docs/store-listing/google-play-store.md` n'a **aucune section abonnements** : les Name et Benefits ne sont pas encore rédigés. Rien à désaligner, mais tout à écrire avec le lexique retenu |
| **Google Play — Full Description de la fiche** | 2 passages, anglais uniquement | **2 phrases** | `google-play-store.md:36` « AI-Powered Transcription: … » et `:62` « Audio and video transcription is available on paid plans » |

**Total : 41 champs**, dont 39 plafonnés à 45 caractères. Aucun ne déclenche de re-soumission à la revue : une localisation d'abonnement se modifie locale par locale sans repasser en revue.

Formulation proposée pour la Description, dans la forme à deux moitiés que l'owner a arrêtée le 2026-09-02 (« illimité » + la quantité) — elle est **plus exacte** que l'actuelle, parce qu'un PDF lu pour son texte est mis en texte sans être « transcrit », et elle **raccourcit** la ligne espagnole qui frôlait les 45 caractères :

| locale | proposé (exemple Audio-Heavy) | longueur |
|---|---|---|
| en | `Unlimited articles + 12 h turned into text.` | 43 |
| fr | `Articles illimités + 12 h mises en texte.` | 41 |
| es | `Artículos ilimitados + 12 h en texto.` | 37 |
| de | `Unbegrenzte Artikel + 12 Std. als Text.` | 39 |
| it | `Articoli illimitati + 12 h in testo.` | 36 |
| pt | `Artigos ilimitados + 12 h em texto.` | 35 |
| nl | `Onbeperkte artikelen + 12 u als tekst.` | 38 |
| ja | `記事は無制限、12 時間をテキスト化。` | 18 |
| zh | `文章不限量，12 小时转成文字。` | 15 |
| ar | `مقالات بلا حدود + 12 ساعة نصًا.` | 31 |
| hi | `असीमित लेख + 12 घंटे टेक्स्ट में।` | 33 |

Longueurs comptées en caractères Unicode. **La seule vérification qui fait foi reste l'acceptation par le formulaire**, et l'agent n'a pas accès à la console.

### 4.4 Chemins de menus exacts, dans l'UI actuelle des deux consoles

**App Store Connect** — relevé le 2026-09-07. Les liens profonds de l'aide Apple répondent **404** depuis cet environnement (Apple a réorganisé `/help/app-store-connect/`) ; le début de la chaîne est celui déjà consigné dans `docs/store-listing/app-store-connect.md`, la fin vient du guide tiers cité en §10.

1. **My Apps** → sélectionner l'app.
2. Dans la barre latérale, sous **Monetization**, cliquer **Subscriptions**.
3. Cliquer le nom du **groupe d'abonnements** (`Second Brain Plans`).
4. Cliquer le **reference name** de l'abonnement (`Reader`, `Mix` ou `Audio-Heavy`).
5. Faire défiler jusqu'à la section **App Store Localization**.
6. Ajouter une locale : bouton **+** à droite du titre de section → choisir la région dans le menu déroulant → remplir **Display Name** (≤ 30) et **Description** (≤ 45) → **Add**. Modifier une locale existante : cliquer son nom dans la liste et éditer ; la modification s'enregistre sans « Save » de l'abonnement.
7. Répéter pour les trois abonnements et les treize entrées.

**Piège documenté à ne pas déclencher** : si l'abonnement a été ajouté à une soumission en cours, il passe en `Ready for Review` et **seuls** reference name, tarification et disponibilité restent modifiables. Pour rouvrir l'édition : **App Review → Submissions → la soumission → Cancel Submission → Confirm** (`docs/store-listing/app-store-connect.md:195-200`).

**Google Play Console** — relevé le 2026-09-07 sur la page d'aide officielle.

1. **Monetize with Play → Products → Subscriptions**.
2. **Create subscription** pour un nouvel abonnement, ou la **flèche droite** à côté d'un abonnement existant.
3. **Edit subscription details**.
4. **Name** — « A short name for your subscription of up to 55 characters. Users will see this in emails and the subscription center. » **C'est le seul champ vu par l'acheteur** dans ce bloc.
5. **Description** — « This is for your own internal use; it is not shown to users on Google Play. » Donc **aucun enjeu de vocabulaire**.
6. **Benefits** — bouton **+ Add benefit**, **jusqu'à 4**, **40 caractères chacun**, sans prix ni mention d'essai gratuit. C'est là que le lexique compte côté Play.
7. **Save changes**. Les tarifs vivent sous **Add base plan** ou dans le base plan existant, jamais dans ce bloc.

---

## 5. Logos de plateformes tierces sur un écran d'achat (AC#5)

**Tranché : non. Des noms, jamais des logos.** Ce n'est pas une prudence de principe, c'est ce que disent les règles, et quatre des marques concernées l'interdisent explicitement dans la configuration exacte qui nous intéresse — une rangée de logos concurrents sur un écran qui vend un abonnement.

| marque | ce que dit sa règle | effet ici |
|---|---|---|
| **Apple / Apple Podcasts** | tout logo appartenant à Apple exige « an express written trademark license » ; le nom en mot seul est toléré à titre référentiel, « less prominent than the product name » et sans laisser croire à un partenariat. La licence marketing de l'App Store (EA0861) ne couvre **que** le badge et l'icône App Store, et ne mentionne jamais Apple Podcasts | **logo interdit sans licence**, nom autorisé en texte référentiel |
| **TikTok** | « You may not use TikTok logos, icons, symbols, or designs, without our prior written permission » | **logo interdit** |
| **WhatsApp** | « DON'T combine the WhatsApp name or logos … with any other logo, company name, mark, or generic terms » ; la marque ne doit jamais être « the most distinctive or prominent feature » | **logo interdit dans une rangée**, ce qui est exactement une vitrine |
| **Instagram / Meta** | interdit ce qui « Implies partnership, sponsorship or endorsement », ce qui « Makes the Instagram brand the most distinctive or prominent feature », et « Don't mention other social networks in the same spot as Instagram and/or Facebook » | **la dernière phrase disqualifie la rangée de logos**, et n'interdit pas une liste de sources techniques en texte |
| **Spotify** | « Don't use the Spotify brand together with any other brand or in any co-branded communications. Pairing of brands is not permitted under our Developer Terms. » et « Spotify content should never be seated next to content from similar services. » | **logo interdit à côté d'Apple Podcasts et de Deezer**, ce qui est la définition d'une vitrine podcast |
| **YouTube** | les ressources de marque n'ont pas pu être récupérées depuis cet environnement (redirection 301 vers `brand.youtube`, contenu limité aux vignettes) — **non vérifié**, voir §9 | prudence : nom seulement |
| **X** | brand toolkit et « developer display requirements » renvoient **HTTP 402 Payment Required** — **non vérifié**, voir §9 | prudence : nom seulement |

**Côté stores**, l'accroche est la guideline **5.2.1** d'Apple : « Don't use protected third-party material such as trademarks, copyrighted works … in your app without permission ». Deux autres guidelines sont souvent invoquées à tort ici et ne s'appliquent pas : **2.3.7** encadre les *métadonnées* de la fiche (« reference other apps »), pas le contenu d'un écran ; **4.1(c)** encadre l'*icône* et le *nom* de l'app.

**Ce qui reste permis, et que le parti pris A utilise :** citer les marques **en texte**, à titre descriptif, dans une taille uniforme, sans hiérarchie de mise en avant entre elles, sans typographie ni couleur propriétaire, et sans jamais suggérer un partenariat. C'est ce que fait déjà `plan.includes.capture.links` aujourd'hui — la refonte ne dégrade donc pas la position juridique, elle la conserve en changeant seulement la forme visuelle (pastilles au lieu d'une phrase).

**Conséquence de conception, à ne pas contourner par une astuce :** remplacer un logo par un pictogramme « qui y ressemble » (une note de musique pour Spotify, une bulle verte pour WhatsApp) est **pire** qu'un logo, parce que c'est une imitation. Les pastilles portent du texte, et rien d'autre. Si un signe visuel est souhaité, il doit être **générique et propre au produit** (une même icône « lien » pour toutes les plateformes, une icône « fichier » pour les formats), jamais dérivé d'une marque.

---

## 6. Empêcher la liste de redevenir fausse (AC#6)

### 6.1 Pourquoi elle est fausse aujourd'hui

La liste des plateformes est de la **prose, retapée onze fois**. `plan.includes.capture.links` énumère des marques dans une phrase, dans chacun des onze catalogues ; rien ne la relie au classifieur qui décide réellement. Résultat mesurable : l'écran vend les publications photo Instagram, que le worker refuse (`IMAGE_POST_UNSUPPORTED`), et ne vend ni WhatsApp, ni `music.youtube.com`, ni `twitter.com`, ni les liens courts TikTok, ni l'URL audio directe. C'est la même mécanique que la dérive de task-299 : une information dupliquée à la main dérive dès que le code bouge.

### 6.2 Le mécanisme : la vitrine devient de la donnée, pas de la prose

**La liste des plateformes est servie par le backend, dérivée de la table qui décide déjà de l'acceptation.** Concrètement : une capacité par entrée, portant l'identifiant `SourcePlatform`, le libellé d'affichage (un nom propre, donc invariant par locale), le groupe d'appartenance, et le régime de coût. La source de vérité est la même table d'hôtes et de prédicats que `RuleBasedUrlClassifier` applique (`core/media_ingestion/adapters/classifiers.py`), plus `DocumentFormat.supported_extensions()` et les listes d'extensions audio pour les fichiers.

Trois propriétés en découlent :

1. **Compatible avec la règle d'en-tête de `planCopy.ts`** — « no figure is written here ». Le mobile n'écrit ni chiffre, ni prix, ni liste : il **affiche** ce qu'on lui sert, exactement comme il affiche les allocations de `GET /api/pricing` et les prix du package store. La règle n'est pas contournée, elle est étendue d'un cran.
2. **Coût i18n nul pour la partie qui dérive.** `YouTube`, `Spotify`, `WhatsApp`, `PDF`, `M4A` ne se traduisent pas — le catalogue `ar.ts` les écrit déjà en caractères latins. Seuls restent dans les onze catalogues les **trois intitulés de groupe** (« ce que vous pouvez envoyer », « fichiers », « ce que ça consomme ») et la phrase de promesse. On passe d'environ **douze phrases × onze locales** à **quatre clés × onze locales**.
3. **La dérive devient une erreur, pas un oubli.** Un nouveau membre de `SourcePlatform` absent de la table de capacités doit faire échouer une vérification côté backend — c'est la contrepartie qui donne sa valeur au mécanisme, et elle est atteignable par l'agent qui implémentera (une assertion d'exhaustivité sur l'énumération, vérifiable par `mypy`/`ruff` et par un appel réel à l'API `-dev`).

### 6.3 Ce que le mécanisme ne doit pas faire

- **Ne pas servir de texte marketing depuis le backend.** Ce qui traverse est un **nom propre** et un **identifiant**, pas une phrase à traduire. Sinon on recrée le problème ailleurs, sans le type `Catalog` pour le rattraper.
- **Ne pas rendre l'écran dépendant d'un second appel réseau.** La vitrine se sert de la charge utile que l'écran demande déjà pour les allocations, sinon elle introduit un quatrième état de chargement — ce que l'AC#7 interdit.
- **Ne pas dupliquer la table côté mobile « pour le mode hors-ligne ».** `AGENTS.md`, « Nothing is deployed yet » : pas de couche de compatibilité, pas de repli qui redevient la source de vérité par accident.

---

## 7. Tenue en langue, en RTL, en accessibilité, et invariants (AC#7)

### 7.1 375 pt, l'arithmétique

Largeur de contenu `375 − 2 × Spacing.lg = 327` pt. Une pastille est un `Text` en `Typography.label` (14 pt) dans une boîte à `Spacing.sm` de marge intérieure horizontale de chaque côté, soit **32 pt** de chrome. Pour une chaîne latine, ≈ 7,5 pt par caractère à 14 pt.

| pastille la plus large de sa catégorie | caractères | largeur estimée | tient en 327 pt ? |
|---|---|---|---|
| `Apple Podcasts` | 14 | ≈ 137 pt | oui |
| `Articles & pages web` (fr) | 20 | ≈ 182 pt | oui |
| `Sprachnachricht` (de, si un libellé générique est retenu) | 15 | ≈ 145 pt | oui |
| `PDF DOCX PPTX XLSX` | 18 | ≈ 167 pt | oui |
| `MP3 M4A WAV FLAC AAC OGG Opus` | 29 | ≈ 250 pt | oui |

Aucune pastille ne peut déborder, et la propriété structurelle compte plus que les chiffres : **une pastille trop large prend sa propre ligne** au lieu de tronquer, parce que le conteneur est en `flexWrap: "wrap"` et que la pastille n'a **pas** de `numberOfLines`. C'est l'inverse du comportement actuel de `tierName`, plafonné à `numberOfLines={1}` : à la plus grande taille Dynamic Type, `Audio-Heavy` s'y tronque déjà.

### 7.2 Arabe, RTL

Le défaut existe et il est visible dans le dépôt : `ar.ts:221` enchâsse huit noms latins dans une phrase RTL et la conjonction se colle au nom — `وReels`, `وSpotify`, `وSpotify أو Deezer`. C'est le comportement attendu de l'algorithme bidi quand un run LTR démarre au milieu d'un run RTL sans caractère de séparation fort.

La vitrine par pastilles supprime la cause : **une pastille = un nœud `Text` = un seul run bidi**, sans voisin à réordonner. Trois précautions pour l'implémentation, toutes déjà pratiquées dans `paywall.tsx` :

- `flexDirection: "row"` est **auto-inversé** par React Native sous RTL ; ne pas le forcer.
- Marges et rembourrages en `marginStart` / `marginEnd` / `paddingStart` / `paddingEnd`, jamais `Left`/`Right`.
- `textAlign: I18nManager.isRTL ? "left" : "right"` pour la colonne de valeurs du tableau de coût — exactement ce que fait déjà `tierPrice`.

Le tableau de coût a un piège propre : **le remplissage en pointillés entre le libellé et la valeur ne doit pas être une chaîne de `·`**, qui se réordonne sous RTL. C'est une bordure ou un fond, pas du texte. Structure : libellé en `flex: 1`, valeur en `flexShrink: 0`.

### 7.3 Allemand et néerlandais

Les langues à mots longs cassent les **grilles** et les **phrases justifiées**, pas les listes qui se replient. C'est la raison principale d'écarter le parti pris B (§3.2) : quatre colonnes sur 327 pt laissent ≈ 60 pt par colonne, ce qu'aucun libellé allemand ne respecte. Dans le parti pris A, un mot long élargit **sa propre pastille** et se replie sur la ligne suivante ; il n'entraîne rien d'autre. Le seul texte véritablement libre est la phrase de promesse, sur deux lignes en anglais et probablement trois en allemand — un budget d'une ligne supplémentaire, pas un débordement.

Contrainte à rappeler à l'implémentation : les intitulés de groupe (« CE QUE VOUS POUVEZ ENVOYER ») en capitales et lettrage espacé sont **la** forme qui déborde le plus vite en allemand. `Was Sie senden können` en `Typography.small` (13 pt) avec `letterSpacing` tient ; en `Typography.label` avec un `letterSpacing` généreux, non. À vérifier sur simulateur.

### 7.4 VoiceOver

Les cartes portent déjà `accessibilityRole="radiogroup"` (`paywall.tsx:396`) et un libellé de prix dédié (`paywall.pricePerMonthA11y`). Deux ajouts sont nécessaires, sinon la vitrine dégrade l'expérience au lieu de l'améliorer :

- **La vitrine doit être un seul élément accessible**, avec un libellé unique construit par jointure de la même liste servie par le backend. Treize pastilles = treize arrêts de balayage sinon.
- **Chaque ligne du tableau de coût est un élément accessible** portant « libellé, valeur », pas deux arrêts distincts.

### 7.5 Ce qui ne bouge pas — vérification ligne à ligne

| exigence | comment le parti pris A la tient |
|---|---|
| prix issus uniquement du package store | les cartes lisent toujours `pkg.product.priceString` / `.price` / `.currencyCode` ; la refonte ne touche pas la source. Le suffixe `/mo` codé en dur (`paywall.tsx:473`) devient une clé traduite — c'est un gain, pas un risque |
| aucune figure écrite côté mobile | allocations et plafonds restent interpolés depuis `GET /api/pricing` ; les quatre valeurs du tableau de coût viennent de `unit_conversion`, aucune n'est écrite dans `mobile/` |
| conditions de renouvellement dès que l'achat est possible | `legalBlock` reste sous les blocs de contenu et rend `paywall.renewalTerms` sous `canPurchase`, inchangé |
| liens CGU et confidentialité dans le binaire, sur l'écran d'achat | inchangés, même emplacement |
| aucun bouton « Restaurer les achats » | la refonte n'en ajoute pas. task-336 l'a retiré ; le commentaire du bloc légal rappelle que l'espacement actuel vient de son absence — l'implémentation ne doit pas « rétablir » cet espace par un bouton |
| aucun claim non vérifiable | la vitrine ne dit que des noms de plateformes vraies ; le tableau de coût ne dit que des conversions issues de la config. La seule mise en avant est `paywall-recommendation`, déjà calculée sur l'usage réel, jamais « le plus populaire » |
| trois états de chargement distincts | inchangés et **non augmentés** : `isLoading` → spinner ; `!hasPlans` → `paywall-pricing-error` ; `!canPurchase` → `paywall-store-notice` + `paywall.selectorLabelReadOnly`. La vitrine et le tableau de coût vivent **à l'intérieur** de la branche `hasPlans`, comme le reste du contenu, donc aucun quatrième état n'apparaît |

Un point d'attention pour l'implémentation, pas un blocage : dans l'état `!canPurchase`, la vitrine reste pertinente (elle ne dépend pas du store) mais la CTA disparaît déjà. L'écran doit rester lisible sans pied de page collant.

---

## 8. Un écran ou deux (AC#8)

**Tranché : deux écrans, avec la frontière déplacée.** Le nombre d'écrans ne change pas ; ce qui change, c'est ce que chacun porte.

### 8.1 La répartition retenue

| surface | ce qu'elle porte | ce qu'elle ne porte plus |
|---|---|---|
| **Onglet Compte** — `SubscriptionStatusCard` (`account.tsx:192`) | l'**état** : formule en cours, minutes restantes, date de recharge, statut d'essai, et **une** ligne d'action neutre vers l'offre | rien à retirer, mais c'est elle qui devient la « gestion de l'abonnement » au sens propre |
| **`/paywall`** | l'**offre** : les trois cartes, la vitrine, le tableau de coût, le mobilier de store et la CTA | plus rien qui ressemble à de la consultation d'état |

### 8.2 Pourquoi pas un seul écran

Quatre raisons, dans l'ordre de force.

1. **Le mobilier de store n'a rien à faire sur un écran de consultation.** Conditions de renouvellement, CGU et confidentialité doivent être présents sur l'**écran d'achat**. Les fusionner dans l'onglet Compte les affiche à chaque visite d'un abonné qui vient juste voir ses minutes.
2. **Le prix doit rester au-dessus du pli.** Un écran unique commencerait par une jauge d'usage, ce qui repousse les trois cartes plus bas que la position mesurée au §1.3. Le grief « trop lent à lire » s'aggraverait.
3. **Changer de formule est un achat.** Apple traite un passage d'un abonnement à l'autre dans un même groupe comme une transaction (guideline 3.1.2(b)) : l'écran qui déclenche cette transaction est un écran d'achat et doit ressembler à un écran d'achat.
4. **La surface de consultation doit fonctionner quand l'achat est impossible.** Sur `canPurchase === false`, `/paywall` bascule en lecture seule ; l'onglet Compte, lui, doit continuer à afficher des minutes et une date. Séparer les deux évite d'entrelacer ces conditions.

### 8.3 Conséquences sur le chemin de navigation

- La ligne `account-upgrade-button` (`account.tsx:201-206`, `router.push("/paywall")`) **reste**, avec ses trois paires de libellés selon l'état (`account.subscription.manage` / `upgrade` / `viewPlans`, plus les `*Hint`).
- Elle change de promesse : elle n'ouvre plus « la gestion de l'abonnement », elle ouvre **les formules**. Le libellé `manage` devient donc le moins juste des trois et doit être revu par task-377 en même temps que le reste du lexique — le mot « gérer » désigne désormais ce que fait la carte au-dessus, pas ce que fait la destination.
- **Aucune route nouvelle, aucune route supprimée.** `/paywall` reste atteint depuis un seul point.
- La règle d'en-tête tient : les deux écrans lisent le même `planCopy.ts`, donc la règle des minutes affichée sous la jauge et le tableau de coût du paywall ne peuvent pas se contredire — à condition que le tableau de coût soit **construit dans `planCopy.ts`**, pas dans `paywall.tsx`.

---

## 9. Ce qui n'a pas pu être vérifié depuis cet environnement

Listé explicitement, comme l'AC#3 l'exige. Chaque ligne dit ce qui a échoué, pourquoi, et ce qui a été fait à la place.

| ce qui n'a pas pu être consulté | symptôme observé | conséquence sur ce README |
|---|---|---|
| Ressources de marque **YouTube** | redirection 301 vers `brand.youtube`, dont le contenu servi se limite aux règles de vignettes | la règle YouTube sur les logos n'est **pas** citée ; le tableau du §5 le dit, et la conclusion « noms seulement » ne dépend pas de cette ligne |
| Brand toolkit et **display requirements de X** | **HTTP 402 Payment Required** sur les deux URL | idem : X est traité par prudence, pas par citation |
| Guidelines de marque **légales de TikTok** | la page ne rend qu'un mot, « TikTok » | remplacé par les *design guidelines* développeurs de TikTok, qui portent la phrase citée au §5 |
| Aide **App Store Connect**, liens profonds | **404** sur toutes les URL `/help/app-store-connect/...` essayées (Apple a réorganisé cette section) | le chemin du §4.4 combine la chaîne déjà consignée dans `docs/store-listing/app-store-connect.md` et un guide tiers daté ; **à confirmer en console avant de l'appliquer** |
| RevenueCat, `paywalls-v2/creating-paywalls` et `paywall-design-best-practices` | **404** | seule la page `tools/paywalls` a pu être lue, et elle ne dit rien sur la densité de texte : c'est pourquoi le §3.0 conclut qu'il n'y a **pas d'autorité** à invoquer sur ce point |
| **YouTube Premium** comme référence de mise en page | redirection 302 vers une page de consentement | écarté de la table des références |
| Rendu réel des maquettes | l'agent n'a **ni appareil ni simulateur** | tous les chiffres de mise en page du §1.3 et du §7.1 sont des **estimations calculées**, jamais des mesures. C'est aussi la note de l'owner en fin de description de tâche |
| Acceptation des chaînes de 45 caractères par le formulaire ASC | pas d'accès console | les longueurs du §4.3 sont comptées en caractères Unicode ; seule la console tranche |

---

## 10. Sources

**Implémentations de référence consultées**

- Google One — plans et tarifs : https://one.google.com/about/plans
- Spotify Premium — plans : https://www.spotify.com/premium/
- Apple One : https://www.apple.com/apple-one/
- Readwise Reader — page produit : https://readwise.io/read
- Snipd — tarifs : https://www.snipd.com/pricing

**Éditeurs d'abonnement**

- RevenueCat, Paywalls (« Single screen » / « Multipage flow ») : https://www.revenuecat.com/docs/tools/paywalls
- RevenueCat, State of Subscription Apps 2025 : https://www.revenuecat.com/state-of-subscription-apps-2025/

**Règles de marque**

- Apple, App Store Marketing Guidelines : https://developer.apple.com/app-store/marketing/guidelines/
- Spotify, Design & Branding Guidelines : https://developer.spotify.com/documentation/design
- TikTok, Design Guidelines pour développeurs : https://developers.tiktok.com/doc/getting-started-design-guidelines/
- WhatsApp, Brand Resource Center (Meta) : https://www.meta.com/brand/resources/whatsapp/whatsapp-brand/
- Instagram, Brand Resource Center (Meta) : https://www.meta.com/brand/resources/instagram/

**Règles des stores**

- Apple, App Store Review Guidelines (3.1.2, 2.3.7, 4.1, 5.2.1) : https://developer.apple.com/app-store/review/guidelines/
- Google Play, « Create and manage subscriptions » (chemin de menus, Name/Description/Benefits et leurs limites) : https://support.google.com/googleplay/android-developer/answer/140504
- Ajout d'une localisation d'abonnement dans App Store Connect (guide tiers, faute d'aide Apple accessible) : https://www.delasign.com/blog/app-store-connect-subscription-localizations/

**Sources internes au dépôt** (toutes citées en ligne dans les sections)

`mobile/app/paywall.tsx`, `mobile/app/(tabs)/account.tsx`, `mobile/src/lib/planCopy.ts`, `mobile/src/constants/theme.ts`, `mobile/src/types/upload.ts`, `mobile/src/types/sharedContent.ts`, les onze catalogues de `mobile/src/i18n/`, `media_summarizer/core/media_ingestion/domain.py`, `media_summarizer/core/media_ingestion/adapters/classifiers.py`, `media_summarizer/core/ports/document_parser.py`, `media_summarizer/core/services/quota_enforcer.py`, `media_summarizer/core/services/audio_quota_gate.py`, `media_summarizer/core/services/pricing_config_service.py`, `media_summarizer/core/models/failure_codes.py`, les workers YouTube / TikTok / Instagram / X / PodcastIndex, `docs/INGESTION_WORKERS_PROVIDERS.md`, `docs/whatsapp-share-payload-shapes.md`, `docs/store-listing/app-store-connect.md`, `docs/store-listing/google-play-store.md`, `AGENTS.md`.

---

## 11. Ce que task-377 aura à faire si l'owner retient le parti pris A

Récapitulatif opérationnel, sans code ni maquette rendue.

1. Supprimer `paywall-includes-toggle`, `isDetailOpen`, `buildPlanIncludes`, `buildMinutesLegend` et les clés `plan.includes.*` / `plan.legend.*` devenues inutiles **dans les onze catalogues** — pas de repli, `AGENTS.md` § « Nothing is deployed yet ».
2. Remplacer `buildPlanHighlights` (4 lignes) par une phrase de promesse unique.
3. Ajouter la vitrine de pastilles, alimentée par la liste servie par le backend (§6), et le tableau de coût à quatre lignes construit **dans `planCopy.ts`**.
4. Appliquer le lexique du §4.2, y compris la suppression de « transcription » des neuf clés qui le portent.
5. Traduire les deux chaînes anglaises codées en dur : l'accroche (`paywall.tsx:291-294`) et le suffixe `/mo` (`paywall.tsx:473`).
6. Mettre `docs/store-listing/app-store-connect.md` et `docs/store-listing/google-play-store.md` en accord, et **créer** dans le second la section abonnements qui n'existe pas encore.
7. Ne pas toucher : source des prix, conditions de renouvellement, liens légaux, absence de bouton « Restaurer les achats », les trois états de chargement.

**Deux points qui ne sont pas des ACs et reviennent à l'owner :** la mise à jour des 39 Descriptions d'abonnement dans App Store Connect (chemins au §4.4), et la relecture des formulations marquées « nouveau » au §4.2 par un locuteur de chaque langue concernée.
