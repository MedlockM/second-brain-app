---
id: task-391
title: >-
  Générer l'aperçu de source sur une sauvegarde dédupliquée et borner l'âge d'un
  pending
status: To Do
assignee: []
created_date: '2026-09-10 11:21'
labels:
  - backend
  - media_summarizer
  - bug
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui est observé

Un aperçu de source (« review blurb ») peut rester indéfiniment annoncé comme en cours de rédaction, ou annoncé indisponible alors que le contenu existe ailleurs. Un correctif mobile a déjà été intégré : il rend l'écran honnête (plus de spinner éternel, état terminal atteint, reprise au retour sur l'écran). Il ne fait pas apparaître les aperçus manquants — la cause qui fabrique les lignes incohérentes est en amont, dans `media_summarizer/`.

## Cause établie

Deux défauts indépendants, côté backend :

1. **Sauvegarde dédupliquée sans blurb.** `finalize_deduplicated_save` (`core/services/durable_media_service.py`) et ses deux appelants n'appellent jamais `trigger_review_blurb_generation` ni `copy_review_blurb_to_library_row`. Le scope de l'artefact étant identique entre deux sauvegardes du même contenu par le même utilisateur, l'API voit l'artefact `READY` et répond `status: "ready"`, tandis que la nouvelle ligne `user_media` n'a jamais reçu le blurb — le contrat annonce un contenu qui n'existe pas. Pour un *autre* utilisateur, il n'y a rien dans son scope et le job est terminal : l'aperçu est annoncé indisponible.
2. **Un `pending` sans borne d'âge.** Une entrée bloquée en `queued` (sans `awaiting_expires_at`) ou en `generating` n'est reprise par aucun sweeper et n'expire jamais : elle reste `pending` indéfiniment côté contrat.

## Périmètre

Déclencher la génération et la copie du blurb dans `finalize_deduplicated_save`, pour les deux cas (même utilisateur, autre utilisateur). Borner l'âge d'un `pending` côté API, de sorte qu'une entrée bloquée finisse par répondre un statut terminal au lieu d'un `pending` perpétuel.

Aucun benchmark : correction de bug, la forme est claire, aucun choix de fournisseur ni d'architecture ouvert.

## Notes au propriétaire (hors critères d'acceptation)

Le correctif ne prend effet qu'après déploiement, qui a lieu au push sur `main`, après le passage de l'implémenteur. Vérification manuelle ensuite : enregistrer deux fois la même source depuis le même compte, puis depuis un second compte, et constater que l'aperçu apparaît dans les deux bibliothèques. Origine : retour d'un beta testeur TestFlight sur le build 9.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 finalize_deduplicated_save déclenche la génération de l'aperçu et sa copie sur la nouvelle ligne user_media, pour une re-sauvegarde par le même utilisateur comme pour une sauvegarde par un autre utilisateur ; le chemin de code est câblé depuis les deux appelants existants.
- [ ] #2 Une entrée d'aperçu bloquée en queued ou generating au-delà d'une borne d'âge explicite n'est plus rapportée comme pending par l'API : elle aboutit à un statut terminal.
- [ ] #3 ruff et mypy passent sans erreur sur les modules touchés.
- [ ] #4 Une vérification directe contre le DynamoDB -dev réel, documentée dans les notes d'implémentation, montre qu'après une sauvegarde dédupliquée la ligne user_media porte bien le review_blurb.
<!-- AC:END -->
