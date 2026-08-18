# Guide d’Authentification — Media Summarizer

Objectif
- Décrire les flux d’authentification supportés par l’API (OAuth Google/Apple + fallback email/mot de passe)
- Documenter la configuration (variables d’environnement, cookies, CORS) et les bonnes pratiques de sécurité
- Fournir des exemples d’enchaînement côté client (front) et des tests rapides (curl)

Composants & Endpoints
- Auth sociale (OIDC)
  - Google
    - GET /api/auth/google/login → redirige vers Google avec state
    - GET /api/auth/google/callback?code=...&state=... → échange code→tokens, vérifie id_token, relie/crée l’utilisateur, émet un refresh cookie httpOnly 30j, redirige FRONTEND_URL
  - Apple
    - GET /api/auth/apple/login → redirige vers Apple
    - GET /api/auth/apple/callback?code=...&state=... → génère client_secret (ES256), échange code, vérifie id_token, relie/crée l’utilisateur, émet refresh cookie 30j, redirige FRONTEND_URL
- Fallback local (email/mot de passe)
  - POST /api/auth/register → crée un utilisateur local + envoie un email de vérification
  - POST /api/auth/login → émet refresh cookie 30j + access token court (JWT) en réponse JSON
  - POST /api/auth/refresh → rotation du refresh (cookie remplacé, expiration absolue conservée) + access token court
  - POST /api/auth/logout → révoque les refresh tokens + supprime le cookie
  - GET  /api/auth/me → retourne l’utilisateur courant
- Exigences d’accès API
  - La plupart des routes sensibles nécessitent un access token (Authorization: Bearer <JWT>)
  - Exemple strict: POST /api/podcast-search/submit-episode → require_verified_email

Cookies & Sessions
- Refresh cookie (httpOnly)
  - Nom: COOKIE_NAME_REFRESH (par défaut refresh_token)
  - Durée: 30 jours (absolus), rotation à chaque /refresh
  - Attributs en production: Secure=true, SameSite=lax (ou none si cross-site) et domain=COOKIE_DOMAIN
- Access token (header Authorization: Bearer)
  - Durée courte configurable (JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
  - Généré à /login et /refresh

CORS & Redirections
- CORS_ORIGINS doit contenir le(s) domaine(s) front autorisés
- FRONTEND_URL utilisé pour construire les URLs de redirection après succès/erreur d’OAuth

Sécurité & Bonnes Pratiques
- Toujours activer:
  - COOKIE_SECURE=true en production (HTTPS obligatoire)
  - COOKIE_SAMESITE=lax (ou none si besoin cross-site sur HTTPS)
  - COOKIE_DOMAIN configuré au domaine de l’app (ex: app.yourdomain.com)
- OAuth
  - Valider id_token (aud/iss/sub/email_verified) côté serveur
  - Lier les comptes par email vérifié
- Logs
  - Éviter de logguer des secrets ou des tokens bruts

Variables d’Environnement (extrait)
- JWT & sessions
  - JWT_SECRET_KEY
  - JWT_ALGORITHM=HS256
  - JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
  - REFRESH_TOKEN_EXPIRE_DAYS=30
  - COOKIE_NAME_REFRESH=refresh_token
  - COOKIE_SECURE=true (prod)
  - COOKIE_SAMESITE=lax (ou none)
  - COOKIE_DOMAIN=app.yourdomain.com
- CORS / Frontend
  - CORS_ORIGINS=https://app.yourdomain.com
  - FRONTEND_URL=https://app.yourdomain.com
- Google OAuth
  - GOOGLE_CLIENT_ID
  - GOOGLE_CLIENT_SECRET
  - GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/auth/google/callback
- Apple OAuth
  - APPLE_CLIENT_ID
  - APPLE_TEAM_ID
  - APPLE_KEY_ID
  - APPLE_PRIVATE_KEY (PEM; peut être fourni en une ligne avec \n)
  - APPLE_REDIRECT_URI=https://api.yourdomain.com/api/auth/apple/callback

Exemples — Flux côté client
- Login Google (navigateur)
  - 1) Ouvrir /api/auth/google/login → redirection Google
  - 2) Consentement utilisateur → redirection /auth/google/callback → refresh cookie posé → redirection FRONTEND_URL
  - 3) Sur le front, appeler /api/auth/me et afficher l’état connecté

- Login local (curl)
  ```bash path=null start=null
  curl -X POST http://localhost:8000/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email": "user@example.com", "password": "your-pass"}' -i
  # → Set-Cookie: refresh_token=...; HttpOnly; Path=/; Max-Age=... 
  ```

- Refresh (curl)
  ```bash path=null start=null
  curl -X POST http://localhost:8000/api/auth/refresh \
    -H 'Content-Type: application/json' \
    -H 'Cookie: refresh_token=<value>'
  ```

- Appel d’une route protégée
  ```bash path=null start=null
  curl -X GET http://localhost:8000/api/auth/me \
    -H 'Authorization: Bearer <access_token>'
  ```

Gestion des Erreurs Courantes
- 401 Invalid token / Missing refresh token → vérifier header Authorization ou cookie
- 400 OAuth non configuré → vérifier GOOGLE_* ou APPLE_* dans l’environnement

La vérification d’email par lien a été retirée : les comptes sont auto-vérifiés
à l’inscription. Les endpoints stubs `/api/auth/verify-email` et
`/api/auth/resend-verification` ont été supprimés (task-222) — le premier
était non authentifié et mutait le champ `email_verified_at` d’un email
arbitraire.

Références Code
- Auth locale: media_summarizer/api/endpoints/auth.py
- OAuth social: media_summarizer/api/endpoints/auth_social.py
- Dépendances/auth: media_summarizer/api/dependencies/auth.py
- CORS & rate limiting: media_summarizer/api/main.py, media_summarizer/api/rate_limit.py
