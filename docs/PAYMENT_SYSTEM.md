# Système de Paiement Stripe - Documentation

## Vue d'ensemble

Le système de paiement du Media Summarizer utilise Stripe pour gérer les achats de crédits. Cette documentation couvre l'architecture, l'utilisation et la configuration du système de paiement.

## Architecture

### Composants principaux

1. **StripeService** (`media_summarizer/core/services/stripe_service.py`)
   - Service central pour toutes les opérations Stripe
   - Gestion des clients, payment intents, et webhooks
   - Configuration des packages de crédits

2. **Endpoints de paiement** (`media_summarizer/api/endpoints/payments.py`)
   - API REST pour les opérations de paiement
   - Authentification requise pour tous les endpoints
   - Gestion des erreurs et validation des données

3. **Modèles de paiement** (`media_summarizer/api/models/payment.py`)
   - Modèles Pydantic pour la validation des données
   - Types de requêtes et réponses standardisés

## Packages de crédits

### Configuration actuelle

| Package | Crédits | Prix (€) | Prix (centimes) | ID |
|---------|---------|----------|-----------------|-----|
| Pack Starter | 50 | 9,99 € | 999 | `small` |
| Pack Standard | 150 | 24,99 € | 2499 | `medium` |
| Pack Premium | 500 | 79,99 € | 7999 | `large` |
| Pack Entreprise | 1000 | 149,99 € | 14999 | `enterprise` |

### Modification des packages

Pour modifier les packages, éditez la propriété `credit_packages` dans `StripeService.__init__()`:

```python
self.credit_packages = {
    "small": {"credits": 50, "price_cents": 999, "name": "Pack Starter"},
    # Ajoutez ou modifiez les packages ici
}
```

## API Endpoints

### GET /api/v1/payments/packages

Récupère la liste des packages de crédits disponibles.

**Réponse:**
```json
{
  "packages": [
    {
      "id": "small",
      "name": "Pack Starter",
      "credits": 50,
      "price_cents": 999,
      "price_euro": 9.99,
      "savings_percent": null
    }
  ],
  "currency": "eur"
}
```

### POST /api/v1/payments/intent

Crée un payment intent Stripe pour l'achat de crédits.

**Authentification:** Requise

**Corps de la requête:**
```json
{
  "credits": 50,
  "currency": "eur",
  "metadata": {
    "custom_field": "value"
  }
}
```

**Réponse:**
```json
{
  "payment_intent_id": "pi_xxx",
  "client_secret": "pi_xxx_secret_xxx",
  "amount": 999,
  "currency": "eur",
  "credits": 50,
  "package": {
    "id": "small",
    "name": "Pack Starter",
    "credits": 50,
    "price_cents": 999
  }
}
```

### POST /api/v1/payments/confirm

Confirme un paiement et ajoute les crédits au compte utilisateur.

**Authentification:** Requise

**Corps de la requête:**
```json
{
  "payment_intent_id": "pi_xxx"
}
```

**Réponse:**
```json
{
  "payment_intent_id": "pi_xxx",
  "status": "succeeded",
  "credits_added": 50,
  "transaction_id": "tx_xxx",
  "message": "Payment successful! 50 credits added to your account."
}
```

### POST /api/v1/payments/webhook

Endpoint pour recevoir les webhooks Stripe.

**Headers requis:**
- `stripe-signature`: Signature Stripe pour la vérification

**Traite les événements:**
- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `charge.dispute.created`

### GET /api/v1/payments/history

Récupère l'historique des paiements de l'utilisateur.

**Authentification:** Requise

**Paramètres de requête:**
- `limit` (optionnel): Nombre maximum de paiements à retourner (défaut: 50)

**Réponse:**
```json
{
  "payments": [
    {
      "payment_intent_id": "pi_xxx",
      "amount": 999,
      "credits": 50,
      "status": "succeeded",
      "created_at": "2023-12-01T10:00:00Z",
      "package_name": "Pack Starter"
    }
  ],
  "total_count": 1,
  "total_spent_cents": 999,
  "total_credits_purchased": 50
}
```

### GET /api/v1/payments/customer

Récupère les informations client Stripe de l'utilisateur.

**Authentification:** Requise

**Réponse:**
```json
{
  "customer_id": "cus_xxx",
  "email": "user@example.com",
  "payment_methods": [
    {
      "id": "pm_xxx",
      "type": "card",
      "card": {
        "brand": "visa",
        "last4": "4242",
        "exp_month": 12,
        "exp_year": 2025
      }
    }
  ],
  "created_at": "2023-12-01T10:00:00Z"
}
```

### POST /api/v1/payments/refund

Crée un remboursement pour un paiement.

**Authentification:** Requise

**Corps de la requête:**
```json
{
  "payment_intent_id": "pi_xxx",
  "amount": 500,
  "reason": "requested_by_customer"
}
```

**Raisons valides:**
- `duplicate`
- `fraudulent`
- `requested_by_customer`
- `expired_uncaptured_charge`
- `product_unsatisfactory`
- `product_not_received`
- `unrecognized`
- `credit_not_processed`

## Configuration

### Variables d'environnement

#### Obligatoires

```bash
# Clé API Stripe (utilise STRIPE_TEST_API_KEY en développement)
STRIPE_API_KEY=sk_live_xxx
STRIPE_TEST_API_KEY=sk_test_xxx

# Secret webhook Stripe
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

#### Configuration docker-compose.dev.yml

```yaml
environment:
  - STRIPE_API_KEY=${STRIPE_TEST_API_KEY}
  - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
```

### Configuration Stripe Dashboard

1. **Créer les webhooks:**
   - URL: `https://your-domain.com/api/v1/payments/webhook`
   - Événements: `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.dispute.created`

2. **Configurer les modes de paiement:**
   - Activer les cartes bancaires
   - Configurer les devises supportées (EUR, USD)

## Workflow de paiement

### 1. Côté Frontend

```javascript
// 1. Créer un payment intent
const response = await fetch('/api/v1/payments/intent', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({
    credits: 50,
    currency: 'eur'
  })
});

const { client_secret, payment_intent_id } = await response.json();

// 2. Confirmer le paiement avec Stripe.js
const { error } = await stripe.confirmCardPayment(client_secret, {
  payment_method: {
    card: cardElement,
    billing_details: {
      name: 'Customer Name'
    }
  }
});

// 3. Confirmer le paiement côté serveur
if (!error) {
  await fetch('/api/v1/payments/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token
    },
    body: JSON.stringify({
      payment_intent_id: payment_intent_id
    })
  });
}
```

### 2. Côté Backend

1. **Création du payment intent:**
   - Validation des données d'entrée
   - Recherche/création du client Stripe
   - Création du payment intent avec métadonnées

2. **Confirmation du paiement:**
   - Vérification du statut du payment intent
   - Validation de l'appartenance à l'utilisateur
   - Ajout des crédits au compte
   - Création de la transaction

3. **Traitement des webhooks:**
   - Vérification de la signature
   - Traitement des événements de paiement
   - Mise à jour des données utilisateur

## Sécurité

### Validation des paiements

- **Vérification de l'utilisateur:** Chaque paiement est lié à l'utilisateur authentifié
- **Signature des webhooks:** Validation de l'authenticité des événements Stripe
- **Idempotence:** Les webhooks sont traités de manière idempotente

### Gestion des erreurs

```python
try:
    # Opération Stripe
    result = stripe.PaymentIntent.create(...)
except stripe.error.CardError as e:
    # Erreur de carte (fonds insuffisants, carte expirée, etc.)
    pass
except stripe.error.InvalidRequestError as e:
    # Paramètres invalides
    pass
except stripe.error.AuthenticationError as e:
    # Erreur d'authentification Stripe
    pass
except stripe.error.StripeError as e:
    # Erreur générale Stripe
    pass
```

## Tests

### Tests unitaires

```bash
# Tests du service Stripe
pytest media_summarizer/tests/unit/core/services/test_stripe_service.py

# Tests des endpoints de paiement
pytest media_summarizer/tests/unit/api/endpoints/test_payments.py
```

### Tests d'intégration

```bash
# Tests du workflow de paiement complet
pytest media_summarizer/tests/integration/workflows/test_payment_workflow.py -m "requires_stripe"

# Tests de gestion des crédits avec Stripe
pytest media_summarizer/tests/integration/workflows/test_credit_management_workflow.py
```

### Configuration pour les tests

```bash
# Variables d'environnement pour les tests
export STRIPE_TEST_API_KEY=sk_test_xxx
export STRIPE_WEBHOOK_SECRET=whsec_test_xxx
```

## Surveillance et logs

### Logs importants

- Création de payment intents
- Confirmations de paiement
- Traitement des webhooks
- Erreurs de paiement
- Remboursements

### Métriques à surveiller

- Taux de réussite des paiements
- Montant moyen des transactions
- Fréquence des remboursements
- Temps de traitement des paiements

## Dépannage

### Problèmes courants

1. **Payment intent non trouvé:**
   - Vérifier la clé API Stripe
   - Contrôler l'ID du payment intent

2. **Webhook signature invalide:**
   - Vérifier la variable `STRIPE_WEBHOOK_SECRET`
   - Contrôler la configuration du webhook dans Stripe

3. **Crédits non ajoutés après paiement:**
   - Vérifier les logs de traitement des webhooks
   - Contrôler l'état du payment intent dans Stripe

### Commandes de diagnostic

```bash
# Vérifier la configuration Stripe
curl -H "Authorization: Bearer $STRIPE_TEST_API_KEY" \
  https://api.stripe.com/v1/payment_intents/pi_xxx

# Tester un webhook
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "stripe-signature: test" \
  -d '{"type":"payment_intent.succeeded"}'
```

## Migration depuis l'ancien système

L'ancien endpoint `/api/v1/credits/purchase` est déprécié. Pour migrer:

1. **Frontend:** Remplacer les appels directs par le workflow payment intent
2. **Backend:** Les anciens achats Stripe sont rejetés avec un message d'erreur explicite
3. **Tests:** Mettre à jour pour utiliser les nouveaux endpoints

## Ressources supplémentaires

- [Documentation Stripe API](https://stripe.com/docs/api)
- [Guide des webhooks Stripe](https://stripe.com/docs/webhooks)
- [Stripe Testing](https://stripe.com/docs/testing)
- [Stripe Security](https://stripe.com/docs/security)