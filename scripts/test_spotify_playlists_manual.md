# Tests Manuels - Spotify Playlists Manager

## Prérequis

### Services requis
```bash
# 1. Backend API
cd /home/marc-medlock/Perso/media-summarizer-project-kiro/media-summarizer-project
source .venv/bin/activate
uvicorn media_summarizer.api.main:app --reload --port 8000

# 2. LocalStack (infrastructure)
docker-compose -f docker-compose.dev.yml --profile infrastructure up -d

# 3. Initialiser tables DynamoDB
python scripts/init_db.py init

# 4. Frontend
cd front
npm run dev
```

### Variables d'environnement
Vérifier dans `.env` :
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/v1/auth/spotify/callback
AWS_ENDPOINT_URL=http://localhost:4566
```

## Test 1: Liaison du compte Spotify

### Via Frontend
1. Ouvrir http://localhost:5173 (Vite dev server)
2. Se connecter avec un compte utilisateur
3. Sur le dashboard, cliquer sur l'icône Spotify
4. **Attendu**: Redirection vers Spotify OAuth
5. Autoriser l'application
6. **Attendu**: Retour au frontend avec redirection automatique vers `/dashboard/spotify/playlists`

### Via API (si tests backend seuls)
```bash
# Récupérer un token utilisateur
TOKEN="your_access_token_here"

# Vérifier statut Spotify (non lié)
curl -X GET "http://localhost:8000/api/v1/auth/spotify/status" \
  -H "Authorization: Bearer $TOKEN"
# Attendu: { "linked": false }

# Obtenir l'URL d'authentification
curl -X GET "http://localhost:8000/api/v1/auth/spotify/auth-url" \
  -H "Authorization: Bearer $TOKEN"
# Attendu: { "url": "https://accounts.spotify.com/authorize?...", "state": "..." }

# Ouvrir l'URL dans le navigateur, autoriser, puis vérifier le callback
```

## Test 2: Lister les playlists (owner uniquement)

```bash
TOKEN="your_access_token_after_spotify_link"

curl -X GET "http://localhost:8000/api/v1/spotify/playlists" \
  -H "Authorization: Bearer $TOKEN" \
  | json_pp

# Attendu: 
# [
#   {
#     "id": "abc123",
#     "name": "Ma Playlist",
#     "images": [{"url": "...", "height": 300, "width": 300}],
#     "tracks_total": 42,
#     "owner_name": "Votre nom",
#     "collaborative": false,
#     "public": true,
#     "enabled": false
#   },
#   ...
# ]
```

**Vérifications**:
- Seules les playlists dont vous êtes propriétaire apparaissent
- `enabled` est `false` par défaut (aucun tracking actif)

## Test 3: Activer le tracking d'une playlist

```bash
# Choisir un ID de playlist depuis le test précédent
PLAYLIST_ID="37i9dQZF1DXcBWIGoYBM5M"  # Remplacer par un ID réel

curl -X PUT "http://localhost:8000/api/v1/spotify/playlists/$PLAYLIST_ID/subscription" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}' \
  | json_pp

# Attendu:
# {
#   "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
#   "enabled": true,
#   "last_synced_at": "2025-11-10T17:30:00.123Z"
# }
```

**Vérifications**:
- La réponse contient `enabled: true`
- `last_synced_at` est défini (timestamp ISO)
- Vérifier les logs backend: synchronisation déclenchée automatiquement
- Vérifier la queue `audio-download-queue` dans LocalStack (messages enqueued)

```bash
# Vérifier les messages SQS
aws --endpoint-url=http://localhost:4566 sqs receive-message \
  --queue-url http://localhost:4566/000000000000/audio-download-queue \
  --max-number-of-messages 10
```

## Test 4: Vérifier la persistance du tracking

```bash
# Relister les playlists
curl -X GET "http://localhost:8000/api/v1/spotify/playlists" \
  -H "Authorization: Bearer $TOKEN" \
  | json_pp

# Attendu: la playlist trackée a maintenant "enabled": true
```

## Test 5: Lister les subscriptions

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/subscriptions" \
  -H "Authorization: Bearer $TOKEN" \
  | json_pp

# Attendu:
# [
#   {
#     "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
#     "enabled": true,
#     "last_synced_at": "2025-11-10T17:30:00.123Z"
#   }
# ]
```

## Test 6: Déclencher une sync manuelle

```bash
curl -X POST "http://localhost:8000/api/v1/spotify/playlists/$PLAYLIST_ID/sync" \
  -H "Authorization: Bearer $TOKEN" \
  | json_pp

# Attendu:
# {
#   "status": "success",
#   "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
#   "scanned": 15,
#   "eligible": 8,
#   "submitted": 5,
#   "skipped": {
#     "below_threshold": 2,
#     "missing_data": 1,
#     "not_matched": 2,
#     "already_submitted": 0
#   }
# }
```

**Vérifications**:
- `submitted` > 0 (épisodes enqueued)
- `scanned` = nombre total d'items dans la playlist
- Logs backend montrent les épisodes traités

## Test 7: Désactiver le tracking

```bash
curl -X PUT "http://localhost:8000/api/v1/spotify/playlists/$PLAYLIST_ID/subscription" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  | json_pp

# Attendu:
# {
#   "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
#   "enabled": false,
#   "last_synced_at": "2025-11-10T17:30:00.123Z"
# }
```

**Vérifications**:
- `enabled` passe à `false`
- `last_synced_at` est préservé (historique)
- Relister les playlists: `enabled` est `false`

## Test 8: Frontend (tests visuels)

### Scénario complet
1. **Dashboard initial** (compte non lié):
   - Cliquer sur l'icône Spotify
   - **Attendu**: Redirection OAuth Spotify
   
2. **Après autorisation**:
   - **Attendu**: Retour automatique à `/dashboard/spotify/playlists`
   - Liste des playlists s'affiche (images, noms, compteurs)
   
3. **Activer tracking**:
   - Cliquer sur le toggle d'une playlist
   - **Attendu**: Toggle passe à ON (vert), toast "Synchronisation lancée avec succès !"
   - Attendre quelques secondes
   
4. **Recharger la page**:
   - **Attendu**: Le toggle reste ON (état persisté)
   
5. **Désactiver tracking**:
   - Cliquer sur le toggle (le remettre à OFF)
   - **Attendu**: Toggle passe à OFF (gris), toast "Tracking désactivé"
   - Recharger: toggle reste OFF

### États vides
- Aucune playlist créée sur Spotify:
  - **Attendu**: Message "Aucune playlist trouvée"
  
### Gestion d'erreurs
- Déconnecter le backend
- Cliquer sur un toggle
- **Attendu**: Toast d'erreur "Erreur lors de la mise à jour"

## Test 9: Vérification DB (DynamoDB LocalStack)

```bash
# Lister les follows
aws --endpoint-url=http://localhost:4566 dynamodb scan \
  --table-name spotify_playlist_follows

# Attendu: items avec user_id, playlist_id, enabled, last_synced_at
```

## Checklist de validation

- [ ] Liaison Spotify via frontend fonctionne
- [ ] Redirection automatique vers playlists après liaison
- [ ] Liste des playlists (owner uniquement) s'affiche
- [ ] Toggle ON déclenche sync immédiate
- [ ] Toast de confirmation s'affiche
- [ ] État persisté (toggle reste ON après reload)
- [ ] Toggle OFF désactive le tracking
- [ ] Sync manuelle via API fonctionne
- [ ] Logs backend montrent épisodes enqueued
- [ ] Messages SQS présents dans audio-download-queue
- [ ] Subscriptions listées via API
- [ ] DB contient les follows créés

## Nettoyage (après tests)

```bash
# Supprimer les follows de test
aws --endpoint-url=http://localhost:4566 dynamodb delete-item \
  --table-name spotify_playlist_follows \
  --key '{"user_id": {"S": "your_user_id"}, "playlist_id": {"S": "your_playlist_id"}}'

# Ou réinitialiser tout LocalStack
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml --profile infrastructure up -d
python scripts/init_db.py init
```

## Troubleshooting

### Erreur "spotify_not_linked"
- Vérifier que l'utilisateur a bien des tokens Spotify en DB
- Relancer le flow de liaison OAuth

### Erreur "Failed to list playlists"
- Vérifier `SPOTIFY_CLIENT_ID` et `SPOTIFY_CLIENT_SECRET`
- Vérifier que les tokens ne sont pas expirés (refresh automatique)

### Toggle ne change pas d'état
- Vérifier logs backend pour erreurs
- Vérifier que la table `spotify_playlist_follows` existe dans LocalStack
- Vérifier CORS si erreur réseau

### Aucune playlist affichée
- Vérifier que vous êtes propriétaire de playlists sur Spotify
- Le filtre "owner only" exclut les playlists suivies/collaboratives dont vous n'êtes pas owner
