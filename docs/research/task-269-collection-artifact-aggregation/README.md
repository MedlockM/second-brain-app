---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark : génération d'artefacts IA au niveau collection (agrégation de N transcripts)

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — texte libre décrivant la décision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes précises de correction à intégrer au prochain passage)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Stratégie S1 « passe unique sur le corpus concaténé », avec plafond dur et refus explicite au-delà, sans troncature, sans étage map-reduce, sans store intermédiaire.**

Concrètement, pour un scope donné (un média ou une collection) et un type d'artefact :

1. L'API résout les sources (le folder et tous ses descendants), obtient pour chacune son *transcript effectif* via la mécanique existante `_resolve_effective_transcript` (détection + traduction task-189/192), et estime le nombre de tokens du corpus.
2. Si le corpus dépasse **25 sources** ou **120 000 tokens estimés**, l'API **refuse** (`422`) avec les deux compteurs mesurés. Elle ne tronque pas, ne sélectionne pas un sous-ensemble arbitraire, n'enfile rien.
3. Sinon elle crée **une entrée d'historique immuable** et enfile **un seul message SQS** sur la queue existante `artifact-generator-queue`.
4. Le worker télécharge les N transcripts, construit **un prompt unique** dont le préfixe est le corpus balisé (`[S1] … [Sn]`) et dont le suffixe est le bloc d'instructions du type demandé, et fait **un seul appel LLM**.
5. Le worker écrit l'artefact dans le bucket S3 du type et bascule l'entrée en `ready`. L'entrée n'est jamais mise à jour ensuite.

La même mécanique sert le scope média : un média est une collection à une source (`sources` de longueur 1). Il n'y a **pas** deux chemins de code.

**Pourquoi celle-là et pas une autre** — les cinq stratégies sont chiffrées en section 2. Résumé du verdict :

- Le coût n'arbitre pas : à 10 sources, toutes les stratégies viables tiennent entre **0,016 € et 0,039 €** pour les 5 types. L'écart maximal (0,023 €) est inférieur au coût de transcription d'**8 minutes** d'audio (0,003 €/min, task-65). Aucune décision d'architecture ne se justifie par cet écart.
- Ce qui arbitre, c'est que **la queue est par type d'artefact** (un message = un type = une invocation Lambda). Toute stratégie multi-étages doit donc soit recalculer son étage de condensation 5 fois (S2 recalculée : 55 appels LLM), soit introduire un store intermédiaire partagé **plus** un verrou de coordination. S1 n'a besoin d'aucun des deux, et le *prompt caching* d'OpenAI fournit gratuitement le partage entre les 5 invocations (préfixe identique, 0,1× le prix d'entrée).
- La prémisse de la stratégie « réutiliser les `summary_detailed` par média » est **empiriquement fausse** : mesuré sur `-dev`, il y a **0 artefact `summary_detailed`** sur 76 artefacts et le bucket `media-summarizer-summary-detailed-125313707865-dev` est **vide**. Cette stratégie serait donc systématiquement dans son cas « froid » : plus chère que S1 (0,041 € contre 0,039 €), 15 appels au lieu de 5, et un résumé-de-résumés en entrée des flashcards et du quiz.
- S1 est la seule stratégie qui garde le **texte intégral de chaque source** devant le modèle, ce qui est la condition pour que les citations, les chiffres et les questions de quiz soient exacts.

**Le plafond n'est pas un choix produit, c'est la limite du modèle** : `gpt-5.4-nano` accepte 272 000 tokens d'entrée. Le corpus entier de `-dev` (190 transcripts, 1,25 Mo) vaut **368 503 tokens, soit 1,35× cette limite** : une collection « tout mon compte » ne rentre pas. 25 sources × la médiane mesurée (4 622 tokens) = 116 050 tokens, soit 42,7 % de la limite ; c'est le point où les deux plafonds (nombre et tokens) se rejoignent pour du contenu typique, ce qui rend le message d'erreur intelligible.

**Les autres décisions**, détaillées en sections 3 à 10 et récapitulées en section 11 :

| Sujet | Décision |
|---|---|
| Sous-collections | **Incluses**, via `_get_descendant_ids`, exactement comme `GET /api/media?folder_id=` |
| Stockage | **Une seule table `media_artifacts`**, un `scope` + `scope_id`, **un** nouveau GSI `scope-index` (hash `scope_key`, range `created_at`) |
| Tri par date | Par le range key du GSI, `ScanIndexForward=false` — pas de tri applicatif |
| Dédup | `artifact_id` **déterministe** dérivé de (scope, type, paramètres, sources, fenêtre de 120 s) + `ConditionExpression` — la table `artifact_idempotence` disparaît |
| Titre | **Généré par le LLM** (un champ `title` ajouté aux 5 schémas), recopié sur l'enregistrement DynamoDB |
| `artifact_statuses` | **Supprimé** (contrat, service, mobile). Le polling passe sur la liste d'artefacts du scope |
| Transcripts pas prêts | Traduction/transcription en vol → **refus `409` retryable** ; transcript définitivement absent → **source exclue**, tracée dans le snapshot |
| Attribution | Au niveau artefact (liste ordonnée des sources) + `source_ref` obligatoire sur les **citations** de `summary_detailed` |
| Quota | Un compteur **`ai_source_units`** (1 unité = une source dans une génération) dans `pricing_config`, mensuel + journalier, aligné task-65 |

---

## 0. Entrées non rouvertes (tranchées par l'owner)

Ces points sont des **contraintes d'entrée** du benchmark, pas des questions ouvertes. Ils sont rappelés parce que toute l'architecture en découle.

1. **Un artefact est immuable et horodaté.** Une génération = une nouvelle entrée. Rien n'est écrasé.
2. **Chaque entrée porte son instantané de sources** : la liste des `media_item_id` retenus, `source_count`, `generated_at`, `generator_version`.
3. **Ajouter ou retirer un média d'une collection n'invalide rien.** Les entrées passées restent valides *telles quelles* : elles décrivent ce qu'était la collection au moment de la génération.
4. **Aucun mécanisme d'invalidation, de péremption, de « stale », de régénération automatique.** Pas de champ `is_stale`, pas de TTL applicatif sur les artefacts, pas de recalcul déclenché par un événement d'organisation.
5. **La même mécanique append-only s'applique au scope média.** Le média n'est pas un cas particulier : c'est un scope à une source. Le code d'aujourd'hui (un artefact « courant » par type, écrasé à chaque régénération) est du legacy à supprimer.

Ce que ces contraintes laissent réellement ouvert côté idempotence, et que ce benchmark tranche en section 5.2 : la **déduplication de courte portée** (double tap sur le bouton, redélivrance SQS at-least-once) — sans réintroduire de sémantique d'invalidation.

---

## 1. Volumétrie réelle mesurée sur `-dev`

Toutes les mesures sont **en lecture seule**. Aucun appel LLM n'a été émis pendant ce benchmark.

### 1.1 Commandes utilisées

Région : `eu-west-3`. Compte AWS de dev : `125313707865`.

Inventaire et taille du corpus de transcripts :

    aws s3 ls --summarize --human-readable --recursive \
      s3://media-summarizer-transcripts-125313707865-dev --region eu-west-3 | tail -3

    aws s3api list-objects-v2 \
      --bucket media-summarizer-transcripts-125313707865-dev \
      --query 'Contents[].[Key,Size]' --output text --region eu-west-3

Population d'artefacts existante et pollution de la table :

    aws dynamodb scan --table-name media_artifacts-dev --region eu-west-3 \
      --projection-expression artifact_id --output text | wc -l

    aws dynamodb scan --table-name media_artifacts-dev --region eu-west-3 \
      --projection-expression artifact_id --output text | grep -c 'request#'

    aws dynamodb scan --table-name media_artifacts-dev --region eu-west-3 \
      --projection-expression artifact_type --output text | sort | uniq -c | sort -rn

    aws dynamodb scan --table-name artifact_idempotence-dev --region eu-west-3 --select COUNT

Taille réelle des collections :

    aws dynamodb scan --table-name user_media-dev --region eu-west-3 \
      --projection-expression folder_id --output text | sort | uniq -c | sort -rn

Étalonnage tokens : un transcript représentatif a été téléchargé (`aws s3 cp … -`) et mesuré ;
`tiktoken` n'est pas installé dans l'environnement, donc la conversion utilise **3,4 octets/token**
(UTF-8, français/anglais mêlés), valeur recoupée avec l'hypothèse validée de task-65
(250 tokens/minute de parole française). C'est une **estimation à ±10 %**, suffisante pour
dimensionner un plafond mais pas pour facturer.

### 1.2 Résultats

| Mesure | Valeur | En tokens (3,4 o/token) |
|---|---|---|
| Objets dans le bucket transcripts `-dev` | **190** | — |
| Taille totale du corpus | **1 252 913 o** (1,2 MiB) | **368 503** |
| Médiane par transcript | **15 715 o** | **4 622** |
| p90 par transcript | **17 041 o** | **5 012** |
| Maximum observé | **41 932 o** | **12 332** |
| Plus grosse collection `-dev` | **11 médias** (7 avec transcript résolvable, 60 287 o) | **17 731** |
| Lignes dans `user_media-dev` | 25 | — |

Population d'artefacts sur `-dev` :

| Mesure | Valeur |
|---|---|
| Lignes totales dans `media_artifacts-dev` | **168** |
| dont pointeurs `request#…` (pas des artefacts) | **92 — 54,8 %** |
| Artefacts réels | **76** |
| Répartition | `quiz` 22, `summary` 17, `notes` 16, `flashcards` 16, `summary_short` 5 |
| Artefacts `summary_detailed` | **0** |
| Lignes dans `artifact_idempotence-dev` | 36 |

Trois faits de ce tableau pèsent directement sur les décisions qui suivent :

- **Plus d'une ligne sur deux de `media_artifacts` n'est pas un artefact** mais un pointeur d'idempotence (`REQUEST_POINTER_PREFIX = "request#"`, cf. `media_summarizer/utils/media_artifacts.py`). L'endpoint de liste les filtre en Python après les avoir lus. Sur une table qui va devenir un **historique** append-only, cette pollution croît linéairement avec le nombre de générations. Elle est supprimée (section 5.2).
- **`summary_detailed` n'existe nulle part** et le type `summary` (17 lignes) n'est **pas** un membre de `MediaArtifactType` : c'est du résidu d'avant task-195. Toute stratégie qui suppose disponible un résumé détaillé par média part d'une couverture réelle de 0 %.
- Le corpus **entier** du compte de dev vaut **1,35× la fenêtre d'entrée maximale** de `gpt-5.4-nano` (272 000 tokens). Une collection « tout » est hors d'atteinte de n'importe quelle stratégie mono-passe : le plafond n'est donc pas négociable, seule sa valeur l'est.

### 1.3 Corpus par taille de collection, face à la fenêtre du modèle

Base : médiane mesurée de 4 622 tokens par source. Fenêtre d'entrée maximale de `gpt-5-nano` et de `gpt-5.4-nano` : **272 000 tokens** (contexte total 400 000, sortie max 128 000).

| Sources | Tokens de corpus | % de la fenêtre d'entrée |
|---|---|---|
| 5 | 23 210 | 8,5 % |
| 10 | 46 420 | 17,1 % |
| 20 | 92 840 | 34,1 % |
| **25 (plafond retenu)** | **116 050** | **42,7 %** |
| 50 | 232 100 | 85,3 % |
| 60 | 278 520 | **dépasse** |

Avec le **maximum** observé (12 332 tokens), 22 sources suffisent à saturer la fenêtre — c'est
pourquoi le plafond en tokens (section 3) existe **en plus** du plafond en nombre de sources.

---

## 2. Les cinq stratégies d'agrégation, chiffrées

### 2.1 Ce qui est comparé

| Id | Stratégie | Principe |
|---|---|---|
| **S1** | **Passe unique (« stuff »)** | Concaténer les N transcripts balisés dans un seul prompt, un appel LLM par type d'artefact. |
| **S2** | **Map-reduce** | Condenser chaque source en ~800 tokens (`gpt-5-nano`), puis un appel de synthèse par type sur les condensés. |
| **S3** | **Réutilisation des `summary_detailed` par média** | Prendre le résumé détaillé déjà généré de chaque média (le générer s'il manque), puis un appel de synthèse par type. |
| **S4** | **Refine / incrémental** | Partir de la source 1, puis replier chaque source suivante dans l'artefact courant : N appels séquentiels par type. |
| **S5** | **RAG / retrieval** | Indexer les chunks (embeddings), ne mettre dans le prompt que les ~40 % les plus pertinents, un appel par type. |

Modèle de coût : `docs/research/task-269-collection-artifact-aggregation/compute.py` (arithmétique
pure, pas de réseau — `python3 compute.py` régénère tous les chiffres cités ici). Hypothèses :
prix catalogue OpenAI par 1M de tokens (`gpt-5-nano` 0,05 / 0,005 / 0,40 $ ; `gpt-5.4-nano`
0,20 / 0,02 / 1,25 $), `USD_EUR = 0,86` comme task-65, budgets de sortie repris de task-65
(short 300, detailed 1 500, notes 1 200, flashcards 800) plus **quiz 1 200** (ajouté ici : task-65
est antérieure au type quiz), bloc d'instructions 400 tokens, en-tête de source 20 tokens,
source médiane **4 622 tokens** (mesure §1.2), modèle par type identique aux défauts codés dans
les générateurs (`summary_short` vers `gpt-5-nano`, les 4 autres vers `gpt-5.4-nano`).

### 2.2 Coût marginal d'une collection, les 5 types générés (EUR)

    sources |  S1 stuff |  S1+cache |    S2 m/r |   S3 warm |   S3 cold | S4 refine |    S5 rag
    --------+-----------+-----------+-----------+-----------+-----------+-----------+----------
          5 |    0.0224 |    0.0116 |    0.0109 |    0.0110 |    0.0234 |    0.0474 |    0.0126
         10 |    0.0394 |    0.0178 |    0.0164 |    0.0166 |    0.0413 |    0.0957 |    0.0198
         20 |    0.0733 |    0.0302 |    0.0273 |    0.0277 |    0.0772 |    0.1921 |    0.0341
         25 |    0.0903 |    0.0364 |    0.0327 |    0.0332 |    0.0951 |    0.2404 |    0.0412

**Lecture honnête de ce tableau : le coût ne tranche pas.** Sur la plage utile, cinq des sept
colonnes tiennent dans un rapport de 1 à 2,5, et l'écart absolu entre la moins chère (S2, 0,0164 €)
et S1 sans cache (0,0394 €) est de **2,3 centimes** pour une collection de 10 sources et les cinq
types. À titre de comparaison, task-65 chiffre la transcription à **0,003 €/minute** : cet écart
vaut 7,7 minutes d'audio, ou **0,4 %** du prix d'un abonnement mensuel à 4,99 €.
Seule S4 sort du lot (2,4× à 6× les autres) et se disqualifie par le coût.

Ce qui tranche, ce sont les trois colonnes suivantes.

### 2.3 Nombre d'appels LLM et chemin critique (10 sources, 5 types)

    S1 stuff         total=  5  sequentiel-par-type=  1
    S2 map-reduce    total= 15  sequentiel-par-type= 11
    S3 reuse warm    total=  5  sequentiel-par-type=  1
    S3 reuse cold    total= 15  sequentiel-par-type= 11
    S4 refine        total= 50  sequentiel-par-type= 10
    S5 rag           total=  5  sequentiel-par-type=  1

Le « séquentiel par type » est ce qui doit tenir dans les budgets **existants** du worker :
`timeout = 300` s sur la Lambda `artifact_generator` et `LLM_TIMEOUT_SECONDS = 180` sur l'appel
HTTP (`infrastructure/terraform/modules/platform/lambda_workers.tf`,
`media_summarizer/workers/artifact_generator/worker.py`). Un appel `gpt-5.4-nano` sur ~100 k
tokens d'entrée se compte en dizaines de secondes : **1 appel séquentiel rentre, 10 ou 11 non**.
S2 et S4 imposent donc soit une refonte du worker (état persistant, reprise, fan-out d'un message
par étape, timeouts relevés), soit du parallélisme `asyncio.gather` sur l'étage map — faisable,
mais c'est du code nouveau que S1 n'a pas besoin d'écrire.

### 2.4 L'argument décisif : la queue est **par type d'artefact**

Aujourd'hui, une demande = un message SQS = un type d'artefact = une invocation Lambda
(`batch_size = 1`). Les 5 types demandés sur une collection sont **5 invocations indépendantes**,
qui ne partagent aucune mémoire.

Conséquence pour chaque stratégie multi-étages :

- **S2** et **S3-cold** doivent produire un étage intermédiaire (condensés / résumés par média).
  Soit ce résultat est **recalculé dans chacune des 5 invocations** — et le tableau §2.2 devient
  faux : 5 fois (10 map + 1 reduce) = **55 appels** pour un coût de l'ordre de 0,036 € à
  10 sources, c'est-à-dire **aussi cher que S1 froid avec 11× plus d'appels** — soit il faut **un
  store intermédiaire partagé** (préfixe S3 ou table) **plus un verrou** pour que deux invocations
  concurrentes ne le calculent pas deux fois. Ce verrou est exactement le genre de machinerie que
  l'owner fait retirer côté idempotence.
- **S1** n'a pas ce problème : les 5 invocations envoient le **même préfixe de prompt**. Le
  partage est fait côté fournisseur par le *prompt caching* — 0,1× le prix d'entrée sur les
  lectures en cache, sans store à nous, sans verrou, sans code de coordination (§2.6). Si le
  cache manque, on paie S1-froid, ce qui reste dans l'ordre de grandeur de tout le monde sauf S4.

C'est le point qui fait basculer la recommandation, et il est architectural, pas économique.

### 2.5 Qualité par type d'artefact

Il n'y a pas de mesure automatisable ici : le projet n'a pas de jeu d'évaluation d'artefacts, et
en produire un impliquerait du trafic LLM, hors périmètre de ce benchmark. L'appréciation
ci-dessous croise la littérature citée en §2.7 et la nature de chaque type.

| Type | S1 passe unique | S2 map-reduce | S3 réutilisation | S4 refine | S5 RAG |
|---|---|---|---|---|---|
| `summary_short` | **bon** — la synthèse courte tolère la perte de détail | **bon** | correct | médiocre (dérive) | correct |
| `summary_detailed` | **excellent** — seul cas où les citations sont **littérales** et vérifiables | dégradé : citations recopiées d'un condensé, donc reformulées | dégradé de même | mauvais : réécritures successives | risqué : citations hors des passages retrouvés |
| `notes` | **excellent** | correct | correct | mauvais | correct |
| `flashcards` | **excellent** — les faits précis (chiffres, noms) sont encore présents | **perte nette** : les faits fins sont ce que la condensation supprime | perte nette | mauvais | correct si le chunk est retrouvé |
| `quiz` | **excellent** — des distracteurs plausibles exigent le détail environnant | perte nette (distracteurs génériques) | perte nette | mauvais | correct |

La ligne qui compte : **`flashcards` et `quiz` sont des extracteurs de détail**, pas des
synthétiseurs. Toute stratégie qui condense avant de générer leur retire précisément la matière
dont ils vivent. Et un `summary_detailed` de collection construit sur des résumés par média est un
résumé de résumés — le défaut que BooookScore documente comme perte de cohérence (§2.7).

### 2.6 Mise en page du prompt : corpus d'abord, instructions ensuite

Le *prompt caching* d'OpenAI ne fonctionne que sur un **préfixe exactement identique**, à partir
de 1 024 tokens et par tranches de 128 ; les lectures en cache sont facturées 0,1× le prix
d'entrée ; la rétention `in_memory` expire après 5 à 10 minutes d'inactivité (jusqu'à ~1 h aux
heures creuses) ; `prompt_cache_key` permet de router les requêtes d'un même préfixe vers la même
machine.

Les cinq générateurs actuels construisent leurs prompts dans l'ordre **instructions → schéma JSON
→ transcript** (`build_prompt` dans `summary_short.py`, `summary_detailed.py`, `quiz.py`,
`notes.py`, `flashcards.py`). Dans ce sens, le préfixe partagé entre deux types fait quelques
dizaines de tokens : **le cache ne mord jamais**. Il faut donc inverser :

1. un préambule fixe court, identique pour tous les types ;
2. **le corpus balisé** — pour chaque source, un en-tête (`[S1]`, titre, langue, `media_item_id`)
   puis le texte ;
3. **puis** le bloc d'instructions et le schéma du type demandé.

Ce seul réordonnancement fait passer une collection de 25 sources de **0,0903 € à 0,0364 €** pour
les cinq types (§2.2, colonnes `S1 stuff` et `S1+cache`), soit **−60 %**, à sortie identique. Il
exige que le worker envoie `prompt_cache_key` = empreinte du corpus, et que les 5 messages d'une
même demande soient traités dans la fenêtre de rétention — ce qui est le cas naturel (5 messages
enfilés ensemble, `batch_size = 1`, invocations concurrentes).

Coût par type à 25 sources (116 050 tokens de corpus) :

| Type | Modèle | Froid | En cache |
|---|---|---|---|
| `summary_short` | `gpt-5-nano` | 0,0051 € | 0,0006 € |
| `summary_detailed` | `gpt-5.4-nano` | 0,0216 € | 0,0037 € |
| `notes` | `gpt-5.4-nano` | 0,0213 € | 0,0034 € |
| `flashcards` | `gpt-5.4-nano` | 0,0209 € | 0,0029 € |
| `quiz` | `gpt-5.4-nano` | 0,0213 € | 0,0034 € |

Pour situer : task-65 chiffre à **0,0104 €** le coût LLM des artefacts d'un podcast de 45 min. Un
artefact de collection au plafond coûte donc **~2× un média entier** à froid, **0,3×** en cache.
Aucun de ces chiffres ne menace le modèle économique ; c'est le **nombre de régénérations** qui
doit être borné, d'où le quota en §10.

### 2.7 Ce que dit la littérature sur le long contexte

L'objection légitime à S1 est la dégradation du modèle quand le contexte grandit :

- **« Lost in the Middle » (Liu et al., TACL 2024)** : la performance est en U — ce qui est au
  début et à la fin du contexte est mieux exploité que ce qui est au milieu, y compris sur des
  modèles annoncés « long contexte ».
- **Context rot (Chroma, 2025)** : sur 18 modèles, la performance décroît de façon non uniforme
  quand la longueur d'entrée augmente, même sur des tâches triviales.
- **NoLiMa (2025)** : sur 12 modèles à contexte ≥ 128 k, 10 tombent sous 50 % de leur score
  « court » dès 32 k tokens **quand la tâche demande un raisonnement associatif** et pas une
  correspondance lexicale.
- **BooookScore (Chang et al., ICLR 2024)** : à budget égal, la **fusion hiérarchique** produit des
  résumés plus cohérents que la **mise à jour incrémentale** — S2/S3 battent donc S4, ce que le
  tableau §2.5 reflète.

Trois raisons pour lesquelles ces résultats ne renversent pas la recommandation :

1. **Le régime retenu est 8 à 43 % de la fenêtre d'entrée** (§1.3), pas 90 %. La zone de
   dégradation sévère mesurée par NoLiMa est au-delà de ce que le plafond autorise.
2. **Les tâches ici sont de la synthèse et de l'extraction sur du texte balisé**, pas de la
   recherche d'aiguille dans une botte de foin. Le balisage explicite par source est précisément
   l'atténuation recommandée contre le « lost in the middle ».
3. **Le plafond est la réponse d'ingénierie à cette littérature.** Refuser au-delà de 25 sources
   plutôt que produire quelque chose de dégradé est ce qui garantit qu'on reste dans le régime où
   S1 tient.

### 2.8 Verdict par stratégie

| Stratégie | Verdict | Motif dominant |
|---|---|---|
| **S1 passe unique** | **retenue** | Aucun store, aucun verrou, 1 appel séquentiel, fidélité maximale ; le cache fournisseur donne le partage entre types gratuitement. |
| S2 map-reduce | écartée | La queue étant par type, elle coûte soit 55 appels, soit un store partagé + verrou ; et elle dégrade `flashcards`/`quiz`. |
| S3 réutilisation | écartée | Prémisse fausse : **0 `summary_detailed` sur `-dev`**, bucket vide → toujours le cas froid (plus cher que S1, 15 appels). Et la qualité dépendrait de quels artefacts par média l'utilisateur a générés par ailleurs : non reproductible. |
| S4 refine | écartée | La plus chère (0,24 € au plafond), N appels séquentiels, la moins cohérente selon BooookScore. |
| S5 RAG | écartée | Demande un store de vecteurs absent de la stack (Algolia est lexical), et le *retrieval* est le mauvais primitif pour une tâche qui exige la **couverture** de toutes les sources et non les k meilleurs passages. |

---

## 3. Plafond et politique de refus

### 3.1 Les deux plafonds

    MAX_COLLECTION_SOURCES = 25
    MAX_COLLECTION_CORPUS_TOKENS = 120_000

Ce sont des **constantes de code**, pas des paramètres commerciaux : elles dérivent de la fenêtre
du modèle, pas du prix. Elles n'ont donc rien à faire dans `pricing_config` (contrairement au
quota, §10, qui est commercial et doit rester ajustable sans déploiement).

Justification des valeurs :

- **25 sources** = 116 050 tokens au médian mesuré, soit **42,7 %** de la fenêtre d'entrée de
  272 000 tokens. Le facteur 2,3 de marge absorbe une collection de sources toutes plus longues
  que la médiane (au p90, 25 sources = 125 300 tokens ; au maximum observé, 22 sources saturent
  déjà la fenêtre — d'où le second plafond).
- **120 000 tokens** est le garde-fou qui rattrape le cas des sources longues. Les deux plafonds
  se rejoignent presque exactement pour du contenu médian, ce qui rend le message d'erreur
  intelligible : dans le cas courant, l'utilisateur voit « 25 sources maximum » ; dans le cas des
  très longues sources, il voit un refus sur le volume avec le chiffre mesuré.

### 3.2 Où et comment le volume est mesuré

Le contrôle est fait **dans l'API**, avant toute écriture. Il ne coûte aucun accès supplémentaire :
l'API lit de toute façon chaque transcript pour la résolution de langue (§7), puisque
`resolve_or_enqueue_translated_transcript` détecte la langue **localement, sans appel LLM**
(`core/services/transcript_translation.py`). Le comptage porte donc sur les octets UTF-8
**réellement concaténés**, convertis en tokens au ratio de 3,4 o/token — pas sur des métadonnées S3.
La conversion reste une approximation à ±10 %, ce que la marge de 2,3 entre le plafond et la fenêtre
du modèle absorbe largement.

Budget de temps : l'API tourne dans une Lambda à `timeout = 30` s (`lambda_api.tf`). 25 sources
représentent ~400 ko et 25 `GetObject` à lancer en `asyncio.gather` — quelques centaines de
millisecondes. La détection de langue est locale. Le seul coût réel est la résolution de traduction,
qui est exactement le chemin par média d'aujourd'hui, exécuté 25 fois en parallèle.

Le worker revérifie le plafond avant l'appel LLM : si le corpus concaténé dépasse
`MAX_COLLECTION_CORPUS_TOKENS` (une traduction plus longue que l'original, par exemple), il passe en
`failed` avec un `error_code` dédié **sans appeler le LLM**. Ce cas doit rester exceptionnel ; il
existe pour ne jamais envoyer une requête que le fournisseur rejettera.

### 3.3 Refuser, ne pas tronquer

**La troncature est exclue.** Un artefact tronqué prétendrait couvrir la collection alors que son
instantané de sources (contrainte d'entrée n° 2) mentirait : il listerait des `media_item_id` dont
le texte n'a jamais atteint le modèle. Or l'instantané est précisément ce qui rend l'historique
interprétable. Même raisonnement contre une sélection automatique « les 25 plus récents » : c'est
une troncature déguisée, et elle rend le résultat non reproductible.

Le refus est **synchrone**, à la création : rien n'est écrit en base, rien n'est enfilé, aucun
appel LLM n'est fait, donc aucun coût. Le remède proposé à l'utilisateur est explicite : **créer
une sous-collection** plus petite (les sous-collections sont incluses, §4, donc découper une
collection trop grosse en sous-collections ne suffit pas — il faut générer *sur* la
sous-collection).

### 3.4 Les quatre refus typés

| Situation | Code HTTP | `error_code` | Réessayable ? |
|---|---|---|---|
| Collection sans aucune source exploitable | **422** | `scope_empty` | non — l'utilisateur doit ajouter des médias |
| Plus de 25 sources, ou plus de 120 000 tokens | **422** | `scope_too_large` | non — l'utilisateur doit réduire le périmètre |
| Au moins une source dont le transcript est en cours (transcription ou traduction) | **409** | `sources_not_ready` | **oui**, tel quel, plus tard |
| Quota d'IA atteint (§10) | **403** monthly / **429** daily | `tier_quota_exceeded` / `daily_rate_limit` | à la période suivante |

Le corps du 422 `scope_too_large` porte les quatre chiffres nécessaires à l'affichage :
`source_count`, `max_sources`, `estimated_tokens`, `max_tokens`. Le mobile n'a alors aucun calcul
à faire (task-272 AC#9 attend trois refus distincts rendus dans l'onglet IA).

Les codes 409 et 403/429 existent déjà dans le code (`ArtifactTranscriptNotReadyError` → 409 dans
`api/endpoints/artifacts.py` ; `QuotaCheckResult.denied(http_status=403|429)` dans
`quota_enforcer.py`). Seuls les deux `422` sont nouveaux.

### 3.5 Repère externe : NotebookLM

NotebookLM plafonne à **50 sources par notebook** en gratuit, 100 en Plus, 300 en Pro, 500 à 600
en Ultra. Ce plafond est bien plus haut que 25, mais il n'est **pas comparable** : NotebookLM
indexe les sources et fait du *retrieval* au moment de la question — il ne met jamais les 300
sources dans un prompt. Un plafond de 25 sur une architecture mono-passe et un plafond de 300 sur
une architecture RAG expriment la même contrainte physique. Si le plafond de 25 devient un jour
gênant en usage réel, la réponse n'est pas de l'augmenter : c'est de rouvrir le choix de stratégie
(S5), avec le store de vecteurs que cela implique.

---

## 4. Sous-collections : incluses

**Décision : la génération sur une collection prend le folder **et tous ses descendants**.**

Trois raisons, dans l'ordre de poids :

1. **C'est déjà la sémantique de l'onglet Sources.** `GET /api/media?folder_id=X` étend le filtre
   à `{X} ∪ _get_descendant_ids(X)` (`core/services/media_search_service.py`), et le mobile appelle
   exactement cet endpoint (`mobile/src/services/organizationService.ts`, `getCollectionMedia`).
   L'onglet Sources d'une collection montre donc déjà les médias des sous-collections. Générer sur
   un sous-ensemble strict de ce que l'onglet Sources affiche produirait un artefact dont le
   `source_count` ne correspond pas à la liste que l'utilisateur a sous les yeux — bug de
   perception garanti.
2. **La hiérarchie de collections n'a de sens que si elle est transitive.** « Mes lectures » →
   « IA » → « Alignement » : demander une synthèse de « Mes lectures » sans « Alignement » n'a
   aucune lecture naturelle.
3. **Le plafond rend la profondeur inoffensive.** Le risque d'une inclusion transitive est
   l'explosion du volume ; il est déjà borné par §3.

Conséquence sur l'instantané : le champ `sources` liste des `media_item_id`, **à plat**, dédupliqués
(un média présent dans deux sous-collections n'apparaît qu'une fois), dans l'ordre où ils entrent
dans le prompt. Le folder d'origine de chaque source n'est pas conservé : ce serait une information
d'organisation, donc périssable, et l'owner a exclu toute péremption.

---

## 5. Mécanique append-only, identique pour les deux scopes

### 5.1 L'enregistrement d'historique

Un seul type d'enregistrement, une seule table (§6), un seul chemin de code. Le média est un scope
à une source.

| Champ | Rôle | Nouveau ? |
|---|---|---|
| `artifact_id` | Clé primaire. **Déterministe** (§5.2), plus de `art_<random>` | modifié |
| `user_id` | Propriétaire. **Indispensable** : le contrôle d'accès ne peut plus passer par le média (un artefact de collection n'en a pas) | **nouveau** |
| `scope` | `media` ou `folder` | **nouveau** |
| `scope_id` | `media_item_id` ou `folder_id` | **nouveau** |
| `scope_key` | `user_id#scope#scope_id` — clé de hash du GSI (§6.2) | **nouveau** |
| `created_at` | ISO-8601 UTC. **Clé de tri du GSI** : l'ordre chronologique inverse vient de là | existant, nouveau rôle |
| `artifact_type` | Un des 5 types | existant |
| `status` | `queued`, `generating`, `ready`, `failed` | existant |
| `title` | Titre affiché, **émis par le LLM** (§5.4), recopié ici pour que la liste ne lise pas S3 | **nouveau** |
| `source_count` | Longueur de `sources`, dénormalisé pour l'affichage « N sources » | **nouveau** |
| `sources` | **L'instantané.** Liste ordonnée, un élément par source : `media_item_id`, `title`, `transcript_s3_key`, `language` | **nouveau** |
| `parameters` | Paramètres de la demande (langue de sortie, etc.) | existant |
| `generator_version` | Version du générateur ayant produit le contenu | existant |
| `storage` | Bucket + clé S3 du contenu | existant |
| `lease_expires_at` | Bail du worker en cours (§5.2) | **nouveau** |
| `completed_at` | Horodatage de passage en `ready` ou `failed` | existant |
| `error_code`, `error_message` | Diagnostic d'échec | existant |
| `llm_usage` | `prompt_tokens`, `cached_tokens`, `completion_tokens`, `cost_eur` — lus dans la réponse OpenAI, servent au quota (§10) et au suivi de coût | **nouveau** |

Champs **supprimés** de `MediaArtifactRecord` : `media_item_id` (remplacé par `scope`/`scope_id`),
`request_fingerprint`, `generation_fingerprint`, `reused_from_artifact_id`, `transcript_s3_key`
(singulier), `transcript_sha256`.

Une fois `status` à `ready`, **l'enregistrement n'est plus jamais modifié**. Il n'y a pas de champ
d'invalidation, pas de « stale », pas de TTL applicatif. Ajouter un média à la collection crée un
écart entre l'instantané et la collection actuelle : cet écart est **la nature même de
l'historique**, pas un défaut à corriger.

### 5.2 Déduplication de courte portée : `artifact_id` déterministe + écriture conditionnelle

C'est le seul point d'idempotence qui reste à traiter, et il se règle **sans table auxiliaire, sans
pointeur, sans verrou**.

    DEDUP_WINDOW_SECONDS = 120

    artifact_id = "art_" + sha256(
        user_id + "|" + scope + "|" + scope_id + "|" + artifact_type
        + "|" + canonical_json(parameters) + "|" + generator_version
        + "|" + ",".join(sorted(source_media_item_ids))
        + "|" + str(int(now_epoch // DEDUP_WINDOW_SECONDS))
    ).hexdigest()[:32]

**À la création (API)** :

1. Calculer `id_now` (fenêtre courante) et `id_prev` (fenêtre précédente).
2. `GetItem(id_prev)` : s'il existe et que son `created_at` est à moins de `DEDUP_WINDOW_SECONDS`,
   le renvoyer tel quel (`200`, `deduplicated: true`). Ce test rattrape le double tap à cheval sur
   une frontière de fenêtre, que le seul découpage temporel laisserait passer.
3. Sinon `PutItem(id_now)` avec `ConditionExpression = attribute_not_exists(artifact_id)`.
   - Succès → enfiler le message SQS, renvoyer `201`.
   - `ConditionalCheckFailedException` → deux requêtes concurrentes du même clic : `GetItem(id_now)`
     et renvoyer l'existant (`200`, `deduplicated: true`). **Aucun message n'est enfilé.**

**À la consommation (worker)** : `mark_artifact_generating` devient **conditionnel** —

    SET status = 'generating', lease_expires_at = now + 300
    IF status = 'queued'
       OR (status = 'generating' AND lease_expires_at < now)

Si la condition échoue (entrée déjà `ready`, déjà `failed`, ou autre worker détenant un bail
vivant), le worker **journalise et rend la main sans appeler le LLM** : le message est acquitté et
disparaît. Cela couvre la redélivrance at-least-once de SQS et le rejeu Lambda, sans nouvelle table.
Le bail de 300 s est calé sur `timeout = 300` de la Lambda ; la `visibility_timeout_seconds` de la
queue vaut 1 800 (`sqs.tf`), donc aucune redélivrance n'arrive avant l'expiration du bail, et un
worker mort en vol laisse l'entrée récupérable.

**Ce que cette mécanique n'est pas** : la fenêtre de 120 s ne porte **aucune sémantique
d'invalidation ni de péremption**. Elle ne dit pas « cet artefact reste valable 120 s » ; elle dit
« deux demandes identiques à moins de 120 s d'écart sont le même clic ». À 121 s, une demande
identique crée une **nouvelle entrée** et régénère : c'est exactement le comportement attendu du
bouton « régénérer », et c'est ce que les mécaniques actuelles (`artifact_idempotence`, pointeurs
`request#`) **empêchent** aujourd'hui.

**Ce qui disparaît** :

| Élément supprimé | Emplacement | Pourquoi |
|---|---|---|
| Table `artifact_idempotence<suffix>` (36 lignes sur `-dev`) | `dynamodb_core_tables.tf` | Son unique rôle est d'empêcher une seconde génération identique — l'inverse du besoin |
| `ArtifactGenerationLock` | `core/models/media_artifact.py` | idem |
| `build_generation_fingerprint`, `build_request_fingerprint` | `core/services/artifact_service.py` | remplacés par l'`artifact_id` déterministe |
| Pointeurs `request#…` (92 lignes sur 168) + `reserve_request_pointer` + `REQUEST_POINTER_PREFIX` | `utils/media_artifacts.py` | polluaient 55 % de la table et devaient être filtrés en Python à chaque liste |
| GSI `request-fingerprint-index`, `generation-fingerprint-index` | `dynamodb_core_tables.tf` | plus de champ à indexer |
| Le drapeau `reused` de `request_artifact_generation` | `artifact_service.py` | remplacé par `deduplicated`, dont le sens est « même clic » et non « on réutilise l'ancien » |

Les artefacts existants de `-dev` sont **jetables** : aucune reprise, aucune couche de
compatibilité, aucune fenêtre de dépréciation. Le contenu S3 déjà produit peut rester en place, il
n'est simplement plus référencé.

### 5.3 Ce qui remplace `artifact_statuses`

Aujourd'hui, `build_status_snapshots` (`artifact_service.py`) construit un dictionnaire « dernier
artefact par type » que le mobile consomme pour savoir quoi afficher. Ce contrat est
**structurellement incompatible** avec un historique : il suppose qu'il y a *un* artefact par type.

Il est **supprimé** — `ArtifactStatusSnapshot`, `build_status_snapshots`, le champ
`artifact_statuses` des réponses média, et le code mobile qui le lit. Rien ne le remplace « à
l'identique ». Ce qui le remplace fonctionnellement :

- **La liste du scope** (`GET /api/artifacts?scope=…&scope_id=…`, §9) renvoie **toutes** les entrées,
  triées par `created_at` décroissant, tous types confondus, avec leur `status`. C'est la source
  unique de l'onglet IA (task-272, task-273).
- **L'état « en cours »** se lit dans cette même liste : les entrées `queued` et `generating` y
  figurent, avec leur type et leur date. Le mobile n'a donc **aucune requête par type d'artefact**
  à faire : une requête par scope sert à la fois la liste et la progression.
- **Le bouton « générer »** n'a plus besoin de savoir si un artefact existe déjà : il est toujours
  actif, sauf refus (§3.4) ou quota (§10). C'est la conséquence directe du modèle append-only.

### 5.4 Origine du titre : émis par le LLM

| Option | Verdict |
|---|---|
| Titre **saisi par l'utilisateur** | écarté : impose une saisie avant chaque génération, alors que le geste doit rester un tap ; et produit des titres vides |
| Titre **dérivé mécaniquement** (« Quiz — 12 mars, 10 sources ») | écarté : c'est de l'habillage de métadonnées déjà affichées à côté (type, date, « N sources ») ; deux entrées du même type le même jour restent indiscernables |
| Titre **émis par le LLM** | **retenu** : le modèle vient de lire le corpus, il est le seul à pouvoir écrire « Les limites du scaling » ; coût marginal ~10 tokens de sortie ; c'est ce qui distingue deux entrées du même type dans l'historique |

Implémentation : ajouter un champ `title` (3 à 80 caractères) **aux cinq schémas de contenu** et aux
validateurs Pydantic correspondants. Le worker recopie le titre sur l'enregistrement DynamoDB lors
du `complete_artifact_generation`, pour que la liste d'historique n'ait **aucun accès S3 à faire** —
c'est ce qui rend l'endpoint de liste tenable (N entrées = 1 requête DynamoDB).

Si le modèle omet le champ malgré le schéma, le validateur rejette la sortie comme pour tout champ
obligatoire, le statut passe `failed`, et la ligne d'historique affiche l'échec. `summary_short` a
déjà un champ `headline` qui joue ce rôle : il est **renommé** `title` pour uniformiser les cinq
types, pas dupliqué.

### 5.5 Le scope média suit exactement la même mécanique

- `scope = "media"`, `scope_id = media_item_id`, `sources` = **un** élément.
- Un tap sur « Résumé » alors qu'un résumé existe déjà crée une **nouvelle** entrée ; l'ancienne
  reste lisible dans l'historique (task-273).
- Aucune vérification « existe-t-il déjà un artefact de ce type ? » nulle part dans le code.
- **Cartes FSRS** : `ReviewScheduleRecord.media_item_id` est aujourd'hui un attribut simple, pas une
  clé (seul `get_cards_by_media_item` le filtre, via `FilterExpression`). Il est remplacé par le
  même couple `scope` / `scope_id`, et `get_cards_by_media_item` / `toggle_spaced_rep_for_media`
  deviennent `get_cards_by_scope` / `toggle_spaced_rep_for_scope`. C'est ce qui permet aux
  flashcards de collection d'entrer dans la file de révision comme les autres — sans quoi elles
  seraient le seul artefact inerte du lot. Le worker passe `scope`/`scope_id` à
  `_init_fsrs_cards` au lieu de `media_item_id`.

---

## 6. Modèle de stockage

### 6.1 Une seule table, pas une table dédiée aux collections

| Option | Verdict |
|---|---|
| **Étendre `media_artifacts` avec un scope** | **retenue** |
| Table `collection_artifacts` dédiée | écartée |

Motifs, dans l'ordre :

1. **Le contenu est identique.** Un `quiz` de collection et un `quiz` de média ont le même schéma,
   le même générateur, le même bucket, le même validateur. Deux tables imposeraient deux chemins de
   lecture, deux services, deux endpoints, et deux composants mobiles — alors que task-273 demande
   explicitement un **composant de ligne d'historique partagé** entre les deux onglets IA.
2. **Un scope à une source est un cas particulier d'un scope à N sources**, pas l'inverse. Séparer
   les tables fige la distinction dans le stockage, où elle n'a aucune conséquence.
3. **La liste et le détail sont les mêmes requêtes.** Avec `scope_key` en clé de hash, le même GSI
   sert les deux onglets IA sans code conditionnel.
4. Le volume ne justifie rien : 168 lignes sur `-dev`, dont 76 réelles.

### 6.2 Le GSI : un seul index, et il est nouveau

Les trois GSI actuels (`media-item-index`, `request-fingerprint-index`,
`generation-fingerprint-index`) sont **hash-only** : ils ne peuvent pas trier. Or task-270 exige une
liste « triée par date décroissante », y compris plusieurs entrées du même type. Un tri applicatif
après `Query` marcherait sur 76 lignes et casserait à la pagination.

    GSI  scope-index
      hash key  = scope_key    (user_id#scope#scope_id)
      range key = created_at   (ISO-8601 UTC, triable lexicographiquement)
      projection = INCLUDE [artifact_type, status, title, source_count,
                            completed_at, error_code]

- **`ScanIndexForward = false`** donne l'ordre chronologique inverse **gratuitement**, sans tri
  applicatif ni pagination cassée.
- **Projection `INCLUDE` et non `ALL`** : la liste n'a alors **aucun accès à la table de base ni à
  S3**. Le champ `sources` (jusqu'à ~5 ko à 25 sources) n'est **pas** projeté — il n'est utile qu'au
  détail, qui interroge la table de base par `artifact_id`. Cela évite de doubler le coût d'écriture
  du plus gros attribut.
- **`user_id` est dans la clé de hash**, donc l'isolation entre utilisateurs est structurelle : une
  requête ne peut pas voir le scope d'un autre. C'est ce qui remplace le contrôle d'accès actuel de
  `get_artifact`, qui passe par `get_media_for_user(record.media_item_id, …)` — impossible à tenir
  pour un artefact de collection puisqu'il n'a pas de média.
- L'index est **sparse** : les 168 lignes existantes n'ont pas de `scope_key`, elles n'y entrent
  donc pas et deviennent invisibles à tous les chemins de lecture, sans script de purge. Un balayage
  `delete-item` ne relève que de la cosmétique.

Ordre des opérations Terraform (`infrastructure/terraform/modules/platform/dynamodb_core_tables.tf`) :

1. `artifact_idempotence_v1` porte `deletion_protection_enabled = true` **et** un
   `lifecycle prevent_destroy = true`. Retirer le bloc de ressource ne suffit pas : il faut d'abord
   passer les deux à `false` et appliquer, **puis** supprimer le bloc et appliquer. **Deux applies,
   dans cet ordre.**
2. Sur `media_artifacts_v1`, remplacer les trois GSI par `scope-index`. DynamoDB n'accepte
   **qu'une création ou suppression d'index par `UpdateTable`** ; le provider AWS enchaîne les
   appels, mais si un apply échoue sur « une seule opération d'index à la fois », **relancer
   `terraform apply`** — l'opération converge (note pour l'owner, §12).
3. `terraform validate` reste vert à chaque étape ; le déploiement réel est un geste owner sur
   `main`.

### 6.3 S3 : aucun changement

`build_artifact_storage_key` produit déjà `<artifact_type>/<artifact_id>.json`, et
`get_artifact_bucket` route vers l'un des cinq buckets par type. Comme `artifact_id` est unique et
encode désormais le scope, **la disposition S3 est inchangée** : pas de nouveau bucket, pas de
nouveau préfixe, pas de renommage. C'est un bénéfice direct du choix « une table, un scope ».

### 6.4 SQS : un message par type, avec les clés et pas le corpus

Le corps du message porte : `artifact_id`, `user_id`, `scope`, `scope_id`, `artifact_type`,
`parameters`, `generator_version`, `prompt_cache_key`, et `sources` — un élément par source avec
`media_item_id`, `title`, `transcript_bucket`, `transcript_s3_key`, `language`.

À 25 sources, cela fait ~5 ko, très loin de la limite de 256 ko de SQS. **Aucun octet de transcript
ne transite par la queue.** La queue, son DLQ, `maxReceiveCount = 3`, `batch_size = 1` et
`visibility_timeout_seconds = 1800` restent tels quels : **aucune ressource SQS nouvelle**.

### 6.5 Worker : trois changements, pas une réécriture

| Aujourd'hui | Demain |
|---|---|
| `_download_transcript(key)` — un seul objet | `_download_transcripts(sources)` — `asyncio.gather` sur N clés (25 × 16 ko = 400 ko en mémoire, Lambda 512 Mo) |
| `generator.build_prompt(transcript, language=…, podcast_title=…, episode_title=…)` | `generator.build_prompt(sources_text, *, language=…)` où `sources_text` est la liste ordonnée (titre + langue + texte) ; le générateur émet préambule → corpus balisé → instructions (§2.6) |
| Enveloppe `source: transcript_s3_key, podcast_title, episode_title` | Enveloppe `scope`, `scope_id`, `sources` (l'instantané), `source_count`, `llm_usage` |

`mark_artifact_generating` devient conditionnel (§5.2) ; `complete_artifact_generation` recopie
`title` et `llm_usage` sur l'enregistrement. `timeout = 300`, `memory_size = 512`,
`LLM_TIMEOUT_SECONDS = 180` : **inchangés** — un seul appel LLM par invocation (§2.3).

Taille de l'item DynamoDB au plafond : ~5 ko pour `sources` + le reste des attributs, contre une
limite de 400 ko. Aucun risque.

---

## 7. Sources non prêtes et langues hétérogènes

### 7.1 Trois états de source, trois traitements

| État de la source | Traitement | Justification |
|---|---|---|
| Transcript disponible | entre dans le corpus | — |
| Transcription ou traduction **en cours** | **refus `409 sources_not_ready`**, avec le nombre et les titres des sources en attente | L'attente est de l'ordre de la minute. Générer sur le sous-ensemble prêt produirait silencieusement un artefact partiel, juste après que l'utilisateur a ajouté ces médias |
| Transcript **définitivement absent** (job en échec, média sans transcript possible) | **source exclue** du corpus, et **tracée dans l'instantané** avec `excluded: true` et un motif | Refuser bloquerait la collection pour toujours à cause d'un seul média cassé. L'exclusion tracée garde l'artefact honnête sur ce qu'il a lu |
| Aucune source exploitable après exclusions | `422 scope_empty` | — |

Le `409` est **réessayable tel quel** : l'utilisateur retape, et comme l'appel précédent a enclenché
les traductions manquantes, elles sont prêtes. Rien n'est écrit en base lors d'un `409`, donc
l'historique ne se pollue pas d'entrées mort-nées.

**Non recommandé** : introduire un délai au bout duquel une traduction « en cours » serait
considérée comme morte. Ce serait une politique de péremption déguisée, et le worker de traduction
a déjà sa propre machine à états (`translation_idempotence`, `queued → in_progress → done | failed`)
qui fait basculer la source vers l'état « définitivement absente » quand il abandonne.

### 7.2 Langues : le corpus est homogénéisé **avant** le LLM

La collection réutilise le chemin existant, source par source : `_resolve_effective_transcript` →
`resolve_or_enqueue_translated_transcript` (task-189 / task-192). Chaque source est résolue vers la
langue de lecture de l'utilisateur (`parameters.language`), en réutilisant la traduction déjà en
cache dans S3 quand elle existe, en enfilant le worker de traduction sinon (d'où le `409` de §7.1).
Le modèle ne voit donc **qu'une seule langue**.

Trois conséquences :

1. L'instantané enregistre la **langue effective par source** et la clé S3 réellement consommée.
   Deux artefacts sur la même collection dans deux langues de lecture ont des `parameters`
   différents, donc des `artifact_id` différents (§5.2), donc deux entrées distinctes — ce qui est
   le comportement correct.
2. **Coût à connaître** : la traduction utilise `gpt-5-nano` (`TRANSLATION_LLM_MODEL`), soit
   ~0,0002 € d'entrée + ~0,0016 € de sortie = **~0,0018 € par source** de 4 622 tokens. Au plafond,
   traduire 25 sources jamais lues coûte **~0,045 €**, c'est-à-dire **plus que la génération des
   cinq artefacts** (0,036 € en cache). Mais cette dépense n'est pas nouvelle et n'est pas
   propre aux collections : c'est le chemin par média d'aujourd'hui, son résultat est mis en cache
   dans S3 et réutilisé par tous les artefacts suivants du même média. Une collection de médias
   déjà lus dans la langue de l'utilisateur ne paie **rien**.
3. Le worker de traduction est déjà idempotent et verrouillé par empreinte
   (`translation_idempotence`), donc 25 résolutions en parallèle n'enfilent pas de doublon.

**Alternative écartée** : envoyer un corpus multilingue et demander au modèle de rédiger dans la
langue cible. Cela économiserait les ~0,045 € du pire cas et supprimerait le `409`, mais : les
citations de `summary_detailed` sortiraient dans la langue de la source alors que le reste est dans
la langue de lecture ; le même média produirait des artefacts différents selon qu'il est lu seul ou
en collection ; et l'instantané ne pourrait plus désigner un texte source unique. La cohérence
entre les deux scopes vaut plus que 4,5 centimes.

---

## 8. Attribution des sources

Deux niveaux, et seulement deux.

**Niveau artefact — l'instantané.** `sources` (liste ordonnée : `media_item_id`, titre, clé de
transcript, langue, `excluded`) plus `source_count`. C'est ce que l'onglet IA affiche sous forme
« N sources » (task-272), et ce qui permet d'ouvrir la liste des médias réellement lus, y compris
ceux qui ont depuis quitté la collection.

**Niveau contenu — le renvoi `[Sk]`.** Le corpus est balisé `[S1] … [Sn]` dans l'ordre de
`sources`. Les schémas de sortie gagnent un champ de renvoi :

| Type | Renvoi | Obligatoire ? |
|---|---|---|
| `summary_detailed` | `notable_quotes` passe de `List[str]` à une liste d'objets `text` + `source_ref` | **oui** — une citation est verbatim, sa provenance est vérifiable |
| `flashcards` | `source_ref` par carte | facultatif (`null` si la carte croise plusieurs sources) |
| `quiz` | `source_ref` par question | facultatif |
| `summary_short`, `notes` | aucun | non — ce sont des synthèses transversales par nature |

Le renvoi est le **label `[Sk]`**, pas un `media_item_id` : le modèle recopie un jeton court et
l'API le résout via l'index dans `sources`. Cela évite de faire écrire au modèle des UUID (source
classique d'hallucination) et coûte ~3 tokens par élément.

**Écarté** : exiger un renvoi sur chaque `key_point`. Un point de synthèse agrège légitimement
plusieurs sources, le modèle inventerait donc un renvoi arbitraire ; et cela gonflerait la sortie
sans bénéfice vérifiable. Les citations sont le seul contenu dont la provenance est objectivement
définie.

---

## 9. Exposition API et polling mobile

### 9.1 Quatre routes, dont deux qui remplacent les routes par média

Le routeur est monté avec `prefix="/api"` (`api/main.py`), donc les routes apparaissent dans
`/openapi.json` sans configuration supplémentaire.

| Méthode | Chemin | Rôle | Codes |
|---|---|---|---|
| `POST` | `/api/artifacts` | Demander une génération. Corps : `scope`, `scope_id`, `artifact_type`, `parameters` | `202` créée, `200` dédupliquée, `409` sources pas prêtes, `422` `scope_empty` / `scope_too_large`, `403`/`429` quota, `400` type désactivé, `503` génération désactivée |
| `GET` | `/api/artifacts` | Historique d'un scope : `scope`, `scope_id`, `limit`, `cursor`. **Tri `created_at` décroissant, tous types confondus** | `200`, `404` scope inconnu ou non possédé |
| `GET` | `/api/artifacts/{artifact_id}` | Une entrée avec son instantané complet | `200`, `404` |
| `GET` | `/api/artifacts/{artifact_id}/content` | Le contenu JSON depuis S3 | `200`, `404`, `409` si pas `ready` |

**Supprimées** : `POST /api/media/{media_item_id}/artifacts` et
`GET /api/media/{media_item_id}/artifacts`. Le scope média passe par les mêmes routes que la
collection, avec `scope = "media"`. Pas d'alias, pas de redirection, pas de fenêtre de dépréciation.

Le contrôle d'accès change de nature : `get_artifact` et `get_artifact_content` vérifient
aujourd'hui la propriété via `get_media_for_user(record.media_item_id, …)`, ce qui n'a pas de sens
pour un artefact de collection. Ils comparent désormais `record.user_id` à l'utilisateur
authentifié — une comparaison, plus une requête.

### 9.2 Forme de la réponse de liste

La réponse de `GET /api/artifacts` est plate et suffit à peindre l'onglet IA sans second appel :

    @@LB@@
      "scope": "folder",
      "scope_id": "c4ef2e55-...",
      "artifacts": [
        @@LB@@
          "artifact_id": "art_9f3c...",
          "artifact_type": "summary_detailed",
          "status": "ready",
          "title": "Les limites du scaling",
          "source_count": 7,
          "created_at": "2026-08-17T09:12:44Z",
          "completed_at": "2026-08-17T09:13:31Z",
          "error_code": null
        @@RB@@,
        @@LB@@
          "artifact_id": "art_1b70...",
          "artifact_type": "quiz",
          "status": "generating",
          "title": null,
          "source_count": 7,
          "created_at": "2026-08-17T09:12:44Z",
          "completed_at": null,
          "error_code": null
        @@RB@@
      ],
      "next_cursor": null
    @@RB@@

Ce sont exactement les attributs projetés par le GSI (§6.2) : **une requête DynamoDB, aucun accès
S3, aucun accès à la table de base**. `sources` (l'instantané détaillé) n'est renvoyé que par
`GET /api/artifacts/{artifact_id}`, quand l'utilisateur ouvre l'entrée.

### 9.3 Polling

Une seule règle : **une requête par scope, jamais une par type**.

- Le mobile appelle `GET /api/artifacts?scope=…&scope_id=…` toutes les **3 s** tant qu'au moins une
  entrée est `queued` ou `generating`.
- Au bout de **60 s**, l'intervalle passe à **10 s** ; au bout de **5 min**, le polling s'arrête et
  l'entrée reste affichée dans son dernier état connu (le worker finira par la basculer en `ready`
  ou `failed` ; un pull-to-refresh la rafraîchira).
- Le polling s'arrête dès qu'aucune entrée n'est en vol.

La progression en vol se lit donc dans la **même** réponse que l'historique : le mobile n'a besoin
d'aucun endpoint de statut, ce qui satisfait « progression en vol sans requête par type d'artefact »
(task-270) et « état en vol rendu » (task-272 AC#7) avec un seul appel réseau.

---

## 10. Quota et paywall

### 10.1 Pourquoi les quotas existants ne suffisent pas

`quota_enforcer.check_submission_allowed` borne les **imports** : minutes audio, articles, documents,
YouTube, avec des caps mensuels et des limites journalières (`pricing_config`, task-110, chiffrés par
task-65 §9.2-9.3). Le coût LLM des artefacts d'un média est **déjà budgété** dans le coût unitaire
par média de task-65 (0,0051 € pour un texte, 0,0104 € pour un podcast de 45 min) : importer un
média et générer ses artefacts est donc couvert.

Deux dépenses échappent à ce cadre, et ce sont exactement celles que task-269/270 introduisent :

1. **Les générations de collection**, qui coûtent jusqu'à 25× une génération par média
   (0,0364 € à 0,0903 € pour les cinq types au plafond, §2.6) sans consommer aucun quota d'import.
2. **Les régénérations**, que le modèle append-only rend non seulement possibles mais **attendues** :
   plus rien dans le code ne dit « tu as déjà cet artefact ». Un utilisateur peut relancer les cinq
   types à volonté sur le même scope.

### 10.2 Deux compteurs nouveaux, un filet existant

**(a) Limite journalière de générations — les deux scopes.**

    rate_limits.<tier>.ai_generations_per_day

Compteur journalier `ai_generations` dans `user_usage_daily` (TTL de 3 jours déjà en place),
incrémenté avec `increment_daily_usage(..., idempotency_token=artifact_id)` — le token empêche un
double débit sur rejeu. Refus : `429`, `error_code = daily_rate_limit`.

| Tier | `ai_generations_per_day` |
|---|---|
| Text-Only (3 €) | **30** |
| Mix (5 €) / essai gratuit | **50** |
| Audio-Heavy (9 €) | **80** |

C'est la limite qui borne le « je retape sur régénérer ». 30 générations/jour, c'est six fois les
cinq types : très au-delà d'un usage normal, très en dessous d'une boucle abusive.

**(b) Cap mensuel en unités-source — scope collection uniquement.**

    hard_caps.<tier>.collection_source_units

**1 unité = une source dans une génération.** Une génération sur 7 sources consomme 7 unités.
Compteur mensuel `collection_source_units` dans `user_usage_monthly`. Refus : `403`,
`error_code = tier_quota_exceeded`.

Ce compteur ne s'applique **pas** au scope média (déjà budgété, §10.1) : le compter deux fois
reviendrait à facturer deux fois la même dépense et casserait des usages nominaux (200 médias × 2
artefacts = 400 unités à eux seuls).

| Tier | `collection_source_units` / mois | Coût LLM pire cas (froid) | Avec cache |
|---|---|---|---|
| Text-Only | **400** | 0,38 € | 0,10 € |
| Mix / essai gratuit | **800** | 0,76 € | 0,19 € |
| Audio-Heavy | **1 200** | 1,14 € | 0,29 € |

(Hypothèse : 0,00079 € d'entrée par unité à froid, 8 sources en moyenne par génération, ~0,0013 € de
sortie par génération — §2.6 et sortie de `compute.py`.) Sur Text-Only, 400 unités = **57
générations** de 7 sources par mois. Le pire cas reste sous **18 %** du revenu net d'un tier à 3 €
(2,125 € selon task-65), et sous 5 % avec le cache.

**(c) Le filet existant : `cost_eur_estimated`.**

`check_submission_allowed` §5 bloque déjà à `cost_monitoring.hard_block_eur` (3,5 € / 6 € / 10 €
selon le tier, task-65 §9.4) sur le compteur mensuel `cost_eur_estimated` — mais **rien n'y écrit
le coût des artefacts aujourd'hui**. Le worker doit désormais l'alimenter avec le coût **réellement
mesuré** :

    increment_monthly_usage(user_id, cost_eur=<llm_usage.cost_eur>,
                            idempotency_token=artifact_id)

où `cost_eur` est calculé à partir du bloc `usage` renvoyé par OpenAI (`prompt_tokens`,
`prompt_tokens_details.cached_tokens`, `completion_tokens`) et des prix du modèle. C'est le
verrou qui rattrape tout ce que (a) et (b) laisseraient passer, il existe déjà, il suffit de le
brancher.

### 10.3 Ordre des vérifications dans `POST /api/artifacts`

L'ordre importe, parce qu'une demande dédupliquée ne doit **rien** consommer :

1. Propriété du scope (`404` sinon).
2. Résolution des sources : descendants, transcripts effectifs, exclusions (§7).
3. Plafonds `MAX_COLLECTION_SOURCES` / `MAX_COLLECTION_CORPUS_TOKENS` → `422`.
4. **Déduplication** (§5.2) : si l'entrée existe déjà, renvoyer `200` **sans toucher aux
   compteurs**.
5. Quota : (a) puis (b) → `429` / `403`.
6. `PutItem` conditionnel, incrément des compteurs avec `idempotency_token = artifact_id`, envoi SQS,
   `202`.

### 10.4 Ce qui n'est pas un levier commercial

**`MAX_COLLECTION_SOURCES` ne dépend pas du tier.** C'est une limite de la fenêtre du modèle, pas un
avantage à vendre : un tier payant ne peut pas acheter 50 sources dans un contexte de 272 000 tokens.
Les tiers se différencient sur le **nombre de générations** et le **volume mensuel d'unités**, pas
sur la taille d'une collection. Vendre le plafond obligerait à changer de stratégie d'agrégation
(§3.5), ce qui est une décision de benchmark, pas de pricing.

Les deux valeurs (a) et (b) vivent dans `pricing_config<suffix>` (DynamoDB), donc **ajustables sans
déploiement** — c'est tout l'intérêt de la table introduite par task-110.

---

## 11. Ce que task-270 doit implémenter, dans l'ordre

**1. Modèle et service (le socle).**

- `core/models/media_artifact.py` : `MediaArtifactRecord` prend `user_id`, `scope`, `scope_id`,
  `scope_key`, `title`, `source_count`, `sources`, `lease_expires_at`, `llm_usage` ; perd
  `media_item_id`, `request_fingerprint`, `generation_fingerprint`, `reused_from_artifact_id`,
  `transcript_s3_key`, `transcript_sha256`. Supprimer `ArtifactGenerationLock` et
  `ArtifactStatusSnapshot`. Retirer le type `summary` résiduel du jeu de valeurs acceptées si un
  quelconque chemin le tolère encore.
- `core/services/artifact_service.py` : supprimer `build_request_fingerprint`,
  `build_generation_fingerprint`, `build_status_snapshots` ; ajouter `build_artifact_id` (§5.2) ;
  `request_artifact_generation` prend `(scope, scope_id, artifact_type, parameters)` et renvoie
  `(record, deduplicated)` ; nouvelle résolution de sources `resolve_scope_sources` qui appelle
  `_get_descendant_ids` pour `scope = folder` et `_resolve_effective_transcript` par source en
  parallèle ; nouvelles exceptions `ArtifactScopeEmptyError`, `ArtifactScopeTooLargeError`.
- `utils/media_artifacts.py` : supprimer `REQUEST_POINTER_PREFIX`, `reserve_request_pointer`,
  `REQUEST_FINGERPRINT_INDEX`, `GENERATION_FINGERPRINT_INDEX`, `MEDIA_ITEM_INDEX`,
  `safe_list_media_artifacts_by_media_item` ; ajouter `SCOPE_INDEX` et
  `list_artifacts_by_scope(scope_key, limit, cursor, forward=False)`.

**2. Générateurs et worker.**

- Les cinq générateurs : `build_prompt(sources, *, language)`, mise en page préambule → corpus
  balisé → instructions (§2.6) ; champ `title` obligatoire dans les cinq schémas (`headline` de
  `summary_short` renommé) ; `notable_quotes` devient une liste d'objets `text` + `source_ref` ;
  `source_ref` facultatif sur les cartes et les questions.
- `workers/artifact_generator/worker.py` : téléchargement parallèle des N transcripts ;
  `mark_artifact_generating` conditionnel avec bail (§5.2) ; enveloppe portant `scope`, `scope_id`,
  `sources`, `source_count`, `llm_usage` ; `prompt_cache_key` dans le payload OpenAI ; recopie de
  `title` et `llm_usage` sur l'enregistrement ; incrément de `cost_eur_estimated` (§10.2c) ;
  `_init_fsrs_cards` reçoit `scope`/`scope_id`.
- `_shuffle_options` du quiz reste inchangé : il se sème sur `artifact_id`, qui reste unique.

**3. API.**

- `api/endpoints/artifacts.py` : les quatre routes de §9.1, suppression des deux routes
  `/media/{media_item_id}/artifacts`, contrôle de propriété par `record.user_id`, les quatre refus
  typés de §3.4, plus le retrait du filtrage Python des lignes `request#`.
- Retirer `artifact_statuses` de toutes les réponses média (`api/endpoints/media.py` et les modèles
  de réponse associés).

**4. Quota.**

- `core/services/quota_enforcer.py` : `check_artifact_generation_allowed(user_id, scope,
  source_count)` lisant `rate_limits.<tier>.ai_generations_per_day` et
  `hard_caps.<tier>.collection_source_units`.
- `utils/quota_usage_db.py` : compteur journalier `ai_generations`, compteur mensuel
  `collection_source_units`.
- Semer les valeurs de §10.2 dans `pricing_config<suffix>`.

**5. FSRS.**

- `core/models/review_schedule.py`, `utils/review_db.py`, `core/services/fsrs_service.py` :
  `media_item_id` → `scope` + `scope_id`, `get_cards_by_media_item` → `get_cards_by_scope`,
  `toggle_spaced_rep_for_media` → `toggle_spaced_rep_for_scope`.

**6. Terraform.**

- `dynamodb_core_tables.tf` : sur `media_artifacts_v1`, les trois GSI remplacés par `scope-index`
  (hash `scope_key`, range `created_at`, projection `INCLUDE`) ; suppression de
  `artifact_idempotence_v1` **en deux applies** (§6.2). Aucune ressource S3 ni SQS nouvelle.

**7. Vérifications que l'agent d'implémentation peut réellement faire.**

- `ruff` et `mypy` verts.
- `terraform validate` vert.
- Lecture directe sur le `-dev` : `aws dynamodb describe-table --table-name media_artifacts-dev`
  montre `scope-index` et **ne montre plus** les deux index d'empreinte ;
  `aws dynamodb list-tables` ne contient plus `artifact_idempotence-dev` ; une `query` sur
  `scope-index` avec `--no-scan-index-forward` renvoie les entrées du plus récent au plus ancien.
- Grep de non-régression : aucune occurrence restante de `artifact_statuses`,
  `build_status_snapshots`, `request_fingerprint`, `generation_fingerprint`, `REQUEST_POINTER_PREFIX`,
  `reused_from_artifact_id` dans le dépôt.

**8. Ordre vis-à-vis des tâches UI.** task-270 supprime le contrat `artifact_statuses` ; task-272 et
task-273 reconstruisent les deux onglets IA sur la liste par scope. **task-270 passe d'abord**, sinon
les tâches UI câblent un contrat qui va disparaître.

---

## 12. Risques, angles morts et notes pour l'owner

### 12.1 Notes d'exploitation (gestes owner, pas des critères d'acceptation)

**Séquence Terraform.** DynamoDB n'autorise **qu'une** création et **qu'une** suppression d'index par
`UpdateTable`, et interdit d'ajouter ou de supprimer un autre index pendant qu'un index est en
`CREATING`. Passer de trois GSI à un seul demanderait donc trois `UpdateTable` enchaînés. Comme les
168 lignes de `-dev` sont jetables, il est plus simple de **recréer la table** :

1. Apply 1 : `deletion_protection_enabled = false` et retrait des blocs `lifecycle prevent_destroy`
   sur `media_artifacts_v1` **et** `artifact_idempotence_v1`.
2. Apply 2 : bloc `artifact_idempotence_v1` supprimé, nouveau schéma d'index sur
   `media_artifacts_v1`, avec
   `terraform apply -replace='module.platform.aws_dynamodb_table.media_artifacts_v1'` →
   un seul `CreateTable` avec la disposition finale, pas de valse d'`UpdateTable`.
3. Apply 3 : rétablir `deletion_protection_enabled = true` et `prevent_destroy = true` sur
   `media_artifacts_v1`.

L'agent d'implémentation écrit le Terraform et fait passer `terraform validate` ; **les applies sont
des gestes owner**, comme le redéploiement de l'image Lambda au push sur `main`.

**Vérification E2E manuelle après déploiement.** La collection de `-dev` qui contient 11 médias
(`folder_id` visible via la commande de §1.1) est le cas de test naturel : générer les cinq types,
vérifier que l'onglet IA liste cinq entrées horodatées, relancer un type et vérifier qu'une
**sixième** entrée apparaît au-dessus sans écraser la précédente, puis vérifier qu'un double tap
rapide n'en crée qu'une.

**Le blocage de coût va enfin se déclencher.** Aujourd'hui `cost_eur_estimated` n'est alimenté que
par l'ingestion ; à partir de task-270, le worker d'artefacts y écrit aussi (§10.2c). Les seuils
`hard_block_eur` de task-65 (3,5 / 6 / 10 €) ont été dimensionnés sans cette contribution. Ils
restent larges au vu des chiffres de §10.2, mais c'est un paramètre à surveiller au premier mois
d'usage réel.

### 12.2 Angles morts assumés

| Risque | Portée | Ce qui est fait / pas fait |
|---|---|---|
| **Le comptage de tokens est une approximation** (3,4 o/token, `tiktoken` absent de l'image) | ±10 % sur la décision de refus | Assumé : la marge de 2,3 entre le plafond et la fenêtre l'absorbe. Embarquer `tiktoken` dans l'image Lambda ajouterait un téléchargement d'encodage au démarrage à froid pour un gain sans usage |
| **Le taux de succès du cache de prompt n'est pas garanti** | coût ×2,5 dans le pire cas | Non bloquant : le pire cas (0,0903 € au plafond pour les cinq types) reste acceptable. `llm_usage.cached_tokens` permet de mesurer le taux réel après déploiement |
| **Qualité d'un artefact mono-passe sur 25 sources hétérogènes : non mesurée** | qualité perçue | Aucun jeu d'évaluation n'existe et en créer un impliquerait du trafic LLM, hors périmètre. Si `quiz` ou `flashcards` paraissent dilués au-delà de ~15 sources, le levier est un **plafond par type** (moins de sources pour les types extractifs), pas un changement de stratégie |
| **Premier `409` sur une collection fraîche** dont plusieurs sources ne sont pas encore traduites | friction UX | Assumé et signalé : le corps du `409` donne le nombre et les titres des sources en attente, et l'appel a déjà enclenché les traductions |
| **L'historique croît sans fin** — pas de suppression d'entrée, pas de TTL | stockage, lisibilité de la liste | **Hors périmètre de task-270 et volontairement pas recommandé** : un TTL serait une péremption, ce que l'owner exclut. Une suppression *explicite par l'utilisateur* est un sujet produit distinct, à ouvrir plus tard si la liste devient longue |
| **Les 17 lignes de type `summary`** (legacy pré-task-195) | données `-dev` | Elles n'ont pas de `scope_key` : le GSI sparse les ignore et aucun chemin de lecture ne les voit. Aucune purge nécessaire |
| **Une collection peut contenir un média retiré depuis** | cohérence perçue | C'est le comportement voulu (contrainte d'entrée n° 3). L'instantané le documente ; l'UI affiche « N sources » d'après l'instantané, pas d'après la collection actuelle |

### 12.3 Ce que ce benchmark ne tranche pas

- **La suppression d'un artefact d'historique** (geste utilisateur) : hors périmètre.
- **Un type d'artefact propre aux collections** (par ex. « comparer ces sources ») : task-269 ne
  couvre que les cinq types existants appliqués à un nouveau scope.
- **Le seuil de bascule vers une architecture RAG** si le plafond de 25 devient gênant : ce serait un
  nouveau benchmark, avec le store de vecteurs comme sujet principal.
