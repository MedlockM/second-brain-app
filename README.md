# Media Summarizer

Plateforme "second cerveau" : enregistrer n'importe quel média en un share, l'organiser dans des dossiers et tags, générer à la demande des artefacts IA (résumé, notes, flashcards).

## Documentation

| Document | Statut | Rôle |
|----------|--------|------|
| `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` | Authoritative | Spec produit V1 complète |
| `docs/CANONICAL_MEDIA_API_CONTRACT.md` | Frozen | Contrats API (5 endpoints canoniques) |
| `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` | Frozen | OpenAPI spec |
| `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` | Current | Architecture hexagonale d'ingestion |
| `docs/MEDIA_KEY_SUBMISSION_GUARD_CONTRACT.md` | Current | Contrat de déduplication par media_key |
| `docs/MEDIA_KEY_MIGRATION.md` | Current | Modèle d'identité runtime (media_key) |
| `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md` | Proposed | Design WhatsApp text/audio (task-61) |
| `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` | Current | Planification locale de dispatch sous-agents à partir d'un snapshot backlog |
| `docs/URL_SAFETY_POLICY.md` | Current | Validation et sécurité des URLs |
| `docs/ERROR_HANDLING_BEST_PRACTICES.md` | Current | Stratégie gestion d'erreurs API→UI |
| `docs/LOGGING_SYSTEM.md` | Current | Spec logging structuré JSON |
| `docs/AUTHENTICATION_SETUP.md` | Current | Flows auth (OAuth + local) |
| `docs/HORIZONTAL_SCALING.md` | Current | Scaling Fargate éphémère |
| `docs/DEEPGRAM_INCIDENT_RUNBOOK.md` | Current | Runbook incidents transcription |
| `docs/ADR/` | Accepted | Décisions d'architecture (4 ADRs) |
| `AGENTS.md` | Current | Instructions pour agents LLM |
| `backlog/tasks/` | Current | Toutes les tâches V1 et post-V1 |

## Quickstart

```bash
# Installer les dépendances
source .venv/bin/activate
uv pip install -e ".[dev]"

# Copier et configurer l'environnement
cp .env.example .env

# Démarrer tous les services (API + Workers + LocalStack)
docker-compose -f docker-compose.dev.yml --profile full up -d

# Ou via Makefile
make dev-full
```

## Services (dev)

- **API** : http://localhost:8000
- **Docs API** : http://localhost:8000/docs
- **LocalStack** : http://localhost:4566

## Tests

```bash
make test-unit          # Tests unitaires
make test-integration   # Tests d'intégration
make test-all           # Tous les tests
```

## Stack

- **Backend** : Python, FastAPI, DynamoDB, SQS, S3
- **Transcription** : Deepgram Nova-3
- **LLM** : configurable (à benchmarker)
- **Paiements** : RevenueCat (mobile) + server-side entitlements
- **Mobile** : React Native + Expo (repo séparé via Stitch, sera intégré ici)
- **Dev local** : Docker + LocalStack

## Licence

Tous droits réservés.
