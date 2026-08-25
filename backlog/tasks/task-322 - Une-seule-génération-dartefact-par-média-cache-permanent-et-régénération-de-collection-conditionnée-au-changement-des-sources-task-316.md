---
id: task-322
title: >-
  Une seule génération d'artefact par média, cache permanent, et régénération de
  collection conditionnée au changement des sources (task-316)
status: Done
assignee: []
created_date: '2026-08-25 11:44'
updated_date: '2026-08-25 12:58'
labels:
  - artifacts
  - backend
  - mobile
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Décision de l'owner sur `docs/research/task-316-artifact-prompts/README.md` (`owner_decision: ok`) : pour un média donné, l'utilisateur ne doit pouvoir générer un artefact d'un type donné **qu'une seule fois** — d'où la possibilité d'un vrai cache. Pour un artefact de **collection**, la régénération reste possible, mais **uniquement si les sources ont changé**.

Ce n'est pas ce que le code fait aujourd'hui. Le modèle est append-only et la déduplication est purement temporelle : `build_artifact_id()` (`media_summarizer/core/services/artifact_service.py:274`) inclut un `window_index` dérivé de `DEDUP_WINDOW_SECONDS`, et `plan_artifact_generation()` (`:627`) ne regarde que la fenêtre courante et la précédente. Passé cette fenêtre, un nouveau tap produit une nouvelle entrée. Le docstring de `commit_artifact_generation()` (`:750`) le dit explicitement : « `deduplicated` means "this was the same tap" — never "we reused an older artifact" ». Le modèle `media_summarizer/core/models/media_artifact.py` assume ce choix dans son propre docstring.

## Ce qu'il faut construire

La règle unifiée est la même pour les deux scopes, ce qui simplifie plutôt que complique : **on réutilise l'artefact existant dès que l'ensemble des sources est identique, et on ne génère que lorsqu'il diffère.** Un média est une collection à une source dont l'ensemble ne change jamais — la génération unique en découle sans cas particulier.

- **Clé de réutilisation** — sortir `window_index` de `build_artifact_id()` et faire de la recherche d'un existant une recherche sans borne de temps. La clé retenue est `(user_id, scope, scope_id, artifact_type, parameters, ensemble trié des source ids)`. Le `DEDUP_WINDOW_SECONDS` et la vérification de la fenêtre précédente disparaissent : ils n'ont plus d'objet une fois la réutilisation permanente.
- **`generator_version` sort de la clé** et reste stocké dans l'enregistrement pour la traçabilité. Sinon le bump `prompt-v2` → `prompt-v3` de task-320 rouvrirait un droit de génération par version, ce qui contredit la décision. Adapte le docstring de `build_artifact_id()`, qui affirme aujourd'hui que « everything that changes the output is in the hash ».
- **Deux langues de lecture restent deux artefacts légitimes** : `parameters` porte la langue et reste dans la clé. La décision porte sur la régénération, pas sur la langue.
- **Réutilisation ≠ dédup de tap** : quand on renvoie un artefact préexistant, aucun compteur de quota ne doit être débité, et la distinction doit rester lisible dans les logs et dans ce que l'API renvoie à l'appelant (un artefact réutilisé n'est pas la même chose qu'un double tap collapsé).
- **Collection** : quand les sources ont changé depuis le dernier artefact d'un type, la génération est autorisée et l'entrée s'ajoute à l'historique append-only, qui reste tel quel. Quand elles n'ont pas changé, la demande renvoie l'artefact existant sans nouvelle génération ni débit.
- **Mobile** : l'affordance de régénération doit disparaître pour un artefact de média (`mobile/src/components/ArtifactsPanel.tsx`) et n'être proposée sur un artefact de collection (`mobile/app/media/collections/[id].tsx`) que lorsque les sources de la collection diffèrent de celles du dernier artefact. L'écran connaît déjà le `sources` snapshot de chaque entrée, qui est exactement ce qui permet cette comparaison. Mets à jour les commentaires qui décrivent l'ancien modèle (`ArtifactsPanel.tsx:122`, `collections/[id].tsx:60`).
- **Documentation** — corriger les docstrings de `media_artifact.py` et d'`artifact_service.py` qui décrivent le modèle temporel : ils deviennent faux et ce sont eux qu'un lecteur croira.

## Hors périmètre

- Les prompts : task-320 (P0) et task-321 (P1) s'en occupent. Ne touche pas aux générateurs ni à `get_generator_version()`.
- Le nettoyage des artefacts déjà présents en dev : rien à migrer, ils restent lisibles.
- Aucune notion de péremption, de fraîcheur ou de régénération automatique n'est introduite : le seul déclencheur d'une nouvelle génération de collection est un ensemble de sources différent.

## Notes à l'owner (non vérifiables par l'agent)

À vérifier après déploiement sur `-dev` : demander deux fois de suite le même type sur un média déjà généré doit renvoyer le même `artifact_id` sans nouvelle entrée dans `media_artifacts-dev` et sans débit de quota, même à plusieurs minutes d'intervalle ; sur une collection, une demande à sources inchangées doit renvoyer l'existant, et la même demande après ajout d'un média doit produire une nouvelle entrée.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 build_artifact_id() ne prend plus de window_index et n'inclut plus generator_version dans le hash ; son docstring decrit la nouvelle cle
- [ ] #2 generator_version continue d'etre enregistre sur chaque artefact pour la tracabilite
- [ ] #3 plan_artifact_generation() cherche un artefact existant pour la meme cle sans borne de temps, et DEDUP_WINDOW_SECONDS ainsi que la verification de la fenetre precedente sont supprimes
- [ ] #4 La reutilisation d'un artefact preexistant est distinguee du collapse de deux taps concurrents, dans les logs comme dans ce que l'API renvoie, et ne debite aucun quota dans les deux cas
- [ ] #5 Une demande d'artefact de collection dont les sources ont change produit une nouvelle entree dans l'historique append-only ; a sources identiques elle renvoie l'existant
- [ ] #6 Deux langues de lecture donnent toujours deux artefacts distincts
- [ ] #7 L'affordance de regeneration a disparu pour les artefacts de media dans ArtifactsPanel.tsx
- [ ] #8 L'ecran de collection ne propose la regeneration que lorsque les sources courantes different du snapshot sources du dernier artefact du type
- [ ] #9 Les docstrings de media_artifact.py et artifact_service.py, et les commentaires mobiles cites dans la description, decrivent le nouveau modele et non la dedup temporelle
- [ ] #10 ruff et mypy passent sur les fichiers Python modifies, et tsc sur les fichiers mobiles modifies
<!-- AC:END -->
