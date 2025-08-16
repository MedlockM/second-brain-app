"""
Endpoints pour la gestion des utilisateurs.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async
from media_summarizer.core.models import User

router = APIRouter()


class UserCreateRequest(BaseModel):
    """Modèle pour la création d'un utilisateur."""
    email: EmailStr


class UserResponse(BaseModel):
    """Modèle pour la réponse utilisateur."""
    id: str
    email: str
    credits: int
    created_at: str
    updated_at: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        """Convertit un objet User en UserResponse."""
        return cls(
            id=user.id,
            email=user.email,
            credits=user.credits,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )


class UserUpdateRequest(BaseModel):
    """Modèle pour la mise à jour d'un utilisateur."""
    email: Optional[EmailStr] = None


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    db=Depends(get_db)
):
    """
    Crée un nouveau utilisateur.

    Args:
        user_data: Données de l'utilisateur à créer
        db: Connexion à la base de données

    Returns:
        L'utilisateur créé

    Raises:
        HTTPException: Si l'email existe déjà
    """
    # Vérifier si l'utilisateur existe déjà
    existing_user = await database_async.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà"
        )

    # Créer le nouvel utilisateur
    new_user = User(
        email=user_data.email,
        credits=0  # Nouveaux utilisateurs commencent avec 0 crédits
    )

    try:
        created_user = await database_async.create_user(new_user)
        return UserResponse.from_user(created_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de l'utilisateur: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db=Depends(get_db)
):
    """
    Récupère un utilisateur par son ID.

    Args:
        user_id: L'ID de l'utilisateur
        db: Connexion à la base de données

    Returns:
        L'utilisateur trouvé

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    user = await database_async.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    return UserResponse.from_user(user)


@router.get("/email/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: EmailStr,
    db=Depends(get_db)
):
    """
    Récupère un utilisateur par son email.

    Args:
        email: L'email de l'utilisateur
        db: Connexion à la base de données

    Returns:
        L'utilisateur trouvé

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    user = await database_async.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    return UserResponse.from_user(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    db=Depends(get_db)
):
    """
    Met à jour un utilisateur.

    Args:
        user_id: L'ID de l'utilisateur
        user_data: Nouvelles données de l'utilisateur
        db: Connexion à la base de données

    Returns:
        L'utilisateur mis à jour

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou si l'email est déjà utilisé
    """
    # Récupérer l'utilisateur existant
    user = await database_async.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )

    # Vérifier si le nouvel email existe déjà (si fourni)
    if user_data.email and user_data.email != user.email:
        existing_user = await database_async.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un utilisateur avec cet email existe déjà"
            )

    # Mettre à jour les champs modifiés
    update_data = {}
    if user_data.email:
        update_data["email"] = user_data.email

    if update_data:
        user.update(**update_data)
        try:
            updated_user = await database_async.update_user(user)
            return UserResponse.from_user(updated_user)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la mise à jour: {str(e)}"
            )

    return UserResponse.from_user(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db=Depends(get_db)
):
    """
    Supprime un utilisateur.

    Args:
        user_id: L'ID de l'utilisateur
        db: Connexion à la base de données

    Raises:
        HTTPException: Si l'utilisateur n'existe pas
    """
    success = await database_async.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
