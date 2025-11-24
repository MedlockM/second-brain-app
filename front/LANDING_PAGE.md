# Landing Page Documentation

## Vue d'ensemble

Une page d'accueil complète a été ajoutée au frontend pour accueillir les utilisateurs non authentifiés ou ceux dont le token de 30 jours a expiré.

## Structure des fichiers

### Nouveaux fichiers créés

1. **`/src/components/ui/features.tsx`**
   - Composant réutilisable de type "features showcase"
   - Affiche des fonctionnalités avec rotation automatique
   - Support du dark mode
   - Animations avec Framer Motion

2. **`/src/components/LandingPage.tsx`**
   - Page d'accueil principale
   - Section hero avec CTA
   - Intégration du composant Features
   - Footer avec CTA secondaire

### Fichiers modifiés

1. **`/src/App.tsx`**
   - Ajout de la logique d'affichage de la landing page
   - Gestion de l'état `showAuthForm` pour naviguer entre landing et auth
   - Bouton "Back to home" depuis le formulaire d'authentification

2. **`/src/index.css`**
   - Ajout des animations CSS personnalisées (blob animation)
   - Classe `.no-scrollbar` pour masquer les scrollbars
   - Keyframes pour les effets de mouvement

3. **`/tailwind.config.js`**
   - Activation du dark mode (`darkMode: "class"`)
   - Ajout de couleurs personnalisées

## Dépendances ajoutées

```json
{
  "framer-motion": "^11.x.x"
}
```

Installation effectuée via :
```bash
npm install framer-motion
```

## Fonctionnalités

### 1. Hero Section
- Titre accrocheur avec gradient
- Sous-titre explicatif
- 2 boutons CTA : "Get Started Free" et "Sign In"
- Badge avec icône
- Trust badges avec icônes
- Éléments décoratifs animés (blobs)

### 2. Features Section
- 3 fonctionnalités principales :
  - Écoute des podcasts favoris
  - Résumés AI
  - Rapidité et efficacité
- Rotation automatique toutes les 10 secondes
- Barre de progression animée
- Cliquable pour changer manuellement de feature
- Images depuis Unsplash
- Responsive (mobile, tablet, desktop)

### 3. Footer CTA
- Section d'appel à l'action finale
- Design avec gradient
- Bouton CTA supplémentaire

### 4. Footer
- Copyright et informations de base

## Flux utilisateur

```
Utilisateur arrive sur l'app
    ↓
Est-il authentifié ?
    ├─ NON → Affiche LandingPage
    │         ↓
    │    Clique sur "Get Started" ou "Sign In"
    │         ↓
    │    Affiche AuthForm (avec bouton retour)
    │         ↓
    │    Après auth → Dashboard
    │
    └─ OUI → Affiche Dashboard directement
```

## Gestion des tokens expirés

Le système gère automatiquement les tokens expirés :

1. Au chargement de l'app, `AuthService.getValidToken()` est appelé
2. Si le token est expiré (> 30 jours), il est supprimé
3. L'utilisateur est redirigé vers la landing page
4. Il doit se ré-authentifier

## Responsive Design

La landing page est entièrement responsive :

- **Mobile (< 768px)** : Layout vertical, features en carousel horizontal
- **Tablet (768px - 1024px)** : Layout adaptatif
- **Desktop (> 1024px)** : Layout 2 colonnes pour la section features

## Dark Mode

Le composant Features supporte le dark mode via les classes Tailwind :
- `dark:bg-black/80`
- `dark:text-white`
- `dark:border-none`

Pour activer le dark mode, ajouter la classe `dark` sur l'élément `<html>`.

## Images utilisées

Les images proviennent d'Unsplash (stock images) :

1. **Listen to Podcasts** : Photo de casque/podcast
   - `https://images.unsplash.com/photo-1590602847861-f357a9332bbc`

2. **AI-Powered Summaries** : Concept AI/technologie
   - `https://images.unsplash.com/photo-1677442136019-21780ecad995`

3. **Quick & Efficient** : Concept de rapidité/productivité
   - `https://images.unsplash.com/photo-1589903308904-1010c2294adc`

## Personnalisation

### Modifier les couleurs

Dans `LandingPage.tsx`, les couleurs peuvent être changées via les props du composant Features :

```tsx
<Features
  primaryColor="blue-600"  // Couleur principale
  progressGradientLight="bg-gradient-to-r from-blue-500 to-purple-500"
  progressGradientDark="bg-gradient-to-r from-blue-400 to-purple-400"
  features={features}
/>
```

### Modifier les features

Éditer le tableau `features` dans `LandingPage.tsx` :

```tsx
const features = [
  {
    id: 1,
    icon: MonIcone,  // Icône de lucide-react
    title: "Titre",
    description: "Description",
    image: "URL de l'image",
  },
  // ...
];
```

### Modifier les textes du Hero

Tous les textes sont directement éditables dans le JSX de `LandingPage.tsx`.

## Tests

Pour tester la landing page en développement :

1. Supprimer le token du localStorage :
   ```javascript
   localStorage.removeItem('auth_token');
   localStorage.removeItem('token_timestamp');
   ```

2. Recharger la page

3. La landing page devrait s'afficher

## Build et déploiement

Le build a été testé et fonctionne correctement :

```bash
npm run build
```

Aucune erreur TypeScript :

```bash
npm run typecheck
```

## Améliorations futures possibles

1. **Analytics** : Ajouter le tracking des clics sur les CTA
2. **A/B Testing** : Tester différentes variantes du hero
3. **Testimonials** : Ajouter une section de témoignages
4. **Pricing** : Ajouter une section de tarification
5. **FAQ** : Ajouter une section FAQ
6. **Video Demo** : Intégrer une vidéo de démonstration
7. **Newsletter** : Formulaire d'inscription à la newsletter
8. **Social Proof** : Compteurs d'utilisateurs, d'épisodes résumés, etc.

## Notes techniques

- Le composant Features utilise `useRef` et `useEffect` pour gérer la rotation automatique
- Les animations sont gérées par Framer Motion pour de meilleures performances
- Le scroll horizontal sur mobile utilise `scroll-smooth` pour une UX fluide
- Les blobs animés utilisent des keyframes CSS pures pour optimiser les performances