---
id: task-394
title: Réutiliser entre comptes les artefacts déjà générés pour un même contenu média
status: To Do
assignee: []
created_date: '2026-09-10 12:36'
labels:
  - backend
  - artifacts
  - cost
dependencies:
  - task-391
  - task-392
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

La déduplication inter-comptes s'arrête au contenu. Le transcript, le titre, le créateur et la cover sont bien repris d'un traitement fait pour un autre utilisateur (`durable_media_service.finalize_deduplicated_save`, dont le `content_job` *"may belong to another user"*). Les **artefacts générés par-dessus ne le sont pas** : deux comptes qui demandent le même type sur le même contenu dans la même langue paient chacun leur génération pour un texte identique.

Une seule chose l'empêche, et elle est doublée :

- `build_artifact_id` (`artifact_service.py`) hashe `user_id | scope | scope_id | type | parameters | sources` ;
- `build_scope_key` (`core/models/media_artifact.py`) place `user_id` en tête de la clé du GSI, avec une justification assumée : *"isolation between users becomes structural, so a listing query cannot reach another account's scope"*.

Tout le reste du matériel de hachage est **déjà en identité de contenu** : `effective_scope_id = content_scope_id or scope_id` vaut le `media_key`, et `ResolvedScope.expected_source_ids` renvoie des `content_id`, pas des ids de bibliothèque. Deux comptes calculeraient donc le même `artifact_id` si `user_id` n'était pas dans le matériel.

## Décisions du propriétaire

- **La mutualisation porte sur les artefacts de scope média**, tous types confondus, `review_blurb` inclus. `ArtifactScope` n'a que deux valeurs et un artefact média est mono-source (*"a media artifact is a folder artifact with a single source"*). Les artefacts de scope dossier ne sont pas concernés.
- **L'isolation entre comptes n'est pas un objectif pour un contenu issu du web.** Un artefact dérivé d'une page publique peut être servi à un autre compte.
- **L'utilisateur est débité dans tous les cas.** Aujourd'hui le quota n'est prélevé que si `not plan.reuses_existing` (`api/endpoints/artifacts.py`) ; le gain de la mutualisation revient à l'exploitant sous forme de coût fournisseur évité, pas à l'utilisateur sous forme de quota gratuit. Le débit ne doit donc plus dépendre du fait que la génération a réellement eu lieu.

## Ce qui reste exclu de la mutualisation

Les fichiers envoyés par l'utilisateur, dont l'identité de contenu est scopée au compte (`doc:{user.id}:...`, `audio:{user.id}:...`) : un document privé ne traverse jamais les comptes, et par conséquent ses artefacts non plus. Cette exclusion découle de l'identité de contenu et ne doit pas être contournée.

## Point d'attention pour l'implémenteur

Retirer `user_id` du hash ne suffit pas : il est aussi dans la clé du GSI, qui est ce qui empêche la requête de listage d'un compte d'atteindre le scope d'un autre. Il faut donc une indirection — un pointeur par compte vers l'artefact partagé — sinon soit le listage d'un compte expose le scope d'un autre, soit l'artefact mutualisé reste introuvable. Le listage d'un utilisateur ne doit continuer de montrer que ce qu'il a lui-même demandé.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après déploiement : depuis deux comptes de test, sauvegarder la même vidéo et demander le même résumé dans la même langue ; constater un seul appel modèle côté coûts fournisseur, deux débits de quota, et un résumé identique servi aux deux bibliothèques.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deux comptes demandant le même type d'artefact sur le même contenu média, dans la même langue de lecture, sont servis par une seule génération : la seconde demande ne déclenche aucun appel au fournisseur.
- [ ] #2 La mutualisation couvre tous les types d'artefacts de scope média, review_blurb inclus, et ne s'applique pas au scope dossier.
- [ ] #3 Un artefact dérivé d'un fichier envoyé par un utilisateur n'est jamais servi à un autre compte.
- [ ] #4 Le quota de l'utilisateur est débité que la génération ait eu lieu ou qu'un artefact existant réponde à sa demande.
- [ ] #5 Le listage des artefacts d'un compte ne retourne que ceux qu'il a lui-même demandés, sans exposer l'activité d'un autre compte.
- [ ] #6 ruff et mypy passent sans erreur sur les modules touchés.
- [ ] #7 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre une entrée d'artefact unique servant deux comptes.
<!-- AC:END -->
