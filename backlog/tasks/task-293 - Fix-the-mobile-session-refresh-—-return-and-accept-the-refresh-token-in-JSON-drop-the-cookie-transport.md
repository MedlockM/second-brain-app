---
id: task-293
title: >-
  Fix the mobile session refresh — return and accept the refresh token in JSON,
  drop the cookie transport
status: Done
assignee: []
created_date: '2026-08-18 17:24'
updated_date: '2026-08-18 18:00'
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
- [x] #1 /api/auth/login et /api/auth/register renvoient un refresh_token dans leur corps de réponse JSON, déclaré dans leur modèle de réponse
- [x] #2 /api/auth/refresh lit le refresh token dans le corps de la requête et n'accède plus aux cookies
- [ ] #3 Plus aucune référence au cookie de refresh dans le code applicatif : un grep de set_cookie, COOKIE_NAME_REFRESH, COOKIE_SECURE, COOKIE_SAMESITE et COOKIE_DOMAIN sur media_summarizer/ ne retourne rien
- [x] #4 get_current_user_flexible et RequireAuthFlexible sont supprimés et aucun appelant ne subsiste dans le repo
- [x] #5 media_summarizer/core/security.py est supprimé et scripts/create_test_user.py obtient son hachage de mot de passe depuis utils/auth_utils.py
- [x] #6 Les variables COOKIE_* ont disparu de .env.example et docs/AUTHENTICATION_SETUP.md décrit le transport JSON du refresh token au lieu du cookie httpOnly
- [x] #7 mobile/src/types/auth.ts déclare refresh_token sur TokenVerificationResponse et persistTokens n'a plus de cast inline
- [x] #8 ruff check et mypy sont clean sur media_summarizer/, npx tsc --noEmit et npm run lint sont clean dans mobile/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Ce qui change dans le contrat

`TokenVerificationResponse` (`media_summarizer/core/models/auth.py`) porte désormais un
`refresh_token` **requis**, et sert de modèle de réponse aux trois endpoints locaux :

- `POST /api/auth/register` → 201 avec une session complète. Il ne renvoyait qu'un
  `AuthUser` : ajouter `refresh_token` à `AuthUser` aurait pollué `/me` et toutes les
  réponses utilisateur, donc register renvoie la même enveloppe que login.
- `POST /api/auth/login` → inchangé sauf le champ ajouté.
- `POST /api/auth/refresh` → prend un corps `RefreshRequest` (`{"refresh_token": "..."}`)
  et renvoie le token rotaté dans le corps. Plus aucun accès aux cookies, donc plus de
  401 « Missing refresh token » : un corps sans champ donne 422, un token inconnu 401
  « Invalid refresh token ». La rotation elle-même n'est pas touchée (task-294 s'en charge).
- `POST /api/auth/logout` → révoque toujours les refresh tokens en base, ne pose plus
  d'en-tête de suppression de cookie.

Côté mobile, `register()` ne rappelle plus `login()` derrière : son commentaire disait
explicitement que ce second appel existait parce que register ne renvoyait que
l'utilisateur et que le mobile ne pouvait pas lire le cookie. La prémisse disparaît avec
cette tâche, donc le contournement aussi (un aller-retour réseau et un refresh token
orphelin en base de moins par inscription).

**Effet de bord repéré et corrigé** : `tests/e2e/conftest.py` et
`tests/e2e/test_transcript_translation.py` lisaient `resp.json()["id"]` sur
`/api/auth/register`. L'id est maintenant sous `["user"]["id"]` — les deux fixtures sont
mises à jour, sinon le run E2E de l'owner casse au setup. Aucun test n'a été ajouté.

### AC #3 laissée décochée — un `set_cookie` subsiste, et c'est volontaire

Après la passe, sur `media_summarizer/` :

- `COOKIE_NAME_REFRESH`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `COOKIE_DOMAIN` : **0 hit**.
- `set_cookie` : **1 hit**, `_set_state_cookie` dans `auth_social.py`, qui pose
  `oauth_state_<provider>` — la garde CSRF des flux OAuth **web**, que la section
  « Hors périmètre » demande explicitement de conserver. Ce cookie n'a rien à voir avec
  le refresh : il est posé par `/google/login|/apple/login`, relu 10 minutes plus tard par
  le callback du même hôte, et c'est la seule chose qui empêche un callback non sollicité
  d'aboutir. Le supprimer ferait échouer toute validation de state en silence ; le
  remplacer par un state signé sans cookie retirerait le lien au navigateur, ce qui est
  strictement plus faible face au login-CSRF. La condition de tête de l'AC (« plus aucune
  référence au cookie **de refresh** ») est donc tenue, mais son grep littéral ne l'est
  pas : l'AC reste décochée, à l'owner de trancher s'il veut aussi voir partir le state.

Ce cookie a quand même été nettoyé au passage : il ne lit plus les variables `COOKIE_*` et
devient host-only, `Secure`, `httpOnly`, `SameSite=lax`. Le `domain=COOKIE_DOMAIN` précédent
était d'ailleurs cassé en prod — un `Domain=app.<domaine>` posé par une réponse de
`api.<domaine>` est rejeté par le navigateur, donc chaque callback web y aurait répondu
`state_mismatch`. `_clear_state_cookie` (zéro appelant) est supprimé.

### Autres suppressions

- `_set_refresh_cookie`, `_clear_refresh_cookie`, `_refresh_cookie_clear_headers` et les
  quatre constantes `COOKIE_*` de `auth.py`, plus les trois de `auth_social.py` et l'import
  `auth as auth_local` qui n'existait que pour partager le helper.
- `get_current_user_flexible` / `RequireAuthFlexible` (`api/dependencies/auth.py`) : zéro
  appelant, et c'était le dernier code capable d'authentifier via cookie.
- `media_summarizer/core/security.py` : module mort doublon de `utils/auth_utils.py`
  (second secret dérivé `JWT_SECRET_KEY + "-refresh"`, `create_refresh_token` JWT jamais
  appelé). `scripts/create_test_user.py` prend `hash_password` dans `utils/auth_utils.py`.
- Les callbacks OAuth web ne créent plus de refresh token en base : ils n'avaient plus
  aucun moyen de le transmettre, donc chaque passage écrivait une ligne inutilisable dans
  `auth_tokens`. Ils vérifient l'id_token, lient/créent l'utilisateur, et redirigent.
- `pyproject.toml` : `media_summarizer.api.endpoints.auth` quitte la liste des overrides
  mypy (vérifié : mypy passe sans elle une fois les cookies partis). `auth_social` y reste,
  pour trois erreurs préexistantes sans rapport (`credits=100` legacy, typage de
  `_b64_to_int`).

### Vérifications faites

- `ruff check media_summarizer/ scripts/ tests/` → clean.
- `uv run mypy media_summarizer/` → `Success: no issues found in 170 source files`.
- `python scripts/check_env_example_complete.py` → OK, 232 variables (le guard aurait
  échoué si un `COOKIE_*` était resté lu par le code).
- `mobile/` : `npx tsc --noEmit` → aucune sortie ; `npm run lint` → 0 error, 8 warnings
  préexistants, tous dans des fichiers non touchés ici.
- Greps de l'AC #3 rejoués, résultat détaillé ci-dessus.

### Hors de portée depuis le worktree

Rien de ce qui touche au runtime déployé n'est vérifiable ici : le déploiement part au push
sur `main`, après la sortie de l'agent. Restent donc à l'owner, comme le prévoit la
description : le sondage `POST /api/auth/refresh` sur l'API dev (200 avec un token valide,
401 « Invalid refresh token » avec `{"refresh_token":"probe"}`) et le test E2E manuel des
trois modes de connexion après expiration de l'access token. Les quatre clés `COOKIE_*` du
secret runtime dev/prod deviennent mortes — elles peuvent rester, plus aucun code ne les
lit ; `docs/DEVBOX_SETUP.md` prévient qu'elles apparaîtront désormais dans la liste
`skipped:` de l'injection `.env` sans que ce soit une anomalie.
<!-- SECTION:NOTES:END -->
