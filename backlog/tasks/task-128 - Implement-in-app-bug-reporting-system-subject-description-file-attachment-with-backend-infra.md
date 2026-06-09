---
id: task-128
title: >-
  Implement in-app bug reporting system (subject, description, file attachment)
  with backend + infra
status: Done
assignee: []
created_date: '2026-06-09 10:35'
labels:
  - feature
  - mobile
  - backend
  - infra
  - community
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Pendant la phase soft-launch V1, on a besoin d'un canal **dédié et frictionless** pour que les users remontent les bugs depuis l'app mobile. Le feedback intake livré par `task-117` couvre les **demandes de fonctionnalités** (votes, roadmap publique) mais pas un flow guidé de bug report — où l'attachement d'une capture / vidéo de repro / log est essentiel pour qu'un bug soit actionnable.

## Goal

Concevoir et livrer un système de remontée de bug **custom**, accessible depuis l'app mobile, avec :

1. Un point d'entrée clair dans le menu Settings ou Profil
2. Un formulaire avec :
   - Champ **sujet** (texte court, obligatoire)
   - Champ **description** du bug (texte long, obligatoire)
   - Possibilité d'**attacher un fichier** parmi : image (jpg/png/heic), vidéo (mp4/mov), PDF, zip
3. Un upload sécurisé du fichier vers le cloud storage
4. Un endpoint backend qui persiste le rapport et le route vers le canal de triage retenu
5. Un retour à l'user (écran de confirmation + identifiant de ticket)

## Scope — décisions d'architecture à prendre par l'implémenteur

L'implémenteur tranche les points suivants **en cohérence avec l'infra existante** (S3, Terraform, FastAPI backend, Expo mobile, hexagonal côté backend) et documente ses choix dans la PR :

- **Storage des attachements** : bucket S3 dédié `bug-reports/` ou préfixe sur le bucket media existant ? Politique de rétention (par défaut : purge automatique 90 jours après résolution).
- **Upload flow** : presigned URL S3 (recommandé pour ne pas faire transiter le binaire par le backend) vs proxy backend. Justifier le choix.
- **Limites de taille** : à fixer (recommandation : 50 Mo / fichier, 1 fichier max V1) et appliquer côté client ET backend.
- **Validation MIME / extension** : whitelist stricte côté backend après upload — ne pas faire confiance au content-type envoyé par le client. Refuser tout fichier hors whitelist.
- **Scan antivirus** : décider V1 — ClamAV via Lambda S3 trigger, SaaS (VirusTotal API), ou on accepte le risque résiduel pour V1 et on note la dette ?
- **Persistence** : nouvelle table `bug_reports` avec a minima `id, user_id, subject, description, attachment_keys[], status, created_at, source_app_version, source_platform`.
- **Routing du report** : Discord webhook (cf. `task-118`) / création d'issue GitHub via API / Linear via API / DB seule + futur dashboard owner. Justifier le choix V1, garder l'option de routage configurable (env var).
- **Auth & rate-limiting** : auth obligatoire (l'user est connecté pour utiliser l'app — pas de bug report anonyme V1) ; rate limit (ex : 5 reports / heure / user) pour éviter abus.
- **Privacy / RGPD** : politique de rétention des attachements documentée, endpoint d'effacement on-demand cohérent avec la politique RGPD existante de l'app.

## Constraints

- Design system mobile **Amber Clarity** respecté pour l'écran de bug report et le bouton d'entrée.
- Pas de hardcode d'URL ni de secret — tout via env vars (`BUG_REPORT_BUCKET`, `BUG_REPORT_ROUTING_WEBHOOK`, etc.) déclarées dans `.env.example` + Terraform `secret_payload` quand secret.
- Hexagonal côté backend (port + adapter) puisque déjà en place sur les autres workers.
- Toute infra additionnelle (bucket, IAM policy, lambda éventuelle, secrets) **doit être en Terraform**, pas en clic-clic console AWS.
- Pas d'extension du périmètre vers un dashboard owner V1 — rester focalisé sur l'intake et le routage.

## References

- `task-117` — feedback intake (Canny) : flow voisin mais distinct (features vs bugs)
- `task-118` — Discord server : potentiel canal de triage
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — design system mobile
- `docs/V1_LAUNCH_PLAN.md` — périmètre V1
- `AGENTS.md` — règles delivery V1, hexagonal, KISS
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un point d'entrée 'Signaler un bug' est accessible depuis le menu Settings ou Profil de l'app mobile, conforme au design system Amber Clarity
- [ ] #2 Le formulaire mobile contient un champ sujet (texte court, obligatoire), un champ description (texte long, obligatoire) et un sélecteur d'attachement
- [ ] #3 Le sélecteur d'attachement accepte uniquement image (jpg/png/heic), vidéo (mp4/mov), PDF et zip ; tout autre type est refusé avec un message clair côté UI
- [ ] #4 Une limite de taille par fichier est définie, documentée, appliquée côté client (UX claire) ET côté backend (refus 413 si dépassée)
- [ ] #5 L'upload du fichier se fait via presigned URL S3 (ou méthode justifiée équivalente) ; le binaire ne transite pas par le backend FastAPI
- [ ] #6 Le content-type ET l'extension du fichier sont validés côté backend après upload (whitelist stricte, pas de confiance dans les valeurs fournies par le client)
- [ ] #7 Un endpoint POST /api/bug-reports authentifié existe, persiste le rapport en base et retourne un identifiant unique de ticket à l'user
- [ ] #8 Une migration crée la table bug_reports avec a minima : id, user_id, subject, description, attachment_keys[], status, created_at, source_app_version, source_platform
- [ ] #9 Le report est routé vers le canal de triage retenu (Discord webhook / GitHub Issue API / Linear API / DB seule) — choix justifié dans la PR description
- [ ] #10 Endpoint refuse un appel non authentifié avec 401 ; rate limiting appliqué (ex : 5 reports / heure / user) avec 429 si dépassé
- [ ] #11 Mobile affiche un écran (ou toast plein écran) de confirmation après envoi avec l'ID du ticket et un message rassurant
- [ ] #12 Toutes les infra additions (bucket S3, IAM policy, lambda éventuelle, secrets, env vars) sont déclarées en Terraform et appliquées via le pipeline existant
- [ ] #13 Politique de rétention des attachements implémentée (lifecycle S3 ou job dédié) — par défaut purge 90 jours après résolution du report
- [ ] #14 docs/community/bug-reports.md créé : où vont les reports, qui répond, SLA cible, politique de rétention RGPD, comment l'owner triage
- [ ] #15 Décision sur le scan antivirus V1 documentée dans la PR (implémenté OU dette consciente avec issue de suivi créée)
<!-- AC:END -->
