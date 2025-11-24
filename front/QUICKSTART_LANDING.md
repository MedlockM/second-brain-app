# Quick Start Guide - Landing Page

## 🚀 Démarrage rapide

### 1. Installation des dépendances

Si ce n'est pas déjà fait, installez les dépendances :

```bash
cd front
npm install
```

### 2. Lancer le serveur de développement

```bash
npm run dev
```

L'application sera accessible sur `http://localhost:5173` (ou un autre port si 5173 est occupé).

### 3. Tester la landing page

Pour voir la landing page, vous devez être **non authentifié** :

#### Option A : Mode incognito
- Ouvrez l'app en mode navigation privée/incognito

#### Option B : Supprimer le token
Dans la console du navigateur (F12), exécutez :
```javascript
localStorage.removeItem('auth_token');
localStorage.removeItem('token_timestamp');
location.reload();
```

## 📁 Structure des nouveaux fichiers

```
front/src/
├── components/
│   ├── ui/
│   │   └── features.tsx          # Composant Features réutilisable
│   └── LandingPage.tsx            # Page d'accueil principale
├── App.tsx                        # Modifié pour intégrer la landing
└── index.css                      # Animations CSS ajoutées
```

## 🎨 Personnalisation rapide

### Changer les textes du Hero

Éditez `front/src/components/LandingPage.tsx` :

```tsx
<h1 className="...">
  Transform Your
  <span className="...">
    Podcast Experience  {/* ← Changez ce texte */}
  </span>
</h1>
```

### Changer les features

Modifiez le tableau `features` dans `LandingPage.tsx` :

```tsx
const features = [
  {
    id: 1,
    icon: Headphones,              // Icône de lucide-react
    title: "Votre titre",          // ← Modifiez
    description: "Votre desc",     // ← Modifiez
    image: "URL_IMAGE",            // ← Modifiez (Unsplash)
  },
  // ...
];
```

### Changer les couleurs

Dans `LandingPage.tsx`, modifiez les props du composant Features :

```tsx
<Features
  primaryColor="blue-600"          // ← Changez la couleur
  progressGradientLight="bg-gradient-to-r from-blue-500 to-purple-500"
  progressGradientDark="bg-gradient-to-r from-blue-400 to-purple-400"
  features={features}
/>
```

Couleurs disponibles : `blue-600`, `purple-600`, `red-600`, `green-600`, etc.

## 🔄 Flux utilisateur

```
Non authentifié → Landing Page
                      ↓
            Clic "Get Started"
                      ↓
              Formulaire Auth
                      ↓
            Authentification
                      ↓
                 Dashboard
```

## 📱 Responsive

La landing page est automatiquement responsive :
- **Mobile** : Features en carousel horizontal
- **Tablet** : Layout adaptatif
- **Desktop** : Layout 2 colonnes

## 🌙 Dark Mode

Le composant supporte le dark mode. Pour l'activer, ajoutez la classe `dark` sur `<html>` :

```javascript
document.documentElement.classList.add('dark');
```

Pour le désactiver :

```javascript
document.documentElement.classList.remove('dark');
```

## 🖼️ Images

Les images utilisent Unsplash. Format d'URL :

```
https://images.unsplash.com/photo-PHOTO_ID?w=800&h=600&fit=crop
```

**Exemples de photos Unsplash pertinentes :**
- Podcasts/Audio : `photo-1590602847861-f357a9332bbc`
- AI/Tech : `photo-1677442136019-21780ecad995`
- Productivité : `photo-1589903308904-1010c2294adc`
- Workspace : `photo-1542744173-8e7e53415bb0`
- Mobile app : `photo-1512941937669-90a1b58e7e9c`

## ✅ Vérifier que tout fonctionne

### Build de production
```bash
npm run build
```

### Vérification TypeScript
```bash
npm run typecheck
```

### Linter
```bash
npm run lint
```

## 🐛 Dépannage

### La landing page ne s'affiche pas
- Vérifiez que vous n'êtes pas authentifié (pas de token dans localStorage)
- Rechargez la page (F5)

### Erreur "framer-motion not found"
```bash
npm install framer-motion
```

### Les animations ne fonctionnent pas
- Vérifiez que `index.css` contient les keyframes
- Vérifiez la config Tailwind

### Les images ne s'affichent pas
- Vérifiez votre connexion internet (images Unsplash)
- Remplacez par d'autres URLs Unsplash si nécessaire

## 📚 Ressources

- **Framer Motion** : https://www.framer.com/motion/
- **Lucide Icons** : https://lucide.dev/
- **Tailwind CSS** : https://tailwindcss.com/docs
- **Unsplash** : https://unsplash.com/

## 🎯 Prochaines étapes

1. ✅ Landing page créée
2. ⏭️ Personnaliser les textes pour votre marque
3. ⏭️ Ajouter vos propres images
4. ⏭️ Configurer les analytics
5. ⏭️ Ajouter d'autres sections (testimonials, FAQ, etc.)

---

**Besoin d'aide ?** Consultez `LANDING_PAGE.md` pour la documentation complète.