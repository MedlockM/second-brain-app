---
id: task-116
title: >-
  Benchmark feedback intake tools (Canny, Featurebase, Frill, etc.) for V1 user
  feature requests
status: To Do
assignee: []
created_date: '2026-06-08 10:51'
labels:
  - benchmark
  - product
  - scoping
  - community
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

L'app est en pré-lancement V1 (cf. `docs/V1_LAUNCH_PLAN.md`). Une fois publiée sur l'App Store et le Play Store, on a besoin d'un canal **structuré** pour collecter les **demandes de fonctionnalités** des users et **prioriser** la roadmap V1.5 / V2 en fonction du signal réel.

Aujourd'hui on n'a aucun système en place. Sans ça, le feedback va arriver de façon dispersée (mails, reviews App Store, DMs Twitter/Discord, retours informels) et il sera impossible de :
- Identifier les features les plus demandées (signal de masse)
- Tracker la "shipping velocity" et fermer la boucle "ils ont demandé X → on a livré X"
- Permettre aux users de **voter** sur les idées des autres pour révéler les vraies priorités plutôt que les loud minorities
- Communiquer publiquement la roadmap

Catégories d'outils existants sur le marché : feedback boards dédiés (Canny.io, Featurebase, Frill, ProductBoard, Upvoty, FeedBear, Sleekplan), GitHub Discussions, Discord forum channels, formulaires Typeform/Tally + spreadsheet, soluces self-hosted (Fider, Astuto), intégrations notion/linear.

## Goal of this benchmark

Produire une recommandation pour un **outil de feedback intake** adapté à un **projet solo / very early stage** (≤ 1000 users en soft launch, freemium). L'outil doit permettre à minima :
1. Aux users de **soumettre** une demande de feature (ou bug, ou question UX) en ≤ 3 clics depuis l'app mobile (web view embarquée OU lien externe acceptable)
2. Aux users de **voter** sur les idées des autres
3. À l'owner de **trier**, **labelliser**, **commenter**, **changer le statut** (Under review / Planned / In progress / Shipped / Declined)
4. Une **roadmap publique** affichant ce qui est en cours, ce qui est shippé, ce qui est planned

Critères secondaires importants : authentification SSO depuis l'app mobile (pour pas re-créer un compte), branding personnalisable (couleurs, logo, sous-domaine type `feedback.secondbrainlabs.com`), API publique pour pouvoir migrer plus tard, RGPD, hébergement EU possible, intégration Slack/Discord pour notifications.

## Méthode imposée

### Critères d'évaluation (à scorer 1-5 pour chaque outil)

1. **Coût** au stade V1 (≤ 1000 users, ≤ 100 idées actives) — gratuit ≥ 4, ≤ 20 €/mois ≥ 3, > 50 €/mois ≤ 2
2. **Friction de soumission** côté user — depuis l'app mobile (lien externe, web view, deep link, popup), nombre de clics, besoin de créer un compte ou pas
3. **Système de vote** — anonyme ou nominatif, 1 vote/user, possibilité de retirer, weighting selon plan d'abonnement
4. **Roadmap publique** — UI claire des statuts, possibilité de filtrer/grouper, branding
5. **SSO / login intégration** — possibilité d'identifier l'user via JWT custom (notre backend) ou OAuth (Google/Apple) sans créer un nouveau compte
6. **Branding & domaine custom** — sous-domaine `feedback.secondbrainlabs.com` possible, CSS/couleurs custom, suppression du logo de l'éditeur
7. **API + portabilité des données** — REST/GraphQL pour exporter idées + votes + comments, format standard (JSON/CSV)
8. **Notifications** — webhooks Slack/Discord, emails, in-app, fréquence configurable
9. **RGPD & hébergement** — datacenters EU disponibles, DPA signable, suppression d'utilisateur on-demand
10. **Intégration mobile** — SDK natif iOS/Android, ou WebView simple, ou deep link uniquement
11. **Future-proof** — si l'app passe à 100k users, est-ce que l'outil scale ? Tier supérieur raisonnable ?
12. **Réputation / track record** — l'outil est-il utilisé par des indie devs / startups respectées ? Pivot risk de l'éditeur ?

### Outils à évaluer (au minimum)

L'agent doit benchmarker au moins ces 8 outils, en complétant si nécessaire avec d'autres trouvés en route :

1. **Canny.io** — référence du marché, focus B2B SaaS
2. **Featurebase.app** — challenger récent (2023), pricing agressif
3. **Frill.co** — concurrent direct de Canny avec free tier
4. **Sleekplan** — feedback + changelog + roadmap dans 1 outil
5. **Upvoty** — un des moins chers
6. **FeedBear** — orienté petits SaaS
7. **GitHub Discussions** — gratuit, déjà disponible, mais public uniquement
8. **Discord forum channels** + bot vote — gratuit, communautaire (cf. task de création du serveur Discord en parallèle)

Pour chaque outil :
- **Free tier limits** précis (idées max, users max, custom domain, branding removal)
- **Premier paid tier** : prix mensuel, ce qu'il débloque
- **Signup test** : créer un compte, soumettre une idée test, voter, changer statut — documenter la friction réelle
- **Mobile UX** : ouvrir le board sur smartphone, noter la fluidité

### Pour chaque finaliste (top 3)

L'agent doit produire :
- Capture d'écran ou description précise du flow user (ouvrir feedback board → voter → soumettre idée)
- Capture / description de l'admin panel
- Liste **exacte** des champs custom configurables (catégorie, priorité, etc.)
- Lien vers la doc d'intégration JWT/SSO
- Lien vers la doc d'export des données
- Liste de produits connus utilisant l'outil (preuve sociale)

## Anti-bias

- Pas d'a priori "Canny est le meilleur" — vérifier ses concurrents qui ont rattrapé en 2024-2025
- Pas d'a priori "GitHub Discussions / Discord suffisent" — ces options ont des limites concrètes (pas de vote natif sur GH Discussions, fragmentation de la conversation sur Discord)
- Considérer le contexte **solo dev avec budget limité** — le tier gratuit + custom domain doit peser fort dans la décision

## Deliverable

Document unique à `docs/research/task-XX-feedback-intake/README.md` avec :

- **Front-matter YAML** avec `owner_decision: pending`
- **Section 1 — Brief produit reformulé** : pourquoi on en a besoin maintenant, quelles features bloquantes
- **Section 2 — Méthode** : critères, outils évalués, biais évités
- **Section 3 — Tableau comparatif synthétique** : 1 ligne par outil × 12 critères, score sur 5
- **Section 4 — Fiche détaillée par finaliste** (top 3) : pricing exact, free tier, captures/UX, intégrations
- **Section 5 — Recommandation** : 1 outil principal recommandé + 1 alternative, avec justification
- **Section 6 — Plan d'intégration V1** : où on met le lien dans l'app mobile (settings ? menu profil ?), faut-il un endpoint backend ? quelle URL custom ? faut-il automatiser le SSO ? 
- **Section 7 — Decision** : section vide pour l'owner

## Constraints

- Tâche de **recherche pure**. Aucun fichier modifié hors `docs/research/task-XX-feedback-intake/`
- Pas de mise à jour `V1_LAUNCH_PLAN.md`, pas de modif `mobile/`, pas de creation d'endpoint backend
- Citer **toutes les URLs** de pricing pages avec date d'accès (ces tarifs bougent souvent)
- Tester gratuitement chaque tier free quand possible (créer un compte test sur 3-4 outils minimum)

## References

- `docs/V1_LAUNCH_PLAN.md` — périmètre V1
- `task-115` (en cours) — nom de l'app, qui pourra être réutilisé pour le branding du board
- `task-XXX` (en parallèle) — création du serveur Discord (canal de communication principal — complémentaire mais distinct du feedback board)
- `CLAUDE.md` — convention benchmark + paire d'implémentation
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 docs/research/task-XX-feedback-intake/README.md existe avec `owner_decision: pending` dans le front-matter
- [ ] #2 #2 Au moins 8 outils benchmarkés (Canny, Featurebase, Frill, Sleekplan, Upvoty, FeedBear, GitHub Discussions, Discord)
- [ ] #3 #3 Tableau comparatif synthétique avec 12 critères scorés 1-5 pour chaque outil
- [ ] #4 #4 Top 3 finalistes ont chacun une fiche détaillée avec pricing exact, free tier limits, captures ou description UX, doc d'intégration SSO/API/export, exemples d'utilisation
- [ ] #5 #5 URLs de pricing avec date d'accès documentées (ces tarifs bougent souvent)
- [ ] #6 #6 Section 5 émet une recommandation principale + 1 alternative avec justification croisée
- [ ] #7 #7 Section 6 décrit le plan d'intégration concret côté mobile et backend (où le lien, quel endpoint, quelle URL custom, faut-il du SSO)
- [ ] #8 #8 Section 7 (Decision) est vide, prête pour l'owner
- [ ] #9 #9 Aucun fichier modifié hors de `docs/research/task-XX-feedback-intake/`
<!-- AC:END -->
