---
id: task-392
title: Traiter un article web dont le texte a changé comme un nouveau média
status: Done
assignee: []
created_date: '2026-09-10 12:35'
labels:
  - backend
  - ingestion
  - media_identity
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

La déduplication du pipeline est globale et volontairement inter-comptes (`user_media.list_by_media_key` : *"The GSI is deliberately cross-user: processing is deduplicated globally"*). `media_key` est un SHA-256 de l'URL canonique (`media_identity.generate_media_key`), sans aucune branche par type de source : un article web est donc réutilisé entre comptes exactement comme une vidéo, et le second utilisateur reçoit le texte capturé lors de la première ingestion, sans re-fetch et sans borne de fraîcheur.

C'est acceptable pour une vidéo ou un podcast, dont le contenu ne change pas. Ça ne l'est pas pour une page web, qui peut être réécrite.

## Décision du propriétaire

**Quand le texte d'un article change, c'est un nouveau média.** L'utilisateur qui sauvegarde un article veut le contenu à jour, pas celui capturé six mois plus tôt — et cela vaut aussi bien entre comptes qu'à l'intérieur d'un même compte.

Conséquence directe sur l'ordre du pipeline : pour une source de type article web, **le contenu doit être récupéré avant d'être identifié**, alors que la déduplication se décide aujourd'hui sur l'URL seule, en amont de toute ingestion. Le fetch supplémentaire est du scraping, pas un appel modèle ; son coût est assumé. Deux sauvegardes d'un article inchangé produisent la même empreinte et restent donc mutualisées — l'exclusion porte sur le contenu modifié, pas sur les articles en tant que tels.

## Périmètre

- Identifier explicitement le type de source. Aujourd'hui `canonicalize_media_url` traite YouTube, Instagram, TikTok, X et Spotify par branches dédiées et **tout le reste tombe dans un `else` fourre-tout** : « article web » n'est pas un type reconnu, c'est un défaut de classification. Il faut un critère explicite.
- Faire entrer une empreinte du texte récupéré dans l'identité de contenu d'un article, de sorte qu'un texte différent donne un média différent.
- Un article dont le texte est inchangé continue de réutiliser le contenu déjà traité, entre comptes comme à l'intérieur d'un compte.
- Les sauvegardes existantes ne sont pas migrées : rien n'est déployé en production et un testeur ne détient que le build qu'il a installé.

## Point d'attention pour l'implémenteur

`build_artifact_id` (`artifact_service.py`) hashe les `content_id` des sources, **pas le texte**. Si l'identité de contenu d'un article ne change pas quand son texte change, une demande de résumé après re-fetch retombe sur le même `artifact_id` et se fait répondre `REUSED` : le nouvel article se verrait servir le résumé de l'ancien. C'est le défaut que cette tâche doit rendre impossible.

## Notes au propriétaire (hors critères d'acceptation)

Le comportement ne prend effet qu'après déploiement, qui a lieu au push sur `main`. Vérification manuelle ensuite : sauvegarder une page dont le contenu bouge, la re-sauvegarder après modification, et constater deux médias distincts avec deux textes distincts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le type de source est déterminé explicitement à l'ingestion ; « article web » est un type reconnu et non le cas par défaut d'une chaîne de branches par domaine.
- [x] #2 Pour une source de type article web, le contenu est récupéré avant que l'identité de contenu ne soit arrêtée, et une empreinte du texte récupéré entre dans cette identité.
- [x] #3 Deux sauvegardes d'un article dont le texte a changé produisent deux identités de contenu distinctes ; deux sauvegardes d'un article inchangé produisent la même, que ce soit par le même compte ou par deux comptes différents.
- [x] #4 Une demande d'artefact formulée après un changement de texte ne peut pas être répondue par un artefact généré sur le texte précédent.
- [x] #5 ruff et mypy passent sans erreur sur les modules touchés.
- [ ] #6 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre les deux lignes attendues pour un article modifié entre deux sauvegardes.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Ce qui a changé

**1. Le type de source est décidé une fois, dans `core/services/media_identity.py`.**
Nouvel enum `MediaSourceType` (10 membres) et `classify_source_type(host=, path=)`.
`WEB_ARTICLE` y est un critère explicite — une page http(s) dont l'hôte n'appartient
à aucune plateforme, dont le chemin n'est ni un flux ni un fichier média — et non la
queue d'une chaîne de `elif`. Les tables d'hôtes (`PLATFORM_HOSTS`,
`AUDIO_URL_EXTENSIONS`) sont publiées depuis ce module ; `adapters/classifiers.py`
les consomme au lieu d'en tenir une seconde copie, et ses neuf jeux d'hôtes locaux
plus quatre helpers de chemin ont été supprimés. `canonicalize_media_url` lit le même
classifieur : la politique d'URL canonique et la table de routage ne peuvent plus
diverger sur un hôte.

Effet de bord réparé au passage : `https://youtube.com/feeds/videos.xml?channel_id=…`
était classé RSS mais canonicalisé par `_canon_youtube`, qui réécrit l'hôte et
**jette la query** — le `channel_id` disparaissait de l'identité. Le type `FEED` étant
maintenant préservateur d'URL, les deux chemins s'accordent.

**2. L'article est lu avant d'être identifié.**
Nouveau port `core/ports/article_content.py` (`ArticleContentFetcherPort`,
`ArticleContent`, `ArticleFetchError`, enum stable `ArticleFetchErrorCode` +
`MEDIA_FAILURE_CODE_BY_ARTICLE_FETCH_ERROR` qui le traduit vers les
`MediaFailureCode` déjà rendus par l'app). Unique implémentation :
`infrastructure/resolvers/trafilatura_article_resolver.py`, où la politique de fetch
(redirections, garde `Content-Type`, plafond 2 Mo, repli d'encodage) a été déplacée
depuis le worker. `ArticleResolver` (`adapters/resolvers.py`) appelle ce port dans la
requête, puis calcule :

`media_key = generate_article_media_key(canonical_url, sha256(texte extrait))`

L'empreinte porte sur le texte **extrait et normalisé**, pas sur le HTML : les slots
publicitaires et les jetons CSRF d'une page changent à chaque requête, hasher le HTML
aurait fait de chaque sauvegarde un nouveau média et cassé la moitié de la décision
(un article inchangé reste mutualisé). `trafilatura` est importé paresseusement, à la
première extraction, pour ne pas faire payer `lxml` aux cold starts qui ne touchent
aucun article. Budget : `ARTICLE_FETCH_TIMEOUT_SECONDS` = 12 s côté API contre le
plafond non négociable de 30 s d'API Gateway ; le worker garde ses 20 s.

**3. Plus rien n'est mis en file pour un article sauvegardé par un utilisateur.**
`ProcessingJobSubmissionOrchestrator._settle_article_submission` écrit le transcript
(`{job_id}.txt`), l'`extraction_metadata`, marque le job terminé et publie
l'`episode_completion_status` de succès — le job est `completed` quand la requête
répond. La branche d'envoi vers `ARTICLE_EXTRACTION_QUEUE` et le drapeau
`article_extraction_enqueued` sont supprimés, ainsi que la permission
`sqs:SendMessage` correspondante sur le rôle de l'API (`iam_lambda.tf`).

**Le worker `article_extraction_worker` et sa queue restent vivants** : contrairement
à ce que le périmètre laissait supposer, `rss_feed_poll_worker.py:145` les alimente
pour chaque nouvel item d'article d'un flux RSS, avec un job déjà créé. Le worker a
donc été **refactorisé sur le même port** (ses `_fetch_article_html`,
`_extract_clean_text`, `_extract_article_metadata`, `_build_extraction_metadata` sont
supprimés) : une seule politique de lecture, deux appelants, aucun risque que l'API et
le worker se contredisent sur ce que dit une page.

**4. Page illisible : aucune exception ne remonte.**
Le resolver renvoie un `ResolvedMedia` sans `raw_text` portant le code d'échec, et
l'orchestrateur marque le job échoué avec le `MediaFailureCode` existant
(`NOT_AN_ARTICLE_PAGE`, `ARTICLE_TEXT_NOT_FOUND`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_TIMED_OUT`). Le miroir durable transforme ça en tuile échouée localisée,
avec l'action « demander le support de cette source » déjà en place : zéro nouveau
vocabulaire d'erreur, zéro travail mobile. **Distinction porteuse** : une cause
transitoire (5xx, timeout, connexion coupée) *libère* la réservation d'idempotence au
lieu de la marquer `failed`, sinon une panne de trente secondes répondrait le même
échec à toutes les sauvegardes futures de cette URL sans jamais relire la page. Un
verdict sur la page elle-même (un PDF, pas de corps) garde la ligne et publie
l'événement d'échec.

**5. `trafilatura` passe en dépendance de base** (`pyproject.toml`, `uv.lock`
régénéré) : l'image API en a besoin maintenant. Elle était dans l'extra `worker`, et
`lambda-api.Dockerfile` installe depuis `uv export --frozen --no-dev
--no-emit-project`, qui exclut les extras. `lxml` a des wheels
`manylinux2014_aarch64` en cp311, donc aucun compilateur n'entre dans l'image.

### Pourquoi #4 est satisfait par construction

`build_artifact_id` hashe `resolution.expected_source_ids`, qui sont les `content_id`,
et `artifact_service.py:755` pose `content_id = record.media_key`. Un texte modifié
donne un `media_key` différent, donc un `artifact_id` différent : une demande de
résumé après réécriture ne peut plus retomber sur l'entrée `REUSED` de l'ancien texte.
Rien à ajouter dans `artifact_service.py` — c'est l'identité de contenu qui était
fausse, pas la réutilisation.

### AC #6 : non coché, et pourquoi

L'AC demande de constater **deux lignes** pour un article modifié entre deux
sauvegardes. Ces deux lignes ne peuvent naître que de deux ingestions réelles passant
par le code de cette branche, donc après déploiement — qui se déclenche au push sur
`main`, bien après la fin de ce run. Fabriquer les deux lignes à la main dans
`user_media-dev` ne prouverait rien : ça testerait `put-item`, pas le pipeline.

Ce qui a été vérifié pour de vrai contre `-dev` (région **eu-west-3** ; le shell
exportait `us-east-1`, d'où des tables « absentes ») est l'**état d'avant**, c'est-à-dire
le défaut lui-même :

- `user_media-dev`, ligne article `https://fr.wikipedia.org/wiki/Commune_de_Paris` →
  `media_key = mkey_v1_f4109137…c1ac9d09`, `processing_status = ready`.
- Recalcul local depuis le dépôt : `derive_media_identity(cette URL)` rend
  **exactement** `mkey_v1_f4109137…c1ac9d09`. L'identité stockée est donc bien le seul
  SHA-256 de l'URL, sans aucune trace du texte servi.
- Idem pour `https://example.com/` → `mkey_v1_0f115db0…7783e9d7`, également reproduit
  à l'identique.
- `media_idempotence-dev`, même clé : `status = processed`, `created_at`
  2026-09-05, `job_id` du premier traitement. C'est la ligne qui, aujourd'hui, répond
  à toute nouvelle sauvegarde de cette URL avec le texte capturé le 5 septembre — quel
  que soit le contenu de la page depuis.
- Avec la nouvelle recette, la même URL rend une clé stable pour un texte identique
  (`mkey_v1_811bcb7c…` deux fois de suite) et une clé différente dès que le texte
  bouge (`mkey_v1_dfdab6e9…`).

Vérification manuelle laissée au propriétaire après déploiement : sauvegarder une page,
la modifier, la re-sauvegarder, et constater deux `media_key` distincts dans
`user_media-dev` avec deux transcripts distincts.

### Aucun test automatisé

Conformément aux règles du dépôt, aucun test unitaire ni d'intégration n'a été ajouté.
Aucun AC n'en demandait.

### Vérifications passées

- `ruff check media_summarizer/` → clean.
- `mypy media_summarizer/` → `Success: no issues found in 188 source files`.
- `terraform validate` (env `dev`) → `Success! The configuration is valid.`
- `uv lock` régénéré ; `uv export --frozen --no-dev` contient bien `trafilatura` et
  `lxml`, c'est-à-dire que l'image API les recevra.
<!-- SECTION:NOTES:END -->
