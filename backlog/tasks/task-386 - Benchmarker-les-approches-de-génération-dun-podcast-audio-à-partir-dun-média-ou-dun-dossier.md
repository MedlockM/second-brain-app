---
id: task-386
title: >-
  Benchmarker les approches de génération d'un podcast audio à partir d'un média
  ou d'un dossier
status: To Do
assignee: []
created_date: '2026-09-09 15:58'
labels:
  - benchmark
  - artifacts
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'on veut évaluer

Un **sixième type d'artefact demandable par l'utilisateur** : un podcast audio généré à partir de tout ce qu'on possède sur un média ou sur un dossier. Même surface que les cinq types actuels (`POST /api/artifacts` avec `scope` + `scope_id`), mais le livrable est de l'audio, pas du JSON.

La piste de l'owner est de reprendre le module de `https://github.com/lfnovo/open-notebook`. Ce benchmark doit **la vérifier factuellement et la confronter aux autres solutions connues**, pas la valider par défaut.

## Ce que la piste de l'owner est réellement — à vérifier dans le code, pas dans le README

Éléments relevés le 2026-09-09, à confirmer par lecture des sources :

- Le README d'`open-notebook` ne nomme **aucun** module podcast : il annonce « Advanced multi-speaker podcast generation », 1 à 4 intervenants via des *Episode Profiles*, et une couche providers `lfnovo/esperanto`.
- Le paquet PyPI **`podcast-creator`** (propriétaire PyPI `lfnovo`, **v0.12.0 du 2026-03-03**, licence **MIT**, Python ≥ 3.10.6) décrit exactement ce pipeline. Dépendances déclarées : `langgraph`, `esperanto`, `content-core`, `ai-prompter`, `moviepy`, `pydub`, `tenacity`, `tiktoken`, `pycountry`, `loguru`, `nest-asyncio`, `click`, `requests`, `python-dotenv` ; extra `ui` : `streamlit`. **Le lien avec `open-notebook` n'est pas affirmé par la page PyPI** — c'est le point à trancher en lisant les deux dépôts.
- `docs/2-CORE-CONCEPTS/podcasts-explained.md` d'`open-notebook` documente 6 étapes (sélection du contenu → profil d'épisode → configuration des intervenants → plan → dialogue → TTS), 4 providers TTS (OpenAI ~$0,015/min, Google ~$0,004/min, ElevenLabs ~$0,10/min, TTS local gratuit mais lent), **« 10+ minutes pour un épisode de 30 minutes »**, et **aucun retry automatique**.

La question n'est donc pas « copier ou non » mais **laquelle de trois options** : dépendre du paquet, copier-adapter le pipeline, ou ne réimplémenter que ce qu'on ne possède pas déjà. On possède déjà la couche corpus + prompt + LLM + sorties structurées (`workers/artifact_generator/`), et on ne possède **rien** du TTS ni de l'assemblage audio.

## Contraintes de notre stack — à prendre pour données, pas à rouvrir

1. **Un artefact est immuable et append-only**, son `artifact_id` est déterministe sur (scope, scope_id, type, `parameters`, sources triées) — `core/services/artifact_service.py:408`. Deux `parameters` différents = deux artefacts ; `parameters` identiques = réutilisation sans rien générer.
2. **Un bucket S3 par type** (`get_artifact_bucket`, `:362`; `infrastructure/terraform/modules/platform/s3.tf`), et `build_artifact_storage_key` (`:382`) **suffixe `.json` en dur**.
3. **Le worker est une image conteneur Lambda** : `artifact_generator` = **512 MB / 300 s** (`lambda_workers.tf:55-60`), `GENERATION_LEASE_SECONDS = 300` (`artifact_service.py`). Le plafond dur d'une Lambda est **900 s** — le « 10+ minutes » documenté n'y tient pas tel quel. Une seule queue pour tous les types (`get_artifact_queue`, `:374`).
4. **Il n'y a ni ffmpeg ni pydub dans l'image**, et ce n'est pas un oubli : `core/services/audio_duration_probe.py` existe précisément pour mesurer une durée « without an ffmpeg dependency ».
5. **`GET /api/artifacts/{id}/content` inline du JSON parsé** (`api/endpoints/artifacts.py:578`) — ce n'est pas un canal de livraison pour de l'audio.
6. **La langue de sortie est celle du lecteur** : `current_user.reading_language` (`artifacts.py:272`) → `language_instruction` (`generators/corpus.py:95`). **11 locales** dans `mobile/src/i18n/locales.ts`, dont `ar` (RTL) et `hi`.
7. **Modèle de consommation tranché** (task-287, validé le 2026-08-18) : on ne compte **que des minutes**. Une génération sur un média est **gratuite**, une génération sur un dossier convertit à **1 minute pour 5 sources** (`quota_enforcer.check_generation_allowed:757`, `minutes_for_folder_sources`). Le podcast serait **le premier artefact dont le coût dépend de la longueur de la sortie**, pas de la taille du corpus : la règle actuelle ne le couvre pas.
8. **Plafonds de corpus existants** : `MAX_FOLDER_SOURCES = 25`, `MAX_FOLDER_CORPUS_TOKENS = 120_000`.
9. **Collision de vocabulaire** : « podcast » désigne déjà un épisode ingéré depuis PodcastIndex (`api/endpoints/podcasts.py`, `podcast_search.py`, `workers/podcastindex_resolution_worker.py`). L'identifiant du type doit être choisi en conséquence.
10. **L'app mobile n'a aucune dépendance de lecture audio** (`mobile/package.json` : ni `expo-av` ni `expo-audio`).

## Les familles de solutions à couvrir

Au minimum, et en disant honnêtement pour chacune si une API publique existe :

- **Pipelines open source** : `podcast-creator` / `open-notebook`, `podcastfy`, et ce que la recherche fait remonter.
- **Fournisseurs TTS qu'on piloterait nous-mêmes** : OpenAI, Google Gemini (TTS multi-locuteurs en un appel), ElevenLabs (dont text-to-dialogue), **Deepgram Aura** (déjà notre fournisseur STT — un fournisseur de moins à contractualiser), **Amazon Polly** (déjà dans le compte AWS et l'IAM), Azure, Cartesia, PlayHT, Hume, et l'auto-hébergé (Kokoro, XTTS, Chatterbox).
- **API clés en main « documents → podcast »** : NotebookLM / Illuminate, Wondercraft, Jellypod, Autocontent, Podcastle, etc.

## Les dimensions à chiffrer

1. **Coût** en EUR par épisode de 5, 15 et 30 minutes, **script LLM et TTS séparés**.
2. **Latence** sourcée, et l'**enveloppe de calcul** qu'elle impose : ça tient dans 900 s, ou il faut choisir entre relever mémoire/timeout, éclater par segment sur la queue existante, Step Functions, ou Fargate. Le benchmark doit en nommer une.
3. **Assemblage audio** : le fournisseur rend-il **un** fichier pour un dialogue multi-voix, ou N segments à concaténer ? Si concaténation, par quel mécanisme et à quel prix dans l'image du worker — sachant le point 4 ci-dessus.
4. **Couverture linguistique** des 11 locales, qualité de voix par langue, `ar` et `hi` en particulier.
5. **Livraison des octets** : URL présignée, proxy de streaming, CloudFront ; format, débit, poids d'un épisode de 30 min, support du seek (requêtes Range).
6. **Comptage** : quelle unité débite un podcast, face à la décision task-287 et à la conversion actuelle. Chiffres à l'appui.
7. **`parameters` à exposer** (durée cible, nombre d'intervenants, ton, voix) et la conséquence sur `build_artifact_id`.
8. **Identifiant du type**, vu la collision du point 9.
9. **Licence et CGU** : licence du candidat OSS retenu, ce que les CGU du fournisseur disent de la propriété et de la rediffusion de l'audio synthétisé. Le clonage de voix est hors sujet.
10. **Modes d'échec** : audio partiel, retry après N segments déjà payés, cohérence avec le bail de génération.
11. **Poids des dépendances** : ce que `langgraph` + `moviepy` + `pydub` ajoutent à une image Lambda (taille, cold start) face au SDK du fournisseur seul.

## Ce que ce benchmark ne tranche pas

- L'UI du lecteur mobile — sa propre tâche.
- Une génération automatique en fin d'ingestion : non, le type est demandé par l'utilisateur.
- Le clonage de la voix de l'utilisateur.

## Notes à l'owner (pas des ACs)

1. Deux tâches d'implémentation dépendront de ce benchmark et **déféreront au champ `Decision`** du README : la recommandation doit être lisible seule.
2. La clé du fournisseur retenu devra être provisionnée (secret + env runtime). Le benchmark nomme **quels** credentials sont nécessaires, jamais leur valeur — dépôt public.
3. Si le verdict est « aucune solution ne tient dans l'enveloppe actuelle », c'est un résultat exploitable : il faut alors que le README dise ce que coûte l'enveloppe qu'il faudrait.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tableau comparatif couvrant les trois familles (pipelines OSS, fournisseurs TTS pilotés par nous, API clés en main) et au moins 8 solutions au total, avec pour chacune : coût, latence, langues, multi-voix, format de sortie. Chaque chiffre porte une URL et une date de consultation.
- [ ] #2 La piste de l'owner est tranchée factuellement : ce qu'`open-notebook` utilise réellement pour le podcast (lu dans les sources du dépôt, pas dans le README), sa licence, ses dépendances, et l'arbitrage entre les trois options — dépendre du paquet, copier-adapter, ou ne réimplémenter que ce qu'on ne possède pas déjà.
- [ ] #3 Coût en EUR par épisode de 5, 15 et 30 minutes pour chaque candidat de la short-list, coût du script LLM et coût du TTS séparés.
- [ ] #4 Une enveloppe de calcul est nommée : l'approche retenue tient ou ne tient pas dans le plafond de 900 s d'une Lambda, et sinon laquelle de (relever mémoire/timeout, éclatement par segment sur `artifact-generator-queue`, Step Functions, Fargate) est recommandée — avec les latences sourcées qui l'imposent.
- [ ] #5 La question de l'assemblage est répondue : un fichier rendu par le fournisseur ou N segments à concaténer, et si concaténation, par quel mécanisme et ce qu'il ajoute à l'image du worker — explicitement face au fait que ffmpeg en est absent par choix (`core/services/audio_duration_probe.py`).
- [ ] #6 Couverture linguistique documentée pour les 11 locales de `mobile/src/i18n/locales.ts`, avec un verdict explicite sur `ar` et `hi`.
- [ ] #7 Une recommandation de livraison des octets audio (le point d'entrée `GET /api/artifacts/{id}/content` inline du JSON et ne peut pas les servir) : canal, format, débit, poids d'un épisode de 30 min, support du seek.
- [ ] #8 Une règle de comptage proposée, écrite face à la décision validée de task-287 (« on ne compte que des minutes ») et à la conversion actuelle `minutes_for_folder_sources` (1 minute pour 5 sources, média gratuit), chiffres à l'appui.
- [ ] #9 Un identifiant de type d'artefact proposé — vu que « podcast » désigne déjà un épisode ingéré depuis PodcastIndex — et le jeu de `parameters` à exposer, avec sa conséquence énoncée sur `build_artifact_id` (deux jeux différents = deux artefacts, jeu identique = réutilisation).
- [ ] #10 Une section licence et CGU : licence du candidat OSS retenu, ce que les CGU du fournisseur retenu disent de la propriété et de la rediffusion de l'audio généré. Le clonage de voix y est déclaré hors périmètre.
- [ ] #11 Une section modes d'échec et retry : ce qu'il advient des segments déjà synthétisés et payés quand la génération échoue, et la cohérence avec le bail de génération du worker.
- [ ] #12 Aucun chiffre inventé : tout nombre non sourcé est marqué comme estimation et accompagné de sa méthode de calcul.
- [ ] #13 Le livrable est `docs/research/task-386-podcast-artifact-generation/README.md`, front-matter `owner_decision: pending` et section `Owner Validation` vide (champs `Decision` et `Validated at` prêts à être remplis).
<!-- AC:END -->
