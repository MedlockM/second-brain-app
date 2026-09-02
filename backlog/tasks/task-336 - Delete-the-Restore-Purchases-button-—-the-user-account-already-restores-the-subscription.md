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
- [x] #1 The Restore Purchases button, its handler and the state and styles that only served it no longer exist in mobile/app/paywall.tsx
- [x] #2 restorePurchases() is gone from mobile/src/services/purchaseService.ts, and grep -rn restorePurchases over mobile/ returns nothing
- [x] #3 The eight paywall.restore* / paywall.nothingToRestore* keys are removed from all eleven locale catalogues in mobile/src/i18n/, leaving no catalogue with an orphan key and any catalogue-comparison guard still green
- [x] #4 The comment in mobile/src/constants/theme.ts no longer cites Restore Purchases as an example
- [x] #5 The App Store submission note stating that the subscription follows the user account is written in mobile/MOBILE_CI_CD.md, where submission is covered
- [x] #6 npm run typecheck and npm run lint pass in mobile/ with no new error and no new warning
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deleted, in one pass, with no fallback: 193 lines removed against 82 added.

**`mobile/app/paywall.tsx`** — the button, `handleRestore`, `isRestoring`, the
`restorePurchases` import and the `restoreButton` / `restoreText` styles are gone.
`Alert`, `ActivityIndicator`, `TouchTarget` and `STORE_NAME` all stayed: the purchase
path still uses every one of them (`STORE_NAME` for `renewalTerms`, `cancelAnytime`
and `pricesUnavailable`).

One thing the button was doing besides lying: **holding the vertical gap**. It
carried `marginTop: Spacing.lg` plus `paddingVertical: Spacing.md` between the
"included in every plan" card and the legal block, and the legal block itself only
had `Spacing.sm` — so a straight excision left the renewal terms nearly flush
against a shadowed card, and flush against it entirely in the `!canPurchase` state
where the terms do not render at all. The terms and the two links are now wrapped in
a `legalBlock` view that owns `marginTop: Spacing.lg`, which is correct in both
states rather than depending on which sibling precedes it. No new token, no new
value — `Spacing.lg` was already the gap the deleted button contributed.

**`mobile/src/services/purchaseService.ts`** — `restorePurchases()` and the
"required by Apple App Store guidelines" comment are gone. The module docblock now
records *why* there is no wrapper, phrased without the identifier so that AC #2's
`grep -rn restorePurchases` over `mobile/` stays empty.

**The eleven catalogues** — the eight keys were contiguous in every one of them
(`"paywall.restore"` through `"paywall.restoreFailedBody"`, always followed by
`"paywall.purchaseSuccess"`), removed by script with an assertion that exactly 8
`"paywall.*"` entries were dropped per file: 88 entries total.

Worth recording for the next catalogue cleanup: **the guard does not catch orphans.**
`Catalog` in `src/i18n/runtime.ts` is
`Record<TranslationKey, string> & Record<string, string>`, and that index signature —
there so Arabic can declare six plural categories — means a key left in `fr` after
being removed from `en` is *not* a `tsc` error. Only a *missing* key is. So the
removal had to be done in all eleven by hand; typecheck being green proves no key is
missing, not that none is orphaned. `grep -rn "paywall.restore\|nothingToRestore"`
over `mobile/` returning nothing is what proves the second half.

**`mobile/MOBILE_CI_CD.md`** — new subsection under *4. App Store Connect Setup*:
"App Review note: the app has no Restore Purchases button". It carries the exact
sentence to paste into App Store Connect → the version → App Review Information →
Notes, and the 3.1.1-is-a-"should" / 3.1.2(a)-is-the-hard-requirement reasoning a
reviewer question would need.

`mobile/.maestro/07_paywall.yaml` never referenced the button, so nothing to ignore
there after all.

Checks: `npm run typecheck` clean. `npm run lint` reports the same two pre-existing
warnings as before the change and no others — `digest.tsx:36` unused `CARD_WIDTH`
(untouched file) and the `catch (error: any)` in `purchasePackage`, which only moved
line number because of the new docblock.
<!-- SECTION:NOTES:END -->
