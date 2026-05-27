# ADR - Strategie E2E mobile (Maestro-first)

## Statut
Acceptee

## Date
2026-02-24

## Decision
Nous retenons **Maestro** comme framework principal pour l'automatisation E2E mobile de l'app share-first.

Nous conservons une approche hybride:
1. **Maestro-first** pour les parcours critiques Android/iOS.
2. **Validation manuelle obligatoire** sur devices reels pour les cas share entrant sensibles.
3. **Fallback Appium cible** uniquement si l'automatisation iOS share extension reste bloquee de facon durable avec Maestro.

## Contexte
- La stack mobile retenue est React Native + Expo (development builds + EAS).
- Le flux critique produit est le partage entrant de lien (Android Share Intent, iOS Share Extension).
- Le projet est en pre-production avec un objectif de time-to-market rapide.
- Les validations deja planifiees incluent une matrice E2E manuelle multi-devices.

## Options evaluees

### Option A - Appium
Points forts:
- Couverture multi-plateforme mature.
- Controle riche pour des parcours natifs complexes.

Points faibles:
- Cout de maintenance plus eleve pour une equipe qui accelere via generation de code.
- Mise en place et stabilisation initiales plus lourdes.

### Option B - Detox
Points forts:
- Bonne integration historique avec React Native.
- Modele adapte aux assertions d'etat app.

Points faibles:
- Retour terrain plus variable sur stabilite/temps CI selon versions RN et environnements.
- Friction d'upgrade potentiellement plus elevee dans un contexte pre-production mouvant.

### Option C - Maestro (retenue)
Points forts:
- Prise en main rapide et authoring simple pour des parcours E2E mobiles.
- Bon compromis vitesse d'implementation / maintenabilite.
- Compatible avec l'objectif de couvrir vite les flux critiques share-first.

Points faibles:
- Certaines limites possibles sur des parcours iOS tres specifiques selon environnement.
- Peut necessiter un complement cible si un blocage natif persiste.

## Pourquoi cette decision
1. Maximiser la vitesse d'implementation des tests E2E utiles au produit.
2. Reduire la charge de maintenance dans un contexte de forte evolution fonctionnelle.
3. Garder un plan de repli strictement cible (Appium) au lieu de basculer toute la strategie.

## Strategie d'implementation
1. Prioriser les scenarii critiques share-first en Maestro (share intake, inbox, detail media, progression, action artefact).
2. Integrer l'execution automatisee sur builds internes et pipeline CI mobile.
3. Maintenir la matrice manuelle sur devices reels comme gate de release.
4. N'ouvrir une couverture Appium que pour les cas iOS share extension non couverts de maniere fiable par Maestro.

## Risques et mitigations
1. Risque: instabilite de certains tests mobile E2E.
   - Mitigation: limiter aux parcours critiques, fiabiliser les donnees de test, triage explicite des flakes.
2. Risque: blocage d'automatisation iOS share extension.
   - Mitigation: fallback Appium cible et borne, sans migration globale de la suite.
3. Risque: confusion entre validation manuelle et automatisation.
   - Mitigation: conserver les deux gates avec roles distincts (automatisation regression, manuel validation device/source app).

## Consequences
- Les travaux de tests mobile se structurent autour de `task-50`.
- `task-41` reste obligatoire pour la validation manuelle sur devices reels.
- La decision de stack mobile (`docs/ADR/mobile-stack-share-first.md`) est completee par cette decision de strategie test.

## References internes
- `docs/ADR/mobile-stack-share-first.md`
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `backlog/tasks/task-41 - Run-manual-mobile-E2E-validation-matrix-for-share-first-flows.md`
- `backlog/tasks/task-42 - Implement-mobile-CI-CD-signing-and-internal-distribution-TestFlight-Internal-Testing.md`
- `backlog/tasks/task-50 - Implement-automated-mobile-E2E-strategy-Maestro-first-for-share-first-critical-flows.md`
