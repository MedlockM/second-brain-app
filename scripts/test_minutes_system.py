"""
Script de test pour vérifier le système de gestion des minutes.

Ce script teste :
1. Création de buckets subscription
2. Consommation de minutes dans le bon ordre (par period_end)
3. Nettoyage des holds expirés

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
    """Test de création de buckets subscription."""
    print("\n" + "="*80)
    print("TEST 1: Création de buckets subscription")
    print("="*80)

    user_id = "test_user_minutes_system"
    now = datetime.now(timezone.utc)

    # Créer un bucket subscription pour la période actuelle
    sub_bucket_1 = MinuteBucket(
        id=f"test_sub_1_{int(now.timestamp())}",
        user_id=user_id,
        source_type=MinuteBucketSource.subscription,
        source_ref="sub_test_1",
        minutes_total=240,
        minutes_remaining=240,
        period_start=now,
        period_end=now + timedelta(days=30),
    )
    await minute_db.create_minute_bucket(sub_bucket_1)
    print(f"✅ Bucket subscription 1 créé: {sub_bucket_1.id} (240 min, period +30d)")

    # Créer un deuxième bucket subscription pour la période suivante
    sub_bucket_2 = MinuteBucket(
        id=f"test_sub_2_{int(now.timestamp())}",
        user_id=user_id,
        source_type=MinuteBucketSource.subscription,
        source_ref="sub_test_2",
        minutes_total=300,
        minutes_remaining=300,
        period_start=now + timedelta(days=30),
        period_end=now + timedelta(days=60),
    )
    await minute_db.create_minute_bucket(sub_bucket_2)
    print(f"✅ Bucket subscription 2 créé: {sub_bucket_2.id} (300 min, period +30-60d)")

    # Vérifier le total
    total = await minute_pool.get_total_available_minutes(user_id)
    print(f"\n📊 Total minutes disponibles: {total} min")
    assert total == 540, f"Expected 540, got {total}"
    print("✅ Total correct (240 + 300 = 540)")

    return user_id, sub_bucket_1, sub_bucket_2


async def test_consumption_order(user_id, sub_bucket_1, sub_bucket_2):
    """Test de l'ordre de consommation par period_end."""
    print("\n" + "="*80)
    print("TEST 2: Ordre de consommation (par period_end)")
    print("="*80)

    # Créer un hold et le finaliser
    job_id = f"test_job_{int(datetime.now(timezone.utc).timestamp())}"

    # Allouer et finaliser 100 minutes
    await minute_pool.allocate_hold_for_job(user_id, job_id, minutes_estimated=100)
    print(f"✅ Hold créé pour job {job_id} (100 min)")

    success = await minute_pool.finalize_usage(job_id, minutes_used=100)
    assert success, "Finalization failed"
    print(f"✅ Hold finalisé (100 min consommées)")

    # Vérifier que les minutes du bucket 1 ont été consommées en premier (period_end plus ancien)
    buckets_updated = await minute_db.get_minute_buckets_by_user_id(user_id)
    sub_1_updated = next(b for b in buckets_updated if b.id == sub_bucket_1.id)
    sub_2_updated = next(b for b in buckets_updated if b.id == sub_bucket_2.id)

    print(f"\n📊 Minutes restantes par bucket:")
    print(f"  - Subscription 1 (period +30d): {sub_1_updated.minutes_remaining}/240 (devrait être 140)")
    print(f"  - Subscription 2 (period +30-60d): {sub_2_updated.minutes_remaining}/300 (devrait être 300)")

    assert sub_1_updated.minutes_remaining == 140, \
        f"Expected sub_1 to have 140 min, got {sub_1_updated.minutes_remaining}"
    assert sub_2_updated.minutes_remaining == 300, \
        f"Expected sub_2 to have 300 min, got {sub_2_updated.minutes_remaining}"
    print("✅ Ordre de consommation correct (période la plus ancienne consommée en premier)")

    # Consommer 200 minutes de plus (finir bucket 1 + entamer bucket 2)
    job_id_2 = f"test_job_2_{int(datetime.now(timezone.utc).timestamp())}"
    await minute_pool.allocate_hold_for_job(user_id, job_id_2, minutes_estimated=200)
    success = await minute_pool.finalize_usage(job_id_2, minutes_used=200)
    assert success, "Second finalization failed"
    print(f"\n✅ 200 min supplémentaires consommées")

    # Vérifier
    buckets_final = await minute_db.get_minute_buckets_by_user_id(user_id)
    sub_1_final = next(b for b in buckets_final if b.id == sub_bucket_1.id)
    sub_2_final = next(b for b in buckets_final if b.id == sub_bucket_2.id)

    print(f"\n📊 État final:")
    print(f"  - Subscription 1: {sub_1_final.minutes_remaining}/240 (devrait être 0)")
    print(f"  - Subscription 2: {sub_2_final.minutes_remaining}/300 (devrait être 100)")

    assert sub_1_final.minutes_remaining == 0, "Sub_1 should be empty"
    assert sub_2_final.minutes_remaining == 100, "Sub_2 should have 100 min"
    print("✅ Consommation correcte sur plusieurs buckets subscription")


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
        user_id, sub_bucket_1, sub_bucket_2 = await test_bucket_creation()

        # Test 2: Ordre de consommation
        await test_consumption_order(user_id, sub_bucket_1, sub_bucket_2)

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
