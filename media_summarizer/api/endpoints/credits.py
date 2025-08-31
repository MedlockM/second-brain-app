"""
Endpoints pour la gestion des crédits.

Note: L'endpoint /credits/purchase est déprécié en faveur des nouveaux endpoints de paiement Stripe.
Utilisez /payments/intent et /payments/confirm pour les nouveaux achats de crédits.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
import uuid

from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async
from media_summarizer.core.models import User, CreditTransaction
from media_summarizer.api.dependencies.auth import require_verified_email

router = APIRouter()


class CreditPurchaseRequest(BaseModel):
    """Modèle pour l'achat de crédits."""
    user_id: str = Field(..., description="ID de l'utilisateur")
    amount: int = Field(..., gt=0, description="Nombre de crédits à acheter")
    payment_method: str = Field(..., description="Méthode de paiement")
    description: Optional[str] = Field(None, description="Description de l'achat")

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Le nombre de crédits doit être positif')
        return v


class CreditDeductionRequest(BaseModel):
    """Modèle pour la déduction de crédits."""
    user_id: str = Field(..., description="ID de l'utilisateur")
    amount: int = Field(..., gt=0, description="Nombre de crédits à déduire")
    job_id: Optional[str] = Field(None, description="ID du job associé")
    description: Optional[str] = Field(None, description="Description de la déduction")

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Le nombre de crédits doit être positif')
        return v


class CreditRefundRequest(BaseModel):
    """Modèle pour le remboursement de crédits."""
    user_id: str = Field(..., description="ID de l'utilisateur")
    amount: int = Field(..., gt=0, description="Nombre de crédits à rembourser")
    job_id: Optional[str] = Field(None, description="ID du job associé")
    reason: str = Field(..., description="Raison du remboursement")

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Le nombre de crédits doit être positif')
        return v


class CreditBalanceResponse(BaseModel):
    """Modèle pour la réponse du solde de crédits."""
    user_id: str
    credits: int
    last_updated: str

    @classmethod
    def from_user(cls, user: User) -> "CreditBalanceResponse":
        """Convertit un objet User en CreditBalanceResponse."""
        return cls(
            user_id=user.id,
            credits=user.credits,
            last_updated=user.updated_at.isoformat()
        )


class CreditTransactionResponse(BaseModel):
    """Modèle pour la réponse d'une transaction de crédits."""
    id: str
    user_id: str
    amount: int
    type: str
    description: Optional[str]
    job_id: Optional[str]
    created_at: str

    @classmethod
    def from_transaction(cls, transaction: CreditTransaction) -> "CreditTransactionResponse":
        """Convertit un objet CreditTransaction en CreditTransactionResponse."""
        return cls(
            id=transaction.id,
            user_id=transaction.user_id,
            amount=transaction.amount,
            type=transaction.type,
            description=transaction.description,
            job_id=transaction.job_id,
            created_at=transaction.created_at.isoformat()
        )


@router.get("/users/{user_id}/credits", response_model=CreditBalanceResponse)
async def get_user_credits(
    user_id: str,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Récupère le solde de crédits d'un utilisateur.

    Args:
        user_id: L'ID de l'utilisateur
        db: Connexion à la base de données

    Returns:
        Le solde de crédits de l'utilisateur

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    user = await database_async.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    return CreditBalanceResponse.from_user(user)


@router.post("/credits/purchase", response_model=CreditBalanceResponse, deprecated=True)
async def purchase_credits(
    purchase_request: CreditPurchaseRequest,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Achète des crédits pour un utilisateur.

    **DÉPRÉCIÉ**: Cet endpoint est déprécié. Utilisez les nouveaux endpoints de paiement Stripe:
    - POST /api/v1/payments/intent pour créer un intent de paiement
    - POST /api/v1/payments/confirm pour confirmer le paiement

    Args:
        purchase_request: Données de la demande d'achat
        db: Connexion à la base de données

    Returns:
        Le nouveau solde de crédits

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou si l'achat échoue
    """
    # Vérifier que l'utilisateur existe
    user = await database_async.get_user_by_id(purchase_request.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Log deprecation warning
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"DEPRECATED: Direct credit purchase used for user {purchase_request.user_id}. "
                   f"Please migrate to Stripe payment endpoints.")

    # Reject Stripe payment method to encourage migration
    if purchase_request.payment_method.lower() == "stripe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct Stripe purchases are no longer supported. Use /api/v1/payments/intent endpoint instead."
        )

    try:
        # Créer la transaction d'achat (pour compatibilité avec méthodes non-Stripe)
        transaction = CreditTransaction.create_purchase(
            user_id=purchase_request.user_id,
            amount=purchase_request.amount,
            description=purchase_request.description or f"Achat direct de {purchase_request.amount} crédits (DEPRECATED)"
        )
        await database_async.create_credit_transaction(transaction)

        # Mettre à jour le solde de l'utilisateur
        new_credits = user.credits + purchase_request.amount
        updated_user = await database_async.update_user_credits(
            purchase_request.user_id,
            new_credits
        )

        return CreditBalanceResponse.from_user(updated_user)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'achat de crédits: {str(e)}"
        )


@router.post("/credits/deduct", response_model=CreditBalanceResponse)
async def deduct_credits(
    deduction_request: CreditDeductionRequest,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Déduit des crédits d'un utilisateur.

    Args:
        deduction_request: Données de la demande de déduction
        db: Connexion à la base de données

    Returns:
        Le nouveau solde de crédits

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou n'a pas assez de crédits
    """
    # Vérifier que l'utilisateur existe
    user = await database_async.get_user_by_id(deduction_request.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Vérifier que l'utilisateur a assez de crédits
    if user.credits < deduction_request.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Crédits insuffisants. Disponible: {user.credits}, Requis: {deduction_request.amount}"
        )

    try:
        # Créer la transaction de déduction
        transaction = CreditTransaction.create_deduction(
            user_id=deduction_request.user_id,
            amount=deduction_request.amount,
            job_id=deduction_request.job_id,
            description=deduction_request.description or f"Déduction de {deduction_request.amount} crédits"
        )
        await database_async.create_credit_transaction(transaction)

        # Mettre à jour le solde de l'utilisateur
        new_credits = user.credits - deduction_request.amount
        updated_user = await database_async.update_user_credits(
            deduction_request.user_id,
            new_credits
        )

        return CreditBalanceResponse.from_user(updated_user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la déduction de crédits: {str(e)}"
        )


@router.post("/credits/refund", response_model=CreditBalanceResponse)
async def refund_credits(
    refund_request: CreditRefundRequest,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Rembourse des crédits à un utilisateur.

    Args:
        refund_request: Données de la demande de remboursement
        db: Connexion à la base de données

    Returns:
        Le nouveau solde de crédits

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou si le remboursement échoue
    """
    # Vérifier que l'utilisateur existe
    user = await database_async.get_user_by_id(refund_request.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    try:
        # Créer la transaction de remboursement
        transaction = CreditTransaction.create_refund(
            user_id=refund_request.user_id,
            amount=refund_request.amount,
            job_id=refund_request.job_id,
            description=f"Remboursement: {refund_request.reason}"
        )
        await database_async.create_credit_transaction(transaction)

        # Mettre à jour le solde de l'utilisateur
        new_credits = user.credits + refund_request.amount
        updated_user = await database_async.update_user_credits(
            refund_request.user_id,
            new_credits
        )

        return CreditBalanceResponse.from_user(updated_user)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du remboursement de crédits: {str(e)}"
        )


@router.get("/users/{user_id}/credits/transactions", response_model=List[CreditTransactionResponse])
async def get_user_credit_transactions(
    user_id: str,
    limit: Optional[int] = 50,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Récupère l'historique des transactions de crédits d'un utilisateur.

    Args:
        user_id: L'ID de l'utilisateur
        limit: Nombre maximum de transactions à retourner
        db: Connexion à la base de données

    Returns:
        Liste des transactions de crédits

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    # Vérifier que l'utilisateur existe
    user = await database_async.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    try:
        transactions = await database_async.get_credit_transactions_by_user_id(user_id)
        # Apply limit if specified
        if limit and len(transactions) > limit:
            transactions = transactions[:limit]
        return [CreditTransactionResponse.from_transaction(tx) for tx in transactions]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des transactions: {str(e)}"
        )


@router.get("/credits/transactions/{transaction_id}", response_model=CreditTransactionResponse)
async def get_credit_transaction(
    transaction_id: str,
    db=Depends(get_db),
    current_user=Depends(require_verified_email)
):
    """
    Récupère une transaction de crédits par son ID.

    Args:
        transaction_id: L'ID de la transaction
        db: Connexion à la base de données

    Returns:
        La transaction de crédits

    Raises:
        HTTPException: Si la transaction n'existe pas
    """
    transaction = await database_async.get_credit_transaction_by_id(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction non trouvée"
        )

    return CreditTransactionResponse.from_transaction(transaction)
