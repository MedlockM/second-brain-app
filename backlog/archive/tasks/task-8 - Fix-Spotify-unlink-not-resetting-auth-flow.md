---
id: task-8
title: Fix Spotify unlink not resetting auth flow
status: To Do
assignee:
  - codex
created_date: '2026-01-24 13:14'
updated_date: '2026-01-24 14:10'
labels: []
dependencies: []
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure that after a user unlinks Spotify in Account Settings, returning to the dashboard and clicking the Spotify button initiates a fresh Spotify login/consent flow rather than reusing the previous linked session.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After unlinking Spotify in Account Settings, the dashboard Spotify button redirects to the Spotify login/consent page on next use
- [ ] #2 Previously stored Spotify access/refresh tokens are cleared or invalidated server-side when unlinking
- [ ] #3 The UI reflects the unlinked state after unlink and does not treat the account as connected
- [ ] #4 Any cached auth state is refreshed so a page refresh is not required to trigger re-link
- [ ] #5 Regression coverage added for unlink → relink flow (manual steps documented or automated test)
<!-- AC:END -->
