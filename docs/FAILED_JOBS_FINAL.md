# Corrections Finales : Gestion des Jobs Failed

## ✅ **Corrections Implémentées**

### 1. **Déduplication Intelligente avec Gestion des Retries**
**Fichier** : `media_summarizer/utils/user_episode_submissions.py`

**Logique** :
- ✅ **Succès** : Bloque la re-soumission
- ✅ **Failed avec retries restants** (retry_count < max_retries) : Autorise retry
- ✅ **Failed après max retries** (retry_count >= max_retries) : Bloque la re-soumission
- ✅ **En cours** : Bloque pour éviter les duplicatas

**Résultat** : Le cron Spotify Sync ne retentera PAS les jobs qui ont épuisé leurs retries.

### 2. **Email d'Erreur User-Friendly**
**Fichier** : `media_summarizer/workers/notification/email_worker.py`

**Changements** :
- ❌ **Supprimé** : Détails techniques (job_id, error_step, error_message)
- ✅ **Ajouté** : Message simple et professionnel en anglais
- ✅ **Logging** : Détails techniques loggés pour debug (pas envoyés à l'utilisateur)

**Template** :
```
Subject: Unable to Process Your Podcast Episode

We're sorry, but we were unable to process your podcast episode.

Our team has been notified and is working to resolve the issue.

We apologize for any inconvenience this may cause.

Best regards,
The Media Summarizer Team
```

---

## 🔍 **Analyse des Systèmes de Retry Existants**

### **Retry au Niveau LLM** ✅
**Fichier** : `media_summarizer/workers/summarization/summarization_worker.py`
**Ligne** : 195

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_summary_with_retry(transcription_text: str, job_data: Dict[str, Any]):
    # Appel LLM avec retry automatique
```
    max_retries: int,
    traceback_info: str
) -> None:
    """
    Send detailed technical alert to ops team when a job fails permanently.
    """
    subject = f"🚨 Job Failed Permanently: {job_id}"
    
    body_text = f"""Job Processing Failed After Max Retries

Job ID: {job_id}
User Email: {user_email}
Error Step: {error_step}
Retry Count: {retry_count}/{max_retries}

Error Message:
{error_message}

Stack Trace:
{traceback_info}

CloudWatch Logs:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/media-summarizer-workers

DynamoDB Job:
Job ID: {job_id}

Action Required:
- Investigate the root cause
- Check if this is a recurring issue
- Consider manual retry if appropriate
"""
    
    body_html = f"""
    <html>
    <body style="font-family: monospace; font-size: 12px;">
        <h2 style="color: #e74c3c;">🚨 Job Failed Permanently</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr><td style="font-weight: bold;">Job ID:</td><td>{job_id}</td></tr>
            <tr><td style="font-weight: bold;">User Email:</td><td>{user_email}</td></tr>
            <tr><td style="font-weight: bold;">Error Step:</td><td>{error_step}</td></tr>
            <tr><td style="font-weight: bold;">Retry Count:</td><td>{retry_count}/{max_retries}</td></tr>
        </table>
        
        <h3>Error Message:</h3>
        <pre style="background: #f4f4f4; padding: 10px; border-radius: 5px;">{error_message}</pre>
        
        <h3>Stack Trace:</h3>
        <pre style="background: #f4f4f4; padding: 10px; border-radius: 5px; max-height: 300px; overflow-y: auto;">{traceback_info}</pre>
        
        <h3>Quick Links:</h3>
        <ul>
            <li><a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/media-summarizer-workers">CloudWatch Logs</a></li>
            <li><a href="https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=processing_jobs">DynamoDB Jobs Table</a></li>
        </ul>
    </body>
    </html>
    """
    
    # Send to ops team email (from environment variable)
    ops_email = os.environ.get("OPS_ALERT_EMAIL", "ops@media-summarizer.com")
    
    await ses.send_email(
        recipient=ops_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        sender=os.environ.get("DEFAULT_EMAIL_SENDER", "alerts@media-summarizer.com")
    )
```

**Déclenchement** : Appeler cette fonction quand un job atteint max_retries.

#### **2.2 CloudWatch Dashboard** (Option A)

**Terraform** : `infrastructure/terraform/aws/monitoring.tf`

```hcl
resource "aws_cloudwatch_dashboard" "jobs_monitoring" {
  dashboard_name = "media-summarizer-jobs"

  dashboard_body = jsonencode({
    widgets = [
      # Widget 1: Job Success vs Failure Rate
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Jobs", "JobSuccessCount", { stat = "Sum", label = "Success" }],
            [".", "JobFailureCount", { stat = "Sum", label = "Failures" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Job Success vs Failure Rate (5min)"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      
      # Widget 2: Failures by Step
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["MediaSummarizer/Jobs", "JobFailureCount", { stat = "Sum", dimensions = { ErrorStep = "download" } }],
            ["...", { dimensions = { ErrorStep = "transcription" } }],
            ["...", { dimensions = { ErrorStep = "summarization" } }],
            ["...", { dimensions = { ErrorStep = "notification" } }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Failures by Processing Step"
        }
      },
      
      # Widget 3: Recent Failed Jobs (Logs)
      {
        type   = "log"
        width  = 24
        height = 6
        properties = {
          query  = <<-EOT
            fields @timestamp, job_id, user_id, error_step, error_message
            | filter level = "ERROR" and msg = "Job processing failed"
            | sort @timestamp desc
            | limit 20
          EOT
          region = var.aws_region
          title  = "Recent Failed Jobs"
        }
      },
      
      # Widget 4: Error Rate Percentage
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            [{ expression = "m2/(m1+m2)*100", label = "Error Rate %", id = "e1" }],
            ["MediaSummarizer/Jobs", "JobSuccessCount", { id = "m1", visible = false }],
            [".", "JobFailureCount", { id = "m2", visible = false }]
          ]
          period = 3600
          stat   = "Sum"
          region = var.aws_region
          title  = "Error Rate Percentage (1h)"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      }
    ]
  })
}
```

---

## 🗑️ **Stratégie de Cleanup et Rétention**

### **Clarification : Rétention par Phase**

#### **Phase 1 : Chaud (0-7 jours)** 
- **Stockage** : DynamoDB (table principale `processing_jobs`)
- **Usage** : 
  - Debug actif
  - Retry automatique (si retry_count < max_retries)
  - Monitoring temps réel
- **Action** : AUCUNE (jobs restent dans DynamoDB)

#### **Phase 2 : Tiède (7-30 jours)**
- **Stockage** : S3 (bucket `media-summarizer-job-archives`)
- **Usage** :
  - Analyse post-mortem
  - Statistiques mensuelles
  - Audit
- **Action** : **Worker de cleanup quotidien** archive vers S3 et supprime de DynamoDB

#### **Phase 3 : Froid (30+ jours)**
- **Stockage** : S3 Glacier (lifecycle policy automatique)
- **Usage** :
  - Compliance long-terme
  - Analytics annuelles
- **Action** : Lifecycle policy S3 (automatique)

### **Implémentation du Worker de Cleanup**

**Fichier** : `media_summarizer/workers/cleanup/job_archiver.py`

```python
async def archive_old_jobs():
    """
    Archive jobs older than 7 days from DynamoDB to S3.
    Runs daily via EventBridge schedule.
    """
    from datetime import datetime, timedelta, timezone
    import json
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Query jobs older than 7 days (requires GSI on created_at)
    # Note: This is a simplified version, actual implementation would use pagination
    old_jobs = await database_async.query_jobs_before_date(cutoff_date)
    
    archived_count = 0
    for job in old_jobs:
        try:
            # Archive to S3
            year = job.created_at.year
            month = job.created_at.month
            archive_key = f"archived-jobs/{year}/{month:02d}/{job.id}.json"
            
            await s3.upload_file_object(
                bucket="media-summarizer-job-archives",
                key=archive_key,
                file_obj=BytesIO(json.dumps(job.to_dynamodb_item(), indent=2).encode()),
                content_type="application/json"
            )
            
            # Delete from DynamoDB
            await database_async.delete_processing_job(job.id)
            
            archived_count += 1
            logger.info(f"Archived job {job.id} to S3: {archive_key}")
            
        except Exception as e:
            logger.error(f"Failed to archive job {job.id}: {e}")
            # Continue with next job
    
    logger.info(f"Archived {archived_count} jobs older than 7 days")
    
    # Send summary to ops
    if archived_count > 0:
        await send_ops_notification(
            subject=f"Daily Job Archive: {archived_count} jobs archived",
            message=f"Successfully archived {archived_count} jobs older than 7 days to S3."
        )
```

**Déclenchement** : EventBridge schedule (cron: `0 2 * * ? *` = 2AM daily)

**Terraform** :
```hcl
resource "aws_cloudwatch_event_rule" "daily_job_archive" {
  name                = "daily-job-archive"
  description         = "Trigger job archiver daily at 2 AM UTC"
  schedule_expression = "cron(0 2 * * ? *)"
}

resource "aws_cloudwatch_event_target" "job_archiver" {
  rule      = aws_cloudwatch_event_rule.daily_job_archive.name
  target_id = "JobArchiverLambda"
  arn       = aws_lambda_function.job_archiver.arn
}
```

### **S3 Lifecycle Policy** (Phase 2 → Phase 3)

**Terraform** :
```hcl
resource "aws_s3_bucket_lifecycle_configuration" "job_archives" {
  bucket = aws_s3_bucket.job_archives.id

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    transition {
      days          = 30  # After 30 days in S3 Standard
      storage_class = "GLACIER"
    }

    expiration {
      days = 365  # Delete after 1 year total
    }
  }
}
```

---

## 📊 **Résumé : Cycle de Vie d'un Job Failed**

```
Job Created
    ↓
Processing (retry_count = 0)
    ↓
❌ Failed
    ↓
retry_count < max_retries ?
    ├─ YES → Retry automatique (via SQS visibility timeout ou worker retry)
    │         ↓
    │     Processing (retry_count++)
    │         ↓
    │     ❌ Failed again
    │         ↓
    │     (loop jusqu'à retry_count >= max_retries)
    │
    └─ NO → Failed Permanently
              ↓
          ┌─────────────────────┬─────────────────────┐
          │                     │                     │
    Email User          Email Ops Team        Mark in DynamoDB
    (simple)           (détails techniques)   (status=failed, 
                                              retry_count=3)
          │                     │                     │
          └─────────────────────┴─────────────────────┘
                              ↓
                    Reste dans DynamoDB (0-7 jours)
                              ↓
                    Worker de cleanup quotidien
                              ↓
                    Archive vers S3 (7-30 jours)
                              ↓
                    Lifecycle → Glacier (30+ jours)
                              ↓
                    Suppression (365+ jours)
```

---

## ✅ **Checklist d'Implémentation**

### **Fait** ✅
- [x] Déduplication intelligente avec gestion des retries
- [x] Email d'erreur user-friendly (sans détails techniques)

### **À Faire** (Phase 2)
- [ ] Email d'alerte ops (avec détails techniques)
- [ ] CloudWatch Dashboard (Option A)
- [ ] CloudWatch Metric Filters
- [ ] CloudWatch Alarms (> 5 erreurs/5min)
- [ ] Worker de cleanup quotidien
- [ ] S3 Lifecycle policy
- [ ] Système de retry au niveau job (optionnel)

### **Variables d'Environnement à Ajouter**
```bash
# .env.dev / .env.prod
OPS_ALERT_EMAIL=ops@media-summarizer.com
JOB_ARCHIVE_BUCKET=media-summarizer-job-archives
JOB_RETENTION_DAYS=7
```

---

## 🎯 **Prochaine Étape Recommandée**

Implémenter l'email d'alerte ops (2.1) car c'est le plus critique pour le debug en production.

Voulez-vous que je commence par ça ?
