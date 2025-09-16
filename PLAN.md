# PLAN.md — Migration Auth

Décision validée le 2025-08-27

Objectif
- Abandonner totalement les magic links.
- Mettre en place: OAuth social (Google, Apple) + option email/mot de passe.
- Sessions persistantes 30 jours (expiration absolue), sans "Remember me".

Approche (phases)
- Phase 1 (cette PR):
  - Implémenter auth locale email/mot de passe.
  - Ajouter refresh tokens en cookie httpOnly + Secure (prod) avec durée 30 jours (absolue).
  - Access token court (par défaut 30 minutes) avec renouvellement silencieux via /auth/refresh.
  - Supprimer le router magic link de l’app (ne plus exposer les endpoints) et introduire un nouveau router auth_v2.
  - Mettre à jour la config .env.example (JWT_ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, COOKIE_*).
  - Documentation: ce PLAN sert de référence temporaire; mise à jour des docs détaillées ultérieurement.
- Phase 2 (prochaine PR):
  - Google OAuth (OIDC): endpoints /auth/google/login et /auth/google/callback.
  - Ajout des variables d’environnement Google et de la dépendance (Authlib).
  - (Optionnel) Lien de compte par email vérifié (linking) + règles si conflit.
- Phase 3:
  - Apple OAuth.
  - Mise à jour complète de la documentation et des tests.

Règles clés
- 30 jours absolus pour la session: le refresh token a une date d’expiration fixe; la rotation ne prolonge pas au-delà de cette date.
- Cookies:
  - httpOnly, SameSite=Lax (par défaut), Secure en prod.
  - Nom: refresh_token.
- Sécurité:
  - Rotation des refresh tokens à chaque /auth/refresh (ancien révoqué/marquage used).
  - Possibilité de révoquer les refresh tokens via /auth/logout.
  - Access tokens courts (30 minutes par défaut), uniquement pour les appels API.

Impact
- Les endpoints magic links sont retirés de l’app (breaking change API). Les tests associés seront ajustés dans les phases suivantes.
- Le modèle User évolue (champs optionnels pour password_hash et providers).

Validation
- Une fois Phase 1 mergée: tests unitaires des nouvelles routes (register/login/refresh/logout/me) + sanity manual.

---

# PLAN — Migration Monétisation (Minutes)

Décision validée le 2025-09-03

Objectif
- Remplacer totalement le système “crédits” par un modèle “minutes” avec:
  - Abonnements S/M/L créditant un pool de minutes mensuel (débit au réel, arrondi à la minute)
  - Packs minutes one-shot (moins avantageux que les abonnements)
  - Rollover des minutes d’abonnement sur 1 mois
  - Réservations “soft” par podcast suivi (prévision mensuelle)

Résumé tarification
- Abonnements:
  - S: 2,00 € → 240 min
  - M: 5,00 € → 840 min
  - L: 10,00 € → 1 980 min
- Packs (validité 6 mois):
  - 100 min / 1,50 € (0,015 €/min)
  - 300 min / 3,00 € (0,010 €/min)
  - 600 min / 6,00 € (0,010 €/min)
  - 1 200 min / 10,00 € (0,0083 €/min)

Règles d’usage
- Débit au réel: minutes = ceil(durée_secondes / 60)
- Ordre de consommation: rollover → minutes abo du mois en cours → packs (par expiration la plus proche)
- Si pool insuffisant: proposer achat d’un pack ou upgrade d’abonnement (prorata Stripe)

Approche (phases)
- Phase 1 — Modèle de données & tables (DynamoDB):
  - Tables: subscriptions, minute_buckets, minute_usage, follows (TTL sur expirations)
  - CRUD et conditions atomiques pour débit/re-crédit
- Phase 2 — Stripe V2 (abonnements + packs + webhooks):
  - Checkout subscriptions/packs, webhooks `checkout.session.completed` / `invoice.payment_succeeded`
  - Création des buckets minutes, synchro abonnement
- Phase 3 — MinutePoolService + hold/finalize:
  - place_hold(job_id, estimate), finalize(actual), release_hold(reason)
  - Intégration soumission/worker download (calcul durée réelle)
- Phase 4 — Follows & réservations (soft):
  - Forecast mensuel selon règles (4/3/2/<1 mois), recalcul mensuel
- Phase 5 — Rollover 1 mois & consommation prioritaire
- Phase 6 — Migration one-shot crédits → minutes (1 crédit = 1 minute), puis suppression code crédits
- Phase 7 — Durcissement: proration, idempotence, tests, observabilité

Impacts
- Suppression des endpoints /credits/* et /payments/intent|confirm|refund
- Nouveaux endpoints billing: /billing/subscriptions/checkout, /billing/packs/checkout, /billing/me, /billing/history (webhook conservé)
- Ajout core/services/minute_pool_service.py et stripe_service_v2.py
- Mise à jour des workers (finalize_hold après download)

Validation
- Achat pack: bucket minutes créé via webhook
- Souscription S/M/L: bucket de période créé via `invoice.payment_succeeded`
- Soumission épisode: hold placé, finalize sur durée réelle, fallback WAITING_FOR_MINUTES si insuffisant
- Rollover opéré en fin de période, consommé en priorité le mois suivant

Notes (2025-09-04)
- Pas de frontend pour l’instant: on utilise des routes backend publiques comme pages de redirection post-Checkout Stripe:
  - /payment-success?session_id={CHECKOUT_SESSION_ID}
  - /payment-cancel
- Variables d’environnement en dev:
  - STRIPE_SUCCESS_URL=http://localhost:8000/payment-success?session_id={CHECKOUT_SESSION_ID}
  - STRIPE_CANCEL_URL=http://localhost:8000/payment-cancel
  - FRONTEND_URL=http://localhost:8000 (fallback)

---

# PLAN — Approvisionnement Infra par Terraform (S3)

Décision validée le 2025-09-04

Décisions
- L’application n’auto-crée plus les buckets S3 (suppression des fallbacks côté code).
- En dev comme en prod, l’approvisionnement est géré par Terraform (LocalStack en dev via docker-compose, AWS en prod).
- Ajout d’un preflight check au démarrage de l’API: si des buckets requis manquent, l’API échoue immédiatement (fail fast) avec un message explicite.

Détails
- Buckets requis (env): AUDIO_BUCKET, TRANSCRIPT_BUCKET, SUMMARY_BUCKET.
|- Variable PRESTART_INFRA_CHECK=1 (par défaut): active la vérification au startup FastAPI.
|- En cas d’erreur: consulter les logs du service Terraform.
|
|Commandes utiles
|- Démarrage full (incluant Terraform):
|  docker-compose -f docker-compose.dev.yml --profile full up -d
|- Logs Terraform:
|  docker-compose -f docker-compose.dev.yml logs terraform
|- Rejouer Terraform seulement:
|  docker-compose -f docker-compose.dev.yml --profile infrastructure up -d terraform
|
|---
|
|# PLAN — Standardisation variables Stripe
|
|Décision validée le 2025-09-04
|
|Décision
|- Standardiser sur une seule variable d’environnement: STRIPE_API_KEY (utiliser une clé sk_test_* en dev, sk_live_* en prod).
|- Remplacer toutes les occurrences de STRIPE_TEST_API_KEY dans le code, les tests, la CI et la doc par STRIPE_API_KEY.
|- docker-compose.dev.yml: s’appuyer sur env_file: .env.dev pour injecter STRIPE_API_KEY (suppression de l’override environment qui pouvait écraser par une valeur vide).
|
|Impacts
|- Les tests d’intégration/unitaires et les workflows CI n’exigent plus STRIPE_TEST_API_KEY.
|- .env.example documente uniquement STRIPE_API_KEY.
|- Les scripts/diagnostics utilisent désormais $STRIPE_API_KEY.
|
|Suivi
||- Secrets CI: prévoir un secret GitHub STRIPE_API_KEY (remplace STRIPE_TEST_API_KEY).
||- En local: .env.dev doit contenir STRIPE_API_KEY=sk_test_...
||
||---
||
||# PLAN — Politique de redirection Stripe (APM)
||
||Décision validée le 2025-09-05
||
||Contexte
||- Certains tests d’intégration Stripe échouaient/étaient ignorés car Stripe exige un return_url lorsque des moyens de paiement à redirection sont activés (ex: iDEAL, Bancontact, Sofort).
||- En prod, ces redirections sont normales et souhaitables; en tests, elles compliquent le run.
||
||Décision
||- Introduire une variable d’environnement STRIPE_REDIRECT_POLICY pour contrôler automatic_payment_methods[allow_redirects].
||  - always (défaut prod): Stripe peut utiliser des moyens de paiement avec redirection (comportement par défaut Stripe si non défini).
||  - never (tests/CI): interdiction des redirections pour éviter d’exiger un return_url et simplifier les tests.
||- Implémentation: StripeService crée le PaymentIntent avec automatic_payment_methods={enabled: true} et ajoute allow_redirects: "never" uniquement si STRIPE_REDIRECT_POLICY=never.
||
||Impacts
||- Prod: aucun changement de comportement par défaut (support maximal des moyens de paiement).
||- Tests/CI: plus de skips liés à l’absence de return_url; exécutions plus stables.
||- Documentation: .env.example documente STRIPE_REDIRECT_POLICY.
||
||Suivi
||- CI: exporter STRIPE_REDIRECT_POLICY=never pour les jobs de tests (à planifier si non présent).
||- Front/Backend: continuer à prévoir des routes de retour (success/cancel) pour Checkout.
||
