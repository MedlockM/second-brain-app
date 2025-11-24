# UI Components Directory

## 📁 Structure

Ce dossier contient les composants UI réutilisables du projet, suivant la structure recommandée par shadcn/ui.

```
ui/
├── features.tsx      # Composant Features avec rotation automatique
└── README.md         # Ce fichier
```

## 📦 Composants disponibles

### Features

Composant de showcase de fonctionnalités avec rotation automatique et animations.

**Fichier** : `features.tsx`

**Props** :
```typescript
interface FeaturesProps {
  features: {
    id: number;
    icon: React.ElementType;
    title: string;
    description: string;
    image: string;
  }[];
  primaryColor?: string;
  progressGradientLight?: string;
  progressGradientDark?: string;
}
```

**Utilisation** :
```tsx
import { Features } from "@/components/ui/features";
import { Sparkles, Zap, Headphones } from "lucide-react";

const features = [
  {
    id: 1,
    icon: Sparkles,
    title: "Feature Title",
    description: "Feature description",
    image: "https://images.unsplash.com/photo-xxx",
  },
  // ...
];

function MyPage() {
  return (
    <Features
      primaryColor="blue-600"
      progressGradientLight="bg-gradient-to-r from-blue-500 to-purple-500"
      progressGradientDark="bg-gradient-to-r from-blue-400 to-purple-400"
      features={features}
    />
  );
}
```

**Fonctionnalités** :
- ✨ Rotation automatique toutes les 10 secondes
- 🖱️ Navigation manuelle par clic
- 📊 Barre de progression animée (Framer Motion)
- 📱 Design responsive
- 🌙 Support du dark mode
- ♿ Accessible

## 🎨 Conventions

### Import Path Alias

Utilisez l'alias `@/components/ui/...` pour importer les composants :

```tsx
import { Features } from "@/components/ui/features";
```

### Nomenclature

- **Fichiers** : camelCase avec extension `.tsx`
- **Composants** : PascalCase
- **Props** : Interface avec suffixe `Props`

### Structure d'un composant UI

```tsx
// 1. Directives (si nécessaire)
"use client";

// 2. Imports
import { useState } from "react";
import { motion } from "framer-motion";

// 3. Types/Interfaces
interface MyComponentProps {
  // ...
}

// 4. Composant
export function MyComponent({ ...props }: MyComponentProps) {
  // Implementation
  return <div>...</div>;
}
```

## 🚀 Ajouter un nouveau composant

### 1. Créer le fichier

```bash
touch src/components/ui/my-component.tsx
```

### 2. Structure de base

```tsx
"use client";

import { ComponentProps } from "react";

interface MyComponentProps extends ComponentProps<"div"> {
  variant?: "default" | "outline";
  size?: "sm" | "md" | "lg";
}

export function MyComponent({
  variant = "default",
  size = "md",
  className,
  ...props
}: MyComponentProps) {
  return (
    <div
      className={`my-component ${variant} ${size} ${className}`}
      {...props}
    />
  );
}
```

### 3. Documenter

Ajoutez une section dans ce README avec :
- Description
- Props
- Exemple d'utilisation
- Fonctionnalités

## 📖 Bonnes pratiques

### Composants réutilisables

Les composants UI doivent être :
- **Génériques** : Ne pas contenir de logique métier spécifique
- **Composables** : Pouvoir être utilisés ensemble
- **Accessibles** : Suivre les standards WCAG
- **Performants** : Optimisés pour la performance
- **Documentés** : Props et utilisation clairement expliqués

### Props

```tsx
// ✅ BIEN : Props typées avec valeurs par défaut
interface ButtonProps {
  variant?: "primary" | "secondary";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  children: React.ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  children,
}: ButtonProps) {
  // ...
}

// ❌ ÉVITER : Props non typées
export function Button(props: any) {
  // ...
}
```

### Styling

Utilisez Tailwind CSS avec des classes conditionnelles :

```tsx
export function Button({ variant, size, className }: ButtonProps) {
  return (
    <button
      className={`
        base-button
        ${variant === "primary" ? "bg-blue-500" : "bg-gray-500"}
        ${size === "sm" ? "px-2 py-1" : "px-4 py-2"}
        ${className}
      `}
    >
      {children}
    </button>
  );
}
```

### Dark Mode

Utilisez les classes `dark:*` de Tailwind :

```tsx
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
  {children}
</div>
```

### Accessibilité

```tsx
// ✅ BIEN
<button
  aria-label="Close dialog"
  aria-pressed={isActive}
  role="button"
  tabIndex={0}
>
  <XIcon aria-hidden="true" />
</button>

// ❌ ÉVITER
<div onClick={handleClick}>
  <XIcon />
</div>
```

## 🔧 Configuration

### Path Alias

Pour utiliser `@/components/ui/...`, vérifiez que `tsconfig.json` contient :

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Dark Mode

Assurez-vous que `tailwind.config.js` active le dark mode :

```javascript
module.exports = {
  darkMode: "class",
  // ...
};
```

## 📚 Ressources

- **Shadcn/ui** : https://ui.shadcn.com/
- **Tailwind CSS** : https://tailwindcss.com/
- **Framer Motion** : https://www.framer.com/motion/
- **Lucide Icons** : https://lucide.dev/
- **Radix UI** : https://www.radix-ui.com/ (pour composants accessibles)

## 🤝 Contribution

Pour ajouter un nouveau composant UI :

1. Créez le fichier dans ce dossier
2. Suivez les conventions ci-dessus
3. Documentez le composant dans ce README
4. Testez sur mobile/tablet/desktop
5. Vérifiez l'accessibilité
6. Testez en dark mode

---

**Note** : Ce dossier suit la structure shadcn/ui pour faciliter l'ajout de composants pré-conçus.