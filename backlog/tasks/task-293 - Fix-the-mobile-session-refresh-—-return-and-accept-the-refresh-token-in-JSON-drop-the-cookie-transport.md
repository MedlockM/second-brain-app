---
id: task-293
title: >-
  Fix the mobile session refresh — return and accept the refresh token in JSON,
  drop the cookie transport
status: To Do
assignee: []
created_date: '2026-08-18 17:24'
labels:
  - bug
  - auth
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problème (constaté le 2026-08-18)

La session mobile meurt **30 minutes** après chaque connexion, quel que soit le mode d'authentification, parce que le refresh n'a jamais pu fonctionner sur mobile. Preuve directe contre l'API dev :

```
POST /api/auth/refresh  {"refresh_token":"…"}  →  401 {"detail":"Missing refresh token"}
```

Deux ruptures indépendantes, une par mode d'auth :

1. **Google / Apple.** `/api/auth/refresh` (`media_summarizer/api/endpoints/auth.py:162`) ne lit le refresh token que dans le cookie `refresh_token`. Le mobile l'envoie dans le corps de la requête (`mobile/src/services/authService.ts:131`), qui est ignoré. Le refresh token est pourtant correctement reçu en JSON depuis `/api/auth/google/native` et stocké dans le keychain.
2. **Email / mot de passe.** `/api/auth/login` et `/api/auth/register` ne renvoient pas de `refresh_token` dans leur corps (`TokenVerificationResponse`, `media_summarizer/core/models/auth.py:155`) : il n'est posé qu'en cookie. Le keychain reste donc vide, et `AuthService.refresh()` échoue avant même l'appel réseau (`authService.ts:117`) puis purge la session.

Dans les deux cas, l'utilisateur voit « Your session has expired. Please sign in again. » 30 minutes après s'être connecté.

## Pourquoi le cookie disparaît au lieu d'être conservé en secours

Le transport par cookie httpOnly est un héritage du front web, qui n'existe plus dans le repo (`front/` a disparu). Il ne reste qu'un client mobile, structurellement incapable de s'en servir. Conformément à la règle « Nothing is deployed yet » : pas de double transport, pas de fallback, le cookie part dans la même passe.

## Périmètre

- `/api/auth/login` et `/api/auth/register` renvoient le refresh token dans leur corps JSON, sur le contrat déjà utilisé par `/api/auth/google/native` (`NativeAuthResponse`).
- `/api/auth/refresh` lit le refresh token dans le corps de la requête.
- Suppression du transport cookie : `_set_refresh_cookie`, `_clear_refresh_cookie`, `_refresh_cookie_clear_headers` et les constantes `COOKIE_*` de `auth.py` et `auth_social.py`, plus `get_current_user_flexible` / `RequireAuthFlexible` (zéro appelant dans le repo). Les variables `COOKIE_*` quittent `.env.example` et `docs/AUTHENTICATION_SETUP.md` décrit le transport JSON.
- `media_summarizer/core/security.py` : module mort qui double `utils/auth_utils.py`, avec un `create_refresh_token` JWT jamais appelé et un second secret dérivé (`JWT_SECRET_KEY + "-refresh"`). Seul `hash_password` sert encore, à `scripts/create_test_user.py` : rebrancher ce script sur `utils/auth_utils.py` et supprimer le module.
- Côté mobile, déclarer `refresh_token` sur `TokenVerificationResponse` (`mobile/src/types/auth.ts`) pour retirer le cast inline de `persistTokens`. Aucun autre changement mobile n'est nécessaire : `authService.ts` envoie déjà le token dans le corps et stocke `response.refresh_token` dès qu'il est présent.

## Hors périmètre

Les flux OAuth **web** `/api/auth/google/login|callback` et `/api/auth/apple/login|callback` posent aussi ce cookie et redirigent vers un `FRONTEND_URL` qui ne mène plus nulle part. Ils cessent de poser un cookie (il n'a plus aucun client capable de le lire) mais **ne sont pas supprimés ici** : l'URL de retour Apple est enregistrée dans le portail Apple Developer et `docs/V1_LAUNCH_PLAN.md` Phase 10 la vérifie encore. Leur suppression complète mérite une décision de l'owner à part entière.

## Notes à l'owner

- Vérification E2E manuelle après merge (ne peut pas être une AC) : se connecter en email/mot de passe, puis en Google et en Apple ; laisser expirer l'access token (30 min, ou raccourcir via `JWT_ACCESS_TOKEN_EXPIRE_SECONDS` sur dev) ; revenir dans l'app → aucune redirection vers le login, l'inbox répond.
- Après déploiement : `POST /api/auth/refresh` avec un refresh token valide dans le corps doit répondre 200 avec un nouveau couple de tokens, et le sondage `{"refresh_token":"probe"}` doit répondre 401 pour token invalide et non plus « Missing refresh token ».
- Cette tâche est le préalable dur : sans elle, l'allongement de la durée de session et la résilience réseau n'ont aucun effet observable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /api/auth/login et /api/auth/register renvoient un refresh_token dans leur corps de réponse JSON, déclaré dans leur modèle de réponse
- [ ] #2 /api/auth/refresh lit le refresh token dans le corps de la requête et n'accède plus aux cookies
- [ ] #3 Plus aucune référence au cookie de refresh dans le code applicatif : un grep de set_cookie, COOKIE_NAME_REFRESH, COOKIE_SECURE, COOKIE_SAMESITE et COOKIE_DOMAIN sur media_summarizer/ ne retourne rien
- [ ] #4 get_current_user_flexible et RequireAuthFlexible sont supprimés et aucun appelant ne subsiste dans le repo
- [ ] #5 media_summarizer/core/security.py est supprimé et scripts/create_test_user.py obtient son hachage de mot de passe depuis utils/auth_utils.py
- [ ] #6 Les variables COOKIE_* ont disparu de .env.example et docs/AUTHENTICATION_SETUP.md décrit le transport JSON du refresh token au lieu du cookie httpOnly
- [ ] #7 mobile/src/types/auth.ts déclare refresh_token sur TokenVerificationResponse et persistTokens n'a plus de cast inline
- [ ] #8 ruff check et mypy sont clean sur media_summarizer/, npx tsc --noEmit et npm run lint sont clean dans mobile/
<!-- AC:END -->
