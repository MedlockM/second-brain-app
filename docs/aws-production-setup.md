# Configuration AWS Production - Éviter l'intermittence SQS

## Vue d'ensemble

En production AWS, plusieurs facteurs peuvent causer de l'intermittence dans les tests et le traitement des messages SQS. Ce guide détaille les configurations recommandées pour garantir la fiabilité.

## 🚨 Problèmes d'intermittence courants

### LocalStack vs AWS Réel
- **LocalStack** : Consistance éventuelle simulée, timing variable
- **AWS Production** : Consistance forte, latence réseau réelle

### Causes principales d'intermittence
1. **Propagation des messages** : Délai entre envoi et disponibilité
2. **Visibility timeout** : Messages temporairement invisibles
3. **Polling inefficace** : Polling trop rapide ou mal configuré
4. **Concurrence** : Plusieurs workers récupèrent le même message

## ⚙️ Configuration SQS Production

### 1. Configuration des Queues

```bash
# Création des queues avec paramètres optimisés
aws sqs create-queue \
  --queue-name rss-resolution-queue \
  --attributes '{
    "VisibilityTimeoutSeconds": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "20",
    "DelaySeconds": "0",
    "MaxReceiveCount": "3",
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:region:account:rss-resolution-dlq\",\"maxReceiveCount\":3}"
  }'
```

### 2. Paramètres critiques

| Paramètre | Valeur Recommandée | Impact |
|-----------|-------------------|---------|
| `VisibilityTimeoutSeconds` | 300 (5 min) | Temps pour traiter un message |
| `ReceiveMessageWaitTimeSeconds` | 20 | Long polling (évite polling vide) |
| `MessageRetentionPeriod` | 1209600 (14 jours) | Rétention des messages |
| `MaxReceiveCount` | 3 | Tentatives avant DLQ |
| `MaxNumberOfMessages` | 1 | Traitement séquentiel (CPU monopolisé) |

### 3. Dead Letter Queues (DLQ)

```yaml
# Configuration DLQ pour chaque queue principale
Queues:
  - Main: rss-resolution-queue
    DLQ: rss-resolution-dlq
  - Main: audio-download-queue
    DLQ: audio-download-dlq
  - Main: transcription-queue
    DLQ: transcription-dlq
  - Main: summarization-queue
    DLQ: summarization-dlq
  - Main: email-notification-queue
    DLQ: email-notification-dlq
```

## 🔧 Configuration Worker Production

### 1. Polling Optimisé

```python
# media_summarizer/workers/base_worker.py
import asyncio
import boto3
from botocore.exceptions import ClientError

class BaseWorker:
    def __init__(self):
        self.sqs = boto3.client('sqs', region_name=AWS_REGION)
        self.max_messages = 1   # Traitement séquentiel (Whisper monopolise CPU)
        self.wait_time = 20     # Long polling
        self.visibility_timeout = 300
        
    async def poll_queue_optimized(self, queue_url: str):
        """Polling optimisé pour production."""
        while True:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=self.max_messages,
                    WaitTimeSeconds=self.wait_time,
                    VisibilityTimeoutSeconds=self.visibility_timeout,
                    AttributeNames=['All'],
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                if not messages:
                    continue
                    
                # Traitement séquentiel (optimal pour Whisper)
                for message in messages:
                    await self.process_message_safe(message, queue_url)
                
            except ClientError as e:
                logger.error(f"Erreur SQS: {e}")
                await asyncio.sleep(5)  # Backoff en cas d'erreur
            except Exception as e:
                logger.error(f"Erreur worker: {e}")
                await asyncio.sleep(1)
```

### 2. Gestion des erreurs robuste

```python
async def process_message_safe(self, message: dict, queue_url: str):
    """Traitement sécurisé avec retry et gestion d'erreurs."""
    receipt_handle = message['ReceiptHandle']
    
    try:
        # Traitement du message
        await self.process_message(message)
        
        # Suppression du message en cas de succès
        self.sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        
    except RetryableError as e:
        # Erreur temporaire - laisser le message revenir
        logger.warning(f"Erreur temporaire: {e}")
        
    except PermanentError as e:
        # Erreur permanente - supprimer le message
        logger.error(f"Erreur permanente: {e}")
        self.sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        
    except Exception as e:
        # Erreur inconnue - logger et laisser timeout
        logger.error(f"Erreur inconnue: {e}")
```

## 🌍 Configuration Terraform Production

### 1. Variables d'environnement

```hcl
# infrastructure/terraform/variables.tf
variable "environment" {
  description = "Environment (development, production)"
  type        = string
  default     = "production"
}

variable "whisper_model_size" {
  description = "Whisper model size based on environment"
  type        = string
  default     = "large"
}

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds"
  type        = number
  default     = 300
}

variable "sqs_message_retention_period" {
  description = "SQS message retention period in seconds"
  type        = number
  default     = 1209600  # 14 days
}
```

### 2. Configuration SQS

```hcl
# infrastructure/terraform/sqs.tf
resource "aws_sqs_queue" "transcription_queue" {
  name = "transcription-queue-${var.environment}"
  
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention_period
  receive_wait_time_seconds  = 20  # Long polling
  delay_seconds             = 0
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.transcription_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = {
    Environment = var.environment
    Purpose     = "Transcription processing"
  }
}

resource "aws_sqs_queue" "transcription_dlq" {
  name = "transcription-dlq-${var.environment}"
  
  message_retention_seconds = 1209600  # 14 days for debugging
  
  tags = {
    Environment = var.environment
    Purpose     = "Dead letter queue for transcription"
  }
}
```

### 3. Configuration ECS avec variables

```hcl
# infrastructure/terraform/ecs.tf
resource "aws_ecs_task_definition" "whisper_worker" {
  family                   = "whisper-worker-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode            = "awsvpc"
  cpu                     = var.environment == "production" ? "2048" : "1024"
  memory                  = var.environment == "production" ? "8192" : "2048"
  
  container_definitions = jsonencode([
    {
      name  = "whisper-worker"
      image = "${aws_ecr_repository.app.repository_url}:latest"
      
      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "WHISPER_MODEL_SIZE"
          value = var.whisper_model_size
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = data.aws_region.current.name
        },
        {
          name  = "TRANSCRIPTION_QUEUE"
          value = aws_sqs_queue.transcription_queue.name
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "whisper-worker"
        }
      }
    }
  ])
}
```

## 📊 Monitoring et Observabilité

### 1. CloudWatch Metrics

```python
# media_summarizer/core/monitoring/metrics.py
import boto3
import time
from datetime import datetime

class SQSMetrics:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
    
    def record_message_processing_time(self, queue_name: str, duration: float):
        """Enregistrer le temps de traitement des messages."""
        self.cloudwatch.put_metric_data(
            Namespace='MediaSummarizer/SQS',
            MetricData=[
                {
                    'MetricName': 'MessageProcessingTime',
                    'Dimensions': [
                        {
                            'Name': 'QueueName',
                            'Value': queue_name
                        }
                    ],
                    'Value': duration,
                    'Unit': 'Seconds',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    
    def record_message_error(self, queue_name: str, error_type: str):
        """Enregistrer les erreurs de traitement."""
        self.cloudwatch.put_metric_data(
            Namespace='MediaSummarizer/SQS',
            MetricData=[
                {
                    'MetricName': 'MessageErrors',
                    'Dimensions': [
                        {
                            'Name': 'QueueName',
                            'Value': queue_name
                        },
                        {
                            'Name': 'ErrorType',
                            'Value': error_type
                        }
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
```

### 2. Alarmes CloudWatch

```hcl
# infrastructure/terraform/monitoring.tf
resource "aws_cloudwatch_metric_alarm" "transcription_queue_dlq" {
  alarm_name          = "transcription-dlq-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfMessages"
  namespace           = "AWS/SQS"
  period              = "120"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "This metric monitors transcription DLQ messages"
  
  dimensions = {
    QueueName = aws_sqs_queue.transcription_dlq.name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "whisper_worker_cpu" {
  alarm_name          = "whisper-worker-high-cpu-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors whisper worker CPU"
  
  dimensions = {
    ServiceName = aws_ecs_service.whisper_worker.name
    ClusterName = aws_ecs_cluster.main.name
  }
  
  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

## 🔄 Tests de Robustesse Production

### 1. Tests de charge

```python
# tests/load/test_sqs_load.py
import asyncio
import boto3
import json
import time
from concurrent.futures import ThreadPoolExecutor

class SQSLoadTest:
    def __init__(self, queue_url: str):
        self.sqs = boto3.client('sqs')
        self.queue_url = queue_url
    
    async def send_messages_batch(self, count: int):
        """Envoyer des messages par batch."""
        messages = []
        for i in range(min(count, 10)):  # SQS limite: 10 messages/batch
            messages.append({
                'Id': str(i),
                'MessageBody': json.dumps({
                    'job_id': f'load-test-{int(time.time())}-{i}',
                    'test_data': 'x' * 1000  # 1KB de données
                })
            })
        
        response = self.sqs.send_message_batch(
            QueueUrl=self.queue_url,
            Entries=messages
        )
        return len(response.get('Successful', []))
    
    async def test_throughput(self, total_messages: int):
        """Tester le débit de traitement."""
        start_time = time.time()
        
        # Envoyer les messages en parallèle
        tasks = []
        for batch in range(0, total_messages, 10):
            task = asyncio.create_task(
                self.send_messages_batch(min(10, total_messages - batch))
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        total_sent = sum(results)
        
        duration = time.time() - start_time
        throughput = total_sent / duration
        
        print(f"Envoyé {total_sent} messages en {duration:.2f}s")
        print(f"Débit: {throughput:.2f} messages/seconde")
        
        return throughput
```

### 2. Tests de résilience

```python
# tests/resilience/test_sqs_resilience.py
import pytest
import asyncio
import boto3
from unittest.mock import patch
from botocore.exceptions import ClientError

class SQSResilienceTest:
    
    @pytest.mark.asyncio
    async def test_network_timeout_recovery(self):
        """Tester la récupération après timeout réseau."""
        sqs = boto3.client('sqs')
        
        # Simuler un timeout réseau
        with patch.object(sqs, 'receive_message') as mock_receive:
            mock_receive.side_effect = [
                ClientError({'Error': {'Code': 'RequestTimeout'}}, 'receive_message'),
                {'Messages': [{'Body': '{"test": "data"}', 'ReceiptHandle': 'handle123'}]}
            ]
            
            # Le worker doit récupérer après le timeout
            result = await self.poll_with_retry(sqs, "test-queue")
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_visibility_timeout_handling(self):
        """Tester la gestion du visibility timeout."""
        # Simuler un message qui réapparaît après timeout
        pass  # Implémentation détaillée
    
    async def poll_with_retry(self, sqs, queue_url, max_retries=3):
        """Polling avec retry automatique."""
        for attempt in range(max_retries):
            try:
                response = sqs.receive_message(
                    QueueUrl=queue_url,
                    WaitTimeSeconds=1
                )
                return response.get('Messages', [])
            except ClientError as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Backoff exponentiel
```

## 📋 Checklist Déploiement Production

### Avant le déploiement

- [ ] **Queues SQS créées** avec paramètres optimisés
- [ ] **Dead Letter Queues** configurées
- [ ] **CloudWatch monitoring** activé
- [ ] **Auto-scaling** configuré pour les workers
- [ ] **Tests de charge** réalisés
- [ ] **Variables d'environnement** validées

### Configuration critique

```bash
# Variables d'environnement production
ENVIRONMENT=production
WHISPER_MODEL_SIZE=large
AWS_DEFAULT_REGION=us-east-1

# SQS Configuration
SQS_VISIBILITY_TIMEOUT=300
SQS_WAIT_TIME=20
SQS_MAX_MESSAGES=10

# Worker Configuration
WORKER_CONCURRENCY=1
WORKER_TIMEOUT=600
```

### Monitoring essentiel

- [ ] **Queue depth** monitoring
- [ ] **DLQ alerts** configurées
- [ ] **Worker health checks** activés
- [ ] **Performance metrics** suivis
- [ ] **Error rate alerts** configurées

## 🚀 Performance Production Attendue

### Métriques cibles

| Métrique | Développement (tiny) | Production (large) |
|----------|---------------------|-------------------|
| Temps transcription | 5-10 secondes | 30-60 secondes |
| Débit messages/min | 50-100 | 10-20 (séquentiel) |
| CPU Utilisation | 50-70% | 90-100% (monopolisé) |
| Précision | ~80% | ~95% |
| Disponibilité | 95% | 99.9% |

### Optimisations recommandées

1. **Auto-scaling ECS** basé sur queue depth
2. **Instances CPU optimisées** pour Whisper Large (traitement séquentiel)
3. **Scaling horizontal** : plus d'instances plutôt que parallélisme
4. **Cache Redis** pour les résultats fréquents
5. **CDN CloudFront** pour l'API
6. **Multi-AZ deployment** pour la haute disponibilité