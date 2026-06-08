---
id: task-118
title: >-
  Set up Second Brain Labs Discord server as primary user-team communication
  channel
status: To Do
assignee: []
created_date: '2026-06-08 10:53'
labels:
  - community
  - ops
dependencies: []
priority: medium
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

L'app V1 (cf. `docs/V1_LAUNCH_PLAN.md`) sera lancée publiquement sur App Store + Play Store en Phase 10. Avant le launch, on veut **un canal de communication public** entre l'équipe (= owner solo pour V1) et les premiers users, pour :

- Répondre aux questions / accompagner les early adopters
- Recevoir du feedback informel et "voir le produit utilisé en vrai"
- Animer une communauté autour du concept "second brain / slow consumption"
- Annoncer les releases, downtime, news produit
- Servir de support de premier niveau (avant un éventuel email/zendesk)

Discord est le choix par défaut : gratuit, pertinent pour un public productivity / techy / curieux, déjà connu de la majorité, mobile-friendly. **Pas besoin de benchmark** — c'est un setup/config task, pas une décision d'architecture.

> Note : ce serveur est **complémentaire** au feedback board défini par `task-116` (Canny / Featurebase / etc.). Discord = conversation, support, communauté. Feedback board = capture structurée + vote sur les feature requests. Les deux peuvent coexister, et `task-117` peut prévoir des bridges (webhook Discord quand une nouvelle idée arrive sur le board).

## Goal

Mettre en ligne un serveur Discord opérationnel à l'URL `discord.gg/secondbrainlabs` (ou similaire si non dispo), prêt à accueillir les premiers users **avant** le soft launch.

## Spécifications

### 1. Identité du serveur

- **Nom** : `Second Brain Labs` (à mettre à jour si l'agent task-115 sort un nom marketing différent — dans ce cas le serveur peut s'appeler `<NomApp> Community`)
- **Logo** : reprendre l'icône / le logo provisoire de l'app (ou un placeholder simple en attendant le branding final)
- **Vanity URL** (`discord.gg/...`) : le claim une fois que le serveur a > 50 membres si c'est nécessaire (Discord exige le niveau Boost 3 pour les vanity URLs dans certains cas — vérifier les conditions actuelles)
- **Couleur d'accent** : warm beige `#fcf9f6` (cohérent avec le splash mobile) ou tout autre couleur du design system "Amber Clarity"

### 2. Structure de canaux (organisée en catégories)

#### Catégorie "👋 Welcome"
- `#welcome` (read-only, message d'accueil + règles + lien vers App Store / Play Store / feedback board)
- `#announcements` (read-only, posts par l'équipe : releases, downtime, blog posts)
- `#rules` (read-only, code de conduite court : être respectueux, pas de spam, langue principale anglais + français OK)

#### Catégorie "💬 General"
- `#general-chat` (discussion libre)
- `#introduce-yourself` (présentations)
- `#showcase` (les users partagent leurs usages, leurs notes générées, leurs flashcards, etc.)

#### Catégorie "🛠️ Support"
- `#help` (questions sur l'app, bugs, comment faire X) — forum channel idéalement (Discord nouveau type de channel "Forum" qui scope mieux les threads)
- `#feature-requests` (renvoie vers le feedback board défini par `task-116` via un message épinglé) — pas de discussion ici, juste un panneau directionnel
- `#known-issues` (read-only, liste des bugs connus en cours de fix)

#### Catégorie "📢 Off-topic"
- `#productivity-talk` (discussions thématiques : note-taking, second brain, lifelong learning)
- `#shared-articles` (partage d'articles intéressants — ironie : ils peuvent les ingérer dans l'app)

### 3. Rôles

- `@admin` (owner uniquement)
- `@moderator` (vide pour l'instant, à attribuer aux premiers contributeurs actifs)
- `@early-adopter` (auto-attribué aux 100 premiers membres — système de "vanity badge" pour récompenser l'arrivée précoce)
- `@beta-tester` (attribué manuellement aux gens qui sont opt-in pour tester les pre-releases)
- `@verified` (attribué via OAuth / email match avec un compte Second Brain Labs payant — *à différer si pas urgent*)

### 4. Bots à installer

- **MEE6** ou **Carl-bot** (modération de base, welcome message, role auto-assignment, anti-spam)
- **Sesh** ou un bot équivalent pour les annonces de releases (cron-based reminders, optional)
- **Webhook custom** : quand un release notes est publié sur GitHub, poster dans `#announcements` (à mettre en place quand CI/CD GitHub Actions est en place — Phase 7 V1 launch plan)
- **Webhook depuis le feedback board** (`task-117`) : quand un nouveau status `Shipped` ou `Planned` est mis, poster dans `#announcements` ou un canal dédié

### 5. Code de conduite (règlement court)

À rédiger dans `#rules` (5-7 lignes max) :
- Sois respectueux et patient (l'équipe est solo, on répondra dès qu'on peut)
- Pas de spam, pas de pub, pas de NSFW
- Langue principale : anglais. Français bienvenu, mais préférer l'anglais dans les channels publics pour rester accessible
- Pour les bugs : utilise `#help` (pas DM)
- Pour les feature requests : utilise le feedback board (lien)
- Pas de partage de credentials, API keys, etc.

### 6. Lien d'invitation à intégrer dans l'app

L'URL Discord sera ajoutée :
- Dans **Settings → Community** dans l'app mobile (à différer dans une future tâche d'implémentation mobile, ou inclure dans `task-117`)
- Dans la **fiche App Store / Play Store** (Phase 10, support URL ou social link)
- Dans **CGU / privacy policy** (mention "Community: discord.gg/...")
- Dans **les emails transactionnels** (welcome email, password reset) — à différer

### 7. Protection / safety

- **Verification level** : "Medium" (l'user doit avoir un compte Discord vérifié par email)
- **Explicit content filter** : "Scan messages from members without roles"
- **2FA requis pour les admins** (paramétré côté Discord User Settings)
- **AutoMod** : règles standard contre les liens suspects, mass mentions, etc.
- **Slow mode** sur `#general-chat` à 5s en cas d'afflux (à activer manuellement seulement si abus)

## Out of scope (pour cette tâche)

- L'intégration **mobile** du lien Discord dans l'app — sera dans `task-117` ou tâche dédiée
- Le **bridge automatique GitHub releases → Discord** — sera fait en Phase 7 (CI/CD)
- Le **rôle `@verified` via OAuth Second Brain Labs** — sera fait après le launch si la communauté grandit
- Animation / community management — pas une tâche dev

## Deliverable

- Serveur Discord créé et configuré selon les specs
- URL d'invitation permanente (`discord.gg/<vanity>` si possible, sinon URL standard) fournie à l'owner et stockée dans `docs/community/discord.md`
- Template de message de welcome pré-rédigé dans `#welcome`
- Code de conduite publié dans `#rules`
- 2 ou 3 messages de seed dans `#general-chat` et `#announcements` (pour pas que ça soit vide au lancement)
- Document `docs/community/discord.md` créé avec : URL du serveur, structure des canaux, liste des rôles, qui modère, comment ajouter un bot, comment configurer un webhook

## Constraints

- Pas de paiement Discord Boost requis pour V1 (peut venir plus tard si la communauté grossit)
- Garder la structure **simple** au début — on peut toujours ajouter des canaux, mais en supprimer crée de la confusion
- L'URL d'invitation doit être **permanente** (pas d'expiration ni de limite d'usages), à régénérer si nécessaire
- Le canal `#announcements` doit être le seul endroit où l'équipe poste — préserver le signal/bruit

## References

- `docs/V1_LAUNCH_PLAN.md` — Phase 10 mentionne le besoin de canaux de communication
- `task-115` — nom de l'app (impacte potentiellement le nom du serveur)
- `task-116` — feedback intake (complémentaire mais distinct)
- `task-117` — implémentation mobile du feedback link, pourrait inclure le lien Discord
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 Serveur Discord créé avec le nom `Second Brain Labs` (ou nom de l'app si task-115 a sorti un nom validé), logo et identité visuelle alignés sur le design system
- [ ] #2 #2 Structure de canaux créée selon les spécifications (4 catégories : Welcome, General, Support, Off-topic)
- [ ] #3 #3 Au moins 5 rôles configurés : @admin, @moderator, @early-adopter, @beta-tester, @verified (même si certains sont vides au départ)
- [ ] #4 #4 Au moins 1 bot de modération installé (MEE6, Carl-bot ou équivalent) avec welcome message + auto-role configurés
- [ ] #5 #5 Code de conduite publié dans `#rules`, 5-7 lignes, en français et anglais
- [ ] #6 #6 Verification level = Medium, AutoMod activé, 2FA requis pour les admins
- [ ] #7 #7 URL d'invitation **permanente** (pas d'expiration, pas de limite d'usages) générée et fournie
- [ ] #8 #8 `docs/community/discord.md` créé avec : URL du serveur, structure complète des canaux, liste des rôles, qui modère, comment ajouter un bot, comment configurer un webhook
- [ ] #9 #9 Au moins 1 message de welcome dans `#welcome` et 1 message de seed dans `#general-chat` pour éviter le serveur vide au lancement
<!-- AC:END -->
