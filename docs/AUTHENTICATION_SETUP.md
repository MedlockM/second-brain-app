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
  - POST /api/auth/login → access_token 60 min (JWT) + refresh_token glissant 1 an en JSON
  - POST /api/auth/refresh {"refresh_token": "..."} → rotation du refresh (expiration reposée à now + 1 an) + nouvel access token. Un token consommé depuis moins de 60 s rejoue le couple déjà émis au lieu de répondre 401 (fenêtre de grâce, task-294)
  - POST /api/auth/logout {"refresh_token": "..."} → révoque la seule lignée de l’appareil qui appelle ; les autres appareils du compte gardent leur session
  - GET  /api/auth/me → retourne l’utilisateur courant
- Exigences d’accès API
  - La plupart des routes sensibles nécessitent un access token (Authorization: Bearer <JWT>)
  - Exemple strict: POST /api/podcast-search/submit-episode → require_verified_email

Transport des tokens (aucun cookie de session)
- Refresh token
  - Transporté dans le **corps JSON** : champ `refresh_token` des réponses de register/login/refresh, champ `refresh_token` du corps de la requête /refresh
  - Valeur opaque stockée en base (table auth_tokens), durée **glissante** de REFRESH_TOKEN_EXPIRE_DAYS (365 par défaut) **sans plafond absolu** : chaque /refresh repose expires_at à now + 1 an. Rotation à chaque /refresh : l’ancien est marqué used_at + is_active=false et ne sert plus qu’à rejouer son successeur pendant 60 s
  - Chaque token porte un `lineage_id` généré côté serveur au login et recopié à chaque rotation : c’est l’identité de la session d’un appareil, jamais fournie par le client, et c’est ce que /logout révoque
  - La table a un TTL (`expire_at` = expires_at + 7 jours) : une ligne périmée finit par disparaître, et la marge garantit qu’un balayage TTL ne peut pas tuer une session encore rafraîchissable
  - Le client mobile le garde dans expo-secure-store (Keychain / Keystore). C’est le seul client, et il ne peut pas lire un cookie httpOnly : le transport par cookie a donc été supprimé (task-293), sans repli
- Access token (header Authorization: Bearer)
  - Durée configurable (JWT_ACCESS_TOKEN_EXPIRE_MINUTES, 60 par défaut ; JWT_ACCESS_TOKEN_EXPIRE_SECONDS pour un dev flow). Sans effet sur la révocation : get_current_user relit l’utilisateur en DynamoDB à chaque requête
  - Généré à /register, /login, /refresh et sur les deux endpoints natifs
- Le seul cookie encore posé par l’API est `oauth_state_<provider>` : garde CSRF du flux web, host-only, Secure, httpOnly, SameSite=lax, 10 minutes, lu par le callback du même hôte

CORS & Redirections
- CORS_ORIGINS doit contenir le(s) domaine(s) front autorisés
- FRONTEND_URL utilisé pour construire les URLs de redirection après succès/erreur d’OAuth web

Sécurité & Bonnes Pratiques
- Sessions
  - Ne jamais logguer un refresh token : c’est un porteur de session d’un an
  - Un refresh token consommé est mort passé la fenêtre de grâce de 60 s, donc un rejeu tardif répond 401 « Expired or used refresh token ». Un token révoqué par /logout n’est jamais rejouable
  - La révocation de toutes les lignées d’un compte n’existe qu’au sein de la suppression de compte, qui supprime les lignes plutôt que de les désactiver
- OAuth
  - Valider id_token (aud/iss/sub/email_verified) côté serveur
  - Lier les comptes par email vérifié
- Logs
  - Éviter de logguer des secrets ou des tokens bruts

Variables d’Environnement (extrait)
- JWT & sessions
  - JWT_SECRET_KEY
  - JWT_ALGORITHM=HS256
  - JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
  - REFRESH_TOKEN_EXPIRE_DAYS=365 (fenêtre glissante, sans plafond absolu)
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

Sign-in Google mobile — un chemin par plateforme (task-325)
- iOS : flux navigateur `expo-auth-session` (`src/hooks/useGoogleSignIn.ts`). Le
  `redirect_uri` est le scheme réservé du client OAuth **iOS**
  (`com.googleusercontent.apps.<guid>:/oauthredirect`), et le code est échangé
  contre l’id_token auprès de ce même client : l’`aud` de l’id_token est donc le
  client iOS (`GOOGLE_NATIVE_AUDIENCE_IOS` côté API)
- Android : **Credential Manager**, via le module Expo local
  `mobile/modules/google-credential-manager`
  (`GetSignInWithGoogleOption` → `GoogleIdTokenCredential`, appelé par
  `src/hooks/useGoogleSignIn.android.ts`). Le `serverClientId` passé au module est
  le client OAuth **Web** (`EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB`, c’est-à-dire la même
  valeur que `GOOGLE_CLIENT_ID` côté API), comme la documentation Google l’exige :
  l’`aud` de l’id_token rendu est donc le client Web, déjà accepté par
  `/api/auth/google/native` — aucune variable d’environnement API à ajouter
  - Il n’y a **pas** de `redirect_uri` sur Android, et il ne peut pas y en avoir :
    Google refuse un custom URI scheme pour un client OAuth Android (`Erreur 400 :
    invalid_request`, « Custom URI scheme is not enabled for your Android client »),
    sans réglage pour le réactiver. C’est ce qui a tué le flux navigateur sur
    Android et motivé le module natif
  - Aucun ID de client Android n’entre dans l’app. Mais un client OAuth **Android**
    doit exister côté Google : Credential Manager vérifie l’appelant sur son nom de
    package (`com.secondbrainlabs.core`) **et l’empreinte SHA-1 du certificat qui
    signe le binaire installé**
  - Pour tout binaire distribué par Google Play (piste interne comprise), ce
    certificat n’est pas le keystore d’upload EAS : Play re-signe l’APK servi. Le
    **SHA-1 de Play App Signing doit donc être déclaré sur un client OAuth
    Android**, en plus de celui du keystore EAS (deux clients Android, même nom de
    package). Sans ça, la feuille de sélection de compte échoue sur l’app installée
    depuis Play alors qu’elle fonctionne sur un build local
    - Où le lire : Play Console → *Test et publication* → *Intégrité de
      l’application* → onglet *Signature de l’application* → *Certificat de clé de
      signature d’application* (SHA-1)
    - Où le déclarer : Google Cloud Console → *API et services* → *Identifiants* →
      *ID clients OAuth 2.0* → *Créer des identifiants* → *ID client OAuth* →
      type *Android*

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
