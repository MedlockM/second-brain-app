---
id: task-387
title: >-
  Implémenter l'artefact podcast audio sur un média et un dossier, selon le
  benchmark validé (task-386)
status: To Do
assignee: []
created_date: '2026-09-09 15:59'
labels:
  - backend
  - artifacts
  - feature
dependencies:
  - task-386
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'il faut faire

Ajouter un **sixième type d'artefact demandable par l'utilisateur** : un podcast audio généré sur un média ou sur un dossier, via la surface existante `POST /api/artifacts`.

**L'implémenteur commence par lire `docs/research/task-386-podcast-artifact-generation/README.md`, section `Owner Validation` → `Decision`** (et les fichiers `complement-response-*.md` que la décision cite éventuellement). C'est cette décision qui fixe : la solution retenue et son mode de reprise (dépendance, copie-adaptation, réimplémentation), le fournisseur TTS, l'identifiant du type, le jeu de `parameters`, l'assemblage audio, l'enveloppe de calcul, le canal de livraison et la règle de comptage. **Rien de tout cela n'est à décider ici**, et rien de ce qui suit ne doit être lu comme une préférence : la présente description ne décrit que les points d'ancrage dans le code, qui ne dépendent pas de la décision.

## Les points d'ancrage, quelle que soit la décision

- **Le type** entre dans `MediaArtifactType` (`core/models/media_artifact.py:32`) et dans `REQUESTABLE_ARTIFACT_TYPES` (`core/services/artifact_service.py:117`). `DEFAULT_ARTIFACT_TYPES_ALLOWED` est dérivé de l'énumération, donc il le contient sans qu'on y touche ; `_allowed_artifact_types()` (`:390`) le laisse passer.
- **Le générateur** s'enregistre dans `GENERATORS` (`workers/artifact_generator/generators/__init__.py`) et implémente le protocole `ArtifactGenerator` (`generators/base.py`). Le script se construit avec `corpus.build_prompt` comme les cinq autres : **le préfixe partagé décrit en tête de `generators/corpus.py` ne doit pas être cassé** — c'est lui qui fait payer le corpus une fois pour cinq types côté cache OpenAI.
- **`build_artifact_storage_key` (`artifact_service.py:382`) suffixe `.json` en dur.** Il doit rendre l'extension du média réellement écrit, et `ArtifactStorageRef.content_type` (`media_artifact.py:95`) porter le vrai type MIME. Pas de couche de compatibilité : les cinq types existants passent par la même fonction corrigée.
- **Un bucket par type** : nouveau bucket dans `s3.tf` avec `prevent_destroy`, exposé dans `runtime_env.tf` (les autres y sont lignes 83-95), lu par `get_artifact_bucket` (`:362`), et droits accordés dans `iam_lambda.tf`.
- **Le quota** se débite dans `api/endpoints/artifacts.py:287-330`, dans un ordre qui ne change pas : verdict de réutilisation → contrôle du quota → écriture. `quota_enforcer.check_generation_allowed` (`quota_enforcer.py:757`) ne connaît aujourd'hui que « média = gratuit, dossier = 1 minute pour 5 sources ».
- **Les `parameters`** sont validés par `ArtifactCreateRequest` (`artifacts.py:80`) et normalisés par `normalize_artifact_parameters` (`artifact_service.py:286`) ; ils entrent dans `build_artifact_id` (`:408`). Conséquence à assumer telle quelle : jeu identique = réutilisation sans génération, jeu différent = nouvel artefact.
- **La langue de sortie** vient de `current_user.reading_language` (`artifacts.py:272`) et passe par `language_instruction` (`corpus.py:95`). Rien à inventer : le podcast se parle dans la langue de lecture de l'utilisateur.
- **La livraison** ne peut pas passer par `GET /api/artifacts/{id}/content` (`artifacts.py:578`), qui télécharge le blob et inline le JSON parsé. Le canal est celui que le README décide.
- **Le bail** : `GENERATION_LEASE_SECONDS = 300` est aligné sur le timeout de la Lambda `artifact_generator` (512 MB / 300 s, `lambda_workers.tf:55-60`). Si la décision change ce timeout ou déplace le calcul ailleurs, le bail suit — un worker tué en vol doit laisser une entrée réclamable, pas une entrée bloquée en `generating`.
- **Pas de ffmpeg dans l'image**, et c'est un choix : `core/services/audio_duration_probe.py` a été écrit pour mesurer une durée sans lui. Si la décision impose un assembleur, c'est une addition consciente à justifier en commentaire, pas un détail d'installation.

## Hors périmètre

- **Le lecteur mobile** : sa propre tâche, qui dépend de celle-ci.
- **Une génération automatique** en fin d'ingestion. Le type est demandé par l'utilisateur, il n'entre pas dans `INTERNAL_ARTIFACT_TYPES`.
- **Le clonage de la voix de l'utilisateur.**
- **Toute compatibilité** avec des artefacts déjà stockés : rien n'est déployé, aucun backfill, aucun double format (`AGENTS.md`, « Nothing is deployed yet »).

## Notes à l'owner (pas des ACs)

1. **Le bucket n'existera qu'après un push sur `main`** : `terraform-dev.yml` applique le root dev sur push. L'implémenteur ne peut aller que jusqu'à `terraform validate` et un `plan` qui montre la création. Vérifier ensuite `aws s3api head-bucket` et un `POST /api/artifacts` réel.
2. **Le credential du fournisseur retenu doit être provisionné** (secret + env runtime) avant tout E2E : sans lui, la génération échouera avec une erreur d'authentification, ce qui n'est pas un défaut de câblage.
3. **L'E2E qui compte** : demander un podcast sur un média, puis sur un dossier de plusieurs sources, écouter le fichier, vérifier la durée obtenue face à la durée demandée, et le débit de minutes sur le compte.
4. **Une re-soumission de la même demande est une réutilisation**, pas une nouvelle génération : pour regénérer, il faut des `parameters` différents ou un dossier dont les sources ont changé.
5. **Coût réel** : c'est le premier artefact dont le coût dépend de la longueur de la sortie. Surveiller `llm_usage` / la facture du fournisseur sur les premiers épisodes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le README `docs/research/task-386-podcast-artifact-generation/README.md` est lu et les Implementation Notes citent la décision de l'owner appliquée : solution retenue, fournisseur, identifiant du type, `parameters`, assemblage, enveloppe de calcul, canal de livraison, règle de comptage.
- [ ] #2 Le type existe dans `MediaArtifactType` sous l'identifiant que le README nomme et dans `REQUESTABLE_ARTIFACT_TYPES` ; il n'est pas dans `INTERNAL_ARTIFACT_TYPES`, donc il apparaît dans l'historique de scope et se demande via `POST /api/artifacts`.
- [ ] #3 Un générateur est enregistré dans `GENERATORS`, implémente le protocole de `generators/base.py` et construit son script via `corpus.build_prompt`. Les cinq générateurs existants ne sont pas modifiés et le préfixe de cache partagé décrit en tête de `generators/corpus.py` reste intact.
- [ ] #4 `build_artifact_storage_key` ne suffixe plus `.json` en dur : la clé porte l'extension du média réellement écrit pour chaque type, et `ArtifactStorageRef.content_type` porte le type MIME réel de l'objet. Aucun chemin de compatibilité n'est conservé pour l'ancienne forme.
- [ ] #5 Un bucket S3 dédié au type est déclaré dans `s3.tf` avec `prevent_destroy`, exposé au runtime dans `runtime_env.tf` à côté des autres buckets d'artefacts, lu par `get_artifact_bucket`, et les droits S3 correspondants sont accordés dans `iam_lambda.tf` aux rôles qui écrivent et lisent l'objet.
- [ ] #6 L'enveloppe de calcul décidée par le README est appliquée en Terraform, et `GENERATION_LEASE_SECONDS` reste aligné sur le timeout effectif du chemin qui génère ce type — le commentaire qui accompagne la constante dit sur quoi elle est alignée.
- [ ] #7 La livraison des octets audio suit la décision du README et ne passe pas par `GET /api/artifacts/{id}/content`. Le contrat est écrit dans `docs/CANONICAL_MEDIA_API_CONTRACT.md` et dans `docs/CANONICAL_MEDIA_API_OPENAPI.yaml`.
- [ ] #8 `quota_enforcer.check_generation_allowed` applique au type la règle de comptage du README, l'ordre existant dans `api/endpoints/artifacts.py` (réutilisation → quota → écriture) est inchangé, et la règle est commentée à l'endroit du code avec un renvoi à task-287 et à task-386.
- [ ] #9 Les `parameters` que le README expose sont validés par `ArtifactCreateRequest` (valeurs hors domaine refusées avec un code d'erreur typé) et traversés par `normalize_artifact_parameters`, donc entrent dans `build_artifact_id`. Un commentaire énonce la conséquence : jeu identique = réutilisation, jeu différent = nouvel artefact.
- [ ] #10 Le credential du fournisseur retenu est lu par le même mécanisme que les autres (`secrets.tf` + env runtime), son absence produit un échec explicite et tracé, et aucune valeur de credential n'apparaît dans le dépôt.
- [ ] #11 Un échec en cours de synthèse laisse une entrée `failed` avec un `error_code` typé et jamais un `ready` dont l'audio serait incomplet ou tronqué ; ce que deviennent les segments déjà produits suit ce que dit le README.
- [ ] #12 `utils/infra_check.py` connaît le nouveau type et son bucket, de sorte qu'un environnement où le bucket manque est signalé par le contrôle d'infra plutôt que par un échec de génération.
- [ ] #13 `ruff check` et `mypy` passent sur `media_summarizer/`, et `terraform validate` passe sur les roots touchés. Un `terraform plan` sur le root dev est consigné dans les Implementation Notes, montrant la création du bucket et la modification du worker — l'apply se fait au push sur `main`, hors de portée de l'implémenteur.
- [ ] #14 Les Implementation Notes consignent une vérification directe contre `-dev` de ce qui existe déjà et conditionne le câblage : la queue `artifact-generator-queue` et la table `media_artifacts` avec son GSI `scope-index`, interrogées via l'AWS CLI en `--region eu-west-3` (l'`AWS_REGION` du shell pointe ailleurs).
<!-- AC:END -->
