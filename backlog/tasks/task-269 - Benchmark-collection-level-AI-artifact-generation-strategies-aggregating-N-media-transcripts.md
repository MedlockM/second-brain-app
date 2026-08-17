---
id: task-269
title: >-
  Benchmark collection-level AI artifact generation strategies (aggregating N
  media transcripts)
status: Done
assignee: []
created_date: '2026-08-17 19:40'
updated_date: '2026-08-17 22:26'
labels:
  - benchmark
  - backend
  - ai
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Research task. No implementation.

## Contexte

Décision de l'owner (2026-08-17) : l'écran d'une collection doit exposer un onglet « IA » qui génère les artefacts non pas sur un média, mais sur **tous les médias de la collection agrégés** — l'équivalent de l'onglet Studio de NotebookLM au niveau du notebook. Rien de tel n'existe : toute la chaîne d'artefacts est aujourd'hui scopée à un `media_item_id` unique.

Périmètre de types tranché par l'owner : les **5 types existants** (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`), pas de nouveau type. Ne pas benchmarker l'ajout de modalités (résumé audio, présentation, infographie) : hors périmètre.

UX cible et découpage mobile : voir task-263 (chantier de refonte NotebookLM), task-271 (onglets Reader/IA sur le media) et task-272 (onglets Sources/IA sur la collection), qui consomme ce que task-270 implémente.

## Modèle de cycle de vie tranché par l'owner (2026-08-17) — ne pas le rouvrir

**Il n'y a pas d'invalidation.** Un artefact de collection est un **résultat immuable et horodaté**, pas une projection à maintenir à jour. Référence : `mobile-design-mockups/notebooklm-reference/collection-ai-generated-list.png` — sous les boutons de génération, NotebookLM liste les artefacts déjà produits, chacun avec son titre, le **nombre de sources** sur lequel il a été généré et sa **date de génération** (« 10 sources • Il y a 11 j »).

Ce que cela implique, et que le benchmark doit prendre comme donnée d'entrée :

- Le stockage est **append-only** : chaque génération crée une nouvelle entrée. Plusieurs artefacts du même type peuvent coexister pour une même collection.
- Chaque entrée porte un **snapshot** de ce sur quoi elle a été produite : la liste des `media_item_id` retenus, leur nombre, et l'horodatage de génération. C'est ce snapshot qui est affiché, et c'est lui qui rend l'artefact honnête quand la collection a bougé depuis.
- Ajouter ou retirer un média d'une collection **ne périme rien, ne régénère rien, ne supprime rien**. L'utilisateur régénère s'il le souhaite ; l'ancien artefact reste dans la liste.
- **Le même modèle s'applique au scope média** (décision de l'owner du 2026-08-17). Aujourd'hui un média n'a qu'un artefact par type, écrasé à la régénération. Cela devient un historique horodaté lui aussi : le benchmark doit traiter les deux scopes avec **une seule** mécanique append-only, pas deux modèles concurrents. Pour un artefact de média, le snapshot n'a pas de « N sources » à afficher, mais garde son horodatage et sa version de générateur.
- Ce qui reste à trancher, et qui est un **vrai** sujet technique : la déduplication à courte portée, c'est-à-dire ne pas produire deux artefacts identiques à cause d'un double tap ou d'une relivraison SQS (la queue est *at-least-once*). Dire comment les locks d'idempotence existants (`artifact_idempotence<suffix>`, `build_request_fingerprint` / `build_generation_fingerprint`) sont réutilisés ou remplacés pour couvrir ce cas **sans** réintroduire une sémantique d'invalidation, et si le titre de l'artefact doit être généré (le screenshot montre des titres porteurs de sens : « Crise des Missiles de Cuba », « Signification JFK »).

## Ce que le code fait aujourd'hui (à vérifier avant de s'appuyer dessus)

- Types et statuts : `media_summarizer/core/models/media_artifact.py` (`MediaArtifactType`, `MediaArtifactStatus`, `MediaArtifactRecord`, `ArtifactGenerationLock`), whitelist runtime `_allowed_artifact_types()` dans `core/services/artifact_service.py`.
- Service : `media_summarizer/core/services/artifact_service.py` — `request_artifact_generation`, fingerprints `build_request_fingerprint` / `build_generation_fingerprint`, `get_generator_version` (`"<type>:<model>:prompt-v1"`), `_load_transcript_bytes`, `_resolve_effective_transcript` (déclenche/attend la traduction), `mark_artifact_generating` / `complete_artifact_generation` / `fail_artifact_generation`.
- Routes : `media_summarizer/api/endpoints/artifacts.py` — `POST/GET /api/media/{media_item_id}/artifacts`, `GET /api/artifacts/{artifact_id}`, `GET /api/artifacts/{artifact_id}/content`. Le statut est aussi projeté dans `GET /api/media/{id}` via `artifact_statuses` (`api/endpoints/media.py`), et c'est ce que le mobile poll.
- Worker unifié : `media_summarizer/workers/artifact_generator/worker.py` (+ `generators/{summary_short,summary_detailed,notes,quiz,flashcards}.py`, un prompt et un schéma par type). Modèle par défaut `OPENAI_MODEL` = `gpt-5.4-nano-2026-03-17`, overrides par type.
- Stockage : table `media_artifacts<suffix>` (PK `artifact_id`, GSI `media-item-index`, `request-fingerprint-index`, `generation-fingerprint-index`), locks `artifact_idempotence<suffix>`, un bucket S3 par type (`infrastructure/terraform/modules/platform/{dynamodb_core_tables.tf,s3.tf,sqs.tf,lambda_workers.tf}`), accès via `utils/media_artifacts.py` et `utils/artifact_idempotence.py`.
- **« Collection » côté UI = `folder` côté backend** (mapping explicite dans `mobile/src/services/organizationService.ts`). Modèle `core/models/folder.py` (profondeur max 5), service `core/services/folder_service.py`, table `user_folders<suffix>`, routes `api/endpoints/folders.py`. Il n'y a **pas** de route « médias d'une collection » : c'est `GET /api/media?folder_id=...`, qui **inclut les sous-collections**. Requêtes durables : `utils/user_media.py` — `list_for_folder` (LSI `folder-index`), `count_media_per_folder`.

## Questions que le benchmark doit trancher

1. **Stratégie d'agrégation des transcripts.** Comparer au minimum : (a) concaténation brute des transcripts effectifs jusqu'à la limite de contexte, avec troncature explicite ; (b) map-reduce — un passage LLM par média puis un passage de synthèse ; (c) hiérarchique paresseux — réutiliser les `summary_*` **déjà générés** par média comme entrée, et n'en générer que les manquants ; (d) toute autre approche que la recherche fait émerger. Pour chacune : qualité attendue par type d'artefact (un quiz agrégé n'a pas les mêmes besoins qu'un résumé), coût marginal par collection, latence, nombre d'appels LLM, et complexité face aux fichiers listés ci-dessus.
2. **Volumétrie réelle.** Mesurer sur le `-dev` la taille des transcripts existants (médiane, p95, max) et le nombre de médias par collection, puis confronter à la fenêtre de contexte et au prix du modèle retenu. Sans ce chiffre, le choix (a) vs (b) est indécidable. Dire explicitement combien de médias une collection peut porter avant que chaque stratégie casse.
3. **Plafond et politique de refus.** Faut-il un maximum de médias (ou de tokens) par génération de collection ? Que renvoie l'API au-delà — refus explicite, troncature annoncée, dégradation ? Le mobile doit pouvoir afficher quelque chose d'honnête.
4. **Sous-collections.** `GET /api/media?folder_id=` remonte les sous-collections. L'artefact d'une collection couvre-t-il ses descendants (cohérent avec le reste de l'app) ou seulement le niveau courant ? Trancher et dire pourquoi. La réponse détermine ce que compte le « N sources » affiché.
5. **Historique append-only, pour les deux scopes.** Le modèle est fixé (voir la section ci-dessus) ; ce qui reste à spécifier est sa mécanique : quels champs porte le snapshot (liste des `media_item_id`, `source_count`, `generated_at`, `generator_version`), comment se fait la déduplication anti-double-tap et anti-relivraison SQS sans sémantique d'invalidation, si l'historique est borné (garder les N derniers par type ? un TTL ?) ou illimité, et si le titre affiché est saisi, dérivé du type, ou généré par le LLM. Dire aussi ce que le passage à l'append-only change pour le **scope média** : ce qui remplace la projection `artifact_statuses` de `GET /api/media/{id}` — sur laquelle le mobile poll aujourd'hui pour savoir si un type est `ready` — quand plusieurs artefacts du même type coexistent.
6. **Modèle de stockage.** Réutiliser `media_artifacts` avec un scope (`scope=media|collection`, `media_item_id` remplacé/complété par `folder_id`) ou introduire une table dédiée. Comparer l'impact sur les GSI existants, sur `utils/media_artifacts.py`, sur les buckets S3, et sur la queue (une queue unifiée de plus ou réutilisation d'`artifact-generator-queue`). Idem pour le worker : étendre `worker.py` ou en ajouter un. Prendre en compte que le listing doit rendre **tous** les artefacts d'une collection triés par date décroissante, pas un par type.
7. **Transcripts non prêts et langues hétérogènes.** Que fait-on d'une collection dont 3 médias sur 10 sont encore en traitement, ou dont les transcripts sont en langues différentes (le pipeline a déjà `transcript_translation`) ? Bloquer, générer sur le sous-ensemble prêt en l'annonçant, attendre ? Noter que le modèle append-only rend l'option « générer sur le sous-ensemble prêt » acceptable, à condition que le snapshot dise sur combien de sources l'artefact a réellement porté.
8. **Attribution des sources.** Un artefact agrégé doit-il citer de quel média vient quoi (utile pour les notes et le quiz) ? Si oui, impact sur les prompts et les schémas de sortie de chaque générateur.
9. **Exposition API.** Forme des routes (`POST /api/folders/{folder_id}/artifacts`, `GET /api/folders/{folder_id}/artifacts` rendant l'historique horodaté ?) et comment le mobile poll l'avancement d'une génération en vol sans multiplier les appels.
10. **Quota et paywall.** Comment une génération de collection est comptée face aux quotas et à l'offre existante : une unité, N unités, un tarif propre ? Un modèle append-only signifie que l'utilisateur peut régénérer sans limite technique — dire ce qui l'en empêche. S'aligner sur les décisions déjà consignées (`docs/research/`, benchmark pricing task-65) plutôt que d'en inventer une.

## Livrable

`docs/research/task-269-collection-artifact-aggregation/README.md`, front-matter `owner_decision: pending`, avec la comparaison chiffrée, une recommandation unique et argumentée, et l'architecture cible assez précise pour que task-270 soit implémentable en la lisant (routes, schéma de stockage, contenu du snapshot, déduplication, worker, plafonds).

## Note à l'owner — hors AC

- Rappel : rien n'est déployé, aucune donnée de production. Aucune stratégie ne doit être retenue au motif de préserver des artefacts existants ou une compatibilité — les artefacts par média du `-dev` sont jetables.
- Les mesures de volumétrie se font en lecture sur le `-dev` (DynamoDB / S3), pas en produisant du trafic LLM.
- Le scope **média** passe lui aussi à l'historique horodaté (votre décision du 2026-08-17). C'est ce qui touche le plus de code existant : la projection `artifact_statuses` de `GET /api/media/{id}`, le polling du mobile et l'écran `artifacts/[artifactId]` supposent tous « un artefact par type ». Attendre la recommandation du README avant d'estimer task-270 et task-271.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `docs/research/task-269-collection-artifact-aggregation/README.md` existe, avec un front-matter conforme au workflow benchmark (`owner_decision: pending`, champs `Decision` et `Validated at` vides sous `Owner Validation`)
- [ ] #2 Au moins trois stratégies d'agrégation (concaténation brute, map-reduce, réutilisation hiérarchique des résumés par média) sont comparées sur : qualité par type d'artefact, coût marginal par collection, latence, nombre d'appels LLM, complexité d'implémentation face aux fichiers du pipeline existant
- [ ] #3 La volumétrie réelle du `-dev` est mesurée et chiffrée dans le README (taille des transcripts : médiane, p95, max ; nombre de médias par collection), avec la commande ou la requête utilisée, et confrontée à la fenêtre de contexte et au prix du modèle retenu
- [ ] #4 Le README tranche explicitement, avec justification : plafond de médias/tokens par génération et comportement au-delà ; inclusion ou non des sous-collections ; traitement des transcripts non prêts et des langues hétérogènes ; attribution des sources dans la sortie
- [ ] #5 Le README spécifie la mécanique de l'historique append-only imposé par l'owner : champs du snapshot (liste des `media_item_id`, nombre de sources, horodatage, version du générateur), déduplication anti-double-tap et anti-relivraison SQS sans sémantique d'invalidation, bornage éventuel de l'historique, et origine du titre affiché
- [ ] #6 Le README applique la même mécanique append-only au scope média et dit ce qui remplace la projection `artifact_statuses` de `GET /api/media/{id}`, ainsi que l'impact sur le polling du mobile et sur l'écran `artifacts/[artifactId]`
- [ ] #7 Le README ne recommande aucun mécanisme d'invalidation, de péremption ou de régénération automatique déclenché par un changement de composition de la collection
- [ ] #8 Le README tranche le modèle de stockage (extension de `media_artifacts` avec un scope vs table dédiée), l'impact sur les GSI, les buckets S3, la queue SQS et le worker `artifact_generator`, et donne la forme exacte des routes API — dont un listing rendant tous les artefacts d'une collection triés par date décroissante — et du polling côté mobile
- [ ] #9 Le README traite le rattachement aux quotas et au paywall en référençant les décisions déjà consignées dans `docs/research/`, et dit ce qui borne les régénérations répétées qu'un modèle append-only autorise

- [ ] #10 Le README ne recommande aucune couche de compatibilité, aucun double stockage et aucune fenêtre de dépréciation : les artefacts existants du `-dev` sont traités comme jetables
- [ ] #11 Aucun fichier hors `docs/research/task-269-collection-artifact-aggregation/` n'est modifié
<!-- AC:END -->
