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
- [x] #1 Tableau comparatif couvrant les trois familles (pipelines OSS, fournisseurs TTS pilotés par nous, API clés en main) et au moins 8 solutions au total, avec pour chacune : coût, latence, langues, multi-voix, format de sortie. Chaque chiffre porte une URL et une date de consultation.
- [x] #2 La piste de l'owner est tranchée factuellement : ce qu'`open-notebook` utilise réellement pour le podcast (lu dans les sources du dépôt, pas dans le README), sa licence, ses dépendances, et l'arbitrage entre les trois options — dépendre du paquet, copier-adapter, ou ne réimplémenter que ce qu'on ne possède pas déjà.
- [x] #3 Coût en EUR par épisode de 5, 15 et 30 minutes pour chaque candidat de la short-list, coût du script LLM et coût du TTS séparés.
- [x] #4 Une enveloppe de calcul est nommée : l'approche retenue tient ou ne tient pas dans le plafond de 900 s d'une Lambda, et sinon laquelle de (relever mémoire/timeout, éclatement par segment sur `artifact-generator-queue`, Step Functions, Fargate) est recommandée — avec les latences sourcées qui l'imposent.
- [x] #5 La question de l'assemblage est répondue : un fichier rendu par le fournisseur ou N segments à concaténer, et si concaténation, par quel mécanisme et ce qu'il ajoute à l'image du worker — explicitement face au fait que ffmpeg en est absent par choix (`core/services/audio_duration_probe.py`).
- [x] #6 Couverture linguistique documentée pour les 11 locales de `mobile/src/i18n/locales.ts`, avec un verdict explicite sur `ar` et `hi`.
- [x] #7 Une recommandation de livraison des octets audio (le point d'entrée `GET /api/artifacts/{id}/content` inline du JSON et ne peut pas les servir) : canal, format, débit, poids d'un épisode de 30 min, support du seek.
- [x] #8 Une règle de comptage proposée, écrite face à la décision validée de task-287 (« on ne compte que des minutes ») et à la conversion actuelle `minutes_for_folder_sources` (1 minute pour 5 sources, média gratuit), chiffres à l'appui.
- [x] #9 Un identifiant de type d'artefact proposé — vu que « podcast » désigne déjà un épisode ingéré depuis PodcastIndex — et le jeu de `parameters` à exposer, avec sa conséquence énoncée sur `build_artifact_id` (deux jeux différents = deux artefacts, jeu identique = réutilisation).
- [x] #10 Une section licence et CGU : licence du candidat OSS retenu, ce que les CGU du fournisseur retenu disent de la propriété et de la rediffusion de l'audio généré. Le clonage de voix y est déclaré hors périmètre.
- [x] #11 Une section modes d'échec et retry : ce qu'il advient des segments déjà synthétisés et payés quand la génération échoue, et la cohérence avec le bail de génération du worker.
- [x] #12 Aucun chiffre inventé : tout nombre non sourcé est marqué comme estimation et accompagné de sa méthode de calcul.
- [x] #13 Le livrable est `docs/research/task-386-podcast-artifact-generation/README.md`, front-matter `owner_decision: pending` et section `Owner Validation` vide (champs `Decision` et `Validated at` prêts à être remplis).
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-09-09, mode **initial** (no `docs/research/task-386-*` directory existed, so no
owner-rejected README and no complement request to integrate).

Deliverable: `docs/research/task-386-podcast-artifact-generation/README.md`, front-matter
`owner_decision: pending`, `Owner Validation` section left empty for the owner. **The
recommendation awaits the owner's validation** — the task stays `To Do` and is not marked Done
by this agent.

Recommendation in one line: **drive Azure AI Speech batch synthesis directly over REST** from the
existing `artifact_generator`, feeding it one SSML document with several `<voice>` elements, and
**adopt nothing from `podcast-creator` / `open-notebook`**.

What was settled, with the load-bearing findings:

- **The owner's lead is factually correct about which package, and it is still rejected.**
  `open-notebook` 1.14.0 (MIT) has no podcast module of its own: it declares
  `podcast-creator>=0.12.0,<1` and calls `from podcast_creator import configure, create_podcast`.
  `podcast-creator` 0.12.0 (MIT) synthesises **one audio file per dialogue turn**
  (`nodes.py::generate_all_audio_node`, batches of `TTS_BATCH_SIZE`, default 5) and stitches them
  with **moviepy** (`core.py::combine_audio_files`, `concatenate_audioclips`). That stitching is
  its entire unique contribution over what this repo already owns — and it is the one thing the
  worker image must not gain.
- **Dependency weight measured, not estimated.** Both wheel closures resolved from scratch for
  `linux/aarch64` + CPython 3.12: **70 wheels / 55.8 MB today** vs **149 wheels / 194.4 MB** with
  `podcast-creator` = **+138.6 MB, 3.48x**. Largest additions: `nodejs-wheel-binaries` 60.59 MB (a
  whole Node.js runtime), `imageio-ffmpeg` 25.63 MB (ships an ffmpeg binary), `pymupdf` 25.10 MB,
  `numpy` 15.67 MB, `pandas` 10.49 MB. **Six of those wheels have no glibc-2.17 build**, so
  adoption would first require migrating the worker off the Amazon Linux 2 base image. The pillow
  collision is empirical: our closure resolves 12.2.0, theirs 11.3.0 — and `open-notebook` itself
  carries an `override-dependencies = ["pillow>=12.2.0"]` workaround for open security advisories
  caused by exactly that cap.
- **The assembly question disappears rather than being answered.** Azure batch synthesis renders
  **one** file, either from one SSML document with several `<voice>` elements or via
  `concatenateResult: true`. `<speak>`/`<voice>` markup is documented as **not billable**. So: no
  ffmpeg, no pydub, no moviepy, no Speech SDK — **zero new Python packages**, which keeps
  `audio_duration_probe.py`'s ffmpeg-free invariant intact. The batch response even returns
  `durationInMilliseconds`, so nothing needs probing.
- **Every rival forces per-turn synthesis.** Polly does not support the `<voice>` SSML tag at all
  and truncates `SynthesizeSpeech` audio at 10 minutes; Deepgram caps at 2 000 characters;
  ElevenLabs Text-to-Dialogue advises <=2 000; Gemini is capped at ~21.3 minutes per call by its
  32 000-token session window, allows 2 speakers, and returns headerless PCM; Azure's own
  real-time endpoint stops at 10 minutes. Cartesia (44 languages, best coverage found) also takes
  one voice per call.
- **Language coverage decides it.** All 11 locales of `mobile/src/i18n/locales.ts` are served by
  Azure Neural with a verified Female/Male pair each. `ar`: 32 voices across 16 Arabic locales,
  exactly 1F + 1M each, no HD tier — enough for two hosts and not one voice more. `hi-IN`: 9
  Standard (5M/4F) plus 8 MAI-Voice-2 HD/HD-Flash entries, fully served. Disqualifiers found:
  **Deepgram Aura covers 7 languages only** (so our own STT provider cannot serve this), **Polly in
  `eu-west-3` has no `hi-IN` voice at all**, Kokoro-82M has no `de`/`nl`/`ar`.
- **Compute envelope named: unchanged.** 512 MB / 300 s on the existing unified
  `artifact-generator-queue`, submit-then-poll modelled on `apify_orchestration` + the delayed-SQS
  `apify_backstop`. Azure batch is asynchronous at p50 10-20 s / p95 <=120 s, so nothing approaches
  the 900 s Lambda ceiling — versus open-notebook's documented "10+ minutes for a 30-minute
  episode", which does not fit. No memory bump, no per-segment fan-out, no Step Functions, no
  Fargate. The single code-level constraint: **`GENERATION_LEASE_SECONDS` must be re-armed on every
  poll hop**, else a multi-hop job looks abandoned and Azure is paid twice.
- **Metering derived from task-287's own formula**, not invented: `round(real_cost / 0.00664)`
  gives 13 / 33 / 63 metered minutes for a 5 / 15 / 30-minute episode; the proposed closed form
  `2 x target_minutes + 5` charges 15 / 35 / 65, covering with a 1.15x worst-case margin (better
  than the 1.5x already accepted in task-287's table). The `+5` happens to equal what
  `minutes_for_folder_sources` already charges for a full 25-source folder. **One flagged departure:
  media-scope generation cannot stay free for this type** (EUR 0.0866 vs the EUR 0.0005-0.0032 that
  justified the free row). **One product finding: a 30-minute episode costs 65 metered minutes and
  therefore does not fit at all inside Reader's 60**, hence the recommendation to expose 5 and 15
  minutes only.
- **Type identifier proposed: `audio_digest`** (verified absent from `media_summarizer/` and
  `mobile/src/`), with closed-enum `parameters` (`target_minutes` in {5,15}, `hosts` in {1,2},
  `tone`) precisely because `build_artifact_id` hashes `parameters` — an open integer or free-text
  value would let one screen mint unbounded distinct paid artifacts. `build_artifact_storage_key`
  must stop hard-coding `.json`.
- **Byte delivery**: presigned S3 GET via the existing `utils/s3.generate_presigned_url`; Range
  seeking verified empirically against a `-dev` bucket (206 / `Accept-Ranges: bytes` /
  `Content-Range`). `audio-24khz-48kbitrate-mono-mp3` = 1.8 / 5.4 / 10.8 MB; `eu-west-3` storage,
  egress and GET costs are three orders of magnitude below synthesis.
- **Licence/ToS**: podcast-creator and open-notebook MIT, podcastfy Apache-2.0, Kokoro Apache-2.0 —
  no licence obstacle anywhere, the rejection is purely engineering. Microsoft Product Terms:
  "Output Content is Customer Data", "Microsoft does not own Customer's Output Content". Batch input
  text and results are stored in Azure storage for 168 h by default, so **the worker must `DELETE`
  the job** after download. Voice cloning declared out of scope, which keeps us clear of the whole
  custom/personal-voice regime.
- **Two things deliberately left open and marked as such**: the Azure CJK character-doubling factor
  (sourced, but no vendor publishes chars/min for CJK speech, so no factor is computed — the
  implementation should log `neuralCharacters` to make it measurable), and the two-host prompt
  design.

AC #12 discipline: the only estimate the cost tables rest on is **1 000 billable characters ~ 1
minute of speech**, labelled ESTIMATE with its anchor (Azure's documented per-voice
`WordsPerMinute`, sample values 139-293) and its counter-datum (Microsoft's own 29-char/2 500 ms
batch example implies 696 chars/min, but it is a single five-word sentence). Because per-character
pricing is linear, every TTS figure rescales by one multiplication if the owner prefers another
basis. Two further numbers are flagged as estimates in place: the Cartesia per-minute derivation,
and `gpt-4o-mini-tts` marked **not computable** rather than guessed.

Credentials the implementation will need (names only, values never in the repo): an Azure **Speech**
resource in **France Central**, tier **Standard S1** (not Free F0 — batch synthesis returns HTTP 400
for F0 there) — its key as a secret, its region and resource name as runtime config. Portal path
recorded in the README section 15.

Owner note carried in the README, not as an AC: the first end-to-end run can only happen after the
key is provisioned and the worker image is redeployed on a push to `main`.
<!-- SECTION:NOTES:END -->
