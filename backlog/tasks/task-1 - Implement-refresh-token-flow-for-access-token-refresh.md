---
id: task-1
title: Implement refresh token flow for access token refresh
status: Done
assignee:
  - codex
created_date: '2026-01-06 19:08'
updated_date: '2026-01-24 14:10'
labels: []
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implementer l'utilisation d'un refresh token pour rafraichir l'access token.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Audit rapide de l’existant
- Vérifier le flux /api/v1/auth/login, /refresh, stockage AuthToken, rotation et expiration absolue (30 jours).
- Vérifier l’usage du refresh cookie dans media_summarizer/api/dependencies/auth.py et front/src/services/authService.ts.

2) Contrat d’erreur “session expirée”
- Standardiser les réponses 401 liées au refresh expiré/invalidé (code SESSION_EXPIRED + message court).
- S’assurer que le refresh cookie est supprimé côté serveur si le refresh est expiré/invalide (évite boucles).

3) Frontend: handling propre
- Détecter l’échec de refresh dans AuthService.refresh() et déclencher logout/redirect vers /login.
- Afficher un message friendly en anglais (mapping existant dans front/src/lib/getFriendlyErrorMessage.ts).

4) Documentation
- Noter le comportement “session expirée → reconnect” dans la doc d’auth (si besoin).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented refresh-expiry handling: backend now clears refresh cookie on 401 from /auth/refresh via Set-Cookie headers, and error handler preserves exception headers. Frontend stores SESSION_EXPIRED flag on refresh failure and AuthForm shows the friendly message on next login view.

Set dev token lifetimes via new env overrides: JWT_ACCESS_TOKEN_EXPIRE_SECONDS and REFRESH_TOKEN_EXPIRE_MINUTES. Auth endpoints now use seconds/minutes helper so short-lived tokens work for UI testing.

Added init guard in AppContent to prevent double auth refresh in React StrictMode; avoids brief /login redirect flash on page refresh with expired access token.

MyQuizzesAndSummaries: keep polling quiet but always surface session-expired errors; Retry now forces error display so users are prompted to sign in instead of seeing an empty state.

Removed 5s polling in MyQuizzesAndSummaries; page now loads once on mount and refreshes only via user action.

Added background access-token refresh timer in AppContent based on token_expiry; refreshes a few seconds before expiry without user action and clears auth on failure.

MyQuizzesAndSummaries now loads data only on first mount and on explicit Refresh click (no reload on token refresh).
<!-- SECTION:NOTES:END -->
