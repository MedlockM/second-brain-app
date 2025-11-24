# Icônes Lucide React - Référence Rapide

## 📦 Installation

Les icônes Lucide sont déjà installées dans le projet :

```bash
npm install lucide-react
```

## 🎨 Icônes utilisées dans la Landing Page

### Hero Section
- `Sparkles` - Badge AI-Powered
- `ArrowRight` - Boutons CTA
- `Headphones` - Trust badge
- `Zap` - Trust badge

### Features
- `Headphones` - Listen to Podcasts
- `Sparkles` - AI Summaries
- `Zap` - Quick & Efficient

## 📚 Icônes recommandées pour votre projet

### Audio & Podcasts
```tsx
import { 
  Headphones,
  Mic,
  Radio,
  Volume2,
  VolumeX,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Music
} from "lucide-react";
```

### AI & Technology
```tsx
import {
  Sparkles,
  Bot,
  Brain,
  BrainCircuit,
  BrainCog,
  Cpu,
  Network,
  Workflow
} from "lucide-react";
```

### Actions
```tsx
import {
  ArrowRight,
  ArrowLeft,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  Plus,
  Minus,
  X,
  Check,
  Trash2,
  Edit,
  Save,
  Download,
  Upload
} from "lucide-react";
```

### Interface & Navigation
```tsx
import {
  Home,
  Settings,
  Menu,
  Search,
  Filter,
  SortAsc,
  SortDesc,
  Grid,
  List,
  MoreVertical,
  MoreHorizontal
} from "lucide-react";
```

### User & Account
```tsx
import {
  User,
  UserCircle,
  Users,
  LogIn,
  LogOut,
  UserPlus,
  Shield,
  Lock,
  Unlock
} from "lucide-react";
```

### Communication & Social
```tsx
import {
  Mail,
  MessageSquare,
  MessageCircle,
  Send,
  Share2,
  Bell,
  BellOff
} from "lucide-react";
```

### Status & Feedback
```tsx
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  AlertTriangle,
  Info,
  HelpCircle,
  Loader,
  Loader2
} from "lucide-react";
```

### Speed & Performance
```tsx
import {
  Zap,
  Rocket,
  TrendingUp,
  Activity,
  BarChart,
  PieChart,
  Target
} from "lucide-react";
```

### Files & Documents
```tsx
import {
  File,
  FileText,
  Folder,
  FolderOpen,
  Copy,
  Clipboard,
  BookOpen,
  Book
} from "lucide-react";
```

### Time & Date
```tsx
import {
  Clock,
  Calendar,
  CalendarDays,
  Timer,
  History,
  RefreshCw
} from "lucide-react";
```

## 💡 Utilisation

### Exemple de base

```tsx
import { Headphones } from "lucide-react";

function MyComponent() {
  return (
    <div>
      <Headphones size={24} />
    </div>
  );
}
```

### Avec couleur

```tsx
<Headphones 
  size={24} 
  color="#3B82F6" 
/>
```

### Avec classes Tailwind

```tsx
<Headphones 
  size={24} 
  className="text-blue-500 hover:text-blue-600" 
/>
```

### Taille responsive

```tsx
<Headphones 
  className="w-6 h-6 md:w-8 md:h-8 lg:w-10 lg:h-10" 
/>
```

### Dans un bouton

```tsx
<button className="flex items-center gap-2">
  <Sparkles size={20} />
  <span>Get Started</span>
</button>
```

### Animation avec Tailwind

```tsx
<ArrowRight 
  size={20} 
  className="group-hover:translate-x-1 transition-transform" 
/>
```

## 🎯 Bonnes pratiques

### 1. Tailles cohérentes
```tsx
// Petite
<Icon size={16} />

// Moyenne (défaut)
<Icon size={24} />

// Grande
<Icon size={32} />
```

### 2. Accessibilité
```tsx
<Headphones 
  size={24} 
  aria-label="Listen to podcasts"
  role="img"
/>
```

### 3. Props dynamiques
```tsx
function IconWrapper({ name, size = 24 }) {
  const icons = {
    headphones: Headphones,
    sparkles: Sparkles,
    zap: Zap,
  };
  
  const Icon = icons[name];
  return <Icon size={size} />;
}
```

### 4. Avec état (actif/inactif)
```tsx
<Play 
  size={24} 
  className={isPlaying ? "text-blue-500" : "text-gray-400"} 
/>
```

## 🔍 Rechercher des icônes

Visitez : https://lucide.dev/icons/

- 1000+ icônes disponibles
- Recherche par mot-clé
- Prévisualisation en temps réel
- Code d'import copié en un clic

## 📖 Exemples spécifiques au projet

### Feature Card avec icône

```tsx
import { Sparkles } from "lucide-react";

<div className="flex items-start gap-4">
  <div className="p-3 bg-blue-500 text-white rounded-full">
    <Sparkles size={24} />
  </div>
  <div>
    <h3>AI-Powered Summaries</h3>
    <p>Get instant summaries</p>
  </div>
</div>
```

### Bouton avec icône animée

```tsx
import { ArrowRight } from "lucide-react";

<button className="group flex items-center gap-2">
  Get Started
  <ArrowRight 
    size={20} 
    className="group-hover:translate-x-1 transition-transform" 
  />
</button>
```

### Badge avec icône

```tsx
import { Sparkles } from "lucide-react";

<div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 rounded-full">
  <Sparkles size={16} className="text-blue-500" />
  <span className="text-blue-700">AI-Powered</span>
</div>
```

### Liste avec icônes

```tsx
import { Check } from "lucide-react";

<ul className="space-y-2">
  {features.map(feature => (
    <li key={feature} className="flex items-center gap-2">
      <Check size={20} className="text-green-500" />
      <span>{feature}</span>
    </li>
  ))}
</ul>
```

## 🎨 Variantes de style

### Outline (par défaut)
```tsx
<Headphones strokeWidth={2} />
```

### Bold
```tsx
<Headphones strokeWidth={3} />
```

### Light
```tsx
<Headphones strokeWidth={1} />
```

## 🌈 Couleurs avec Tailwind

```tsx
// Couleurs primaires
<Icon className="text-blue-500" />
<Icon className="text-purple-500" />
<Icon className="text-green-500" />

// Avec hover
<Icon className="text-gray-400 hover:text-blue-500" />

// Avec dark mode
<Icon className="text-gray-900 dark:text-white" />

// Avec background
<div className="p-2 bg-blue-500 rounded">
  <Icon className="text-white" />
</div>
```

## 📱 Responsive

```tsx
// Taille responsive
<Icon className="w-4 h-4 sm:w-6 sm:h-6 lg:w-8 lg:h-8" />

// Visible/caché selon breakpoint
<Icon className="hidden md:block" />
<Icon className="block md:hidden" />
```

## 🔗 Liens utiles

- **Documentation** : https://lucide.dev/guide/
- **GitHub** : https://github.com/lucide-icons/lucide
- **NPM** : https://www.npmjs.com/package/lucide-react
- **Figma Plugin** : https://www.figma.com/community/plugin/939567362549682242

---

**Note** : Toutes les icônes Lucide sont open-source sous licence ISC.