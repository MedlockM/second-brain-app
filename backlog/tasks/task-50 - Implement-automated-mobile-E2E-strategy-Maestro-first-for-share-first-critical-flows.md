---
id: task-50
title: >-
  Implement automated mobile E2E strategy (Maestro-first) for share-first
  critical flows
status: To Do
assignee: []
created_date: '2026-02-24 21:17'
updated_date: '2026-05-18 21:16'
labels: []
dependencies:
  - task-93
  - task-94
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the mobile E2E automation baseline using Maestro as the primary framework for React Native + Expo share-first flows, with explicit fallback guidance for targeted Appium usage only if iOS share-extension automation is blocked.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Maestro test flows cover critical share-first paths on Android and iOS (share intake, inbox visibility, media detail progression, artifact trigger action).
- [ ] #2 Automation runs reproducibly in CI on internal mobile build artifacts and reports actionable pass/fail results.
- [ ] #3 A documented fallback path defines when and how to use targeted Appium coverage for iOS share-extension gaps without replacing the primary Maestro strategy.
- [ ] #4 Test artifacts and failure triage guidance are documented for release-readiness decisions.
<!-- AC:END -->
