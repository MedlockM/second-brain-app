---
id: task-361
title: Maquetter le nouvel encart « Revue des non classés » de l'accueil
status: Done
assignee: []
created_date: '2026-09-06 13:40'
updated_date: '2026-09-07 12:00'
labels:
  - mobile
  - ui
  - design
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce que l'owner reproche à l'encart actuel (2026-09-06)

L'encart d'entrée dans le tri des médias non classés, en haut de l'accueil, ne tient pas le standing du reste de l'app : **l'icône fait vieillotte et enfantine**, **la formulation « Tri des non classés » manque d'allure**, et **l'ensemble de l'encart est à revoir**, pas seulement retouché.

## État actuel, mesuré

`UnsortedReviewButton`, `mobile/app/(tabs)/inbox.tsx` (composant vers la ligne 371, styles `reviewButton*` vers la ligne 589) :

- icône Ionicons **`file-tray-outline`** en 22px, dans une pastille 40×40 remplie de `rgba(255, 203, 5, 0.1)` — une valeur littérale, pas un token ;
- libellé 16px/700 sur deux lignes maximum, puis un badge de compte sur `surfaceContainerHigh` et un chevron ;
- carte `Colors.surface`, `BorderRadius.xl`, bordure `StyleSheet.hairlineWidth` en `outlineVariant`, `Shadows.soft` ;
- l'encart disparaît entièrement quand le compte vaut 0.

Le commentaire du composant dit l'origine du problème : « *Same silhouette, card, badge and chevron as the Daily Digest card it replaces — the style block was renamed, not redrawn* ». L'encart est le bouton Daily Digest recyclé (sa maquette d'origine est `mobile-design-mockups/inbox_daily_digest_button_ux/`), ce qui explique qu'il ne ressemble à rien d'autre dans l'app actuelle.

## Écarts vérifiables au design system

`mobile-design-mockups/my_design_system/DESIGN.md` (« Amber Clarity ») :

- **« The No-Line Rule »** — « *Avoid 1px solid borders for broad layout divisions* » : la carte porte une bordure hairline pleine.
- **« Signature Textures »** — « *Use a 5% opacity tint of the Primary color* » : la pastille d'icône est à 10 %.
- **« Don't over-apply shadows. Only the top bar and primary interactive containers should utilize the soft shadow »** : à arbitrer, l'encart n'est pas le conteneur principal de l'écran.

Ces trois points sont des faits opposables, pas des goûts. Ce sont eux qui doivent porter les variantes, avec les références demandées plus bas.

## Le libellé est tranché

**« Revue des non classés »** (décision owner, 2026-09-06). Ce n'est pas une préférence : le français est le **seul catalogue sur onze** à parler de « tri » — EN « Unsorted review », DE « Unsortiertes durchgehen », NL « Ongesorteerd nalopen », IT « Revisione dei non ordinati », PT « Revisão dos não organizados ». Le FR revient dans le rang. La maquette affiche ce libellé ; son portage dans les catalogues appartient à la tâche d'implémentation.

## Contraintes de la maquette

- Valeurs prises dans `mobile/src/constants/theme.ts` uniquement — couleurs, rayons, ombres, échelle typographique, `TouchTarget`.
- Le compteur reste lisible d'un coup d'œil : c'est la seule information chiffrée de l'encart, et l'encart s'efface à 0.
- Ionicons est la langue d'icônes de l'app partout ailleurs ; une variante qui en sort doit dire pourquoi.
- **Le rythme vertical de l'accueil n'est pas rouvert.** Le feedback `AE3J09ClZ0T9VY8Jc5SnCRc` est classé `declined` le 2026-09-04 dans `docs/testflight-feedback-log.md` : l'owner a tranché qu'on ne touche pas aux écarts entre sections. Aucune variante ne doit proposer de changer `HOME_BLOCK_GAP` ni les marges de section.

## Justifier par des références, pas par une intuition

Une variante n'est recevable que si elle s'appuie sur une règle citée du design system **et** sur au moins une implémentation de référence nommée : les files « à traiter » des apps de lecture différée (Readwise Reader, Matter, Raindrop, Pocket), les patterns documentés de Material 3 (card, list item, banner), ou les captures déjà déposées dans `mobile-design-mockups/notebooklm-reference/`. C'est la même exigence que task-263 posait : un agent ne devine pas une cible visuelle.

## Périmètre

Le livrable est la maquette, pas le code de l'app. Aucun fichier de `mobile/app/` ni de `mobile/src/` n'est modifié ici — l'implémentation suit dans la tâche qui dépend de celle-ci.

## Notes pour l'owner (pas des ACs)

- Tu ouvres `code.html` dans un navigateur, tu choisis une variante (ou tu demandes un tour de plus), et tu notes ton choix dans le README du dossier : c'est ce que la tâche d'implémentation lira.
- Aucune capture d'écran n'est demandée à l'agent : il n'a pas de navigateur pour la produire. Le HTML autonome tient ce rôle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `mobile-design-mockups/home_unsorted_review_card/code.html` existe et s'ouvre seul dans un navigateur, sans ressource distante nécessaire à la fidélité du rendu (repli de police système déclaré), présentant au moins trois variantes de l'encart côte à côte
- [x] #2 Chaque variante est rendue avec les valeurs réelles de `mobile/src/constants/theme.ts` (couleurs, rayons, ombres, échelle typographique) et porte le libellé « Revue des non classés », son icône, son compteur et son affordance d'entrée
- [x] #3 Chaque variante est montrée dans les cas limites que l'app produit : compteur à un chiffre et à trois chiffres, et libellé long des catalogues existants (DE « Unsortiertes durchgehen », PT « Revisão dos não organizados »)
- [x] #4 `mobile-design-mockups/home_unsorted_review_card/README.md` justifie chaque variante par une règle citée de `my_design_system/DESIGN.md` et par au moins une implémentation de référence nommée, dit ce que chaque variante abandonne, et ne s'appuie à aucun endroit sur une préférence personnelle
- [x] #5 Le README nomme l'icône proposée par variante avec son identifiant exact dans la bibliothèque utilisée par l'app, et dit ce qui la rend préférable à `file-tray-outline`
- [x] #6 Le README traite explicitement les trois écarts relevés au design system — bordure hairline contre la « No-Line Rule », teinte d'icône à 10 % contre les 5 % de la règle, usage de `Shadows.soft` — en disant pour chacun ce que la variante retient et pourquoi
- [x] #7 Aucune variante ne propose de modifier le rythme vertical de l'accueil (`HOME_BLOCK_GAP`, marges de section), conformément au no-go owner du 2026-09-04 consigné dans `docs/testflight-feedback-log.md` (`AE3J09ClZ0T9VY8Jc5SnCRc`)
- [x] #8 Le diff de la tâche se limite à `mobile-design-mockups/` et au backlog : aucun fichier de `mobile/app/` ou `mobile/src/` n'est modifié
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Livrable : `mobile-design-mockups/home_unsorted_review_card/code.html` + `README.md`. Aucun fichier de `mobile/` touché (AC#8 vérifié : `git status` ne liste que le dossier de maquette et ce fichier de tâche).

**Autonomie du rendu (AC#1).** Les maquettes existantes du dossier (`inbox_daily_digest_button_ux/code.html`) tirent Tailwind d'un CDN et les polices de Google Fonts, ce qui viole « sans ressource distante nécessaire à la fidélité ». Ici : CSS écrit à la main avec des custom properties nommées d'après les tokens (`--surface-container`, `--radius-xl`, `--shadow-soft`…), pile système déclarée (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto…`) — justifiée par le fait que l'app ne charge aucune police custom et rend donc en San Francisco / Roboto —, et **icônes Ionicons inlinées en `<symbol>` SVG extraites de la fonte de l'app elle-même** (`@expo/vector-icons/.../Fonts/Ionicons.ttf` + `glyphmaps/Ionicons.json`, contours récupérés avec fontTools `SVGPathPen` et un `TransformPen` de retournement en Y). La maquette est donc plus fidèle que les précédentes, pas moins. Sept glyphes embarqués : `file-tray-outline` (état actuel), `layers-outline`, `albums-outline`, `checkmark-done-outline`, `chevron-forward`, `arrow-forward`, `sparkles`.

**Les trois variantes.** A « Pastille tonale » (`surfaceContainer`, `BorderRadius.full`, 56 de haut, ni bordure ni ombre ni teinte, icône `layers-outline` ambre, compteur en chiffre nu) ; B « Encart callout ambre » (champ ambre 5 % + barre `primary` de 4, `BorderRadius.xl`, `albums-outline`, compteur en Metadata Chip blanc) ; C « Compteur en display » (carte `surface`, `Shadows.soft` conservée et argumentée, pastille ambre 5 % de 40, `checkmark-done-outline`, compteur en `Typography.display`, `arrow-forward`). Chaque variante est montrée en contexte accueil complet (safe area, carte, `HOME_BLOCK_GAP`, en-tête « Ajouts récents », deux tuiles) puis dans six cellules de cas limites : FR·3, FR·128, DE·128, PT·9, FR·1042 (`media_count` n'est pas plafonné côté API), et DE·128 dans un cadre étroit de 320 pt.

**Norme « référence, pas intuition ».** Chaque affirmation du README est ancrée soit sur une citation verbatim de `my_design_system/DESIGN.md`, soit sur un fait du dépôt avec fichier:ligne, soit sur une implémentation nommée (pills du Studio NotebookLM déjà déposées dans `notebooklm-reference/`, list item / card / badge / banner Material 3, lignes de boîtes d'iOS Mail, tuiles de listes intelligentes de Rappels, collection système « Unsorted » de Raindrop.io, Inbox de Todoist, file Feed→Inbox→Later de Readwise Reader, et en interne `MinutesWarningBanner` / `FreeTrialNotice` / le chevron de `HomeTile`).

**Faits mesurés pendant l'analyse, versés au README.** (1) L'encart est l'exception de sa propre colonne : les deux autres blocs pleine largeur de l'accueil (`MinutesWarningBanner`, `FreeTrialNotice`) sont des champs tonals sans bordure ni ombre. (2) `Shadows.soft` compte 33 usages dans 20 fichiers, dont 3 sur l'accueil — la règle « only the top bar and primary interactive containers » n'est déjà pas tenue, ce que la variante C assume explicitement au lieu de le taire. (3) `file-tray-outline` est aussi l'icône de l'onglet Accueil (`mobile/app/(tabs)/_layout.tsx`) : l'encart répète le glyphe de l'onglet où il vit, ce qui est un argument opposable en plus du reproche esthétique de l'owner.

**Trois écarts au design system (AC#6).** Traités dans un tableau 3 écarts × 3 variantes, avec un paragraphe d'arbitrage par écart. Point notable : le filet hairline de la puce de compteur de la variante B n'est pas une violation de la No-Line Rule — DESIGN.md prescrit ce filet à l'échelle du composant (« Metadata Chips … a very subtle outline-variant outline »), la règle interdisant les filets pour les « broad layout divisions ».

**Rythme vertical (AC#7).** Une section du README (« Ce que la maquette ne rouvre pas ») et une section de fermeture du HTML (« Ce qu'aucune variante ne touche ») citent le feedback `AE3J09ClZ0T9VY8Jc5SnCRc` classé `declined` le 2026-09-04 et son motif. Les trois variantes déclarent la même `margin-top` de `HOME_BLOCK_GAP` (= `Spacing.lg`, 24) et les mêmes marges latérales `Spacing.md` que l'existant ; seule la hauteur interne de l'encart varie (56 pour A, ≈ 80 pour B, ≈ 108–128 pour C, contre ≈ 80 aujourd'hui).

**Vérifications.** Rendu réel contrôlé en Chrome headless (capture 1400×2400 relue : cadres, variantes, glyphes et cellules de cas limites corrects) ; parse HTML sans balise non fermée ni mal appariée ; zéro `<link>`, `<script>`, `<img>` ou URL dans le fichier ; libellés DE/PT vérifiés contre les catalogues réels de `mobile/src/i18n/locales/` (le « Kürzlich hinzugefügt » des cellules 320 pt a été corrigé après vérification, il avait été deviné tronqué). Deux collisions de rendu corrigées : le fond de page passait à `surfaceContainer` et se confondait avec le remplissage de la variante A (page en `surfaceContainerHigh` désormais), et le fond des `code` inline devait rester visible à la fois sur la page et sur les panneaux blancs (`surfaceContainerLow`).

Aucun test automatisé ajouté, conformément à la règle projet. Le choix de variante appartient à l'owner : le README se termine sur une section « Choix de l'owner » vide, que la tâche d'implémentation lira.
<!-- SECTION:NOTES:END -->
