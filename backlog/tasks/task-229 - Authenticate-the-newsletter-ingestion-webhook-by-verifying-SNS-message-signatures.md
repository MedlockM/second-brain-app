---
id: task-229
title: Authenticate the newsletter ingestion webhook by verifying SNS message signatures
status: To Do
assignee: []
created_date: '2026-08-05 18:45'
labels:
  - security
  - api
  - release
  - bug
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Découvert pendant l'audit AC#7 de `task-222` (audit des routes sans dépendance
d'authentification).

`POST /api/media/newsletter/ingest`
(`media_summarizer/api/endpoints/newsletter_webhook.py`) est une route publique
sans **aucune** authentification ni vérification de signature. Le handler
`newsletter_ingest_webhook` se contente de parser le JSON reçu et de faire
confiance à son contenu.

Deux abus possibles pour un appelant anonyme sur l'API dev publiquement
joignable :

1. **Injection de travail dans le pipeline.** Un `Type: "Notification"` forgé
   avec un `Message` contenant un bloc SES arbitraire est enfilé tel quel dans
   `newsletter-ingestion-queue` via `_extract_email_content`. Les champs
   `s3_bucket`, `s3_key` et `recipient` sont entièrement contrôlés par
   l'appelant, qui peut donc faire lire au worker un objet S3 de son choix et
   attribuer le média ingéré au compte d'un tiers.
2. **SSRF via `SubscriptionConfirmation`.** Un `Type:
   "SubscriptionConfirmation"` avec un `SubscribeURL` arbitraire déclenche un
   `client.get(subscribe_url)` sortant depuis le Lambda, sans validation du
   domaine. La réponse n'est pas renvoyée à l'appelant, mais la requête part.

La classe de faille est la même que celle traitée par `task-222` sur
`/api/v1/users/*` : une route de mutation joignable sans preuve d'identité de
l'appelant. Elle n'a pas été corrigée dans `task-222` car la contre-mesure est
différente en nature (vérification cryptographique de signature SNS côté
infrastructure, pas dépendance `get_current_user`) et mérite sa propre
validation.

## Objectif

Rendre la route inexploitable par un appelant qui n'est pas SNS. La forme exacte
est à l'appréciation de l'implémenteur.

Points d'attention :

- **Vérifier la signature SNS** (`SigningCertURL`, `Signature`,
  `SignatureVersion`, chaîne à signer canonique) avant toute action. Ne faire
  confiance au `SigningCertURL` que s'il pointe vers un domaine AWS légitime,
  sinon la vérification est contournable.
- **Contraindre le topic** : n'accepter que le ou les `TopicArn` attendus,
  fournis par configuration.
- **`SubscriptionConfirmation`** : ne suivre le `SubscribeURL` qu'après
  validation de la signature *et* du domaine, ou retirer l'auto-confirmation si
  la souscription est déjà gérée par Terraform.
- **`s3_bucket`** ne doit pas être pris tel quel depuis le payload : le worker
  ne doit lire que dans le bucket d'ingestion attendu.
- Vérifier si `POST /api/webhooks/revenucat` (secret partagé en clair comparé
  sans `secrets.compare_digest`) mérite un durcissement dans la même passe.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A forged SNS notification without a valid signature is rejected and nothing is enqueued
- [ ] #2 A notification carrying a valid signature but an unexpected topic ARN is rejected
- [ ] #3 The SubscribeURL is only followed when both the signature and the URL host are validated, or the auto-confirmation path is removed
- [ ] #4 The newsletter worker only reads from the expected ingestion bucket and never from a bucket named in the request payload
- [ ] #5 A legitimate SES-originated newsletter email still ingests end to end against AWS dev after the change
- [ ] #6 The RevenueCat webhook shared-secret comparison is either hardened or an explicit decision to leave it is recorded
<!-- AC:END -->
