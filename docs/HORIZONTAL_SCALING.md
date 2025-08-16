# Horizontal Scaling Architecture - Media Summarizer

## Overview

Le système de scaling horizontal de Media Summarizer utilise des workers Fargate éphémères pour traiter les messages SQS de manière automatique et économique. L'architecture garantit un coût de 0€ quand il n'y a pas de jobs à traiter.

## Architecture

### Composants Principaux

1. **Lambda de Contrôle de Scaling** (`scaling_controller.py`)
   - Déclenché par des alarmes CloudWatch ou EventBridge
   - Calcule le nombre de workers nécessaires
   - Lance des tâches Fargate éphémères
   - Respecte la limite maximale de 15 workers parallèles

2. **Workers Fargate Éphémères** (`ephemeral_worker.py`)
   - Traite un seul message SQS puis se termine
   - Gère automatiquement le lease renewal
   - Supporte tous les types de workers (RSS, Download, Whisper, Summarization, Email)

3. **CloudWatch Alarms**
   - Monitore `ApproximateNumberOfVisibleMessages` pour chaque queue
   - Déclenche le scaling quand des messages sont détectés

4. **EventBridge Timer**
   - Vérifie périodiquement (toutes les 2 minutes) les queues
   - Assure une réactivité même sans alarmes

## Flux de Fonctionnement

```
Message ajouté → CloudWatch Alarm → Lambda Scaling → Fargate Task → Message traité → Task terminée
                      ↓
             EventBridge (backup)
```

### Séquence Détaillée

1. **Détection de Messages**
   - Un message arrive dans une queue SQS
   - CloudWatch détecte `ApproximateNumberOfVisibleMessages > 0`
   - L'alarme se déclenche et invoke le Lambda

2. **Calcul de Scaling**
   - Le Lambda lit le nombre de messages dans toutes les queues
   - Calcule le nombre de workers nécessaires : `min(queue_length, max_parallel_workers - running_tasks)`
   - Priorise les queues selon leur importance

3. **Lancement des Workers**
   - Pour chaque worker nécessaire, lance une tâche Fargate
   - Passe les variables d'environnement appropriées
   - Configure le networking et les permissions

4. **Traitement Éphémère**
   - Le worker reçoit un message SQS
   - Démarre le lease renewal automatique
   - Traite le message selon son type
   - Supprime le message et se termine

## Configuration

### Variables d'Environnement

#### Lambda Scaling Controller
```bash
CLUSTER_NAME=media-summarizer-cluster
RSS_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/media-summarizer-rss-worker
DOWNLOAD_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/media-summarizer-download-worker
WHISPER_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/media-summarizer-whisper-worker
SUMMARIZATION_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/media-summarizer-summarization-worker
EMAIL_TASK_DEFINITION_ARN=arn:aws:ecs:region:account:task-definition/media-summarizer-email-worker
SUBNET_IDS=subnet-xxx,subnet-yyy
SECURITY_GROUP_IDS=sg-xxx
MAX_PARALLEL_WORKERS=15
AWS_DEFAULT_REGION=us-east-1
```

#### Workers Éphémères
```bash
WORKER_TYPE=rss|download|whisper|summarization|email
QUEUE_URL=https://sqs.region.amazonaws.com/account/queue-name
QUEUE_NAME=queue-name
EPHEMERAL_MODE=true
MAX_PROCESSING_TIME=3600
HEARTBEAT_INTERVAL=60
VISIBILITY_TIMEOUT=300
```

### Priorités des Queues

Les queues sont traitées par ordre de priorité :

1. `rss-resolution-queue` (priorité 1)
2. `audio-download-queue` (priorité 2)
3. `transcription-queue` (priorité 3)
4. `summarization-queue` (priorité 4)
5. `email-notification-queue` (priorité 5)

## Déploiement

### Prérequis

1. **AWS CLI configuré**
2. **Terraform ≥ 1.0**
3. **Docker**
4. **Variables d'environnement requises :**
   - `OPENAI_API_KEY`
   - `VPC_ID` (optionnel, utilise le VPC par défaut)
   - `SUBNET_IDS` (optionnel, utilise les subnets publics)

### Commandes de Déploiement

```bash
# Déploiement complet
cd infrastructure/scaling
./deploy.sh --region us-east-1 --environment production

# Déploiement sans rebuild Docker
./deploy.sh --skip-docker

# Déploiement sans tests
./deploy.sh --skip-test

# Destruction de l'infrastructure
./deploy.sh --destroy
```

### Structure Terraform

```
infrastructure/terraform/
├── scaling.tf              # Infrastructure principale
├── scaling_controller.zip  # Package Lambda (généré)
└── tfplan                  # Plan Terraform (généré)
```

## Monitoring

### Métriques CloudWatch

1. **Métriques SQS natives :**
   - `ApproximateNumberOfVisibleMessages`
   - `ApproximateNumberOfMessagesNotVisible`
   - `NumberOfMessagesSent`
   - `NumberOfMessagesReceived`

2. **Métriques personnalisées :**
   - `MediaSummarizer/Scaling/QueueLength`
   - `MediaSummarizer/Scaling/RunningTasks`
   - `MediaSummarizer/Scaling/LaunchedTasks`

3. **Métriques ECS :**
   - Nombre de tâches en cours d'exécution
   - Utilisation CPU/Mémoire des tâches

### Alarmes Configurées

- **Queue Messages Alarm** : Se déclenche quand `ApproximateNumberOfVisibleMessages > 0`
- **Task Failure Alarm** : Monitore les échecs de tâches
- **Lambda Error Alarm** : Monitore les erreurs du contrôleur de scaling

### Dashboards Recommandés

1. **Dashboard de Scaling**
   - Nombre de messages par queue
   - Nombre de workers actifs
   - Taux de succès des tâches
   - Latence de traitement

2. **Dashboard de Coûts**
   - Temps d'exécution des tâches Fargate
   - Coût par heure/jour
   - Nombre de tâches lancées

## Tests

### Test Suite Automatisé

```bash
# Lancer les tests de scaling
cd infrastructure/scaling
python test_scaling.py
```

### Tests Inclus

1. **Test de Scaling Basique**
   - Envoie des messages dans une queue
   - Vérifie que les workers sont lancés
   - Confirme le traitement des messages

2. **Test de Limite Maximale**
   - Envoie plus de 15 messages
   - Vérifie que max 15 workers sont lancés
   - Confirme le respect de la limite

3. **Test Multi-Queue**
   - Envoie des messages dans plusieurs queues
   - Vérifie la priorisation correcte
   - Confirme le scaling approprié

4. **Test de Queue Vide**
   - Vérifie qu'aucun worker n'est lancé
   - Confirme l'absence de coûts inutiles

### Tests Manuels

```bash
# Test direct du Lambda
aws lambda invoke \
  --function-name media-summarizer-scaling-controller \
  --payload '{"action":"scale","source":"manual_test"}' \
  response.json

# Ajout de messages de test
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/rss-resolution-queue \
  --message-body '{"job_id":"test-123","podcast_url":"https://example.com/feed.rss"}'
```

## Troubleshooting

### Problèmes Courants

1. **Workers ne se lancent pas**
   - Vérifier les permissions IAM
   - Vérifier la configuration du networking (subnets, security groups)
   - Vérifier que les task definitions existent

2. **Messages ne sont pas traités**
   - Vérifier les logs CloudWatch des workers
   - Vérifier la visibilité timeout des messages
   - Vérifier les credentials AWS des workers

3. **Scaling trop agressif**
   - Ajuster `MAX_PARALLEL_WORKERS`
   - Modifier la fréquence d'EventBridge
   - Ajuster les seuils d'alarmes CloudWatch

4. **Coûts élevés**
   - Vérifier que les workers se terminent correctement
   - Optimiser la taille des tâches (CPU/Memory)
   - Vérifier les timeouts de traitement

### Logs Importants

1. **Lambda Scaling Controller**
   ```
   /aws/lambda/media-summarizer-scaling-controller
   ```

2. **Workers Fargate**
   ```
   /ecs/media-summarizer-rss-worker
   /ecs/media-summarizer-download-worker
   /ecs/media-summarizer-whisper-worker
   /ecs/media-summarizer-summarization-worker
   /ecs/media-summarizer-email-worker
   ```

### Commandes de Debug

```bash
# Vérifier l'état du cluster
aws ecs describe-clusters --clusters media-summarizer-cluster

# Lister les tâches en cours
aws ecs list-tasks --cluster media-summarizer-cluster

# Vérifier les messages dans une queue
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/rss-resolution-queue \
  --attribute-names All

# Vérifier les métriques CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfVisibleMessages \
  --dimensions Name=QueueName,Value=rss-resolution-queue \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T01:00:00Z \
  --period 300 \
  --statistics Average
```

## Optimisations

### Performance

1. **Taille des Tâches**
   - RSS Worker : 256 CPU, 512 MB
   - Download Worker : 512 CPU, 1024 MB  
   - Whisper Worker : 1024 CPU, 2048 MB
   - Summarization Worker : 512 CPU, 1024 MB
   - Email Worker : 256 CPU, 512 MB

2. **Timeouts**
   - Whisper : 30 minutes (transcriptions longues)
   - Autres : 5 minutes

3. **Batch Processing**
   - Possibilité future d'optimiser avec des workers qui traitent plusieurs messages

### Coûts

1. **Cold Start Optimization**
   - Images Docker optimisées
   - Dependencies pré-installées
   - Configuration par défaut appropriée

2. **Resource Right-Sizing**
   - Monitoring continu des métriques CPU/Memory
   - Ajustement régulier des allocations

3. **Scheduling Intelligent**
   - Éviter les heures de pointe AWS quand possible
   - Batching des petites tâches

## Évolutions Futures

### Améliorations Planifiées

1. **Auto-Scaling Intelligent**
   - Machine learning pour prédire les pics de charge
   - Scaling proactif basé sur l'historique

2. **Multi-Region**
   - Réplication de l'infrastructure dans plusieurs régions
   - Load balancing géographique

3. **Optimisations de Coûts**
   - Spot instances pour les workers non-critiques
   - Scheduling intelligent selon les prix

4. **Observabilité Avancée**
   - Tracing distribué avec X-Ray
   - Métriques business personnalisées
   - Alertes intelligentes

### Considérations d'Architecture

1. **State Management**
   - Tous les workers sont stateless
   - État persisté uniquement en DynamoDB

2. **Error Handling**
   - Retry automatique avec backoff exponentiel
   - Dead letter queues pour les échecs permanents
   - Notification des erreurs critiques

3. **Security**
   - Principe du moindre privilège pour les IAM roles
   - Chiffrement en transit et au repos
   - Audit logs complets

## Conclusion

Cette architecture de scaling horizontal offre :

- **Coût optimal** : 0€ sans workload, scaling automatique
- **Résilience** : Retry automatique, dead letter queues
- **Simplicité** : Infrastructure as Code, déploiement automatisé
- **Observabilité** : Métriques complètes, logs centralisés
- **Maintenabilité** : Code modulaire, tests automatisés

Le système est prêt pour la production et peut gérer des charges variables efficacement tout en minimisant les coûts d'infrastructure.