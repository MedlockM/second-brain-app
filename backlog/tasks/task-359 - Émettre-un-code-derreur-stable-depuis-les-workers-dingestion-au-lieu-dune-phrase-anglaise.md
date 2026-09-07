---
id: task-359
title: >-
  Émettre un code d'erreur stable depuis les workers d'ingestion au lieu d'une
  phrase anglaise
status: Done
assignee: []
created_date: '2026-09-06 10:57'
updated_date: '2026-09-07 00:00'
labels:
  - ingestion
  - mobile
  - i18n
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Un média Instagram en échec affiche à un testeur en `fr-FR` la phrase anglaise « Unable to extract transcribable media from this Instagram URL. ». Le défaut n'est pas l'absence de traduction : c'est que les workers **émettent une phrase au lieu d'un code**, alors que le reste de la chaîne est déjà bâti pour des codes. Instagram est le cas qui l'a révélé, pas le périmètre.

## L'arbitrage est déjà tranché dans le dépôt, et il est conforme à l'état de l'art

`mobile/src/lib/getFriendlyErrorMessage.ts` mappe déjà des codes stables (`SESSION_EXPIRED`, `UNSUPPORTED_URL`, `QUOTA_EXCEEDED`, …) vers des clés de catalogue i18n, résolues **à l'appel** et non à l'import — le commentaire du fichier explique que tenir une phrase résolue figerait chaque message dans la langue de démarrage. Onze catalogues existent (`mobile/locales/*.json`) et le repli générique `media.failedFallback` est déjà là. Le client n'a donc rien à inventer : c'est le serveur qui ne tient pas sa part du contrat.

Deux références normatives confirment cette forme et condamnent la forme actuelle :

- **RFC 9457** (Problem Details for HTTP APIs, successeur de RFC 7807) : le `type` est un identifiant stable ; les chaînes lisibles sont négociées via `Accept-Language` / `Content-Language`, et ne sont jamais le contrat.
- **Google AIP-193** : `Status.message` est « developer-facing […] should be in English » et n'est pas destiné à l'affichage ; le message utilisateur est un champ distinct (`LocalizedMessage`, `locale` BCP-47 + `message`). Surtout : « Any request-specific information which contributes to the message must be represented within metadata. This practice is critical **so that machine actors do not need to parse error messages** to extract information. »

C'est exactement ce que fait `media_summarizer/utils/user_facing_errors.py` : du regex-matching sur le texte d'erreur, avec en prime des motifs français censés rattraper des messages amont. Ce module est le vestige à supprimer, pas à étendre.

## Portée : globale, décidée par l'owner

Le correctif ne se limite pas à Instagram. L'inventaire mesuré au moment de l'écriture :

- **68 occurrences de `user_message=`**, réparties sur les quatre workers d'ingestion : `instagram_ingestion_worker.py`, `tiktok_ingestion_worker.py`, `x_ingestion_worker.py`, `youtube_ingestion_worker.py` ;
- **un filet de rattrapage** en `base_worker.py:99`, qui applique `get_user_facing_error_message(str(e))` à toute exception non gérée — c'est lui qui rend le pattern-matching global plutôt que local à un worker.

Le cas déclencheur reste instructif pour dimensionner les codes : les trois sites de `instagram_ingestion_worker.py` (lignes 292 `apify_result_invalid`, 355 `resolver_non_retryable`, 500 `no_transcript_or_audio_url`) partagent aujourd'hui `_DEFAULT_UNSUPPORTED_MESSAGE` et ne sont discriminés que par `details`, qui part en logs. Trois causes sans rapport entre elles, un seul texte affiché : c'est la démonstration que la phrase ne peut pas servir d'identifiant.

Côté mobile, il ne devrait y avoir qu'à ajouter les clés manquantes aux catalogues : le mécanisme de résolution existe et ne change pas.

Cadrage `AGENTS.md`, « Nothing is deployed yet » : aucune version n'est en circulation qu'on ne puisse réémettre. On remplace le pattern-matching, on ne le fait pas cohabiter avec le nouveau contrat — pas de repli sur l'ancien chemin, pas de fenêtre de dépréciation, pas de conservation de `user_facing_errors.py` « au cas où ».

## Notes pour l'owner (pas des ACs)

- La vérification visuelle finale — rejouer une ingestion en échec et voir la phrase française dans l'app — demande un build et t'appartient.
- Les clés ajoutées côté mobile sont des chaînes JS : diffusables en OTA, sans consommer de build.
- Le diagnostic de la cause racine de l'échec Instagram n'est **pas** dans cette tâche : tu l'as écarté explicitement (cas isolé, pas de signal de récurrence). Cette tâche garantit seulement qu'un tel échec sera désormais lisible, et discriminable par son code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Aucun message destiné à l'affichage n'est plus produit par correspondance de motifs sur un texte d'erreur : `media_summarizer/utils/user_facing_errors.py` est supprimé et son appel dans `base_worker.py` retiré, sans chemin de repli conservé
- [x] #2 Chaque code émis par les workers a une entrée dans `ERROR_CODE_MESSAGES` de `mobile/src/lib/getFriendlyErrorMessage.ts`, et tout code inconnu retombe sur `media.failedFallback` sans afficher de texte serveur brut
- [x] #3 Les onze catalogues de `mobile/locales/` portent les clés ajoutées, aucune valeur laissée en anglais dans `fr.json`
- [x] #4 `ruff` et `mypy` passent sur `media_summarizer/`, `tsc --noEmit` passe sur `mobile/`
- [x] #5 Un enregistrement en échec écrit dans la table DynamoDB `-dev` porte le code et ses métadonnées, vérifié par une lecture directe via l'AWS CLI et la commande consignée dans les notes d'implémentation
- [x] #6 Les 68 sites `user_message=` des quatre workers d'ingestion (`instagram`, `tiktok`, `x`, `youtube`) émettent un code d'erreur stable au lieu d'une phrase, l'information contextuelle passant en métadonnées structurées — inventaire exhaustif, aucun `user_message=` littéral ne subsiste dans `media_summarizer/workers/`

- [x] #7 Le filet de rattrapage de `base_worker.py:99`, qui devine un message en faisant correspondre des motifs sur `str(e)`, est remplacé par un code générique unique : une exception non gérée produit un code, jamais une phrase déduite de son texte
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Ce qui a été construit

Un vocabulaire unique, `MediaFailureCode` (`media_summarizer/core/models/failure_codes.py`, 23 membres), et une exception de base partagée, `IngestionFailure` (`media_summarizer/workers/ingestion_failures.py`), qui porte trois choses distinctes :

- `code` — le `MediaFailureCode`, seule information d'échec qui atteint l'app ;
- `details` — le token d'observabilité en lower-snake, c'est-à-dire l'ancien code interne du worker, **conservé mot pour mot** pour ne pas casser les requêtes de logs et les runbooks ;
- `**context` — les faits structurés (`http_status`, `apify_run_id`, `content_type`, `timeout_seconds`, `exception_type`…), qui partent dans `ProcessingJob.error_metadata` à côté de `reason`.

Les fragments variables qui étaient autrefois interpolés dans le code interne (`apify_terminal_FAILED`, `subtitle_http_status:502`, `processing_job_not_found:<id>`, `resolver_non_retryable:<exc>`) sont devenus des tokens fixes plus des clés de contexte — c'est le cœur de l'AC #6.

Aucune phrase de provider n'est persistée : le libellé d'origine survit en CloudWatch via `exc_info=exc` sur le `log_event` terminal, tandis que `error_metadata` reste structuré. `error_metadata` n'est servi que par le routeur opérationnel `GET /jobs/{job_id}` ; le contrat bibliothèque (`GET /api/media/{id}`) ne l'expose pas, ce qui garantit de bout en bout le « sans texte serveur brut » de l'AC #2.

### AC #5 — écriture et relecture sur le DynamoDB `-dev`

Un enregistrement en échec a été produit par le vrai chemin de code (`ProcessingJob.mark_failed()` puis `to_dynamodb_item()`, via un script jetable hors dépôt) et écrit dans `processing_jobs-dev`. La relecture directe :

```
AWS_REGION=eu-west-3 aws dynamodb get-item \
  --table-name processing_jobs-dev \
  --key '{"id":{"S":"job_task359_probe_instagram"}}' \
  --projection-expression "id,job_status,error_code,error_metadata,error_step" \
  --output json
```

a renvoyé :

```json
{"Item": {
  "error_code":     {"S": "NO_TRANSCRIBABLE_MEDIA"},
  "error_metadata": {"M": {"reason":  {"S": "no_transcript_or_audio_url"},
                           "step":    {"S": "instagram_ingestion"},
                           "provider":{"S": "apify"},
                           "apify_run_id": {"S": "run_task359_probe"}}},
  "error_step":     {"S": "instagram_ingestion"},
  "id":             {"S": "job_task359_probe_instagram"},
  "job_status":     {"S": "failed"}
}}
```

Aucun attribut `error_message` dans l'item. La ligne sonde a ensuite été supprimée (`aws dynamodb delete-item`, même clé) : elle n'appartenait à aucun compte réel (`user_id="task-359-probe"`, e-mail synthétique en `example.invalid`).

### Correction factuelle sur l'AC #3

L'AC #3 et la description parlent de `mobile/locales/*.json` pour « les onze catalogues ». C'est inexact : ces JSON ne portent que les chaînes natives d'`app.config` (`CFBundleDisplayName`, `NSPhotoLibraryUsageDescription`…). Les vrais catalogues d'interface sont `mobile/src/i18n/{en,fr,es,de,it,pt,nl,ja,zh,ar,hi}.ts`, où `TranslationKey = keyof typeof en` — une clé absente de `en.ts` est donc une erreur `tsc`, et les dix autres langues sont vérifiées par le type `Catalog`. Les 18 clés `mediaError.*` ont été ajoutées là, entièrement traduites dans les onze langues, aucune valeur laissée en anglais.

`media.processingFailed` a perdu son dernier consommateur (le hook lit désormais le repli `media.failedFallback` imposé par l'AC #2) et a été supprimée des onze catalogues dans la même passe.

### Vérifications

- `ruff check media_summarizer/` → *All checks passed!*
- `mypy media_summarizer/` → *Success: no issues found in 181 source files*
- `cd mobile && npm run typecheck` → aucune sortie (propre)
- `cd mobile && npm run lint` → 0 erreur, 2 avertissements préexistants dans des fichiers non touchés (`app/(tabs)/digest.tsx`, `src/services/purchaseService.ts`)

Aucun test automatisé n'a été ajouté, conformément à la règle du dépôt.

### Reste à la charge de l'owner

La vérification visuelle finale — rejouer une ingestion en échec et lire la phrase française dans l'app — demande un déploiement puis un build, hors de portée d'un worktree.
<!-- SECTION:NOTES:END -->
