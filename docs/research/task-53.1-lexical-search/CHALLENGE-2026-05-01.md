# Challenge du benchmark task-53.1 (Lexical Search)

**Auteur**: challenge indépendant
**Date**: 2026-05-01 (révisé après clarification owner)
**Document challengé**: `docs/research/task-53.1-lexical-search/README.md` (owner_decision: ok, 2026-04-28)
**Statut**: ce document ne modifie pas la décision validée — il l'interroge.

---

## Clarification de scope (owner 2026-05-01)

L'owner a confirmé que **le besoin V1 est bien une recherche lexicale full-text sur tous les transcripts de l'utilisateur** (pas seulement metadata). Cela tranche une ambiguïté documentaire antérieure:

- La mémoire `project_v1_scope.md` (2026-03-29) disait "recherche sur métadonnées uniquement, pas de full-text".
- Task-74 (Done, metadata via DynamoDB) reflétait cette décision initiale.
- Task-53.1 (validée 2026-04-28, Typesense Cloud) a **étendu** le scope au full-text sans que la mémoire soit mise à jour.

**Résolution**: task-74 (metadata) et task-53.1 (full-text) sont **deux features V1 complémentaires**. La mémoire `project_v1_scope.md`, le mobile plan et la description de task-74 ont été mis à jour en conséquence le 2026-05-01.

Les objections §1 du premier jet de ce challenge (contradiction scope) sont **retirées**. Le reste du challenge reste pertinent et concerne l'implémentation de task-53.1.

---

## Verdict global

Le benchmark task-53.1 est techniquement solide sur la **comparaison** des moteurs (Typesense vs Meilisearch vs OpenSearch vs Algolia). Deux problèmes subsistent après clarification du scope:

1. **Hypothèses d'usage non sourcées** qui pilotent la recommandation ("100-1,000 concurrent searches initially", "1M searches/month Year 1") alors que l'usage réel d'un second-brain à cette phase sera probablement **100-1000× plus faible**. Dimensionnement potentiellement excessif.
2. **Option SQLite FTS5 sur la VM non évaluée**: une alternative locale gratuite au Typesense Cloud à 15 €/mois, techniquement viable pour V1. Absente du benchmark.
3. **Paradoxe Typesense vs Meilisearch** : le benchmark lui-même conclut *"Winner: Meilisearch Cloud (by slim margin)"* (9,15 vs 8,95) mais la décision owner est Typesense. Le pivot n'est pas tracé. Si la raison était "multilingue non prioritaire V1", ça mérite d'être noté; si c'était autre chose (DX, écosystème, scoped keys), idem.

Le résultat: le benchmark **recommande correctement un bon outil**, mais peut-être **trop dimensionné et trop coûteux** pour la phase V1. Impact pricing: Typesense Cloud MVP = **52% des coûts d'infra fixes** du tier Standard V1 (cf. task-65 rev.2). Retarder son intégration de 3-6 mois libérerait de la marge, mais retarde aussi une feature V1 — arbitrage à faire.

---

## 1. Hypothèses d'usage invérifiées qui pilotent la reco

### 1.1 Performance & volume annoncés par le benchmark

§1.1 de task-53.1:
- *"Latency < 200ms p95"*
- *"Support 100-1,000 concurrent searches initially"*

§6.3:
- *"Moderate query volume: < 1M searches/month in Year 1"*

### 1.2 Réalité attendue en V1

**100 users en Year 1** (hypothèse task-65). Usage second-brain typique:

- Un user consulte son app ~5-10 fois/semaine.
- Par visite: 0 à 3 recherches (souvent 0 — les dossiers et tags suffisent pour 80% des retrievals).
- **Estimation réaliste: 1-3 recherches/user/semaine** = 4-12 recherches/user/mois.
- 100 users → **400-1200 recherches/mois total**. Trois ordres de grandeur sous l'hypothèse de task-53.1.

**Concurrent searches** = 100-1000 simultanés: ça voudrait dire que le 1er jour de lancement, 100 users cliqueraient *exactement* au même moment. Pour une app consultative asynchrone, c'est absurde. Réalité: **<5 searches concurrentes** en pic absolu à 100 users.

### 1.3 Ce que ça change pour la reco

Typesense Cloud est **parfaitement dimensionné pour 1M searches/mois**. Pour 400-1200 searches/mois, c'est sortir l'artillerie pour tuer une mouche. Cela n'invalide pas l'outil, mais ouvre la porte à une solution plus modeste en V1.

---

## 2. Option manquante: SQLite FTS5 local sur la VM

### 2.1 L'option qui n'a pas été évaluée

Le benchmark évalue 7 options:
1. DynamoDB native ❌
2. OpenSearch ⚠️
3. PostgreSQL FTS ❌ (nécessite migration RDS)
4. Algolia ❌
5. Typesense Cloud ✅
6. Meilisearch Cloud ✅
7. DynamoDB + Lambda + S3 Select ❌

Il manque: **SQLite FTS5 embarqué sur la VM EC2** qui héberge déjà FastAPI + les workers (cf. task-65 rev.2).

### 2.2 Comment ça marche

- Même pipeline que Typesense: le worker `search_indexing_worker.py` (déjà implémenté) consomme la queue, récupère le transcript depuis S3, l'indexe.
- Au lieu d'envoyer au SaaS Typesense, on écrit dans un fichier SQLite local `/var/lib/app/search.db`.
- Module natif Python (`sqlite3` dans la stdlib) + extension FTS5 compilée par défaut.
- Requête type: `SELECT media_id, snippet(idx, 0, '<b>', '</b>', '...', 10) FROM idx WHERE user_id = ? AND transcript MATCH ? ORDER BY rank LIMIT 20;`
- Persistance: fichier sur EBS gp3 → snapshots quotidiens EBS = backup.
- Perte accidentelle: rebuild en ~5 min depuis S3 (re-indexer tous les transcripts).

### 2.3 Performance

- **Latence**: <10 ms pour des requêtes sur <10 GB d'index (V1 et V2 largement couverts).
- **Typo tolerance**: pas native comme Typesense, mais possible via l'extension `spellfix1` (stdlib) ou trigram indexing.
- **Prefix search**: natif FTS5 avec `MATCH 'mach*'`.
- **Ranking BM25**: natif FTS5 (`ORDER BY rank`).
- **Highlighting**: natif FTS5 (`snippet()`).
- **Multi-tenancy**: `WHERE user_id = ?` en filtre normal, garantie via layer applicatif comme DynamoDB.

### 2.4 Coût

| Poste | SQLite FTS5 local | Typesense Cloud MVP |
|-------|-------------------|---------------------|
| Infra mensuelle | **0 €** | 15 €/mois |
| RAM VM consommée | Négligeable (lecture disque) | 0 (externe) |
| Disque EBS | ~300 MB à 100 users | 0 (externe) |
| Ops overhead | Inclus dans le backup EBS existant | 0 (managé) |

### 2.5 Limites honnêtes

- **Lié à la VM unique (SPOF)**: si la VM meurt, l'index est perdu jusqu'à rebuild (~5 min). Mitigation: snapshots EBS quotidiens + script de rebuild automatisé. À V1 scale c'est acceptable.
- **Typo tolerance moins native** qu'un moteur dédié. L'extension `spellfix1` est décente mais pas au niveau de Typesense sur ce critère.
- **Scaling vertical seulement**: tant que l'app est sur une seule VM, c'est aligné. Si on passe à plusieurs VMs (V2+), il faut soit répliquer le SQLite soit migrer vers Typesense. Migration = 1-2j vu que le pipeline d'indexation est déjà factorisé dans `search_indexing.py`.
- **Moins bon multilingue qu'un moteur spécialisé** pour le non-latin (chinois, arabe, japonais). Pour FR/EN/ES: largement suffisant.

### 2.6 Pourquoi c'est pertinent pour V1 spécifiquement

- La VM EC2 existe déjà (cf. task-65 rev.2), SQLite n'ajoute aucune infrastructure.
- 100-500 users V1 = volume confortable pour FTS5 local (10-100 MB d'index).
- Économie: **15 €/mois × 12 = 180 €/an** soit ~4 points de marge sur Standard 5€ @100u.
- Le worker d'indexation existant reste quasi identique (swap de l'adapter Typesense → adapter SQLite).

---

## 3. Paradoxe Typesense vs Meilisearch

### 3.1 Ce que conclut le benchmark

§6.1:

> **Winner: Meilisearch Cloud (by slim margin), with Typesense Cloud as equally viable alternative.**

Scores:
- Meilisearch: **9,15**
- Typesense: **8,95**

Différentiateurs Meilisearch cités:
- **Meilleur multilingue** (§3.1: *"best for non-Latin scripts"*).
- **Disk-based storage** (lower RAM requirements).
- **Légèrement moins cher** en cloud usage-based ($30-50/mois vs $40-60 Typesense MVP).

### 3.2 Ce qu'a choisi l'owner

§7 (Owner Validation): **Typesense Cloud**.

Pas de justification du pivot dans le document.

### 3.3 Pourquoi ça compte

Si le choix Typesense est arbitraire ou non-documenté, un benchmark futur (V1.5, V2) risque de revenir sur cette décision sans savoir pourquoi elle avait été prise, gaspillant du temps de recherche.

**Hypothèses plausibles de la préférence Typesense**:
- Scoped API keys plus élégants que tenant tokens Meilisearch (§4.3 du benchmark le note).
- Meilleur field weighting pour mix transcript+title (§2.5: *"stronger field-weighting control"*).
- Écosystème plus mature (25k vs 57k stars mais c'est tout récent pour Meilisearch).
- Intégration mobile native plus simple.

**Recommandation**: ajouter une ligne à `task-53.1/README.md` §7 expliquant pourquoi Typesense a été préféré à Meilisearch malgré le scoring légèrement inférieur. Utile pour la traçabilité future.

---

## 4. Coupling avec le pricing V1 et signup credit

### 4.1 Impact sur le pricing

Task-65 rev.2 modélise l'infra V1 en 3 phases:

| Phase | Fixed cost/mois | Dont Typesense |
|-------|----------------:|---------------:|
| Pré-launch (signup credit) | 14 €/mois | 0 € (credit) |
| Launch (MVP cluster) | 29,5 €/mois | **15,5 €** (52%) |
| Growth (Growth cluster) | 53 €/mois | **43 €** (81%) |

Typesense pèse lourd sur l'infra fixe. Si SQLite FTS5 est viable (§2), on peut rester en phase pré-launch côté Typesense **indéfiniment** (juste EC2 + AWS misc ≈ 14 €/mois) tant qu'on reste sur VM unique.

### 4.2 Signup credit Typesense — non mentionné

Le benchmark ne mentionne **pas** le free signup credit Typesense Cloud (*"free credits, no credit card"* — confirmé sur cloud.typesense.org le 2026-05-01). Montant non public, mais utile pour:

- **Validation technique du pipeline d'indexation** sans coût M0.
- **Beta closed** avec les premiers users sans basculer en MVP cluster payant.

À activer dès que task-53.1 passe en implémentation.

### 4.3 Budgétaire sincère (trois branches)

| Solution full-text V1 | Year 1 | 3-year |
|----------------------|-------:|-------:|
| **SQLite FTS5 local** | 0 € | 0 € |
| **Typesense Cloud signup credit → MVP cluster au user 500** | ~90 € | ~5 500 € |
| **Typesense Cloud MVP dès jour 1** | 180 € | ~5 700 € |

L'écart pour 3 ans est faible entre les deux branches Typesense, plus large vs SQLite.

---

## 5. Risques non évoqués dans le benchmark

### 5.1 Vendor lock-in plus fort que "low"

§5.4 classe Typesense en "Low Lock-In". En pratique:

- L'adapter `search_indexing.py` est déjà écrit pour Typesense. Migrer vers Meilisearch/SQLite FTS5 nécessite réécriture adapter + schema de reindex + re-test qualité.
- Estimation: **1-2 semaines** pour un solo dev.
- Ce n'est pas "low lock-in" au sens "cliquer un bouton"; c'est "reasonable lock-in" si on veut changer.

Mitigation: l'abstraction "SearchProvider" proposée en §5.4 du benchmark **n'est pas encore en place dans le code actuel**. Elle mériterait d'être implémentée explicitement pour que l'owner puisse swap sans refactor massif.

### 5.2 Qualité de recherche sur transcripts FR bruités

Le benchmark §3.1 dit *"Language: Primarily English, potential multilingual content"*. Or cette app cible le marché **FR en premier**. Les transcripts Deepgram FR comportent:

- Erreurs homophones ("chant" vs "champ", "cou" vs "coût").
- Ponctuation irrégulière.
- Accents non toujours bien reconnus.
- Anglicismes fréquents dans les podcasts tech.

Typesense FR est **correct** mais pas optimisé. Meilisearch serait potentiellement meilleur sur ce terrain. À mesurer empiriquement dès les premiers transcripts FR indexés.

---

## 6. Questions concrètes à trancher avec l'owner

Par ordre de priorité:

1. **SQLite FTS5 local comme alternative V1**: gain de 15 €/mois (~180 €/an), acceptable de perdre les bénéfices managed de Typesense en échange? (cf. §2)
   - Si **oui** → retravailler task-53.1 pour implémenter l'adapter SQLite, garder Typesense Cloud comme option V2.
   - Si **non** → confirmer Typesense Cloud comme décidé.

2. **Justification Typesense vs Meilisearch**: ajouter une ligne au §7 du benchmark task-53.1 expliquant pourquoi Typesense a été préféré malgré score Meilisearch légèrement supérieur. Prévention de rework futur. (cf. §3)

3. **Signup credit Typesense**: activer dès M0 pour étendre la phase pré-launch gratuite. (cf. §4.2)

4. **Abstraction SearchProvider**: investir 1-2j pour poser une interface proprement abstraite dans `search_indexing.py`, afin de pouvoir swap SQLite ⟷ Typesense ⟷ Meilisearch sans refactor lourd. (cf. §5.1)

5. **Mesure empirique FR**: dès qu'on a 20-30 transcripts FR indexés, lancer 10-20 recherches représentatives et noter les échecs (typo, homophone, accent). Seuil d'acceptabilité à définir. Si dégradé, évaluer Meilisearch. (cf. §5.2)

---

## 7. Recommandation personnelle

Si j'étais l'owner, je reverrais la décision dans cet ordre:

1. **Activer le signup credit Typesense Cloud immédiatement** pour la phase pré-launch (0 € pendant M0-M3 selon le crédit reçu). Pas de changement de décision.

2. **Considérer SQLite FTS5 comme alternative V1 sérieuse** si la marge compte (+4 pts sur Standard 5€). La décision se pose ainsi:
   - Typesense Cloud = 15 €/mois, zéro ops, typo tolerance supérieure, prêt pour scale.
   - SQLite FTS5 = 0 €/mois, SPOF VM (acceptable V1), typo tolerance correcte via spellfix1.
   - Différence UX: marginale à 100 users. Différence financière: 180 €/an.

3. **Dans tous les cas**: implémenter l'abstraction `SearchProvider` pour rendre réversible à peu de frais.

4. **Dans tous les cas**: documenter la raison du choix Typesense vs Meilisearch dans task-53.1 §7.

La décision "Typesense Cloud" **n'est pas mauvaise** — elle est juste **un peu chère pour V1** et **non justifiée** vis-à-vis du benchmark lui-même qui pointe Meilisearch en gagnant.

---

## 8. Analyse de l'approche Readwise Reader

*Ajout 2026-05-11 — recherche sur le blog et Hacker News Readwise.*

### 8.1 Ce qu'ils ont construit

Readwise Reader est un concurrent direct sur le marché "second brain + lecture". Leur solution de recherche full-text est **client-side SQLite FTS5**:

> *"Our search on web is built with wasm sqlite."*
> — Tristan Homsi (cofounder), Hacker News, décembre 2022 ([source](https://news.ycombinator.com/item?id=34006202))

Concrètement, l'architecture Readwise repose sur trois couches:

1. **Parsing server-side**: les articles, PDFs, podcasts et leurs transcripts sont parsés côté serveur. Readwise maintient un ingestion pipeline dédié.
2. **Sync vers device**: le contenu parsé est synchronisé en continu vers le device de l'utilisateur via un mécanisme **JSON Patch** custom (ils ont évalué puis rejeté les CRDTs type Automerge pour des raisons de performance).
3. **SQLite local + FTS5**: sur mobile (iOS/Android), le contenu indexé vit dans un SQLite natif. Sur web, ils utilisent **SQLite compilé en WebAssembly (WASM)**. Dans les deux cas, l'index FTS5 est construit localement à partir des données synchronisées.

Résultat: la recherche full-text fonctionne **hors ligne**, sans roundtrip réseau, avec une latence <10ms.

### 8.2 Scope réel de la recherche

- **Ce qui est indexé**: texte complet de tous les documents de la Library (articles, PDFs, ebooks, transcripts de podcasts) + titres + auteurs.
- **Ce qui n'est pas indexé**: le Feed (documents pas encore sauvegardés dans la Library).
- **Performance**: "blazingly fast" — justifiée par la recherche locale (pas de latence réseau).
- **Offline**: natif. Si le tab web est ouvert avant de passer offline, ça continue de fonctionner. Sur mobile, après sync initial, ça fonctionne offline indéfiniment.

### 8.3 Contraintes du modèle WASM SQLite sur web

SQLite WASM sur web n'est pas trivial à déployer:

- Requiert les en-têtes HTTP **`Cross-Origin-Opener-Policy: same-origin`** et **`Cross-Origin-Embedder-Policy: require-corp`** pour accéder à `SharedArrayBuffer`.
- Ces en-têtes cassent les iframes tierces (publicités, widgets d'embed), ce qui nécessite une révision de l'intégration de tout contenu cross-origin.
- La persistance WASM SQLite passe par **OPFS** (Origin Private File System) ou IndexedDB — deux APIs aux comportements subtils selon le navigateur.
- Complexité de build: SQLite doit être compilé en WASM avec FTS5 activé (`-DSQLITE_ENABLE_FTS5`), ce qui n'est pas la configuration par défaut de `sql.js`.

### 8.4 Pertinence pour notre app — analyse honnête

| Critère | Readwise Reader | Notre app V1 |
|---------|----------------|--------------|
| Architecture | Local-first / offline-first | Server-first (AWS) |
| Offline search V1 requis? | Oui (use case core) | Non |
| Taille contenu par doc | Articles : ~500-2000 mots | Podcast 45 min: ~9000 mots |
| Multi-device sync déjà en place | Oui (JSON Patch custom) | Non (pas de sync local) |
| Stack mobile | Cross-platform depuis M0 | Mobile V2 (Stitch) |
| Coût implémentation client-side | Équipe dédiée, 12+ mois de R&D | Solo dev V1 |

**La complexité Readwise vient d'un seul choix**: la recherche fonctionne **hors ligne**. Pour ça, l'index FTS5 doit vivre sur le device. Pour ça, le contenu (transcripts complets) doit être synchronisé sur le device. C'est cette cascade qui crée la complexité: sync JSON Patch + WASM SQLite + gestion de cohérence multi-device.

Si la recherche offline n'est **pas un requirement V1** — ce qui est le cas ici — on n'a pas à faire ce que Readwise a fait. Le schéma mobile V1 est bien plus simple: actions offline queued localement → flush vers l'API à la reconnexion → serveur met à jour DynamoDB + Typesense. La recherche n'est simplement pas disponible hors ligne (comme dans 99% des apps V1). Rien dans ce schéma ne requiert un index local ni un sync de contenu vers le device.

### 8.5 Ce que l'approche Readwise confirme néanmoins

1. **SQLite FTS5 est la bonne technologie** pour ce use case. Readwise l'a validé en production à grande échelle. Ça conforte l'option §2 de ce challenge (SQLite FTS5 sur VM).
2. **La recherche peut être excellente sans SaaS spécialisé**. Typesense/Meilisearch ne sont pas obligatoires pour avoir de bonnes performances FTS.
3. **L'architecture client-side est la cible long-terme naturelle** si on construit des apps mobiles offline. La migration SQLite FTS5 server → client est plus simple que Typesense Cloud → client (Typesense n'a pas de mode embarqué).

### 8.6 Comparaison des trois approches

| Approche | Coût V1 | Offline | Perf | Complexité | Migration V2 |
|----------|--------:|--------|------|------------|-------------|
| **SQLite FTS5 server** (§2) | 0 €/mois | Non | <10ms | Faible | Easy → client (futur) |
| **Typesense Cloud** (décision actuelle) | 15 €/mois | Non | <50ms | Faible | Difficile → SQLite client |
| **SQLite FTS5 client-side** (approche Readwise) | 0 €/mois | Oui | <10ms | Très élevée | Pas de migration nécessaire |

**Conclusion section 8**: Readwise a eu raison de choisir client-side SQLite FTS5 pour *leur* produit. Ce choix **n'est pas transposable à notre V1** faute d'architecture locale et de ressources. En revanche, il valide SQLite FTS5 comme technologie, renforce l'option §2 (serveur local), et dessine une trajectoire crédible pour une V2 mobile offline si on décide de l'investissement.

---

## 9. Ce que ce challenge ne dit pas

- Il ne prétend pas que Typesense est un mauvais outil. Typesense est excellent.
- Il ne remet pas en cause la qualité technique du benchmark (exhaustif, bien structuré).
- Il confirme que **full-text transcript est bien une feature V1** (clarifié par l'owner 2026-05-01).
- Il ne tranche pas: il pose les bonnes questions pour que l'owner arbitre.

---

**Reference au challenge task-65** (même date, même auteur): ces deux benchmarks interagissent via le coût infra fixe. Task-65 rev.2 a modélisé Typesense MVP à 15 €/mois. Si task-53.1 bascule sur SQLite FTS5 local, la marge Standard 5€ @100u passe de +27% à ~+31% (récupération de 4 points).
