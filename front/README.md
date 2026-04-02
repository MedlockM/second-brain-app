# Media Summarizer - Frontend

Application React + TypeScript pour l'interface utilisateur du service de résumé automatique de podcasts.

## 🚀 Démarrage rapide

### Prérequis

- Node.js 18+ ou npm/pnpm/yarn
- Backend API en cours d'exécution (voir section Configuration Backend)

### Installation

```bash
npm install
```

### Configuration

1. Copier le fichier d'exemple de configuration :
```bash
cp .env.example .env.development
```

2. Ajuster les variables d'environnement si nécessaire :
```env
VITE_API_URL=http://localhost:8000
VITE_ENV=development
```

### Lancement en développement

```bash
npm run dev
```

L'application sera accessible sur `http://localhost:5173` (port par défaut de Vite).

## 🔧 Configuration Backend

### Démarrer l'API backend

Depuis la racine du projet :

```bash
# Démarrer l'API avec Docker
docker compose -f docker-compose.dev.yml --profile api up

# Ou démarrer tous les services
docker compose -f docker-compose.dev.yml --profile full up
```

L'API sera accessible sur `http://localhost:8000`.

### Configuration CORS

Le backend est configuré pour accepter les requêtes depuis :
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (alternative port)
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`

## 📁 Structure du projet

```
front/
├── src/
│   ├── components/      # Composants React
│   │   ├── AuthForm.tsx
│   │   ├── Dashboard.tsx
│   │   ├── PodcastCard.tsx
│   │   └── PodcastSearch.tsx
│   ├── services/        # Services API
│   │   ├── authService.ts
│   │   └── podcastService.ts
│   ├── types/           # Définitions TypeScript
│   ├── App.tsx          # Composant principal
│   ├── main.tsx         # Point d'entrée
│   └── index.css        # Styles globaux
├── .env.development     # Variables d'environnement (dev)
├── .env.production      # Variables d'environnement (prod)
├── .env.example         # Exemple de configuration
├── vite.config.ts       # Configuration Vite
└── package.json
```

## 🔐 Fonctionnalités

### Authentification
- Inscription / Connexion
- Gestion de session avec tokens JWT
- Déconnexion

### Recherche de Podcasts
- Recherche dans le catalogue
- Affichage des résultats avec pagination

## 🛠️ Scripts disponibles

```bash
# Développement
npm run dev

# Build de production
npm run build

# Prévisualiser le build
npm run preview

# Linting
npm run lint

# Type checking
npm run typecheck
```

## 🔗 Endpoints API utilisés

### Authentification
- `POST /api/v1/auth/register` - Inscription
- `POST /api/v1/auth/login` - Connexion
- `GET /api/v1/auth/me` - Récupérer l'utilisateur courant
- `POST /api/v1/auth/logout` - Déconnexion

### Podcasts
- `GET /api/v1/podcasts/search` - Rechercher des podcasts

## 🐛 Résolution de problèmes

### L'API n'est pas accessible

1. Vérifier que le conteneur Docker de l'API est en cours d'exécution :
```bash
docker ps | grep api
```

2. Vérifier que `VITE_API_URL` pointe vers la bonne URL :
```bash
cat .env.development
```

3. Vérifier les logs de l'API :
```bash
docker compose -f docker-compose.dev.yml logs api
```

### Erreurs CORS

Si vous rencontrez des erreurs CORS, vérifiez que :
1. Le backend inclut votre origin dans `CORS_ORIGINS`
2. L'URL du frontend correspond à celle configurée
3. Les cookies sont autorisés (`allow_credentials: true`)

## 📝 Variables d'environnement

| Variable | Description | Valeur par défaut | Obligatoire |
|----------|-------------|-------------------|-------------|
| `VITE_API_URL` | URL de l'API backend | `http://localhost:8000` | Oui |
| `VITE_ENV` | Environnement d'exécution | `development` | Non |

## 🚢 Déploiement

### Build de production

```bash
npm run build
```

Les fichiers optimisés seront générés dans le dossier `dist/`.

### Variables d'environnement en production

Assurez-vous de définir `VITE_API_URL` avec l'URL de votre API en production :

```env
VITE_API_URL=https://api.votredomaine.com
VITE_ENV=production
```

## 🧪 Tests

```bash
# À venir
npm test
```

## 📚 Technologies utilisées

- **React 18** - Framework UI
- **TypeScript** - Typage statique
- **Vite** - Build tool et dev server
- **Tailwind CSS** - Framework CSS
- **Lucide React** - Icônes
- **Fetch API** - Requêtes HTTP

## 📄 License

Propriétaire - Tous droits réservés
