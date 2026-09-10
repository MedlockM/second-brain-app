---
id: task-393
title: >-
  Fonder l'identité d'un fichier envoyé sur son contenu réel plutôt que sur son
  nom et sa taille
status: To Do
assignee: []
created_date: '2026-09-10 12:36'
labels:
  - backend
  - ingestion
  - media_identity
dependencies:
  - task-392
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les fichiers envoyés par l'utilisateur ne sont **pas** mutualisés entre comptes, et c'est voulu : leur identité de contenu porte le compte (`api/endpoints/media.py`, `media_key = f"doc:{user.id}:{file_name}:{staged.size_bytes}"` et `f"audio:{user.id}:..."`). Un document privé ne traverse donc jamais les comptes. Cette isolation est confirmée par le propriétaire et doit être conservée.

Le défaut est **à l'intérieur d'un compte** : `nom de fichier + taille en octets` n'identifie pas un contenu. Deux documents différents qui portent le même nom et font la même taille sont confondus — l'utilisateur retrouve le mauvais document. Symétriquement, le même document renvoyé sous un autre nom est traité comme neuf et repayé.

## La brique existe déjà, à un seul endroit

Le chemin de partage audio utilise une empreinte réelle (`api/endpoints/media.py`, autour de la ligne 1820) : *"A single-part PUT under SSE-S3 gives an ETag that is the MD5 of the body, so the API keeps a real content identity — the same share sent twice still lands on the same `media_key` — without ever holding the bytes to hash them."* Les deux autres chemins d'upload sont restés sur `nom:taille`.

Il s'agit donc de **généraliser un mécanisme déjà en place**, pas d'en concevoir un.

## Contrainte à respecter

L'API ne voit jamais les octets : l'envoi se fait par URL présignée directement vers S3. L'empreinte vient donc de S3 ou du client, jamais d'un hash calculé côté serveur. L'implémenteur doit vérifier ce que devient l'ETag pour un envoi multi-part ou sous chiffrement KMS, où il cesse d'être le MD5 du corps, et traiter ce cas plutôt que de supposer le cas simple.

## Périmètre

Tous les chemins d'envoi de fichier : documents et audio. L'identité de contenu d'un fichier reste scopée au compte et devient fondée sur le contenu réel. Aucune migration des envois existants : rien n'est déployé en production.

## Notes au propriétaire (hors critères d'acceptation)

Vérification manuelle après déploiement : envoyer deux fois le même fichier sous deux noms différents (un seul média attendu), puis deux fichiers différents portant le même nom et la même taille (deux médias attendus).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les chemins d'envoi de documents et d'audio dérivent l'identité de contenu d'une empreinte du contenu réel du fichier, et non de son nom ni de sa taille.
- [ ] #2 L'identité de contenu d'un fichier envoyé reste scopée au compte : deux comptes envoyant le même fichier ne partagent ni contenu ni artefacts.
- [ ] #3 Deux fichiers de contenus différents portant le même nom et la même taille produisent deux identités distinctes ; le même fichier envoyé sous deux noms différents en produit une seule.
- [ ] #4 Le cas où l'empreinte fournie par S3 n'est pas celle du corps du fichier est traité explicitement plutôt que supposé absent, et la façon dont il est traité est documentée dans les notes d'implémentation.
- [ ] #5 ruff et mypy passent sans erreur sur les modules touchés.
<!-- AC:END -->
