---
id: task-392
title: Traiter un article web dont le texte a changé comme un nouveau média
status: To Do
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
- [ ] #1 Le type de source est déterminé explicitement à l'ingestion ; « article web » est un type reconnu et non le cas par défaut d'une chaîne de branches par domaine.
- [ ] #2 Pour une source de type article web, le contenu est récupéré avant que l'identité de contenu ne soit arrêtée, et une empreinte du texte récupéré entre dans cette identité.
- [ ] #3 Deux sauvegardes d'un article dont le texte a changé produisent deux identités de contenu distinctes ; deux sauvegardes d'un article inchangé produisent la même, que ce soit par le même compte ou par deux comptes différents.
- [ ] #4 Une demande d'artefact formulée après un changement de texte ne peut pas être répondue par un artefact généré sur le texte précédent.
- [ ] #5 ruff et mypy passent sans erreur sur les modules touchés.
- [ ] #6 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre les deux lignes attendues pour un article modifié entre deux sauvegardes.
<!-- AC:END -->
