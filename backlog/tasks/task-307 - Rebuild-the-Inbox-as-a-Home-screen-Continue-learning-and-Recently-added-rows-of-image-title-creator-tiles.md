---
id: task-307
title: >-
  Rebuild the Inbox as a Home screen: Continue learning and Recently added rows
  of image/title/creator tiles
status: Done
assignee: []
created_date: '2026-08-20 16:18'
updated_date: '2026-08-21 01:10'
labels:
  - mobile
  - ui
  - phase-6
dependencies:
  - task-304
  - task-305
  - task-306
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rework the Inbox into the home screen of the owner's reference screenshot: a greeting, the Daily Digest entry point, then two **horizontally scrollable** rows of large tiles — **Continue learning** and **Recently added** — and nothing else. The vertical list of every media item leaves this screen for good; task-306 has already moved it to the Search tab, so it is not lost.

## What the screen becomes

**Header.** The greeting stays (`getGreeting` in `mobile/app/(tabs)/inbox.tsx:474`; Maestro asserts `Good .*` twice in `03_inbox_visibility.yaml`), and so does the `MinutesWarningBanner` slot. The `Free Trial - 3 days left` pill the screenshot shows **already exists**: task-301 shipped it as `FreeTrialNotice` (`mobile/src/components/FreeTrialNotice.tsx`, testID `free-trial-notice`), rendered in today's `ListHeader` at `inbox.tsx:294` just above `MinutesWarningBanner`. You are rebuilding that header around both of them — keep the two components, their order, their ids and their own top margins. Neither is yours to restyle.

**Daily Digest card.** Keep the existing card and add the count the screenshot shows on its right, from `DigestService.getDailyDigest()` → `stats.media_count` (`mobile/src/types/digest.ts`). Render nothing rather than a zero, a dash or a spinner, and a failed digest fetch must leave the card working as a plain entry point.

**Row 1 — Continue learning.** The media items and collections the user last engaged with, read from whatever task-305 exposes, in the order that endpoint returns. When it is empty — a brand-new account, or before the first engagement is recorded — the whole section is absent: no heading, no empty box, no placeholder tiles.

**Row 2 — Recently added.** The most recently saved media and the most recently created collections, merged into one row ordered newest-first: media from `MediaService.listMedia()` (already `saved_at` DESC server-side), collections from `OrganizationService.getUserCollections()`, whose `created_at` is what orders them. Cap the row and state the cap in the code.

**Optimistic share items land here.** `useMediaPolling().pendingLocalItems` currently renders as placeholder cards in the vertical list; with that list gone, they belong at the head of Recently added, still showing the shared URL while the backend catches up. This is what keeps a share visible on return from the confirmation screen — and what keeps `03_inbox_visibility.yaml`'s post-share `youtube.com` assertion meaningful.

**The tile.** One shared component for both rows: a large cover image, the title on up to three lines, the creator on one muted line — `media_image` and `creator_name`, both delivered by task-304 and already declared in `mobile/src/types/media.ts`. Render the image with **`expo-image`**, which that task installed (`~55.0.11`, already registered in `app.config.ts:160`) precisely for this screen and which nothing reads yet: `docs/research/task-302-media-cover-and-creator/README.md` §6 specifies the source shape, the `cachePolicy`/`recyclingKey` props a recycled row needs, and the **16:9** tile ratio it assumes. No image available: the media-type icon on `Colors.surfaceContainerLow`, never an empty grey square — the README names the always-null grey box at `digest.tsx:306` as the anti-pattern. A collection tile has no image of its own: use a mosaic of up to four member covers, and when there are none, an accent surface carrying the name and the item count. A media tile opens `/media/<id>`, a collection tile opens `/media/collections/<id>`.

**Section headings.** Replace the uppercase muted `YOUR MEDIA` style with the screenshot's shape: Title Case, an icon in the primary tint, one heading per row. Use Ionicons rather than emoji — Ionicons is the app's icon language everywhere else.

## What gets deleted

The vertical `FlatList` over `unifiedItems`, `UnifiedItemCard`, `BackendItemCard`, `LocalItemCard`, the `YOUR MEDIA` header and, if the tile carries no type badge, the `getMediaTypeLabel` / `getMediaTypeBgColor` helpers and the styles that only served them. Nothing unused stays behind (`AGENTS.md`, "Nothing is deployed yet").

## What must not change

- The two floating controls and their ids: `inbox-camera-button`, `inbox-add-button`, and the `AddSourceSheet` they open. Ingestion behaviour is untouched.
- The `inbox-screen` testID — `utils/login.yaml`, `01_login.yaml` and `utils/ensure_logged_out.yaml` all wait on it.
- Pull-to-refresh, and the refetch-on-focus that also refreshes entitlements (`inbox.tsx:84-89`).

## Constraints

- **Each section fails alone.** Three data sources now feed this screen; one failing must not blank the others, and only the very first load may show a full-screen spinner. No section may leave the screen in a permanent loading state.
- **`03_inbox_visibility.yaml` must be updated in this task** — it asserts `YOUR MEDIA` and expects a domain string in a card. Update its assertions to the new sections and keep the post-share check resolvable through the pending tile. Its wiring is readable in the YAML; do not claim anything about a run.
- Amber Clarity tokens only (`mobile/src/constants/theme.ts`), 48 px minimum touch targets, an `accessibilityLabel` per tile, and a `testID` on each row so a flow can assert it.
- No automated tests unless the owner asks. `cd mobile && npm run typecheck && npm run lint` clean.

## Owner notes (not acceptance criteria)

- **task-301 landed first** (merged 2026-08-20), so the cheaper ordering is gone: its free-trial pill sits in the header this task rebuilds. That is a fact for the implementer, not a conflict to resolve — the pill and the minutes banner move into the new header unchanged. Nothing else in this task changed as a result.
- Only a simulator can judge tile width, image aspect ratio and how many tiles peek at the right edge to signal that the row scrolls. The implementer will put the tile's style block and the layout constants in the Implementation Notes so you can read the numbers without building.
- The collection mosaic is the one piece with no reference in the screenshot; it is worth a look before it ships.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Inbox renders a greeting, the Daily Digest card, then a horizontally scrollable 'Continue learning' row and a horizontally scrollable 'Recently added' row, and no vertical list of media items remains on the screen
- [x] #2 Continue learning is fed by the read path task-305 exposes, keeps that order, and the entire section including its heading is absent when the list is empty
- [x] #3 Recently added merges the most recently saved media and the most recently created collections into one newest-first row, capped at a limit stated in the code
- [x] #4 Pending local share items appear at the head of Recently added showing the shared URL, so a share is visible on return from the confirmation screen
- [x] #5 One shared tile component renders both rows with a large cover image, a title on up to three lines and the creator on one muted line, reading media_image and creator_name through expo-image with the props and ratio the task-302 README specifies
- [x] #6 A tile with no available image falls back to the media-type icon on a theme surface, and a collection tile renders a mosaic of up to four member covers or an accent surface with its name and item count
- [x] #7 A media tile opens /media/<id> and a collection tile opens /media/collections/<id>
- [x] #8 The Daily Digest card shows the daily digest count and renders no badge at all when the figure is unavailable, with a failed digest fetch leaving the card usable
- [x] #9 Each of the three data sources fails independently: one error never blanks the other sections, and no section can be left permanently loading — only the first load may show a full-screen spinner
- [x] #10 The vertical list and its now-unused parts are deleted — UnifiedItemCard, BackendItemCard, LocalItemCard, the YOUR MEDIA header and any helper or style left with no reader
- [x] #11 inbox-screen, inbox-camera-button, inbox-add-button and the AddSourceSheet behaviour are unchanged, and pull-to-refresh plus refetch-on-focus with entitlement refresh still work
- [x] #12 mobile/.maestro/03_inbox_visibility.yaml no longer asserts YOUR MEDIA, asserts the two new sections instead, and its post-share assertion resolves against the pending tile
- [x] #13 FreeTrialNotice (testID free-trial-notice) and MinutesWarningBanner both still render in the new header, in that order and without overlap, neither restyled
- [x] #14 Each row carries a testID, each tile an accessibilityLabel, touch targets stay at 48 px minimum, only theme.ts tokens are used, and cd mobile && npm run typecheck && npm run lint are clean
<!-- AC:END -->


## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
### Ce qui a été écrit

- `mobile/src/components/HomeTile.tsx` (nouveau) — la tuile partagée des deux rangées, plus la mosaïque de collection.
- `mobile/src/hooks/useHomeSections.ts` (nouveau) — les deux sources que l'écran possède en propre (engagements, collections) et le compteur du digest.
- `mobile/app/(tabs)/inbox.tsx` — réécrit : `ScrollView` + deux `FlatList` horizontales à la place de la `FlatList` verticale.
- `mobile/.maestro/03_inbox_visibility.yaml` — assertions mises à jour.

### Constantes de layout (à lire sans builder — cf. note owner)

```
TILE_WIDTH        = 200      // HomeTile.tsx
TILE_COVER_HEIGHT = 113      // 200 x 113 = 16:9 à un demi-point près
TILE_GAP          = Spacing.md (16)
rowContent        = { paddingHorizontal: Spacing.md (16), gap: 16 }
titre             = Typography.label, fontSize 15, lineHeight 20, numberOfLines 3
sous-titre        = Typography.small, Colors.textSubtle, numberOfLines 1
RECENTLY_ADDED_LIMIT   = 12
MAX_COLLECTION_PREVIEWS = 4
```

Ce que ces nombres donnent au bord droit : la tuile 1 occupe [16, 216], la tuile 2 démarre à 232. Sur l'écran le plus étroit visé (375 pt) il en reste ~143 pt de visible, ~158 pt sur 390 pt — coupée dans les deux cas, jamais affleurante. C'est le seul signal qui dit à l'utilisateur que la rangée défile, d'où le choix de 200 plutôt que 176 (qui laissait la deuxième tuile entièrement visible sur 390 pt).

### Décisions à connaître

**La mosaïque de « Recently added » ne coûte aucune requête.** L'API des engagements livre `preview_images` pour « Continue learning », mais `GET /api/folders` ne renvoie pas de couvertures. Plutôt qu'une requête par collection, les couvertures sont indexées en une passe sur la liste média déjà en main (`indexCoversByCollection`), par `folder_id`. C'est du best-effort assumé : une collection dont aucun membre n'est dans la page courante retombe sur la surface accent, qui est un état conçu, pas un état dégradé.

**Clé de cache des images.** Les tuiles média de « Recently added » utilisent `${media_item_id}:${updated_at}`, la forme exacte du §6.2 du README task-302. Les tuiles issues des engagements n'ont pas d'`updated_at` dans leur payload et `engaged_at` changerait à chaque engagement — donc l'`id` seul, qui est l'identité stable disponible. Les vignettes de mosaïque, elles, sont signées : leur clé est l'URL amputée de sa query string, ce qui survit à la rotation de signature tout en changeant quand l'objet change.

**Le sentinel de la rangée vide.** « Continue learning » disparaît en entier quand la liste est vide (AC #2). « Recently added » disparaît de même quand il n'y a rien du tout, et l'`EmptyState` d'origine (« Your shared media will appear here. ») reprend la main — il n'était pas dans la liste des suppressions de l'AC #10 et c'est la seule affordance d'onboarding de l'écran.

**Indépendance des sources (AC #9).** `useHomeSections` émet ses trois appels en `Promise.allSettled` : un rejet laisse les deux autres utilisables, et un refresh qui échoue conserve la valeur précédente plutôt que de vider la section. Aucune des trois n'expose de flag de chargement — une rangée sans contenu est absente, ce qui rend un spinner de section inutile par construction. Le seul spinner plein écran reste celui du premier `fetch` média, inchangé.

**Le `setState` différé d'un tick** dans `useHomeSections` reprend la forme de `useMediaPolling` : la règle `react-hooks/set-state-in-effect` est active dans ce dépôt et refuse un `setState` atteint synchroniquement depuis un effet.

### Deux points pour la relecture owner

1. **La collection sans couverture affiche son nom deux fois** — une fois sur le bloc accent (l'AC #6 demande « an accent surface with its name and item count ») et une fois sur la ligne de titre de la tuile, juste en dessous, puisque le composant est partagé avec les tuiles média. L'AC est satisfaite littéralement ; si la redondance déplaît au simulateur, retirer le `accentName` de `HomeTile.tsx` suffit. C'est exactement la pièce que la note owner signalait comme sans référence dans le screenshot.
2. **Une couleur littérale subsiste sur cet écran** : `digestIconContainer` porte `"rgba(255, 203, 5, 0.1)"`. C'est du code d'origine, sur la carte que la tâche demandait explicitement de garder telle quelle en n'y ajoutant que le compteur ; `theme.ts` n'expose pas de token « primary à 10 % » et l'exprimer via `opacity` délaverait aussi l'icône. Tout le code neuf (tuile, rangées, badge) n'utilise que des tokens.

### Suppressions (AC #10)

`UnifiedItemCard`, `BackendItemCard`, `LocalItemCard`, le type `UnifiedItem`, le `ListHeader` et son en-tête `YOUR MEDIA`, la `FlatList` verticale, ainsi que `getMediaTypeLabel`, `getMediaTypeBgColor`, `getRelativeTime` et les styles de carte (`card`, `cardContent`, `thumbnailContainer`, `typeBadge`, `cardMeta`, `timeText`, `cardDomain`, `errorMessage`, `cardFailed`…) — plus aucune tuile ne porte de badge de type ni d'horodatage. `grep -rn "UnifiedItemCard\|BackendItemCard\|LocalItemCard\|UnifiedItem"` sur `mobile/` ne renvoie rien. Les copies de `getMediaTypeLabel` / `getMediaTypeBgColor` qui subsistent dans `MediaListCard.tsx` sont lues par l'onglet Search et ne sont pas concernées. Le type local `PendingShare` que j'avais introduit a été remplacé par l'`InboxItem` existant plutôt que de créer un jumeau.

### Maestro (AC #12)

`03_inbox_visibility.yaml` n'assère plus `YOUR MEDIA` ni le badge `VIDEO` (les tuiles n'en portent plus). Il assère « Continue learning » en `optional` — un compte de test fraîchement créé n'a engagé avec rien, la rangée est donc légitimement absente — et « Recently added » en `optional` avant le partage, puis en assertion ferme après, car la tuile optimiste la fait exister à coup sûr. L'assertion post-partage `youtube.com` se résout sur cette même tuile, dont le titre est l'URL partagée. Rien n'est affirmé ici sur un *run* : seul le câblage du YAML est vérifiable depuis le worktree.

Egalement mis à jour : `docs/V1_LAUNCH_PLAN.md` citait `YOUR MEDIA` comme exemple de sélecteur Maestro fragile — l'exemple est devenu littéralement vrai, il est remplacé par les nouveaux sélecteurs avec la date de péremption de l'ancien.

### Vérifications

`cd mobile && npm run typecheck` puis `npm run lint` : 0 erreur. Les deux warnings restants (`digest.tsx` `CARD_WIDTH` inutilisé, `purchaseService.ts` `any`) préexistent dans des fichiers que cette tâche ne touche pas.

### Note owner (hors AC)

Seul un simulateur peut juger la largeur de tuile, le cadrage 16:9 et la profondeur du peek au bord droit. Les constantes sont ci-dessus pour être lues sans build ; les deux points de relecture listés plus haut sont ceux qui méritent un coup d'œil avant de ficher l'écran.
<!-- SECTION:NOTES:END -->
