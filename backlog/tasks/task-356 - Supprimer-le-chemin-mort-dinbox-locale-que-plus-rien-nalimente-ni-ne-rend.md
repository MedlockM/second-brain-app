---
id: task-356
title: Supprimer le chemin mort d'inbox locale que plus rien n'alimente ni ne rend
status: Done
assignee: []
created_date: '2026-09-04 15:22'
updated_date: '2026-09-04 15:43'
labels:
  - mobile
  - cleanup
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le fait

`InboxContext` expose un `addItem` qui crée un item local à l'état `pending` et le pousse en tête d'une liste `items` tenue en mémoire (`mobile/src/contexts/InboxContext.tsx`, déclaré ligne 41, implémenté ligne 61, exposé ligne 133).

**Rien ne l'appelle.** `grep -rn "addItem" mobile/src mobile/app` ne renvoie que ces trois occurrences, toutes dans le fichier qui le définit : aucun consommateur, aucun écran, aucun test. Le chemin est mort au sens propre — il ne peut rien rendre, puisque personne ne l'alimente.

Relevé pendant l'implémentation de task-353. Il vaut la peine de dire *pourquoi* c'est du code mort et pas une fonctionnalité inachevée à finir : la question posée à ce moment-là était d'afficher la vignette d'un média partagé plus tôt, et une des deux voies envisagées consistait justement à faire vivre un item local pendant l'upload — ce à quoi ce code aurait servi. L'arbitrage a retenu l'autre voie : c'est le backend qui émet l'image tôt (task-353, livrée). Ce chemin n'a donc plus de futur consommateur ; ce n'est pas une amorce qu'on garderait « au cas où ».

## Ce qui est attendu

Supprimer `addItem` et tout ce qui n'existe que pour lui — le générateur d'identifiant local s'il ne sert à rien d'autre, l'entrée correspondante du type du contexte, les champs de `InboxItem` qui deviendraient inatteignables.

**Établir la portée avant de couper** plutôt que la présumer : `items`, `updateItem` et le reste du contexte peuvent avoir des consommateurs bien vivants. Ne supprimer que ce dont on a vérifié qu'il ne reste lu par personne.

Cadrage (`AGENTS.md`, « Nothing is deployed yet ») : rien n'est en production, pas de couche de compatibilité, pas de dépréciation — la suppression se fait dans le même run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `grep -rn 'addItem' mobile/src mobile/app` ne renvoie plus rien
- [ ] #2 Tout ce qui n'existait que pour ce chemin est supprimé avec lui ; ce qui reste dans `InboxContext` a au moins un lecteur, vérifié par grep et non présumé
- [ ] #3 `npm run typecheck` et `npm run lint` sont propres dans `mobile/`
<!-- AC:END -->
