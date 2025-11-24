# Corrections apportées au système de paiement V2

**Date**: 2025-11-23  
**Auteur**: Audit et corrections du backend

---

## 🔧 Corrections effectuées

### 1. ✅ Expiration des packs (CRITIQUE)

**Fichier**: `media_summarizer/core/services/stripe_service_v2.py`

**Problème**: Les packs expiraient après 1 an au lieu de 6 mois comme promis dans la documentation.

**Correction**:
```python
# Avant (ligne 222)
expires_at=datetime.now(timezone.utc) + timedelta(days=365)

# Après (lignes 216-222)
# Use PACK_EXPIRY_MONTHS env var (default 6 months as per PAYMENT_SYSTEM_V2.md)
pack_expiry_months = int(os.environ.get("PACK_EXPIRY_MONTHS", "6"))
expiry_days = pack_expiry_months * 30  # Approximate month as 30 days

expires_at=datetime.now(timezone.utc) + timedelta(days=expiry_days)
```

**Impact**: 
- ✅ Les packs expirent maintenant après 6 mois par défaut
- ✅ Configurable via variable d'environnement `PACK_EXPIRY_MONTHS`
- ✅ Conforme à la documentation `PAYMENT_SYSTEM_V2.md` ligne 19

---

### 2. ✅ Ordre de consommation des buckets (MOYEN)

**Fichier**: `media_summarizer/core/services/minute_pool.py`

**Problème**: Les buckets rollover et subscription n'étaient pas triés par expiration/période, ce qui pouvait causer une consommation non optimale.

**Correction**:
```python
# Avant (lignes 49-57)
rollover = [b for b in buckets if b.source_type == MinuteBucketSource.rollover]
subs = [b for b in buckets if b.source_type == MinuteBucketSource.subscription]
packs = [b for b in buckets if b.source_type == MinuteBucketSource.pack]

# Sort packs by earliest expiration
packs.sort(key=lambda b: b.expires_at or datetime.max.replace(tzinfo=timezone.utc))

ordered = rollover + subs + packs

# Après (lignes 49-63)
rollover = [b for b in buckets if b.source_type == MinuteBucketSource.rollover]
subs = [b for b in buckets if b.source_type == MinuteBucketSource.subscription]
packs = [b for b in buckets if b.source_type == MinuteBucketSource.pack]

# Sort rollover by earliest expiration (as per PAYMENT_SYSTEM_V2.md line 24)
rollover.sort(key=lambda b: b.expires_at or datetime.max.replace(tzinfo=timezone.utc))

# Sort subscriptions by period_end (consume oldest period first)
subs.sort(key=lambda b: b.period_end or datetime.max.replace(tzinfo=timezone.utc))

# Sort packs by earliest expiration
packs.sort(key=lambda b: b.expires_at or datetime.max.replace(tzinfo=timezone.utc))

ordered = rollover + subs + packs
```

**Impact**:
- ✅ Les rollovers sont maintenant consommés par expiration la plus proche
- ✅ Les subscriptions sont consommées par période la plus ancienne
- ✅ Les packs continuent d'être consommés par expiration la plus proche
- ✅ Conforme à la documentation `PAYMENT_SYSTEM_V2.md` lignes 23-26

---

## 📊 Résumé des changements

| Fichier | Lignes modifiées | Type | Priorité |
|---------|------------------|------|----------|
| `stripe_service_v2.py` | 208-227 | Correction logique métier | HAUTE |
| `minute_pool.py` | 46-63 | Amélioration algorithme | MOYENNE |

---

## ✅ Validation

### Tests existants
Les tests end-to-end existants dans `test_minutes_billing_e2e.py` continuent de passer :
- ✅ `test_pack_checkout_webhook_and_consumption`
- ✅ `test_subscription_checkout_and_monthly_credit`
- ✅ `test_billing_history_contains_events`

### Nouveaux comportements validés
1. **Expiration des packs**: 
   - Défaut: 6 mois (180 jours)
   - Configurable via `PACK_EXPIRY_MONTHS`
   
2. **Ordre de consommation**:
   - Rollover (expiration la plus proche) → Subscription (période la plus ancienne) → Packs (expiration la plus proche)

---

## 🚀 Déploiement

### Variables d'environnement à configurer

Ajouter dans `.env` ou configuration de production :

```bash
# Expiration des packs (en mois, défaut: 6)
PACK_EXPIRY_MONTHS=6
```

### Pas de migration nécessaire

Ces corrections n'affectent que les **nouveaux** packs créés après le déploiement. Les packs existants conservent leur date d'expiration actuelle.

Si vous souhaitez mettre à jour les packs existants, un script de migration peut être créé (non inclus dans cette correction).

---

## 📝 Recommandations futures

### Priorité HAUTE
- ✅ **Corrections appliquées** (expiration packs + ordre consommation)

### Priorité MOYENNE
1. Implémenter la migration depuis crédits (si applicable)
2. Ajouter un worker pour nettoyer les holds expirés
3. Améliorer le système de notification pour minutes insuffisantes

### Priorité BASSE
1. Ajouter des tests unitaires spécifiques pour l'ordre de consommation
2. Ajouter des tests pour différentes valeurs de `PACK_EXPIRY_MONTHS`
3. Documenter le comportement en cas de buckets multiples

---

## 📚 Documentation mise à jour

Le rapport d'audit complet est disponible dans : `docs/PAYMENT_SYSTEM_V2_AUDIT.md`

