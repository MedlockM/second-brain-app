---
id: task-336
title: >-
  Delete the Restore Purchases button — the user account already restores the
  subscription
status: To Do
assignee: []
created_date: '2026-09-02 12:21'
labels:
  - mobile
  - paywall
  - revenuecat
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

The paywall carries a **Restore Purchases** button (`mobile/app/paywall.tsx:583-594`) that has no use case in this app, and it is being deleted rather than kept for a store requirement that does not exist.

**The subscription follows the app account, not the store account.** `identifyUser()` calls `Purchases.logIn(user.id)` (`mobile/src/services/purchaseService.ts:53`, from `mobile/src/contexts/PurchasesContext.tsx:102`), and the access the UI shows comes from `GET /api/entitlements/status`, which reads the `subscriptions` table (`media_summarizer/api/endpoints/entitlements.py:43`). New device or reinstall, same account, and the subscription is active without the button being involved.

**No orphan purchase can exist.** The paywall only opens from the Account tab and from a quota refusal on the share-confirmation screen (`mobile/app/_layout.tsx:148-157`), so a purchase is always made under an identified App User ID. There is no anonymous receipt to reattach.

**In the one case where the button could matter, it repairs nothing.** If the backend never learned about a purchase, `restorePurchases()` on the App User ID that already owns it emits no RevenueCat webhook — RevenueCat only emits on a state change — so the `refreshEntitlements()` that follows re-reads an unchanged backend.

**And it can lie.** `handleRestore` (`mobile/app/paywall.tsx:221-245`) picks its alert from `customerInfo.entitlements.active` (RevenueCat) while access comes from `entitlementStatus.is_active` (backend, `PurchasesContext.tsx:171`). It can therefore announce "Purchases restored" on a paywall that stays shut.

**The comment that justified it is wrong.** `purchaseService.ts:107` reads "required by Apple App Store guidelines". Guideline 3.1.1 says *"you should make sure you have a restore mechanism for any restorable in-app purchases"* — a "should", and the mechanism it asks for already exists: the account. The hard requirement is 3.1.2(a), *"Subscriptions must work on all of the user's devices"*, and the server satisfies it.

## Scope

A straight deletion, no fallback and no flag — nothing reads this button but the user.

- `mobile/app/paywall.tsx` — the button, `handleRestore`, the `isRestoring` state, the `restorePurchases` import and the styles that serve them only
- `mobile/src/services/purchaseService.ts` — `restorePurchases()` and its false comment
- `mobile/src/i18n/*.ts` — the eight `paywall.restore*` / `paywall.nothingToRestore*` keys across the eleven locale catalogues (`ar`, `de`, `en`, `es`, `fr`, `hi`, `it`, `ja`, `nl`, `pt`, `zh`), i.e. 88 entries
- `mobile/src/constants/theme.ts:22` — the comment cites "Restore Purchases" as an example of the paywall's grey line

Check whether anything compares the catalogues against each other before removing keys; if such a guard exists it must stay green.

`STORE_NAME` and the `Alert` import may still be used by the purchase path — verify before removing either.

**Labels deliberately omit `cleanup`**, even though this is one: the dispatcher's routing table gives `cleanup` priority 2 and `mobile` priority 3, and `task-mobile` is the only agent allowed to touch `mobile/`.

## Owner note

Nothing here needs a device or a build. The one thing that lands outside the code is the App Store submission note, which replaces the button: *"Purchases are tied to the user account. Signing in on any device restores the active subscription; there is no separate restore step."* If a reviewer ever pushes back, re-adding a button costs less than maintaining a dead one — that is not worth pre-empting.

`mobile/.maestro/07_paywall.yaml` is mothballed (task-254) and never constrains this code; ignore it if it references the button.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Restore Purchases button, its handler and the state and styles that only served it no longer exist in mobile/app/paywall.tsx
- [ ] #2 restorePurchases() is gone from mobile/src/services/purchaseService.ts, and grep -rn restorePurchases over mobile/ returns nothing
- [ ] #3 The eight paywall.restore* / paywall.nothingToRestore* keys are removed from all eleven locale catalogues in mobile/src/i18n/, leaving no catalogue with an orphan key and any catalogue-comparison guard still green
- [ ] #4 The comment in mobile/src/constants/theme.ts no longer cites Restore Purchases as an example
- [ ] #5 The App Store submission note stating that the subscription follows the user account is written in mobile/MOBILE_CI_CD.md, where submission is covered
- [ ] #6 npm run typecheck and npm run lint pass in mobile/ with no new error and no new warning
<!-- AC:END -->
