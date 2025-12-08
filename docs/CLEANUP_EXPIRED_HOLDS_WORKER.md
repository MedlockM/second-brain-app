# Worker de nettoyage des holds expirés

## Vue d'ensemble

Le worker `cleanup_expired_holds_worker.py` nettoie périodiquement les holds expirés dans la table `minute_usage`.

## Fonctionnement

### Qu'est-ce qu'un hold ?

Lorsqu'un utilisateur soumet un épisode pour traitement :
1. Un **hold** est créé dans `minute_usage` avec `status='held'`
2. Le hold réserve un nombre estimé de minutes
3. Quand le traitement se termine, le hold est **finalisé** (`status='finalized'`)
4. Si le traitement échoue, le hold est **relâché** (`status='released'`)

### Pourquoi nettoyer les holds expirés ?

Certains holds peuvent rester bloqués en statut `held` si :
- Le worker de traitement crash avant de finaliser/relâcher
- Une erreur réseau empêche la mise à jour
- Un job est abandonné sans nettoyage

Pour éviter d'avoir des holds "zombies" qui encombrent la base, ce worker :
1. Scanne la table `minute_usage`
2. Trouve les holds avec `hold_expires_at < now` et `status='held'`
3. Les marque comme `status='expired'`

**Note importante** : Les holds expirés ne bloquent PAS de minutes réelles (car non finalisés), mais il est bon de les nettoyer pour la clarté des données.

## Configuration

### Variables d'environnement

```bash
# Nombre maximum de holds à traiter par exécution
EXPIRED_HOLDS_BATCH_SIZE=100

# Mode dry-run (ne modifie pas la base)
DRY_RUN=false
```

### Exécution locale

```bash
# Mode normal
python -m media_summarizer.workers.cleanup_expired_holds_worker

# Mode dry-run (test sans modification)
DRY_RUN=true python -m media_summarizer.workers.cleanup_expired_holds_worker
```

## Déploiement en production

### Option 1 : EventBridge (recommandé)

Créer une règle EventBridge qui déclenche le worker quotidiennement :

```hcl
# infrastructure/terraform/eventbridge_cleanup.tf

resource "aws_cloudwatch_event_rule" "cleanup_expired_holds" {
  name                = "cleanup-expired-holds-daily"
  description         = "Trigger cleanup of expired minute holds daily"
  schedule_expression = "cron(0 2 * * ? *)"  # 2h du matin UTC chaque jour
}

resource "aws_cloudwatch_event_target" "cleanup_expired_holds" {
  rule      = aws_cloudwatch_event_rule.cleanup_expired_holds.name
  target_id = "CleanupExpiredHoldsECS"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.eventbridge_ecs.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.cleanup_expired_holds.arn
    launch_type         = "FARGATE"
    network_configuration {
      subnets          = var.private_subnet_ids
      security_groups  = [aws_security_group.workers.id]
      assign_public_ip = false
    }
  }
}
```

### Option 2 : Cron job

Si vous utilisez EC2 ou un serveur dédié :

```bash
# Ajouter au crontab
0 2 * * * cd /app && python -m media_summarizer.workers.cleanup_expired_holds_worker >> /var/log/cleanup_holds.log 2>&1
```

## Performance et optimisation

### Scan de table

⚠️ **Attention** : La fonction `scan_expired_holds()` utilise un **scan DynamoDB**, ce qui peut être coûteux sur de grandes tables.

### Optimisations possibles

1. **GSI sur (status, hold_expires_at)** :
   ```hcl
   global_secondary_index {
     name            = "status-expiry-index"
     hash_key        = "status"
     range_key       = "hold_expires_at"
     projection_type = "ALL"
   }
   ```
   Permet de faire une query au lieu d'un scan.

2. **DynamoDB TTL** :
   Activer le TTL sur `hold_expires_at` pour suppression automatique :
   ```hcl
   ttl {
     attribute_name = "hold_expires_at_ttl"  # timestamp Unix
     enabled        = true
   }
   ```
   ⚠️ Mais cela supprime complètement l'item au lieu de le marquer comme expiré.

3. **Batch processing** :
   Le worker traite par lots de `BATCH_SIZE` items. Augmenter cette valeur si nécessaire.

## Monitoring

### Métriques à surveiller

- Nombre de holds expirés trouvés par exécution
- Nombre de holds marqués avec succès
- Nombre d'échecs
- Durée d'exécution du worker

### Logs

Le worker log toutes ses actions :
```
INFO - Starting expired holds cleanup...
INFO - Found 15 expired holds
INFO - Marked usage mu_abc123 (job job_xyz) as expired
INFO - Cleanup complete: {'total_found': 15, 'total_marked': 15, 'total_failed': 0}
```

### Alertes recommandées

- Si `total_failed > 10%` → Problème de connexion DynamoDB
- Si `total_found > 1000` → Beaucoup de jobs abandonnés, investiguer

## Tests

```bash
# Test unitaire
pytest media_summarizer/tests/unit/workers/test_cleanup_expired_holds_worker.py

# Test d'intégration avec LocalStack
pytest media_summarizer/tests/integration/test_cleanup_expired_holds_integration.py
```

## Fréquence recommandée

- **Développement** : Manuel ou quotidien
- **Production** : **Quotidien** à 2h du matin (faible trafic)

Les holds expirent après **2 jours** (voir `minute_pool.py` ligne 47), donc une exécution quotidienne est suffisante.

## Dépannage

### Le worker ne trouve aucun hold expiré

✅ Normal si tous les jobs se terminent correctement

### Le worker trouve beaucoup de holds expirés

⚠️ Possible problème :
- Workers de traitement qui crashent
- Timeouts réseau
- Bugs dans la finalisation des jobs

→ Investiguer les logs des workers de traitement

### Erreur "Failed to scan expired holds"

Vérifier :
- Connexion à DynamoDB
- Permissions IAM (action `dynamodb:Scan`)
- Nom de la table (`MINUTE_USAGE_TABLE`)
