# ADR - Stack mobile share-first

## Statut
Acceptée

## Date
2026-02-24

## Décision
Nous retenons **React Native + Expo (development builds + EAS)** comme stack mobile par defaut pour le produit share-first.

## Contexte
- Le produit est pre-production, avec objectif de livraison rapide.
- Le flux critique est le partage entrant de lien (Android Share Intent, iOS Share Extension).
- L'equipe est novice mobile, avec une base forte en Python et TypeScript.
- Le projet front actuel est deja en TypeScript, ce qui favorise la reutilisation de pratiques/outils JS.

## Options evaluees

### Option A - React Native + Expo (retenue)
Points forts:
- Demarrage plus rapide pour une equipe novice mobile.
- Moins de friction sur setup local, builds et distribution interne via EAS.
- Bonne continuite avec un environnement TypeScript.

Points faibles:
- Le partage entrant n'est pas disponible "automatiquement".
- Besoin d'ajouter de la configuration native pour Android/iOS.
- Sur iOS, la mise en place d'extension peut demander plus de vigilance (support Expo a valider en pratique).

### Option B - React Native bare
Points forts:
- Controle natif maximal des flux share entrant.
- Moins de dependance aux limites d'une couche d'abstraction.

Points faibles:
- Complexite plus elevee pour une equipe novice (Xcode, Gradle, signatures, maintenance native).
- Ralentit le demarrage MVP.

### Option C - Flutter
Points forts:
- Stack mobile solide et coherente pour une app from-scratch.

Points faibles:
- Moins d'alignement avec les habitudes TypeScript du projet.
- Cout de montee en competence plus important dans le contexte actuel.

## Pourquoi cette decision
1. Priorite au time-to-market avec risque controle.
2. Meilleur compromis pour une equipe novice mobile.
3. Possibilite d'escalade: conserver une porte de sortie vers du natif plus direct si un blocage critique apparait sur le share entrant.

## Contraintes produit a respecter
1. L'app doit apparaitre dans le menu Partager sur Android et iOS.
2. Une URL partagee doit etre visible dans l'app rapidement.
3. Le flux de partage entrant doit rester stable sur de vrais devices, pas seulement en simulateur.

## Strategie d'implementation share entrant
1. Demarrer en Expo avec development builds (pas Expo Go pour valider ce flux).
2. Implementer Android Share Intent puis iOS Share Extension.
3. Valider tot sur devices physiques (au moins un Android, un iPhone).
4. Si blocage critique non resolu dans delai acceptable: bascule ciblee vers React Native bare pour la partie native, sans remettre en cause le reste du code applicatif.

## Implications setup developpeur
1. Prerequis:
   - Node.js LTS
   - EAS CLI
   - Android Studio (SDK + emulator)
   - Xcode (pour iOS, sur macOS)
2. Travail quotidien:
   - Developpement JS/TS principal.
   - Configuration native ponctuelle pour share entrant.
3. Regle projet:
   - Toute dependance/plugin touchant au partage entrant doit etre evaluee d'abord sur Android + iOS reel.

## Implications CI/CD et signing
1. Utiliser EAS Build pour builds internes Android/iOS.
2. Signatures gerees avec credentials stores (Apple/Google) documentees dans le runbook release.
3. Pipeline minimal:
   - Build preview interne
   - Validation manuelle share entrant
   - Build release candidate
4. Conditions de passage en phase publication:
   - Share entrant valide sur devices reels.
   - Flux ingestion/transcription/artifacts stable.

## Risques et mitigations
1. Risque: integration iOS share extension plus longue que prevu.
   - Mitigation: spike technique precoce et validation device des Phase 4.
2. Risque: ecart entre comportement dev et build store.
   - Mitigation: tester tot avec development builds EAS et non uniquement en local.
3. Risque: dependance a un plugin tiers fragile.
   - Mitigation: privilegier code/strategie maintenable en interne et documenter un plan fallback.

## Consequences
- Les taches Phase 4 et Phase 5 prennent cet ADR comme reference unique.
- Les decisions futures mobile doivent rester coherentes avec ce choix, sauf nouvel ADR explicite.

## References internes
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `backlog/tasks/task-18 - Decide-mobile-stack-and-lock-ADR-React-Native-Expo-vs-Flutter.md`
