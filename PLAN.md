# PLAN.md — Migration Auth

Décision validée le 2025-08-27

Objectif
- Abandonner totalement les magic links.
- Mettre en place: OAuth social (Google, Apple) + option email/mot de passe.
- Sessions persistantes 30 jours (expiration absolue), sans "Remember me".

Approche (phases)
- Phase 1 (cette PR):
  - Implémenter auth locale email/mot de passe.
  - Ajouter refresh tokens en cookie httpOnly + Secure (prod) avec durée 30 jours (absolue).
  - Access token court (par défaut 30 minutes) avec renouvellement silencieux via /auth/refresh.
  - Supprimer le router magic link de l’app (ne plus exposer les endpoints) et introduire un nouveau router auth_v2.
  - Mettre à jour la config .env.example (JWT_ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, COOKIE_*).
  - Documentation: ce PLAN sert de référence temporaire; mise à jour des docs détaillées ultérieurement.
- Phase 2 (prochaine PR):
  - Google OAuth (OIDC): endpoints /auth/google/login et /auth/google/callback.
  - Ajout des variables d’environnement Google et de la dépendance (Authlib).
  - (Optionnel) Lien de compte par email vérifié (linking) + règles si conflit.
- Phase 3:
  - Apple OAuth.
  - Mise à jour complète de la documentation et des tests.

Règles clés
- 30 jours absolus pour la session: le refresh token a une date d’expiration fixe; la rotation ne prolonge pas au-delà de cette date.
- Cookies:
  - httpOnly, SameSite=Lax (par défaut), Secure en prod.
  - Nom: refresh_token.
- Sécurité:
  - Rotation des refresh tokens à chaque /auth/refresh (ancien révoqué/marquage used).
  - Possibilité de révoquer les refresh tokens via /auth/logout.
  - Access tokens courts (30 minutes par défaut), uniquement pour les appels API.

Impact
- Les endpoints magic links sont retirés de l’app (breaking change API). Les tests associés seront ajustés dans les phases suivantes.
- Le modèle User évolue (champs optionnels pour password_hash et providers).

Validation
- Une fois Phase 1 mergée: tests unitaires des nouvelles routes (register/login/refresh/logout/me) + sanity manual.

