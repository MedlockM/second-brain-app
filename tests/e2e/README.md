# Tests E2E — Phase 4 AWS dev

Suite pytest qui valide la chaîne API + ingestion + génération d'artifacts contre une vraie API backend (par défaut : AWS dev). Reproduit les commandes curl utilisées manuellement pendant la validation Phase 4 du V1 launch plan.

## Quand les utiliser

À chaque déploiement Lambda de l'API ou des workers. Si les 6 tests du happy path passent, l'infra ne régresse pas. Sinon, le diff CloudWatch des Lambdas concernés vous dira ce qui s'est cassé.

## Prérequis

1. **Lambda déployée et joignable** : par défaut `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. Override via `API_BASE_URL`.
2. **`.env` racine pointé sur AWS dev** : `AWS_REGION=eu-west-3`, `AWS_ENDPOINT_URL=` vide, `USE_LOCALSTACK=0`. C'est le default depuis la déprécation de LocalStack (cf. task-130).
3. **Credentials AWS valides** : soit statiques (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` dans `.env`), soit un profil (`AWS_PROFILE`) résolu via la chaîne standard. Mêmes credentials qu'utilise `scripts/check_job_status.py`.
4. **Permissions DynamoDB** : le teardown supprime des items dans `users`, `auth_tokens`, `processing_jobs`, `media_artifacts`, `user_tags`, `user_folders`. L'identité IAM doit avoir `Query`, `Scan`, `DeleteItem` sur ces tables.
5. **OpenAI / Deepgram crédités** : la génération d'artifacts appelle OpenAI (et Deepgram pour audio). Compte vide = artifacts qui ne complètent jamais.

## Commandes

```bash
# Run unit tests only (E2E skipped, default behavior)
pytest

# Run E2E suite contre AWS dev
pytest -m e2e

# Run contre un autre backend (staging quand il existe)
API_BASE_URL=https://api.staging.example.com pytest -m e2e

# Cibler une autre région AWS (rare, ex re-bench staging)
AWS_REGION=eu-west-1 AWS_DEFAULT_REGION=eu-west-1 pytest -m e2e

# Un seul artifact test
pytest -m e2e tests/e2e/test_phase4_ingestion.py::test_artifact_summary_e2e -v

# Health check seul (le plus rapide)
pytest -m e2e tests/e2e/test_health.py -v

# Skeletons des sources non encore validées
pytest -m e2e tests/e2e/test_phase4_other_sources.py -v
```

## Structure

| Fichier | Rôle |
|---|---|
| `conftest.py` | Fixtures partagées + teardown automatique |
| `test_health.py` | `GET /api/health/` → 200 + `database: connected` |
| `test_phase4_ingestion.py` | Article Wikipedia + 4 artifact types |
| `test_phase4_other_sources.py` | Skeletons xfail/skip pour podcast, X, TikTok, IG, PDF, YouTube |
| `test_transcript_translation.py` | task-192 : reading_language=fr + Reel Instagram anglais → artifact ET transcript brut (`/raw-content`) traduits en fr ; vérifie aussi que le pré-chauffage synchrone côté worker Deepgram (avant `mark_completed`) rend le premier `/raw-content` rapide (non-régression timeout API Gateway) |

## Cleanup automatique

La fixture `test_user` (scope session) crée un user avec un email horodaté `e2e-test-<timestamp>-<uuid6>@test.local`. À la fin de la session, peu importe si les tests ont passé ou planté, le teardown :

1. Liste les processing_jobs, tags et folders du user
2. Pour chaque processing_job, supprime tous les artifacts associés via la GSI `media-item-index` de `media_artifacts`
3. Supprime les processing_jobs eux-mêmes
4. Supprime tags et folders
5. Se re-logue pour obtenir un access token frais, puis supprime le user via `DELETE /api/account` (puis fallback DynamoDB direct)
6. Supprime les auth_tokens **en dernier**, y compris ceux créés par ce login

La route de suppression est authentifiée et déduit le compte de la session : elle
ne prend aucun id (`task-224`), et purge l'intégralité des données du compte, pas
seulement la ligne `users`. Le teardown se re-logue juste avant le DELETE plutôt que de
réutiliser la fixture `auth_token` (scope session), qui peut avoir expiré sur une
run longue. Si le login échoue, le teardown passe directement au fallback
DynamoDB.

Chaque opération est isolée par `try/except` — un échec partiel ne bloque pas le reste, et ne fait pas planter le test. Les erreurs sont imprimées dans la sortie pytest sous la forme `[e2e] <op> failed: <repr>`.

**Limite connue** : si pytest est interrompu brutalement (Ctrl-C entre deux tests, kill -9), le teardown ne tourne pas et le user reste en DynamoDB. La prochaine run crée un nouveau user avec un timestamp différent — pas de conflit, juste de la dette à nettoyer manuellement de temps en temps via :

```bash
# Liste les users de test résiduels
aws dynamodb scan --region eu-west-3 \
  --table-name users \
  --filter-expression "begins_with(email, :p)" \
  --expression-attribute-values '{":p":{"S":"e2e-test-"}}'
```

## Vérifier le teardown

```bash
# Avant la run
COUNT_BEFORE=$(aws dynamodb scan --region eu-west-3 --table-name users \
  --filter-expression "begins_with(email, :p)" \
  --expression-attribute-values '{":p":{"S":"e2e-test-"}}' \
  --select COUNT --output json | jq .Count)

pytest -m e2e

COUNT_AFTER=$(aws dynamodb scan --region eu-west-3 --table-name users \
  --filter-expression "begins_with(email, :p)" \
  --expression-attribute-values '{":p":{"S":"e2e-test-"}}' \
  --select COUNT --output json | jq .Count)

echo "Avant: $COUNT_BEFORE / Après: $COUNT_AFTER"
# Doit afficher la même valeur des deux côtés
```

## Promouvoir un skeleton en happy path

Quand une source non encore validée (podcast, X, TikTok, IG, PDF) commence à passer :

1. Tester manuellement contre AWS dev avec une URL réelle
2. Si la source atteint `completed`, dans `test_phase4_other_sources.py` :
   - Remplacer `@pytest.mark.skip(...)` ou `@pytest.mark.xfail(...)` par juste `@pytest.mark.e2e`
   - Renommer le test pour retirer le suffixe `_skip` / `_xfail`
   - Optionnellement déplacer le test dans `test_phase4_ingestion.py` si on veut le couvrir avec les artifacts aussi

Pour YouTube spécifiquement, attendre la résolution de task-126 (benchmark stratégies extraction) avant de toucher.

## Coût d'une run

À l'unité (toute la suite, ~30s) :
- Lambda invocations × ~10
- DynamoDB ops × ~50
- S3 ops × ~6 (transcript + 4 artifacts uploads + reads)
- OpenAI ~ 4 prompts complets sur l'article Wikipedia (~$0.05 cumulé sur gpt-4-mini)
- Deepgram : 0 (pas d'audio)

Total estimé < $0.10 par run. Pas un problème pour du dev manuel ; à monitorer si on intègre au CI plus tard.
