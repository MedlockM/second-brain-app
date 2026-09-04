---
id: task-358
title: >-
  Pointer les liens légaux du paywall vers les pages retenues par le benchmark
  (task-357)
status: To Do
assignee: []
created_date: '2026-09-04 15:26'
labels:
  - mobile
  - compliance
dependencies:
  - task-357
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mettre en place les liens légaux de l'app conformément à la décision de l'owner sur le benchmark **task-357**.

## Avant de commencer

Lire `docs/research/task-357-*/README.md` et en particulier le champ `Decision` sous **Owner Validation** : c'est lui qui fait foi, pas la recommandation initiale du benchmark, et il peut renvoyer à un fichier de complément qu'il faut alors lire aussi. Suivre l'option retenue et l'architecture qu'elle décrit.

## Portée

Les deux liens exigés par l'écran d'achat — conditions d'utilisation et politique de confidentialité — ainsi que l'adresse de contact de confidentialité, sont lus depuis un seul fichier, `mobile/src/constants/legal.ts`. Le travail côté code se concentre là, plus les éventuels points d'appel que la décision ferait apparaître.

Deux exigences portées par le fichier lui-même, à ne pas perdre en chemin :

- l'écran d'achat **et** l'écran de suppression de compte doivent pointer vers les mêmes adresses, sans divergence ;
- l'adresse de contact doit rester cohérente avec la section « accès / portabilité » de la politique de confidentialité, l'app n'ayant pas d'export en libre-service.

Le domaine actuellement référencé n'appartient pas au projet : aucune de ses adresses ne doit subsister, y compris en valeur de repli ou en commentaire donné comme exemple valide.

Cadrage (`AGENTS.md`, « Nothing is deployed yet ») : l'app n'a jamais été soumise à un store, aucun lien n'est en circulation. On remplace, on ne fait pas cohabiter l'ancien et le nouveau.

## Notes pour l'owner (pas des ACs)

- **Publier les pages vous revient** : elles doivent être joignables publiquement, sans authentification, avant la première soumission. Un agent ne peut ni acheter un domaine ni mettre une page en ligne.
- Une fois publiées, vérifier depuis l'app que les deux liens de l'écran d'achat ouvrent bien les bonnes pages — un lien qui répond 404 est rejeté comme un lien absent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `TERMS_URL`, `PRIVACY_POLICY_URL` et l'adresse de contact de `mobile/src/constants/legal.ts` valent exactement les adresses décidées dans le `Decision` du README de task-357
- [ ] #2 `grep -rn 'mediasummarizer' mobile/` ne renvoie plus aucune adresse légale, ni en valeur, ni en repli, ni en exemple de commentaire
- [ ] #3 L'écran d'achat et l'écran de suppression de compte lisent tous deux ces constantes ; aucune URL légale n'est écrite en dur ailleurs dans `mobile/`
- [ ] #4 `npm run typecheck` et `npm run lint` sont propres dans `mobile/`
<!-- AC:END -->
