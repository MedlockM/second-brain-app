---
id: task-263
title: Redesign the mobile UI along Google NotebookLM's interface
status: Done
assignee: []
created_date: '2026-08-13 19:45'
updated_date: '2026-08-19 19:25'
labels:
  - mobile
  - ui
  - design
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Décision de l'owner (2026-08-13) : rapprocher l'UI de l'app de celle de **Google NotebookLM**. La cible n'est pas un thème, c'est la façon dont NotebookLM organise la lecture (structure de navigation, hiérarchie de l'information, densité, place des artefacts générés à côté de la source).

Ce chantier est aussi le jalon qui **fige l'UI** : task-254 a mis la CI Maestro en sommeil le 2026-08-13 précisément parce que les flows assertent la copie affichée et les `testID` des écrans, et que chaque itération de design les casse. Le déclencheur de réactivation consigné dans `docs/V1_LAUNCH_PLAN.md` (Phase 7, section « Maestro E2E CI — en sommeil ») est « l'UI est figée ». Cette tâche est ce jalon.

Matériel existant :
- `mobile-design-mockups/` — 11 maquettes du design actuel (`my_design_system`, `inbox_daily_digest_button_ux`, `media_detail_ai_artifacts_dropdown`, `media_detail_ai_artifacts_expanded`, `search_harmonized_v2`, `account_harmonized_v2`, `weekly_digest_harmonized_v2`, `daily_digest_your_day_in_review`, `confirmation_de_partage_version_finale`, `s_lection_de_collection`, `gestion_des_tags_no_keyboard_space`).
- Design system courant « Amber Clarity » dans `mobile/src/constants/theme.ts`, seul autorisé pour les valeurs de couleur/espacement/typo.
- Écrans actuels : `mobile/app/(tabs)/{inbox,search,digest,account}.tsx`, `mobile/app/media/[id].tsx`, `mobile/app/media/{collection,collections,tags}`, `mobile/app/artifacts/[artifactId].tsx`, `mobile/app/share-confirmation.tsx`, `mobile/app/paywall.tsx`, `mobile/app/(auth)/*`, `mobile/app/onboarding/language.tsx`, `mobile/app/bug-report.tsx`, `mobile/app/settings/*`.

Pas de tâche benchmark ici : il n'y a pas de choix technologique ouvert, la cible visuelle est tranchée par l'owner via ses screenshots.

## Ce qui a déjà été détaché de ce chantier (2026-08-17)

L'owner a livré ses deux premières références et la structure de navigation qu'elles impliquent. Le travail correspondant est **sorti de cette tâche** et vit dans des tâches dispatchables, indépendantes du verrou ci-dessous :

- `mobile-design-mockups/notebooklm-reference/collection-sources-tab.png` et `collection-studio-tab.png` sont déposés, et leur mapping écran par écran est consigné dans `mobile-design-mockups/notebooklm-reference/README.md`.
- **task-271** — media detail : la liste déroulante « AI Artifacts » disparaît au profit de deux onglets intra-écran **« Reader »** (transcript) et **« AI »** (génération). Cette tâche crée les deux composants partagés (onglets, tuile d'artefact) que les suivantes réutilisent.
- **task-269** (benchmark) puis **task-270** (implémentation) — le backend qui manque : générer un artefact sur **tous les médias d'une collection agrégés**, ce qui n'existe nulle part aujourd'hui (toute la chaîne est scopée à un `media_item_id`).
- **task-272** — collection detail : onglets **« Sources »** (liste dépouillée icône + titre) et **« AI »** (les 5 types au scope collection). Dépend de task-270 et task-271.

Ce qui reste dans cette tâche : la refonte visuelle des autres écrans du périmètre, le portage des tokens, et le rôle de jalon « l'UI est figée » qui rouvre la CI Maestro. Les tâches ci-dessus sont volontairement **antérieures** : elles fixent la structure de navigation des deux écrans les plus chargés, et la refonte visuelle globale s'y adosse plutôt que de les refaire.

## Pourquoi cette tâche est verrouillée (`dispatchable: false`)

Un agent ne peut pas deviner la cible visuelle. Sans les screenshots de référence dans le repo, un dispatch produirait une refonte au hasard, coûteuse à défaire, et casserait au passage les libellés que les flows Maestro asserteront à la réactivation. Le verrou est donc dans le front-matter, indépendant du statut et de la priorité.

## Ce que l'owner doit fournir avant de déverrouiller

1. **Les screenshots NotebookLM**, déposés dans `mobile-design-mockups/notebooklm-reference/` (png ou jpg), un fichier par écran, nommés lisiblement. *Deux sont déposés (collection : Sources et Studio) — il manque les écrans du reste du périmètre.*
2. **Pour chaque screenshot** : quel écran de l'app il cible, et ce qui doit être repris (structure de navigation, hiérarchie typographique, densité, composants, palette) vs ce qui ne doit surtout pas l'être. *Fait pour les deux screenshots déposés, dans le README de référence — à compléter au fil des suivants.*
3. **Le périmètre d'écrans**, en cochant la liste ci-dessous.
4. **Le sort d'Amber Clarity** : palette conservée avec la structure NotebookLM, ou palette également alignée sur la référence.
5. Retirer la ligne `dispatchable: false` du front-matter de cette tâche.

Périmètre — à cocher par l'owner (laisser décoché = hors périmètre) :

- [ ] Inbox `(tabs)/inbox.tsx`
- [ ] Search `(tabs)/search.tsx`
- [ ] Digest quotidien + hebdo `(tabs)/digest.tsx`
- [ ] Account `(tabs)/account.tsx`
- [ ] Barre d'onglets `(tabs)/_layout.tsx`
- [ ] Media detail `media/[id].tsx`
- [ ] Artifact detail `artifacts/[artifactId].tsx`
- [ ] Explorateur de collections + détail `media/collections`, `media/collection.tsx`
- [ ] Gestion des tags `media/tags.tsx`
- [ ] Écran de confirmation de partage `share-confirmation.tsx`
- [ ] Paywall `paywall.tsx`
- [ ] Login / Register `(auth)/*`
- [ ] Onboarding langue `onboarding/language.tsx`
- [ ] Settings `settings/*`, Bug report `bug-report.tsx`

## Scope, une fois déverrouillée

1. **Tracer la cible** dans `mobile-design-mockups/notebooklm-reference/README.md` : screenshot → écran(s) visés → écart constaté avec l'écran actuel → décision de reprise. C'est ce document que l'implémenteur suit, et ce qui permettra plus tard de comprendre pourquoi un écran a la forme qu'il a.
2. **Design system d'abord** : porter les tokens de la cible dans `mobile/src/constants/theme.ts` et dans les composants partagés de `mobile/src/components/`, avant de toucher aux écrans. Une refonte écran par écran avec des valeurs en dur est le résultat à éviter.
3. **Refondre les écrans cochés**, et seulement eux (la propagation des tokens sur les autres écrans est normale et attendue).
4. **Consigner les maquettes de `mobile-design-mockups/` que la refonte périme** dans le README de référence. Ne pas les supprimer : ce sont les documents de design de l'owner, leur sort lui revient.
5. **Consigner les libellés et `testID` modifiés** et les flows Maestro qu'ils cassent. C'est l'information la plus chère à reconstituer à la réactivation.

Lien avec task-264 (import de fichiers + prise de photo) : cette tâche-là ajoute un point d'entrée « ajouter » dans l'inbox et étend l'écran de confirmation. Aucune dépendance déclarée pour ne pas se bloquer mutuellement, mais si task-264 a déjà landé au moment du dispatch, ses écrans font partie de la surface à refondre.

## Note à l'owner — hors AC

- **La validation visuelle reste la vôtre** : un agent en worktree ne lance pas l'app. À prévoir sur dev build iOS et Android après merge.
- **Réactivation Maestro** : c'est cette tâche qui ouvre la porte. Le plan est dans `docs/V1_LAUNCH_PLAN.md` Phase 7 ; task-172 est verrouillée `dispatchable: false` jusque-là.
- **Tâches voisines sur la même surface** : task-186 (rebranding « Media Summarizer » → nom final) et task-180 (icônes). Les ordonner avec celle-ci plutôt que de les laisser se croiser.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile-design-mockups/notebooklm-reference/README.md` existe et mappe chaque screenshot fourni par l'owner vers le ou les écrans visés, l'écart constaté avec l'écran actuel, et la décision de reprise
- [ ] #2 Les tokens de la cible sont portés dans `mobile/src/constants/theme.ts` et dans les composants partagés de `mobile/src/components/` ; aucun écran refondu n'introduit de valeur de couleur, d'espacement ou de typographie en dur
- [ ] #3 Chaque écran coché par l'owner dans le périmètre est refondu conformément au mapping du README, et aucun écran non coché n'est modifié au-delà de la propagation des tokens
- [ ] #4 Aucune route de `mobile/app/` n'est supprimée ou renommée sans que tous ses points d'entrée (`router.push`, `router.replace`, `href`) soient mis à jour — aucune cible de navigation morte ne subsiste
- [ ] #5 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning, et les règles react-hooks restent au niveau où task-227 les a laissées
- [ ] #6 La liste des libellés visibles et des `testID` modifiés par la refonte est consignée, avec pour chacun les flows de `mobile/.maestro/*.yaml` qu'il casse, comme matière pour la réactivation prévue par task-254
- [ ] #7 Les maquettes de `mobile-design-mockups/` périmées par la refonte sont listées dans le README de référence, et aucune n'est supprimée
- [ ] #8 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->
