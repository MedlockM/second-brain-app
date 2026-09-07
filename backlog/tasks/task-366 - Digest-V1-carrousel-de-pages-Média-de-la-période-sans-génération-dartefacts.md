---
id: task-366
title: >-
  Digest V1 : carrousel de pages Média de la période, sans génération
  d'artefacts
status: To Do
assignee: []
created_date: '2026-09-06 15:41'
updated_date: '2026-09-06 16:11'
labels:
  - mobile
  - backend
  - feature
dependencies:
  - task-365
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## La forme décidée

Décision owner du 2026-09-06. Le Digest V1 est **un carrousel horizontal de pages Média, et rien d'autre** :

- une carte = la page Média complète d'un média, avec ses deux onglets Reader et IA ;
- ordre **chronologique croissant** ;
- pagination horizontale reprise de la Revue des non-classés (`mobile/app/media/unsorted-review.tsx`, `ScrollView horizontal pagingEnabled`), **mais sans les actions Jeter / Approfondir / Ranger** : le Digest ne propose aucune action sur le média, il le présente.

L'intérêt visé est la rétention par la répétition : revoir le contenu réel, pas un résumé de résumé.

## Les périodes — révisées le 2026-09-06 avec la décision sur les notifications

Le Digest est notifié : chaque jour à 18h30 locale pour le daily, chaque lundi à 9h30 locale pour le weekly (tâche séparée). Les périodes sont donc définies par ce que la notification annonce, pas par le calendrier :

- **Daily = les 24 heures glissantes précédant l'envoi de 18h30.** Pas la journée calendaire. C'est ce qui garantit qu'un média enregistré à 22h est annoncé exactement une fois, au lieu de rejoindre en silence un digest déjà notifié.
- **Weekly = la semaine écoulée, lundi à dimanche révolus.** Pas la semaine ISO en cours, qui n'a que neuf heures d'âge quand la notification part le lundi à 9h30.

### Conséquence à implémenter explicitement : la fenêtre est figée, pas recalculée

Une fenêtre recalculée à chaque ouverture de l'écran ne correspondrait **jamais** à ce que la notification a annoncé : ouvert à 21h, un digest glissant montrerait 21h−24h, un autre ensemble que celui de 18h30.

Le digest est donc **capturé au moment de l'envoi** et reste stable jusqu'au suivant. Entre minuit et 18h30, l'écran montre la capture de la veille. Le `period_key` reste utilisable : date locale de l'envoi pour le daily, semaine ISO écoulée pour le weekly.

## Dépendance stricte

La carte rend le composant partagé produit par **task-365**, avec son chrome désactivé. Le Digest ne redessine pas la page Média et n'en fait aucune variante : si la page Média change demain, le Digest suit sans qu'on y touche. C'est l'exigence centrale de l'owner, pas une préférence d'implémentation.

Un header unique « Daily / Weekly » est rendu au-dessus du pager. Le sélecteur Daily/Weekly existant de `mobile/app/(tabs)/digest.tsx` est conservé.

## Ce que la V1 supprime

En affichant la page Média entière, la V1 retire son unique consommateur à toute la charge utile actuelle du digest. Elle est supprimée, pas conservée :

- backend : `insights`, `themes`, `stats` (`media_count`, `total_minutes`, `by_type`), `summary_excerpt`, `read_time_minutes` dans `core/models/digest.py`, `utils/digest_db.py` et `api/endpoints/digest.py` ;
- mobile : les mêmes champs dans `mobile/src/types/digest.ts`, et le composant `InsightCard` de l'écran digest.

Le contrat se réduit à **une liste ordonnée d'identifiants de médias** pour la période, plus ce que la pagination exige réellement.

## Le Digest ne génère plus rien

`trigger_summary_short_generation` de `media_summarizer/core/services/digest_service.py` (vers la ligne 252) est supprimé. Avec lui disparaissent `DigestStatus.PENDING` et `DigestStatus.READY`, qui n'existaient que pour suivre cette pré-génération, ainsi que `summary_short_artifact_id` et `summary_short_status` de `DigestMediaItem`.

Conséquence assumée par l'owner : dans le Digest, l'onglet IA d'un média affiche ses tuiles « à générer » tant qu'elles ne l'ont pas été ailleurs, et une génération lancée depuis le Digest débite le quota comme depuis la page Média. C'est le comportement normal de la page, et c'est voulu.

## Période vide

Décision owner : **aucun enregistrement de digest n'est écrit** pour une période sans média, et l'onglet affiche un **état vide sobre**. Pas de repli sur une période précédente remplie, pas de bascule automatique sur Weekly. Aucune notification ne part non plus (traité dans la tâche notifications).

## Le risque technique à traiter

Une page Média scrolle verticalement et porte ses propres onglets ; l'imbriquer dans un pager horizontal expose à des conflits de gestes sur iOS. La Revue des non-classés ne rencontre pas le problème parce que ses cartes sont courtes (`MAX_BULLET_LINES = 3`). C'est le point dur de la tâche et il doit être traité explicitement, pas découvert à l'exécution.

Volume : une période chargée peut compter plusieurs dizaines de médias, chacun avec son `MediaStatusResponse` et ses artefacts. Le montage et le chargement doivent être paresseux — fenêtre autour de la carte courante — faute de quoi l'ouverture du Digest déclenche autant de requêtes que de médias.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Aucun champ conservé « pour compatibilité », aucun rendu de repli sur l'ancienne carte, aucune double lecture du contrat. Les anciens champs sont retirés du modèle, de l'endpoint et des types mobile dans la même passe. La bascule journée calendaire → 24 h glissantes remplace la logique existante, elle ne coexiste pas avec elle.

## Notes pour l'owner (pas des ACs)

- La vérification visuelle du carrousel et du comportement des gestes demande un build : elle t'appartient.
- Le déploiement du contrat réduit se joue au push sur `main`, après la fin de l'agent.
- L'envoi effectif à 18h30 et 9h30 relève de la tâche notifications ; ici, seules les fenêtres de calcul changent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'onglet Digest rend un carrousel horizontal paginé où chaque page est le composant partagé de task-365, chrome désactivé, affichant la page Média complète avec ses onglets Reader et IA
- [ ] #2 Aucune action Jeter, Approfondir ou Ranger n'est rendue dans le Digest, et un header unique Daily/Weekly est rendu au-dessus du pager, le sélecteur Daily/Weekly étant conservé
- [ ] #3 Daily liste les médias enregistrés dans la journée et Weekly ceux de la semaine, dans l'ordre chronologique croissant, vérifiable contre les enregistrements réels de DynamoDB -dev
- [ ] #4 Seules la carte courante et ses voisines immédiates sont montées et voient leur donnée chargée : l'ouverture du Digest ne déclenche pas une requête par média de la période
- [ ] #5 Le comportement des gestes est traité explicitement : le scroll vertical de la page Média et le changement d'onglet Reader/IA n'empêchent pas la pagination horizontale, et les notes d'implémentation décrivent le mécanisme retenu
- [ ] #6 trigger_summary_short_generation est supprimé de digest_service.py, et le Digest ne déclenche plus aucune génération d'artefact, vérifiable sur -dev en constatant qu'aucun artefact n'est créé à l'assemblage d'un digest
- [ ] #7 DigestStatus.PENDING et READY, summary_short_artifact_id et summary_short_status ne subsistent plus dans core/models/digest.py ni dans utils/digest_db.py
- [ ] #8 Les champs insights, themes, stats, summary_excerpt et read_time_minutes sont retirés du modèle backend, de api/endpoints/digest.py et de mobile/src/types/digest.ts, et le composant InsightCard est supprimé
- [ ] #9 Une période sans média enregistré n'écrit aucun enregistrement de digest et l'onglet affiche un état vide, sans repli sur une autre période ni bascule automatique sur Weekly
- [ ] #10 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés

- [ ] #11 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
