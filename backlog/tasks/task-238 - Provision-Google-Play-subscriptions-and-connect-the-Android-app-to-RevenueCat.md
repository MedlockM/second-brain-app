---
id: task-238
title: Provision Google Play subscriptions and connect the Android app to RevenueCat
status: To Do
assignee: []
created_date: '2026-08-09 21:05'
labels:
  - phase-6
  - mobile
  - release
  - android
  - revenuecat
  - iap
dependencies:
  - task-162
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the production-like Android billing configuration that is intentionally absent today. The Android application must exist in Google Play Console and RevenueCat, expose the three validated V1 monthly tiers through the current offering, and use a real Google Play public SDK key instead of the Test Store key or the current placeholder. This work involves owner-controlled Google Play Console credentials and billing setup; an agent may automate verifiable RevenueCat/API portions but must not handle or expose private service-account material.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Google Play application for package com.secondbrainlabs.core exists and is eligible for Internal Testing
- [ ] #2 A Google Play app is connected in the RevenueCat project and its Google service credentials validate successfully
- [ ] #3 The Text-Only, Mix, and Audio-Heavy monthly subscriptions exist in Google Play with the validated V1 prices and active base plans
- [ ] #4 All three Google Play products are imported into RevenueCat, attached to entitlement pro, and mapped to packages text_only, mix, and audio_heavy in the current offering
- [ ] #5 The real RevenueCat Google public SDK key is configured securely for Android development, preview, CI, and production profiles, while the Test Store key remains restricted to tests
- [ ] #6 An Internal Testing build fetches all three packages through Google Play without configuration errors
- [ ] #7 A Google Play license tester completes a sandbox purchase and restore, and RevenueCat Customer Info reports entitlement pro as active
<!-- AC:END -->
