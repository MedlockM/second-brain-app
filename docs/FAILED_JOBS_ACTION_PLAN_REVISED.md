# Plan d'Action Révisé : Gestion des Jobs Failed

## 🎯 Corrections Basées sur la Review

### **🔴 HAUTE PRIORITÉ**

#### 1. ✅ Corriger l'Incohérence de Statut
**Status** : Approuvé

**Action** : Modifier `email_worker.py` pour ne marquer "completed" QUE pour les emails de succès.

#### 2. 📧 Email d'Erreur Révisé
**Feedback** : Ne PAS inviter à réessayer (c'est automatique toutes les 24h)

**Nouveau Template** :
```python
async def send_error_notification(
    recipient: str,
    job_id: str,
    error_message: str,
    step: Optional[str] = None
) -> Dict[str, Any]:
    subject = "Error processing your podcast episode"
    
    body_text = f"""We encountered an error while processing your podcast episode.

Job ID: {job_id}
Error occurred during: {step or 'processing'}

What happens next:
• Our system will automatically retry processing this episode
• If the issue persists, our team will be notified
• You don't need to do anything - we'll handle it

Technical details (for debugging):
{error_message}

The Media Summarizer Team"""
    
    # HTML version similaire
```

#### 3. 🔍 Logging & Alerting

**État Actuel** :
- ✅ CloudWatch Logs configurés pour les Lambdas
- ✅ SNS Topic existe pour le scaling
- ❌ Pas d'alerting spécifique pour les jobs failed
- ❌ Logs pas structurés pour faciliter le debug

**Actions Recommandées** :

##### A. Améliorer le Logging Structuré
**Fichier** : Tous les workers

**Avant** :
```python
logger.error(f"Failed to process job {job_id}: {e}")
```

**Après** :
```python
logger.error(
    "Job processing failed",
    extra={
        "job_id": job_id,
        "user_id": job.user_id,
        "error_step": step,
        "error_type": type(e).__name__,
        "error_message": str(e),
        "retry_count": job.retry_count,
        "traceback": traceback.format_exc()
    }
)
```

**Avantage** : Permet de créer des filtres CloudWatch précis.

##### B. CloudWatch Metric Filters
**Terraform** : `infrastructure/terraform/aws/monitoring.tf` (nouveau fichier)

```hcl
# Metric filter pour compter les erreurs par étape
resource "aws_cloudwatch_log_metric_filter" "job_failures" {
  name           = "JobFailures"
  log_group_name = aws_cloudwatch_log_group.workers.name
  pattern        = "[time, request_id, level=ERROR, msg=\"Job processing failed\", ...]"

  metric_transformation {
    name      = "JobFailureCount"
    namespace = "MediaSummarizer/Jobs"
    value     = "1"
    dimensions = {
      ErrorStep = "$error_step"
    }
  }
}

# Alarme si > 5 erreurs en 5 minutes
resource "aws_cloudwatch_metric_alarm" "high_job_failure_rate" {
  alarm_name          = "high-job-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "JobFailureCount"
  namespace           = "MediaSummarizer/Jobs"
  period              = "300"  # 5 minutes
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Alert when job failure rate is high"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
}

# SNS Topic pour les alertes opérationnelles
resource "aws_sns_topic" "ops_alerts" {
  name = "media-summarizer-ops-alerts"
}

# Subscription email
resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.ops_alert_email  # À définir dans variables.tf
}
```

##### C. CloudWatch Insights Queries
**Queries pré-configurées** pour debug rapide :

```sql
-- Top 10 erreurs par type
fields error_type, error_step, count(*) as error_count
| filter level = "ERROR" and msg = "Job processing failed"
| stats count(*) as error_count by error_type, error_step
| sort error_count desc
| limit 10

-- Jobs failed pour un utilisateur spécifique
fields @timestamp, job_id, error_step, error_message
| filter user_id = "USER_ID_HERE"
| filter level = "ERROR"
| sort @timestamp desc

-- Taux d'échec par heure
fields bin(@timestamp, 1h) as hour, count(*) as failures
| filter level = "ERROR" and msg = "Job processing failed"
| stats count(*) as failures by hour
```

##### D. LocalStack Support
**Disponible dans LocalStack** :
- ✅ CloudWatch Logs
- ✅ CloudWatch Metrics (basic)
- ⚠️ CloudWatch Alarms (limité)
- ❌ CloudWatch Insights (pas supporté)

**Pour le dev local** :
- Utiliser des logs structurés JSON
- Parser avec `jq` ou scripts Python
- Simuler les alertes avec des scripts de monitoring

---

### **🟡 MOYENNE PRIORITÉ**

#### 3. 🔄 Système de Retry Automatique

**État Actuel** : ❌ N'existe PAS (le code du modèle existe mais n'est jamais utilisé)

**Implémentation Recommandée** :

##### Option A : Retry au Niveau du Worker (Immédiat)
**Fichier** : `media_summarizer/workers/base_worker.py`

```python
async def process_job_with_retry(job_id: str, process_func):
    """
    Process a job with automatic retry on failure.
    
    Args:
        job_id: Job ID to process
        process_func: Async function to execute
    """
    job = await database_async.get_processing_job_by_id(job_id)
    
    try:
        await process_func(job)
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", extra={
            "job_id": job_id,
            "error": str(e),
            "retry_count": job.retry_count
        })
        
        if job.can_retry():
            # Increment retry and re-queue
            job.increment_retry()
            await database_async.update_processing_job(job)
            
            # Re-send to appropriate queue based on current step
            queue_name = get_queue_for_step(job.status)
            await sqs.send_message(
                queue_name=queue_name,
                message_body={"job_id": job_id},
                delay_seconds=60 * (2 ** job.retry_count)  # Exponential backoff
            )
            logger.info(f"Job {job_id} queued for retry {job.retry_count}/{job.max_retries}")
        else:
            # Max retries reached
            job.mark_failed(str(e), get_current_step(job))
            await database_async.update_processing_job(job)
            
            # Send final failure notification
            await sqs.send_message(
                queue_name="email-notification-queue",
                message_body={
                    "notification_type": "error",
                    "job_id": job_id,
                    "email": job.user_email,
                    "error": f"Max retries ({job.max_retries}) exceeded",
                    "step": get_current_step(job)
                }
            )
```

##### Option B : Worker de Retry Dédié (Plus robuste)
**Nouveau fichier** : `media_summarizer/workers/retry/retry_worker.py`

**Déclenchement** : EventBridge schedule (toutes les 5 minutes)

**Avantages** :
- Centralisé
- Peut gérer les jobs "coincés" (stuck)
- Indépendant des workers de traitement

**Inconvénients** :
- Plus complexe
- Nécessite un index DynamoDB sur `status`

**Recommandation** : **Option A** pour commencer (plus simple), puis Option B si besoin.

#### 4. 📊 Dashboard de Monitoring

**Question** : "Tu parles d'un dashboard dans AWS ?"

**Réponse** : Plusieurs options :

##### Option A : CloudWatch Dashboard (Natif AWS)
**Terraform** :
```hcl
resource "aws_cloudwatch_dashboard" "jobs_monitoring" {
  dashboard_name = "media-summarizer-jobs"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["MediaSummarizer/Jobs", "JobFailureCount", { stat = "Sum" }],
            [".", "JobSuccessCount", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Job Success vs Failure Rate"
        }
      },
      {
        type = "log"
        properties = {
          query = "fields @timestamp, job_id, error_step | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          region = var.aws_region
          title  = "Recent Job Failures"
        }
      }
    ]
  })
}
```

**Avantages** :
- Natif AWS, pas de code supplémentaire
- Gratuit (dans les limites)
- Accessible via console AWS

**Inconvénients** :
- Pas très customisable
- Pas d'actions (retry manuel, etc.)

##### Option B : Dashboard Custom (API + Frontend)
**Nouveau endpoint** : `/api/v1/admin/jobs/failed`

**Frontend** : Page admin dans le dashboard React

**Avantages** :
- Totalement customisable
- Actions possibles (retry manuel, voir logs, etc.)
- Peut inclure des métriques business

**Inconvénients** :
- Plus de code à maintenir
- Nécessite authentification admin

**Recommandation** : **Option A** (CloudWatch) pour commencer, Option B si besoin de fonctionnalités avancées.

---

### **🟢 BASSE PRIORITÉ**

#### 5. 🚨 Système d'Alerting Exhaustif

**Propositions** :

##### A. Alertes CloudWatch → SNS → Email
**Déjà couvert ci-dessus** (section Haute Priorité #3)

##### B. Alertes CloudWatch → SNS → Slack
**Terraform** :
```hcl
resource "aws_sns_topic_subscription" "slack_webhook" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "https"
  endpoint  = var.slack_webhook_url
  
  # Nécessite un Lambda pour transformer le format SNS → Slack
  endpoint_auto_confirms = false
}

# Lambda pour formater les messages Slack
resource "aws_lambda_function" "sns_to_slack" {
  filename      = "sns_to_slack.zip"
  function_name = "sns-to-slack-forwarder"
  role          = aws_iam_role.lambda_sns_to_slack.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  
  environment {
    variables = {
      SLACK_WEBHOOK_URL = var.slack_webhook_url
    }
  }
}
```

**Code Lambda** :
```python
import json
import urllib3

http = urllib3.PoolManager()

def handler(event, context):
    message = json.loads(event['Records'][0]['Sns']['Message'])
    
    slack_message = {
        "text": f"🚨 *Job Failure Alert*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Alarm*: {message['AlarmName']}\n*Description*: {message['AlarmDescription']}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in CloudWatch"},
                        "url": f"https://console.aws.amazon.com/cloudwatch/..."
                    }
                ]
            }
        ]
    }
    
    http.request(
        'POST',
        SLACK_WEBHOOK_URL,
        body=json.dumps(slack_message),
        headers={'Content-Type': 'application/json'}
    )
```

##### C. Alertes CloudWatch → SNS → Discord
**Similaire à Slack**, mais avec webhook Discord

##### D. Alertes CloudWatch → SNS → PagerDuty
**Pour incidents critiques** (production down, etc.)

##### E. Alertes Personnalisées par Sévérité
```hcl
# Critique : > 10 erreurs en 5 min → PagerDuty
resource "aws_cloudwatch_metric_alarm" "critical_failure_rate" {
  alarm_name          = "critical-job-failure-rate"
  threshold           = "10"
  alarm_actions       = [aws_sns_topic.pagerduty_alerts.arn]
}

# Warning : > 5 erreurs en 5 min → Slack
resource "aws_cloudwatch_metric_alarm" "warning_failure_rate" {
  alarm_name          = "warning-job-failure-rate"
  threshold           = "5"
  alarm_actions       = [aws_sns_topic.slack_alerts.arn]
}

# Info : > 1 erreur en 5 min → Email
resource "aws_cloudwatch_metric_alarm" "info_failure_rate" {
  alarm_name          = "info-job-failure-rate"
  threshold           = "1"
  alarm_actions       = [aws_sns_topic.email_alerts.arn]
}
```

##### F. Alertes Basées sur des Patterns Spécifiques
```hcl
# Alerte si erreur LLM API (comme dans les jobs de test@example.com)
resource "aws_cloudwatch_log_metric_filter" "llm_api_errors" {
  name           = "LLMAPIErrors"
  log_group_name = aws_cloudwatch_log_group.workers.name
  pattern        = "[time, request_id, level=ERROR, msg, error_type=LLMAPIError, ...]"

  metric_transformation {
    name      = "LLMAPIErrorCount"
    namespace = "MediaSummarizer/Errors"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "llm_api_errors" {
  alarm_name          = "llm-api-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "LLMAPIErrorCount"
  namespace           = "MediaSummarizer/Errors"
  period              = "300"
  statistic           = "Sum"
  threshold           = "3"
  alarm_description   = "LLM API is experiencing issues"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
}
```

#### 6. 🗑️ Cleanup des Jobs Failed

**Question** : "Ne devrait-on pas les garder pour X ou Y raison ?"

**Réponse** : OUI, il faut les garder mais avec une stratégie :

##### Stratégie Recommandée : Archivage Progressif

**Phase 1 : Chaud (0-7 jours)**
- **Stockage** : DynamoDB (table principale)
- **Usage** : Debug actif, retry, monitoring
- **Coût** : Normal

**Phase 2 : Tiède (7-30 jours)**
- **Stockage** : DynamoDB avec TTL ou S3
- **Usage** : Analyse post-mortem, statistiques
- **Coût** : Réduit

**Phase 3 : Froid (30+ jours)**
- **Stockage** : S3 Glacier
- **Usage** : Compliance, audit, analytics long-terme
- **Coût** : Minimal

**Implémentation** :

```python
# Worker de cleanup quotidien
async def cleanup_old_failed_jobs():
    """Archive failed jobs older than 7 days."""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Query failed jobs older than cutoff
    # (Nécessite un GSI sur status + created_at)
    old_failed_jobs = await database_async.query_jobs_by_status_and_date(
        status="failed",
        before_date=cutoff_date
    )
    
    for job in old_failed_jobs:
        # Archive to S3
        archive_key = f"archived-jobs/{job.created_at.year}/{job.created_at.month}/{job.id}.json"
        await s3.upload_file(
            bucket="media-summarizer-archives",
            key=archive_key,
            content=json.dumps(job.to_dynamodb_item())
        )
        
        # Delete from DynamoDB
        await database_async.delete_processing_job(job.id)
        
        logger.info(f"Archived job {job.id} to S3: {archive_key}")
```

**Raisons de Garder les Jobs Failed** :
1. **Analytics** : Identifier les patterns d'erreurs récurrentes
2. **Compliance** : Prouver qu'on a essayé de traiter (facturation)
3. **Debug** : Reproduire les erreurs
4. **Métriques Business** : Taux de succès, SLA, etc.
5. **Audit** : Traçabilité pour les utilisateurs premium

**Configuration DynamoDB TTL** :
```hcl
resource "aws_dynamodb_table" "processing_jobs" {
  # ... config existante ...
  
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }
}
```

**Dans le code** :
```python
# Lors de la création du job
job.ttl_timestamp = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
```

---

## 📋 Plan d'Action Révisé

### **Phase 1 : Corrections Immédiates** (2-3 heures)
1. ✅ Corriger le bug de statut dans `email_worker.py`
2. ✅ Améliorer l'email d'erreur (pas d'invitation à retry)
3. ✅ Ajouter logging structuré dans tous les workers
4. ✅ Implémenter retry au niveau du worker (Option A)

### **Phase 2 : Monitoring & Alerting** (4-6 heures)
1. ✅ Créer CloudWatch Metric Filters
2. ✅ Créer CloudWatch Alarms
3. ✅ Configurer SNS → Email
4. ⚠️ (Optionnel) SNS → Slack/Discord

### **Phase 3 : Optimisations** (optionnel)
1. CloudWatch Dashboard
2. Worker de retry dédié (Option B)
3. Système d'archivage automatique
4. Dashboard admin custom

---

## 🎯 Recommandation Finale

**À faire MAINTENANT** :
1. Phase 1 complète (corrections + retry)
2. Logging structuré
3. Alarme CloudWatch basique (> 5 erreurs/5min → Email)

**À planifier** :
- Slack/Discord integration (si l'équipe l'utilise)
- Dashboard CloudWatch
- Archivage automatique

**Voulez-vous que je commence par implémenter la Phase 1 ?**
