---
id: task-102
title: >-
  Remove email notification worker and SMTP/EMAIL config (replaced by mobile
  polling)
status: Done
assignee: []
created_date: '2026-05-20 10:07'
labels:
  - cleanup
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Le worker e-mail (`media_summarizer/workers/notification/email_worker.py`) envoie aujourd'hui des notifs de complétion/échec aux users via SES, mais en V1 toutes les notifs utilisateur passent par l'app mobile (polling/écran détail). Le provider e-mail ne sert plus à rien.

À supprimer :

1. `media_summarizer/workers/notification/email_worker.py` (~400 lignes) et le dossier `notification/` au complet.
2. Dans `media_summarizer/workers/summarization/summarization_worker.py` : la constante `NOTIFICATION_QUEUE`, la fonction `send_notification()`, et son appel dans `process_summarization_message` (ligne ~403).
3. Dans `media_summarizer/workers/events/media_completed_worker.py` : la constante `NOTIFICATION_QUEUE`, les fonctions `_notify_watcher_completion` et `_notify_watcher_insufficient_minutes`, et leurs appels. Garder le reste du fan-out (mark_watcher_emailed → renommer en mark_watcher_processed, finalize_usage minutes, status update).
4. Dans `media_summarizer/workers/base_worker.py` : la fonction `send_error_notification` (lignes 226-261, déjà no-op) et son appel ligne 159.
5. `media_summarizer/utils/ses.py` (vérifier qu'il n'a plus de caller hors du worker email).
6. `EMAIL_FROM` dans `media_summarizer/core/config.py`.
7. `.env.example` section 13 (EMAIL) + ligne `NOTIFICATION_QUEUE=...` de la section 4.
8. `infrastructure/terraform/terraform.tfvars.example` : retirer `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` du `secret_payload`.
9. `infrastructure/terraform/localstack/main.tf` : supprimer la queue `email-notification-queue` si présente.
10. `infrastructure/terraform/scaling.tf` ou équivalent : supprimer la définition d'ECS task / Lambda du worker email si elle existe.
11. `docs/V1_LAUNCH_PLAN.md` : retirer la ligne « Provider email transactionnel » de la table section 2, le bloc SMTP/EMAIL_FROM de la section 3.2, et la checkbox provider e-mail de la section 5.

Précautions :
- La queue `push-notification-queue` (utilisée par `digest/scheduler.py`) reste en place — elle ne sera pas active en V1 mais sera réutilisée post-V1 pour les vraies push notifications. Ne pas la supprimer.
- Ne pas casser l'appel à `mark_watcher_emailed` dans `media_completed_worker.py` : il sert à dédupliquer le fan-out (un watcher déjà notifié ne doit pas être retraité). Le renommer en `mark_watcher_processed` (et propager dans `media_summarizer/utils/media_watchers.py` + DynamoDB attribute si stocké) ou garder le nom mais documenter qu'il s'agit maintenant juste d'un flag de traitement.
- Vérifier que `mobile/` ne fait aucun appel SMTP / e-mail (il ne devrait pas).
<!-- SECTION:DESCRIPTION:END -->
