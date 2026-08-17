---
id: task-270
title: >-
  Implement collection-scoped AI artifact generation per validated benchmark
  (task-269)
status: To Do
assignee: []
created_date: '2026-08-17 19:41'
updated_date: '2026-08-17 20:13'
labels:
  - backend
  - ai
  - feature
dependencies:
  - task-269
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Rendre possible la génération d'artefacts IA au niveau d'une **collection** — sur l'ensemble des médias qu'elle contient — et non plus seulement sur un média isolé. C'est le backend qui manque à l'onglet « IA » de l'écran collection (task-272).

**Lire d'abord `docs/research/task-269-collection-artifact-aggregation/README.md`**, section `Owner Validation`, champ `Decision`. C'est cette décision qui fixe la stratégie d'agrégation, le modèle de stockage, la forme des routes, le contenu du snapshot, la déduplication et les plafonds. Si le `Decision` renvoie à un fichier `complement-response-*.md` du même dossier, le suivre aussi. Ne pas rejouer le benchmark et ne pas substituer une autre architecture : en cas de contradiction entre cette description et le README, **le README gagne**.

## Contraintes indépendantes de la décision

- Périmètre de types tranché par l'owner : les **5 types existants** (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`). Aucun nouveau type d'artefact, aucune nouvelle modalité.
- **Historique append-only, aucune invalidation** (décision de l'owner du 2026-08-17, référence `mobile-design-mockups/notebooklm-reference/collection-ai-generated-list.png`). Chaque génération crée une entrée immuable qui porte un snapshot de ce sur quoi elle a porté — au minimum la liste des `media_item_id` retenus, leur nombre et l'horodatage. Plusieurs artefacts du même type coexistent pour une même collection. Une modification de la composition de la collection **ne périme, ne régénère et ne supprime rien**. Ne pas implémenter de péremption, de statut « obsolète », ni de régénération automatique.
- **Le scope média passe au même modèle** (décision de l'owner du 2026-08-17). Aujourd'hui un média n'a qu'un artefact par type, écrasé à la régénération : cela devient un historique horodaté lui aussi. Une seule mécanique append-only sert les deux scopes — pas deux modèles concurrents. Concrètement, la projection `artifact_statuses` de `GET /api/media/{id}`, sur laquelle le mobile poll aujourd'hui, doit être remplacée par ce que le README prescrit ; l'affichage mobile correspondant est traité par task-273.
- La déduplication reste nécessaire mais **à courte portée uniquement** : un double tap et une relivraison SQS (*at-least-once*) ne doivent pas produire deux artefacts. C'est la seule chose que les locks d'idempotence couvrent ici.
- Rappel « rien n'est déployé » : pas de double écriture, pas de champ conservé « au cas où », pas de fenêtre de dépréciation. Si le README impose de restructurer la table `media_artifacts` ou la forme des messages SQS, la restructuration est faite franchement et les chemins devenus morts sont supprimés dans le même run.
- « Collection » côté UI = `folder` côté backend. Ne pas introduire un troisième vocabulaire : rester sur `folder` dans le code Python et l'infra, et ne parler de « collection » que dans les libellés exposés.
- L'API doit rester utilisable par un mobile qui poll : l'avancement d'une génération en vol et l'historique des artefacts produits doivent être lisibles sans multiplier les appels, dans la forme décidée par le README.
- Les erreurs métier doivent être des refus explicites et typés (dans l'esprit des `ArtifactGenerationDisabledError` / `ArtifactTypeNotEnabledError` / `ArtifactTranscriptNotReadyError` existantes), pas des 500 : dépassement de plafond, collection vide, transcripts non prêts.

## Surface concernée (point de départ, à confronter au README)

- `media_summarizer/core/models/media_artifact.py`, `core/models/folder.py`
- `media_summarizer/core/services/artifact_service.py` (fingerprints, locks, résolution du transcript effectif, enqueue), `core/services/folder_service.py`
- `media_summarizer/api/endpoints/artifacts.py`, `api/endpoints/folders.py`, `api/models/media_contracts.py`
- `media_summarizer/workers/artifact_generator/worker.py` et ses `generators/*.py` (prompts et schémas de sortie)
- `media_summarizer/utils/{media_artifacts.py,artifact_idempotence.py,user_media.py}`
- `infrastructure/terraform/modules/platform/{dynamodb_core_tables.tf,s3.tf,sqs.tf,lambda_workers.tf}`

## Note à l'owner — hors AC

- Le déploiement (image Lambda + `terraform apply` sur `-dev`) se fait au push sur `main`, après le passage de l'agent. La vérification E2E « je génère un résumé sur une collection de 5 médias depuis le mobile, puis je retrouve l'artefact daté dans la liste » est manuelle et vous revient.
- Si le README retient une stratégie multi-appels LLM, surveiller le coût sur `-dev` après les premiers essais avant d'ouvrir l'onglet côté mobile. Le modèle append-only n'oppose aucune limite technique aux régénérations répétées.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les Implementation Notes citent explicitement la décision lue dans `docs/research/task-269-collection-artifact-aggregation/README.md` (stratégie d'agrégation, modèle de stockage, forme des routes, contenu du snapshot, plafonds) et signalent tout point où l'implémentation a dû interpréter le README
- [ ] #2 Le chemin complet existe et est câblé de bout en bout pour les 5 types (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`) : route API → service → lock d'idempotence → enqueue SQS → worker `artifact_generator` → écriture S3 + DynamoDB → lecture du contenu, avec le scope collection dans la forme décidée par le README
- [ ] #3 Les routes de génération, de listing et de récupération du contenu d'un artefact de collection sont montées dans l'app FastAPI et déclarées dans le schéma OpenAPI, avec les modèles de requête/réponse typés
- [ ] #4 Chaque artefact de collection persiste un snapshot immuable de sa génération — au minimum la liste des `media_item_id` retenus, leur nombre et l'horodatage — et le listing rend **tous** les artefacts d'une collection triés par date de génération décroissante, plusieurs entrées du même type incluses
- [ ] #5 Aucun mécanisme d'invalidation n'est implémenté : ajouter ou retirer un média d'une collection ne modifie, ne marque et ne supprime aucun artefact existant, et aucun statut de péremption n'est introduit
- [ ] #6 La déduplication couvre le double tap et la relivraison SQS — deux demandes concomitantes pour le même type sur la même collection produisent une seule génération — sans empêcher une régénération ultérieure demandée par l'utilisateur, qui crée bien une nouvelle entrée
- [ ] #7 L'avancement d'une génération en vol est lisible par le mobile dans la forme décidée par le README, sans requête par type d'artefact
- [ ] #8 Le plafond retenu par le README est appliqué et le dépassement, la collection vide, et les transcripts non prêts renvoient chacun un refus explicite typé avec un code HTTP distinct de 500
- [ ] #9 Les ressources d'infrastructure requises par le README (attributs et index DynamoDB, buckets S3, queue SQS, event source de la Lambda) sont déclarées dans `infrastructure/terraform/modules/platform/` et `terraform validate` passe
- [ ] #10 Aucune couche de compatibilité n'est introduite : pas de double écriture, pas de champ ou de route conservé sans lecteur ; tout chemin rendu mort par la restructuration est supprimé dans le même run et listé dans les Implementation Notes

- [ ] #11 `ruff` et `mypy` passent sur `media_summarizer/` sans nouvelle erreur
- [ ] #12 Une vérification directe contre le `-dev` est consignée dans les Implementation Notes (lecture AWS CLI des tables/buckets/queue ciblés, ou requête sur les médias d'un `folder_id` réel) montrant que les identifiants de ressources utilisés par le code correspondent à ceux qui existent

- [ ] #13 Le scope média utilise la même mécanique append-only que le scope collection : une régénération sur un média crée une nouvelle entrée horodatée au lieu d'écraser la précédente, le listing par média rend l'historique trié par date décroissante, et ce qui remplaçait la projection `artifact_statuses` de `GET /api/media/{id}` est implémenté conformément au README
- [ ] #14 Aucun code ne suppose plus « un seul artefact par type et par média » : les chemins qui faisaient cette hypothèse (écriture, lecture, contrats API) sont listés dans les Implementation Notes avec ce qui les remplace
<!-- AC:END -->
