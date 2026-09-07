# Encart « Revue des non classés » de l'accueil — trois variantes (task-361)

Maquette de l'encart d'entrée dans le tri des médias non classés, en haut de
l'onglet Accueil. Le livrable est `code.html` ; ce fichier est l'argumentaire.

Chaque variante y est justifiée par **une règle citée** de
`../my_design_system/DESIGN.md` et par **au moins une implémentation de référence
nommée**, et chacune dit ce qu'elle abandonne. Rien ici ne repose sur un goût :
quand une question ne se tranche pas par une règle ou par une référence, elle est
laissée ouverte et signalée comme telle, à l'owner.

## Comment lire la maquette

- Ouvre `code.html` dans un navigateur, hors ligne si tu veux : le fichier ne
  contient ni `<link>`, ni `<script>`, ni `<img>`, donc aucune requête réseau.
  Ce qui s'affiche est ce qui est dans le fichier.
- **Police** : l'app ne charge aucune police (aucun `useFonts`, aucun
  `fontFamily` dans `mobile/app` ni `mobile/src`, hormis le `"serif"` du digest).
  Elle rend donc en police système — SF Pro sur iOS, Roboto sur Android — et la
  maquette déclare la pile système équivalente (`-apple-system,
  BlinkMacSystemFont, "Segoe UI", Roboto, …`). Aller chercher Plus Jakarta Sans
  chez Google Fonts aurait été à la fois une ressource distante et une
  **infidélité** : l'app ne l'embarque pas.
- **Icônes** : chaque glyphe est le contour exact extrait de la fonte que l'app
  embarque (`@expo/vector-icons/…/Fonts/Ionicons.ttf`, 512 unités/em), reporté
  dans un `<symbol viewBox="0 0 512 512">`. Ce ne sont pas des redessins : c'est
  la géométrie que `<Ionicons name="…" />` affiche, à la taille où elle
  l'affiche.
- **Valeurs** : toutes les couleurs, tailles de texte, espacements, rayons et
  ombres sont les variables CSS déclarées en tête de `code.html`, recopiées de
  `mobile/src/constants/theme.ts`.
- **Cadres** : 390 pt de large (device courant) et 320 pt pour la colonne
  Display Zoom, avec la zone sûre au-dessus, puis l'encart, puis l'écart
  d'accueil et l'en-tête de section « Ajouts récents ». L'encart se juge dans son
  voisinage, pas isolé.

## Le libellé n'est pas en discussion ici

Le libellé affiché est **« Revue des non classés »** (décision owner du
2026-09-06). Le fait qui la porte : sur onze catalogues, le français était le
seul à parler de « tri » — EN `Unsorted review`, DE `Unsortiertes durchgehen`,
NL `Ongesorteerd nalopen`, IT `Revisione dei non ordinati`,
PT `Revisão dos não organizados`. Le portage dans `mobile/src/i18n/fr.ts`
appartient à la tâche d'implémentation, pas à cette maquette.

## Ce que la maquette ne rouvre pas

- **Le rythme vertical de l'accueil.** `HOME_BLOCK_GAP` reste `Spacing.lg` (24),
  déclaré au-dessus de chaque bloc et nulle part en dessous
  (`mobile/src/constants/homeRhythm.ts`), et les marges de section ne bougent pas
  (`Spacing.md` = 16 en horizontal pour l'encart, `Spacing.lg` = 24 pour
  l'en-tête de section). Motif : le retour TestFlight `AE3J09ClZ0T9VY8Jc5SnCRc`
  est classé `declined` le 2026-09-04 dans `docs/testflight-feedback-log.md`,
  avec la raison écrite « fausse alerte, on ne touche à rien ». Aucune des trois
  variantes ne propose de changer un écart entre sections. La seule chose qui
  varie d'une variante à l'autre est la **hauteur propre de l'encart**, qui n'est
  pas un écart de section.
- **La disparition à 0.** L'encart s'efface entièrement quand le compteur vaut 0,
  comme aujourd'hui (`if (count <= 0) return null;`). Aucune variante ne propose
  d'état vide.
- **Le contrat d'accessibilité.** Le libellé lu par le lecteur d'écran reste bâti
  sur `home.unsortedReviewA11y` + `common.itemCount`, et la cible reste la carte
  entière — jamais le chevron seul.

## L'encart actuel, en faits

`UnsortedReviewButton`, `mobile/app/(tabs)/inbox.tsx` (composant vers la ligne
372, styles `reviewButton*` vers la ligne 589) :

| Ce qui est posé | Valeur dans le code |
|---|---|
| Coque | `Colors.surface`, `BorderRadius.xl`, `padding: Spacing.md + 4`, `minHeight: TouchTarget.comfortable` |
| Filet | `borderWidth: StyleSheet.hairlineWidth`, `borderColor: Colors.outlineVariant` |
| Ombre | `...Shadows.soft` |
| Pastille d'icône | 40 × 40, `BorderRadius.lg`, `backgroundColor: "rgba(255, 203, 5, 0.1)"` — littéral, hors token |
| Icône | `file-tray-outline`, 22 px, `Colors.primary` |
| Libellé | 16 px / 700, deux lignes maximum |
| Compteur | badge `surfaceContainerHigh`, `minWidth: 24`, 13 px / 700 |
| Affordance | `chevron-forward` 20 px en `Colors.primary` |

Trois faits mesurables encadrent la refonte, et ils sont vérifiables dans le
dépôt :

1. **L'encart est l'exception de sa propre colonne.** Les deux blocs qui peuvent
   se placer juste au-dessus de lui sur le même écran n'ont ni filet ni ombre :
   `MinutesWarningBanner` est un bloc tonal (`Colors.surfaceContainerHigh`,
   `BorderRadius.lg`, aucune bordure, aucune ombre) et `FreeTrialNotice` est une
   pastille (`BorderRadius.full`, `Colors.highlight`, aucune bordure, aucune
   ombre). L'encart est le seul à s'entourer d'un trait.
2. **`Shadows.soft` ne distingue plus rien.** Le dépôt en compte 33 usages dans
   20 fichiers, dont **trois sur l'accueil seul** : l'encart, le bouton photo et
   le bouton d'ajout. Trois des quatre surfaces interactives de l'écran sont
   « élevées ».
3. **Le glyphe est celui de l'onglet où l'on se trouve.** `file-tray-outline` est
   l'icône Android de l'onglet Accueil (`mobile/app/(tabs)/_layout.tsx:98`, avec
   `sf="tray"` côté iOS). L'encart porte donc, en haut de l'accueil, l'icône de
   l'accueil.

Le commentaire du composant dit d'où vient la silhouette : « *Same silhouette,
card, badge and chevron as the Daily Digest card it replaces — the style block
was renamed, not redrawn* ». La maquette d'origine est
`../inbox_daily_digest_button_ux/`.

## Les trois écarts au design system, et ce que chaque variante en fait

| Écart | Citation de `DESIGN.md` | A — Pastille tonale | B — Callout ambre | C — Compteur en display |
|---|---|---|---|---|
| Filet hairline autour de la carte | « **The "No-Line" Rule** : Visual sectioning is achieved through color blocks and tonal shifts. **Avoid 1px solid borders for broad layout divisions.** » | **Supprimé** — remplacé par un décalage tonal `surfaceContainer` sur `background` | **Supprimé** — remplacé par un fond primaire à 5 % + la barre de 4 px | **Supprimé** — la carte reste blanche et se détache par l'ombre |
| Pastille d'icône à 10 % | « **Signature Textures** : Use a **5% opacity** tint of the Primary color (Amber) for callouts and blockquotes » | **Supprimée** — plus de pastille du tout | **Supprimée** — la teinte à 5 % passe au fond de l'encart entier, ce que la règle décrit | **Conservée et ramenée à 5 %** exactement |
| `Shadows.soft` sur l'encart | « **Don't** over-apply shadows. **Only the top bar and primary interactive containers** should utilize the `soft` shadow » | **Retirée** | **Retirée** | **Conservée, et assumée** |

Le détail des trois arbitrages :

### Le filet — les trois variantes le retirent

Aucune ne le garde, parce que la règle est explicite sur le cas : un encadré
pleine largeur qui sépare un bloc de son fond est exactement une « broad layout
division ». Le remplacement diffère (bloc tonal, champ ambré, ombre), et c'est ce
que l'owner arbitre.

Un filet subsiste pourtant dans B, à un seul endroit : le **chip de compteur**.
C'est le seul filet que le système prescrit lui-même — « **Metadata Chips** :
Pill-shaped (`rounded-full`) with a `surface` fill and a **very subtle
`outline-variant`** (5% black) to give them a physical "sticker" feel ». Un chip
n'est pas une division de layout, il est l'objet posé dessus ; les deux règles ne
se contredisent pas, elles n'opèrent pas à la même échelle.

### La teinte à 10 % — deux la suppriment, une la ramène à 5 %

Le fait derrière l'écart n'est pas seulement la valeur, c'est qu'elle est écrite
en dur : `backgroundColor: "rgba(255, 203, 5, 0.1)"`, dans un dépôt où toute
couleur vient de `theme.ts`. **Quelle que soit la variante retenue, la valeur
doit devenir un token nommé** — c'est une note pour l'implémentation, pas une
variante.

Il y a une tension réelle à signaler, parce qu'elle contraint le choix : l'ambre
`#ffcb05` est très clair, donc un glyphe ambre en trait fin sur un fond clair est
**décoratif**, jamais porteur d'information — et le ramener de 10 % à 5 %
éclaircit encore son support. Les trois variantes en tirent trois conclusions
différentes : A garde le glyphe ambre sans pastille et fait porter le sens par le
libellé et le chiffre (`textSubtle`, le gris créé pour être lu) ; B met le glyphe
en `textMain` et donne l'ambre à la structure (barre + champ) ; C conforme la
pastille à 5 % et met le glyphe en `textMain` par-dessus.

### L'ombre — A et B la retirent, C la garde et l'argumente

La règle nomme ses ayants droit : « the top bar and primary interactive
containers ». Sur l'accueil, les conteneurs qui flottent au-dessus du contenu
sont les deux boutons ronds (`cameraButton`, `addButton`, `TouchTarget.large`,
épinglés au-dessus de la barre d'onglets) : eux sont littéralement au-dessus du
contenu qui défile dessous. L'encart, lui, défile avec le contenu.

- **A et B la retirent** : un encart qui défile n'est pas une couche au-dessus du
  contenu, et l'ombre est déjà sur trois surfaces de l'écran (fait 2 ci-dessus).
- **C la garde** au titre de « primary interactive container » : c'est le seul
  appel à l'action de l'écran, en tête de colonne, et la variante l'assume comme
  telle. C'est un arbitrage, pas une évidence : c'est précisément ce que l'owner
  tranche en choisissant C ou non. Référence de ce raisonnement hors du dépôt :
  Material 3 range les cartes en trois familles — *elevated*, *filled*,
  *outlined* — et réserve l'*elevated* à ce qui doit se lire comme surélevé, la
  *filled* servant justement à séparer du fond « avec moins d'emphase ». A est
  une *filled card* (au rayon d'une pastille), C une *elevated card*.

---

## A — « Pastille tonale »

**Coque** : `surfaceContainer` (#f1edea) sur `background`, `BorderRadius.full`,
hauteur `TouchTarget.comfortable` (56), marges `Spacing.md`, aucun filet, aucune
ombre, aucune teinte ambre de fond.
**Contenu** : `layers-outline` 22 px en `Colors.primary` sans pastille · libellé
16 px / 600 `textMain` **sur une ligne, tronqué** · compteur en chiffre nu 16 px /
600 en `textSubtle` · `chevron-forward` 20 px en `textMuted`.

### Règles du système citées

- « The "No-Line" Rule : … **the segment control uses a subtle
  `surface_container` background against the main `surface` rather than a
  stroke** » — A applique littéralement l'exemple donné par la règle : un
  contrôle se signale par un fond tonal, pas par un trait.
- « **The Layering Principle** : Use the `surface-container` tiers to stack
  information » — la hiérarchie vient du palier tonal.
- « Don't over-apply shadows » — aucune ombre.
- « **Segmented Control** : A pill-shaped container… » — le rayon `full` est la
  forme que le système donne à ses conteneurs de contrôle.

### Implémentations de référence

1. **NotebookLM, onglet Studio** — capture déjà déposée dans le dépôt :
   `../notebooklm-reference/collection-ai-generated-list.png`. Les entrées de
   génération (« Infographie », « Rapports ») sont des **pastilles pleine
   largeur, rayon full, remplissage tonal, glyphe à gauche + libellé, sans filet
   ni ombre**. Cette grammaire est déjà retenue par l'owner dans ce dépôt :
   `../notebooklm-reference/README.md` écrit, pour task-272, « À reprendre : …
   la pile de grandes pastilles pleine largeur, une par type d'artefact, icône à
   gauche et libellé ». A est cette pastille, avec un compteur.
2. **Material 3, *list item*** — un item une ligne fait **56 dp** de haut et
   porte une icône en tête (*leading icon*), un *headline*, et un *trailing
   supporting text* à droite ; il ne s'entoure pas d'un trait. Les 56 de
   `TouchTarget.comfortable` et le trio icône / libellé / chiffre à droite sont
   exactement ce patron.
3. **Mail sur iOS, liste des boîtes** — glyphe teinté à gauche, nom de la boîte,
   **nombre à droite en gris**, puis chevron. C'est la référence du compteur en
   chiffre nu plutôt qu'en badge : le nombre est une information secondaire
   alignée à droite, pas une décoration.
4. **Raindrop.io, collection système « Unsorted »** — le jumeau conceptuel exact
   (un signet enregistré sans collection y tombe), rendu comme une **ligne de
   liste avec son compteur aligné à droite**, pas comme une carte.

### L'icône : `layers-outline`

Identifiant exact dans la bibliothèque de l'app (Ionicons, via
`@expo/vector-icons`) : **`layers-outline`**.

- Ce que le glyphe dessine : trois plaques empilées vues en perspective, c'est-à-
  dire **une pile avec une épaisseur**.
- Pourquoi préférable à `file-tray-outline` : (a) le seul contenu informatif de
  l'encart est une **quantité en attente**, et ce glyphe dessine une quantité là
  où un bac dessine un récipient ; (b) `layers` n'apparaît **nulle part** dans
  `mobile/app` ni `mobile/src` — zéro collision, alors que `file-tray-outline` a
  quatre sites d'appel pour trois sens (onglet Accueil, état vide d'une
  collection dans `mobile/app/media/collections/[id].tsx:800`, ligne « Non
  classés » du sélecteur dans `mobile/src/components/CollectionPickerView.tsx:297`,
  et cet encart) ; (c) il ne représente aucun objet physique — là où un bac à
  courrier en papier est un meuble de bureau du XX<sup>e</sup> siècle, sans
  équivalent dans ce que l'app contient (vidéos, podcasts, articles, photos).
  C'est le contenu objectif du reproche « vieillot et enfantin » : une métaphore
  skeuomorphe empruntée à un objet que le produit ne manipule pas.

### Ce qu'elle abandonne

- **La prééminence.** Elle se lit comme un contrôle, pas comme une annonce. Un
  utilisateur qui ne cherche pas à trier peut passer devant sans le voir : c'est
  le prix du respect strict de la No-Line Rule et de la règle d'ombre.
- **La deuxième ligne de libellé.** Le patron *list item* une ligne tronque. À
  320 pt, DE et PT sont coupés — visible dans la dernière colonne de la maquette.
  C'est un abandon assumé, pas un oubli : deux lignes dans une pastille au rayon
  `full` cassent la forme du contrôle.
- **L'ambre comme accent de valeur.** Il n'en reste qu'un glyphe décoratif à
  faible contraste ; le sens est porté par le libellé et par le chiffre gris.

---

## B — « Encart callout ambre »

**Coque** : fond `rgba(255, 203, 5, 0.05)` (primaire à 5 %), barre verticale de
`Spacing.xs` (4) en `Colors.primary` collée au bord de tête, `BorderRadius.xl`,
marges `Spacing.md`, aucun filet de carte, aucune ombre.
**Contenu** : `albums-outline` 22 px en `textMain` · libellé 16 px / 600 sur
**deux lignes maximum** · compteur en **Metadata Chip** (`surface`, rayon full,
filet `outlineVariant` à l'échelle du chip, 13 px / 700 `textMain`) ·
`chevron-forward` 20 px en `textMuted`.

### Règles du système citées

- « **Signature Textures** : Use a **5% opacity tint of the Primary color**
  (Amber) for callouts and blockquotes to create a "highlighted" tactile feel » —
  B est ce callout.
- « **Callout Aside** : A **vertical 4px bar using the Primary color**, paired
  with a **5% primary background**. This creates an editorial "pull quote"
  effect » — B reprend le composant du système tel qu'il est spécifié, sans en
  inventer la géométrie.
- « **Metadata Chips** : Pill-shaped (`rounded-full`) with a `surface` fill and a
  very subtle `outline-variant` (5% black) » — le compteur est ce chip.
- « The Amber primary is used **sparingly for high-value interactions** … and
  meaningful accents » — c'est la règle que B met le plus sous tension : voir
  « ce qu'elle abandonne ».

### Implémentations de référence

1. **Material Design, *banner*** — « A banner displays a prominent message and
   related optional actions », placé **sous la barre supérieure, au-dessus du
   contenu**, et persistant jusqu'à ce que le message soit résolu. C'est
   exactement le rôle de l'encart : un message qui s'efface de lui-même quand
   l'arriéré tombe à 0. Le spec de référence est celui de Material 2 — Material 3
   n'a pas repris le composant, ce qui est aussi la limite de cette référence, et
   il faut le dire.
2. **`MinutesWarningBanner`, dans ce dépôt** (`mobile/src/components/`) — la
   preuve que la place du bandeau existe déjà sur l'accueil et qu'elle y est
   rendue **sans filet ni ombre**, en simple bloc tonal, à la même largeur et
   avec le même `HOME_BLOCK_GAP`. B ne crée pas un type de bloc nouveau sur cet
   écran ; il l'utilise pour autre chose que le quota.
3. **Todoist, projet « Inbox »** — la boîte par défaut de tout ce qui est capturé
   sans projet, présentée en **destination permanente nommée, avec son compteur**,
   et non en simple raccourci. Même statut que la collection par défaut ici.
4. **Readwise Reader, découpe Feed / Inbox / Later / Archive** — l'« Inbox » y est
   la destination nommée du non trié, et le tri est un geste de première classe
   dans le produit, pas une option de réglage.

### L'icône : `albums-outline`

Identifiant exact : **`albums-outline`**.

- Ce que le glyphe dessine : trois rectangles arrondis empilés — **une pile de
  cartes**.
- Pourquoi ce glyphe ici : l'écran de revue (`mobile/app/media/unsorted-review.tsx`)
  présente les médias **une carte à la fois**, avec une position « n / total ».
  Le glyphe annonce donc littéralement la forme de ce qui suit l'appui.
- Pourquoi préférable à `file-tray-outline` : mêmes trois raisons que pour A —
  pile plutôt que récipient, pas de collision avec le glyphe de l'onglet où l'on
  se trouve, pas de métaphore de mobilier de bureau.
- **Collision à déclarer** : `albums-outline` est déjà employé une fois, comme
  glyphe de l'état « bibliothèque vide » (`mobile/app/(tabs)/search.tsx:1034`).
  Les deux emplois ne se croisent jamais sur un même écran, mais le glyphe
  voudrait alors dire « rien ici » d'un côté et « une pile ici » de l'autre.
  C'est un défaut réel de cette variante ; A n'en a pas.

### Ce qu'elle abandonne

- **La carte blanche.** L'encart ne ressemble plus aux cartes de médias de
  l'app ; il ressemble à un bandeau. Sur un écran dont tout le reste est en
  cartes, c'est une rupture de famille.
- **L'ambre comme signal d'action.** C'est l'abandon le plus coûteux, et il est
  frontal avec la règle citée plus haut : ici la couleur de marque annonce un
  **arriéré à traiter**. Si l'ambre veut dire à la fois « appuie ici » (les
  boutons flottants, l'état actif) et « tu as du retard », il ne discrimine plus
  rien.
- **La discrétion de la disparition.** À 0 l'encart s'efface : c'est une bande
  colorée qui disparaît d'un coup, un saut visuel plus grand que celui d'une
  ligne tonale.

---

## C — « Compteur en display »

**Coque** : carte `Colors.surface`, `BorderRadius.xl`, `padding: Spacing.md`,
marges `Spacing.md`, aucun filet, **`Shadows.soft` conservée**.
**Contenu**, sur deux lignes : pastille 40 (= `Spacing.lg + Spacing.md`), rayon
`BorderRadius.lg`, fond primaire à **5 %**, avec `checkmark-done-outline` 22 px en
`textMain` ; en regard, le compteur en **`Typography.display`** (32 px / 700 /
-0,5) en `textMain` ; en seconde ligne le libellé 16 px / 600 sur deux lignes
maximum et `arrow-forward` 20 px en `Colors.primary`.

### Règles du système citées

- « **Scale Ground Truth** : **Display/H1 : 32px (Bold, Tracking Tight) —
  Reserved for major entry points** » — le compteur passe en display parce que
  l'encart *est* un point d'entrée majeur, et parce que le chiffre est la seule
  donnée de l'encart.
- « The layout breaks the rigid "template" look by using **intentional
  typographic scale shifts** » — le saut 32 / 16 entre le chiffre et le libellé
  est ce mécanisme, pas un effet.
- « **Signature Textures** : … 5% opacity tint » — la pastille est exactement à
  5 %, la seule des trois variantes à conserver une pastille et à la conformer.
- « Only the top bar and **primary interactive containers** should utilize the
  `soft` shadow » — la variante revendique ce statut pour l'encart. Voir
  l'arbitrage plus haut.
- « **Don't** use pure black for text ; use the `text-main` (`#2b2d42`) » — le
  chiffre de 32 px est en `textMain`, pas en noir.

### Implémentations de référence

1. **Rappels sur iOS, tuiles de listes intelligentes** (iOS 14 et suivants) —
   chaque tuile porte **un glyphe dans un cercle teinté** en haut à gauche, **le
   compteur en gros chiffre** en regard, et le nom de la liste en dessous. C'est
   la référence directe de la géométrie de C : le nombre est le héros, le libellé
   est le support, le glyphe colore la catégorie.
2. **Material 3, *badge*** — le grand badge est plafonné à environ **quatre
   caractères** et le spec prescrit d'abréger au-delà (`999+`). C'est la raison
   documentée de **sortir le nombre du badge** : le compteur de l'accueil est
   `media_count` de la collection par défaut, sans plafond côté client, donc un
   badge y est structurellement à l'étroit. La maquette montre 1042 dans les
   trois variantes pour cette raison.
3. **Material 3, *elevated card*** — la famille de cartes que M3 réserve à ce qui
   doit se lire comme surélevé, par opposition à la *filled card* « avec moins
   d'emphase ». C est l'*elevated*, A la *filled*.
4. **`arrow-forward` dans ce dépôt** — l'app emploie déjà ce glyphe une fois pour
   « on avance » (`mobile/app/artifacts/[artifactId].tsx:867`), là où
   `chevron-forward` sert dix fois pour « on entre dans une ligne ». C n'invente
   pas une affordance, elle emprunte l'autre déjà présente.

### L'icône : `checkmark-done-outline`

Identifiant exact : **`checkmark-done-outline`**.

- Ce que le glyphe dessine : deux coches superposées.
- Pourquoi ce glyphe ici : C ne raconte pas un lieu, elle raconte une **tâche à
  ramener à zéro** — le chiffre est le sujet de la carte. La double coche est le
  glyphe de la file vidée.
- Pourquoi préférable à `file-tray-outline` : il dit **l'action** au lieu de
  nommer un contenant, il n'entre en collision avec rien (`checkmark-done`
  n'apparaît nulle part dans `mobile/app` ni `mobile/src`), et il n'emprunte
  aucune métaphore de mobilier.
- **Risque à déclarer** : dans les messageries, la double coche signifie « lu ».
  Sur une carte qui invite à commencer, elle peut se lire « déjà fait ». C'est le
  défaut propre de cette variante, et c'est aussi la seule des trois dont
  l'icône ne dit rien de **ce qui** attend.

### Ce qu'elle abandonne

- **La compacité.** ≈ 108 de haut sur une ligne de libellé et ≈ 128 sur deux,
  contre ≈ 80 aujourd'hui et 56 pour A, en tête de l'accueil, c'est-à-dire à
  l'endroit le plus cher de l'app. Le rythme entre blocs ne change pas, mais la
  première rangée de tuiles descend d'autant.
- **La grammaire du chevron.** L'app dit « on entre ici » avec `chevron-forward`
  partout ailleurs (dix sites d'appel) ; C emploie une flèche.
- **La neutralité du ton.** 128 en 32 px, c'est un reproche. La variante
  dramatise l'arriéré : c'est ce qui la rend lisible d'un coup d'œil et ce qui la
  rend inconfortable quand l'arriéré est gros.

---

## Récapitulatif des icônes

Bibliothèque : **Ionicons**, via `@expo/vector-icons` — la langue d'icônes de
l'app partout ailleurs. Aucune variante n'en sort, donc aucune n'a à le
justifier.

| Variante | Identifiant exact | Ce que le glyphe dessine | Collision dans l'app | Ce qui le rend préférable à `file-tray-outline` |
|---|---|---|---|---|
| A | `layers-outline` | Trois plaques empilées, en perspective | **Aucune** (`layers` : 0 occurrence dans `mobile/app` et `mobile/src`) | Dessine la quantité en attente, pas un récipient ; aucune collision ; aucun objet physique évoqué |
| B | `albums-outline` | Trois rectangles arrondis empilés — une pile de cartes | **Une** : état « bibliothèque vide », `mobile/app/(tabs)/search.tsx:1034` | Annonce la forme de l'écran de revue (une carte à la fois) ; pas le glyphe de l'onglet courant |
| C | `checkmark-done-outline` | Deux coches superposées | **Aucune** (`checkmark-done` : 0 occurrence) | Dit l'action (ramener la file à zéro) plutôt qu'un contenant ; risque « lu » à déclarer |
| — (actuel) | `file-tray-outline` | Un bac à courrier en papier | **Trois autres sens** : onglet Accueil (`_layout.tsx:98`), état vide de collection (`collections/[id].tsx:800`), ligne « Non classés » du sélecteur (`CollectionPickerView.tsx:297`) | — |

Le reproche fait à `file-tray-outline` tient donc en trois faits, aucun affaire
de goût : **il est déjà l'icône de l'onglet où l'encart se trouve**, donc il
n'informe pas ; **il porte quatre emplois pour trois sens** dans l'app, donc il ne
distingue pas ; **il représente un meuble de bureau** que le produit ne manipule
pas, là où les trois glyphes proposés représentent soit la quantité, soit
l'action.

## Cas limites rendus dans la maquette

Chaque variante est rendue dans six états, tous côte à côte :

| Cellule | Ce qu'elle éprouve |
|---|---|
| FR · 3 | Compteur à un chiffre |
| FR · 128 | Compteur à trois chiffres |
| DE « Unsortiertes durchgehen » · 128 | Le libellé le plus long des catalogues, avec trois chiffres |
| PT « Revisão dos não organizados » · 9 | Le second libellé long, avec des diacritiques, et un chiffre |
| FR · 1042 | Le compteur n'est pas plafonné : c'est `media_count` de la collection par défaut, sans clamp côté client (`inbox.tsx`, `buildCollectionTree(...).defaultCollection?.media_count ?? 0`) |
| DE · 128 à **320 pt** | Display Zoom, la largeur la plus étroite visée — c'est là que A tronque |

Les en-têtes de section des cadres DE et PT portent les vrais libellés des
catalogues (`home.recentlyAdded` : « Kürzlich hinzugefügt », « Adicionados
recentemente »), pour que la largeur restante soit celle du vrai écran.

## Notes pour l'implémentation (pas des critères de cette tâche)

1. `backgroundColor: "rgba(255, 203, 5, 0.1)"` doit devenir un token nommé dans
   `theme.ts`, quelle que soit la variante retenue — et à 5 % si c'est C.
2. La pastille de 40 est un nombre magique dans le code actuel ; l'exprimer
   comme `Spacing.lg + Spacing.md` (ce que fait la maquette) ou lui donner un
   token.
3. `home.unsortedReview` doit passer à « Revue des non classés » dans
   `mobile/src/i18n/fr.ts` ; les dix autres catalogues restent tels quels.
4. Le libellé d'accessibilité (`home.unsortedReviewA11y` + `common.itemCount`) et
   la cible unique (la carte entière) sont à conserver à l'identique.
5. Si A est retenue, le libellé passe à `numberOfLines={1}` : c'est un changement
   de comportement par rapport aux deux lignes actuelles, à faire explicitement.

## Choix de l'owner

À remplir par l'owner après lecture de `code.html` ; c'est ce que lira la tâche
d'implémentation.

- **Variante retenue** : _(A / B / C, ou « un tour de plus » avec les consignes)_
- **Date** :
- **Écarts demandés par rapport à la variante** :
