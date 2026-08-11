---
id: task-245
title: >-
  Surface subscription state in the mobile app (isSubscribed is computed but
  never consumed)
status: To Do
assignee: []
created_date: '2026-08-11 16:24'
labels:
  - mobile
  - billing
  - feature
  - phase-6
dependencies:
  - task-244
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

`mobile/src/contexts/PurchasesContext.tsx` calcule `isSubscribed` et expose `entitlementStatus` (tier, minutes restantes, fin de période) depuis `GET /api/v1/entitlements/status`. Audit du code (2026-08-11) : **aucun écran ne consomme ces valeurs**. Le seul appelant de `usePurchases()` est `paywall.tsx`, et seulement pour `refreshEntitlements`.

L'utilisateur n'a donc aujourd'hui **aucun moyen de voir** son tier, ses minutes restantes ou la date de fin de période, alors que le backend fournit tout.

## À clarifier avec l'owner avant implémentation

Le vrai « gating » (restreindre des fonctionnalités selon le tier) est déjà assuré **côté backend** par `quota_enforcer.py` (task-110, Done), qui est la seule place où il est fiable — un gating purement client serait contournable. La question ouverte est donc :

- Faut-il seulement **afficher** l'état (tier + minutes restantes dans Account, éventuellement un indicateur d'approche de limite) ?
- Ou aussi **désactiver côté client** certaines actions par anticipation (griser l'import audio quand le solde est épuisé), pour éviter un aller-retour réseau soldé par une erreur ?

Trancher ce point avant de coder : la première option est un affichage, la seconde duplique une règle métier côté client et doit rester cosmétique.

## Scope indicatif (à confirmer selon la réponse ci-dessus)

1. Afficher dans l'onglet Account le tier courant, les minutes restantes et la fin de période à partir de `entitlementStatus`.
2. Gérer les états `null` / chargement / erreur réseau sans casser l'écran (l'endpoint peut échouer : `PurchasesContext.tsx` logge déjà l'erreur et laisse `entitlementStatus` à `null`).
3. Optionnel selon décision : indication anticipée quand le solde est proche de zéro, complémentaire au refus backend traité par task-244.

## Hors scope

- Les points d'entrée du paywall (task-244).
- Toute règle d'enforcement côté client qui remplacerait `quota_enforcer.py`.

## Références

- `mobile/src/contexts/PurchasesContext.tsx` (`isSubscribed`, `entitlementStatus`, `refreshEntitlements`)
- `media_summarizer/api/endpoints/entitlements.py`
- `media_summarizer/core/services/quota_enforcer.py`, task-110 (enforcement backend, Done)
- task-244 (points d'entrée paywall + traitement des refus de quota)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The owner has confirmed whether the scope is display-only or also includes client-side pre-emptive disabling, and the task description records the answer
- [ ] #2 The Account tab shows the current tier, remaining minutes, and period end from entitlementStatus
- [ ] #3 A null or failed entitlements response leaves the Account tab usable, with no crash and no misleading 'free tier' claim
- [ ] #4 usePurchases is consumed by at least one screen other than paywall.tsx
<!-- AC:END -->
