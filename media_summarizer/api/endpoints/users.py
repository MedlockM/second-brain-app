"""
Endpoints pour la gestion des utilisateurs.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from media_summarizer.adapters.database.connection import get_db

router = APIRouter()

class UserCreate(BaseModel):
    """Modèle pour la création d'un utilisateur."""
    email: EmailStr
    password: str
    
    from pydantic import field_validator
    
    @field_validator('password')
    @classmethod
    def password_must_not_be_empty(cls, v):
        """Valide que le mot de passe n'est pas vide."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Le mot de passe ne peut pas être vide")
        return v

class UserResponse(BaseModel):
    """Modèle pour la réponse utilisateur."""
    id: str
    email: str

@router.post("/register", response_model=UserResponse)
async def register_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre un nouvel utilisateur.
    """
    # TODO: Implémenter la création d'utilisateur
    
    return UserResponse(
        id="user-id",
        email=user.email,
    )

@router.post("/login")
async def login_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Connecte un utilisateur existant.
    """
    # TODO: Implémenter la connexion utilisateur
    
    return {"access_token": "dummy_token", "token_type": "bearer"}