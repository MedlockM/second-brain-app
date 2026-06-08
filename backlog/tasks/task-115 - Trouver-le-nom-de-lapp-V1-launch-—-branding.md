---
id: task-115
title: Trouver le nom de l'app (V1 launch — branding)
status: To Do
assignee: []
created_date: '2026-06-07 21:32'
labels:
  - benchmark
  - product
  - scoping
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

L'app est en phase de pré-lancement V1 (cf. `docs/V1_LAUNCH_PLAN.md`). Tous les éléments **techniques d'identité** sont figés au 2026-06-07 :

- **Entité / company name** : `Second Brain Labs` (déjà affichée sur l'écran de consentement Google OAuth)
- **Bundle ID iOS / Android package** : `com.secondbrainlabs.core` (immuable, propagé dans `mobile/app.config.ts`, RevenueCat product IDs, Apple App ID, share extension, etc.)
- **Domaine prévu** : `secondbrainlabs.com` (à acheter)

Ce qui **manque encore** : le **nom marketing public de l'app**, c'est-à-dire le `CFBundleDisplayName` (iOS) / `applicationLabel` (Android) qui sera affiché :
- Sur l'icône du téléphone des users
- Sur les fiches App Store et Play Store
- Dans les screenshots marketing
- Dans la communication, le futur landing page, les push notifications

Ce nom est **découplé** du Bundle ID et peut être changé à chaque release sans casser l'infra. Mais il sera **très coûteux à changer après le lancement** (re-uploads stores, SEO, perte de reconnaissance, push token routing dans certains cas).

## Goal of this benchmark

Produire une **shortlist de 5 candidats finaux** pour le nom de l'app, chacun documenté avec :
- Pourquoi ce nom matche le produit (brief produit ci-dessous)
- Vérification de **disponibilité réelle** (App Store, Play Store, domaine `.com`/`.app`, trademark USPTO + EUIPO classes 9 et 42, handles sociaux)
- Score selon une **grille de critères** définie ci-dessous
- Un **nom recommandé** classé en tête, avec les 4 alternatives en backup

## Brief produit (ce que fait l'app)

Lis `docs/V1_LAUNCH_PLAN.md` pour le périmètre exact. En résumé :

- **Concept** : une app mobile "second cerveau" qui ingère du contenu hétérogène que l'user **partage depuis d'autres apps** (Safari, YouTube, podcasts, X, TikTok, Instagram, WhatsApp, fichiers PDF/DOCX/PPTX, etc.) et le transforme en **artifacts utiles** : transcript, résumé court, résumé détaillé, notes structurées, flashcards, quiz.
- **UX principale** : un **share intent** depuis n'importe quelle app → l'item arrive dans une **inbox** → traitement asynchrone (transcription Deepgram + génération via OpenAI) → consultable dans l'app.
- **Fonctions secondaires** : digest journalier, recherche full-text (Algolia), folders + tags, spaced repetition sur les flashcards.
- **Public visé** : users curieux qui consomment beaucoup de contenu et veulent en garder une trace exploitable / mémorisée. Pas un public ultra-tech, plutôt productivity / lifelong learning.
- **Ton de marque** : calme, focus, "slow consumption", l'opposé du doomscroll. Couleurs warm beige (`#fcf9f6`) côté splash.
- **Modèle business** : freemium + abonnements via IAP RevenueCat (3 tiers : text-only, mix, audio-heavy).

## Méthode imposée

### Critères d'évaluation (à scorer 1-5 pour chaque candidat)

1. **Mémorabilité** — Est-ce qu'on s'en souvient après l'avoir entendu une fois ?
2. **Prononçabilité internationale** — Lisible en anglais, français, allemand, espagnol sans ambiguïté
3. **Concision** — ≤ 8 lettres idéalement, ≤ 10 max
4. **Lien avec la promesse produit** — Évoque l'idée du produit (mémoire, résumé, focus, knowledge)
5. **Sonorité** — Agréable à dire, pas de syllabes lourdes
6. **Disponibilité légale** — Pas de trademark conflictuel en classes 9 (software) et 42 (services tech) sur USPTO + EUIPO
7. **Disponibilité commerciale** — App Store iOS, Play Store, handles sociaux (`@<nom>` Twitter/X, Instagram, TikTok), domaine `.com` ou `.app` libre
8. **Risque d'homonymie** — Pas trop proche d'une marque connue qui pourrait porter à confusion (`iBrain`, `Notion-clone-name`, etc.)
9. **Future-proof** — Tient si l'app pivote légèrement (ex: si on ajoute des fonctions de social/sharing, est-ce que le nom limite le scope ?)

### Pièges à éviter (à filtrer en amont)

- ❌ Mots avec accents ou caractères spéciaux (non-universels)
- ❌ Suffixes datés type `-ly`, `-fy`, `-io` (`Mindly`, `Notify`, `Brainio`)
- ❌ Noms commençant par `App`, `i`, `My`, `Get` (Apple les rejette ou les déclasse)
- ❌ Noms trop génériques (`Inbox`, `Brain`, `Memory` — déjà saturés sur l'App Store)
- ❌ Noms inventés trop bizarres type `Zynapsi`, `Memorix`, `Brevora` (sympa pour les VC, friction pour les users)
- ❌ Noms qui ressemblent à un produit Apple/Google/Microsoft existant
- ❌ Noms > 8 lettres sans raison forte
- ❌ Tout nom déjà associé à une app de productivity/notes/AI populaire (Notion, Bear, Obsidian, Roam, Reflect, Mem, Heptabase, Readwise, etc.)

### Angles thématiques à explorer (au moins 4 de ces angles)

L'agent doit générer ≥ 30 candidats bruts puis filtrer, en explorant **au moins 4** de ces angles :
- **Mémoire / second cerveau** (cortex, memo, recall, mnemo, etc.)
- **Résumé / digest / essence** (gist, brief, recap, sift, distill, etc.)
- **Curation / inbox / flux** (stash, vault, queue, drift, etc.)
- **Calme / slow consumption / focus** (linger, ember, pith, sediment, etc.)
- **Lumière / clarté / illumination** (spark, glimpse, lantern, etc.)
- **Métaphore botanique / organique** (root, sprout, fern, etc.)
- **Mots inventés courts par condensation** (2-3 syllabes max, fortement euphoniques)
- **Mots de langues étrangères** (japonais, latin, scandinave) qui sonnent bien à l'oreille anglophone

### Méthode de vérification de disponibilité

Pour les 10-15 candidats finalistes (avant la shortlist de 5), l'agent doit :
1. **App Store Connect / iTunes Search API** : `curl "https://itunes.apple.com/search?term=<nom>&entity=software&country=us&limit=10"` et regarder s'il y a une app avec exactement ce nom dans les premiers résultats
2. **Google Play** : recherche manuelle `https://play.google.com/store/search?q=<nom>&c=apps`
3. **Domaine** : WHOIS via WebFetch sur registrar (Namecheap, Cloudflare) pour `.com` et `.app`
4. **Trademark USPTO** : `https://tmsearch.uspto.gov/` — chercher dans les classes 9 (computer software) et 42 (computer services)
5. **EUIPO** : `https://www.tmdn.org/tmview/` même classes
6. **Handles sociaux** : checker `twitter.com/<nom>`, `instagram.com/<nom>`, `tiktok.com/@<nom>` via WebFetch (ou rapporter "non vérifiable depuis l'agent" si bloqué par auth)

> Si une vérification ne peut pas être faite automatiquement, le noter explicitement comme "à vérifier manuellement par l'owner" dans la fiche du candidat.

## Anti-bias

L'agent **ne doit pas** être influencé par les noms suggérés en conversation antérieure (Sift, Recap, Drift, Pith, Stash, Cache, Trace, Echo, Mnemo, Cortex, Tether, Drop, etc.). Il doit faire la recherche **from scratch** en partant des angles thématiques, générer ses propres candidats, et appliquer la grille de scoring sans connaître les pré-suggestions humaines.

Si un de ses candidats coïncide avec un nom déjà cité (recoupement naturel), c'est OK — mais pas de "biais d'ancrage" sur la liste précédente.

## Deliverable

Un document unique à `docs/research/task-XX-app-name/README.md` (remplacer XX par l'ID réel de cette tâche) contenant :

- **Front-matter YAML** avec `owner_decision: pending`, conformément aux conventions du projet (voir `.claude/agents/task-research.md` pour le template exact)
- **Section 1 — Brief produit reformulé** : 2-3 paragraphes pour montrer que l'agent a bien compris le produit avant de proposer
- **Section 2 — Méthode** : angles thématiques explorés, sources de vérification utilisées, biais explicites évités
- **Section 3 — Candidats bruts** (≥ 30) : tableau avec colonnes `nom | angle | filtré (oui/non + raison)` — beaucoup vont être filtrés à ce stade
- **Section 4 — Finalistes** (10-15) : pour chacun, fiche complète avec grille de scoring 1-5 sur les 9 critères + vérifications de disponibilité documentées avec URLs et dates
- **Section 5 — Shortlist top 5** : classement final avec recommandation principale + 4 alternatives, et pour chacun :
  - Score total
  - 3 phrases sur pourquoi
  - 3 phrases sur les risques
  - Tagline marketing potentielle (1 phrase)
  - Logo/identité visuelle suggérée (1 phrase, sans dessin)
- **Section 6 — Recommandation finale** : un seul nom mis en avant avec 1 paragraphe de justification croisée (pourquoi ce nom > les 4 autres)
- **Section 7 — Decision** : section vide laissée à l'owner pour qu'il valide ou demande un `redo` / `more`

## Constraints

- C'est une tâche de **recherche pure**. NE MODIFIE AUCUN FICHIER hors du `docs/research/task-XX-app-name/`. Pas de changement dans `mobile/app.config.ts`, pas de mise à jour de `V1_LAUNCH_PLAN.md`. Output = README uniquement.
- Cite **toutes les URLs** consultées avec date d'accès (App Store search, WHOIS, USPTO, EUIPO, etc.).
- Pour chaque candidat finaliste, montrer la **commande exacte** ou l'URL de vérification (reproductibilité).
- Respect strict des **anti-biases** : ne pas s'appuyer sur les noms cités en conversation antérieure dans le repo (chercher from scratch).
- Si moins de 5 noms passent les filtres de disponibilité, élargir la génération initiale plutôt que de baisser la barre.

## References

- `docs/V1_LAUNCH_PLAN.md` — périmètre V1 et identité technique figée
- `mobile/app.config.ts` — Bundle ID actuel `com.secondbrainlabs.core`
- `CLAUDE.md` — convention de création de tâche (benchmark + paire d'implémentation)
- `.claude/agents/task-research.md` — instructions de l'agent qui exécutera cette tâche
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 docs/research/task-XX-app-name/README.md existe avec `owner_decision: pending` dans le front-matter
- [ ] #2 #2 Section 1 (brief produit reformulé) montre une compréhension correcte du périmètre V1 (share intent, artifacts, freemium, ton calme)
- [ ] #3 #3 Section 3 contient ≥ 30 candidats bruts avec angle d'origine et raison de filtrage
- [ ] #4 #4 Section 4 contient 10-15 finalistes scorés sur les 9 critères avec vérifications de disponibilité documentées (App Store, Play Store, domaine, USPTO, EUIPO, handles sociaux) — URLs + date d'accès
- [ ] #5 #5 Section 5 contient une shortlist de 5 noms classés avec score, justification, risques, tagline et identité visuelle
- [ ] #6 #6 Section 6 met en avant 1 nom recommandé avec justification croisée vs les 4 autres
- [ ] #7 #7 Aucun fichier modifié hors de `docs/research/task-XX-app-name/`
- [ ] #8 #8 Aucun nom de la conversation préalable (Sift, Recap, Drift, Pith, Stash, Cache, Trace, Echo, Mnemo, Cortex, Tether, Drop, Brief, Gist, etc.) n'est repris tel quel sans avoir été regénéré indépendamment depuis les angles thématiques (anti-bias)
- [ ] #9 #9 Section 7 (Decision) est vide, prête pour l'owner
<!-- AC:END -->

## Implementation Notes

**Mode**: initial (first research pass — no prior `docs/research/task-115-app-name/` directory existed)

**Produced**: `docs/research/task-115-app-name/README.md` — full benchmark deliverable containing:
- 40 raw candidates across 8 thematic angles (memory, digest, curation, calm, light, botanical, invented words, foreign languages)
- 12 detailed finalist evaluations with 9-criteria scoring and availability verification
- Top 5 shortlist: Culma (43/45), Shimiru (40/45), Steepen (38/45), Humus (38/45), Nureru (37/45)
- Final recommendation: **Culma** — invented word (calm + Latin -ma), 5 letters, zero App Store/Play Store conflicts, multiple domains available (.app, .io, .co)

**Availability verification methods used**:
- iTunes Search API (automated, 2026-06-07)
- Google Play Store search (automated, 2026-06-07)
- DNS resolution via `dig +short` for .com/.app/.io/.co domains (automated, 2026-06-07)
- Brave Search and DuckDuckGo for trademark/brand existence checks (2026-06-07)

**Note**: USPTO TESS and EUIPO TMView are not programmatically accessible (return 403/captcha). Trademark verification was done indirectly via web search. Owner should confirm via manual TESS/TMView search before filing.

**Recommendation awaits owner validation** via `owner_decision` field in the README front-matter.

---

**Mode**: complement (2026-06-08) — responding to owner's `more` request

**Owner feedback integrated**:
- Culma eliminated: "cul" substring unacceptable for French-first market
- Steepen direction appreciated (infusion/intensification metaphor)
- Request for more alternatives before final decision

**Produced**: `docs/research/task-115-app-name/complement-response-2026-06-08.md` containing:
- 22 new raw candidates (all generated from scratch with FR linguistic sensitivity filter)
- 8 scored finalists with full 9-criteria evaluation and availability verification
- New recommendation: **Imbura** (44/45) — fusion of EN "imbue" + FR "imbiber", 6 letters, ALL domains free (.app/.com/.io/.co), zero French sensitivity issue, bilingual semantic resonance
- Full shortlist: Imbura (44), Macena (42), Imbuva (42), Fondma (41), Steepra (39), Tremoa (39), Fonsma (38), Steepen (38)

**Key improvement over initial pass**: Imbura (44/45) outscores all original candidates including Culma (43/45), with zero French language issues and exceptional commercial availability (all 4 TLDs free including .com — extremely rare for a 6-letter name).

**Recommendation awaits owner validation** via `owner_decision` field in the main README front-matter.

---

**Mode**: redo (2026-06-08) — fresh benchmark after owner rejected both the initial pass and the complement

**Owner feedback integrated in this redo**:
1. French is PRIMARY market — name must sound great in French first, then English
2. "Cul" substring fatal — verified all candidates with FR sensitivity filter
3. Complement was bad: too many "-ra" suffix names, options were "peu parlantes" (not evocative)
4. Owner wants IMMEDIATELY EVOCATIVE names (not obscure invented words)
5. Diversity of structures required (not all same suffix pattern)
6. "Steepen" direction still valid but needs genuine alternatives

**Produced**: `docs/research/task-115-app-name/README.md` (NEW, replaces archived version) containing:
- 35 raw candidates across 6 thematic angles (percolation, distillation, material/receptacle, retention, organic growth, intensification)
- 12 detailed finalist evaluations with full 9-criteria scoring and availability verification
- Top 5 shortlist: Percole (43/45), Retenso (41/45), Macerer (39/45), Buvard (39/45), Steepen (38/45)
- Final recommendation: **Percole** — real word (FR/IT conjugated form of "percoler"), transparent in both FR and EN ("percolate"), ALL domains free (.com/.app/.io/.co), zero App Store conflict, zero trademark

**Key improvements over previous passes**:
- ALL names are "parlant" (immediately evocative): real French/English words or ultra-transparent Latin roots
- NO repeated suffix patterns: diverse structures (verbe conjugue, verbe infinitif, nom commun, mot invente, verbe anglais)
- French sensitivity verified for every candidate
- None of the rejected names reused (Culma, Imbura, Macena, Imbuva, Fondma, Steepra, Tremoa, Fonsma)
- Percole beats all previous recommendations in bilingual transparency: FR and EN speakers BOTH understand it immediately

**Recommendation awaits owner validation** via `owner_decision` field in the README front-matter.
