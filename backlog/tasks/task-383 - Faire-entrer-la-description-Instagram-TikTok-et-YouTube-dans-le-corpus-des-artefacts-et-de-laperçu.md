---
id: task-383
title: >-
  Faire entrer la description Instagram, TikTok et YouTube dans le corpus des
  artefacts et de l'aperçu
status: To Do
assignee: []
created_date: '2026-09-09 14:58'
updated_date: '2026-09-09 15:42'
labels:
  - backend
  - ingestion
  - artifacts
  - feature
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

La description écrite par l'auteur **est** extraite pour Instagram et TikTok, et n'est même pas lue pour YouTube. Là où elle existe, elle ne sert qu'à fabriquer un titre, puis elle est perdue pour tout ce qui compte.

- **Instagram** : `_extract_caption` lit `item["caption"]` du dataset Apify (`infrastructure/resolvers/instagram_apify_resolver.py:119`), sur la branche reel/IGTV (`:265`) comme sur la branche post (`:345`). Elle alimente `first_sentence(caption)` → titre (`:267`, `:364`), puis est rangée dans `metadata["caption"]` (`:292`, `:361`), qui atterrit dans `job.extraction_metadata["resolver_metadata"]["caption"]` (`workers/instagram_ingestion_worker.py:129`, `:382-389`). **Personne ne relit ce champ.**
- **Instagram, deuxième fuite** : la caption est transmise à Deepgram (`instagram_ingestion_worker.py:456` → `utils/deepgram_dispatch.py:87`), mais `deepgram_worker` ne lit jamais `caption`. Tuyau mort.
- **TikTok** : `select_title([info.get("title"), info.get("description")], …)` (`workers/tiktok_ingestion_worker.py:969-972`). yt-dlp dérive `title` de la description — c'est donc bien la caption qui devient le titre, mais le texte intégral n'est stocké nulle part : aucun des trois constructeurs de métadonnées (`:724`, `:767`, `:618`) ne porte de champ description.
- **YouTube** : rien du tout. `grep -n description workers/youtube_ingestion_worker.py` ne renvoie **aucune** ligne. La description n'est ni lue, ni stockée, ni utilisée pour le titre.
- **Le corpus** que lit le modèle, c'est exclusivement le texte des transcripts S3 : `_download_transcripts` (`workers/artifact_generator/worker.py:84-109`) ne construit qu'un dict `{media_item_id, title, language, published, captured, text}`, et `build_corpus_block` (`workers/artifact_generator/generators/corpus.py:40-78`) n'affiche rien d'autre. La description n'atteint donc ni résumé, ni flashcards, ni quiz, ni notes, ni aperçu.

L'aperçu passe par le même chemin que les artefacts demandés par l'utilisateur : `review_blurb_service.py:94-111` appelle `resolve_scope_sources` → `plan_artifact_generation`, et `review_blurb.py:140` construit son prompt avec `corpus.build_prompt`. **Une seule modification du corpus couvre donc les deux demandes** — il n'y a pas de second pipeline à câbler.

## Ce qu'on veut

La description entre dans le corpus comme un **champ distinct** du transcript, pas fondue dedans : le transcript est affiché tel quel à l'utilisateur dans l'onglet lecteur, et `transcript_markers_instruction()` (`corpus.py:209`) annonce au modèle que les sources sont de la parole transcrite. Y coller du texte écrit contredirait les deux.

**1. La persister sur le job**, là où le service d'artefacts peut la relire. Aucun nouveau champ DynamoDB : `extraction_metadata` est déjà une map libre sur le job, elle porte déjà la caption Instagram, et `deepgram_worker` ne la réécrit jamais (vérifié : ce worker ne touche pas `extraction_metadata`). Restent deux côtés à alimenter :

- **TikTok** : la `description` de `info` doit y être écrite sur les chemins yt-dlp. Sur le repli Apify, l'acteur ne rend qu'un transcript : pas de description à écrire, absence normale.
- **YouTube** : la voie est faite d'acteurs Apify de transcript (`:109`, dialectes `:110-129`), et **aucun des deux ne déclare `title`, `channel` ni `thumbnail` dans son schéma de sortie** — d'où les tuples de graphies `_APIFY_TITLE_FIELDS` / `_APIFY_CREATOR_FIELDS` / `_APIFY_THUMBNAIL_FIELDS` (`:131-141`) sondés par `_apify_item_string`, un miss laissant simplement le champ vide. La description reçoit exactement ce traitement : son propre tuple de graphies, lu dans `_parse_apify_transcript` (`:445-466`) à côté de `title`, puis écrit par `_build_extraction_metadata` (`:607-630`). **Rien ne garantit qu'un acteur en renvoie une** ; l'absence est une issue normale, pas un échec, et le bloc manque alors au corpus.

**2. La faire voyager jusqu'au prompt**, par le chemin que `published`/`captured` ont déjà tracé (task-316 §2.7) : un lecteur normalisé qui rend la description depuis `job.extraction_metadata` quelle que soit la plateforme → un attribut sur `ResolvedSource` (`core/services/artifact_service.py:456-494`) → une clé dans le payload SQS `sources[]` (`:1272-1286`) → le dict de `_download_transcripts` → un bloc dans `build_corpus_block`.

**3. La rendre lisible par le modèle comme ce qu'elle est.** L'en-tête actuel est une ligne `|`-jointe : une description multi-lignes, chargée de hashtags, de liens et d'emojis, n'y tient pas. Il lui faut son propre bloc étiqueté, avant le texte du transcript, et une phrase d'instruction partagée disant ce que c'est — le texte de présentation écrit par l'auteur, à traiter comme du contenu de la source, en sachant qu'il finit souvent sur une salve de hashtags, d'appels à s'abonner, de listes de liens et de chapitres horodatés, qui ne sont pas de la matière.

**4. La compter dans le volume.** `byte_length` (`artifact_service.py:467`, `:552`) est ce qui borne le corpus contre `MAX_FOLDER_CORPUS_TOKENS`, et le worker recompte de son côté (`worker.py:308-316`) sur `source["text"]` seul. Une description présente dans le prompt mais absente des deux comptes, c'est un plafond qui mesure autre chose que ce qui est envoyé. Elle n'est pour autant **pas tronquée** : une coupe arbitraire sectionnerait une phrase, et le plafond existant est le bon endroit pour refuser un corpus devenu trop gros.

## Ce que l'implémenteur n'a pas à chercher

- **Un seul site d'appel** de `resolve_source` : `artifact_service.py:760`, dans `resolve_one`. Il tient déjà le `job`.
- **`prompt_cache_key` (`:1402`) n'a pas à changer.** Il route les 5 requêtes d'une génération vers la même machine ; la description est déterministe pour une source donnée, donc le préfixe partagé reste identique entre les 5 types.
- **Les 5 générateurs n'ont pas à être touchés un par un** : ils appellent tous `corpus.build_prompt`. Le bloc et le fragment d'instruction se posent une fois dans `corpus.py`.
- **X est déjà servi** : le texte du tweet **est** le transcript (`workers/x_ingestion_worker.py:461-462`). Rien à faire de ce côté.
- **Pas de compatibilité à assurer.** Une source déjà ingérée n'a pas de description en base et n'en aura pas : le bloc est simplement absent de son en-tête. Aucun backfill, aucun double format (`AGENTS.md`, « Nothing is deployed yet »).

## Coexistence avec task-145

task-145 (`To Do`) remplace le repli Apify par un proxy résidentiel sur les workers TikTok et Instagram. Pas de dépendance dans un sens ni dans l'autre : les régions touchées diffèrent (constructeurs de métadonnées et appel Deepgram ici, `_start_apify_fallback` là-bas). Si task-145 passe d'abord, la branche Apify de l'AC #1 peut avoir disparu et l'AC est sans objet ; si cette tâche passe d'abord, le chemin proxy de task-145 disposera d'un `info` yt-dlp et devra porter la description comme les autres.

## Hors périmètre

- **Les posts image Instagram** : traités par leur propre tâche, qui dépend de celle-ci.
- **L'exposition de la description dans l'API et l'app** : elle entre dans le prompt, elle ne s'affiche pas dans l'onglet lecteur.
- **La traduction de la description** : `resolve_or_enqueue_translated_transcript` traduit le fichier transcript ; la description reste dans sa langue d'origine et `language_instruction` impose déjà la langue de sortie.
- **L'usage de la description YouTube pour dériver un titre** : le titre YouTube vient déjà de `_APIFY_TITLE_FIELDS` et n'a pas à changer.

## Notes à l'owner (pas des ACs)

1. **La vérification réelle demande un déploiement puis un E2E** : sauver un reel Instagram, un TikTok et une vidéo YouTube sur `-dev`, puis lire l'aperçu et un résumé pour voir si la description y a laissé une trace. L'implémenteur ne peut vérifier que le câblage et le prompt construit.
2. **Une re-soumission de la même URL est bloquée par la dédup** : prévoir un lien neuf, ou rejouer le message SQS.
3. **Côté YouTube, seul un run réel dira si l'acteur configuré renvoie une description** — comme pour le thumbnail, le schéma de sortie ne la déclare pas. Si aucune graphie ne mord, l'information à en tirer est qu'il faut un autre acteur, pas que le câblage est cassé.
4. **La description YouTube est le seul de ces trois champs capable de faire basculer un dossier au-dessus du plafond** (plusieurs milliers de caractères de liens et de chapitres, × 25 sources). Ça se verra par le refus `corpus_too_large` existant, avant tout appel au modèle. Si ça arrive en vrai, la question d'un plafonnement par source se posera — pas avant.
5. **Pour couvrir les deux branches TikTok**, il faut un clip avec sous-titres natifs et un clip sans (repli Deepgram). Le repli Apify ne se déclenche que sur IP-block, que le sentinel E2E de `utils/ingestion_sentinels.py::strip_e2e_force_ip_block_sentinel` sait forcer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le worker TikTok écrit la description de `info` dans `extraction_metadata` sur les deux chemins yt-dlp — sous-titres natifs (`_build_native_extraction_metadata`) et repli Deepgram (`_build_fallback_extraction_metadata`) — sous une clé stable et documentée. Sur le chemin Apify (`_build_apify_native_extraction_metadata`) la clé est absente ou nulle, l'acteur ne rendant qu'un transcript.
- [x] #2 Le worker YouTube sonde la description du dataset Apify par un tuple de graphies connues, sur le motif exact de `_APIFY_TITLE_FIELDS` / `_APIFY_THUMBNAIL_FIELDS` (`youtube_ingestion_worker.py:131-141`) et via `_apify_item_string`, la retourne depuis `_parse_apify_transcript` (`:445-466`) et l'écrit dans `extraction_metadata` (`_build_extraction_metadata`, `:607-630`).
- [x] #3 Un acteur YouTube qui ne renvoie aucune des graphies sondées laisse la description vide sans échec, sans retry et sans log d'erreur — même contrat que le thumbnail absent (`:136-141`). Le commentaire qui accompagne le tuple dit que le schéma de sortie ne la déclare pas.
- [x] #4 Un lecteur unique et normalisé rend la description d'un job quelle que soit la plateforme : la caption Instagram sous `extraction_metadata["resolver_metadata"]["caption"]`, la clé TikTok de l'AC #1 et la clé YouTube de l'AC #2 passent tous par lui. Il rend `None` sur un job sans description, et une chaîne débarrassée de ses espaces de bord sinon.
- [x] #5 `ResolvedSource` porte la description, `resolve_source` la remplit depuis le `job` qu'il tient déjà, et le payload SQS `sources[]` de `_build_generation_message` la transporte à côté de `published` et `captured` (`artifact_service.py:1272-1286`).
- [x] #6 `_download_transcripts` recopie la description dans le dict de source consommé par les générateurs (`workers/artifact_generator/worker.py:94-107`).
- [x] #7 `build_corpus_block` émet la description dans son propre bloc étiqueté — jamais dans la ligne d'en-tête `|`-jointe, qu'une description multi-lignes casserait — placé avant le texte du transcript, et n'émet rien du tout quand la source n'en porte pas. Le docstring de `build_corpus_block` explique le bloc et pourquoi il est distinct du transcript, sur le motif de ce qu'il fait déjà pour `published`/`captured`.
- [x] #8 Un fragment d'instruction partagé dit au modèle ce qu'est ce bloc (texte de présentation écrit par l'auteur, à traiter comme contenu de la source ; hashtags, appels à s'abonner, listes de liens et chapitres horodatés exclus de la matière), sur le motif rédactionnel de `transcript_markers_instruction`. Il est posé une seule fois dans le chemin partagé de `corpus.py`, sans modifier aucun des 5 générateurs ni `review_blurb`.
- [x] #9 Le fragment de l'AC #8 n'est émis que si au moins une source du corpus porte une description : il reste donc identique entre les 5 types d'une même génération, et le préfixe de cache décrit en tête de `corpus.py` est intact.
- [x] #10 Le `byte_length` de `ResolvedSource` inclut les octets de la description, et le recomptage du worker (`worker.py:308-316`) aussi, de sorte que le plafond `MAX_FOLDER_CORPUS_TOKENS` mesure ce qui est réellement envoyé au modèle. La description n'est tronquée nulle part.
- [x] #11 Le tuyau mort est supprimé : les paramètres `caption`, `comments` et `comments_count` de `enqueue_deepgram_transcription` (`deepgram_dispatch.py:49-51`, `:87-89`) et leurs arguments côté Instagram (`instagram_ingestion_worker.py:456-458`) disparaissent — `deepgram_worker` ne les a jamais lus, et le resolver n'a jamais produit de `comments`. Le docstring du worker Instagram (`:17`) ne les mentionne plus.
- [x] #12 `docs/INGESTION_WORKERS_PROVIDERS.md` ne prétend plus que le worker Instagram porte « the caption, the comments, the derived title » jusqu'à Deepgram (`:293`) et dit, pour les trois plateformes, où la description va réellement : `extraction_metadata`, puis le corpus des artefacts et de l'aperçu.

- [x] #13 Une vérification directe contre `-dev` est consignée dans les Implementation Notes : sur au moins un job Instagram réel, `extraction_metadata.resolver_metadata.caption` est bien renseignée en base (`aws dynamodb ... --region eu-west-3` — `AWS_REGION` du shell pointe ailleurs). C'est la prémisse dont dépend le lecteur de l'AC #4.
- [x] #14 `ruff check` et `mypy` passent sur `media_summarizer/`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Le trajet, tel qu'il est câblé

`media_summarizer/core/media_ingestion/source_description.py` est le nouveau module pur qui tient les deux bouts : la clé canonique `SOURCE_DESCRIPTION_KEY = "source_description"`, le normalisateur d'écriture `normalize_source_description`, et le lecteur unique `job_source_description` (AC #4). Le lecteur sonde deux chemins sur `job.extraction_metadata`, dans l'ordre : `source_description` (TikTok, YouTube), puis `resolver_metadata.caption` (Instagram, qui l'écrit là depuis task-266). Il strippe, ne tronque jamais, et rend `None` quand rien ne mord. Une quatrième plateforme = une entrée de tuple ici, rien ailleurs.

Ensuite : `ResolvedSource.description` ← `job_source_description(job)` dans `resolve_source` (le seul site d'appel, il tenait déjà le job) → clé `description` de `sources[]` dans `build_generation_message` → clé `description` du dict de `_download_transcripts` → bloc `--- author description ---` dans `build_corpus_block`.

### Vérification directe contre `-dev` (AC #13)

`aws dynamodb scan --table-name processing_jobs-dev --region eu-west-3` filtré sur `source_platform = "instagram"` : **14 jobs Instagram, dont 10 portent `extraction_metadata.resolver_metadata.caption` sous forme de chaîne non vide** (longueurs relevées : 456, 79 et 1 673 caractères — le contenu n'est pas recopié ici). Les 4 autres sont des jobs en échec dont `resolver_metadata` vaut `NULL`, ce qui est cohérent : le resolver n'a pas produit de métadonnées. La prémisse de l'AC #4 tient donc, et le lecteur trouvera bien quelque chose sur les jobs Instagram existants.

Second relevé, sur le même scan élargi aux 78 jobs de la table : **aucun job ne porte déjà une clé `extraction_metadata.source_description`**. La clé canonique choisie n'entre en collision avec rien en base.

### Le bloc dans le corpus, rendu réel

Layout produit par `build_prompt` sur une source qui porte une description et une qui n'en porte pas :

```
[S1] | title: A | language: fr | captured: 2026-09-09
--- author description ---
Ma recette

#food #paris
--- transcript ---
Bonjour tout le monde.

[S2] | title: B
No desc here.
```

Trois choses à noter. La description ne touche pas la ligne d'en-tête `|`-jointe (AC #7). Le marqueur `--- transcript ---` n'est émis que lorsqu'une description le précède, donc **une source sans description garde exactement la mise en page qu'elle avait avant cette tâche** — pas de bloc vide, pas de marqueur orphelin. Et le fragment d'instruction (`source_description_instruction`) est posé une seule fois, dans `build_prompt`, entre le corpus et les instructions de type : il ne dépend que des sources, donc les 5 types (+ l'aperçu) d'une même génération le portent tous ou aucun (AC #9), et comme il se place *avant* la partie qui varie, il rallonge le préfixe partagé du cache au lieu de le casser. Aucun des 5 générateurs ni `review_blurb` n'a été touché (AC #8), et le commentaire de tête de `corpus.py` sur le préfixe de cache est inchangé.

### Le volume

`ResolvedSource.byte_length` = octets du transcript effectif **+** octets de la description ; le recomptage post-traduction du worker additionne `source["text"]` et `source["description"]`. `MAX_FOLDER_CORPUS_TOKENS` mesure donc ce qui part réellement au modèle (AC #10). Rien n'est tronqué : si un dossier passe au-dessus, c'est le refus `corpus_too_large` existant qui répond, avant tout appel au modèle.

Effet de bord assumé sur le payload SQS : la description voyage en clair (elle n'a pas d'objet S3 à pointer). Les plateformes plafonnent ce qu'elles exposent (5 000 caractères sur YouTube, 2 200 sur Instagram), donc un dossier plein de sources bavardes reste sous la limite de 256 kB de SQS. Le commentaire du payload le dit.

### Le tuyau mort (AC #11)

`caption`, `comments` et `comments_count` sont supprimés de `enqueue_deepgram_transcription` et de son unique appelant Instagram. Vérifié avant suppression : `grep` sur `deepgram_worker.py` ne renvoie aucune occurrence de `caption` ni de `comments`, et aucun test ne référençait ces paramètres. Le resolver n'a d'ailleurs jamais produit de `comments` — l'appelant passait `resolver_metadata.get("comments", [])`, soit toujours `[]`. Pas de couche de compatibilité, suppression dans le même run.

### Documentation

`docs/INGESTION_WORKERS_PROVIDERS.md` : l'affirmation fausse de l'étape 4 d'Instagram est corrigée, et une section transverse « Where the author's description goes (task-383) » donne le tableau des trois plateformes (+ X et le repli Apify TikTok, qui n'en portent pas et pourquoi), le trajet complet et le contrat de tolérance. `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` §6 disait aussi que la caption était « forwarded to Deepgram » : corrigé au même endroit, avec renvoi vers la section canonique.

### Ce qui reste hors de portée de l'implémenteur

Aucun AC n'est resté non coché, mais la **vérification qui compte n'est pas faite** et ne peut pas l'être d'ici : il faut le déploiement (déclenché au push sur `main`, bien après ma sortie) puis un E2E sur `-dev` — sauver un reel, un TikTok et une vidéo YouTube, puis lire l'aperçu et un résumé. Côté YouTube en particulier, **seul un run réel dira si l'acteur configuré renvoie une des quatre graphies sondées** : le schéma de sortie ne déclare pas la description, exactement comme pour le titre et le thumbnail. Si aucune ne mord, la conclusion est qu'il faut un autre acteur, pas que le câblage est cassé. Les notes 1 à 5 de la description de la tâche restent le mode opératoire.

Aucun test automatisé n'a été écrit (règle du projet). Le rendu du prompt ci-dessus a été obtenu par un appel direct et jetable à `corpus.build_prompt`, sans fichier créé.
<!-- SECTION:NOTES:END -->
