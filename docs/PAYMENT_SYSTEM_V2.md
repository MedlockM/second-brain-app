# Système de monétisation — Modèle “minutes”

Objectif
- Remplacer le modèle “crédits” par un modèle “minutes” simple et prévisible.
- Unifier l’UX: abonnements qui créditent automatiquement un pool mensuel + packs ponctuels.
- Débit au réel sur la durée de l’audio, arrondi à la minute.

1) Produits
- Abonnements (S/M/L)
  - S: 2,00 € → 240 min/mois
  - M: 5,00 € → 840 min/mois
  - L: 10,00 € → 1 980 min/mois
  - Règles: 1 LLM, pas de remise cache, rollover des minutes d’abonnement sur 1 mois.
- Packs de minutes (one‑shot)
  - Mini: 100 min / 1,50 € (0,015 €/min) — dépannage
  - Standard: 300 min / 3,00 € (0,010 €/min) — usage ponctuel
  - Plus: 600 min / 6,00 € (0,010 €/min)
  - Max: 1 200 min / 10,00 € (0,0083 €/min) — gros besoin ponctuel
  - Validité recommandée: 6 mois

2) Débit et calcul
- Débit au réel sur la durée de l’audio: minutes_utilisées = ceil(durée_secondes / 60).
- Ordre de consommation (priorités):
  1. Buckets “rollover” (minutes reportées du mois précédent), par expiration la plus proche.
  2. Bucket d’abonnement courant (mois en cours).
  3. Buckets “packs” (par expiration la plus proche).

3) Réservations par podcast suivi (soft)
- Lorsqu’un utilisateur “suit” un podcast, on calcule une prévision mensuelle de minutes.
- Règles de prévision (fixes):
  - ≥ 4 mois d’historique: moyenne des 4 derniers mois
  - = 3 mois: moyenne des 3 derniers mois
  - 1–2 mois: moyenne des 2 derniers mois
  - < 1 mois: somme de toutes les minutes publiées
- Recalcul mensuel et affichage dans l’UI (réservations “soft” non bloquantes en v1).

4) Architecture technique
- Tables DynamoDB (nouvelles):
  - subscriptions: état des abonnements Stripe (tier, status, periods, ids Stripe)
  - minute_buckets: sources de minutes (subscription|pack|rollover|migration) avec minutes_total/remaining et expires_at (TTL)
  - minute_usage: holds et consommations finales par job (held/finalized/released/expired) avec breakdown par buckets
  - follows: podcasts suivis, forecast_minutes, reserved_minutes, pointeur d’historique
  - stripe_events (existant): idempotence webhooks
- Services:
  - StripeService V2: checkout subscriptions/packs; webhooks checkout.session.completed, invoice.payment_succeeded, customer.subscription.*
  - MinutePoolService: place_hold(job_id, estimate), finalize_hold(job_id, actual_minutes), release_hold(job_id)
- Intégration pipeline:
  - submit-episode: place_hold (si durée inconnue: hold conservateur, ex: 60 min)
  - download_worker: calcule durée réelle → finalize_hold (continue seulement si succès)
  - en cas d’échec irréversible: release_hold

5) Webhooks Stripe (principaux)
- checkout.session.completed
  - mode=payment → créer un bucket “pack” (minutes + expiry)
  - mode=subscription → enregistrer l’abonnement; minutes créditées lors de invoice.payment_succeeded
- invoice.payment_succeeded
  - créer un bucket “subscription” pour la période (minutes_per_period selon tier S/M/L) avec period_start/end
- customer.subscription.created/updated/deleted
  - synchro status, cancel_at_period_end, etc.

6) Rollover (1 mois)
- En fin de période abonnement, si minutes_remaining > 0:
  - créer un bucket “rollover” avec expires_at = fin du mois suivant (TTL)
  - priorité de consommation la plus haute le mois suivant

7) API (exposition)
- POST /api/v1/billing/subscriptions/checkout { tier: "S"|"M"|"L" }
- POST /api/v1/billing/packs/checkout { minutes: 100|300|600|1200 }
- POST /api/v1/billing/customer-portal
- GET  /api/v1/billing/me → statut abonnement, récap minutes libres/réservées par source, prochaine échéance
- GET  /api/v1/billing/history → historique (abonnements, packs)
- POST /api/v1/payments/webhook → handler Stripe (signé)
- (Follows) POST/DELETE/GET /api/v1/follows → gestion des podcasts suivis et prévisions

8) Variables d’environnement (extrait)
- STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_ID_SUB_S, STRIPE_PRICE_ID_SUB_M, STRIPE_PRICE_ID_SUB_L
- STRIPE_PRICE_ID_PACK_100, STRIPE_PRICE_ID_PACK_300, STRIPE_PRICE_ID_PACK_600, STRIPE_PRICE_ID_PACK_1200
- STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL
- DEFAULT_HOLD_MINUTES=60
- PACK_EXPIRY_MONTHS=6

9) Transition depuis “crédits”
- Migration one‑shot proposée: 1 crédit = 1 minute → création d’un bucket “migration” par utilisateur (expiration longue ou nulle), puis mise à 0 de l’ancien champ credits.
- Décommissionner: endpoints /credits/* et /payments/intent|confirm|refund remplacés par les routes billing + webhooks.

10) Critères de validation
- Achat d’un pack → bucket minutes créé (webhook) avec expiry.
- Souscription S/M/L → bucket minutes créé sur invoice.payment_succeeded.
- Soumission épisode → hold placé, finalize sur durée réelle; si insuffisant, job en WAITING_FOR_MINUTES + notification.
- Rollover de fin de période → bucket “rollover” créé et consommé en priorité.

