---
id: task-365
title: >-
  Extraire CompletedDetailView de la route média vers un composant partagé, avec
  chrome optionnel
status: To Do
assignee: []
created_date: '2026-09-06 15:41'
labels:
  - mobile
  - refactor
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Pourquoi cette tâche existe

Le Digest V1 doit afficher la page Média de chaque média d'une période, dans un carrousel. **Exigence owner du 2026-09-06 : le Digest et la route média doivent rendre le même composant**, pour qu'une modification future de la page Média se répercute automatiquement dans le Digest, par construction et non par discipline.

Cette tâche ne fait que rendre ce partage possible. Elle ne crée aucune fonctionnalité et ne change rien de visible.

## L'état actuel est déjà favorable

`mobile/app/media/[id].tsx` contient déjà, vers la ligne 294, un composant séparé :

```ts
interface CompletedDetailViewProps {
  mediaData: MediaStatusResponse;
  onBack: () => void;
}
function CompletedDetailView({ mediaData, onBack }: CompletedDetailViewProps)
```

Il prend **la donnée en prop**, pas un identifiant de route. Il n'y a donc rien à réécrire : il faut le sortir du fichier de route vers `mobile/src/components/`, avec ses styles et ses sous-composants privés, et laisser `[id].tsx` l'importer. Les états non-`completed` de la route (chargement, erreur, `processing`, timeout, échec) restent dans le fichier de route : ils appartiennent au cycle de vie de la route, pas à l'affichage d'un média abouti.

## Le chrome doit devenir optionnel

Le composant porte aujourd'hui son propre `SafeAreaView` et son header avec bouton retour. Dans un carrousel, ce header serait répété sur chaque carte, ce qui n'a pas de sens : le Digest affichera un header unique au-dessus du pager.

Le composant reçoit donc de quoi ne pas rendre son chrome. **Le défaut reproduit exactement le comportement actuel de la route** : un appel sans la nouvelle prop rend la page telle qu'elle est aujourd'hui, `SafeAreaView` et header compris. C'est la route qui doit rester inchangée sans rien modifier de son appel.

## Contrainte de comportement constant

Aucun changement visuel, aucun changement de navigation, aucun `testID` retiré ou renommé, aucune valeur de style recalculée « au passage ». Le composant garde son usage de `useRouter()` pour ses navigations internes (sélecteur de collection, ouverture de la source), ce qui fonctionne aussi bien depuis un carrousel que depuis une route.

En revanche il ne doit lire **aucun** paramètre de route : pas de `useLocalSearchParams`, pas de dépendance au segment d'URL. Sa seule source de donnée est la prop `mediaData`.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de réexport de compatibilité depuis `[id].tsx`, pas d'alias conservé, pas de duplication temporaire du composant aux deux endroits. Il vit à un seul endroit après la tâche.

## Note pour l'owner (pas un AC)

La vérification visuelle que la page média est inchangée demande un build : elle t'appartient. L'agent ne peut prouver que l'absence de régression de type et de lint.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CompletedDetailView et ses styles et sous-composants privés vivent dans mobile/src/components/, exportés depuis ce module, et mobile/app/media/[id].tsx ne les définit plus mais les importe
- [ ] #2 Le composant n'utilise plus useLocalSearchParams ni aucun accès aux paramètres de route : sa seule source de donnée est la prop mediaData
- [ ] #3 Une prop optionnelle permet de ne pas rendre le SafeAreaView ni le header interne, et son absence reproduit exactement le rendu actuel de la route média
- [ ] #4 Les états non-completed de la route (chargement, erreur, processing, timeout, échec) restent dans mobile/app/media/[id].tsx
- [ ] #5 Aucun testID n'est retiré ni renommé, et aucune valeur de couleur, d'espacement ou de rayon n'est modifiée pendant le déplacement
- [ ] #6 Aucun réexport de compatibilité ni alias n'est laissé dans mobile/app/media/[id].tsx : le composant n'existe qu'à un seul endroit
- [ ] #7 npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
