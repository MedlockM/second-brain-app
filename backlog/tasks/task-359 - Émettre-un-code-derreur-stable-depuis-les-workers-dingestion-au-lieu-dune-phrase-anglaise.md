---
id: task-359
title: >-
  Émettre un code d'erreur stable depuis les workers d'ingestion au lieu d'une
  phrase anglaise
status: To Do
assignee: []
created_date: '2026-09-06 10:57'
labels:
  - ingestion
  - mobile
  - i18n
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Un média Instagram en échec affiche à un testeur en `fr-FR` la phrase anglaise « Unable to extract transcribable media from this Instagram URL. ». Le défaut n'est pas l'absence de traduction : c'est que ce worker **émet une phrase au lieu d'un code**, alors que le reste de la chaîne est déjà bâti pour des codes.

## L'arbitrage est déjà tranché dans le dépôt, et il est conforme à l'état de l'art

`mobile/src/lib/getFriendlyErrorMessage.ts` mappe déjà des codes stables (`SESSION_EXPIRED`, `UNSUPPORTED_URL`, `QUOTA_EXCEEDED`, …) vers des clés de catalogue i18n, résolues **à l'appel** et non à l'import — le commentaire du fichier explique que tenir une phrase résolue figerait chaque message dans la langue de démarrage. Onze catalogues existent (`mobile/locales/*.json`) et le repli générique `media.failedFallback` est déjà là.

Deux références normatives confirment cette forme et condamnent la forme actuelle :

- **RFC 9457** (Problem Details for HTTP APIs, successeur de RFC 7807) : le `type` est un identifiant stable ; les chaînes lisibles sont négociées via `Accept-Language` / `Content-Language`, et ne sont jamais le contrat.
- **Google AIP-193** : `Status.message` est « developer-facing […] should be in English » et n'est pas destiné à l'affichage ; le message utilisateur est un champ distinct (`LocalizedMessage`, `locale` BCP-47 + `message`). Surtout : « Any request-specific information which contributes to the message must be represented within metadata. This practice is critical **so that machine actors do not need to parse error messages** to extract information. »

C'est exactement ce que fait `media_summarizer/utils/user_facing_errors.py` : du regex-matching sur le texte d'erreur (avec, en prime, des motifs français censés rattraper des messages amont). Ce module est le vestige à supprimer, pas à étendre.

## Portée

Faire émettre aux workers d'ingestion un **code d'erreur stable** accompagné de métadonnées structurées, au lieu d'une phrase. Le cas Instagram est le déclencheur : les trois sites d'émission de `instagram_ingestion_worker.py` (lignes 292, 355, 500) partagent aujourd'hui `_DEFAULT_UNSUPPORTED_MESSAGE` et ne sont discriminés que par `details`, qui part en logs.

Côté mobile, il ne devrait y avoir qu'à ajouter les clés manquantes aux catalogues : le mécanisme de résolution existe.

Cadrage `AGENTS.md`, « Nothing is deployed yet » : aucune version n'est en circulation qu'on ne puisse réémettre. On remplace le pattern-matching, on ne le fait pas cohabiter avec le nouveau contrat — pas de repli sur l'ancien chemin, pas de fenêtre de dépréciation.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle finale — rejouer une ingestion Instagram en échec et voir la phrase française dans l'app — demande un build et t'appartient.
- Si l'inventaire des causes fait apparaître qu'un code doit être ajouté au contrat côté mobile, cela reste une chaîne côté client, donc diffusable en OTA.
- Le diagnostic de la cause racine de l'échec Instagram lui-même n'est **pas** dans cette tâche : tu l'as explicitement écarté (cas isolé, pas de signal de récurrence).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Les trois sites d'émission de `instagram_ingestion_worker.py` (292, 355, 500) émettent chacun un code d'erreur stable distinct, accompagné en métadonnées structurées de l'information aujourd'hui reléguée dans `details` — le code est lisible dans le payload d'erreur, pas déductible d'une phrase
- [ ] #2 Aucun message destiné à l'affichage n'est plus produit par correspondance de motifs sur un texte d'erreur : `media_summarizer/utils/user_facing_errors.py` est supprimé et son appel dans `base_worker.py` retiré, sans chemin de repli conservé
- [ ] #3 Chaque code émis par les workers a une entrée dans `ERROR_CODE_MESSAGES` de `mobile/src/lib/getFriendlyErrorMessage.ts`, et tout code inconnu retombe sur `media.failedFallback` sans afficher de texte serveur brut
- [ ] #4 Les onze catalogues de `mobile/locales/` portent les clés ajoutées, aucune valeur laissée en anglais dans `fr.json`
- [ ] #5 `ruff` et `mypy` passent sur `media_summarizer/`, `tsc --noEmit` passe sur `mobile/`
- [ ] #6 Un enregistrement en échec écrit dans la table DynamoDB `-dev` porte le code et ses métadonnées, vérifié par une lecture directe via l'AWS CLI et la commande consignée dans les notes d'implémentation
<!-- AC:END -->
