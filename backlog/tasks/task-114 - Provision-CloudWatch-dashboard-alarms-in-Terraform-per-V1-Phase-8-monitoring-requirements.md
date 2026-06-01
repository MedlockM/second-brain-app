---
id: task-114
title: >-
  Provision CloudWatch dashboard + alarms in Terraform per V1 Phase 8 monitoring
  requirements
status: To Do
assignee: []
created_date: '2026-06-01 13:58'
labels:
  - infra
  - monitoring
  - v1
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Phase 8 du `docs/V1_LAUNCH_PLAN.md` (« Monitoring & observabilité »). Le repo a déjà `infrastructure/terraform/pipeline_dashboard.tf` et `infrastructure/terraform/pipeline_alerts.tf` qui datent de l'archi ECS. Suite à la migration Lambda (task-106), une partie des widgets/alarmes pointe sur des ressources ECS qui n'existent plus, et il manque les widgets/alarmes spécifiques aux nouvelles ressources Lambda + API Gateway HTTP API + tables/queues récentes.

Ce ticket aligne la Phase 8 sur l'architecture Lambda actuelle.

## Audit préalable attendu

L'agent doit d'abord auditer ce qui existe et ce qui manque :

- Lire `pipeline_dashboard.tf` et `pipeline_alerts.tf` actuels et identifier les widgets/alarmes orphelins (références ECS, `scaling.tf`, `download-queue`, etc.).
- Lister toutes les ressources Lambda nouvelles via `infrastructure/terraform/lambda_workers.tf` (locals.workers map, ~13 fonctions) et `lambda_api.tf` (1 fonction API).
- Lister toutes les queues SQS via `infrastructure/terraform/sqs.tf` (chacune a sa DLQ).
- Identifier les sources d'erreur métier non encore monitorées : LlamaParse 4xx/5xx, Unstructured fallback déclenché, Apify cost runaway, Deepgram échecs.

## Scope d'implémentation

1. **Nettoyer les widgets/alarmes orphelins** :
   - Retirer toute référence à `aws_ecs_*`, `download-queue`, `scaling_controller`, `whisper`, ou autre ressource supprimée.

2. **Dashboard CloudWatch** (`pipeline_dashboard.tf`) :
   - **API Gateway HTTP API** : latence p50/p95/p99, count 4xx/5xx, count par route majeure (`/api/media/ingest-url`, `/api/media/ingest-shared-content`, `/api/media/{id}`).
   - **Lambda workers** : par fonction, métriques `Invocations`, `Errors`, `Duration p95`, `Throttles`, `ConcurrentExecutions`.
   - **SQS** : profondeur de queue (`ApproximateNumberOfMessagesVisible`) pour chaque queue + sa DLQ. Une seule rangée de 14 widgets compacts (un par queue/DLQ).
   - **Coût par source** : log metric filters sur `source_platform=youtube|tiktok|instagram|x|podcast|article|document` qui agrègent un compteur par 5 min, affichés en stacked area.
   - **Quota LlamaParse** : compteur de calls LlamaParse vs Unstructured (logs metric filters sur `parser=llamaparse` et `parser=unstructured`).
   - **Quota Apify** : compteur d'appels Apify (logs metric filters sur `provider=apify` + actor type) — utile pour tracker la consommation de credits.

3. **Alarms CloudWatch** (`pipeline_alerts.tf`) :
   - **API latency** : p95 > `API_SLOW_REQUEST_THRESHOLD_MS` pendant 5 min consécutives.
   - **API 5xx rate** : `5XX_count / total_count > 1%` sur 5 min.
   - **DLQ depth** : alarme si **n'importe quelle DLQ** > 0 messages pendant 5 min (cf. `pipeline-alerts.md` runbook qui le mentionne explicitement pour `document-parsing-queue`).
   - **Lambda errors** : par fonction, alarme si error rate > 5% sur 10 min.
   - **Lambda throttles** : alarme si throttles > 0 sur 5 min.
   - **Deepgram error rate** : log metric filter `transcript_source=deepgram error_code=*` → alarme si > 5% des deepgram calls en erreur sur 15 min.
   - **LlamaParse → Unstructured fallback** : alarme si fallback Unstructured déclenché plus de N fois/heure (signal que le quota LlamaParse free tier 1000 pages/jour est épuisé).
   - Toutes les alarmes routent vers le SNS topic existant `aws_sns_topic.scaling_alerts` (renommer en `pipeline_alerts` si pertinent) → email subscription owner.

4. **SNS topic + subscription** :
   - Créer ou conserver un SNS topic `media-summarizer-pipeline-alerts-<env>`.
   - Subscription email vers `var.alert_email` (à ajouter dans `variables.tf` si manquant).
   - Subscription confirmée par l'owner manuellement après `terraform apply` (mentionné dans Implementation Notes).

5. **Logs structurés à exploiter** :
   - L'agent doit vérifier que les workers émettent bien les champs nécessaires (`source_platform`, `parser`, `provider`, `transcript_source`, `error_code`) dans les logs structurés. Si un champ manque pour un widget/alarme, le mentionner dans Implementation Notes — **ne pas modifier** le code worker dans ce ticket.

## Hors-scope

- Modifier le code des workers pour émettre de nouveaux champs structurés : si un champ manque, le ticket le note et un follow-up sera créé.
- Datadog, Grafana, ou autre alternative : on reste sur CloudWatch en V1.
- Coûts AWS facturés (CloudWatch Synthetics, X-Ray) : pas activés en V1.
- Runbooks détaillés par alarme : `infrastructure/observability/runbooks/pipeline-alerts.md` existe déjà, à mettre à jour si nouvelle alarme l'exige.

## Vérification

- `terraform validate && terraform plan` sur l'env dev passe sans erreur, montre la création du dashboard, des alarmes, et des metric filters attendus.
- `aws cloudwatch describe-alarms` après `terraform apply` montre toutes les alarmes en état `OK` initial.
- Le dashboard CloudWatch (Console AWS → CloudWatch → Dashboards) affiche tous les widgets sans erreur "no data" tant qu'aucun trafic réel n'est généré (les widgets doivent juste être valides côté config).
- Test de bout-en-bout : envoyer un message dans une queue avec un payload qui force une erreur worker → DLQ se remplit → alarme `DLQ depth > 0` se déclenche → email reçu.

## Contexte fichiers utiles

- `infrastructure/terraform/pipeline_dashboard.tf` — dashboard actuel à auditer/réécrire.
- `infrastructure/terraform/pipeline_alerts.tf` — alarmes actuelles à auditer/réécrire.
- `infrastructure/terraform/lambda_workers.tf` — locals.workers map qui définit les 13 fonctions Lambda.
- `infrastructure/terraform/lambda_api.tf` — Lambda FastAPI.
- `infrastructure/terraform/sqs.tf` — toutes les queues + DLQ.
- `infrastructure/observability/runbooks/pipeline-alerts.md` — runbook ops à mettre à jour.
- `media_summarizer/utils/logging_config.py` — confirmer les champs structurés disponibles.
- `docs/LOGGING_SYSTEM.md` — référence des événements et champs loggés.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 pipeline_dashboard.tf et pipeline_alerts.tf ne contiennent plus aucune référence ECS / scaling_controller / download-queue / whisper
- [ ] #2 Le CloudWatch dashboard expose : API Gateway latency p50/p95/p99, 4xx/5xx counts, route counters, Lambda Invocations/Errors/Duration p95/Throttles par fonction, SQS queue depth pour chaque queue + DLQ, log-metric counters par source_platform, parser, provider
- [ ] #3 Alarme : API latency p95 > API_SLOW_REQUEST_THRESHOLD_MS pendant 5 min
- [ ] #4 Alarme : API 5xx rate > 1% sur 5 min
- [ ] #5 Alarme : DLQ depth > 0 sur 5 min, pour CHAQUE DLQ déclarée dans sqs.tf
- [ ] #6 Alarme : Lambda errors > 5% sur 10 min, par fonction Lambda
- [ ] #7 Alarme : Lambda throttles > 0 sur 5 min
- [ ] #8 Alarme : Deepgram error rate > 5% sur 15 min via log metric filter
- [ ] #9 Alarme : fallback Unstructured déclenché plus de N fois/heure (N paramétrable via variable Terraform)
- [ ] #10 Toutes les alarmes routent vers un SNS topic dédié + subscription email vers var.alert_email
- [ ] #11 terraform validate + terraform plan passent sans erreur sur l'env dev
- [ ] #12 Implementation Notes liste : (a) tout champ structuré manquant dans les logs workers qui empêche un widget/alarme, (b) la confirmation manuelle de la subscription SNS à effectuer par l'owner après apply, (c) si runbook pipeline-alerts.md doit être mis à jour
<!-- AC:END -->
