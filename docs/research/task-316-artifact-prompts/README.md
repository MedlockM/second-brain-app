---
owner_decision: ok
---

# Analyse des prompts de génération des artefacts (task-316)

## Owner Validation

**Decision**: je valide toutes tes recommandations exceptée celle concernant la regénération : en fait il faut que pour un media donné l'use rne puisse générer l'artefact qu'une seule fois. Mais il faut que cet artefact soit exhaustif (par exemple le quiz doit adapter sa longueur pour couvrir tous les points du media). Donc pas de regénération au niveau d'un media, et donc possibliité d'utilliser le principe de cache. Ensuite concernant les artefacts de collection l'user doit avoir la possibilité de regénérer uniquement si les sources ont changé.
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Base de preuves

- **Code lu** à `82fbee6` (branche `main`). Aucun fichier du générateur d'artefacts n'était modifié dans le working tree au moment de la lecture.
- **Sorties réelles** : les 44 artefacts présents dans les buckets `-dev`
  (`media-summarizer-{flashcards,notes,quiz,summary-detailed,summary-short}-125313707865-dev`),
  dont **14 produits par les prompts actuels** (`generator_version` en `:prompt-v2`, générés
  entre le 2026-08-18 et le 2026-08-21). Les 30 autres sont antérieurs et servent uniquement
  aux mesures d'agrégat quand c'est signalé.
- **Transcripts sources** correspondants, téléchargés depuis
  `media-summarizer-transcripts-125313707865-dev`, pour pouvoir vérifier la fidélité des
  sorties et calculer les ratios volume-sortie / volume-source.
- **Configuration réellement déployée** : variables d'environnement de la Lambda
  `media-summarizer-worker-artifact_generator-dev` et clés (noms seulement) du secret runtime.

Aucun appel LLM n'a été émis pour produire cette analyse et aucun fichier de production n'a été
modifié.

---

## 1. Inventaire des prompts en usage

Cinq prompts, un par type d'artefact, tous construits par la même mécanique partagée.

### 1.1 Les cinq prompts de type

| Type | Prompt (fichier:ligne) | Modèle effectif en dev | Structured Outputs | Planchers de quantité |
|---|---|---|---|---|
| `summary_short` | [summary_short.py:66](../../../media_summarizer/workers/artifact_generator/generators/summary_short.py#L66) | `gpt-5-nano-2025-08-07` | **non** (`response_format_schema()` → `None`) | « 3-5 » puces, **non validé** |
| `summary_detailed` | [summary_detailed.py:89](../../../media_summarizer/workers/artifact_generator/generators/summary_detailed.py#L89) | `gpt-5.4-nano-2026-03-17` | **non** | 3-7 thèmes / 7-15 puces / 2-5 citations, **non validés** |
| `notes` | [notes.py:106](../../../media_summarizer/workers/artifact_generator/generators/notes.py#L106) | `gpt-5.4-nano-2026-03-17` | **non** | aucun |
| `flashcards` | [flashcards.py:69](../../../media_summarizer/workers/artifact_generator/generators/flashcards.py#L69) | `gpt-5.4-nano-2026-03-17` | oui | `MIN_FLASHCARDS=5` / `MAX_FLASHCARDS=15`, **validés** (rejet sous 5, troncature au-dessus de 15) |
| `quiz` | [quiz.py:103](../../../media_summarizer/workers/artifact_generator/generators/quiz.py#L103) | `gpt-5.4-nano-2026-03-17` | oui | `MIN_QUESTIONS=5` / `MAX_QUESTIONS=10`, **validés** |

Modèles vérifiés sur l'infrastructure : le secret runtime porte `OPENAI_MODEL =
gpt-5.4-nano-2026-03-17` et **aucune** clé `*_LLM_MODEL` par type. Les quatre types qui
retombent sur `OPENAI_MODEL` utilisent donc bien `gpt-5.4-nano`, et `summary_short` utilise son
littéral `gpt-5-nano-2025-08-07`.

### 1.2 Le squelette partagé — [corpus.py](../../../media_summarizer/workers/artifact_generator/generators/corpus.py)

Tout prompt est assemblé par `corpus.build_prompt()` ([corpus.py:57](../../../media_summarizer/workers/artifact_generator/generators/corpus.py#L57)) dans cet ordre :

```
PROMPT_PREAMBLE                      (corpus.py:23)  — identique pour les 5 types
===== SOURCES =====
[S1] | title: … | language: …
<texte intégral de la source 1>
…
===== END OF SOURCES =====

<instructions du type>               — le seul bloc qui varie
```

L'ordre corpus-puis-instructions est délibéré (cache de prefix OpenAI, task-269 §2.6) et **ne
doit pas être inversé** : c'est lui qui fait passer une collection de 25 sources de 0,0903 € à
0,0364 € pour les cinq types. Toute proposition ci-dessous préserve cet ordre.

Trois fragments d'instruction sont mutualisés :

- `language_instruction()` ([corpus.py:71](../../../media_summarizer/workers/artifact_generator/generators/corpus.py#L71)) — « Use {language} for the output. » ou « Use the same language as the sources. »
- `title_instruction()` ([corpus.py:79](../../../media_summarizer/workers/artifact_generator/generators/corpus.py#L79)) — titre de 3 à 80 caractères, nommant le sujet et non le type
- `source_ref_instruction()` ([corpus.py:94](../../../media_summarizer/workers/artifact_generator/generators/corpus.py#L94)) — obligatoire pour les citations, optionnel ailleurs

### 1.3 Ce que le worker fait de ce prompt — [worker.py:101-137](../../../media_summarizer/workers/artifact_generator/worker.py#L101)

- Le prompt part **entièrement dans un unique message `user`** ([worker.py:122](../../../media_summarizer/workers/artifact_generator/worker.py#L122)). Il n'y a **aucun message `system`**.
- `temperature` est **délibérément omise** pour la famille `gpt-5` ([worker.py:130-136](../../../media_summarizer/workers/artifact_generator/worker.py#L130)). Comme les cinq types utilisent aujourd'hui un modèle `gpt-5*`, `LLM_TEMPERATURE` est **inerte** sur l'ensemble du pipeline.
- `prompt_cache_key` est un hash de (scope, scope_id, clés S3 des transcripts) ([artifact_service.py:812](../../../media_summarizer/core/services/artifact_service.py#L812)) : il route les cinq requêtes d'une même génération vers le même cache.
- `response_format` n'est posé que si le modèle le supporte **et** que le générateur fournit un schéma — donc pour `flashcards` et `quiz` uniquement.

### 1.4 Prompts adjacents, hors périmètre

- **Traduction de transcript** : `_build_system_prompt()` dans [transcript_translation.py:210](../../../media_summarizer/core/services/transcript_translation.py#L210), issu du benchmark task-189. Il s'exécute *avant* la génération et détermine la langue du corpus vu par les prompts d'artefacts. Non modifié ici, mais c'est lui qui explique une partie des constats de langue (§2.9).
- **Mise en forme de transcript** ([transcript_formatting.py](../../../media_summarizer/core/services/transcript_formatting.py)) : purement algorithmique, aucun appel LLM.

---

## 2. Constats transverses

Chaque constat est chiffré sur les sorties `-dev` et illustré par un exemple réel.

### 2.1 Le volume de sortie est décorrélé de la densité de la source — et il s'inverse

Volume du JSON `content` produit rapporté au volume du transcript source, sur les 14 artefacts `prompt-v2` :

| Source | Taille | Artefact | Sortie | Ratio |
|---|---|---|---|---|
| Sketch humour couple (`d50b6bb4`) | 414 o | `summary_detailed` `art_f48f7e2d` | 3 469 o | **×8,4** |
| Sketch humour couple | 414 o | `flashcards` `art_a246929e` | 1 995 o | **×4,8** |
| Short surf « mesure des vagues » (`850fd228`) | 772 o | `quiz` `art_b122a526` | 3 742 o | **×4,8** |
| Page Le Grand Crohot (`96425307`) | 2 210 o | `notes` `art_b2b6120a` | 4 913 o | ×2,2 |
| Page Le Grand Crohot | 2 210 o | `quiz` `art_d84bfee1` | 4 774 o | ×2,2 |
| Cours de surf take-off (`3b339279`) | 17 699 o | `notes` `art_2c98f665` | 6 935 o | ×0,39 |
| Vidéo série « Tout pour la lumière » (`a03085f7`) | 28 876 o | `quiz` `art_302131eb` | 4 806 o | **×0,17** |

Le volume produit est **quasi constant** (`completion_tokens` : 495 à 1 860 pour les artefacts
mono-source) quelle que soit la matière disponible. Une source 70 fois plus grosse ne produit
pas un artefact plus riche ; une source minuscule produit un artefact qui la dépasse d'un
facteur 8.

Le point le plus net : sur un transcript de **414 octets** (dix répliques d'un sketch),
`summary_detailed` a produit **12 « key points détaillés », 5 thèmes majeurs et 5 citations
verbatim**. Les cinq citations sont fidèles au mot près — mais elles reprennent à elles seules
près de 40 % du texte source. Le « résumé exhaustif » est plus long que ce qu'il résume.

Cela coûte : les prix de [llm_pricing.py:22-25](../../../media_summarizer/core/services/llm_pricing.py#L22) donnent 0,20 $/M en entrée contre **1,25 $/M en sortie** pour `gpt-5.4-nano`. Sur cet artefact (552 tokens d'entrée, 926 de sortie), **91 % du coût est du remplissage**.

### 2.2 Les planchers de quantité sont durs, et la « densité de contenu » est lettre morte

Les prompts `flashcards` et `quiz` disent « depending on content density »
([flashcards.py:74](../../../media_summarizer/workers/artifact_generator/generators/flashcards.py#L74), [quiz.py:108](../../../media_summarizer/workers/artifact_generator/generators/quiz.py#L108)), mais l'instruction n'a aucun effet observable :

| Source | Taille | Questions produites |
|---|---|---|
| Short surf | 772 o | 5 |
| Page Le Grand Crohot | 2 210 o | **7** puis **8** (deux générations) |
| Vidéo série | 28 876 o | **7** puis **7** |

Une source **13 fois plus grosse** produit **une question de moins**. Même constat côté
flashcards : 10 cartes sur le sketch de 414 octets, 11 cartes sur la page de 2 210 octets.

La cause est structurelle et pas seulement rédactionnelle : `validate()` **rejette** une sortie
de moins de 5 cartes ([flashcards.py:155](../../../media_summarizer/workers/artifact_generator/generators/flashcards.py#L155)) ou de moins de 5 questions ([quiz.py:223](../../../media_summarizer/workers/artifact_generator/generators/quiz.py#L223)). Le modèle n'a donc pas le droit de produire moins, quelle que soit la matière ; il ne peut que remplir.

### 2.3 Aucune porte de sortie quand la source ne porte pas de matière apprenable

Les 10 cartes produites sur le sketch (`art_a246929e`) violent les règles du prompt qui les a
générées :

| Règle du prompt | Carte produite |
|---|---|
| « Do NOT generate trivial cards » | « Quelle est la relation générale des personnages au début du texte ? » → « Ils se tutoient en utilisant "chérie" et "chéri", indiquant un couple. » |
| « each question must have a single, verifiable answer » | « Pourquoi le personnage dit-il "Bon, on est sur la tête, on marche" ? » → « **Il semble s'agir** d'un moment décalé où le dialogue bascule dans le n'importe quoi. » |
| « Keep answers factual » | « À quel moment le dialogue se conclut-il avec "Attends, e pas pour rien" ? » → « Juste après une scène où il/elle se dit fier et où le dialogue **semble** s'interrompre ou se rattraper. » |

Une carte est même auto-contradictoire : « Quel prénom/le nom est donné à Petrouka dans le
sketch ? » a pour réponse « Petrouka est présenté comme l'élément censé subvenir aux besoins du
couple » — qui ne répond pas à la question posée.

Même mécanique sur `summary_short` d'un clip TikTok de 729 octets (`art_2eb072df`) : le prompt
exige « one actionable insight », donc le modèle en fabrique un, adressé à personne :
« *Mettre en avant des détails pris sur le vif et des gestes du quotidien pour générer de la
proximité et de l'humour.* » C'est un conseil de création de contenu, sur une vidéo qui n'en
donnait aucun.

Le prompt ne prévoit **aucune branche** « si la source ne porte pas de matière de ce type ».
L'écran mobile, lui, la prévoit déjà : chaque section est rendue conditionnellement
(`objectives && objectives.length > 0`, `takeaway ? … : null`, etc. dans
`mobile/app/artifacts/[artifactId].tsx`, lignes 400-570). **Une section vide s'affiche déjà correctement — c'est le prompt qui interdit de la laisser vide.**

### 2.4 66 % des bonnes réponses de quiz sont l'option la plus longue

Mesuré sur les 112 questions de quiz présentes en dev (17 artefacts, prompts v1 et v2
confondus) :

- **74 / 112 (66 %)** des `correct_answer` désignent l'option dont le texte est le plus long.
- Sur les seuls artefacts `prompt-v2` : **26 / 41 (63 %)**.
- Le hasard donnerait 25 %.

Exemple (`art_302131eb`, question 1) :

> A — Une enquête policière visant à retrouver un auteur de chanson disparu
> B — La rivalité entre deux maisons de production qui s'approprient les chansons
> C — Une compétition internationale entre écoles de musique
> **D — La vie à l'école/studio Lumière, avec l'apprentissage artistique des élèves et le travail des coachs** ← correcte

On répond juste sans avoir lu la source, en prenant systématiquement l'option la plus longue et
la plus qualifiée. `_shuffle_options()` ([quiz.py:289](../../../media_summarizer/workers/artifact_generator/generators/quiz.py#L289)) corrige déjà le biais *de position* — le modèle plaçait la bonne réponse en A parce qu'il l'écrit avant les distracteurs — mais **ne corrige pas le biais de longueur**, qui survit à la permutation. Le prompt dit « Make incorrect options plausible » sans jamais contraindre leur **calibre**.

### 2.5 39 % des questions portent sur le document, pas sur le sujet

Sur les 41 questions `prompt-v2`, **16 (39 %)** contiennent une référence explicite au document
(« Selon la source », « d'après le texte », « La vidéo précise que », « D'après le narrateur »).
Sur le short surf (`art_b122a526`), c'est **5 questions sur 5** :

> « Selon la source, pourquoi les surfeurs hawaïens… »
> « D'après la source, comment obtenir une estimation… »
> « Qu'affirme la source à propos de la pratique traditionnelle aujourd'hui ? »

Les `explanation` suivent le même pli (« La vidéo explique que… », « Le narrateur mentionne
que… »). Résultat : le quiz teste la mémoire du document, pas la compréhension du sujet — ce qui
est précisément l'inverse de ce que le prompt demande (« test comprehension of key concepts »).

Le même travers touche `summary_detailed`, qui décrit sa source au lieu de la restituer : « **Le
texte présente** un court sketch », « **Le sketch s'ouvre sur** un salut », « **Le discours
enchaîne** des justifications ».

### 2.6 Régénérer produit deux fois le même artefact

Deux quiz sur la même page Le Grand Crohot, générés à deux minutes d'intervalle
(`art_e52915082d`, 7 questions ; `art_d84bfee1c`, 8 questions) portent sur exactement les mêmes
six faits : température du jour, écart à la normale, période du maximum, période du minimum,
combinaison de début mars, écart rivage / eaux libres.

Idem pour les deux quiz sur la vidéo « Tout pour la lumière » (`art_302131eb` et
`art_081a2f49`), générés à six minutes d'écart : 5 des 7 questions couvrent le même fait, dont
une question **identique** sur le rythme de diffusion (« un épisode par jour du lundi au
vendredi »).

Le modèle d'historique est append-only : chaque « Générer » au-delà de la fenêtre de dédup de
120 s crée une **nouvelle** entrée. L'utilisateur qui régénère paie et attend pour obtenir le
même artefact. Deux mécanismes s'additionnent : `temperature` est inerte sur la famille `gpt-5`
(§1.3) et le prompt ne porte **aucune information sur ce qui a déjà été produit**.

### 2.7 Des données périssables sont figées dans un artefact permanent

La page Le Grand Crohot est un bulletin. Les artefacts en gardent la valeur du jour :

- `flashcards` `art_df043a24`, **carte n° 1** : « Quelle est la température de la mer aujourd'hui à Le Grand Crohot ? » → « Elle est de 25,7 °C. »
- `notes` `art_b2b6120a` : « **Aujourd'hui** : eau à 25,7 °C (≈ 3,9 °C au-dessus de la normale) »
- `summary_short` `art_76cad523` : « **Aujourd'hui**, l'eau est à 25,7 °C »

Cette carte part ensuite dans la file de révision espacée FSRS
([worker.py:`_init_fsrs_cards`](../../../media_summarizer/workers/artifact_generator/worker.py#L400)) : l'application ré-interrogera l'utilisateur, des mois plus tard, sur la température d'un jour d'août 2026. Le prompt ne dit rien des faits datés, et l'en-tête de corpus ne porte **aucune date** qui permettrait au modèle de les ancrer (« au 18 août 2026, … »).

Au passage, une dérive factuelle sur la même source : `summary_short` écrit « elle culmine
autour de 20-25 °C **fin mai à août** » là où la source dit « peak … on around the **10th of
August** ».

### 2.8 Corpus multi-sources : primauté de S1 et en-tête pollué

Sur le quiz à 3 sources `art_909a7ce3` (corpus 4 642 / 2 165 / 2 210 octets, soit 51 % / 24 % /
24 %), la répartition des questions est **5 / 1 / 1** — 71 % pour S1. L'instruction « Spread the
questions across the sources rather than covering only the first one » est purement qualitative
et n'obtient pas d'équilibrage.

Le `summary_short` du même corpus (`art_518ecf77`) illustre l'autre moitié du problème : les
trois sources n'ont pas de thème commun (un tutoriel longboard, une vidéo de surf, une page
météo). Le prompt impose pourtant « Cover the sources as a whole; do not summarise them one by
one ». Le résultat est un titre qui ignore deux sources sur trois — « Guide rapide du
longboard: stance, poussée, freinage et pop-up » — suivi d'une puce orpheline collée à la fin :
« Adapte ta combinaison à la température de l'eau… ». **Rien dans le prompt ne dit quoi faire
quand les sources ne partagent pas de sujet**, ce qui est le cas normal d'une collection
utilisateur.

Enfin, l'en-tête de corpus ([corpus.py:35-53](../../../media_summarizer/workers/artifact_generator/generators/corpus.py#L35)) ne porte que `title` et `language`, et le `title` est parfois du bruit : le corpus ci-dessus commence littéralement par

```
[S1] | title: youtube:youtube_video | language: fr
```

Le modèle doit nommer un sujet à partir d'un identifiant technique. Le message SQS transporte
déjà `media_item_id`, `title`, `language`, et l'entité `MediaItem` porte type, créateur et date —
disponibles sans nouvelle requête si on choisit de les propager.

### 2.9 La langue de sortie n'est tenue qu'à moitié

`language_instruction()` fixe la langue globale mais ne dit rien du vocabulaire repris de la
source. Sur une source bilingue FR/EN, les `notes` en français (`art_b2b6120a`) rendent un
glossaire à moitié anglais : « **Long sleeve shorty** », « **Spring wetsuit (ex. 3/2mm)** »,
« Capuche (**hood**) », et des puces mélangées (« Recommandation du jour : **boardshorts** ou
**shorty** »). Pour du jargon de surf c'est discutable ; pour un glossaire destiné à
l'apprentissage, l'incohérence saute aux yeux.

### 2.10 Les marqueurs de transcription sont traités comme du contenu

Les transcripts portent des marqueurs de locuteur (`>>`) et des annotations non verbales
(`[rires]`, `[musique]`, `[tousse]`). Aucun prompt n'en dit un mot. Le `summary_short` du clip
TikTok en fait un point d'analyse : « Le ton est léger et **rythmé par des rires**, des renforts
sonores et **une touche musicale à la fin**. » — c'est-à-dire un commentaire sur les artefacts
de la transcription, pas sur le contenu.

### 2.11 Trois types sur cinq n'utilisent pas les Structured Outputs alors que le modèle les supporte

`summary_short`, `summary_detailed` et `notes` renvoient `None` depuis
`response_format_schema()`. Ils s'appuient donc sur une consigne textuelle (« Output STRICT JSON
only. No markdown. No commentary. No code fences. »), sur `_strip_code_fences()` et sur un
`json.loads()` qui lève `VALIDATION_ERROR` en cas d'écart.

Or `_supports_structured_outputs()` ([worker.py:184](../../../media_summarizer/workers/artifact_generator/worker.py#L184)) renvoie **`True`** pour ces trois types, puisqu'ils tournent tous sur un modèle `gpt-5*`. Le garde-fou est disponible et n'est pas branché. Pour `notes`, un schéma strict supprimerait en prime un mode d'échec propre : l'`enum` `core|supporting` de `importance`, aujourd'hui validé *après coup* par Pydantic ([notes.py:33-40](../../../media_summarizer/workers/artifact_generator/generators/notes.py#L33)).

### 2.12 Aucun message `system`, aucun rôle assigné

Les cinq prompts partent dans un unique message `user`. Le modèle n'a pas de rôle
(« pédagogue », « auteur de fiches de révision »), pas de public cible, pas de registre. Toutes
les consignes de comportement sont noyées **après** un corpus qui peut faire 120 000 tokens.

### 2.13 Le volume de tokens facturés n'est pas expliqué par la sortie visible

`summary_short` `art_518ecf77` a consommé **2 160 `completion_tokens`** pour un `content` final
de **870 octets** (~300 tokens de français). L'écart de ~1 800 tokens n'a pas d'explication dans
la sortie stockée. L'hypothèse la plus simple est que `completion_tokens` inclut des tokens de
raisonnement, non instrumentés : `ArtifactLlmUsage` ne conserve que
`prompt_tokens`, `cached_tokens` et `completion_tokens` ([worker.py:165-181](../../../media_summarizer/workers/artifact_generator/worker.py#L165)), et laisse tomber `completion_tokens_details`.

À confirmer avant d'agir (§4, P2-2) : c'est la seule proposition de ce document qui repose sur
une inférence plutôt que sur une lecture directe.

---

## 3. Analyse par prompt

### 3.1 `summary_short` — [summary_short.py:66](../../../media_summarizer/workers/artifact_generator/generators/summary_short.py#L66)

**Ce qu'il demande** : titre, 3-5 puces d'une phrase, un `takeaway` « actionnable ».

**Points faibles observés**

1. Le `takeaway` obligatoire fabrique du conseil sur les sources qui n'en portent aucun (§2.3, exemple TikTok).
2. Sur corpus hétérogène, la consigne « ne pas résumer source par source » produit un résumé qui en ignore deux sur trois (§2.8).
3. Pas de Structured Outputs alors que le modèle les supporte (§2.11).
4. Dérive factuelle non contrainte : aucune consigne n'interdit de généraliser une valeur ponctuelle (§2.7, « fin mai à août »).
5. C'est le seul type sur `gpt-5-nano-2025-08-07` là où les quatre autres sont sur `gpt-5.4-nano` — écart hérité du benchmark task-72, jamais réévalué depuis.

**Propositions** → P0-1, P0-2, P1-1, P1-4, P2-1.

### 3.2 `summary_detailed` — [summary_detailed.py:89](../../../media_summarizer/workers/artifact_generator/generators/summary_detailed.py#L89)

**Ce qu'il demande** : titre, contexte (2-3 phrases), 3-7 thèmes, **7-15** puces détaillées, 2-5 citations verbatim avec `source_ref` obligatoire, conclusion (2-3 phrases).

**Points faibles observés**

1. C'est le prompt le plus exposé au remplissage : **×8,4** sur le sketch de 414 octets, 12 puces et 5 citations tirées de dix répliques (§2.1).
2. Style méta-référentiel systématique : « Le texte présente… », « Le sketch s'ouvre sur… » (§2.5).
3. « Be EXHAUSTIVE and THOROUGH » est une consigne de volume sans plafond relatif à la source : elle pousse dans la même direction que les planchers.
4. **Ce qui marche** : `source_ref` obligatoire sur les citations tient. Les 5 citations vérifiées sur le transcript sont exactes au caractère près, y compris les erreurs de transcription (« Je homme marié moi. »). Cette contrainte est à conserver telle quelle.

**Propositions** → P0-1, P0-3, P1-2, P1-4.

### 3.3 `notes` — [notes.py:106](../../../media_summarizer/workers/artifact_generator/generators/notes.py#L106)

**Ce qu'il demande** : titre, `objectives`, `concepts` (terme / explication / `core`|`supporting`), `key_points`, `action_items`, `glossary`.

**Points faibles observés**

1. Cinq sections toujours remplies, quelle que soit la nature de la source. Sur un bulletin météo, cela produit des « objectifs pédagogiques » inventés (« Interpréter la température de la mer actuelle et son écart saisonnier ») pour un document qui n'enseigne rien.
2. Données périssables figées, et « Aujourd'hui » écrit en toutes lettres dans une note permanente (§2.7).
3. `importance` n'est cadré par aucune règle : 8 concepts sur 8 en `core` sur le cours de surf, 4 `core` / 2 `supporting` sur la page météo. Le badge est rendu tel quel par le mobile (`mobile/app/artifacts/[artifactId].tsx`, lignes 520-537) ; s'il ne discrimine jamais, il n'informe pas.
4. Glossaire à moitié anglais dans des notes françaises (§2.9).
5. Pas de Structured Outputs, alors que l'`enum` de `importance` en bénéficierait directement (§2.11).
6. **Ce qui marche** : sur une source dense et réellement pédagogique (cours de surf, 17,7 ko), la sortie est de bonne qualité — 8 concepts justes, glossaire pertinent, `action_items` exécutables. **Le prompt n'est pas mauvais ; il est non calibré.** C'est le point le plus important de cette analyse : les corrections doivent viser la calibration, pas la réécriture.
7. Le docstring du module annonce `gpt-4o-mini-2024-07-18` et le repli du code pointe vers ce modèle ([notes.py:94-99](../../../media_summarizer/workers/artifact_generator/generators/notes.py#L94)), alors que les quatre autres types replient sur `gpt-5.4-nano`. En dev le secret runtime fournit `OPENAI_MODEL`, donc le repli n'est jamais atteint — mais si la clé disparaissait, `notes` basculerait silencieusement sur `gpt-4o-mini` **tandis que le `generator_version` enregistré continuerait d'annoncer `gpt-5.4-nano`** (`artifact_service.py` a son propre repli, différent). Divergence à supprimer.

**Propositions** → P0-1, P0-2, P1-3, P1-4, P2-3.

### 3.4 `flashcards` — [flashcards.py:69](../../../media_summarizer/workers/artifact_generator/generators/flashcards.py#L69)

**Ce qu'il demande** : 5 à 15 cartes, un concept par carte, pas de carte triviale, pas de carte ambiguë, réponses de 1 à 3 phrases.

**Points faibles observés**

1. Le plancher de 5 cartes est **imposé par le validateur**, pas seulement suggéré : sur une source sans matière, le modèle ne peut pas se conformer aux règles « pas de carte triviale / pas de carte ambiguë » **et** au plancher. Il choisit le plancher, et viole les deux autres (§2.3).
2. Cartes à réponse périssable, qui partent ensuite en révision espacée FSRS (§2.7).
3. « depending on content density » sans effet mesurable (§2.2).
4. **Ce qui marche** : sur une source factuelle, les cartes sont bonnes (11 cartes sur la page météo, une notion par carte, réponses vérifiables) et `source_ref` est correctement renseigné.

**Propositions** → P0-1, P0-2, P1-5, P1-6.

### 3.5 `quiz` — [quiz.py:103](../../../media_summarizer/workers/artifact_generator/generators/quiz.py#L103)

**Ce qu'il demande** : 5 à 10 questions, 4 options A-D, une seule correcte, explication, distracteurs « plausibles mais clairement faux ».

**Points faibles observés**

1. **Biais de longueur de l'option correcte : 66 % contre 25 % attendus** (§2.4). C'est le défaut le plus exploitable de tout le lot : il rend le quiz réussissable sans lire la source.
2. 39 % des questions portent sur le document plutôt que sur le sujet (§2.5).
3. Régénération quasi identique (§2.6).
4. Déséquilibre 5/1/1 sur corpus multi-sources (§2.8).
5. Nombre de questions insensible à la taille de la source (§2.2).
6. **Ce qui marche** : `_shuffle_options()` fait ce qu'il promet — la position de la bonne réponse est bien redistribuée, de façon déterministe et rejouable, et **aucune** des 112 explications en dev ne nomme une lettre d'option (ce qui aurait cassé au moment de la permutation). Le mécanisme est sain, il lui manque le pendant sur la longueur.

**Propositions** → P0-1, P0-4, P1-2, P1-4, P1-7.

---

## 4. Propositions, par priorité

Chaque proposition indique **où** intervenir, **quoi** écrire et **comment le vérifier** sur `-dev`.

### P0 — Corrigent les défauts mesurés les plus lourds

#### P0-1 · Rendre la quantité fonction de la matière, et abaisser les planchers durs

*Où* : `flashcards.py:17-18` et `quiz.py:19-20` (constantes), leurs `validate()` respectifs
(`flashcards.py:155`, `quiz.py:223`), et les cinq blocs d'instructions.

*Quoi* :
- Abaisser `MIN_FLASHCARDS` et `MIN_QUESTIONS` de 5 à **1**, et ne conserver en rejet dur que le cas « zéro élément ».
- Remplacer « Generate between 5 and 15 … depending on content density » par une règle explicitement adossée à la matière, du type : *« Produce one card per distinct fact or concept the sources actually teach, up to 15. If the sources teach fewer than five, produce fewer than five — never pad. A source with nothing to teach yields an empty deck. »*
- Pour `summary_detailed`, remplacer « Key points should be 7-15 detailed bullet points » par une fourchette conditionnée : *« Up to 15 bullet points, one per distinct piece of information; a short source legitimately yields two or three. Never restate the same fact in two bullets. »* Idem pour `main_topics` et `notable_quotes`.
- Pour `summary_short`, plafonner explicitement la reformulation : *« Never write more than the sources say. If one sentence covers it, write one. »*

*Vérification* : régénérer les cinq types sur le sketch (`mi_6c142cb699dc4d8dbd0df65500660df0`,
414 o) et sur le cours de surf (17,7 ko), puis comparer les ratios sortie/source du §2.1. Cible :
ratio < 1 sur la source courte, volume en hausse sur la source dense.

#### P0-2 · Autoriser une section — et un artefact — vide

*Où* : les cinq blocs d'instructions ; aucun changement côté mobile n'est nécessaire (§2.3).

*Quoi* : ajouter à chaque prompt une clause de sortie explicite, par exemple pour `notes` :
*« Each section is optional. Leave `objectives` empty when the sources do not teach anything to
achieve; leave `glossary` empty when they introduce no term; leave `action_items` empty when
they prescribe nothing. An empty section is a correct answer — an invented one is not. »*
Pour `summary_short`, rendre `takeaway` facultatif dans le prompt **et** dans
`SummaryShortContent` (validateur `_non_empty_text`, `summary_short.py:33-40`, où il est
aujourd'hui contraint non vide).

*Vérification* : générer `notes` sur le sketch de 414 o ; attendu : `objectives`, `action_items`
et `glossary` vides, `concepts` réduit. L'écran mobile masque déjà les sections vides.

#### P0-3 · Interdire le style méta-référentiel

*Où* : `corpus.py`, en ajoutant un fragment partagé (à l'image de `title_instruction()`), inclus
par les cinq types.

*Quoi* : *« Write about the subject matter, never about the document. Do not write "the source
says", "the video explains", "the text presents", "according to the narrator". State the fact
itself. The one exception is `notable_quotes`, which is verbatim by construction. »*

*Vérification* : relancer la mesure du §2.5 sur les quiz régénérés (aujourd'hui 16/41 = 39 %).

#### P0-4 · Casser le biais de longueur des distracteurs de quiz

*Où* : `quiz.py:103-125` (instructions), et éventuellement un contrôle dans `validate()`.

*Quoi* : contrainte de calibre explicite, par exemple : *« All four options must be of
comparable length and specificity — within roughly ten words of each other. A reader who has not
read the sources must not be able to spot the correct option by its length, its detail, or its
hedging. Write the three distractors first, then the correct option to match their calibre. »*
L'inversion de l'ordre de rédaction est la même idée que celle qui a motivé `_shuffle_options()`
pour la position.

Option complémentaire, si la contrainte de prompt ne suffit pas : ajouter dans `validate()` un
rejet quand l'option correcte dépasse la plus longue des autres de plus de N %. À trancher après
mesure — commencer par le prompt seul.

*Vérification* : rejouer le calcul du §2.4 sur les quiz régénérés. Cible : proche de 25 %.

### P1 — Améliorations de fond

#### P1-1 · Traiter le corpus hétérogène pour ce qu'il est

*Où* : `summary_short.py` et `summary_detailed.py`.

*Quoi* : remplacer « Cover the sources as a whole; do not summarise them one by one » par une
règle à deux branches : *« If the sources share a subject, synthesise across them. If they do
not, say so in one sentence and give one line per source — never force a single narrative over
unrelated material, and never title the artifact after one source when it covers several. »*

*Vérification* : régénérer `summary_short` sur la collection à 3 sources hétérogènes du §2.8 ;
le titre doit cesser d'annoncer le longboard seul.

#### P1-2 · Quantifier la couverture multi-sources

*Où* : `corpus.py`, dans un fragment partagé par `quiz`, `flashcards` et `summary_detailed`.

*Quoi* : *« Distribute the items across sources roughly in proportion to how much each one
contributes. With N sources, no single source may account for more than about half the items
unless the others are markedly shorter. »*

*Vérification* : régénérer le quiz du corpus 4 642 / 2 165 / 2 210 o ; la répartition 5/1/1 doit
se rapprocher de 3/2/2.

#### P1-3 · Cadrer `importance` dans les notes

*Où* : `notes.py:106-147`.

*Quoi* : donner un critère opérationnel plutôt qu'un mot : *« `core` marks a concept the reader
cannot do without to use the material; `supporting` marks context. Expect a minority of `core`
— if everything is core, nothing is. »* Si l'on ne veut pas de cette règle, l'alternative
honnête est de supprimer le champ et le badge côté mobile : un badge qui affiche « CORE »
partout n'apporte rien.

*Vérification* : régénérer les notes du cours de surf (aujourd'hui 8/8 `core`).

#### P1-4 · Ancrer les faits datés

*Où* : `corpus.py:35-53` (en-tête de corpus) + fragment partagé.

*Quoi* : deux volets.
1. Enrichir l'en-tête : `[S1] | title: … | language: … | type: … | published: …`, à partir de ce que le message SQS transporte déjà ou de ce qu'on décide d'y ajouter (`artifact_service.py:731-741`).
2. Instruction : *« When a fact is only true at a point in time, anchor it — "on 18 August 2026, the sea was 25.7 °C" — never "today". Do not turn a dated measurement into a flashcard or a quiz question: card the rule, not the reading of the day. »*

*Vérification* : régénérer flashcards et notes sur la page Le Grand Crohot ; aucune occurrence
de « aujourd'hui » ne doit subsister, et la carte n° 1 ne doit plus porter sur la valeur du jour.

#### P1-5 · Neutraliser les marqueurs de transcription

*Où* : `corpus.py`, fragment partagé.

*Quoi* : *« The sources are automatic transcripts. `>>` marks a change of speaker and bracketed
tags such as `[laughs]`, `[music]`, `[coughs]` are non-speech annotations: use them to attribute
speech, never treat them as content to analyse. Transcription errors are expected — reproduce
them only inside verbatim quotes. »*

*Vérification* : régénérer `summary_short` sur le clip TikTok ; la puce sur les rires et la
musique doit disparaître.

#### P1-6 · Tenir la langue jusqu'au vocabulaire

*Où* : `corpus.py:71`, `language_instruction()`.

*Quoi* : *« Use {language} for every string you produce, including glossary terms and headings.
Keep a term in its original language only when it has no accepted equivalent in {language}, and
then gloss it on first use. »*

*Vérification* : régénérer les notes de la page bilingue FR/EN ; le glossaire ne doit plus
contenir d'entrées uniquement anglaises non glosées.

#### P1-7 · Donner un levier de diversité à la régénération

*Où* : `worker.py:117-137` et le message SQS.

*Quoi* : deux options, à trancher par l'owner.
- **(a)** Passer un `seed` / une variation d'instruction dérivée de `artifact_id` — même logique que `_question_rng()`, appliquée à la génération : *« This is a regeneration; favour aspects a previous pass would have skipped. »*
- **(b)** Injecter dans le prompt les titres (ou les questions) déjà produits pour ce scope et ce type, avec la consigne de les éviter.

L'option (b) est plus efficace mais **casse le préfixe de cache partagé** (§1.2) puisque le
contenu injecté diffère d'un type à l'autre — sauf à la placer **après** le corpus, dans le bloc
d'instructions, ce qui la rend compatible. L'option (a) est neutre pour le cache.

*Vérification* : générer deux fois de suite le même quiz sur la page Le Grand Crohot ; le
recouvrement des faits testés doit descendre nettement sous les 6/7 observés.

### P2 — À instruire avant d'agir

#### P2-1 · Brancher les Structured Outputs sur les trois types restants

*Où* : `response_format_schema()` de `summary_short.py`, `summary_detailed.py`, `notes.py`.

*Quoi* : fournir un `json_schema` `strict: true` calqué sur le modèle Pydantic existant (toutes
les propriétés en `required`, `additionalProperties: false`, `enum` pour `importance`). Le
chemin d'appel est déjà prêt : `_supports_structured_outputs()` renvoie déjà `True` pour ces
trois modèles, seul le schéma manque.

*Point d'attention* : `strict: true` interdit les champs optionnels ; les sections rendues
facultatives par P0-2 doivent donc rester **présentes mais vides** (`[]`, `""`), ce que le
rendu mobile gère déjà. À valider conjointement avec P0-2, et non séparément.

*Vérification* : générer les trois types et confirmer qu'aucun `VALIDATION_ERROR` n'apparaît
dans `media_artifacts-dev`.

#### P2-2 · Instrumenter les tokens de raisonnement avant de régler l'effort

*Où* : `_read_llm_usage()` ([worker.py:165](../../../media_summarizer/workers/artifact_generator/worker.py#L165)) et `ArtifactLlmUsage`.

*Quoi* : conserver `completion_tokens_details.reasoning_tokens` du bloc `usage`. **Si** l'écart
du §2.13 se confirme, évaluer un `reasoning_effort` bas pour les types d'extraction
(`flashcards`, `quiz`), qui sont des tâches de recopie structurée plutôt que de raisonnement.
Ne rien changer au paramétrage avant d'avoir la mesure.

#### P2-3 · Aligner le repli de modèle de `notes`

*Où* : `notes.py:94-99` et son docstring.

*Quoi* : remplacer le repli `gpt-4o-mini-2024-07-18` par `gpt-5.4-nano-2026-03-17`, comme les
trois autres types, et corriger le docstring. Sinon le `generator_version` enregistré par l'API
peut mentir sur le modèle réellement appelé (§3.3.7).

#### P2-4 · Réexaminer le modèle de `summary_short`

`summary_short` est seul sur `gpt-5-nano-2025-08-07`, choix hérité du benchmark task-72. Il est
aussi celui qui présente l'écart tokens facturés / sortie visible le plus large (§2.13). À
réévaluer une fois P0 et P1 appliqués, sur la base des coûts réellement observés — pas avant.

---

## 5. Ce qui n'est *pas* un problème de prompt

- **Les deux artefacts `failed` de dev** (`art_518ecf77`, `art_909a7ce3`) portent
  `error_message: "Float types are not supported. Use Decimal types instead."` — une écriture
  DynamoDB, sans rapport avec la génération. Les deux datent du 2026-08-18 vers 00 h 35 ; les
  artefacts produits le même jour à partir de 16 h enregistrent leur `llm_usage` correctement.
  Rien à corriger côté prompt.
- **La fidélité des citations** est bonne : les 5 `notable_quotes` vérifiées sont exactes au
  caractère près. Ne pas toucher à `source_ref_instruction(required=True)`.
- **`_shuffle_options()`** fait son travail et aucune explication ne nomme de lettre.
- **La qualité sur source dense** est au rendez-vous (notes du cours de surf). Le problème est la
  calibration, pas la conception.
- **L'ordre corpus → instructions** est un choix de coût validé (task-269). Aucune proposition
  ci-dessus ne le remet en cause ; P1-7 option (b) est la seule qui s'en approche et reste
  compatible à condition de rester dans le bloc d'instructions.

---

## 6. Notes à l'owner

1. **Bump de `generator_version`.** Toute modification retenue doit faire passer `prompt-v2` à
   `prompt-v3` dans les cinq entrées de `get_generator_version()`
   ([artifact_service.py:203-225](../../../media_summarizer/core/services/artifact_service.py#L203)). Sans cela, l'historique ne permet plus de dire quel prompt a produit quel artefact — et c'est précisément ce champ qui a permis d'isoler les 14 artefacts analysés ici.
2. **Vérification E2E après déploiement.** Les mesures des §2.1, §2.2, §2.4, §2.5 et §2.8 sont
   rejouables à l'identique : elles ne demandent que les artefacts et les transcripts `-dev`. Le
   plus court chemin pour juger l'effet d'un changement est de régénérer les cinq types sur le
   sketch de 414 octets (cas dégénéré) et sur le cours de surf de 17,7 ko (cas dense), puis de
   recalculer les ratios.
3. **Coût.** Le remplissage n'est pas qu'un problème de qualité : la sortie est facturée
   6,25 fois l'entrée sur `gpt-5.4-nano`. P0-1 réduit la facture en même temps que le bruit.
4. **Une seule tâche d'implémentation suffit** pour P0 et P1 : tout est dans
   `generators/` plus deux fragments de `corpus.py`, sans changement de contrat ni de rendu
   mobile. P2-1 (Structured Outputs) et P0-2 (sections vides) doivent en revanche être livrés
   ensemble.
