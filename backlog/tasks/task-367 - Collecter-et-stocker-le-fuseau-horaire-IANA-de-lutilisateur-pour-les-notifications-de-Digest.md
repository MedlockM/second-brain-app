---
id: task-367
title: >-
  Collecter et stocker le fuseau horaire IANA de l'utilisateur pour les
  notifications de Digest
status: To Do
assignee: []
created_date: '2026-09-06 16:11'
labels:
  - mobile
  - backend
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Pourquoi maintenant, et séparément

Le Digest sera notifié à **18h30 heure locale** de l'utilisateur (daily) et **lundi 9h30 locale** (weekly). Or aucun fuseau horaire n'est stocké nulle part dans le dépôt : tout le digest raisonne en UTC. 18h30 UTC, c'est 20h30 à Paris et 13h30 à New York.

Cette tâche ne fait que **collecter et stocker le fuseau**. Elle n'envoie aucune notification et ne dépend d'aucun choix de chemin de livraison : elle peut donc partir avant le benchmark, et c'est souhaitable — au moment où les notifications seront livrées, les fuseaux seront déjà connus pour les testeurs actifs, au lieu d'un premier envoi manqué.

## Le moyen est déjà dans le dépôt

`expo-localization` est **déjà installé** (`~55.0.18`) et déjà utilisé pour la détection de langue dans `mobile/src/i18n/index.tsx`. Son `getCalendars()[0].timeZone` renvoie le fuseau IANA de l'OS.

**Aucune dépendance nouvelle, donc aucun build EAS** : le fingerprint ne bouge pas, la tâche part en OTA.

## Ce qui est décidé et n'est pas à rediscuter

- **On stocke le nom IANA** (`"Europe/Paris"`), **jamais un décalage horaire**. Un `+02:00` stocké serait faux six mois par an ; le nom IANA gère l'heure d'été sans aucune logique côté serveur.
- **Le champ se range sur `User`**, à côté de `reading_language` (`media_summarizer/core/models/user.py`), avec la même mécanique de persistance et de lecture.
- **Rafraîchi à chaque passage de l'app au premier plan**, pas seulement à l'inscription : un utilisateur qui voyage voit ses notifications suivre, sans rien faire.
- **Aucune question posée à l'utilisateur, aucun écran de réglage.** Si le fuseau doit un jour être modifiable à la main, ce sera une autre tâche.
- L'écriture ne part que si la valeur a changé : pas d'écriture DynamoDB à chaque foreground.

## Le cas « fuseau inconnu »

Un compte qui n'a pas rouvert l'app depuis la livraison n'a pas de fuseau. Décision owner : **on ne notifie pas** tant qu'on ne sait pas, plutôt que de replier sur UTC et de sonner à 20h30 chez lui. Le champ reste donc légitimement vide et les consommateurs doivent le tolérer.

Le premier passage au premier plan règle le cas.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de valeur par défaut fabriquée, pas de rétro-remplissage à UTC, pas de migration des comptes existants : le champ est vide jusqu'à ce que l'app le renseigne.

## Notes pour l'owner (pas des ACs)

- Cette tâche seule ne produit rien de visible : elle remplit une colonne. Sa vérification est une lecture DynamoDB.
- Le déploiement se joue au push sur `main`. Comme aucune dépendance native n'est touchée, c'est une OTA et non un build.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le modèle User de media_summarizer/core/models/user.py porte un champ de fuseau horaire optionnel, persisté et relu comme reading_language, sans valeur par défaut fabriquée
- [ ] #2 L'app lit le fuseau IANA via getCalendars()[0].timeZone d'expo-localization et le transmet au serveur, sans ajouter aucune dépendance au mobile
- [ ] #3 La valeur transmise est un nom IANA et jamais un décalage horaire, et le serveur rejette une valeur qui n'est pas un identifiant IANA reconnu
- [ ] #4 Le fuseau est réévalué à chaque passage de l'application au premier plan, et n'est écrit que s'il diffère de la valeur déjà stockée
- [ ] #5 Aucun écran de réglage ni aucune question n'est ajouté à l'interface pour ce fuseau
- [ ] #6 Un compte sans fuseau connu reste valide : le champ demeure vide, sans rétro-remplissage ni repli sur UTC
- [ ] #7 Le trajet complet est vérifié sur l'environnement -dev : après un passage au premier plan, l'enregistrement utilisateur en DynamoDB -dev porte le nom IANA attendu
- [ ] #8 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
