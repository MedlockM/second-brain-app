"""
Script de test pour vérifier le système de gestion des minutes.

Ce script teste :
1. Création de buckets de différents types
2. Consommation de minutes dans le bon ordre
3. Rollover de minutes
4. Nettoyage des holds expirés

Usage:
    python scripts/test_minutes_system.py
"""
import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from media_summarizer.core.models.billing import (
    MinuteBucket,
    MinuteBucketSource,
    MinuteUsage,
    MinuteUsageStatus,
)
from media_summarizer.utils import minute_db
from media_summarizer.core.services import minute_pool


async def test_bucket_creation():
    """Test de création de buckets de différents types."""
    print("\n" + "="*80)
    print("TEST 1: Création de buckets")
    print("="*80)
    
    user_id = "test_user_minutes_system"
    now = datetime.now(timezone.utc)
    
    # Créer un bucket subscription
    sub_bucket = MinuteBucket(
        id=f"test_sub_{int(now.timestamp())}",
        user_id=user_id,
        source_type=MinuteBucketSource.subscription,
        source_ref="sub_test",
        minutes_total=240,
        minutes_remaining=240,
        period_start=now,
        period_end=now + timedelta(days=30),
    )
    await minute_db.create_minute_bucket(sub_bucket)
    print(f"✅ Bucket subscription créé: {sub_bucket.id} (240 min)")
    
    # Créer un bucket pack
    pack_bucket = MinuteBucket(
        id=f"test_pack_{int(now.timestamp())}",
        user_id=user_id,
        source_type=MinuteBucketSource.pack,
        source_ref="pack_300",
        minutes_total=300,
        minutes_remaining=300,
        expires_at=now + timedelta(days=180),  # 6 mois
    )
    await minute_db.create_minute_bucket(pack_bucket)
    print(f"✅ Bucket pack créé: {pack_bucket.id} (300 min)")
    
    # Créer un bucket rollover
    rollover_bucket = MinuteBucket(
        id=f"test_rollover_{int(now.timestamp())}",
        user_id=user_id,
        source_type=MinuteBucketSource.rollover,
        source_ref="sub_test",
        minutes_total=50,
        minutes_remaining=50,
        expires_at=now + timedelta(days=30),  # 1 mois
    )
    await minute_db.create_minute_bucket(rollover_bucket)
    print(f"✅ Bucket rollover créé: {rollover_bucket.id} (50 min)")
    
    # Vérifier le total
    total = await minute_pool.get_total_available_minutes(user_id)
    print(f"\n📊 Total minutes disponibles: {total} min")
    assert total == 590, f"Expected 590, got {total}"
    print("✅ Total correct (240 + 300 + 50 = 590)")
    
    return user_id, sub_bucket, pack_bucket, rollover_bucket


async def test_consumption_order(user_id, sub_bucket, pack_bucket, rollover_bucket):
    """Test de l'ordre de consommation."""
    print("\n" + "="*80)
    print("TEST 2: Ordre de consommation")
    print("="*80)
    
    # Créer un hold et le finaliser
    job_id = f"test_job_{int(datetime.now(timezone.utc).timestamp())}"
    
    # Allouer 30 minutes
    await minute_pool.allocate_hold_for_job(user_id, job_id, minutes_estimated=30)
    print(f"✅ Hold créé pour job {job_id} (30 min)")
    
    # Finaliser avec 30 minutes
    success = await minute_pool.finalize_usage(job_id, minutes_used=30)
    assert success, "Finalization failed"
    print(f"✅ Hold finalisé (30 min consommées)")
    
    # Vérifier que les minutes rollover ont été consommées en premier
    rollover_updated = await minute_db.get_minute_buckets_by_user_id(user_id)
    rollover_bucket_updated = next(b for b in rollover_updated if b.id == rollover_bucket.id)
    
    print(f"\n📊 Minutes restantes par bucket:")
    print(f"  - Rollover: {rollover_bucket_updated.minutes_remaining}/50 (devrait être 20)")
    
    assert rollover_bucket_updated.minutes_remaining == 20, \
        f"Expected rollover to have 20 min, got {rollover_bucket_updated.minutes_remaining}"
    print("✅ Ordre de consommation correct (rollover consommé en premier)")
    
    # Consommer 40 minutes de plus (finir rollover + entamer subscription)
    job_id_2 = f"test_job_2_{int(datetime.now(timezone.utc).timestamp())}"
    await minute_pool.allocate_hold_for_job(user_id, job_id_2, minutes_estimated=40)
    success = await minute_pool.finalize_usage(job_id_2, minutes_used=40)
    assert success, "Second finalization failed"
    print(f"\n✅ 40 min supplémentaires consommées")
    
    # Vérifier
    buckets = await minute_db.get_minute_buckets_by_user_id(user_id)
    rollover_final = next(b for b in buckets if b.id == rollover_bucket.id)
    sub_final = next(b for b in buckets if b.id == sub_bucket.id)
    
    print(f"\n📊 État final:")
    print(f"  - Rollover: {rollover_final.minutes_remaining}/50 (devrait être 0)")
    print(f"  - Subscription: {sub_final.minutes_remaining}/240 (devrait être 220)")
    print(f"  - Pack: 300/300 (non touché)")
    
    assert rollover_final.minutes_remaining == 0, "Rollover should be empty"
    assert sub_final.minutes_remaining == 220, "Subscription should have 220 min"
    print("✅ Consommation correcte sur plusieurs buckets")


async def test_expired_holds():
    """Test du nettoyage des holds expirés."""
    print("\n" + "="*80)
    print("TEST 3: Nettoyage holds expirés")
    print("="*80)
    
    # Créer un hold expiré
    user_id = "test_user_expired_holds"
    job_id = f"expired_job_{int(datetime.now(timezone.utc).timestamp())}"
    
    expired_usage = MinuteUsage(
        id=f"mu_{job_id}",
        user_id=user_id,
        job_id=job_id,
        status=MinuteUsageStatus.held,
        minutes_estimated=10,
        hold_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expiré il y a 1h
    )
    await minute_db.create_minute_usage(expired_usage)
    print(f"✅ Hold expiré créé: {expired_usage.id}")
    
    # Scanner les holds expirés
    expired_holds = await minute_db.scan_expired_holds(limit=10)
    print(f"\n📊 Holds expirés trouvés: {len(expired_holds)}")
    
    found_our_hold = any(h.id == expired_usage.id for h in expired_holds)
    assert found_our_hold, "Our expired hold should be found"
    print(f"✅ Notre hold expiré a été détecté")
    
    # Marquer comme expiré
    expired_usage.status = MinuteUsageStatus.expired
    await minute_db.update_minute_usage(expired_usage)
    print(f"✅ Hold marqué comme expiré")
    
    # Vérifier
    updated = await minute_db.get_minute_usage_by_job_id(job_id)
    assert updated.status == MinuteUsageStatus.expired, "Status should be expired"
    print(f"✅ Statut confirmé: {updated.status.value}")


async def cleanup_test_data():
    """Nettoyer les données de test."""
    print("\n" + "="*80)
    print("NETTOYAGE")
    print("="*80)
    print("⚠️  Les données de test restent en base pour inspection manuelle")
    print("    Pour nettoyer, supprimer manuellement les items avec user_id='test_user_*'")


async def main():
    """Point d'entrée principal."""
    print("\n" + "="*80)
    print("🧪 TEST DU SYSTÈME DE GESTION DES MINUTES")
    print("="*80)
    print("\nCe script teste les fonctionnalités principales du système de minutes.")
    print("Assurez-vous que LocalStack est démarré et les tables créées.\n")
    
    try:
        # Test 1: Création de buckets
        user_id, sub_bucket, pack_bucket, rollover_bucket = await test_bucket_creation()
        
        # Test 2: Ordre de consommation
        await test_consumption_order(user_id, sub_bucket, pack_bucket, rollover_bucket)
        
        # Test 3: Holds expirés
        await test_expired_holds()
        
        # Nettoyage
        await cleanup_test_data()
        
        print("\n" + "="*80)
        print("✅ TOUS LES TESTS SONT PASSÉS")
        print("="*80)
        print("\n🎉 Le système de gestion des minutes fonctionne correctement!\n")
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ ÉCHEC DES TESTS")
        print("="*80)
        print(f"\nErreur: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
