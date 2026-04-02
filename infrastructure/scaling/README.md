# Horizontal Scaling Setup - Media Summarizer

## Vue d'ensemble

Ce système de scaling horizontal permet de déployer des workers Fargate éphémères qui se lancent automatiquement quand des messages arrivent dans les queues SQS et se terminent une fois le travail terminé. **Coût = 0€ quand il n'y a pas de jobs**.

## Architecture

```
Message SQS → CloudWatch Alarm → Lambda Controller → Fargate Worker → Message traité → Worker terminé
```

### Composants

1. **Lambda Scaling Controller** : Décide combien de workers lancer
2. **Workers Fargate Éphémères** : Traitent un message puis se terminent
3. **CloudWatch Alarms** : Détectent les messages dans les queues
4. **EventBridge Timer** : Vérifie périodiquement les queues (backup)

## Déploiement Production

### Prérequis

```bash
# AWS CLI configuré
aws configure

# Terraform installé
terraform --version

# Docker installé
docker --version

# Variables d'environnement requises
export OPENAI_API_KEY="sk-..."
export DEEPGRAM_API_KEY="dg_..."
export AWS_DEFAULT_REGION="us-east-1"
```

### Déploiement Rapide

```bash
# Cloner et naviguer
cd media-summarizer-project/infrastructure/scaling

# Déployer tout
./deploy.sh --region us-east-1 --environment production

# Ou avec des options personnalisées
./deploy.sh \
  --region us-west-2 \
  --environment staging \
  --vpc-id vpc-12345678 \
  --project media-summarizer-v2
```

### Options de Déploiement

```bash
# Déploiement sans rebuild Docker (plus rapide)
./deploy.sh --skip-docker

# Déploiement sans tests
./deploy.sh --skip-test

# Détruire l'infrastructure
./deploy.sh --destroy

# Aide
./deploy.sh --help
```

## Test Local

### Prérequis Locaux

```bash
# Démarrer LocalStack
cd media-summarizer-project
docker-compose -f docker-compose.dev.yml up localstack -d

# Vérifier que LocalStack fonctionne
curl http://localhost:4566/_localstack/health
```

### Tests des Workers Éphémères

```bash
# Construire l'image et tester tous les workers
python scripts/test_ephemeral_local.py --build

# Tester un worker spécifique
python scripts/test_ephemeral_local.py --worker rss

# Tester sans cleanup (pour debug)
python scripts/test_ephemeral_local.py --no-cleanup
```

### Test Manuel

```bash
# Envoyer un message test
aws sqs send-message \
  --endpoint-url http://localhost:4566 \
  --queue-url http://localhost:4566/000000000000/deepgram-transcription-queue \
  --message-body '{"job_id":"test-123","audio_url":"https://example.com/audio.mp3"}'

# Lancer un worker éphémère manuellement
docker run --rm \
  --network media-summarizer-project_default \
  -e WORKER_TYPE=deepgram \
  -e QUEUE_URL=http://localstack:4566/000000000000/deepgram-transcription-queue \
  -e QUEUE_NAME=deepgram-transcription-queue \
  -e EPHEMERAL_MODE=true \
  -e AWS_ENDPOINT_URL=http://localstack:4566 \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  media-summarizer-project-ephemeral-worker
```

## Configuration

### Variables d'Environnement - Lambda

```bash
CLUSTER_NAME=media-summarizer-cluster
RSS_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/...
YOUTUBE_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/...
DEEPGRAM_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/...
SUMMARIZATION_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/...
SUBNET_IDS=subnet-xxx,subnet-yyy
SECURITY_GROUP_IDS=sg-xxx
MAX_PARALLEL_WORKERS=15
```

### Variables d'Environnement - Workers

```bash
WORKER_TYPE=rss|youtube|deepgram|summarization|download
QUEUE_URL=https://sqs.region.amazonaws.com/account/queue-name
EPHEMERAL_MODE=true
MAX_PROCESSING_TIME=3600
HEARTBEAT_INTERVAL=60
VISIBILITY_TIMEOUT=300
```

### Limites de Ressources

| Worker Type     | CPU   | Memory | Timeout |
|----------------|-------|--------|---------|
| RSS            | 256   | 512MB  | 5min    |
| YouTube        | 512   | 1024MB | 5min    |
| Download       | 512   | 1024MB | 15min   |
| Deepgram       | 1024  | 2048MB | 30min   |
| Summarization  | 512   | 1024MB | 5min    |

## Tests de Production

### Test Automatisé

```bash
# Après déploiement
cd media-summarizer-project/infrastructure/scaling
python test_scaling.py
```

### Test Manuel

```bash
# Test du Lambda
aws lambda invoke \
  --function-name media-summarizer-scaling-controller \
  --payload '{"action":"scale","source":"manual_test"}' \
  response.json

# Ajout de message de test
aws sqs send-message \
  --queue-url $(terraform output -raw queue_urls | jq -r .deepgram_transcription) \
  --message-body '{"job_id":"prod-test-123","audio_url":"https://cdn.example.com/episode.mp3"}'

# Vérifier les workers lancés
aws ecs list-tasks --cluster media-summarizer-cluster
```

## Monitoring

### Métriques Importantes

1. **SQS Metrics**
   - `ApproximateNumberOfVisibleMessages`
   - `ApproximateNumberOfMessagesNotVisible`

2. **ECS Metrics**
   - Nombre de tâches en cours
   - CPU/Memory utilization

3. **Custom Metrics**
   - `MediaSummarizer/Scaling/QueueLength`
   - `MediaSummarizer/Scaling/LaunchedTasks`

### CloudWatch Dashboard

```bash
# Créer un dashboard personnalisé
aws cloudwatch put-dashboard \
  --dashboard-name MediaSummarizerScaling \
  --dashboard-body file://dashboard.json
```

### Alarmes Configurées

- **Queue Messages** : Déclenche scaling quand messages > 0
- **Lambda Errors** : Alerte sur erreurs du contrôleur
- **Task Failures** : Alerte sur échecs de workers

## Troubleshooting

### Problèmes Courants

#### Workers ne se lancent pas

```bash
# Vérifier les permissions
aws iam get-role --role-name media-summarizer-lambda-scaling
aws iam get-role --role-name media-summarizer-ecs-task

# Vérifier le networking
aws ec2 describe-subnets --subnet-ids subnet-xxx
aws ec2 describe-security-groups --group-ids sg-xxx

# Vérifier les task definitions
aws ecs describe-task-definition --task-definition media-summarizer-rss-worker
```

#### Messages ne sont pas traités

```bash
# Vérifier les logs des workers
aws logs get-log-events \
  --log-group-name /ecs/media-summarizer-rss-worker \
  --log-stream-name ecs/media-summarizer-rss/task-id

# Vérifier la visibilité des messages
aws sqs get-queue-attributes \
  --queue-url https://sqs.region.amazonaws.com/account/queue-name \
  --attribute-names VisibilityTimeout,MessageRetentionPeriod
```

#### Scaling trop agressif

```bash
# Ajuster la limite de workers
aws lambda update-function-configuration \
  --function-name media-summarizer-scaling-controller \
  --environment Variables='{
    "MAX_PARALLEL_WORKERS":"10"
  }'

# Modifier la fréquence EventBridge
aws events put-rule \
  --name media-summarizer-scaling-check \
  --schedule-expression "rate(5 minutes)"
```

### Logs Utiles

```bash
# Lambda scaling controller
aws logs tail /aws/lambda/media-summarizer-scaling-controller --follow

# Workers Fargate
aws logs tail /ecs/media-summarizer-rss-worker --follow
aws logs tail /ecs/media-summarizer-deepgram-worker --follow

# Tous les logs ECS
aws logs describe-log-groups --log-group-name-prefix /ecs/media-summarizer
```

### Commandes de Debug

```bash
# État du cluster
aws ecs describe-clusters --clusters media-summarizer-cluster

# Tâches en cours
aws ecs list-tasks --cluster media-summarizer-cluster --desired-status RUNNING

# Détails des tâches
aws ecs describe-tasks \
  --cluster media-summarizer-cluster \
  --tasks $(aws ecs list-tasks --cluster media-summarizer-cluster --query 'taskArns[0]' --output text)

# Messages dans les queues
for queue in podcastindex-resolution-queue youtube-ingestion-queue deepgram-transcription-queue summarization-queue; do
  echo "=== $queue ==="
  aws sqs get-queue-attributes \
    --queue-url $(aws sqs get-queue-url --queue-name $queue --query QueueUrl --output text) \
    --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible
done
```

## Optimisations

### Performance

1. **Images Docker optimisées**
   ```dockerfile
   # Multi-stage build pour réduire la taille
   FROM python:3.11-slim as base
   # ... optimisations
   ```

2. **Cold start reduction**
   ```bash
   # Pré-chauffage des images
   aws ecs run-task --cluster cluster --task-definition task-def --count 0
   ```

### Coûts

1. **Right-sizing des ressources**
   ```bash
   # Analyser l'utilisation
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name CPUUtilization \
     --dimensions Name=ServiceName,Value=media-summarizer-rss-worker
   ```

2. **Spot instances** (à venir)
   ```json
   {
     "capacityProviders": ["FARGATE_SPOT"],
     "defaultCapacityProviderStrategy": [
       {
         "capacityProvider": "FARGATE_SPOT",
         "weight": 1
       }
     ]
   }
   ```

## Évolutions

### Phase 2 - Optimisations Avancées

- [ ] Spot instances pour réduire les coûts de 70%
- [ ] Batch processing (plusieurs messages par worker)
- [ ] Auto-scaling intelligent avec ML
- [ ] Multi-region deployment

### Phase 3 - Enterprise Features

- [ ] Blue/green deployments
- [ ] Canary releases pour les workers
- [ ] Advanced monitoring avec X-Ray
- [ ] Cost optimization recommandations

## Sécurité

### Principe du Moindre Privilège

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage"
      ],
      "Resource": "arn:aws:sqs:region:account:queue-name"
    }
  ]
}
```

### Chiffrement

- **SQS** : Messages chiffrés en transit (TLS) et au repos (KMS)
- **S3** : Chiffrement par défaut avec AWS KMS
- **Secrets Manager** : Clés API chiffrées avec rotation automatique
- **CloudWatch Logs** : Logs chiffrés avec KMS

### Network Security

```bash
# Security Groups restrictifs
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# VPC Endpoints pour éviter le transit internet
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxx \
  --service-name com.amazonaws.region.s3
```

### Audit et Compliance

```bash
# CloudTrail pour audit des actions
aws cloudtrail create-trail \
  --name media-summarizer-audit \
  --s3-bucket-name audit-logs-bucket

# Config pour compliance
aws configservice put-configuration-recorder \
  --configuration-recorder name=media-summarizer-config
```

## FAQ

### Q: Comment réduire les coûts davantage ?

**R:** 
- Utiliser Fargate Spot (70% moins cher)
- Optimiser les tailles de tâches selon l'utilisation réelle
- Implémenter du batch processing pour traiter plusieurs messages
- Utiliser des lifecycle policies S3 agressives

### Q: Comment gérer les pics de charge ?

**R:**
- Le système scale automatiquement jusqu'à 15 workers
- Pour des pics plus importants, augmenter `MAX_PARALLEL_WORKERS`
- Considérer le sharding des queues par priorité
- Implémenter du rate limiting si nécessaire

### Q: Que faire en cas de panne d'une région AWS ?

**R:**
- Déployer dans une région secondaire
- Utiliser Route 53 pour le failover automatique
- Répliquer les données critiques cross-region
- Tester régulièrement les procédures de disaster recovery

### Q: Comment débugger un worker qui ne traite pas les messages ?

**R:**
```bash
# 1. Vérifier que le worker reçoit bien les variables d'environnement
aws ecs describe-tasks --cluster cluster --tasks task-arn

# 2. Vérifier les logs en temps réel
aws logs tail /ecs/media-summarizer-worker-type --follow

# 3. Vérifier les permissions IAM
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::account:role/media-summarizer-ecs-task \
  --action-names sqs:ReceiveMessage \
  --resource-arns arn:aws:sqs:region:account:queue-name

# 4. Tester manuellement avec un worker local
python scripts/test_ephemeral_local.py --worker rss
```

### Q: Comment monitorer les coûts en temps réel ?

**R:**
```bash
# Cost Explorer API
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-02 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Budgets avec alertes
aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

## Support

- **Documentation complète** : `docs/HORIZONTAL_SCALING.md`
- **Issues GitHub** : [Créer un ticket](https://github.com/your-org/media-summarizer/issues)
- **Monitoring** : CloudWatch Dashboard après déploiement
- **Logs** : CloudWatch Logs avec retention de 7 jours

---

**🎉 Félicitations !** Votre infrastructure de scaling horizontal est maintenant déployée et prête à traiter des millions de podcasts de manière économique et automatique.
