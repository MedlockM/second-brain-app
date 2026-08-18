# Guide d’Authentification — Media Summarizer

Objectif
- Décrire les flux d’authentification supportés par l’API (OAuth Google/Apple + fallback email/mot de passe)
- Documenter la configuration (variables d’environnement, transport des tokens, CORS) et les bonnes pratiques de sécurité
- Fournir des exemples d’enchaînement côté client et des tests rapides (curl)

Composants & Endpoints
- Auth sociale native (le seul chemin qui ouvre une session sociale)
  - POST /api/auth/google/native {"id_token": "..."} → vérifie l’id_token du SDK Google, relie/crée l’utilisateur, renvoie access_token + refresh_token en JSON
  - POST /api/auth/apple/native {"identity_token": "...", "user": {...}} → idem via la JWKS Apple
- Auth sociale web (flux navigateur, conservé pour les redirect URIs enregistrées chez Google/Apple)
  - GET /api/auth/google/login → redirige vers Google avec un state lié au navigateur par un cookie oauth_state_google
  - GET /api/auth/google/callback?code=...&state=... → échange code→tokens, vérifie id_token, relie/crée l’utilisateur, redirige FRONTEND_URL. **N’émet aucun token de session** : il n’y a plus de client web pour en recevoir
  - GET /api/auth/apple/login et GET /api/auth/apple/callback → même contrat (client_secret ES256 généré à la volée)
- Local (email/mot de passe)
  - POST /api/auth/register → crée un utilisateur local auto-vérifié et ouvre directement la session (201 + access_token + refresh_token)
  - POST /api/auth/login → access_token court (JWT) + refresh_token 30j en JSON
  - POST /api/auth/refresh {"refresh_token": "..."} → rotation du refresh (expiration absolue conservée) + nouvel access token
  - POST /api/auth/logout → révoque tous les refresh tokens de l’utilisateur en base
  - GET  /api/auth/me → retourne l’utilisateur courant
- Exigences d’accès API
  - La plupart des routes sensibles nécessitent un access token (Authorization: Bearer <JWT>)
  - Exemple strict: POST /api/podcast-search/submit-episode → require_verified_email

Transport des tokens (aucun cookie de session)
- Refresh token
  - Transporté dans le **corps JSON** : champ `refresh_token` des réponses de register/login/refresh, champ `refresh_token` du corps de la requête /refresh
  - Valeur opaque stockée en base (table auth_tokens), durée 30 jours **absolus**, rotation à chaque /refresh : l’ancien est marqué used_at + is_active=false et ne peut plus servir
  - Le client mobile le garde dans expo-secure-store (Keychain / Keystore). C’est le seul client, et il ne peut pas lire un cookie httpOnly : le transport par cookie a donc été supprimé (task-293), sans repli
- Access token (header Authorization: Bearer)
  - Durée courte configurable (JWT_ACCESS_TOKEN_EXPIRE_MINUTES, ou JWT_ACCESS_TOKEN_EXPIRE_SECONDS pour un dev flow)
  - Généré à /register, /login, /refresh et sur les deux endpoints natifs
- Le seul cookie encore posé par l’API est `oauth_state_<provider>` : garde CSRF du flux web, host-only, Secure, httpOnly, SameSite=lax, 10 minutes, lu par le callback du même hôte

CORS & Redirections
- CORS_ORIGINS doit contenir le(s) domaine(s) front autorisés
- FRONTEND_URL utilisé pour construire les URLs de redirection après succès/erreur d’OAuth web

Sécurité & Bonnes Pratiques
- Sessions
  - Ne jamais logguer un refresh token : c’est un porteur de session de 30 jours
  - Un refresh token consommé est mort (rotation), donc un rejeu répond 401 « Expired or used refresh token »
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
  - (aucune variable COOKIE_* : le refresh token ne passe plus par un cookie)
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
- Login Google / Apple (mobile)
  - 1) Le SDK natif rend un id_token (Google) ou un identity_token (Apple)
  - 2) POST /api/auth/google/native ou /api/auth/apple/native avec ce token
  - 3) Stocker access_token + refresh_token du corps de la réponse dans le secure store
  - 4) À l’expiration de l’access token, POST /api/auth/refresh avec le refresh token stocké

- Login local (curl)
  ```bash path=null start=null
  curl -X POST http://localhost:8000/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email": "user@example.com", "password": "your-pass"}'
  # → {"access_token":"...","refresh_token":"...","token_type":"bearer","expires_in":1800,"user":{...}}
  ```

- Refresh (curl)
  ```bash path=null start=null
  curl -X POST http://localhost:8000/api/auth/refresh \
    -H 'Content-Type: application/json' \
    -d '{"refresh_token": "<value>"}'
  # → même contrat, avec un refresh_token neuf : l’ancien est consommé
  ```

- Appel d’une route protégée
  ```bash path=null start=null
  curl -X GET http://localhost:8000/api/auth/me \
    -H 'Authorization: Bearer <access_token>'
  ```

Gestion des Erreurs Courantes
- 401 Invalid authentication token → vérifier le header Authorization
- 401 Invalid refresh token / Expired or used refresh token → le refresh stocké est inconnu, expiré ou déjà rotaté : il faut se reconnecter
- 422 sur /api/auth/refresh → le corps ne contient pas de champ refresh_token
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
