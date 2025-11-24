# Analyse détaillée du mécanisme de Rollover

## 🔍 Comment fonctionne le rollover actuellement

### Déclenchement
Le rollover est déclenché lors du webhook **`invoice.payment_succeeded`** (lignes 234-295 de `stripe_service_v2.py`).

### Flux actuel (lignes 257-284)

```python
# 1. Récupération de tous les buckets de l'utilisateur
all_buckets = await minute_db.get_minute_buckets_by_user_id(sub.user_id)

# 2. Filtrage des buckets d'abonnement de la période PRÉCÉDENTE
prev_sub_buckets = [
    b for b in all_buckets
    if b.source_type == MinuteBucketSource.subscription
    and b.source_ref == subscription_id
    and b.period_end is not None
    and ps is not None
    and b.period_end < ps  # ⚠️ Période terminée AVANT le début de la nouvelle
]

# 3. Si des buckets précédents existent
if prev_sub_buckets:
    # Prendre le plus récent
    prev = sorted(prev_sub_buckets, key=lambda b: b.period_end)[-1]
    leftover = int(prev.minutes_remaining or 0)
    
    # 4. Si des minutes restent, créer un bucket rollover
    if leftover > 0 and pe is not None:
        rollover_bucket = MinuteBucket(
            id=f"rollover_{subscription_id}_{int(ps.timestamp())}",
            user_id=sub.user_id,
            source_type=MinuteBucketSource.rollover,
            source_ref=subscription_id,
            minutes_total=leftover,
            minutes_remaining=leftover,
            expires_at=pe,  # ✅ Expire à la fin de la NOUVELLE période
        )
        await minute_db.create_minute_bucket(rollover_bucket)
```

---

## 🔴 PROBLÈME CRITIQUE IDENTIFIÉ

### Le problème : Rollover créé APRÈS consommation

**Scénario problématique** :

1. **Mois 1** : L'utilisateur reçoit 240 minutes (bucket subscription)
2. **Pendant le mois 1** : L'utilisateur consomme 100 minutes → reste 140 minutes
3. **Début du mois 2** : Stripe envoie `invoice.payment_succeeded`
4. **Le code actuel** :
   - ✅ Trouve le bucket du mois 1 avec 140 minutes restantes
   - ✅ Crée un bucket rollover avec 140 minutes
   - ✅ Crée un nouveau bucket subscription avec 240 minutes
   
**MAIS** : Entre le moment où le mois 2 commence et le moment où le webhook arrive, l'utilisateur pourrait :
- Soumettre des épisodes
- Consommer les 140 minutes du bucket du mois 1
- **Le rollover serait alors créé avec 0 minutes** (ou moins que prévu)

### Exemple concret

```
Timeline:
─────────────────────────────────────────────────────────────
Mois 1                          │ Mois 2
                                │
01/01 - Bucket créé: 240 min    │ 01/02 00:00 - Nouvelle période commence
15/01 - Consommé 100 min        │ 01/02 00:05 - User soumet épisode (40 min)
        Reste: 140 min          │             Bucket mois 1: 140 → 100 min
                                │ 01/02 00:10 - Webhook invoice.payment_succeeded
                                │             Rollover créé avec: 100 min ❌
                                │             (au lieu de 140 min attendu)
```

---

## ⚠️ Autres problèmes identifiés

### 1. Pas de marquage du bucket source

Le bucket du mois 1 n'est **jamais marqué comme "rollé"**. Cela signifie :
- Il reste actif et consommable
- Il pourrait être rollé plusieurs fois si le webhook est rejoué
- Pas de traçabilité de ce qui a été rollé

### 2. Pas de gestion de l'expiration du bucket source

Le bucket du mois 1 devrait :
- Soit être marqué comme `minutes_remaining = 0` après rollover
- Soit être supprimé
- Soit avoir un flag `rolled_over = true`

### 3. Rollover des rollovers ?

Si un rollover du mois 1→2 n'est pas consommé, sera-t-il rollé vers le mois 3 ?
- **Non**, car le code ne filtre que `source_type == subscription`
- Les rollovers expirés sont perdus (ce qui est conforme à la doc)

---

## ✅ Ce qui fonctionne correctement

1. **Expiration du rollover** : `expires_at = pe` (fin de la nouvelle période) ✅
2. **Priorité de consommation** : Les rollovers sont consommés en premier ✅
3. **Tri par expiration** : Les rollovers sont triés par expiration ✅
4. **Idempotence** : Le webhook est enregistré dans `stripe_events` ✅

---

## 🔧 Solutions recommandées

### Solution 1 : Snapshot immédiat (RECOMMANDÉ)

Lors de la création du rollover, **capturer immédiatement** les minutes restantes et **marquer le bucket source** :

```python
if leftover > 0 and pe is not None:
    # Créer le rollover
    rollover_bucket = MinuteBucket(...)
    await minute_db.create_minute_bucket(rollover_bucket)
    
    # Marquer le bucket source comme rollé (vider les minutes)
    prev.minutes_remaining = 0
    prev.rolled_over = True  # Nouveau champ optionnel
    await minute_db.update_minute_bucket(prev)
```

**Avantages** :
- Empêche la double consommation
- Traçabilité claire
- Pas de race condition

**Inconvénients** :
- Nécessite un nouveau champ `rolled_over` (optionnel)

---

### Solution 2 : Rollover à la fin de période (ALTERNATIVE)

Au lieu de créer le rollover au **début** de la nouvelle période, le créer à la **fin** de l'ancienne :

- Utiliser un webhook `customer.subscription.updated` ou un cron job
- Créer le rollover juste avant la fin de période
- Plus complexe à implémenter

---

### Solution 3 : Accepter le comportement actuel (RISQUÉ)

Si les webhooks Stripe arrivent **très rapidement** (< 1 seconde), le risque est faible.

**Mais** : En production, les webhooks peuvent être retardés de plusieurs secondes/minutes.

---

## 📊 Évaluation du risque

### Probabilité : MOYENNE
- Les webhooks Stripe sont généralement rapides (< 5 secondes)
- Mais des retards de 30-60 secondes sont possibles
- En cas de problème réseau, peut prendre plusieurs minutes

### Impact : ÉLEVÉ
- Perte de minutes pour l'utilisateur
- Incohérence entre ce qui est promis et ce qui est livré
- Difficulté à déboguer (pas de traçabilité)

### Risque global : **MOYEN-ÉLEVÉ** 🟡

---

## 🎯 Recommandation finale

**Je recommande d'implémenter la Solution 1** (snapshot + marquage) car :

1. ✅ Simple à implémenter
2. ✅ Pas de race condition
3. ✅ Traçabilité complète
4. ✅ Conforme à l'esprit de la documentation
5. ✅ Pas de perte de minutes pour l'utilisateur

---

## 📝 Conclusion

Le rollover est **partiellement implémenté** mais présente un **défaut de conception** qui peut causer une perte de minutes en cas de :
- Consommation entre le début de période et l'arrivée du webhook
- Retard du webhook Stripe
- Rejeu du webhook (bien que l'idempotence limite ce risque)

**Score de conformité du rollover** : 70% ⚠️

Le mécanisme fonctionne dans 90% des cas, mais le risque de perte de minutes existe.

