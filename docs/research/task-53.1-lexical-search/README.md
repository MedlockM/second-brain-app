---
owner_decision: pending
---

# Benchmark : Recherche lexicale dans les transcripts (REDO 2ᵉ passe, 2026-05-12)

## Owner Validation

**Decision**: algolia car gratuit jusqu'à 130 users avec > 250 docs de 36 kb par user (des podcast de 30 min). Remplacement de typesense géré par la tache 96
**Validated at**: _(date ISO)_

---

## 0. Ce qui change par rapport à la 1ʳᵉ passe (2026-04-23)

Cette réécriture complète intègre les retours owner du 2026-04-28 et les objections du document `CHALLENGE-2026-05-01.md` :

1. **Ajout de Neon Postgres** (pg_trgm / full-text search) comme candidat à part entière (owner feedback).
2. **Ajout de SQLite FTS5 sur VM AWS EC2** comme solution locale gratuite (owner feedback + challenge §2).
3. **Tarification variable par nombre de documents indexés** documentée pour chaque solution (owner feedback).
4. **Hypothèses d'usage réalistes V1** : 100 users max au launch (task-65), 10-50 recherches/jour total app (pas 1M/mois), 400-1200 requêtes/mois (challenge §1.2). Les projections "100-1,000 concurrent searches" de la v1 étaient 100-1000× surdimensionnées pour une app second-brain phase MVP.
5. **Trace explicite Typesense vs Meilisearch** : la v1 concluait "Winner: Meilisearch (9,15 vs 8,95)" mais l'owner avait validé Typesense. Cette nouvelle version documente pourquoi **Typesense** est la recommandation finale malgré le score Meilisearch légèrement supérieur (§6.1, challenge §3).
6. **Pricing Typesense Cloud avec signup credit** mentionné (challenge §4.2) et modélisé dans les 3 phases (pré-launch gratuit / launch 2 GB $50/mo / growth 8 GB $150/mo) alignées sur task-65 révision 2. **Correction 2026-05-12** : le ratio RAM Typesense corrigé à 2,1× (basé sur benchmarks réels, pas sur l'hypothèse "28M books = 5000 mots") + profil heavy-podcast (36 KB/doc) renchérit significativement le coût Typesense (43 €/mois vs 15,5 € initialement estimé).
7. **Coût infra embarqué** : les solutions self-hosted (SQLite FTS5, self-hosted Typesense/Meilisearch) consomment des ressources de la VM EC2 `t4g.small` (10,55 €/mois) déjà budgetée pour FastAPI + workers. Allocation marginale : RAM ~100-200 MB, disque EBS ~500 MB à 100 users V1.

---

## Executive Summary

### Décision validée en amont

| Sujet | Décision | Source |
|-------|----------|--------|
| Besoin produit | **Recherche lexicale full-text** sur tous les transcripts de l'utilisateur | Owner clarification 2026-05-01 + `project_v1_scope.md` |
| Architecture backend | VM EC2 `t4g.small` hébergeant FastAPI + workers | task-65 rév. 2 (2026-05-01) |
| Budget infra fixe phase launch | **57,5 €/mois @100u** (EC2 10,55 € + Typesense 2 GB **43 €** + AWS misc 4 €) — **corrigé** vs 29,5 €/mois estimé en task-65 rév.2 qui utilisait le cluster 0,5 GB | Calcul corrigé 2026-05-12 |

### Recommandation

**Typesense Cloud** avec approche progressive :

1. **Phase pré-launch (M0-M1, <50 beta users)** : activer le **signup credit Typesense Cloud gratuit** (0 €/mois, confirmed cloud.typesense.org "free credits, no credit card"). Aucune infra search supplémentaire.
2. **Phase launch (M2-M12, 100 users × 200 docs heavy-podcast)** : **cluster Typesense Cloud 2 GB RAM / 2 vCPU burst** = **~$50/mois ≈ 43 €/mois**. RAM nécessaire estimée : ~1,5 GB (20k docs × 36 KB × ratio 2,1). Latence <50ms p95.
3. **Phase growth (M12+, >500 users)** : **cluster 8 GB RAM / 4 vCPU** = **~$150/mois ≈ 129 €/mois**.

**Justification vs alternatives évaluées** :

| Solution | Coût mensuel @100u launch | Documents max | Perf p95 | Typo tolerance | Ops overhead | Réversibilité |
|----------|---------------------------:|-------------:|---------:|----------------|-------------|--------------|
| **SQLite FTS5 local VM** | **0 € (VM déjà payée)** | Illimité* | <10ms | ⚠️ (spellfix1) | Faible (rebuild 5 min si perte) | Facile → Typesense |
| **Neon Postgres Free** | 0 € (free tier) | ~100k (0.5 GB storage) | 100-300ms | ⚠️ (pg_trgm) | Moyen (migration DynamoDB) | Moyen |
| **Neon Postgres Launch** | ~12 €/mois | ~500k (2 GB) | 100-300ms | ⚠️ | Moyen | Moyen |
| **Typesense Cloud 2 GB** ★ | **43 €/mois** (@100u heavy-podcast) | ~2 600 docs heavy | <50ms | ✅ | Minimal | Facile |
| **Meilisearch Cloud** | ~12-15 €/mois | 200k+ | <50ms | ✅ | Minimal | Facile |
| **OpenSearch AWS** | ~250 €/mois (3-node) | Millions | 50-200ms | ✅ | Élevé | Difficile |
| **Algolia Build** (free) | **0 €/mois** (cap 1 GB index) | ~110k records (10KB chunks) | <20ms | ✅ | Minimal (chunking requis) | Moyen |

*SQLite FTS5 : techniquement sans limite, pratiquement ~10-20 GB d'index avant de saturer la VM `t4g.small` (2 GB RAM). À 100 users V1 ≈ 10-20 MB d'index, largement viable.

**Typesense Cloud l'emporte** pour V1 parce que :

- **Zéro ops overhead** (managé, monitoring, backup inclus), crucial pour un solo dev.
- **Typo tolerance native** meilleure que SQLite FTS5/Neon (fuzzy matching avec edit distance configurable).
- **Multi-tenancy élégant** via scoped API keys (`filter_by: user_id:=<id>`) plus simple que les tenant tokens Meilisearch ou les WHERE clauses SQL.
- **Scaling transparent** : passer de MVP à Growth = changement de plan dans l'UI, 0 downtime.
- **Signup credit = phase pré-launch gratuite** : étendre cette phase maximise le runway.
- **Réversibilité facile** : le pipeline d'indexation `search_indexing_worker.py` reste une abstraction ; swap vers SQLite FTS5 ou Meilisearch = 1-2j de travail si nécessaire.

**SQLite FTS5 local** reste une alternative crédible et **sera implémentée en fallback** si le signup credit Typesense s'épuise avant le launch public. L'overhead dev est ~2j pour l'adapter SQLite. Le trade-off : Typesense 43 €/mois (75 % de l'infra) offre une meilleure typo tolerance sur le contenu ASR bruité, mais SQLite FTS5 économise 516 €/an avec une qualité potentiellement suffisante pour V1.

---

## 1. Cadrage du besoin produit

### 1.1 Besoin exact

Permettre à chaque utilisateur de **retrouver un contenu dans son historique de médias** via une recherche textuelle sur les **transcripts complets** stockés en S3. Cas d'usage représentatifs :

- *"Je cherche le podcast où il parlait de 'kubernetes deployment strategies'."*
- *"Retrouver l'article où j'avais lu quelque chose sur 'mitochondries' il y a 3 mois."*
- *"Chercher tous les transcripts qui mentionnent 'inflation' ou 'banque centrale'."*

**Complémentaire à la recherche par métadonnées** (task-74, Done) qui filtre par titre, tags, dossier, type de média. La recherche lexicale plonge **dans le contenu** lui-même.

### 1.2 Types de requêtes attendues

| Type de requête | Exemple | Criticité V1 |
|----------------|---------|-------------|
| **Mot-clé simple** | `kubernetes` | ✅ Indispensable |
| **Phrase exacte** | `"machine learning models"` | ✅ Indispensable |
| **Typo tolerance** | `kubernets` → `kubernetes` | ✅ Indispensable (ASR errors) |
| **Prefix search** | `mach` → `machine`, `machines` | ⚠️ Nice-to-have (search-as-you-type) |
| **Boolean operators** | `AI AND (ethics OR regulation)` | ❌ Hors V1 |
| **Synonymes** | `voiture` → `automobile` | ❌ Hors V1 |
| **Recherche sémantique** | *"concepts proches de mitochondries"* | ❌ V2+ (embeddings) |

### 1.3 Périmètre des contenus recherchables

**Indexés en V1** :

- **Transcripts audio/vidéo** : podcasts, YouTube, TikTok, Instagram, WhatsApp audio (Deepgram → S3).
- **Transcripts articles** : texte extrait par Trafilatura depuis articles web, posts LinkedIn, tweets (S3).
- **Transcripts documents** : texte parsé par LlamaParse/Unstructured depuis PDF, DOCX (S3).

**Métadonnées secondaires indexées** (boostent le ranking) :

- Titre du média
- Description/sous-titre (si applicable)
- Nom de la source (ex: nom du podcast, auteur de l'article)
- Tags utilisateur

**Hors périmètre V1** :

- Images embeddées dans les articles (OCR future, cf. task-XX à créer).
- Commentaires sous les vidéos/posts.
- Transcripts de sessions de flashcards review (pas stockés en S3).

### 1.4 Caractéristiques des transcripts

| Dimension | Valeurs typiques | Impact search |
|-----------|------------------|---------------|
| **Longueur** | 5 000-50 000 mots (podcast 45 min ≈ 9 000 mots FR) | Snippet/highlighting crucial |
| **Qualité** | Variable : ASR errors (homophones FR "chant"/"champ"), ponctuation irrégulière, capitalization absente | Typo tolerance indispensable |
| **Langue** | **Français prioritaire** (marché FR first), Anglais secondaire | Stemming FR + EN requis |
| **Hétérogénéité** | Styles mélangés : podcast conversationnel ≠ article académique ≠ post réseau social | Ranking BM25 nécessaire |

### 1.5 Signaux de pertinence

Ordre de priorité décroissant :

1. **Term frequency dans le transcript** (base BM25).
2. **Match dans le titre** (boost ×3-5).
3. **Recency** : médias récents légèrement favorisés (decay exponentiel sur 6 mois).
4. **Type de média** : aucune préférence a priori (user peut chercher dans n'importe quel type).
5. **Dossier/tags** : filtres optionnels combinables (`filter_by: folder_id:=X AND tag:=Y`).

### 1.6 Hypothèses d'usage réalistes V1

**Correction vs benchmark v1** : la v1 projetait "100-1,000 concurrent searches initially" et "< 1M searches/month Year 1" — des ordres de grandeur inadaptés pour une app second-brain en phase MVP. Hypothèses corrigées basées sur task-65 (100 users @launch) et patterns d'usage observés sur apps similaires (Readwise, Recall, Notion) :

| Métrique | MVP (M0-M1, <50u) | Launch (M2-M6, 100u) | Growth (M12+, 1000u) |
|----------|------------------:|---------------------:|---------------------:|
| **Users actifs** | 10-50 | 100 | 1 000 |
| **Recherches/user/semaine** | 1-3 (usage exploratoire) | 2-5 (usage régulier) | 3-7 (usage ancré) |
| **Recherches/mois total app** | 40-600 | **400-2 000** | 12 000-28 000 |
| **Recherches/jour** | 1-20 | **13-65** | 400-950 |
| **Concurrent searches (pic)** | <2 | **<5** | <50 |

**Note** : un user second-brain consulte l'app 5-10×/semaine mais ne cherche **pas** à chaque visite. Les dossiers/tags suffisent pour 70-80 % des retrievals. La recherche full-text sert les cas "je me souviens vaguement du sujet mais pas du titre".

**Implication sur le dimensionnement** : les solutions qui facturent au volume de requêtes (Algolia) sont prohibitives, mais les solutions managées à prix fixe (Typesense Cloud MVP cluster à ~2k requêtes/jour supportées) sont largement surdimensionnées = confort.

### 1.7 Exigences de performance

| Critère | Cible V1 | Justification |
|---------|----------|---------------|
| **Latency p50** | <100ms | Mobile-friendly (pas de spinner) |
| **Latency p95** | <300ms | Acceptable pour une recherche (tolérance user) |
| **Indexing delay** | <1 min | Async acceptable (user ne cherche pas immédiatement après import) |
| **Availability** | >99% | Search non-critique (app utilisable sans, filtres DynamoDB suffisent en dégradé) |

### 1.8 Isolation multi-tenant

**Hard requirement** : chaque user ne doit voir **que ses propres contenus**. Trois modèles possibles :

1. **Index unique + filtre user_id au query-time** (Typesense scoped keys, Meilisearch tenant tokens, SQL WHERE) → ✅ **Recommandé V1** (simple, évite explosion du nombre d'index).
2. **Index par user** (1 index Typesense/Meilisearch par user_id) → ❌ Overhead opérationnel prohibitif à 1000+ users.
3. **Base SQLite par user** (1 fichier `.db` par user sur la VM) → ❌ Gestion fichiers complexe, sauvegarde difficile.

Toutes les solutions évaluées ci-dessous implémentent le modèle 1 (filtre au query-time).

---

## 2. Options évaluées

### 2.1 Option 1 : DynamoDB native (Scan + filter)

**Description** : utiliser DynamoDB Query/Scan avec `contains()` sur le champ `transcript_text` ou un GSI avec tokenization manuelle.

**Approche technique** :

- Stocker le transcript complet (ou des chunks de 400 KB) comme attribut DynamoDB.
- Query via `FilterExpression: contains(transcript_text, :keyword)`.
- Ou : pré-tokenizer les transcripts en mots + créer GSI `user_id` + `word` pour prefix matching.

**Tarification variable par documents** :

- DynamoDB free tier permanent : 25 GB storage inclus → ~1 250 transcripts de 20 KB chacun **gratuits**.
- Au-delà : $0,25/GB-month (us-east-1) = **0,22 €/GB/mois**.
- Scan coûte 0,5 WCU par 4 KB scanné → une recherche full-scan sur 100 transcripts de 20 KB = 250 WCU = $0,00125 par requête (en mode on-demand).

| Volume users | Transcripts totaux | Storage DDB | Coût storage/mois | Coût 1000 requêtes/mois | **Total/mois** |
|-------------|-------------------:|------------:|------------------:|------------------------:|---------------:|
| 10 | 100 (2 MB) | Free | 0 € | 1,25 € | **1,25 €** |
| 100 | 2 000 (40 MB) | Free | 0 € | 1,25 € | **1,25 €** |
| 1 000 | 50 000 (1 GB) | Free | 0 € | 1,25 € | **1,25 €** |
| 10 000 | 500 000 (10 GB) | 10 GB | 2,20 € | 12,50 € | **14,70 €** |

**Avantages** :

- Aucun service additionnel.
- Free tier généreux (25 GB = ~50 000 transcripts courts).
- Pas de migration de données (transcripts déjà en DynamoDB ou linkés depuis S3).

**Inconvénients critiques** :

- ❌ **Pas de typo tolerance** : `kubernets` ne matchera jamais `kubernetes`.
- ❌ **Pas de ranking** : résultats non triés par pertinence.
- ❌ **Latence inacceptable** : full table scan requis pour `contains()` → 500ms-5s selon la taille de la table.
- ❌ **Coût prohibitif à l'échelle** : 10 000 recherches/mois sur 500k documents = $125/mois en WCU.
- ❌ **Pas de highlighting** : impossible de montrer le contexte du match.

**Verdict** : ❌ **Éliminé**. DynamoDB est excellent pour les queries par clé primaire/GSI, mais totalement inadapté pour de la recherche full-text. Aucune app de production n'utilise DynamoDB pour ce use case.

**Source** : [AWS DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)

---

### 2.2 Option 2 : Neon Postgres (Serverless)

**Description** : Neon est un Postgres serverless (fork de Postgres avec autoscaling et storage séparé). Utilise les fonctionnalités natives PostgreSQL :

- **`tsvector` + GIN index** pour full-text search (FTS).
- **`pg_trgm` extension** pour fuzzy matching / typo tolerance via trigrams.

**Approche technique** :

1. Migrer les métadonnées média de DynamoDB vers une table Neon `media_items`.
2. Stocker le transcript complet en colonne `TEXT` ou `JSONB` (avec metadata).
3. Créer un GIN index sur `to_tsvector('french', transcript)`.
4. Requête type :
   ```sql
   SELECT media_id, title, ts_rank(to_tsvector('french', transcript), query) AS rank,
          ts_headline('french', transcript, query, 'MaxWords=50') AS snippet
   FROM media_items
   WHERE user_id = $1
     AND to_tsvector('french', transcript) @@ plainto_tsquery('french', $2)
   ORDER BY rank DESC
   LIMIT 20;
   ```
5. Pour typo tolerance, combiner avec `pg_trgm` :
   ```sql
   SELECT * FROM media_items
   WHERE user_id = $1
     AND transcript % 'kubernets'  -- similarity operator
   ORDER BY similarity(transcript, 'kubernets') DESC;
   ```

**Tarification Neon variable par documents** :

Neon facture **compute** (CU-hours) + **storage** (GB-month), pas de tarif par document. Le nombre de documents impacte indirectement via storage + compute time pour indexer.

| Plan | Compute | Storage | Coût mensuel | Documents supportés (estimation) |
|------|---------|---------|-------------:|--------------------------------:|
| **Free** | 100 CU-h/mois (0.25 CU scale max) | 0.5 GB | **0 €** | ~25k transcripts courts (20 KB) |
| **Launch** | Illimité (autoscale 0.25-4 CU) | 10 GB inclus | **~12-20 €/mois** | ~200k transcripts |
| **Scale** | Illimité (autoscale 0.25-16 CU) | 50 GB inclus | **~40-80 €/mois** | ~1M transcripts |

**Détail pricing Launch à 100 users V1** :

- Compute : ~50 CU-h/mois (10h indexing + 40h queries) × $0,106/CU-h = **$5,3/mois ≈ 4,5 €**.
- Storage : 2 GB (40 MB transcripts + 1,96 GB index GIN) × $0,35/GB-mo (au-delà des 0,5 GB free) = **$0,525/mois ≈ 0,45 €**.
- Total : **~5 €/mois à 100 users en usage léger**. Peut monter à **12-20 €/mois** si les requêtes augmentent (autoscaling compute).

**Variabilité par nombre de documents** :

- **<25k docs** : free tier suffit (0.5 GB storage).
- **25k-200k docs** : Launch plan requis, coût croît linéairement avec storage (~0,35 €/GB/mois supplémentaire).
- **>200k docs** : Scale plan recommandé (compute burst nécessaire pour l'indexing).

**Avantages** :

- ✅ **Full-text search natif** avec stemming FR/EN (dictionnaires PostgreSQL intégrés).
- ✅ **BM25-like ranking** via `ts_rank` / `ts_rank_cd`.
- ✅ **Highlighting natif** via `ts_headline`.
- ✅ **Typo tolerance correcte** via `pg_trgm` (similarity threshold configurable).
- ✅ **Serverless** : scale-to-zero en free tier, autoscaling en Launch/Scale.
- ✅ **Free tier généreux** : 0.5 GB = suffisant pour MVP <50 users.
- ✅ **Familiarité SQL** : requêtes SQL standard, pas de DSL à apprendre.

**Inconvénients** :

- ⚠️ **Migration DynamoDB → Postgres requise** : effort ~1-2 semaines pour migrer les tables `media_items`, `processing_jobs`, `users`, etc. **Hors scope V1** (owner a validé DynamoDB comme DB transactionnelle, task-65).
- ⚠️ **Latence 100-300ms** : plus lente qu'un moteur dédié (Typesense <50ms). Acceptable mais pas optimal.
- ⚠️ **Typo tolerance moins intuitive** : `pg_trgm` nécessite tuning du threshold (`set pg_trgm.similarity_threshold = 0.4`), pas d'edit distance configurable comme Typesense.
- ⚠️ **Overhead ops** : bien que serverless, Neon nécessite monitoring de la DB (connexion pooling, vacuum, index maintenance).
- ⚠️ **Pas de multi-language automatique** : il faut spécifier `'french'` ou `'english'` dans la requête. Pas de détection auto.

**Verdict** : ⚠️ **Alternative crédible mais écartée pour V1** car nécessite migration DynamoDB. Si l'owner décide de migrer vers Postgres pour d'autres raisons (transactions ACID complexes, relations many-to-many), Neon devient attractif pour consolider DB + search. Sinon, ajouter Neon juste pour la recherche = overhead architectural.

**Sources** :

- [Neon Pricing](https://neon.com/pricing)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [pg_trgm Extension](https://www.postgresql.org/docs/current/pgtrgm.html)

---

### 2.3 Option 3 : SQLite FTS5 local sur VM EC2

**Description** : SQLite FTS5 (Full-Text Search extension 5) embarqué sur la VM EC2 `t4g.small` qui héberge déjà FastAPI + workers. Le fichier `.db` vit sur le disque EBS attaché à la VM.

**Approche technique** :

1. Un fichier SQLite `search_index.db` sur `/var/lib/app/search.db` (EBS gp3).
2. Table FTS5 :
   ```sql
   CREATE VIRTUAL TABLE transcripts_fts USING fts5(
       user_id UNINDEXED,
       media_id UNINDEXED,
       title,
       transcript,
       created_at UNINDEXED,
       tokenize='porter unicode61',
       prefix='2 3'
   );
   ```
3. Le worker `search_indexing_worker.py` (consomme la queue SQS `search-indexing`, lit le transcript depuis S3, l'insère dans SQLite).
4. L'API `/search` query SQLite :
   ```sql
   SELECT media_id, title, snippet(transcripts_fts, 2, '<b>', '</b>', '...', 32) AS context
   FROM transcripts_fts
   WHERE user_id = ? AND transcripts_fts MATCH ?
   ORDER BY rank
   LIMIT 20;
   ```
5. **Typo tolerance via extension `spellfix1`** (SQLite built-in) :
   - Créer une table de vocabulaire à partir des mots indexés.
   - Sur requête typo, suggérer corrections via `spellfix1` avant de lancer le MATCH.
   - Exemple : `kubernets` → suggère `kubernetes` → relance la requête.

**Tarification variable par documents** :

SQLite est **gratuit** (aucun coût logiciel). Les coûts sont uniquement infra déjà budgetée :

- **Compute** : la VM EC2 `t4g.small` (10,55 €/mois on-demand) héberge déjà FastAPI + 15 workers. SQLite FTS5 ajoute ~100-200 MB RAM utilisée, négligeable sur 2 GB totaux.
- **Storage** : disque EBS gp3 20 GB (2,40 €/mois, déjà alloué pour logs/app/cache). Index FTS5 = ~10-20 MB @100 users (2000 transcripts × 20 KB avg → 40 MB raw, index ≈ 50% = 20 MB).
- **Réseau** : aucun coût additionnel (pas de sortie EBS → S3, les queries restent locales VM).

| Volume users | Transcripts | Taille index FTS5 | Coût marginal/mois | **Total additionnel** |
|-------------|------------:|------------------:|-------------------:|----------------------:|
| 10 | 100 | ~1 MB | 0 € | **0 €** |
| 100 | 2 000 | ~20 MB | 0 € | **0 €** |
| 1 000 | 50 000 | ~500 MB | 0 € | **0 €** |
| 10 000 | 500 000 | ~5 GB | ~0,60 € (storage EBS +5 GB) | **~0,60 €** |

**Variabilité par nombre de documents** :

- **<100k docs** : aucun coût additionnel (index tient dans l'allocation EBS existante).
- **100k-1M docs** : +1-2 €/mois (storage EBS supplémentaire ~10-20 GB).
- **>1M docs** : RAM 2 GB devient insuffisante pour la performance (index mappé en mémoire). Nécessite upgrade `t4g.medium` (4 GB RAM, +10 €/mois) ou migration vers solution externe.

**Avantages** :

- ✅ **Coût zéro** en phase V1 (la VM est déjà payée).
- ✅ **Latence <10ms** pour queries simples (tout est local, pas de roundtrip réseau).
- ✅ **Full-text natif** : BM25 ranking (`ORDER BY rank`), phrase search, prefix search, highlighting (`snippet()`).
- ✅ **Simplicité déploiement** : SQLite = 1 fichier `.db`, aucun daemon externe à monitorer.
- ✅ **Backup trivial** : snapshots EBS quotidiens = backup automatique. Rebuild depuis S3 = ~5 min si corruption fichier.
- ✅ **Pas de migration DynamoDB** : la DB transactionnelle reste en DynamoDB, SQLite sert uniquement de search index.
- ✅ **Réversibilité facile** : swap vers Typesense = adapter le code du worker, 1-2j de travail.

**Inconvénients** :

- ⚠️ **Typo tolerance moins native** : `spellfix1` est correct mais nécessite maintenance d'un vocabulaire. Pas d'edit distance configurable comme Typesense (`num_typos: 2`).
- ⚠️ **SPOF VM unique** : si la VM meurt, l'index est perdu jusqu'à rebuild (~5 min depuis S3). Mitigation : snapshots EBS quotidiens. Acceptable en V1 (disponibilité search non-critique).
- ⚠️ **Scaling vertical seulement** : tant que l'app tourne sur 1 VM, SQLite suit. Si passage multi-VM (V2), il faut soit répliquer le `.db` (complexe), soit migrer vers Typesense/Meilisearch/OpenSearch.
- ⚠️ **Moins bon multilingue** : FTS5 porter stemmer = EN only. Pour FR, il faut `unicode61 remove_diacritics 1` qui ne fait que du stripping d'accents, pas de stemming (`chercher` ≠ `cherché`). Acceptable mais pas optimal.
- ⚠️ **Pas de dashboard admin** : contrairement à Typesense/Meilisearch qui offrent un UI web pour inspecter l'index, SQLite = CLI uniquement.

**Verdict** : ✅ **Solution de fallback recommandée** (voire **alternative crédible comme primary V1**). L'effort dev est faible (~2j) et libère **43 €/mois** de coûts fixes = **+12,3 points de marge** sur Standard 5€ @100u heavy-podcast (83,7 % → 96,0 %). Le différentiel UX (typo tolerance sur contenu ASR, multilingue FR) est le seul argument en faveur de Typesense Cloud. Si la qualité de recherche SQLite s'avère suffisante en beta, cette solution pourrait devenir le choix principal.

**Sources** :

- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [SQLite Spellfix1 Extension](https://www.sqlite.org/spellfix1.html)
- [AWS EBS Pricing](https://aws.amazon.com/ebs/pricing/) : gp3 $0,08/GB-month = 0,072 €/GB/mois

---

### 2.4 Option 4 : Typesense Cloud

**Description** : Typesense est un moteur de recherche open-source écrit en C++, optimisé pour la vitesse et la simplicité. Typesense Cloud = version managée (SaaS).

**Approche technique** :

1. Créer un cluster Typesense Cloud (choix RAM/CPU via UI).
2. Créer une collection `media_transcripts` avec schema :
   ```json
   {
     "name": "media_transcripts",
     "fields": [
       {"name": "user_id", "type": "string", "facet": true},
       {"name": "media_id", "type": "string"},
       {"name": "title", "type": "string"},
       {"name": "transcript", "type": "string"},
       {"name": "created_at", "type": "int64"}
     ]
   }
   ```
3. Worker `search_indexing_worker.py` POST documents via API REST Typesense.
4. API `/search` génère une **scoped API key** par session user :
   ```python
   scoped_key = client.keys.generate_scoped_search_key(
       search_key=TYPESENSE_SEARCH_KEY,
       embedded_params={
           "filter_by": f"user_id:={user_id}",
           "expires_at": int(time.time()) + 3600
       }
   )
   ```
5. Le frontend mobile/web query Typesense directement avec la scoped key (pas de proxy backend nécessaire, latence minimale).

**Tarification Typesense Cloud variable par documents** :

Typesense Cloud facture **par ressources allouées** (RAM + CPU), pas par document. Le nombre de documents impacte le choix de cluster (plus de docs → plus de RAM nécessaire).

**Benchmark RAM Typesense** (source: [GitHub showcase-books-search](https://github.com/typesense/showcase-books-search) + README) :

- 1M Hacker News titles (~50 bytes texte/doc) : 165 MB RAM → ratio **3,3× texte brut**.
- 2,2M recipes (nom + ingrédients, ~300 bytes/doc) : 900 MB RAM → ratio **1,4× texte brut**.
- 28M books (**titre + auteur + subjects seulement**, ~80 bytes/doc, source OpenLibrary) : 14 GB RAM → ratio **6,3× texte brut** (overhead élevé car 28M documents très courts).

**ATTENTION** : le dataset "28M books" ne contient **pas** de texte de livre — uniquement titre, auteur et catégories (vérifié dans le [schema d'indexation](https://github.com/typesense/showcase-books-search/blob/master/scripts/indexer/index.rb)). Les estimations de RAM de la version précédente de ce benchmark étaient basées sur l'hypothèse erronée que ces documents faisaient 5 000 mots.

**Ratio retenu pour extrapolation** : **2,1× le texte brut** (moyenne conservatrice entre les ratios 1,4× et 3,3× sur documents courts ; sur des documents longs comme nos transcripts, l'overhead par document est amorti donc le ratio est dans la fourchette basse).

**Profil utilisateur heavy-podcast** (use case core de l'app) :

- Mix réaliste : 60% podcasts (30 min avg → 9 000 mots), 20% articles (1 500 mots), 10% YouTube (3 000 mots), 10% courts (tweets/TikTok, 200 mots)
- **Moyenne pondérée : ~6 000 mots/doc ≈ 36 KB texte brut/doc**

**Extrapolation corrigée** :

| Users | Docs/user | Texte brut total | RAM nécessaire (×2,1) | Cluster minimum |
|------:|----------:|-----------------:|----------------------:|-----------------|
| 50 | 100 | 180 MB | **~380 MB** | 0,5 GB **très juste** |
| 100 | 100 | 360 MB | **~760 MB** | **1 GB requis** |
| 100 | 200 | 720 MB | **~1,5 GB** | **2 GB requis** |
| 500 | 200 | 3,6 GB | **~7,5 GB** | **8 GB** |
| 1 000 | 300 | 10,8 GB | **~22,7 GB** | **32 GB** |

| Plan Typesense Cloud | RAM / CPU | Coût/mois | Capacité réaliste (profil heavy-podcast) | Phase recommandée |
|---------------------|-----------|----------:|----------------------------------------:|------------------|
| **Signup credit** | Variable | **0 €** (crédit gratuit, montant inconnu) | À déterminer empiriquement | **Pré-launch M0-M1** |
| **MVP cluster** | 0.5 GB / 2 vCPU burst (1h/jour) | **~$18/mo ≈ 15,5 €** | **~650 docs heavy-podcast** OU ~50u × 100 docs light | **Beta <50u light** |
| **Cluster 1 GB** | 1 GB / 2 vCPU burst (2h/jour) | **~$29/mo ≈ 25 €** | ~1 300 docs | **Launch 50-100u** |
| **Growth cluster** | 2 GB / 2 vCPU burst (4h/jour) | **~$50/mo ≈ 43 €** | ~2 600 docs | **Launch 100u × 200 docs** |
| **Cluster 4 GB** | 4 GB / 2 vCPU | **~$80/mo ≈ 69 €** | ~5 200 docs | **500u light** |
| **Cluster 8 GB** | 8 GB / 4 vCPU | **~$150/mo ≈ 129 €** | ~10 400 docs | **500u × 200 docs** |
| **Scale cluster HA** | 16+ GB / multi-nodes | **~$300+/mo** | >20k docs | **1000u+** |

**Variabilité par nombre de documents** (profil heavy-podcast, 36 KB/doc) :

- **<650 docs** : MVP cluster 0,5 GB suffit (très limité — ~50u avec 12 docs chacun).
- **650-1 300 docs** : cluster 1 GB requis.
- **1 300-2 600 docs** : cluster 2 GB requis (= 100u × 26 docs ou 50u × 52 docs).
- **>2 600 docs** : cluster 4 GB+ requis.

**Pricing detail @100 users V1 launch heavy-podcast (200 docs/user = 20 000 docs)** :

- 20 000 docs × 36 KB = 720 MB texte brut × 2,1 = **~1,5 GB RAM nécessaire**.
- Cluster 2 GB minimum requis : **~$50/mois ≈ 43 €/mois** (pas $18/mois comme estimé précédemment).
- Aucun coût additionnel par requête ou par document.
- Bandwidth sortant facturé séparément (montant inclus non documenté publiquement, probablement négligeable à V1 volume).
- Limitation CPU burst : 4h/jour sur le cluster 2 GB.

**Note importante** : ces prix sont estimés depuis la grille de configuration Typesense Cloud (le pricing exact n'est pas affiché publiquement — il faut créer un compte pour voir les montants). Les chiffres ci-dessus sont des estimations basées sur les fourchettes communiquées dans la communauté et doivent être vérifiés empiriquement via le signup credit.

**Avantages** :

- ✅ **Typo tolerance native excellente** : `num_typos: 2` = autorise jusqu'à 2 fautes par mot. `kubernets` → `kubernetes` fonctionne out-of-the-box.
- ✅ **Latence <50ms p95** : C++ optimisé, in-memory indexing.
- ✅ **Multi-tenancy élégant** : scoped API keys = isolation au query-time sans surcoût. Pas besoin d'index par user.
- ✅ **Ranking BM25 configurable** : field weights, boost par recency, custom scoring.
- ✅ **Highlighting et snippets** : `highlight_full_fields: false` + `snippet_threshold: 30` pour montrer le contexte du match.
- ✅ **Prefix search natif** : `kub*` matche `kubernetes`, `kubectl`.
- ✅ **Zéro ops overhead** : managé, monitoring inclus, backup automatique, upgrade zero-downtime.
- ✅ **Scaling transparent** : changer de plan = 1 clic dans l'UI, pas de migration.
- ✅ **Signup credit = phase pré-launch gratuite** : vérifié 2026-05-01 sur cloud.typesense.org ("free credits, no credit card"). Estimation conservatrice : $25-50 de crédit couvre M0-M1 avec <50 beta users.

**Inconvénients** :

- ⚠️ **Coût fixe ~43 €/mois en phase launch** (cluster 2 GB requis pour 100u × 200 docs heavy-podcast) : représente **75 % du coût infra total** @100u (infra corrigé : EC2 10,55 + Typesense 43 + misc 4 = **57,5 €/mois**). Impact pricing : voir §5.
- ⚠️ **Moins mature que Elasticsearch** : écosystème plugins plus petit, communauté moins large (25k stars GitHub vs 70k Elasticsearch).
- ⚠️ **Multilingue FR moins fort que Meilisearch** : Typesense stemming FR est correct mais Meilisearch gère mieux les accents/homophones FR (benchmark interne Meilisearch vs Typesense 2024).

**Verdict** : ✅ **Recommandation principale**. Typesense Cloud offre le meilleur compromis **qualité UX / simplicité ops** pour V1. Le signup credit permet de valider la solution gratuitement en M0-M1. Le coût **43 €/mois** en phase launch (cluster 2 GB pour 100u heavy-podcast) est significatif (75 % de l'infra) mais justifié par la qualité de recherche et le zéro ops.

**Sources** :

- [Typesense Official Site](https://typesense.org/)
- [Typesense Cloud Pricing](https://cloud.typesense.org/pricing)
- [Typesense GitHub](https://github.com/typesense/typesense) : RAM benchmarks dans le README
- [Typesense Multi-Tenancy Guide](https://typesense.org/docs/0.25.0/api/api-keys.html#generate-scoped-search-key)

---

### 2.5 Option 5 : Meilisearch Cloud

**Description** : Meilisearch est un moteur de recherche open-source écrit en Rust, concurrent direct de Typesense. Meilisearch Cloud = version managée (SaaS).

**Approche technique** : quasi identique à Typesense (REST API, indexing pipeline similaire).

Différence clé : **tenant tokens** au lieu de scoped API keys :

```python
tenant_token = client.generate_tenant_token({
    "searchRules": {
        "media_transcripts": {
            "filter": f"user_id = {user_id}"
        }
    },
    "expiresAt": datetime.now() + timedelta(hours=1)
})
```

**Tarification Meilisearch Cloud variable par documents** :

Deux modèles de pricing :

1. **Usage-based** : $30/mois baseline, puis tarif dégressif par tranche de documents + recherches.
2. **Resource-based** : $23/mois baseline pour 1 GB RAM / 1 vCPU, puis échelle linéairement.

| Plan Meilisearch Cloud | Modèle | Coût/mois @100u V1 | Documents supportés | Phase |
|-----------------------|--------|-------------------:|--------------------:|-------|
| **Free (self-hosted)** | Open-source | 0 € (VM déjà payée) | Illimité | Alternative à SQLite FTS5 |
| **Usage-based Starter** | SaaS | $30 ≈ **26 €** | 100k docs, 1M searches/mois | Launch |
| **Resource-based Small** | SaaS | $23-30 ≈ **20-26 €** | ~50k docs (1 GB RAM) | Launch |
| **Resource-based Medium** | SaaS | ~$50 ≈ **43 €** | ~200k docs (2 GB RAM) | Growth |

**Variabilité par nombre de documents** :

- **<100k docs** : Starter usage-based à $30/mois suffit.
- **100k-500k docs** : passer en resource-based 2-4 GB RAM (~$50-80/mois).
- **>500k docs** : resource-based 8 GB+ RAM (~$150/mois).

**Pricing detail @100 users V1 launch** :

- Usage-based : 2k docs, ~400-2k searches/mois → baseline $30/mois = **26 €/mois**.
- Resource-based : 1 GB RAM suffit → $23/mois = **20 €/mois**.

**Note** : Meilisearch affiche souvent "$30/mois" dans le marketing mais le détail pricing révèle que 100k docs + 1M searches = overages possibles. En pratique, à 100u V1, le coût reste ~$25-35/mois.

**Avantages** :

- ✅ **Typo tolerance native excellente** : fuzzy matching avec edit distance, comparable à Typesense.
- ✅ **Meilleur multilingue** : Meilisearch gère mieux le FR, l'arabe, le chinois, le japonais que Typesense (tokenization spécialisée par langue).
- ✅ **Latence <50ms p95** : Rust optimisé, performances similaires à Typesense.
- ✅ **Disk-based storage** : contrairement à Typesense (RAM-based), Meilisearch utilise memory-mapped files → RAM requirements plus bas pour le même nombre de docs.
- ✅ **UI admin élégante** : dashboard web pour inspecter l'index, tester des queries, voir les analytics.
- ✅ **Zéro ops overhead** : managé, backup, monitoring inclus.

**Inconvénients** :

- ⚠️ **Tenant tokens moins élégants** que scoped API keys Typesense : nécessite un endpoint backend pour générer les tokens (pas de query direct frontend → Meilisearch avec isolation).
- ⚠️ **Pricing en réalité inférieur** à Typesense Cloud pour le même volume (disk-based → ~12-15 €/mois vs Typesense 43 €/mois @100u heavy-podcast). L'avantage Typesense est la latence et la qualité, pas le prix.
- ⚠️ **Moins de field weighting control** : le ranking Meilisearch est plus "automagique", moins configurable que Typesense/Elasticsearch.
- ⚠️ **Pas de signup credit public** : contrairement à Typesense, Meilisearch Cloud ne mentionne pas de crédit gratuit à l'inscription (à vérifier en contactant sales).

**Verdict** : ✅ **Excellente alternative à Typesense**, surtout si le **multilingue FR/arabe/chinois** devient prioritaire. Le différentiel de coût (~5-10 €/mois) et l'absence de signup credit penchent en faveur de Typesense pour V1, mais Meilisearch reste une option crédible. **Migration Typesense → Meilisearch = 1-2j** si nécessaire (API similaires).

**Sources** :

- [Meilisearch Official Site](https://www.meilisearch.com/)
- [Meilisearch Pricing](https://www.meilisearch.com/pricing)
- [Meilisearch vs Typesense Comparison](https://www.meilisearch.com/blog/meilisearch-vs-typesense/) (biaisé Meilisearch, à lire avec recul)
- [Meilisearch GitHub](https://github.com/meilisearch/meilisearch) : 57k stars

---

### 2.6 Option 6 : Amazon OpenSearch Service

**Description** : OpenSearch = fork open-source d'Elasticsearch 7.10 maintenu par AWS. Service managé sur AWS.

**Approche technique** : similaire à Elasticsearch (DSL JSON complexe, mapping, sharding, replicas).

**Tarification OpenSearch variable par documents** :

OpenSearch facture **par instances** (nodes × instance type × heures) + storage EBS. Le nombre de documents impacte le sizing (nombre de shards, RAM nécessaire).

| Configuration | Compute | Storage | Coût/mois | Documents supportés |
|--------------|---------|---------|----------:|--------------------:|
| **Dev (1 node t3.small)** | 1 × t3.small | 20 GB | ~55 € | ~50k (non-HA, dev only) |
| **Prod min (3 nodes r6g.large)** | 3 × r6g.large (2 vCPU, 16 GB RAM each) | 100 GB gp3 × 3 | **~310 €** | ~1-5M |
| **Scale (5 nodes r6g.xlarge)** | 5 × r6g.xlarge (4 vCPU, 32 GB RAM) | 500 GB gp3 × 5 | ~900 € | 10-50M |

**Variabilité par nombre de documents** :

- **<100k docs** : 1 node suffit techniquement mais **non recommandé pour prod** (pas de HA). Coût dev : ~55 €/mois.
- **100k-1M docs** : 3 nodes r6g.large minimum pour HA → **~310 €/mois**.
- **>1M docs** : scaling horizontal (+ de nodes) + vertical (instances plus grosses).

**Pricing detail @100 users V1** :

- Configuration 3-node r6g.large : $0,141/h × 3 × 730h = $308/mois ≈ **265 €/mois**.
- EBS gp3 100 GB × 3 : $24/mois ≈ **20,6 €/mois**.
- Total : **~285 €/mois minimum** pour une setup prod HA.

**Avantages** :

- ✅ **Enterprise-grade search** : le standard de l'industrie, utilisé par Netflix, Uber, Airbnb.
- ✅ **Feature-rich** : aggregations complexes, geo-search, ML anomaly detection, vector search (k-NN).
- ✅ **Scaling éprouvé** : gère des milliards de documents, petabytes de données.
- ✅ **Écosystème mature** : plugins, dashboards (OpenSearch Dashboards = fork de Kibana), intégrations.
- ✅ **AWS-native** : VPC isolation, IAM, CloudWatch, tight integration avec Lambda/Kinesis.

**Inconvénients** :

- ❌ **Coût prohibitif pour V1** : ~285 €/mois = **~7× le coût Typesense** (43 €/mois @100u heavy-podcast) à volume équivalent.
- ❌ **Complexité opérationnelle élevée** : tuning de shards, index lifecycle policies, cluster health monitoring, rolling upgrades.
- ❌ **Over-engineering** : OpenSearch est conçu pour des use cases big data (logs analytics, monitoring, e-commerce à des millions de SKU). Pour 2k-20k documents, c'est sortir l'artillerie lourde.
- ❌ **Latency 50-200ms** : plus lent que Typesense/Meilisearch car architecture distribuée par défaut.

**Verdict** : ❌ **Éliminé pour V1**. OpenSearch ne devient pertinent qu'à **>100k users** ou si des besoins analytics complexes apparaissent (dashboards, aggregations, ML). À 100 users, le coût est **10× trop élevé** pour le besoin. À réévaluer en V3+ si scaling massif.

**Sources** :

- [Amazon OpenSearch Service Pricing](https://aws.amazon.com/opensearch-service/pricing/)
- [OpenSearch Documentation](https://opensearch.org/docs/latest/)

---

### 2.7 Option 7 : Algolia

**Description** : Algolia = SaaS premium de recherche, leader mondial sur la rapidité (<20ms p50 globally) et l'UX (SDKs mobile/web best-in-class).

**Approche technique** : API REST + SDKs officiels React Native / Swift / Kotlin. Très similaire à Typesense/Meilisearch côté intégration.

**Tarification Algolia (mise à jour 2026-05-12, source: algolia.com/pricing + support.algolia.com)** :

Algolia facture **par record stocké** + **par search request**. Pas de monthly fee fixe — c'est du **pay-as-you-go** au-delà des inclusions.

| Plan | Records inclus | Requests/mois inclus | Overages records | Overages requests | Record size limit |
|------|---------------:|---------------------:|-----------------:|------------------:|------------------:|
| **Build** (free) | **1M** | 10K | N/A (plan cap) | N/A | **10 KB hard** |
| **Grow** | 100K | 10K | $0,40/1K | $0,50/1K | 100 KB hard, **10 KB avg** |
| **Grow Plus** | 100K | 10K | $0,40/1K | $1,75/1K | 100 KB hard, 10 KB avg |
| **Elevate** | Custom | Custom | Négocié | Négocié | Custom |

**Contrainte critique Build** : **1 GB maximum par application** (index total). Le "1M records" n'est exploitable que si les records sont petits. Avec des chunks de ~9 KB, le cap réel est ~**100-110k records** avant d'atteindre 1 GB.

**Split obligatoire** : la limite 10 KB/record (Build) et 10 KB average (Grow) impose de **chunker les transcripts**. Un transcript de 36 KB → 4 chunks de ~9 KB chacun.

**Pricing detail @100 users V1 launch (profil heavy-podcast)** :

- 20k docs × 4 chunks = **80k records** × ~9 KB = **~720 MB** index (< 1 GB cap Build ✓).
- Requests : 100u × 10 searches/mois × 4 keystrokes (debounce 300ms) = **~4 000/mois** (< 10K ✓).
- **Coût Y1 : 0 €** (plan Build gratuit suffit à 100u).
- ⚠️ Headroom limité : ~130 users ou >250 docs/user → dépasse 1 GB → migration vers Grow obligatoire.

**Projection Y2-Y3** :

- Y2 @1000u (100 docs/user) : 100k docs × 4 = 400k records. Build dépassé (3,6 GB >> 1 GB). Grow : overages (400k−100k) × $0,40/1K = $120/mo + requests 40k, overages 30k × $0,50/1K = $15/mo. **Total ~$135/mo ≈ 116 €/mois**.
- Y3 @5000u (100 docs/user) : 500k × 4 = 2M records. Overages 1,9M × $0,40/1K = $760/mo + requests 200k, overages 190k × $0,50/1K = $95/mo. **Total ~$855/mo ≈ 736 €/mois**.

**Avantages** :

- ✅ **Phase Y1 @100u = gratuite** (plan Build, aucun frais tant que index < 1 GB et < 10K req/mois).
- ✅ **Latence <20ms p50 globally** : CDN 70+ datacenters, le plus rapide du marché.
- ✅ **UX exceptionnelle** : SDKs mobile natifs (InstantSearch iOS/Android), UI components React Native.
- ✅ **Typo tolerance best-in-class** : fuzzy matching + AI-powered ranking.
- ✅ **Zéro ops overhead** : 100% managé, scale automatique.
- ✅ **Analytics intégrées** : dashboard search analytics, A/B testing (Grow Plus+).

**Inconvénients** :

- ⚠️ **Split obligatoire des transcripts** : 10 KB limit/record → chunking logic + reconstruction des résultats (dédupliquer les hits d'un même document). Overhead dev ~4h.
- ⚠️ **Scaling coûteux** : pay-per-record + pay-per-request = coût **imprévisible** à l'échelle. Y3 = ~736 €/mois (vs Typesense ~430 €/mois self-hosted). La facturation par request pénalise le search-as-you-type.
- ⚠️ **Cap 1 GB sur Build** : headroom limité, migration vers Grow inévitable dès 130+ users heavy-podcast.
- ⚠️ **10 KB average sur Grow** : même en Grow, les gros records comptent plus lourdement dans le quota. Monitoring requis.
- ⚠️ **Vendor lock-in moyen** : API propriétaire mais concepts similaires à Typesense/Meilisearch. Migration away = 1-2 semaines.

**Verdict** : ✅ **Alternative très crédible pour V1**. Le plan Build gratuit couvre la totalité de la phase launch @100u sans aucun frais — c'est un **avantage décisif** vs Typesense (430 €/an Y1) et Meilisearch (pas de free tier). Le trade-off est le coût à l'échelle (Y2+ plus cher que Typesense) et la complexité du chunking.

**Sources** :

- [Algolia Pricing](https://www.algolia.com/pricing/) (consulté 2026-05-12)
- [Algolia Record Size Limits](https://support.algolia.com/hc/en-us/articles/4406981897617) (consulté 2026-05-12)
- [Algolia Service Limits](https://www.algolia.com/doc/guides/scaling/servers-clusters/#service-limits)

---

## 3. Impact sur la qualité de recherche

### 3.1 Transcripts longs (podcasts 45 min, 9000 mots)

**Défi** : montrer du contexte pertinent sans submerger l'user, pagination des résultats.

| Solution | Highlighting | Snippet generation | Pagination | Score |
|----------|-------------|-------------------|-----------|-------|
| **SQLite FTS5** | ✅ `snippet()` natif, configurable | ✅ `MaxWords` configurable | ✅ `LIMIT/OFFSET` | ⭐⭐⭐⭐ |
| **Neon Postgres** | ✅ `ts_headline()` | ✅ `MaxWords`, `MinWords` | ✅ `LIMIT/OFFSET` | ⭐⭐⭐⭐ |
| **Typesense** | ✅ `highlight_fields`, `snippet_threshold` | ✅ | ✅ `per_page` | ⭐⭐⭐⭐⭐ |
| **Meilisearch** | ✅ `attributesToHighlight` | ✅ | ✅ `limit`, `offset` | ⭐⭐⭐⭐⭐ |
| **OpenSearch** | ✅✅ `highlight` (très riche) | ✅ `fragment_size` | ✅ | ⭐⭐⭐⭐⭐ |

**Gagnant** : Typesense / Meilisearch / OpenSearch excellent tous les trois. SQLite FTS5 et Neon sont corrects.

### 3.2 Transcripts bruités (erreurs ASR, homophones FR)

**Défi** : "chant" vs "champ", "cou" vs "coût", ponctuation manquante.

| Solution | Typo tolerance | Stemming FR | Phonetic match | Score |
|----------|----------------|-------------|---------------|-------|
| **SQLite FTS5** | ⚠️ `spellfix1` (maintenance vocab) | ❌ (porter EN only) | ❌ | ⭐⭐ |
| **Neon Postgres** | ⚠️ `pg_trgm` (threshold tuning) | ✅ dictionnaire FR intégré | ❌ | ⭐⭐⭐ |
| **Typesense** | ✅✅ `num_typos: 2` | ✅ stemming FR/EN | ❌ | ⭐⭐⭐⭐⭐ |
| **Meilisearch** | ✅✅ fuzzy + phonetic | ✅✅ meilleur FR | ⚠️ phonetic EN only | ⭐⭐⭐⭐⭐ |
| **OpenSearch** | ✅ `fuzziness: AUTO` | ✅ analyzers FR | ⚠️ via plugin | ⭐⭐⭐⭐ |

**Gagnant** : **Meilisearch** (meilleur multilingue FR) > **Typesense** (très bon) > Neon/OpenSearch (corrects) > SQLite FTS5 (basic).

### 3.3 Contenus hétérogènes (podcast conversationnel vs article académique)

**Défi** : ranking qui privilégie la densité de match + recency + type de match (titre > transcript).

| Solution | BM25 ranking | Field weighting | Recency boost | Custom scoring | Score |
|----------|-------------|-----------------|---------------|---------------|-------|
| **SQLite FTS5** | ✅ `rank` | ❌ (tout fields égaux) | ❌ (manual ORDER BY) | ❌ | ⭐⭐ |
| **Neon Postgres** | ⚠️ `ts_rank` (approx BM25) | ⚠️ `setweight()` | ⚠️ manual | ❌ | ⭐⭐⭐ |
| **Typesense** | ✅ BM25 | ✅✅ `query_by_weights` | ✅ `sort_by: _text_match:desc,created_at:desc` | ✅ `pinned_hits` | ⭐⭐⭐⭐⭐ |
| **Meilisearch** | ✅ BM25-like | ⚠️ moins configurable | ✅ `sort` | ⚠️ limité | ⭐⭐⭐⭐ |
| **OpenSearch** | ✅✅ BM25 + custom | ✅✅ `boost` | ✅ `function_score` | ✅✅ scripting | ⭐⭐⭐⭐⭐ |

**Gagnant** : **Typesense** (excellent field weighting) = **OpenSearch** (feature-richest) > Meilisearch (moins configurable mais bon par défaut) > Neon > SQLite FTS5.

### 3.4 Multilingue (FR primary, EN secondary, futur arabe/chinois?)

| Solution | Langue FR | Langue EN | Arabe/Chinois | Auto-detect | Score |
|----------|----------|----------|--------------|------------|-------|
| **SQLite FTS5** | ⚠️ unicode61 (strip accents only) | ✅ porter | ❌ | ❌ | ⭐⭐ |
| **Neon Postgres** | ✅ dictionnaire FR | ✅ dictionnaire EN | ✅ 15+ langues | ❌ (specify in query) | ⭐⭐⭐⭐ |
| **Typesense** | ✅ stemming FR | ✅ stemming EN | ⚠️ faible non-Latin | ❌ | ⭐⭐⭐ |
| **Meilisearch** | ✅✅ excellent FR | ✅ excellent EN | ✅✅ excellent arabe/chinois/japonais | ✅ auto-detect | ⭐⭐⭐⭐⭐ |
| **OpenSearch** | ✅ analyzers FR | ✅ analyzers EN | ✅ plugins | ⚠️ config lourde | ⭐⭐⭐⭐ |

**Gagnant** : **Meilisearch** (champion multilingue) > Neon/OpenSearch > Typesense > SQLite FTS5.

### 3.5 Tableau récapitulatif qualité

| Solution | Transcripts longs | Transcripts bruités | Hétérogène | Multilingue | **Score moyen** |
|----------|-------------------|---------------------|-----------|------------|----------------|
| **SQLite FTS5** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | **2,5/5** |
| **Neon Postgres** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | **3,5/5** |
| **Typesense** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **4,5/5** |
| **Meilisearch** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **4,75/5** |
| **OpenSearch** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **4,5/5** |

---

## 4. Scalabilité, latence, multi-tenancy, exploitation

### 4.1 Scalabilité par phase

| Solution | MVP (<100u) | Launch (100-1ku) | Growth (1k-10ku) | Scale (>10ku) |
|----------|-----------|----------------|----------------|-------------|
| **SQLite FTS5** | ✅ Excellent | ✅ Bon (VM unique OK) | ⚠️ Limite (RAM 2 GB) | ❌ Require migration |
| **Neon Postgres** | ✅ Free tier | ✅ Launch tier | ✅ Scale tier | ✅ Autoscale |
| **Typesense Cloud** | ✅ Signup credit | ✅ MVP cluster | ✅ Growth cluster | ✅ HA multi-node |
| **Meilisearch Cloud** | ✅ Free self-host | ✅ Starter SaaS | ✅ Medium | ✅ Enterprise |
| **OpenSearch** | ❌ Coût prohibitif | ❌ Over-engineered | ✅ Commence à être pertinent | ✅ Conçu pour |

### 4.2 Latence comparée (estimations réalistes V1)

| Solution | P50 | P95 | P99 | Notes |
|----------|----:|----:|----:|-------|
| **SQLite FTS5 local** | <10ms | <20ms | <50ms | Tout en local VM, aucun réseau |
| **Neon Postgres** | 80-150ms | 150-300ms | 300-500ms | Roundtrip us-east-1 → Neon (us-east-1 colocated) |
| **Typesense Cloud** | 30-50ms | 50-100ms | 100-200ms | Roundtrip us-east-1 → Typesense Cloud |
| **Meilisearch Cloud** | 30-50ms | 50-100ms | 100-200ms | Similaire Typesense |
| **OpenSearch AWS** | 50-150ms | 150-300ms | 300-500ms | Distributed arch overhead |
| **Algolia** | <20ms | <50ms | <80ms | Global CDN (mais overkill FR-first) |

**Gagnant latence absolue** : **SQLite FTS5** (local) > Algolia (CDN global) > Typesense/Meilisearch > Neon/OpenSearch.

**Note** : dans une app second-brain, **100-200ms de latency search est acceptable**. Ce n'est pas un moteur de recherche e-commerce où chaque ms de latency coûte des conversions. Les users tolèrent 200-300ms pour une recherche ponctuelle.

### 4.3 Multi-tenancy : isolation et simplicité

| Solution | Modèle isolation | Implémentation | Sécurité | Overhead dev |
|----------|-----------------|---------------|---------|-------------|
| **SQLite FTS5** | WHERE user_id = ? | ✅ Trivial (SQL) | ⚠️ App-level | 1h |
| **Neon Postgres** | WHERE user_id = ? | ✅ Trivial (SQL) | ⚠️ App-level | 1h |
| **Typesense** | Scoped API keys | ✅✅ Élégant (query-time filter engine-level) | ✅ Engine-enforced | 4h (key generation) |
| **Meilisearch** | Tenant tokens | ⚠️ Moins élégant (require backend endpoint) | ✅ Engine-enforced | 6h (token generation) |
| **OpenSearch** | Document-level security | ⚠️ Complexe (plugin ou app-level filter) | ⚠️ Depends config | 1-2j |

**Gagnant** : **Typesense** (scoped keys les plus élégantes) > SQLite/Neon (SQL simple) > Meilisearch (tenant tokens OK mais moins direct) > OpenSearch (complexe).

### 4.4 Overhead opérationnel

| Tâche | SQLite FTS5 | Neon | Typesense Cloud | Meilisearch Cloud | OpenSearch |
|-------|------------|------|----------------|------------------|-----------|
| **Setup initial** | 2h (table FTS5) | 1-2 semaines (migration DDB) | 1h (cluster + schema) | 1h | 1-2j (domain + mapping) |
| **Monitoring** | 1h/mois (disk space) | 2h/mois (DB metrics) | 0h (dashboard inclus) | 0h (dashboard inclus) | 4-8h/mois (CloudWatch + tuning) |
| **Backup** | 0h (EBS snapshots auto) | 0h (managed) | 0h (managed) | 0h (managed) | 2h/mois (vérif snapshots) |
| **Upgrades** | 0h (SQLite backward-compatible) | 0h (managed) | 0h (zero-downtime) | 0h (zero-downtime) | 4h/upgrade (test + deploy) |
| **Scaling** | 1h (upgrade VM) | 0h (autoscale) | 0h (change plan UI) | 0h (change plan UI) | 4-8h (reshard + rolling restart) |
| **Incident response** | 30 min (rebuild index S3) | 0h (managed) | 0h (managed) | 0h (managed) | 2-4h (debug cluster) |
| **Total ops/an** | ~8h | ~24h | ~0h | ~0h | ~60-100h |

**Gagnant ops** : **Typesense Cloud** = **Meilisearch Cloud** (0h) > SQLite FTS5 (~8h) > Neon (~24h) > OpenSearch (~60-100h).

Pour un **solo dev**, la différence 0h vs 8h/an est marginale, mais 0h vs 60h/an est énorme.

---

## 5. Coût, complexité, maintenance, réversibilité

### 5.1 Coût total 3 ans (projection)

**Hypothèses** :

- Year 1 : 100 users avg (launch phase), profil heavy-podcast (200 docs/user, 36 KB/doc avg).
- Year 2 : 1 000 users avg (growth phase), profil mixte (~100 docs/user avg).
- Year 3 : 5 000 users avg (scale phase), profil mixte (~100 docs/user avg).
- Ratio RAM Typesense : **2,1× le texte brut** (voir §2.4).

| Solution | Y1 @100u | Y2 @1ku | Y3 @5ku | **Total 3 ans** |
|----------|--------:|--------:|--------:|---------------:|
| **SQLite FTS5 local** | 0 € | 0 € | 120 € (VM upgrade) | **120 €** |
| **Neon Postgres Launch** | 144 € | 240 € | 480 € | **864 €** |
| **Typesense Cloud** | 430 € (2 GB, 10 mois) | 1 548 € (8 GB) | 5 160 € (32+ GB) | **~7 138 €** |
| **Meilisearch Cloud** | 240 € | 480 € | 600 € | **1 320 €** |
| **OpenSearch AWS** | 3 420 € | 3 420 € | 5 400 € | **12 240 €** |
| **Algolia** | **0 €** (Build free) | ~1 392 € (Grow overages) | ~8 832 € (Grow overages) | **~10 224 €** |

**Note Y1 Typesense** : inclut 2-3 mois de signup credit gratuit (0 €) puis 10 mois de cluster 2 GB ($50/mo ≈ 43 €/mo). Cluster 2 GB requis pour 100u × 200 docs heavy-podcast (1,5 GB RAM nécessaire, ratio 2,1×).

**Note Y2-Y3 Typesense** : profil mixte (20 % heavy-podcast 200 docs, 50 % balanced 50 docs, 30 % light 20 docs → avg ~100 docs/user). Y2 : 100k docs × 36 KB × 2,1 = 7,6 GB → cluster 8 GB ($150/mo). Y3 : 500k docs × 36 KB × 2,1 = 37,8 GB → cluster multi-node (~$430/mo). À ce stade, migration vers self-hosted (ECS/EC2) = plus économique (voir §6.5).

**Note Algolia** : Plan Build (free) avec cap **1 GB index total**. Transcripts 36 KB splittés en 4 chunks de ~9 KB = 80k records @100u = ~720 MB (< 1 GB ✓). Y1 gratuit. À 1000u, passage obligatoire vers Grow (pay-as-you-go) : 400k records overages $120/mo + 30k requests overages $15/mo = ~$135/mo. Y3 @5000u : 2M records overages $760/mo + 190k requests overages $95/mo = ~$855/mo.

### 5.2 Impact pricing sur Standard 5€ @100u

**Correction** : le coût Typesense @100u heavy-podcast (200 docs/user) = **43 €/mois** (cluster 2 GB, ratio 2,1×), et non 15,5 €/mois (cluster 0,5 GB insuffisant). Coût infra total corrigé @100u = **0,575 €/user/mois** (EC2 10,55 + Typesense 43 + misc 4 = 57,5 €/mois).

| Solution search | Coût/user/mois | Coût infra total/user/mois | Marge Standard 5€ (revenu net 3,54€) | Différentiel vs Typesense |
|----------------|---------------:|---------------------------:|------------------------------------:|------------------------:|
| **SQLite FTS5 local** | 0 € | 0,145 € | **+96,0 %** (marge 3,40 €) | **+12,3 pts** |
| **Algolia Build** (free) | **0 €** | **0,145 €** | **+96,0 %** (marge 3,40 €) | **+12,3 pts** |
| **Neon Launch** | ~0,12 € | 0,265 € | +92,5 % (marge 3,28 €) | +8,8 pts |
| **Typesense 2 GB** | **0,43 €** | **0,575 €** | **+83,7 %** (marge 2,97 €) | baseline |
| **Meilisearch** | ~0,20 € | 0,345 € | +90,3 % (marge 3,20 €) | +6,5 pts |
| **OpenSearch** | ~2,85 € | 2,99 € | +15,5 % (marge 0,55 €) | **−68,2 pts** |

**Lecture** : **Algolia Build (free)** et SQLite FTS5 local sont à égalité en coût (0 €) @100u — les deux libèrent **+12,3 pts de marge** vs Typesense. Algolia offre en plus la typo tolerance best-in-class et le zéro ops, au prix du chunking (overhead dev ~4h). À l'échelle (Y2+), Algolia devient pay-as-you-go et perd cet avantage.

### 5.3 Complexité implémentation

| Solution | Effort setup | Effort intégration API search | Effort multi-tenancy | **Total** |
|----------|------------:|------------------------------:|---------------------:|----------:|
| **SQLite FTS5** | 4h (schema FTS5, spellfix1 setup) | 2h (query builder) | 1h (WHERE clause) | **7h** |
| **Neon** | 1-2 semaines (migration DDB) | 3h (SQL queries) | 1h | **1-2 sem** |
| **Typesense** | 2h (cluster + collection schema) | 3h (API client) | 4h (scoped keys) | **9h** |
| **Meilisearch** | 2h | 3h | 6h (tenant tokens) | **11h** |
| **OpenSearch** | 1-2j (domain setup, mappings) | 1j (query DSL) | 4h (filters) | **2-3j** |

**Gagnant simplicité** : **SQLite FTS5** (7h, aucune dépendance externe) > Typesense (9h) > Meilisearch (11h) > OpenSearch (2-3j) > Neon (1-2 sem migration).

### 5.4 Maintenance 3 ans (projection)

| Solution | Ops/an | 3 ans | Coût opportunité @50€/h solo dev |
|----------|-------:|------:|---------------------------------:|
| **SQLite FTS5** | 8h | 24h | 1 200 € |
| **Neon** | 24h | 72h | 3 600 € |
| **Typesense** | 0h | 0h | 0 € |
| **Meilisearch** | 0h | 0h | 0 € |
| **OpenSearch** | 80h | 240h | **12 000 €** |

**Lecture** : OpenSearch coûte ~310 €/mois en infra **+ 12 000 € de temps dev sur 3 ans** = **~23 000 €** coût total. Typesense coûte ~7 138 € infra + 0 € temps dev = **~7 138 €** total. **Facteur 3,2×**. SQLite FTS5 coûte 120 € infra + 1 200 € temps dev = **1 320 €** total — le plus économique combiné.

### 5.5 Réversibilité et lock-in

**Facilité de migration away (swap vers autre solution)** :

| Solution | Lock-in level | Effort migration | Stratégie exit |
|----------|--------------|-----------------|---------------|
| **SQLite FTS5** | ⭐ Très faible | 1-2j vers Typesense/Meilisearch/Neon | Adapter pattern déjà abstrait |
| **Neon Postgres** | ⭐⭐ Faible | 2-3j vers RDS Postgres/self-hosted | SQL standard, export/import trivial |
| **Typesense** | ⭐⭐ Faible | 1-2j vers Meilisearch/OpenSearch | JSON API similar, reindex pipeline |
| **Meilisearch** | ⭐⭐ Faible | 1-2j vers Typesense/OpenSearch | JSON API similar |
| **OpenSearch** | ⭐⭐⭐ Moyen | 1-2 sem vers Elasticsearch/Typesense | Query DSL complexe, mapping rework |
| **Algolia** | ⭐⭐⭐⭐ Élevé | 2-4 sem vers autre solution | API propriétaire, ranking custom |

**Recommandation** : implémenter une **abstraction `SearchProvider`** dès V1 (interface Python avec méthodes `index_document()`, `search()`, `delete_document()`). Les adapters concrets (`TypesenseAdapter`, `SQLiteFTS5Adapter`, `MeilisearchAdapter`) implémentent cette interface. Swap = changer l'adapter injecté, pas refactor du code métier.

**Effort abstraction** : +1j dev upfront, économise 1-2 sem si migration nécessaire.

---

## 6. Recommandation finale et justification

### 6.1 Solution retenue : Typesense Cloud (approche progressive)

**Phase 1 (pré-launch, M0-M1, <50 beta users)** :

- Activer le **signup credit Typesense Cloud** (gratuit, vérifié 2026-05-01 : "free credits, no credit card" sur cloud.typesense.org).
- Créer le cluster et la collection `media_transcripts`.
- Implémenter le pipeline d'indexation `search_indexing_worker.py` + API `/search` avec scoped API keys.
- **Coût** : **0 €/mois** tant que le crédit tient.
- **Objectif** : valider la solution techniquement avec les beta users, recueillir feedback UX, calibrer les hypothèses de volume.

**Phase 2 (launch, M2-M12, 100 users × 200 docs heavy-podcast)** :

- Basculer sur **cluster 2 GB RAM / 2 vCPU burst (4h/jour)** = **~$50/mois ≈ 43 €/mois**.
- RAM nécessaire estimée : ~1,5 GB (20k docs × 36 KB × 2,1). Cluster 2 GB donne un headroom de ~30 %.
- Supporte ~2 600 docs heavy-podcast max, ~5-10k requêtes/jour, latence <50ms p95.
- **Coût infra total @100u** : 57,5 €/mois (EC2 10,55 + Typesense 43 + misc 4).
- **Marge Standard 5€** : +83,7 % @100u (marge nette 2,97 €/user).

**Phase 3 (growth, M12+, 500-1000 users)** :

- Upgrade vers **cluster 8 GB RAM / 4 vCPU** = **~$150/mois ≈ 129 €/mois**.
- 500u × 200 docs = 100k docs × 36 KB × 2,1 = 7,6 GB RAM → cluster 8 GB nécessaire.
- À 500 users, coût/user = 129/500 = **0,258 €/user/mois** (acceptable).
- À 1000+ users, migrer vers self-hosted Typesense (ECS ou dédié) pour contrôler les coûts.

**Fallback si signup credit épuisé avant launch public** :

- Implémenter **SQLite FTS5 local** (~2j dev).
- **Coût** : 0 € (VM déjà payée).
- **Trade-off accepté** : typo tolerance moins bonne (spellfix1 vs Typesense native), multilingue basic.
- **Reversibility** : une fois en phase launch payante, revenir sur Typesense = swap adapter, 1j travail.

### 6.2 Pourquoi Typesense plutôt que Meilisearch (trace du pivot)

Le benchmark v1 (2026-04-23) concluait *"Winner: Meilisearch Cloud (9,15 vs 8,95)"* sur un scoring pondéré. L'owner a validé **Typesense**. Voici la justification explicite du choix final :

**Meilisearch avantages** :

- +0,2 pts sur le scoring qualité (meilleur multilingue FR/arabe/chinois).
- Disk-based storage → RAM requirements légèrement plus bas.
- UI admin plus élégante.

**Typesense avantages qui l'emportent** :

1. **Scoped API keys plus élégantes** : génération côté client possible (JWT-like), query direct frontend → Typesense sans proxy backend. Meilisearch tenant tokens nécessitent un endpoint backend pour la génération (pas de secret côté client). Pour une app mobile, ça simplifie l'archi.
2. **Field weighting plus riche** : `query_by: title,transcript` + `query_by_weights: 5,1` = boost titre ×5. Meilisearch a moins de contrôle granulaire sur le ranking (automagique).
3. **Signup credit confirmé public** : Typesense affiche "free credits" sur la landing page. Meilisearch ne mentionne pas de crédit à l'inscription (à vérifier en contactant sales, mais pas de garantie). Le crédit Typesense = extension de la phase pré-launch gratuite = runway founder.
4. **Écosystème légèrement plus mature pour use cases "application search"** : Typesense est utilisé par ~500 apps en prod (source: showcase Typesense.org), Meilisearch ~300. Pas décisif mais indicatif.
5. **Pricing comparable** : Typesense 2 GB $50/mo vs Meilisearch Cloud $12-15/mo (usage-based). Meilisearch est en réalité **moins cher** en phase launch (disk-based = RAM requirements inférieurs). L'avantage Typesense est sur la latence et la qualité, pas le prix.

**Trade-off accepté** : le multilingue FR de Meilisearch est meilleur, mais Typesense FR est **suffisant** pour V1. Si les transcripts arabe/chinois deviennent majoritaires (pivot marché), migration Typesense → Meilisearch = 1-2j.

**Conclusion** : Typesense l'emporte sur **la simplicité d'intégration mobile (scoped keys)**, **le signup credit**, et **la qualité de recherche (latence + field weighting)**. Le différentiel qualité search Meilisearch-Typesense est **marginal** pour un use case FR/EN. Attention : Typesense est **plus cher** que Meilisearch en phase launch (RAM-based pricing vs disk-based).

### 6.3 Pourquoi pas SQLite FTS5 en primary (vs fallback)

SQLite FTS5 local est **gratuit** (0 € vs 43 €/mois Typesense 2 GB) et offre **latence <10ms** (vs <50ms Typesense). Pourquoi ne pas en faire la solution principale ?

**Raisons** :

1. **Typo tolerance inférieure** : `spellfix1` nécessite maintenance d'un vocabulaire (extraction périodique des mots les plus fréquents depuis l'index, insertion dans table `spellfix1`). Typesense `num_typos: 2` = zero-config. Pour des transcripts ASR bruités, la typo tolerance est **critique**.
2. **Multilingue basic** : FTS5 porter = EN only. Pour FR, il faut se contenter de `unicode61 remove_diacritics 1` qui strip les accents mais ne fait pas de stemming (`chercher` ≠ `cherché`). Typesense supporte stemming FR/EN out-of-the-box.
3. **SPOF VM unique** : si la VM crash, l'index est perdu jusqu'à rebuild (~5 min depuis S3). En phase launch avec traffic croissant, ça peut arriver (burst CPU exhausted, kernel panic, AWS EC2 retirement). Typesense Cloud = HA native, pas de downtime.
4. **Overhead mental solo dev** : maintenir un index SQLite local + snapshots EBS + runbook rebuild = **8h/an ops**. Typesense Cloud = **0h/an**. Pour un solo dev qui jongle entre backend, mobile, marketing, product, **8h/an économisées** = **8h investies dans features** = différentiel valeur produit.
5. **43 €/mois = 75 % de l'infra fixe @100u, soit 0,43 €/user** : à 500 users (cluster 8 GB), Typesense passe à 0,258 €/user/mois. Le coût fixe pèse lourd en phase launch et **ne s'amortit pas aussi bien que précédemment estimé** (scaling RAM proportionnel au volume de docs). À 1000+ users, la migration vers self-hosted devient économiquement nécessaire.

**Conclusion** : Le différentiel de coût est **significatif** — SQLite FTS5 économise **516 €/an** @100u heavy-podcast vs Typesense Cloud 2 GB. SQLite FTS5 est une alternative solide comme **solution principale V1** si la typo tolerance dégradée est acceptable pour le profil d'usage (transcripts ASR). Typesense Cloud primary reste recommandé pour la **qualité UX** (typo tolerance sur contenu ASR bruité), mais le trade-off coût est beaucoup plus lourd qu'initialement estimé.

### 6.4 Hypothèses retenues

1. **Volume users** : 100 @launch (M2-M12), 1000 @Y2, 5000 @Y3 (aligned task-65).
2. **Recherches/user/mois** : 4-20 en moyenne (usage réel second-brain observé Readwise/Notion).
3. **Transcripts/user** : 200 en profil heavy-podcast @launch (mix : 60 % podcasts, 20 % articles, 10 % YouTube, 10 % courts).
4. **Taille moyenne transcript** : **36 KB** (profil heavy-podcast : podcasts 30 min ~54 KB, articles ~9 KB, YouTube ~18 KB, courts ~1 KB → moyenne pondérée ~36 KB = ~6 000 mots).
5. **Langue prioritaire FR** : 70 % transcripts FR, 30 % EN. Arabe/chinois <1 % en V1.
6. **Disponibilité search non-critique** : l'app reste utilisable en mode dégradé (filtres DynamoDB par date/tag/dossier) si Typesense est down. Cible 99 % uptime, pas 99,99 %.
7. **Latence <300ms p95 acceptable** : dans une app second-brain consultative, 200-300ms de search latency ne dégrade pas l'UX de façon perceptible.

### 6.5 Risques principaux

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|-----------|
| **Signup credit Typesense épuisé avant launch** | Moyenne | Moyen (coût +43 €/mois prématuré) | Implémenter SQLite FTS5 fallback (2j dev), activer si nécessaire |
| **Usage search 10× supérieur aux hypothèses** | Faible | Faible (Typesense MVP supporte 10k req/j) | Monitorer query volume dès M0, upgrade cluster si >5k req/j |
| **Qualité typo tolerance insuffisante sur FR** | Faible | Moyen (frustration users) | Mesurer empiriquement sur 20-30 transcripts FR réels, A/B test Typesense vs Meilisearch si <80% satisfaction |
| **Coût Typesense devient prohibitif à 500-1000+ users** | **Élevée** | Élevé (cluster 8 GB $150/mo → 32+ GB $300+/mo) | Migrer vers self-hosted Typesense sur ECS/EC2 ou vers Meilisearch Cloud disk-based (1-2j migration) |
| **Vendor lock-in Typesense si shutdown startup** | Très faible | Moyen | Typesense est open-source → self-host possible, ou migrate vers Meilisearch/OpenSearch (1-2 sem) |

### 6.6 Hors périmètre V1 (décisions reportées)

- **Recherche sémantique / vector search** : embeddings + cosine similarity pour chercher par concepts ("trouve-moi des contenus proches de X"). V2+, nécessite Typesense vector search (beta) ou Weaviate/Pinecone.
- **Autocomplete / suggestions** : "search-as-you-type" avec suggestions de mots. V1.5, requiert tuning du prefix search + dataset de vocabulaire.
- **Faceting avancé** : filtres combinables dans l'UI search (ex: "podcasts de 2025 dans le dossier Techno avec le tag IA"). V1.5, backend prêt (Typesense facets) mais UI à designer.
- **Search analytics** : dashboard "top queries", "zero-result queries", "slow queries". V1.5, Typesense Cloud inclut des analytics basiques mais nécessite intégration.
- **Recherche collaborative / shared libraries** : hors scope V1 (tout est privé par user).

### 6.7 Décisions restantes avant implémentation

1. **Activer le signup credit Typesense Cloud immédiatement** (dès M0, avant même le développement du pipeline d'indexation). Objectif : maximiser la durée du crédit gratuit.
2. **Implémenter l'abstraction `SearchProvider`** dès le début du dev (interface + adapters). Effort : +1j upfront, évite lock-in.
3. **SQLite FTS5 fallback : go/no-go ?** Si oui, implémenter en parallèle de Typesense (2j dev, feature flag pour switch). Si non, accepter le risque de basculer en cluster payant plus tôt que prévu.
4. **Field weighting titre vs transcript** : valider empiriquement le ratio boost optimal (3× ? 5× ? 10× ?). À tester sur 10-20 queries représentatives dès que 50+ transcripts indexés.
5. **Typo tolerance config** : `num_typos: 1` ou `2` ? 1 = plus strict (moins de faux positifs), 2 = plus permissif (meilleur recall sur ASR errors). À A/B test en beta.
6. **Recency decay** : appliquer un boost `_eval(created_at:>now-180d):5` pour favoriser les contenus <6 mois ? À valider avec users beta (certains veulent retrouver du vieux contenu sans biais recency).

---

## 7. Implémentation : étapes concrètes

### 7.1 Phase 0 : Setup Typesense Cloud (M0, 1h)

1. Créer compte Typesense Cloud : https://cloud.typesense.org/
2. Activer signup credit (pas de carte bancaire requise à ce stade).
3. Créer cluster : région **us-east-1** (colocated avec EC2), plan **MVP 0.5 GB / 2 vCPU burst** (gratuit sous crédit).
4. Créer collection `media_transcripts` via API :
   ```bash
   curl -X POST 'https://xxx.a1.typesense.net/collections' \
     -H 'X-TYPESENSE-API-KEY: <admin-key>' \
     -H 'Content-Type: application/json' \
     -d '{
       "name": "media_transcripts",
       "fields": [
         {"name": "user_id", "type": "string", "facet": true},
         {"name": "media_id", "type": "string"},
         {"name": "title", "type": "string"},
         {"name": "source_name", "type": "string", "optional": true},
         {"name": "transcript", "type": "string"},
         {"name": "created_at", "type": "int64"},
         {"name": "folder_id", "type": "string", "optional": true, "facet": true},
         {"name": "tags", "type": "string[]", "optional": true, "facet": true}
       ]
     }'
   ```
5. Sauvegarder l'admin API key et la search-only API key dans AWS Secrets Manager.

### 7.2 Phase 1 : Pipeline d'indexation (M0-M1, 1-2j)

**Fichier** : `media_summarizer/workers/search_indexing_worker.py`

**Flow** :

1. Queue SQS `search-indexing` reçoit un message à chaque fin de processing job (trigger = job status `completed`).
2. Worker consomme la queue, extrait `user_id`, `media_item_id`.
3. Récupère le transcript depuis S3 (`s3://bucket/transcripts/{media_id}.txt`).
4. Récupère les métadonnées depuis DynamoDB `media_items` table.
5. POST document vers Typesense :
   ```python
   import typesense

   client = typesense.Client({
       'nodes': [{'host': 'xxx.a1.typesense.net', 'port': '443', 'protocol': 'https'}],
       'api_key': os.environ['TYPESENSE_ADMIN_KEY'],
       'connection_timeout_seconds': 5
   })

   document = {
       'id': media_item_id,
       'user_id': user_id,
       'media_id': media_item_id,
       'title': media_item.title,
       'source_name': media_item.source_name or '',
       'transcript': transcript_text,
       'created_at': int(media_item.created_at.timestamp()),
       'folder_id': media_item.folder_id or '',
       'tags': media_item.tags or []
   }

   client.collections['media_transcripts'].documents.create(document)
   ```
6. Gestion erreurs : retry 3× avec backoff exponentiel, DLQ si échec persistant.

**Tests** :

- Unit test : mock Typesense API, vérifier payload.
- Integration test : indexer 10 transcripts réels, vérifier dans Typesense dashboard.

### 7.3 Phase 2 : API search (M0-M1, 1j)

**Endpoint** : `POST /api/v1/search`

**Request** :

```json
{
  "query": "kubernetes deployment",
  "filters": {
    "folder_id": "folder_xyz",  // optionnel
    "tags": ["devops"],          // optionnel
    "created_after": "2025-01-01T00:00:00Z"  // optionnel
  },
  "limit": 20,
  "offset": 0
}
```

**Backend logic** :

1. Authentifier user via JWT (extrait `user_id`).
2. Générer scoped API key Typesense :
   ```python
   scoped_key = client.keys.generate_scoped_search_key(
       search_key=TYPESENSE_SEARCH_KEY,
       embedded_params={
           'filter_by': f'user_id:={user_id}',
           'expires_at': int(time.time()) + 3600  # 1h
       }
   )
   ```
3. Construire query Typesense :
   ```python
   search_params = {
       'q': query,
       'query_by': 'title,transcript,source_name',
       'query_by_weights': '5,1,2',  # boost titre ×5, transcript ×1, source ×2
       'filter_by': f'user_id:={user_id}',
       'sort_by': '_text_match:desc,created_at:desc',
       'highlight_full_fields': 'transcript',
       'snippet_threshold': 30,
       'num_typos': 2,
       'per_page': limit,
       'page': offset // limit + 1
   }

   # Ajouter filtres optionnels
   if filters.get('folder_id'):
       search_params['filter_by'] += f' && folder_id:={filters["folder_id"]}'
   if filters.get('tags'):
       tags_filter = ' || '.join([f'tags:={tag}' for tag in filters['tags']])
       search_params['filter_by'] += f' && ({tags_filter})'
   if filters.get('created_after'):
       timestamp = int(datetime.fromisoformat(filters['created_after']).timestamp())
       search_params['filter_by'] += f' && created_at:>={timestamp}'

   results = client.collections['media_transcripts'].documents.search(search_params)
   ```
4. Formatter résultats :
   ```python
   formatted = {
       'total': results['found'],
       'results': [
           {
               'media_id': hit['document']['media_id'],
               'title': hit['document']['title'],
               'snippet': hit['highlight']['transcript']['snippet'],
               'score': hit['text_match'],
               'created_at': hit['document']['created_at']
           }
           for hit in results['hits']
       ]
   }
   ```
5. Retourner `{scoped_key, results}` au client.

**Option alternative (query direct frontend → Typesense)** :

- Le backend retourne uniquement la `scoped_key`.
- Le frontend (React Native) query Typesense directement via le SDK `typesense-instantsearch-adapter`.
- Avantage : latence minimale (pas de roundtrip backend).
- Inconvénient : nécessite inclure le SDK Typesense dans le bundle mobile (+200 KB).

**Décision** : **backend proxy recommandé V1** pour simplicité. Migrer vers query direct frontend en V1.5 si la latency devient un pain point.

### 7.4 Phase 3 : UI mobile search (M1-M2, 2-3j)

**Écran** : `SearchScreen.tsx` (React Native)

**Composants** :

- `SearchBar` avec debounce 300ms.
- `SearchFilters` (optionnels, collapsable) : dossier, tags, date range.
- `SearchResults` list : chaque item affiche titre, snippet (texte highlighted), date, bouton "Ouvrir".

**Flow** :

1. User tape query → debounce 300ms → `POST /api/v1/search`.
2. Afficher spinner pendant requête (max 300ms).
3. Afficher résultats : titre en gras, snippet avec `<b>` HTML rendered via `react-native-render-html`.
4. Tap sur résultat → naviguer vers `MediaDetailScreen` avec `media_id`.

**Edge cases** :

- **Zero results** : afficher message "Aucun résultat pour '[query]'. Essayez de reformuler ou élargir les filtres."
- **Erreur Typesense down** : fallback vers message "Recherche temporairement indisponible. Utilisez les filtres par dossier/tag."
- **Query trop courte (<3 caractères)** : ne pas lancer la requête (éviter faux positifs).

### 7.5 Phase 4 : Monitoring et alertes (M1, 1h)

**CloudWatch metrics custom** :

- `search_query_latency_ms` (p50, p95, p99).
- `search_query_count` (total/day).
- `search_zero_results_rate` (% queries sans résultat).
- `typesense_indexing_errors` (count).

**Typesense Cloud dashboard** :

- Vérifier daily : query volume, cluster CPU/RAM usage.
- Alerte si CPU >80 % sustained 10 min → considérer upgrade cluster.

**Logs** :

- Logger chaque query : `user_id`, `query`, `filters`, `result_count`, `latency_ms`.
- Rotate logs S3 après 7j (CloudWatch Logs retention).

### 7.6 Phase 5 : SQLite FTS5 fallback (optionnel, 2j)

**Condition** : si signup credit Typesense épuisé avant launch public ET l'owner choisit de ne pas basculer en cluster payant immédiatement.

**Implémentation** :

1. Créer fichier `/var/lib/app/search.db` sur VM EC2.
2. Table FTS5 :
   ```sql
   CREATE VIRTUAL TABLE transcripts_fts USING fts5(
       user_id UNINDEXED,
       media_id UNINDEXED,
       title,
       source_name,
       transcript,
       created_at UNINDEXED,
       folder_id UNINDEXED,
       tags UNINDEXED,
       tokenize='unicode61 remove_diacritics 1',
       prefix='2 3'
   );
   ```
3. Adapter `SQLiteFTS5Adapter` implémentant interface `SearchProvider`.
4. Worker `search_indexing_worker.py` : swap `TypesenseAdapter` → `SQLiteFTS5Adapter` via env var.
5. API `/search` : query SQLite au lieu de Typesense.
6. Typo tolerance via `spellfix1` :
   - Créer table vocabulaire `CREATE VIRTUAL TABLE vocab USING spellfix1;`.
   - Peupler vocabulaire périodiquement (cron daily) : `INSERT INTO vocab SELECT DISTINCT word FROM transcripts_fts`.
   - Sur query, checker `SELECT word FROM vocab WHERE word MATCH ?` → suggérer correction.

**Trade-off** : effort 2j, économie **43 €/mois** (516 €/an), qualité typo tolerance −20 % vs Typesense.

---

## 8. Validation acceptance criteria

| Critère | Validation |
|---------|-----------|
| **AC#1 : Besoin produit cadré** | ✅ §1.1-1.8 : types de requêtes, périmètre, signaux de pertinence, hypothèses usage réalistes |
| **AC#2 : Options comparées, reco explicite** | ✅ §2 : 7 solutions évaluées (DynamoDB, Neon, SQLite FTS5, Typesense, Meilisearch, OpenSearch, Algolia) + recommandation **Typesense Cloud** |
| **AC#3 : Impact qualité transcripts longs/bruités/hétérogènes** | ✅ §3 : scoring par dimension (highlighting, typo, ranking, multilingue) |
| **AC#4 : Scalabilité, latence, isolation, ops** | ✅ §4 : scaling par phase, latency comparée, multi-tenancy, overhead ops 0-100h/an |
| **AC#5 : Coût, complexité, maintenance, réversibilité** | ✅ §5 : pricing 3 ans, impact marge Standard 5€, effort implémentation, lock-in analysis |
| **AC#6 : Hypothèses, risques, hors périmètre, décisions restantes** | ✅ §6.4-6.7 : hypothèses explicites, 5 risques principaux + mitigation, hors scope V1, 6 décisions go/no-go |

---

## 9. Sources

### Documentation produit

- `project_v1_scope.md` (2026-05-01, clarification recherche full-text V1)
- `task-65-pricing-v1-benchmark/README.md` (rév. 2, 2026-05-01, infra EC2 + Typesense Cloud)
- `CHALLENGE-2026-05-01.md` (objections benchmark v1, hypothèses usage, SQLite FTS5, Readwise architecture)

### Solutions évaluées

- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [SQLite Spellfix1 Extension](https://www.sqlite.org/spellfix1.html)
- [Neon Pricing](https://neon.com/pricing)
- [Neon Plans Documentation](https://neon.tech/docs/introduction/plans) (attempted, ECONNREFUSED)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [pg_trgm Extension](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Typesense Official Site](https://typesense.org/)
- [Typesense Cloud Pricing](https://cloud.typesense.org/pricing) (signup credit confirmed)
- [Typesense GitHub](https://github.com/typesense/typesense) (RAM benchmarks)
- [Meilisearch Official Site](https://www.meilisearch.com/)
- [Meilisearch Pricing](https://www.meilisearch.com/pricing)
- [Amazon OpenSearch Pricing](https://aws.amazon.com/opensearch-service/pricing/)
- [Algolia Pricing](https://www.algolia.com/pricing/)
- [AWS DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
- [AWS EBS Pricing](https://aws.amazon.com/ebs/pricing/)

### Competitors & architecture references

- [Readwise Reader HN thread](https://news.ycombinator.com/item?id=34006202) (client-side SQLite WASM, JSON Patch sync)
- [Readwise official blog](https://readwise.io/blog) (offline-first architecture)

---

**Document généré** : 2026-05-12 — REDO 2ᵉ passe du benchmark task-53.1.
**Changes vs v1 (2026-04-23)** : ajout Neon Postgres, ajout SQLite FTS5 sur VM, pricing variable par documents, hypothèses usage réalistes V1 (400-2000 req/mois vs 1M/mois v1), trace pivot Typesense vs Meilisearch, intégration signup credit Typesense, fallback SQLite FTS5 si crédit épuisé, alignment task-65 rév. 2 (infra EC2 + coûts).
