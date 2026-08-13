---
id: task-254
title: >-
  Mothball the Maestro E2E CI while the UI is still moving, and record the
  reactivation plan in V1_LAUNCH_PLAN
status: Done
assignee: []
created_date: '2026-08-13 14:16'
updated_date: '2026-08-13 16:40'
labels:
  - tooling
  - mobile
  - e2e
  - ci
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les flows Maestro assèrent des libellés et des `testID` d'écrans (`Welcome back`, `Good .*`, `YOUR MEDIA`, `AI Artifacts`, `Choose Your Plan`, `Reader`/`Mix`/`Audio-Heavy`, `paywall-screen`, `search-result-card`…). L'UI de l'app est encore en cours de développement et va changer prochainement : chaque itération de design casse ces selectors et impose de recoder les flows. Maintenir la suite verte maintenant, c'est payer un coût de réécriture à chaque changement d'écran, pour une couverture qui sera de toute façon à refaire.

Décision de l'owner (2026-08-13) : **mettre la CI Maestro en sommeil**, sans supprimer quoi que ce soit. Le workflow, les 7 flows, les scripts runner, les secrets et la fixture de test restent en place et réutilisables tels quels une fois l'UI figée.

## Ce qu'on veut

Que plus aucun run Maestro ne se déclenche tout seul. Aujourd'hui `.github/workflows/mobile-e2e-maestro.yml` se déclenche sur `push` (branches `main` et `second-brain-project`) et sur `pull_request`, tous deux filtrés sur `mobile/**` — donc tout commit touchant le mobile lance un émulateur Android 45 min max, et un push sur `main` en enchaîne un de plus. C'est ce déclenchement automatique qu'il faut neutraliser.

Le `workflow_dispatch` doit rester fonctionnel : c'est le seul moyen de relancer la suite à la main quand on voudra vérifier quelque chose ponctuellement, et c'est aussi ce qui servira à la réactivation.

## Scope

1. **Neutraliser les déclencheurs automatiques** de `.github/workflows/mobile-e2e-maestro.yml` : retirer (ou commenter, au choix de l'implémenteur — l'important est que le YAML reste valide et la logique restaurable en une édition) les blocs `push:` et `pull_request:`. Garder `workflow_dispatch` intact avec ses deux inputs `flow_filter` et `platform`.
2. **Ne rien supprimer d'autre.** Les jobs `android-e2e` / `ios-e2e` / `e2e-summary`, `.github/scripts/run-android-maestro.sh`, `run-ios-maestro.sh`, `.github/scripts/lib/maestro-flows.sh`, les 7 flows de `mobile/.maestro/`, les utils et la suite `suites/tasks_168_170.yaml` restent en place à l'identique.
3. **Écrire en tête du workflow un commentaire de mise en sommeil** qui dit : pourquoi (UI mouvante), depuis quand (2026-08-13), ce qui a été retiré, comment relancer un run entre-temps (`workflow_dispatch`), et où lire le plan de réactivation (la section du V1_LAUNCH_PLAN créée au point 5).
4. **Signaler l'état de sommeil dans `mobile/.maestro/README.md`** et corriger au passage les deux affirmations périmées de `mobile/E2E_TESTING.md` : sa table (ligne ~98) présente le flow 02 comme « Deep link share simulation, confirmation screen, Save action / Android (full) », et sa ligne ~109 présente `media-summarizer://share?url=…` comme le mécanisme de simulation de share sur Android. Les deux sont faux depuis le 2026-06-11 : `mobile/app/+native-intent.tsx` (fonction `redirectSystemPath`) teste `path.includes("://share?")` et redirige vers `/(tabs)/inbox`, donc l'écran de share-confirmation n'apparaît plus par deep link.
5. **Créer dans `docs/V1_LAUNCH_PLAN.md` une section de réactivation** (voir le détail ci-dessous).

## Contenu attendu de la section V1_LAUNCH_PLAN

La placer là où elle sera lue au bon moment — Phase 7 (CI/CD) traite déjà de Maestro à son point 7, et Phase 5 liste task-168 à task-172. L'implémenteur choisit l'emplacement le plus cohérent et **déplace** l'information existante plutôt que de la dupliquer : le point 7 de Phase 7 et les points 6 à 10 de Phase 5 décrivent un état « CI Maestro réparée et à valider » qui n'est plus la trajectoire retenue, et doivent renvoyer vers la nouvelle section au lieu de la contredire.

La section doit couvrir :

- **Le déclencheur de réactivation** : l'UI est figée (plus de refonte d'écran prévue). C'est un jalon produit, pas une date.
- **Ce qui est en sommeil et ce qui ne l'est pas** : les déclencheurs automatiques dorment ; les flows, scripts, secrets GitHub (`E2E_TEST_USER_*`, `E2E_SEARCH_TEST_TERM`, clé RevenueCat Test Store) et la fixture Algolia « Commonplace book » restent provisionnés.
- **L'état réel des 7 flows au moment de la mise en sommeil**, parce que c'est l'information qui coûtera le plus cher à reconstituer plus tard :
  - `01_login`, `06_search`, `07_paywall` — verts sur émulateur Android API 33 et simulateur iOS 18.5 au run 31612429695 (2026-08-12). Ce sont les seuls validés.
  - `02_share_intake` — volontairement neutralisé, réduit à un smoke test auth, tag `skipped`. Le vrai share natif n'est pas pilotable par Maestro (share sheet hors process) ; `E2E_TESTING.md` prévoit un fallback Appium ciblé à n'activer que si une release est bloquée par cette incertitude.
  - `03_inbox_visibility`, `04_media_detail_progression`, `05_artifact_trigger_action` — **cassés, jamais exécutés en CI**. Tous trois amorcent leur scénario par `openLink: "media-summarizer://share?url=…"` puis attendent `assertVisible: "Save Link"` : ce deep link est redirigé vers l'inbox depuis le 2026-06-11, donc « Save Link » n'apparaît jamais et le flow échoue à sa première assertion non optionnelle. Le run vert du 2026-08-12 les a évités via `flow_filter: suites/tasks_168_170`.
- **Le travail à prévoir à la réactivation**, en distinguant ce qui relève du réamorçage et ce qui relève de bugs de flow déjà identifiés :
  - Réamorcer 03/04/05 sur la fixture persistante déjà provisionnée (article « Commonplace book », `ready_for_artifacts`, indexé Algolia) au lieu de simuler un share. Effet de bord bénéfique sur 05 : `mediaReady` est vrai d'emblée, ce qui supprime l'attente de l'apparition du bouton `Generate`.
  - Corriger quatre défauts du flow 05, indépendants de l'UI : (a) `tapOn: text: "Generate", index: 0` est ambigu — les cinq tuiles rendent un bouton dont le texte est exactement `Generate` (`mobile/app/media/[id].tsx:1032`) et l'index se décale dès qu'une tuile est `ready` ; cibler l'`accessibilityLabel` `Generate Summary`, déjà exposé ; (b) `assertVisible: text: "Summary"` est ambigu avec la tuile `Detailed summary` ; (c) aucun `assertNotVisible: "Failed"` après le tap, alors que l'UI rend `Failed` + `Retry` en cas d'échec — le flow brûle donc 180 s avant de tomber sur un diagnostic inutile ; (d) l'`extendedWaitUntil` sur la regex `Queued|Generating|Ready` peut être satisfait d'emblée par une autre tuile déjà `ready`, et le `tapOn: "View"` sans index ouvrirait alors le mauvais artifact.
  - Reprendre la cible finale, portée par deux tâches déjà au backlog : task-171 a été clôturée `Done` le 2026-08-13 sur les 3 flows validés, ses notes consignent ce qui manque (run complet des 7 flows, vert sur les deux plateformes) ; task-172 (Android bloquant sur PR, iOS en nightly/manuel sous le budget de ~200 min macOS gratuites par mois) est verrouillée `dispatchable: false` jusqu'à ce jalon — la déverrouiller consiste à retirer cette ligne de son front-matter.
- **La contrainte de budget CI** qui n'a pas changé : runner macOS = x10 sur les minutes Actions, plan gratuit, donc iOS ne redevient jamais un required check par PR.

## Note à l'owner — hors AC

La désactivation ne devient effective qu'au push sur `main` : tant que les commits ne sont pas poussés, la CI continue de se déclencher avec l'ancienne configuration. À vérifier après push : un commit touchant `mobile/**` ne doit plus faire apparaître de run « Mobile E2E Tests (Maestro) » dans l'onglet Actions, et le bouton « Run workflow » doit toujours être présent sur ce workflow.

Si `Mobile E2E Tests (Maestro)` figure dans les required status checks de la branch protection de `main`, il faut l'en retirer — sinon les PR resteront bloquées en attente d'un check qui ne se déclenchera plus. C'est une action sur `github.com/MedlockM/second-brain-app/settings/branches`, hors de portée d'un agent.

## Ce qu'il ne faut pas faire

- Ne pas supprimer le workflow, les flows, les scripts runner, les secrets ni la fixture.
- Ne pas toucher aux autres workflows (`pr.yml`, `main.yml`, `deploy-lambda.yml`, `mobile-build-distribute.yml`, `mobile-store-promote.yml`).
- Ne pas réécrire les flows 03/04/05 dans cette tâche : le constat est consigné, la réparation appartient à la réactivation.
- Ne pas archiver task-171 ni task-172 — elles restent la cible et sont référencées par la nouvelle section.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le workflow .github/workflows/mobile-e2e-maestro.yml ne comporte plus de déclencheur push ni pull_request actif, et `workflow_dispatch` reste présent avec ses inputs flow_filter et platform
- [x] #2 Le YAML du workflow reste valide et les jobs android-e2e, ios-e2e et e2e-summary sont inchangés ; aucun flow de mobile/.maestro/, aucun script de .github/scripts/ n'a été supprimé ni modifié
- [x] #3 Un commentaire en tête du workflow explique la mise en sommeil : sa raison (UI en cours de refonte), sa date (2026-08-13), ce qui a été neutralisé, le recours au workflow_dispatch, et un renvoi vers la section de réactivation du V1_LAUNCH_PLAN
- [x] #4 docs/V1_LAUNCH_PLAN.md contient une section de réactivation qui énonce le jalon déclencheur (UI figée), ce qui reste provisionné, l'état des 7 flows au 2026-08-13 (3 verts, 02 neutralisé, 03/04/05 cassés sur le deep link redirigé), le travail de réamorçage sur la fixture Commonplace book, les quatre défauts du flow 05, le renvoi à task-171 et task-172, et la contrainte du budget macOS
- [x] #5 Les mentions Maestro devenues fausses dans Phase 5 et Phase 7 du V1_LAUNCH_PLAN renvoient à la nouvelle section au lieu de décrire une validation CI en cours ; l'information n'est pas dupliquée entre les deux endroits
- [x] #6 mobile/.maestro/README.md indique que la CI automatique est en sommeil et comment lancer un run manuel
- [x] #7 mobile/E2E_TESTING.md ne présente plus le deep link media-summarizer://share comme un mécanisme de simulation de share fonctionnel, ni le flow 02 comme couvrant l'écran de confirmation sur Android, et mentionne la redirection opérée par redirectSystemPath dans mobile/app/+native-intent.tsx
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Quatre fichiers touchés, aucune suppression : `.github/workflows/mobile-e2e-maestro.yml`, `docs/V1_LAUNCH_PLAN.md`, `mobile/.maestro/README.md`, `mobile/E2E_TESTING.md`.

### AC #1 et #2 — neutralisation des déclencheurs

Les blocs `push:` et `pull_request:` sont **commentés en place** plutôt que supprimés : la restauration se fait en retirant les marqueurs `#`, sans avoir à retrouver les filtres de paths. Le bloc `on:` ne contient donc plus que `workflow_dispatch`, avec ses deux inputs inchangés.

Vérifié en parsant le fichier avec PyYAML : les clés de haut niveau sont `name`, `permissions`, `on`, `env`, `jobs` ; `on` ne porte que `workflow_dispatch` avec `flow_filter` et `platform` (choice android/ios/both) ; les trois jobs `android-e2e`, `ios-e2e`, `e2e-summary` sont présents. Le `git diff` du workflow ne contient que le commentaire d'en-tête et la mise en commentaire des deux blocs — les jobs sont intouchés au caractère près, et aucun fichier de `mobile/.maestro/` ni de `.github/scripts/` n'apparaît dans le diff.

Point conservé volontairement : la condition `if:` de `android-e2e` commence par `github.event_name != 'workflow_dispatch'`. Elle devient une branche morte puisque seul `workflow_dispatch` déclenche, mais elle reste correcte (la suite du `||` évalue `platform`) et l'AC #2 demande des jobs inchangés — donc pas touchée. Elle redeviendra utile telle quelle à la réactivation.

### AC #3 — commentaire d'en-tête

Bloc `MOTHBALLED — 2026-08-13` en tête du workflow : la raison (UI en refonte, les flows assertent la copie affichée), ce qui a été neutralisé (les deux déclencheurs automatiques, et *seulement* eux), comment lancer un run entre-temps (UI Actions et équivalent `gh workflow run`, avec `suites/tasks_168_170` comme filtre utile), et le renvoi vers `docs/V1_LAUNCH_PLAN.md` Phase 7.

### AC #4 et #5 — section de réactivation, information déplacée

Section `#### Maestro E2E CI — en sommeil depuis le 2026-08-13` placée **en fin de Phase 7 (CI/CD)** : c'est la phase qui traite déjà de Maestro, et le lecteur qui y arrive est en train de statuer sur les gates CI.

Information déplacée, pas dupliquée — les quatre endroits qui décrivaient un état « CI Maestro réparée et à valider » sont devenus des pointeurs d'une ligne :

- Phase 7 point 7 : ne décrit plus le premier run en attente de commit/push ni le paywall rouge ; dit « en sommeil, plus un gate de release, cf. section ci-dessous ».
- Phase 5 « À faire » : les cinq points `task-168` à `task-172` sont collapsés en un seul point 5 qui constate que la couverture Maestro n'est plus un prérequis de Phase 5, et renvoie à la section. Le point sur `task-166` est renuméroté 6 et ne conditionne plus la clôture de Phase 5 à `task-171`/`task-172`.
- Table « Bloquants release immédiats » (section 1) : les lignes `Maestro V1` et `Clôture Phase 5` portaient des constats faux (« Flows 06 search et 07 paywall absents ; workflow CI cassé […] masqués par `|| true` », clôture conditionnée à `task-171/172`) — remplacés par un renvoi. Hors du périmètre littéral de l'AC #5, mais c'était la même affirmation périmée sur les mêmes tâches.

Contenu de la section : jalon déclencheur (UI figée, jalon produit et non date) ; ce qui dort vs ce qui reste provisionné (flows + `utils/` + `suites/`, les trois scripts runner, les jobs, les cinq secrets cités **par nom uniquement**, la fixture « Commonplace book ») ; table de l'état réel des 7 flows au 2026-08-13 avec la preuve pour les 3 verts (run `31612429695`, Android API 33 + iOS 18.5) et la cause exacte pour 03/04/05 ; le travail de réactivation en trois points (réamorçage sur la fixture avec l'effet de bord `mediaReady`, les quatre défauts du flow 05, la reprise de `task-171`/`task-172` avec le geste précis pour déverrouiller 172) ; la contrainte macOS x10 sur plan gratuit.

Ajout connexe : Phase 7 point 8 (déjà consacré à la branch protection) rappelle qu'un `Mobile E2E Tests (Maestro)` resté dans les required checks bloquerait les PR. C'est une consignation pour l'owner, pas une tentative de satisfaire sa note hors-AC — le réglage est sur `settings/branches`, hors de portée d'un agent.

### AC #6 — mobile/.maestro/README.md

Bandeau de sommeil en tête, avec renvoi vers la section V1_LAUNCH_PLAN. La première puce de « Execution model » (« Pull requests and pushes touching `mobile/**` run Android on an emulator ») était devenue fausse : remplacée par le constat de sommeil et le geste de restauration. Nouvelle section « Running a run » (UI Actions, `gh workflow run`, `maestro test` local) qui absorbe le paragraphe final préexistant sur `flow_filter` au lieu de le dupliquer, et qui prévient que 03/04/05 sont rouges à la première assertion.

### AC #7 — mobile/E2E_TESTING.md

- Table des flows : la ligne 02 ne prétend plus couvrir « Deep link share simulation, confirmation screen, Save action / Android (full) » — elle dit « auth smoke test only, tagged `skipped` ». La colonne « Platforms » devient « Status », parce que « Android, iOS » sur 03/04/05 laissait croire à une couverture qui n'a jamais tourné.
- Section « Share Intent Testing Approach » : la sous-section « Android (Fully Automated) » est remplacée par « Neither platform is automated », qui cite `redirectSystemPath` dans `mobile/app/+native-intent.tsx`, les trois patterns matchés (`dataUrl=`, `://share?`, `://share/`), le retour `/(tabs)/inbox`, et **pourquoi** cette redirection est volontaire (une URL de lancement périmée faisait clignoter l'écran de confirmation). Le deep link reste montré, mais comme contre-exemple.
- Corrections de cohérence dans la foulée : bandeau de sommeil dans l'Overview ; « CI Environment » précise que les runs sont manuels ; l'exemple « Run a Specific Flow » ne pointe plus vers `02_share_intake` ; le critère d'escalade Appium ne s'appuie plus sur « Maestro's deep-link-based share simulation » qui n'existe pas ; la ligne 02 de l'arbre de triage ; « All 5 Maestro flows » devient 7 flows, explicitement cadré comme cible post-réactivation.

### Hors périmètre, volontairement

Les flows 03/04/05 ne sont pas réparés (la tâche l'interdit : le constat est consigné, la réparation appartient à la réactivation). Aucun test ajouté. `task-171` et `task-172` ne sont pas archivées. Aucune valeur de secret n'est écrite : seuls les noms `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`, `E2E_SEARCH_TEST_TERM`, `E2E_REVENUECAT_TEST_KEY`, `E2E_API_BASE_URL` apparaissent — le diff a été grepé avant `git add`.

### Ce qui reste à l'owner

La désactivation ne devient effective qu'au push sur `main` : jusque-là la CI continue de se déclencher avec l'ancienne configuration. Après push, vérifier qu'un commit touchant `mobile/**` ne produit plus de run « Mobile E2E Tests (Maestro) », que le bouton « Run workflow » est toujours là, et retirer ce check des required status checks de la branch protection s'il y figure.
<!-- SECTION:NOTES:END -->
