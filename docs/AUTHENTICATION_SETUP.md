# Authentication Setup Guide

This document describes the current authentication system for Media Summarizer after removal of magic links.

Overview
- Local authentication (email + password)
- JWT access tokens for API calls (short-lived)
- Refresh tokens stored as httpOnly cookies (30 days, expiration absolue)
- Optional future: Social OAuth (Google/Apple) — see PLAN.md

Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend/     │    │   API Server     │    │   Database      │
│   Client        │    │                  │    │                 │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│ 1. Register /   │───▶│ POST /auth/      │    │ DynamoDB:       │
│    Login        │    │ register, login  │    │ • users         │
│                 │    │                  │    │ • auth_tokens   │
│                 │    │                  │    │                 │
│ 2. Access token │◀───│ Return access    │    │                 │
│    + refresh    │    │ token + set      │    │                 │
│    cookie       │    │ refresh cookie   │    │                 │
│                 │    │ (httpOnly)       │    │                 │
│ 3. Use access   │───▶│ Protected        │    │                 │
│    token        │    │ endpoints        │    │                 │
│                 │    │                  │    │                 │
│ 4. Token expiry │───▶│ POST /auth/      │    │                 │
│                 │    │ refresh (rotate) │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

Environment Variables
- JWT_SECRET_KEY or SECRET_KEY: clé de signature JWT
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES: durée de l’access token (par défaut 30)
- REFRESH_TOKEN_EXPIRE_DAYS: durée du refresh token (par défaut 30, absolue)
- COOKIE_NAME_REFRESH: nom du cookie (refresh_token)
- COOKIE_SECURE: true en production (HTTPS requis)
- COOKIE_SAMESITE: Lax/Strict/None
- COOKIE_DOMAIN: domaine du cookie (optionnel en local)

Database Schema
- users: id (PK), email (GSI email-index), credits, password_hash (optionnel), auth_provider/provider_id (optionnels)
- auth_tokens: id (PK), token (GSI), user_id (GSI), token_type (RANGE sur user-type-index), expires_at, used_at, is_active

API Endpoints
- POST /api/v1/auth/register
  - Body: { "email": "...", "password": "..." }
  - Crée l’utilisateur, pose un refresh cookie (30j), renvoie un access token + infos user
- POST /api/v1/auth/login
  - Body: { "email": "...", "password": "..." }
  - Vérifie les credentials, pose un refresh cookie (30j), renvoie un access token + infos user
- POST /api/v1/auth/refresh
  - Utilise le refresh cookie; rotate le refresh (même expiration absolue) et renvoie un nouvel access token
- POST /api/v1/auth/logout
  - Révoque les refresh tokens de l’utilisateur et efface le cookie
- GET /api/v1/auth/me
  - Renvoie l’utilisateur courant (JWT requis)

Security Notes
- Access token court (ex. 30 min) pour réduire l’impact d’une fuite
- Refresh token en cookie httpOnly, SameSite=Lax, Secure en prod
- Rotation à chaque refresh; révoque l’ancien
- Expiration absolue à 30 jours: la session n’est jamais prolongée au-delà de 30 jours

Frontend
- Stocker l’access token de manière volatile (mémoire)
- Ajouter un intercepteur HTTP: sur 401, appeler /auth/refresh puis rejouer la requête
- Pas de “Remember me”: tout le monde est gardé connecté 30 jours par défaut

Email vérification (local auth)
- À l’inscription (register), un email de vérification est envoyé à l’utilisateur avec un lien contenant token + email (exp. 24h par défaut)
- Le frontend redirige l’utilisateur vers /api/v1/auth/verify-email en POST avec { token, email }
- Si succès: email_verified_at est renseigné pour l’utilisateur

Migration
- Les routes et emails de magic link ont été supprimés
- Les anciennes tables “magic_links” ne sont plus utilisées (script LocalStack mis à jour)

Tests
- À mettre à jour: auth unit/integration tests pour les flux register/login/refresh/logout

