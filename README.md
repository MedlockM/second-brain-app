# Media Summarizer

Plateforme "second cerveau" : enregistrer n'importe quel média en un share, l'organiser dans des dossiers et tags, générer à la demande des artefacts IA (résumé, notes, flashcards).

## Documentation

| Document | Statut | Rôle |
|----------|--------|------|
| `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` | Authoritative | Spec produit V1 complète |
| `docs/CANONICAL_MEDIA_API_CONTRACT.md` | Frozen | Contrats API (5 endpoints canoniques) |
| `docs/CANONICAL_MEDIA_API_OPENAPI.yaml` | Frozen | OpenAPI spec |
| `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` | Current | Architecture hexagonale d'ingestion |
| `docs/MEDIA_KEY_MIGRATION.md` | Current | Modèle d'identité runtime (media_key) |
| `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md` | Proposed | Design WhatsApp text/audio (task-61) |
| `docs/URL_SAFETY_POLICY.md` | Current | Validation et sécurité des URLs |
| `docs/ERROR_HANDLING_BEST_PRACTICES.md` | Current | Stratégie gestion d'erreurs API→UI |
| `docs/LOGGING_SYSTEM.md` | Current | Spec logging structuré JSON |
| `docs/AUTHENTICATION_SETUP.md` | Current | Flows auth (OAuth + local) |
| `docs/DEVBOX_SETUP.md` | Current | Reconstruire un poste de dev complet (nouvelle machine) |
| `docs/API_LAMBDA_RUNTIME.md` | Current | Runtime Lambda API dédié, warm-up, release et seuil provisioned concurrency |
| `docs/DEEPGRAM_INCIDENT_RUNBOOK.md` | Current | Runbook incidents transcription |
| `docs/ADR/` | Accepted | Décisions d'architecture (4 ADRs) |
| `AGENTS.md` | Current | Instructions pour agents LLM |
| `backlog/tasks/` | Current | Toutes les tâches V1 et post-V1 |

## Quickstart

```bash
# Créer ou recréer un environnement backend propre avec Python 3.10
uv venv --clear --python 3.10 .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# Copier et configurer l'environnement
cp .env.example .env
# Fill in AWS credentials for the dev environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
```

Poste entièrement neuf (profils AWS, mobile, Terraform, credentials à récupérer
depuis Secrets Manager) : `docs/DEVBOX_SETUP.md`.

Utiliser les binaires du venv directement : cela reste reproductible même si
le shell courant n'a pas activé `.venv` et évite de prendre un outil global par
erreur.

```bash
.venv/bin/ruff check media_summarizer tests
.venv/bin/mypy media_summarizer
```

Pas de suite de tests unitaires : le projet n'ajoute pas de tests automatisés
sans demande explicite (cf. `AGENTS.md`). Seule la suite E2E `tests/e2e/` existe,
skippée par défaut car elle tape l'API AWS dev réelle — la lancer avec
`.venv/bin/python -m pytest -m e2e` (runbook : `tests/e2e/README.md`).

Si `.venv/bin/python` pointe vers une ancienne installation Python (par exemple
un chemin Snap/VS Code versionné qui n'existe plus), relancer les deux commandes
de création ci-dessus. `uv venv --clear` reconstruit le venv et son interpréteur
sans créer de variante locale `.venv-<tâche>`.

## Services (dev)

- **API** : http://localhost:8000
- **Docs API** : http://localhost:8000/docs

## Stack

- **Backend** : Python, FastAPI, AWS (DynamoDB, SQS, S3, Lambda)
- **Transcription** : Deepgram Nova-3
- **LLM** : configurable (à benchmarker)
- **Paiements** : RevenueCat (mobile) + server-side entitlements
- **Mobile** : React Native + Expo (repo séparé via Stitch, sera intégré ici)
- **Dev workflow** : AWS dev environment (eu-west-3)

## Licence

Tous droits réservés.
