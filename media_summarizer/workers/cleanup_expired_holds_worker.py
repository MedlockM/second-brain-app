"""
Worker pour nettoyer les holds expirés dans la table minute_usage.

Ce worker s'exécute périodiquement pour :
1. Identifier les holds expirés (hold_expires_at < now)
2. Les marquer comme 'expired'
3. Optionnellement envoyer une notification à l'utilisateur

Déploiement :
- En local : peut être exécuté manuellement ou via cron
- En production : déclenché par EventBridge (voir infrastructure/terraform)
"""
from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from media_summarizer.utils import minute_db
from media_summarizer.core.models.billing import MinuteUsage, MinuteUsageStatus

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = int(os.environ.get("EXPIRED_HOLDS_BATCH_SIZE", "100"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


async def find_expired_holds() -> List[MinuteUsage]:
    """
    Trouve tous les holds expirés dans la table minute_usage.
    
    Returns:
        Liste des MinuteUsage avec status='held' et hold_expires_at < now
    """
    logger.info("Scanning minute_usage table for expired holds...")
    
    try:
        expired_holds = await minute_db.scan_expired_holds(limit=BATCH_SIZE)
        logger.info(f"Found {len(expired_holds)} expired holds")
        return expired_holds
    except Exception as e:
        logger.error(f"Error scanning for expired holds: {e}")
        return []



async def mark_hold_as_expired(usage: MinuteUsage) -> bool:
    """
    Marque un hold comme expiré.
    
    Args:
        usage: L'objet MinuteUsage à marquer comme expiré
        
    Returns:
        True si succès, False sinon
    """
    try:
        if usage.status != MinuteUsageStatus.held:
            logger.warning(f"Usage {usage.id} is not in 'held' status, skipping")
            return False
            
        usage.status = MinuteUsageStatus.expired
        
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would mark usage {usage.id} (job {usage.job_id}) as expired")
            return True
        
        await minute_db.update_minute_usage(usage)
        logger.info(f"Marked usage {usage.id} (job {usage.job_id}) as expired")
        return True
        
    except Exception as e:
        logger.error(f"Failed to mark usage {usage.id} as expired: {e}")
        return False


async def cleanup_expired_holds() -> dict:
    """
    Nettoie tous les holds expirés.
    
    Returns:
        Dictionnaire avec les statistiques de nettoyage
    """
    logger.info("Starting expired holds cleanup...")
    
    stats = {
        "total_found": 0,
        "total_marked": 0,
        "total_failed": 0,
        "dry_run": DRY_RUN
    }
    
    try:
        expired_holds = await find_expired_holds()
        stats["total_found"] = len(expired_holds)
        
        logger.info(f"Found {len(expired_holds)} expired holds")
        
        for usage in expired_holds:
            success = await mark_hold_as_expired(usage)
            if success:
                stats["total_marked"] += 1
            else:
                stats["total_failed"] += 1
                
        logger.info(f"Cleanup complete: {stats}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        stats["error"] = str(e)
    
    return stats


async def main() -> None:
    """Point d'entrée principal du worker."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info("Expired Holds Cleanup Worker")
    logger.info(f"DRY_RUN: {DRY_RUN}")
    logger.info(f"BATCH_SIZE: {BATCH_SIZE}")
    logger.info("=" * 80)
    
    stats = await cleanup_expired_holds()
    
    logger.info("=" * 80)
    logger.info(f"Final stats: {stats}")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
