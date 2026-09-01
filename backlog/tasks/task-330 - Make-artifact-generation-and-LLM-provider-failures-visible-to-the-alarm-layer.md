---
id: task-330
title: Make artifact-generation and LLM-provider failures visible to the alarm layer
status: To Do
assignee: []
created_date: '2026-09-01 16:42'
labels:
  - observability
  - artifacts
  - terraform
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

On 2026-09-01 the backend stopped producing any artifact for an entire test session — the OpenAI credit was exhausted — and **no automated signal could have fired**. Two distinct reasons, the second being the more troubling:

### 1. No alarm covers artifact-generation failure or an LLM-provider refusal

The 19 `aws_cloudwatch_metric_alarm` blocks in the `platform` module cover API p95 latency, the 5xx rate, DLQ depth, Lambda errors and throttles, Deepgram, the LlamaParse fallback, the job archiver, the `user_media` lifecycle and the RevenueCat tier. Nothing covers "the LLM refuses to answer".

### 2. `lambda_error_rate` gives false assurance on exactly these workers

That alarm computes `100 * Errors / Invocations` on `AWS/Lambda` (`infrastructure/terraform/modules/platform/pipeline_alerts.tf:153-201`) for every worker in `local.lambda_workers`, `artifact_generator` and `transcript_translation` included. But `media_summarizer/workers/lambda_handlers.py:83` reports failures through `batchItemFailures` **without raising**, and the translation worker even catches its own failure internally. So `Errors` stayed at **0** while 3 artifact generations and 25 translation invocations were failing. The DLQs stayed empty for the same reason.

An error rate built on `Errors` structurally cannot see these outages. A reader looking at the alarm list would conclude the pipeline was covered.

## Scope

What is missing is an **application metric the alarm layer can observe**, not one more alarm on a blind one. Emit it from the two workers that call the LLM, alarm on it the way the module already alarms on everything else, and leave a note next to `lambda_error_rate` so nobody trusts it for these workers again.

`enable_alarms = false` in dev is a deliberate cost decision (confirmed by the owner) — this task does not change it.

## Owner note

`enable_alarms = false` holds for `staging` (`infrastructure/terraform/envs/staging/main.tf:86`) and `prod` (`infrastructure/terraform/envs/prod/main.tf:91`) too, so none of the module's alarms is deployed anywhere. Flipping prod to `true` and subscribing an address to the SNS topic is a launch prerequisite, out of scope here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The artifact generation worker emits a CloudWatch application metric when generation fails, distinguishing an LLM-provider refusal (quota, authentication, rate limit) from a failure of any other nature
- [x] #2 The transcript translation worker emits the same family of metric on its own failure path
- [x] #3 The namespace, metric name and dimensions are documented where the repo already documents the pipeline alarms
- [x] #4 An aws_cloudwatch_metric_alarm covers those metrics, gated by var.enable_alarms like every other alarm in the module, with an alarm_description pointing at a runbook as the existing ones do, and a name that keeps the environment suffix the alarm-naming check requires
- [x] #5 A comment next to lambda_error_rate records that it cannot detect a failure reported through batchItemFailures, so the next reader does not rely on it for the worker Lambdas
- [x] #6 enable_alarms stays false in the dev, staging and prod envs
- [x] #7 terraform validate passes on the platform module and on the dev env; ruff and mypy pass on the changed Python modules
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### La métrique applicative est un log event, pas un put_metric_data

Les 19 alarmes du module lisent toutes des métriques produites par des
`aws_cloudwatch_log_metric_filter` sur les événements JSON structurés
(`revenucat_alerts.tf`, `durable_media_alerts.tf`, `pipeline_alerts.tf`) : dans ce
dépôt l'application n'appelle jamais `put_metric_data`. La métrique ajoutée suit
la même voie — `media_summarizer/utils/llm_failures.py` définit l'événement
`llm.generation_failed`, deux filtres (un par log group de worker LLM) le
convertissent en `LlmGenerationFailures`. Un appel `put_metric_data` depuis les
workers aurait ajouté une dépendance IAM `cloudwatch:PutMetricData`, un appel
réseau dans le chemin d'échec (celui qui est déjà en train d'échouer) et une
seconde façon de produire une métrique dans un module qui n'en avait qu'une.

### Une seule métrique, dimensionnée, plutôt que deux noms

`LlmGenerationFailures` porte la dimension `FailureKind` = `provider_refused` |
`other`, au lieu de deux métriques distinctes. Le refus du provider est classé
par `refusal_reason_for_status()` à partir du statut HTTP : 401/403 →
`authentication`, 402 → `quota`, 429 → `quota` si le corps contient un marqueur
de facturation (`insufficient_quota`, `billing`, `exceeded your current quota`),
`rate_limit` sinon. La distinction quota/rate limit compte parce qu'elle sépare
« l'owner doit recharger le compte » de « ça repassera tout seul », mais les deux
sont le même refus vu de la couche d'alarme, donc elles partagent
`failure_kind = provider_refused` et se lisent dans le champ `refusal_reason` de
l'événement. Une clé manquante est classée `authentication` : une clé absente et
une clé révoquée sont la même panne et demandent la même action.

Conséquence côté Terraform : un seul bloc `aws_cloudwatch_metric_alarm` avec
`for_each` sur une map de locals produit les deux alarmes avec deux seuils. Une
alarme sur une métrique dimensionnée doit fixer la valeur de sa dimension, d'où
une alarme par `failure_kind`.

### Le vrai angle mort était la traduction, qui n'échoue pas en levant

Le worker d'artifacts lève et laisse `lambda_handlers.py` transformer
l'exception en `batchItemFailures` ; l'événement est émis juste avant le
`raise`. Le worker de traduction, lui, ne voit aucune exception dans le cas
principal : `ensure_translated_transcript()` attrape sa propre
`TranscriptTranslationError` et retourne un `TranslationOutcome` avec
`translation_failed = True`. Classer ce cas demandait de faire remonter la raison
sans parser le message d'erreur : `TranscriptTranslationError` porte désormais
`refusal_reason` et `provider_status`, `_translate_with_retry` les reconduit sur
son raise terminal, et `TranslationOutcome` expose
`translation_refusal_reason` que le worker lit pour émettre. Trois points
d'émission dans ce worker : l'erreur terminale, l'exception inattendue, et le
`outcome.translation_failed` — le seul des trois où rien du tout n'était
observable auparavant.

### Seuils

`provider_refused` : seuil 0 sur 5 minutes, severity critical. Il n'y a pas de
niveau de fond acceptable pour un provider qui nous refoule, et aucun retry ne
sauve la situation. `other` : seuil 3 sur 15 minutes, severity high — un artifact
condamné brûle ses 3 livraisons SQS et émet 3 événements, donc >3 est le premier
compte qui signifie autre chose qu'une génération malchanceuse. Les deux alarmes
sont en `treat_missing_data = "notBreaching"`, obligatoire ici : CloudWatch
refuse un `default_value` sur une transformation dimensionnée, donc la métrique
n'a pas de point à 0 quand rien n'échoue.

### La note à côté de lambda_error_rate

16 lignes en tête du bloc `lambda_error_rate` (`pipeline_alerts.tf`) qui
énoncent ce que cette alarme ne peut pas voir : la factory
`_build_handler` (`media_summarizer/workers/lambda_handlers.py`) attrape par
record, ajoute à `batchItemFailures` et retourne 200, donc `Errors` reste à 0.
L'alarme ne couvre que ce qui casse *en dehors* du try/except par record — cold
start, timeout, OOM, mauvais chemin de handler. La note renvoie vers
`llm_alerts.tf`, `durable_media_alerts.tf` et les alarmes de l'archiver pour les
questions de résultat.

### Vérifications

- `ruff` : All checks passed. `mypy media_summarizer` : Success, no issues in 178
  source files.
- `terraform fmt -check -recursive` propre ; `terraform validate` Success sur le
  module `platform` et sur `envs/dev`.
- `aws logs test-metric-filter` sur le vrai CloudWatch avec le pattern
  `{ $.event = "llm.generation_failed" }` : les deux formes d'événement (worker
  artifact et worker traduction) matchent, un événement voisin ne matche pas.
- `terraform plan` réel sur `envs/dev` : `Plan: 2 to add, 0 to change, 0 to
  destroy` — les deux filtres seulement, suffixés `-dev`, et aucune alarme
  puisque `enable_alarms = false` (ce plan est aussi la preuve de l'AC #6 : dev,
  staging et prod restent à `false`, non touchés).
- Les deux noms d'alarme ont été vérifiés via un root Terraform jetable avec
  `enable_alarms = true`, planifiés comme
  `media-summarizer-llm-provider-refused-dev` et
  `media-summarizer-llm-generation-failures-dev` — suffixe d'environnement conforme
  à la garde de nommage de `scripts/tf_plan_guard.sh`. Le root jetable a été
  supprimé.

Aucune alarme n'a pu être poussée en `ALARM` puis `OK` : `enable_alarms = false`
partout, donc aucune des deux n'existe dans AWS. Le déclenchement réel est à
vérifier par l'owner après le flip de prod mentionné dans la note de la
description.
<!-- SECTION:NOTES:END -->
