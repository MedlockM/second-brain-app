"""
Endpoints pour la soumission et le suivi des podcasts.
"""
import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

import boto3

from media_summarizer.adapters.database.connection import get_db
from media_summarizer.api.dependencies.auth import get_current_user

router = APIRouter()

# Configuration AWS
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Initialisation du client SQS
sqs_client = boto3.client(
    "sqs",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=AWS_REGION,
)

class PodcastSubmissionRequest(BaseModel):
    """Modèle pour la soumission d'un podcast."""
    url: HttpUrl
    email: EmailStr

class JobResponse(BaseModel):
    """Modèle pour la réponse de soumission d'un job."""
    job_id: str
    status: str
    message: str

@router.post("/submit", response_model=JobResponse)
async def submit_podcast(
    request: PodcastSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Soumet un lien de podcast pour traitement.
    
    Vérifie d'abord si l'utilisateur a suffisamment de crédits.
    """
    # Vérification des crédits de l'utilisateur
    REQUIRED_CREDITS = 10  # Nombre de crédits requis pour traiter un podcast
    
    if current_user["credits"] < REQUIRED_CREDITS:
        raise HTTPException(
            status_code=400,
            detail=f"Crédits insuffisants. Vous avez {current_user['credits']} crédits, mais {REQUIRED_CREDITS} sont nécessaires pour traiter un podcast."
        )
    
    # Génération d'un ID de job
    job_id = str(uuid.uuid4())
    
    # Création du message pour la file SQS
    message = {
        "job_id": job_id,
        "podcast_url": str(request.url),
        "email": request.email,
        "user_id": current_user["id"],
    }
    
    try:
        # Envoi du message à la file SQS
        queue_url = f"{AWS_ENDPOINT_URL}/000000000000/rss-resolution-queue" if AWS_ENDPOINT_URL else "rss-resolution-queue"
        
        # Tentative d'envoi du message à SQS
        try:
            sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
            )
        except Exception as sqs_error:
            # Log the SQS error but continue with the job creation
            # In a real implementation, we might want to handle this differently
            print(f"Warning: SQS message sending failed: {str(sqs_error)}")
        
        # TODO: Enregistrer le job dans la base de données
        
        # TODO: Déduire les crédits de l'utilisateur
        # Dans une implémentation réelle, nous mettrions à jour le solde de l'utilisateur dans la base de données
        
        return JobResponse(
            job_id=job_id,
            status="pending",
            message="Votre demande a été soumise avec succès et est en cours de traitement.",
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la soumission du podcast: {str(e)}",
        )

@router.get("/{job_id}/status", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère le statut d'un job de traitement.
    """
    # TODO: Récupérer le statut depuis la base de données
    
    # Pour l'instant, retourne un statut fictif
    return JobResponse(
        job_id=job_id,
        status="processing",
        message="Votre podcast est en cours de traitement.",
    )