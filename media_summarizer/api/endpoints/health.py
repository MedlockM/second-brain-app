"""
Endpoints pour la vérification de l'état du service.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import asyncio
import httpx

from media_summarizer.utils.database_async import get_db

router = APIRouter()


@router.get("/", response_model=Dict[str, Any])
async def health_check(db=Depends(get_db)):
    """
    Vérifie l'état de santé du service.

    Returns:
        Dict contenant l'état de santé du service
    """
    try:
        # Test de la connexion DynamoDB
        async with await db.get_client() as client:
            # Simple test pour vérifier la connectivité
            await client.list_tables()

        return {
            "status": "healthy",
            "service": "Media Summarizer API",
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db=Depends(get_db)):
    """
    Vérifie l'état de santé détaillé du service.

    Returns:
        Dict contenant l'état détaillé de tous les composants
    """
    health_status = {
        "status": "healthy",
        "service": "Media Summarizer API",
        "version": "1.0.0",
        "components": {}
    }

    # Test de la base de données DynamoDB
    try:
        async with await db.get_client() as client:
            response = await client.list_tables()
            tables = response.get('TableNames', [])
            health_status["components"]["database"] = {
                "status": "healthy",
                "type": "DynamoDB",
                "tables_count": len(tables),
                "tables": tables
            }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "type": "DynamoDB",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # Déterminer le statut global
    if any(component.get("status") == "unhealthy"
           for component in health_status["components"].values()):
        health_status["status"] = "unhealthy"
        raise HTTPException(
            status_code=503,
            detail=health_status
        )

    return health_status


@router.get("/system", response_model=Dict[str, Any])
async def system_status():
    """
    Get comprehensive system status including infrastructure services.

    Returns:
        Dict containing status of all system components
    """
    system_status = {
        "status": "healthy",
        "infrastructure": {},
        "message": "System status check completed"
    }

    # Check LocalStack
    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.get("http://localhost:4566/_localstack/health")
            if response.status_code == 200:
                localstack_data = response.json()
                system_status["infrastructure"]["localstack"] = {
                    "status": "healthy",
                    "services": localstack_data.get("services", {})
                }
            else:
                system_status["infrastructure"]["localstack"] = {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}"
                }
                system_status["status"] = "degraded"
    except Exception as e:
        system_status["infrastructure"]["localstack"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        system_status["status"] = "degraded"

    # Check API health (self-check)
    system_status["infrastructure"]["api"] = {
        "status": "healthy",
        "message": "API is responding"
    }

    return system_status
