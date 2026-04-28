---
id: task-82
title: 'TEST-A: Add MAX_FOLDERS_PER_USER constant to core/constants.py'
status: Done
assignee: []
created_date: '2026-04-21 22:35'
updated_date: '2026-04-21 22:41'
labels:
  - feature
  - test-dispatch
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
<!-- SECTION:DESCRIPTION:BEGIN -->
Créer le fichier `media_summarizer/core/constants.py` s'il n'existe pas, puis ajouter la constante `MAX_FOLDERS_PER_USER = 50` avec un commentaire explicatif. Ajouter aussi `DEFAULT_FOLDER_NAME = "Uncategorized"` dans le même fichier.
<!-- SECTION:DESCRIPTION:END -->

<!-- SECTION:NOTES:BEGIN -->
Tâche de test pour valider le dispatch parallèle avec conflits. À supprimer après le test.
<!-- SECTION:NOTES:END -->
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le fichier media_summarizer/core/constants.py existe
- [ ] #2 MAX_FOLDERS_PER_USER = 50 est défini
- [ ] #3 DEFAULT_FOLDER_NAME = 'Uncategorized' est défini
<!-- AC:END -->
