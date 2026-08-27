---
id: task-323
title: >-
  Nouveau type d'artefact review_blurb : résumé court en prose généré à
  l'ingestion, et tri chronologique croissant de la bibliothèque
status: To Do
assignee: []
created_date: '2026-08-25 12:15'
labels:
  - backend
  - artifacts
  - infrastructure
dependencies:
  - task-320
  - task-322
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'écran de triage des médias non triés (tâche mobile qui dépend de celle-ci) présente chaque média avec sa vignette, son titre, son auteur et **un résumé court en prose de 5 à 10 lignes** permettant de décider en quelques secondes s'il faut le jeter, l'approfondir ou le ranger dans une collection.

Décision de l'owner : ce résumé est un **nouveau type d'artefact dédié** `review_blurb`, généré **en tâche de fond dès la fin de l'ingestion**. Ce n'est ni une extension de `summary_short`, ni une réutilisation de ses `key_points` : la forme visée est un paragraphe continu qui répond « de quoi ça parle, quelle est la thèse, pour qui », alors que `summary_short` produit une liste de points destinée au digest.

Cette tâche livre l'intégralité du volet backend : le type et son générateur, son déclenchement automatique, sa lecture bon marché depuis le mobile, et le tri chronologique croissant dont l'écran a besoin.

## Pourquoi cette tâche dépend de task-320 et task-322

Ce ne sont pas des dépendances de confort. Les deux réécrivent le code que cette tâche modifie, et la règle du projet est que la restructuration passe avant la tâche qui peuple :

- **task-320** crée dans `corpus.py` un fragment partagé interdisant le style méta-référentiel, inclus par les cinq générateurs. « Pas de méta-commentaire » est littéralement une clause du prompt `review_blurb` : passer avant 320 obligerait à l'écrire en dur puis à la voir factoriser.
- **task-322** fait de `plan_artifact_generation()` une recherche d'existant sans borne de temps et supprime `DEDUP_WINDOW_SECONDS`. C'est le mécanisme même de la décision owner « une seule génération, cache permanent » : après 322, l'unicité à vie du blurb est acquise par construction. Avant 322, il faudrait la simuler avec la fenêtre de 120 s, donc jeter ce travail.

## Ce qu'il faut construire

Lis d'abord `workers/artifact_generator/generators/summary_short.py` : c'est le sibling le plus proche, et le protocole à satisfaire est dans `generators/base.py`.

### Le type et son générateur

Le type est **interne et limité au scope `media`** : l'utilisateur ne le demande jamais, il n'apparaît dans aucune UI d'artefacts. `REQUESTABLE_ARTIFACT_TYPES` reste donc la surface publique et ne l'accueille pas ; introduis à côté un ensemble des types générables (`REQUESTABLE` + internes) sur lequel `plan_artifact_generation` s'appuie, avec un garde « type interne implique scope média ». L'endpoint de création d'artefact doit refuser un type interne avant d'atteindre le service.

Point à ne pas manquer : `list_scope_artifacts` doit **filtrer** les types internes. `mobile/src/components/ArtifactHistoryRow.tsx` retombe sur `artifact.artifact_type` brut quand aucune tuile ne correspond au type, donc un `review_blurb` remonté ferait apparaître une ligne littéralement libellée « review_blurb » dans l'historique de l'onglet AI. Ce filtre côté serveur est ce qui rend inutile tout ajout du type côté mobile.

Le générateur : prose, donc pas de schéma de structured output. Validation par `_strip_code_fences` puis rejet du vide et de ce qui sort d'une bande large autour de la cible du prompt. Le rejet du vide ne contredit pas la clause « une section peut être vide » de task-320 : celle-ci vise la quantité d'items d'un quiz ou de flashcards face à une source pauvre, alors qu'ici le champ est unique et la condition d'entrée est l'existence d'un transcript.

Le modèle est `OPENAI_MODEL` avec le fallback des artefacts non-`summary_short`. **Aucun benchmark n'est nécessaire** : la Decision owner de `docs/research/task-72-llm-artifact-benchmark/README.md` (`owner_decision: ok`) partitionne déjà tous les types, `summary_short` d'un côté et « all other artefacts » de l'autre. N'introduis pas de variable `REVIEW_BLURB_LLM_MODEL` : la famille `*_LLM_MODEL` n'existe que dans `.env.example` et n'est portée par aucun secret runtime, ce sont des boutons morts.

Le type réutilise la file d'attente d'artefacts partagée. Aucune nouvelle queue, aucun nouveau Lambda. Il lui faut en revanche son bucket S3, son entrée dans les noms de buckets du runtime, et ses permissions IAM aux quatre emplacements habituels (objet et bucket, rôles worker et api).

### Le déclenchement à l'ingestion

Un module de service dédié, **pas** dans `digest_service` dont l'import tirerait tout le graphe digest dans le chemin de complétion. Le template à suivre est `digest_service.trigger_summary_short_generation` : `resolve_scope_sources`, `enforce_scope_ceilings`, `plan_artifact_generation`, `commit_artifact_generation`. Comme lui, il **ne débite aucun quota** — le débit est le fait de l'endpoint API, pas du service (cf. le commentaire d'`artifact_service.py:605`). C'est ce qui rend une génération automatique légitime : l'utilisateur ne paie pas un artefact qu'il n'a pas demandé.

Le point d'accrochage est `workers/events/media_completed_worker.py :: process_event`, **aux deux endroits** où l'indexation de recherche est déclenchée. Le second n'est pas une boucle de retry mais un fan-out par utilisateur : chaque watcher possède sa propre ligne `user_media` dans son propre dossier par défaut, donc l'omettre priverait de blurb tout média sauvegardé via la déduplication. Les deux appels doivent avaler toute exception et se contenter d'un warning : une remontée laisserait le message SQS non supprimé et rejouerait toute la complétion, réindexation comprise.

**Piège de traduction à éviter.** Le template passe le `reading_language` de l'utilisateur à `resolve_scope_sources`, ce qui peut lever `ArtifactTranscriptNotReadyError` à la première ingestion, quand la traduction n'est pas prête. Rien ne retente, donc le blurb serait définitivement absent. Résous les sources avec `reading_language=None` — chemin qui ne peut pas lever — et passe la langue dans les `parameters` du plan : le modèle lit le transcript original et écrit dans la langue de lecture via le fragment de langue de `corpus.py`. Un job de traduction en moins par ingestion, et la langue restant dans la clé de l'artefact, deux langues de lecture donnent bien deux blurbs distincts (cf. task-322).

### La lecture bon marché depuis le mobile

Sans dénormalisation, ouvrir l'écran de triage coûterait une requête d'artefacts plus un `get_object` S3 **par carte**. Recopie donc la prose sur la ligne `user_media` au moment où l'artefact se termine — le précédent est la recopie du `title` que `complete_artifact_generation` fait déjà — et surface-la sur l'item de bibliothèque. La recopie doit être encapsulée de façon à ne jamais faire échouer l'artefact si elle rate.

Attention au piège : le mapper du service de recherche et le modèle de réponse de l'endpoint doivent **tous les deux** être modifiés. Le modèle tourne sous l'`extra='ignore'` par défaut de Pydantic v2, donc une clé sans champ déclaré est silencieusement jetée, et un champ sans clé lit silencieusement `None`. Aucun crash ne le signalera.

Rien à changer dans l'helper d'écriture `user_media` : sa mise à jour d'attributs est générique et le nouvel attribut n'est ni interdit ni immuable. Pas de bump de la version de schéma non plus : le précédent `last_engaged_at` a été ajouté sans bump et un attribut optionnel absent se lit correctement.

### Le tri chronologique croissant

L'écran présente les médias du plus ancien au plus récent. Le service de recherche charge déjà toute la bibliothèque et la trie en mémoire avant de paginer, donc c'est un paramètre additif d'une dizaine de lignes sur l'endpoint canonique existant : le sens du tri, et la comparaison du curseur inversée en conséquence. Défaut inchangé, aucun appelant existant modifié.

Ne propose pas de solution cliente à la place : inverser une page décroissante de 100 items renvoie « les plus anciens des 100 plus récents », silencieusement faux au-delà de 100.

### Le backfill

Un script CLI lançable en `python -m`, sur le modèle de `workers/digest/scheduler.py :: pre_generate_summary_shorts` : parcours des utilisateurs, parcours de la bibliothèque, saut des lignes déjà pourvues, appel du déclencheur, temporisation entre deux appels pour ne pas saturer le LLM. Deux garde-fous en variables d'environnement documentées dans le docstring, la temporisation et une limite d'items, pour permettre un essai à blanc.

## Nettoyages inclus

Le projet n'a jamais été déployé : on supprime le legacy, on ne le préserve pas.

- `_PUBLIC_ARTIFACT_TYPES` dans `api/endpoints/media.py` est déclaré et référencé nulle part.
- Le défaut `ARTIFACT_TYPES_ALLOWED` de `utils/infra_check.py` est périmé (il liste encore `summary`). Trois sites doivent s'accorder — `core/config.py`, `artifact_service.py`, `infra_check.py` — plus `.env.example`, dont le `summary` legacy disparaît.

## Hors périmètre

- Toute l'UI mobile de l'écran de triage : tâche dépendante.
- Les prompts des cinq types existants (task-320 et task-321) et le cycle de vie génération unique / cache (task-322).
- Toute exposition publique de `review_blurb` : pas d'entrée dans les types demandables, pas de tuile mobile, pas d'affordance de génération manuelle.

## Notes à l'owner (non vérifiables par l'agent)

- **Déploiement** : après merge et push de `main`, déployer le module platform (nouveau bucket, IAM, variable d'environnement Lambda) puis l'image du worker d'artefacts, sinon le type existe dans le code sans support runtime.
- **Backfill** : à lancer sur `-dev` après ce déploiement pour pourvoir les médias déjà en bibliothèque. Après task-322, le relancer est sans risque — un média déjà pourvu renvoie son artefact existant sans générer.
- **Vérification E2E** : une ingestion fraîche doit poser un `review_blurb` non vide sur sa ligne `user_media` dans `user_media-dev`, sans débit de quota.
- **Effet de bord connu et accepté** : écrire le blurb met à jour `updated_at`, qui est la moitié de la clé de cache des vignettes côté mobile. Chaque média re-télécharge sa vignette une fois.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le type d'artefact `review_blurb` existe dans l'enum des types et le registre des générateurs le mappe à un générateur qui satisfait tous les membres du protocole `ArtifactGenerator`
- [x] #2 Le générateur résout son modèle depuis `OPENAI_MODEL` avec le fallback des artefacts non-`summary_short` validé par task-72, et `grep -rn "REVIEW_BLURB_LLM_MODEL"` sur le repo ne renvoie rien
- [x] #3 Le prompt inclut par appel le fragment anti-méta-référentiel de `corpus.py` posé par task-320 sans réécrire la consigne, et passe par les helpers partagés de `corpus.py` pour le corpus et la langue
- [x] #4 L'entrée du type dans `get_generator_version()` est en version 1 : c'est un prompt neuf qui n'a jamais produit d'artefact
- [x] #5 Ni le service de déclenchement ni le générateur n'appellent de compteur de quota ou d'entitlement : la génération automatique ne débite rien à l'utilisateur
- [x] #6 `plan_artifact_generation` accepte le type via l'ensemble des types générables, et lève `ArtifactTypeNotEnabledError` si le scope demandé n'est pas `media`
- [x] #7 `REQUESTABLE_ARTIFACT_TYPES` ne contient pas le nouveau type, et l'endpoint de création d'artefact le refuse en 422 avant d'atteindre le service
- [x] #8 `list_scope_artifacts` ne renvoie aucun enregistrement de type interne, de sorte qu'aucun libellé de type brut ne puisse remonter dans l'historique mobile
- [x] #9 La ligne de bibliothèque `UserMediaRecord` porte le nouvel attribut texte optionnel, la version de schéma `user_media` est inchangée, et `scripts/check_purge_at_writers.py` sort en 0
- [x] #10 `complete_artifact_generation` recopie la prose sur la ligne `user_media` uniquement pour ce type et le scope média, dans une enveloppe qui avale l'échec en le loggant sans faire échouer l'artefact
- [x] #11 Le mapper de résultats du service de recherche émet la nouvelle clé ET le modèle de réponse de l'endpoint déclare le champ correspondant : les deux, sans quoi l'`extra='ignore'` de Pydantic la perd silencieusement
- [x] #12 L'endpoint canonique de liste des médias accepte un paramètre de sens de tri valant `asc` ou `desc`, défaut `desc` ; le service trie et applique le curseur dans la direction demandée, et aucun appelant existant n'est modifié
- [x] #13 Le déclencheur vit dans son propre module de service et non dans `digest_service`, et enchaîne résolution des sources, plafonds de scope, plan puis commit
- [x] #14 Le déclencheur résout les sources sans langue de lecture et passe la langue par les `parameters` du plan, de sorte qu'une première ingestion ne puisse pas échouer sur une traduction non prête
- [x] #15 `process_event` appelle le déclencheur aux deux endroits où l'indexation de recherche est déclenchée, y compris le fan-out par watcher, chacun enveloppé pour qu'aucune exception ne puisse sortir de `process_event`
- [x] #16 Le déclencheur court-circuite avant d'entrer dans le service si la ligne porte déjà une prose non vide ou si elle n'a pas de transcript
- [x] #17 Un script de backfill lançable en `python -m` existe, saute les lignes déjà pourvues, et expose une temporisation et une limite d'items en variables d'environnement documentées dans son docstring
- [x] #18 Le nouveau bucket S3 du type est déclaré, exposé au runtime sous forme de variable d'environnement, et couvert par les permissions IAM aux quatre emplacements habituels
- [x] #19 Les défauts `ARTIFACT_TYPES_ALLOWED` s'accordent entre `core/config.py`, `artifact_service.py` et `utils/infra_check.py`, incluent tous le nouveau type, aucun n'inclut le `summary` legacy, et `.env.example` correspond
- [x] #20 `_PUBLIC_ARTIFACT_TYPES` n'apparaît plus nulle part sous `media_summarizer/`
- [x] #21 `ruff check media_summarizer` et `mypy media_summarizer` sont propres
- [x] #22 `terraform validate` passe et le `plan` sur `-dev` montre l'ajout du seul nouveau bucket, les mises à jour IAM et l'ajout de variable d'environnement Lambda, sans aucune destruction ni remplacement de bucket existant
- [x] #23 L'absence actuelle du bucket planifié est vérifiée à l'AWS CLI et consignée dans les notes d'implémentation, confirmant que le plan crée bien une ressource neuve
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Le type interne : deux ensembles au lieu d'un drapeau

`artifact_service.py` porte désormais trois ensembles au lieu d'un :

- `REQUESTABLE_ARTIFACT_TYPES` — inchangé, les cinq types que l'utilisateur peut demander. C'est resté la surface publique, donc toute lecture existante (tuiles, quotas, entitlements) exclut `review_blurb` **par défaut** et non en s'en souvenant.
- `INTERNAL_ARTIFACT_TYPES` — `{REVIEW_BLURB}`.
- `GENERATABLE_ARTIFACT_TYPES` — l'union, c'est-à-dire ce que le pipeline sait produire. C'est ce que `plan_artifact_generation` valide, avec juste après le garde « type interne implique scope média » qui lève `ArtifactTypeNotEnabledError`.

Le refus côté endpoint est un `field_validator` Pydantic sur `ArtifactCreateRequest.artifact_type`, donc un `RequestValidationError` que `api/error_handling.py` traduit déjà en 422. Il rejette **uniquement** les types internes : un type inconnu ou une coquille garde son 400 existant, produit plus bas par le service. Le validateur est au bord de la requête et non dans le service parce que c'est cet endpoint qui débite le quota et vérifie l'entitlement : nommer un type interne là aurait sinon consommé l'allocation de l'utilisateur pour un artefact qu'aucun écran ne lui montrera.

`list_scope_artifacts` filtre `INTERNAL_ARTIFACT_TYPES` **après** la requête DynamoDB. Conséquence assumée et documentée dans son docstring : une page peut revenir plus courte que `limit` tout en portant un curseur de suite. Le client pagine déjà sur le curseur et non sur la taille de page, et l'alternative (sur-lire pour recompléter) coûterait des requêtes pour un cas qui ne se produit que sur les médias pourvus d'un blurb.

### Le générateur

Prose, donc `response_format_schema()` renvoie `None` et `unwrap_structured_response` est l'identité : le texte du modèle *est* l'artefact. `validate()` normalise les espaces après `_strip_code_fences`, rejette le vide, et rejette hors de la bande 140–2600 caractères — délibérément ~2,5× plus large de chaque côté que les 5–10 lignes demandées par le prompt. L'objectif est d'attraper « ce n'est pas un blurb » (un télégramme d'une ligne, ou le résumé détaillé recopié), pas de policer la longueur d'une prose.

Le dict validé ne porte **pas** de clé `title`, contrairement aux cinq types demandables : le titre sert à distinguer deux entrées d'un même type dans l'historique, et ce type est justement filtré de l'historique. Le worker lit le titre en `.get`, l'enregistrement garde donc un `title` nul. Le docstring de `generators/base.py` a été précisé en conséquence.

`ReviewBlurbValidationError` est ajoutée au tuple d'`isinstance` du worker qui pose `error_code = "VALIDATION_ERROR"`, comme les erreurs de validation des autres types.

Version du générateur : `review_blurb:<OPENAI_MODEL>:prompt-v1`, prompt neuf jamais exécuté.

### Recopie sur la ligne de bibliothèque, et son chemin de réparation

`complete_artifact_generation` recopie la prose sur `user_media` sous double condition (`artifact_type == REVIEW_BLURB` **et** `scope == MEDIA` — à scope collection le `scope_id` est un id de dossier ou de tag et adresserait une ligne inexistante). La recopie est dans `_mirror_review_blurb_onto_library_row`, qui avale toute exception avec un warning : l'artefact est déjà écrit et scellé quand elle s'exécute, une génération réussie ne doit pas devenir un échec parce qu'un `update_attributes` a raté.

D'où un second chemin, `copy_review_blurb_to_library_row(record=…, media_item_id=…)`, qui relit l'objet S3 et remplit une ligne dépourvue de prose. Il couvre deux situations que task-322 rend structurelles :

1. la recopie de complétion a raté (S3 a écrit, DynamoDB non) ;
2. une seconde sauvegarde du même contenu par le même utilisateur résout au **même** `artifact_id` — l'id dérive de la clé de contenu, pas de la ligne — donc `commit_artifact_generation` répond `REUSED` et aucune complétion ne se produit. C'est pour cette raison que `media_item_id` est un **paramètre** et n'est pas lu sur `record` : le `scope_id` de l'artefact réutilisé pointe la *première* ligne, pas celle de l'appelant.

Le déclencheur appelle donc ce chemin de réparation dès qu'il reçoit `REUSED`.

### Le déclenchement

`core/services/review_blurb_service.py` est un module dédié, jamais importé par `digest_service`. Ses imports d'`artifact_service` sont faits dans la fonction pour ne pas allonger le démarrage à froid du worker de complétion sur un chemin qui court-circuite la plupart du temps.

Deux court-circuits avant toute entrée dans le service : ligne portant déjà une prose non vide, et absence de `transcription_s3_key` sur le job. Ni quota, ni entitlement, ni `record_observed_cost` n'est touché.

Le piège de traduction est traité comme demandé : `resolve_scope_sources(..., reading_language=None)` — vérifié : ce chemin ne peut pas lever `TranslationInProgressError` ni `ArtifactTranscriptNotReadyError` pour un motif de traduction — et la langue de lecture voyage dans `parameters={"language": …}`. Vérifié aussi que `plan_artifact_generation` préserve ce `parameters` (il ne l'écrase que si `resolution.target_language` est non nul, ce qui n'arrive pas ici), donc la langue reste dans la clé de l'artefact et deux langues de lecture donnent bien deux blurbs distincts.

Les deux points d'accrochage de `process_event` passent par `_trigger_review_blurb`, qui avale tout : une remontée laisserait le message SQS non supprimé et rejouerait toute la complétion, réindexation comprise. Au premier site l'id est `canonical_job.media_item_id` sans repli sur l'id de job (un repli poserait le blurb sur une clé qui n'est pas une ligne de bibliothèque) ; au second, celui du fan-out par watcher, c'est le `media_item_id` du job du watcher et son `user_id`.

### Backfill

`python -m media_summarizer.scripts.backfill_review_blurbs`. Deux garde-fous en variables d'environnement, documentés dans le docstring et déclarés dans `.env.example` :

- `REVIEW_BLURB_BACKFILL_DELAY_SECONDS` (flottant, défaut `2.0`) — temporisation entre deux déclenchements ;
- `REVIEW_BLURB_BACKFILL_LIMIT` (entier, défaut `25`) — nombre maximum de déclenchements ; `0` donne un essai à blanc qui n'appelle aucun LLM et se contente de compter les lignes à pourvoir.

### Nettoyages

`_PUBLIC_ARTIFACT_TYPES` supprimé d'`api/endpoints/media.py` (déclaré, référencé nulle part). Le défaut d'`ARTIFACT_TYPES_ALLOWED` est maintenant une seule constante `DEFAULT_ARTIFACT_TYPES_ALLOWED` dérivée de l'enum dans `core/models/media_artifact.py`, lue par `core/config.py`, `artifact_service.py` et `utils/infra_check.py` : les trois sites ne peuvent plus diverger au prochain type ajouté, et le `summary` legacy disparaît. Vérifié que `ARTIFACT_TYPES_ALLOWED` n'est **pas** injecté par Terraform, donc c'est bien ce défaut dérivé de l'enum qui s'applique en environnement déployé.

`infra_check` n'a délibérément **pas** été étendu à `REVIEW_BLURB_BUCKET` : `required_env("REVIEW_BLURB_BUCKET")` échoue déjà à l'import, ajouter une seconde vérification n'apporterait qu'un nouveau mode d'échec au démarrage à froid.

### Preuves

- `ruff check .` (racine, comme la CI) : `All checks passed!` ; `mypy media_summarizer` : `Success: no issues found in 176 source files`.
- `scripts/check_purge_at_writers.py` et `scripts/check_env_example_complete.py` : OK (239 variables déclarées). Les deux gardes grep de `pr.yml` (task-143, task-195) : OK.
- `terraform validate` : Success ; `terraform fmt -check -recursive` : propre ; `terraform plan -lock=false` sur `envs/dev` : `Plan: 1 to add, 17 to change, 0 to destroy`, la **seule** création étant `module.platform.aws_s3_bucket.review_blurb`. Aucune destruction, aucun remplacement de bucket. Les 17 changements sont les deux policies IAM (`lambda_api`, `lambda_worker`) mises à jour sur place et les Lambdas qui gagnent `REVIEW_BLURB_BUCKET` dans leur environnement.
- AC#23 — `aws s3api head-bucket` sur le nom planifié (`media-summarizer-review-blurb-<account>-dev`) répond `An error occurred (404) ... Not Found`, et les 13 buckets `media-summarizer-*` existants du compte ne comportent aucun nom approchant. Le plan crée donc bien une ressource neuve et ne réadopte rien.
- `grep -rn "REVIEW_BLURB_LLM_MODEL"` sur l'ensemble du dépôt : aucun résultat. `grep -rn "_PUBLIC_ARTIFACT_TYPES" media_summarizer/` : aucun résultat.

### Non fait, et pourquoi

Aucun test automatisé n'a été ajouté : la règle du projet l'interdit. Aucun AC n'en demandait.

Les trois notes à l'owner restent hors de portée d'un agent en worktree : le déploiement du module platform puis de l'image du worker (déclenché au push sur `main`), le lancement du backfill sur `-dev` (qui suppose ce déploiement, sinon `REVIEW_BLURB_BUCKET` n'existe pas encore), et la vérification E2E d'une ingestion fraîche. Le chemin de code est en place et câblé de bout en bout ; ce qui reste est un déploiement et un run.
<!-- SECTION:NOTES:END -->
