---
id: task-382
title: >-
  Alerter par mail sur un nouveau rapport de bug et supprimer le routage Discord
  mort
status: Done
assignee: []
created_date: '2026-09-08 16:43'
labels:
  - backend
  - infrastructure
  - cleanup
dependencies:
  - task-381
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

`POST /api/bug-reports` écrit un rapport dans `bug_reports-dev` puis appelle `BugReportService.route_to_triage`, qui poste un embed sur un webhook Discord — **mais seulement si `BUG_REPORT_ROUTING_WEBHOOK` est défini**, et cette variable est absente de `infrastructure/terraform/modules/platform/runtime_env.tf`. Vérifié le 2026-09-08 : seuls `BUG_REPORTS_TABLE` et `BUG_REPORTS_BUCKET` y sont câblés. Le code prend donc systématiquement la branche `logger.debug("No BUG_REPORT_ROUTING_WEBHOOK configured, skipping routing.")`.

Autrement dit **un rapport de bug atterrit en silence dans DynamoDB**. La table en contient déjà 2, jamais annoncées à personne. Et `docs/community/bug-reports.md` affirme le contraire, noir sur blanc : « Routed in real-time to the triage Discord channel via webhook », puis « A new embed appears in the Discord `#bug-reports` channel » comme première étape du triage. La doc décrit un mécanisme qui n'a jamais tourné.

Discord n'est pas le canal d'alerte de ce projet — le mail l'est, et tout l'outillage d'alarmes existant en atteste : chaque `*_alerts.tf` route ses alarmes vers le topic SNS `pipeline_alerts`, dont l'abonnement `pipeline_alerts_email` est créé dès que `var.alert_email` est renseigné.

## Ce qu'on veut

**1. Une alerte mail sur création de rapport**, par le mécanisme du module et pas un autre. La convention est explicite dans `media_summarizer/utils/llm_failure.py` : « per the module convention metrics are derived from log metric filters and the application never calls `put_metric_data` ». Donc trois maillons, tous déjà en place ailleurs :

- l'application émet un événement structuré via `log_event(logger, level, event, message, **fields)` (`media_summarizer/utils/logging_config.py:259`) — aujourd'hui `create_bug_report` se contente d'une f-string `logger.info(f"Bug report created: id=...")`, illisible par un filtre ;
- un `aws_cloudwatch_log_metric_filter` sur `aws_cloudwatch_log_group.lambda_api` transforme l'événement en métrique, sur le motif de `revenucat_tier_unresolved` (`revenucat_alerts.tf:27-38`) ;
- un `aws_cloudwatch_metric_alarm` gardé par `var.enable_alarms`, `alarm_actions = [aws_sns_topic.pipeline_alerts[0].arn]`.

Seuil `0`, comme les alarmes de `revenucat_alerts.tf` : il n'existe pas de niveau de fond acceptable de rapports de bug qu'on ignore. Un rapport, un mail.

**2. La suppression du chemin Discord.** `route_to_triage`, son embed, la constante `BUG_REPORT_ROUTING_WEBHOOK` et l'appel `try/except` dans `create_bug_report` disparaissent. Rien ne lit ce code, aucune variable ne l'active, et le canal retenu est le mail. C'est de l'échafaudage à supprimer, pas une option à garder : il n'y a **aucun** utilisateur installé à ménager (`AGENTS.md`, section « Nothing is deployed yet »), donc pas de webhook à préserver « au cas où ».

**3. La correction de `docs/community/bug-reports.md`** pour qu'elle décrive ce qui tourne : le mail comme alerte, le scan DynamoDB comme lecture, et plus une ligne sur Discord — y compris dans la section « Data retention » qui parle de purger des messages Discord, et dans « How to triage » dont l'étape 1 est un embed Discord.

## Pourquoi cette tâche dépend de task-381 et pas l'inverse

Les deux touchent `media_summarizer/core/services/bug_report_service.py` et l'endpoint `bug_reports.py`, dans des régions voisines de `create_bug_report` — les faire en parallèle produirait un conflit. Et l'ordre utile est celui-ci : task-381 ajoute `media_item_id` et `error_code` au rapport, donc l'événement structuré écrit ici peut les porter en champs, ce qui rend la demande de prise en charge d'une source distinguable d'un rapport générique venu de l'onglet Compte. L'inverse obligerait à repasser sur le `log_event` juste après.

## Ce que l'implémenteur n'a pas à chercher

- Le topic et l'abonnement mail **existent déjà** : `aws_sns_topic.pipeline_alerts` et `aws_sns_topic_subscription.pipeline_alerts_email` (`pipeline_alerts.tf:16-33`). Aucune adresse n'est committée dans le dépôt, par convention : l'abonnement se crée dès que `var.alert_email` est passé à l'apply. Ne rien créer de neuf de ce côté.
- `local.metrics_namespace` et `local.suffix` sont déjà définis dans le module et utilisés par tous les `*_alerts.tf`.
- Le motif de nommage d'une métrique est CamelCase (`RevenueCatTierUnresolved`, `DurableMediaWriteFailed`), celui d'un `event` de log est `domaine.verbe_au_participe` (`revenucat.tier_unresolved`, `llm.generation_failed`).
- Le limiteur de débit `_rate_limit_store` de `bug_reports.py` est un `dict` en mémoire de processus, donc poreux sur Lambda. Dette assumée existante : **hors périmètre.**

## Hors périmètre

- **Le contenu du mail.** SNS envoie le corps de l'alarme CloudWatch ; on ne construit pas de rendu sur mesure, et on n'ajoute pas de Lambda de formatage.
- **Un tableau de bord ou une intégration Linear**, que la doc évoque comme futur. Le scan DynamoDB reste le mode de lecture.
- **L'écran `mobile/app/bug-report.tsx`** et le service mobile : aucun changement côté client.
- **Le bucket S3 des pièces jointes** et son cycle de vie à 90 jours : inchangés.

## Notes à l'owner (pas des ACs)

1. **L'alarme ne peut être vérifiée qu'après déploiement**, l'apply Terraform et le push sur `main` arrivant après le passage de l'implémenteur. À faire ensuite : envoyer un rapport depuis l'app, confirmer l'arrivée du mail, puis vérifier que l'alarme repasse en `OK`.
2. **Si `var.alert_email` n'a jamais été passé sur `-dev`**, l'abonnement n'existe pas et aucun mail ne partira quoi que fasse cette tâche. À contrôler avant de conclure à une panne :
   ```
   aws sns list-subscriptions-by-topic --region eu-west-3 \
     --topic-arn $(aws sns list-topics --region eu-west-3 \
     --query "Topics[?contains(TopicArn,'pipeline-alerts-dev')].TopicArn" --output text)
   ```
   `AWS_REGION` vaut `us-east-1` dans le shell alors que l'infra est en `eu-west-3` : `--region` est obligatoire.
3. **Les 2 rapports déjà présents dans `bug_reports-dev`** n'ont jamais été lus. Ils valent un coup d'œil pendant cette tâche.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `create_bug_report` émet la création par `log_event` (`media_summarizer/utils/logging_config.py:259`) avec un `event` structuré nommé selon la convention `domaine.verbe_au_participe`, portant au minimum l'identifiant du rapport, `source_platform`, `source_app_version` et — quand ils sont présents — le `media_item_id` et l'`error_code` introduits par task-381. La f-string `logger.info(f"Bug report created: ...")` ne subsiste pas.
- [x] #2 Un `aws_cloudwatch_log_metric_filter` sur `aws_cloudwatch_log_group.lambda_api` transforme cet événement en métrique dans `local.metrics_namespace`, avec `value = "1"` et `default_value = "0"`, sur le motif de `revenucat_tier_unresolved` (`revenucat_alerts.tf:27-38`).
- [x] #3 Un `aws_cloudwatch_metric_alarm` gardé par `count = var.enable_alarms ? 1 : 0` déclenche sur cette métrique avec un seuil de `0`, et route vers `aws_sns_topic.pipeline_alerts[0].arn` en `alarm_actions`. Son `alarm_description` dit quoi faire et cite une section ajoutée à `infrastructure/observability/runbooks/pipeline-alerts.md`, sur le motif des descriptions de `durable_media_alerts.tf` — aucun nouveau fichier de runbook n'est créé.
- [x] #4 Aucun nouveau topic SNS ni abonnement mail n'est créé : `aws_sns_topic.pipeline_alerts` et `aws_sns_topic_subscription.pipeline_alerts_email` sont réutilisés tels quels, et aucune adresse mail n'apparaît dans un fichier du dépôt.
- [x] #5 `BugReportService.route_to_triage`, son embed Discord, l'import `httpx` s'il ne sert plus qu'à lui, la constante `BUG_REPORT_ROUTING_WEBHOOK` et l'appel `try/except` correspondant dans `create_bug_report` sont supprimés. `grep -rn 'route_to_triage\|BUG_REPORT_ROUTING_WEBHOOK\|discord' media_summarizer/` ne renvoie plus rien.
- [x] #6 `docs/community/bug-reports.md` ne mentionne plus Discord une seule fois — ni dans « Where reports go », ni dans « Who responds », ni à l'étape 1 de « How to triage », ni dans la ligne « Discord messages » de « Data retention / RGPD » — et décrit à la place l'alerte mail via SNS et la lecture par scan de la table `bug_reports`.
- [x] #7 `docs/community/bug-reports.md` donne la commande de lecture exacte des rapports, avec `--region eu-west-3` explicite puisque `AWS_REGION` du shell pointe ailleurs.
- [x] #8 `terraform validate` passe dans `infrastructure/terraform/`, et `terraform fmt -check` ne signale aucun écart sur les fichiers touchés.
- [x] #9 `ruff check` et `mypy` passent sur `media_summarizer/`.
<!-- AC:END -->

## Implementation Notes

### Changes Made

**Code Cleanup:**
- Removed `BugReportService.route_to_triage()` method completely (166-202 lines deleted from `bug_report_service.py`)
- Removed `BUG_REPORT_ROUTING_WEBHOOK` environment variable constant
- Removed `import httpx` (no longer needed)
- Removed try/except block calling `route_to_triage` in `bug_reports.py` (lines 251-255)
- Updated docstrings to remove Discord references

**Event Logging:**
- Added `from media_summarizer.utils.logging_config import log_event` to `bug_report_service.py`
- Replaced `logger.info(f"Bug report created: ...")` f-string with structured `log_event` call
- Event name: `bug_report.created` (follows `domaine.verbe_au_participe` convention)
- Event fields: `report_id`, `user_id`, `source_platform`, `source_app_version`, `media_item_id`, `error_code`

**Terraform Infrastructure:**
- Created `infrastructure/terraform/modules/platform/bug_report_alerts.tf` with:
  - `aws_cloudwatch_log_metric_filter.bug_report_created`: filters on `$.event = "bug_report.created"`
  - `aws_cloudwatch_metric_alarm.bug_report_created`: threshold 0, routes to `aws_sns_topic.pipeline_alerts[0].arn`
  - Uses existing `local.metrics_namespace` and `local.suffix`
  - Gated on `var.enable_alarms` following module convention

**Documentation:**
- Added "Bug Reports" section to `infrastructure/observability/runbooks/pipeline-alerts.md` with:
  - Alarm name, severity, threshold
  - Event schema and field descriptions
  - Investigation steps with exact AWS CLI commands (--region eu-west-3 explicit)
  - First response and escalation guidance
- Updated table of contents to include new section
- Updated `docs/community/bug-reports.md`:
  - Removed all Discord references (4 locations per AC #6)
  - Updated "Overview" to describe SNS email alerts
  - Updated "Where reports go" table to reference SNS
  - Updated "Who responds" to mention email notifications and DynamoDB scanning
  - Updated "Data retention" to replace Discord messages line with email retention note
  - Updated "How to triage" to add exact AWS CLI command with --region eu-west-3

### Verification

- `grep -rn 'route_to_triage\|BUG_REPORT_ROUTING_WEBHOOK\|discord' media_summarizer/` returns no results ✓
- `terraform validate` passes ✓
- `terraform fmt -check` on new file passes ✓
- `ruff check media_summarizer/` passes ✓
- `mypy media_summarizer/` passes ✓

### Deployment Notes

The alarm will fire when `var.enable_alarms = true` and `var.alert_email` is configured on apply. The existing SNS topic and email subscription are reused per module convention — no new resources are created. Alert emails will be routed to the same address that receives all other pipeline alerts.

The 2 existing bug reports in `bug_reports-dev` are unaffected and will remain in DynamoDB; the alarm only fires on new reports created after this code deploys.
