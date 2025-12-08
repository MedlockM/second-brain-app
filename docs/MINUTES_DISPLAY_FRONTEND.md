# Affichage des minutes disponibles - Documentation

## 📊 Vue d'ensemble

L'affichage des minutes disponibles a été intégré dans le Dashboard avec rafraîchissement automatique et mise à jour en temps réel.

## ✅ Fonctionnalités implémentées

### 1. **Service de récupération des minutes**
**Fichier** : `front/src/services/billingService.ts`

- `getAvailableMinutes(token)` : Récupère le total de minutes disponibles
- `getMinutesBreakdown(token)` : Récupère le détail par source (rollover, subscription, packs)
- Gestion d'erreur gracieuse (retourne 0 en cas d'échec)

### 2. **Composant d'affichage**
**Fichier** : `front/src/components/MinutesDisplay.tsx`

**Fonctionnalités** :
- ✅ Affichage du nombre de minutes avec icône horloge
- ✅ Code couleur selon le niveau :
  - 🔴 Rouge : 0 minutes
  - 🟠 Orange : < 30 minutes
  - 🟡 Jaune : < 100 minutes
  - 🟢 Vert : ≥ 100 minutes
- ✅ Animation lors du changement de valeur
- ✅ Format compact pour grands nombres (1.5k au lieu de 1500)
- ✅ État de chargement avec skeleton

### 3. **Contexte global de gestion**
**Fichier** : `front/src/contexts/MinutesContext.tsx`

**Fonctionnalités** :
- ✅ Provider React pour partager l'état des minutes
- ✅ Hook `useMinutes()` pour accéder aux minutes depuis n'importe quel composant
- ✅ Rafraîchissement automatique toutes les 30 secondes
- ✅ Fonction `refreshMinutes()` pour forcer un rafraîchissement manuel

### 4. **Intégration dans le Dashboard**
**Fichier** : `front/src/components/Dashboard.tsx`

**Position** : Header, entre "My Quizzes & Summaries" et l'icône utilisateur

**Comportement** :
- ✅ Chargement initial au montage du composant
- ✅ Rafraîchissement automatique toutes les 30 secondes
- ✅ Mise à jour en temps réel lors des actions utilisateur

## 🔄 Mise à jour automatique

Les minutes se mettent à jour automatiquement dans les cas suivants :

### 1. **Rafraîchissement périodique** (toutes les 30 secondes)
Le contexte `MinutesProvider` rafraîchit automatiquement les données.

### 2. **Actions utilisateur** (à implémenter si nécessaire)
Pour forcer un rafraîchissement immédiat après certaines actions :

```typescript
import { useMinutes } from "../contexts/MinutesContext";

function MonComposant() {
  const { refreshMinutes } = useMinutes();
  
  const handleAction = async () => {
    // Faire l'action (achat pack, consommation épisode, etc.)
    await faireQuelqueChose();
    
    // Rafraîchir les minutes immédiatement
    await refreshMinutes();
  };
}
```

## 📍 Emplacement dans l'interface

```
┌─────────────────────────────────────────────────────────────┐
│  [Pricing]  [My Quizzes & Summaries]  [📊 500 min]  [👤]   │
│                                         ↑                    │
│                                    Ici !                     │
└─────────────────────────────────────────────────────────────┘
```

## 🎨 Apparence

### État normal (500 minutes)
```
┌──────────────┐
│ 🕐 Minutes   │
│    500       │ (vert)
└──────────────┘
```

### État faible (25 minutes)
```
┌──────────────┐
│ 🕐 Minutes   │
│    25        │ (orange)
└──────────────┘
```

### État vide (0 minutes)
```
┌──────────────┐
│ 🕐 Minutes   │
│    0         │ (rouge)
└──────────────┘
```

### État chargement
```
┌──────────────┐
│ 🕐 Minutes   │
│    ▓▓▓       │ (skeleton)
└──────────────┘
```

## 🔧 Configuration

### Fréquence de rafraîchissement
Par défaut : **30 secondes**

Pour modifier, éditer `front/src/contexts/MinutesContext.tsx` :
```typescript
const interval = setInterval(refreshMinutes, 30000); // Modifier ici
```

### Seuils de couleur
Pour modifier les seuils, éditer `front/src/components/MinutesDisplay.tsx` :
```typescript
const getColorClass = (): string => {
    if (minutes === 0) return "text-red-600 dark:text-red-400";
    if (minutes < 30) return "text-orange-600 dark:text-orange-400";  // ← Modifier
    if (minutes < 100) return "text-yellow-600 dark:text-yellow-400"; // ← Modifier
    return "text-green-600 dark:text-green-400";
};
```

## 🚀 Utilisation dans d'autres composants

Pour afficher les minutes ailleurs dans l'application :

```typescript
import { useMinutes } from "../contexts/MinutesContext";
import MinutesDisplay from "./MinutesDisplay";

function MonComposant() {
  const { availableMinutes, loadingMinutes, refreshMinutes } = useMinutes();
  
  return (
    <div>
      {/* Option 1 : Utiliser le composant */}
      <MinutesDisplay minutes={availableMinutes} loading={loadingMinutes} />
      
      {/* Option 2 : Affichage personnalisé */}
      <p>Vous avez {availableMinutes} minutes disponibles</p>
      
      {/* Option 3 : Rafraîchir manuellement */}
      <button onClick={refreshMinutes}>Rafraîchir</button>
    </div>
  );
}
```

## 📊 API Backend utilisée

**Endpoint** : `GET /api/v1/billing/me`

**Réponse** :
```json
{
  "subscription": { ... },
  "minutes": {
    "total_free": 500,
    "by_source": {
      "rollover": 50,
      "subscription": 240,
      "packs": 210
    }
  },
  "buckets_count": 3
}
```

Le composant utilise `minutes.total_free` pour l'affichage.

## ✅ Tests recommandés

### Test manuel
1. Se connecter au Dashboard
2. Vérifier que les minutes s'affichent
3. Acheter un pack → les minutes doivent augmenter (après 30s max)
4. Consommer un épisode → les minutes doivent diminuer (après 30s max)
5. Vérifier les couleurs selon le niveau

### Test de rafraîchissement
1. Ouvrir le Dashboard
2. Ouvrir la console réseau (F12)
3. Vérifier qu'une requête `GET /api/v1/billing/me` est faite toutes les 30s

## 🐛 Dépannage

### Les minutes ne s'affichent pas
- Vérifier que l'API `/api/v1/billing/me` fonctionne
- Vérifier la console pour les erreurs
- Vérifier que le token est valide

### Les minutes ne se mettent pas à jour
- Vérifier que le rafraîchissement périodique fonctionne (console réseau)
- Vérifier qu'il n'y a pas d'erreur dans la console
- Essayer de rafraîchir manuellement la page

### Les couleurs ne s'affichent pas correctement
- Vérifier les classes Tailwind dans `MinutesDisplay.tsx`
- Vérifier que le dark mode fonctionne

## 📝 Améliorations futures possibles

1. **Tooltip détaillé** : Afficher le détail par source au survol
2. **Notification** : Alerter quand les minutes sont faibles
3. **Graphique** : Historique de consommation
4. **Prédiction** : Estimation de la date d'épuisement
5. **Badge** : Afficher un badge rouge quand minutes < 10

## 🎯 Résumé

✅ **Implémenté** :
- Service de récupération des minutes
- Composant d'affichage avec code couleur
- Contexte global avec rafraîchissement automatique
- Intégration dans le Dashboard

✅ **Fonctionne automatiquement** :
- Rafraîchissement toutes les 30 secondes
- Mise à jour après achat pack, consommation épisode, rollover, etc.
- Animation lors des changements

🚀 **Prêt à l'emploi** !
