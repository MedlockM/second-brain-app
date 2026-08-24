---
id: task-316
title: >-
  Analyser et améliorer les prompts de génération des artefacts (notes, résumés,
  flashcards, quiz)
status: Done
assignee: []
created_date: '2026-08-23 00:38'
updated_date: '2026-08-23 18:32'
labels:
  - artifacts
  - prompt-engineering
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Les artefacts générés actuellement (notes, résumés, flashcards, quiz) sont corrects mais perfectibles. Personne n'a encore fait d'analyse structurée des prompts qui les génèrent pour identifier leurs faiblesses (qualité du contenu généré, pertinence, formulation, structure) ni proposé d'améliorations ciblées.

Cette tâche couvre uniquement l'analyse et l'amélioration des prompts eux-mêmes (le texte envoyé au LLM et la logique de génération associée), pas l'expérience utilisateur autour des artefacts une fois générés — ce point est traité séparément.

Périmètre :
- Recenser tous les prompts de génération d'artefacts actuellement en usage dans le code (workers/générateurs concernés)
- Analyser leurs forces et faiblesses : qualité et pertinence du contenu produit, respect du format attendu, robustesse face à des transcripts variés (longueur, langue, domaine)
- Comparer avec des échantillons réels de sortie (artefacts déjà générés en dev) pour étayer l'analyse par des exemples concrets
- Proposer des améliorations concrètes et justifiées par prompt (reformulation, structuration, contraintes de format, exemples few-shot, etc.)
- Documenter les recommandations de façon exploitable pour une implémentation ultérieure
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un inventaire des prompts de génération d'artefacts actuellement en usage est produit, avec leur emplacement dans le code
- [x] #2 Pour chaque prompt, une analyse écrite couvre au moins : points faibles observés, exemples concrets tirés de sorties réelles en dev, et proposition d'amélioration
- [x] #3 Les propositions d'amélioration sont formulées de façon suffisamment précise pour qu'une tâche d'implémentation puisse les reprendre directement
- [x] #4 Le document d'analyse est accessible dans le repo (ex. docs/) et référencé depuis la tâche
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Document livré : `docs/research/task-316-artifact-prompts/README.md` (`owner_decision: pending`, en attente de l'arbitrage owner sur les recommandations à retenir).

## Base de preuves

- Code lu à `82fbee6`. Aucun fichier du générateur d'artefacts n'était modifié dans le working tree.
- 44 artefacts réels tirés des cinq buckets `-dev`, dont **14 produits par les prompts actuels** (`generator_version` en `:prompt-v2`), plus les transcripts sources correspondants, ce qui permet de calculer des ratios sortie/source et de vérifier la fidélité au texte.
- Configuration réellement déployée vérifiée sur la Lambda `media-summarizer-worker-artifact_generator-dev` (variables d'env) et sur le secret runtime (noms de clés uniquement, aucune valeur sensible écrite ici) : `OPENAI_MODEL = gpt-5.4-nano-2026-03-17`, aucune surcharge `*_LLM_MODEL` par type.
- Aucun appel LLM émis, aucun fichier de production modifié.

## Inventaire (AC #1)

Cinq prompts, un par type, tous assemblés par `corpus.build_prompt()` (préambule → corpus tagué `[S1]…[Sn]` → instructions du type) :
`summary_short.py:66`, `summary_detailed.py:89`, `notes.py:106`, `flashcards.py:69`, `quiz.py:103`, plus les fragments partagés de `corpus.py` (préambule, `language_instruction`, `title_instruction`, `source_ref_instruction`) et l'enveloppe d'appel de `worker.py:101-137`. Prompt adjacent hors périmètre recensé : la traduction de transcript (`transcript_translation.py:210`).

## Principaux constats chiffrés (AC #2)

- **Volume de sortie décorrélé de la source, et inversé** : ×8,4 sur un transcript de 414 o (`summary_detailed` a produit 12 « key points », 5 thèmes et 5 citations depuis dix répliques), contre ×0,17 sur une source de 28,9 ko.
- **« depending on content density » sans effet** : 5 questions sur 772 o, 7 et 8 sur 2 210 o, 7 et 7 sur 28 876 o — une source 13× plus grosse produit une question de moins. Les planchers `MIN_FLASHCARDS`/`MIN_QUESTIONS` = 5 sont imposés par `validate()`, donc le modèle ne peut que remplir.
- **Le remplissage viole les règles du prompt lui-même** : sur le sketch de 414 o, 10 cartes dont des cartes triviales et des réponses au conditionnel (« Il semble s'agir de… »), interdites explicitement par le prompt.
- **Biais de longueur des options de quiz : 66 % (74/112) des bonnes réponses sont l'option la plus longue** (63 % sur `prompt-v2` seul), contre 25 % attendus. `_shuffle_options()` corrige déjà le biais de position, pas celui-là.
- **39 % des questions (16/41) portent sur le document et non sur le sujet** (« Selon la source… ») — 5/5 sur un artefact.
- **Régénérer produit le même artefact** : deux quiz à 2 min d'écart couvrent les six mêmes faits ; deux autres à 6 min d'écart partagent 5 questions sur 7, dont une identique. `temperature` est inerte sur la famille `gpt-5` et le prompt ignore ce qui a déjà été produit.
- **Données périssables figées** : « eau à 25,7 °C aujourd'hui » devient une flashcard qui part ensuite en révision espacée FSRS.
- **Corpus multi-sources** : répartition 5/1/1 des questions sur un corpus 51/24/24 % ; en-tête de corpus pauvre et parfois pollué (`title: youtube:youtube_video`) ; aucune consigne pour un corpus sans thème commun.
- **3 types sur 5 (`summary_short`, `summary_detailed`, `notes`) n'utilisent pas les Structured Outputs** alors que `_supports_structured_outputs()` renvoie déjà `True` pour leur modèle.
- Aucun message `system` sur les cinq prompts.

## Ce qui n'est pas un problème de prompt

Les 2 artefacts `failed` de dev portent `"Float types are not supported. Use Decimal types instead."` — une écriture DynamoDB, corrigée le jour même. La fidélité des citations est bonne (les 5 `notable_quotes` vérifiées programmatiquement sont verbatim). `_shuffle_options()` fonctionne et aucune explication ne nomme de lettre d'option. Sur source dense et réellement pédagogique, la qualité est au rendez-vous : le défaut est la **calibration**, pas la conception.

## Recommandations (AC #3)

12 propositions numérotées P0-1 à P2-4, chacune avec son point d'intervention (fichier:ligne), le texte de contrainte à écrire et la vérification rejouable sur `-dev` :
- **P0** : quantité fonction de la matière + abaissement des planchers durs ; autorisation explicite des sections vides (le rendu mobile les gère déjà) ; interdiction du style méta-référentiel ; contrainte de calibre sur les distracteurs de quiz.
- **P1** : corpus hétérogène, couverture multi-sources quantifiée, cadrage d'`importance`, ancrage des faits datés, neutralisation des marqueurs de transcription, langue tenue jusqu'au vocabulaire, levier de diversité à la régénération.
- **P2** (à instruire avant d'agir) : Structured Outputs sur les trois types restants, instrumentation des tokens de raisonnement, alignement du repli de modèle de `notes`, réexamen du modèle de `summary_short`.

## Notes à l'owner

1. Toute modification retenue doit faire passer `prompt-v2` → `prompt-v3` dans les cinq entrées de `get_generator_version()` (`artifact_service.py:203-225`), sans quoi l'historique ne permet plus de dire quel prompt a produit quel artefact.
2. Les mesures des §2.1, §2.2, §2.4, §2.5 et §2.8 sont rejouables à l'identique après déploiement : régénérer les cinq types sur le sketch de 414 o (cas dégénéré) et sur le cours de surf de 17,7 ko (cas dense), puis recalculer les ratios.
3. La sortie est facturée 6,25× l'entrée sur `gpt-5.4-nano` : P0-1 réduit la facture en même temps que le bruit.
4. Une seule tâche d'implémentation suffit pour P0 + P1 (tout est dans `generators/` et deux fragments de `corpus.py`, sans changement de contrat ni de rendu mobile). P0-2 et P2-1 doivent en revanche être livrés ensemble, `strict: true` interdisant les champs optionnels.

Rien n'est committé : le working tree porte le chantier i18n de task-313 en cours par un autre agent, seuls `docs/research/task-316-artifact-prompts/README.md` et ce fichier de tâche relèvent de task-316.
<!-- SECTION:NOTES:END -->
