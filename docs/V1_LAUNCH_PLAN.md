# V1 Launch Plan — Media Summarizer

> Plan exhaustif des étapes restantes pour mettre l'application en production.
> Date de rédaction : 2026-05-19. Dernière mise à jour : **2026-09-02**
> (réconciliation de l'état git — 43 commits locaux non poussés — et clôture du
> second client OAuth Android ; la réconciliation de fond avec le worktree, le
> backlog, la CI et le code date du 2026-08-21). Les gates
> techniques backend qui bloquaient le plan au 2026-07-31 restent **fermés** :
> source synchronisée, CI verte, HEAD déployé, runtime API isolé, dev et prod
> dans deux comptes AWS séparés. Ce qui reste est concentré sur **le mobile, le
> billing, les stores et le légal** — plus sur l'infrastructure. Le chemin
> critique n'a pas bougé depuis le 2026-08-13 ; ce qui a bougé, c'est la
> **surface produit** (cf. § 0), retravaillée en profondeur du 2026-08-14 au
> 2026-08-21.

### État de vérité au 2026-08-21

- **Source et CI vertes** : `Main Branch Checks` et `Deploy Lambda Functions`
  sont `success` sur tous les push récents. Le dernier commit poussé est
  `30cf62c` (2026-08-29T21:10) — c'est lui que le runtime dev exécute.
- **43 commits locaux non poussés** — relevé le 2026-09-02 contre
  `git ls-remote`, la seule mesure fiable : `origin/main` est sur `30cf62c`,
  `main` local sur `e78ce1b`. **10 d'entre eux touchent `media_summarizer/` ou
  `infrastructure/`**, donc le runtime dev n'est pas le HEAD :
  - le matching événement RevenueCat → abonnement (`task-334`, `2376622`) ;
  - le `max(trial, paid)` sur le quota d'un abonné (`task-335`, `fedb843`) ;
  - les fixes translation / artifacts / classifieur LLM (`task-327`, `328`,
    `330`, `333`) ;
  - **deux alarmes CloudWatch** (`e2cae8d`, `aebbb73`), qui demandent un
    `terraform apply` en plus du deploy Lambda déclenché par le push.

  Conséquence à ne pas oublier : **les achats sandbox du 2026-09-01/02 ont
  tourné sur le code d'avant `task-334`**, donc le fix de matching webhook n'a
  jamais été exercé en vrai. À pousser avant tout re-run E2E.
- **Runtime API isolé (`task-217`, Done le 2026-08-06)** : image API dédiée,
  reserved concurrency configurable, warm-up EventBridge, health gate de release,
  logs API Gateway enrichis, documenté dans `docs/API_LAMBDA_RUNTIME.md`. Mesure
  du 2026-08-13 sur dev : **cold 5,2 s / warm 1,0 s**, contre 25,7 s au
  déclenchement de la tâche.
- **Isolation par comptes AWS séparés (`task-221` + `task-237` + `task-248`)** :
  Terraform éclaté en `envs/{dev,staging,prod}` sur `modules/platform`, 100 % des
  noms physiques suffixés, un state par environnement. **`staging` a été détruit**
  (145 ressources, il était vide) et **`prod` vit dans un compte AWS dédié**
  `866874944541` sous l'organisation `o-7sf5u7j5hd`. 199 ressources créées, health
  prod `HTTP 200`. Les 21 tables legacy non suffixées sont supprimées
  (`task-249`) : dev ne porte plus que 26 tables, toutes `-dev`.
- **Prod est une coquille en veille, volontairement** : `enable_alarms`,
  `enable_dashboard` et `enable_worker_polling` à `false`, et son secret runtime
  contient **0 clé**, contre **40 clés dont 37 vivantes** côté dev (recomptées
  clé par clé le 2026-08-21 par `task-312` ; le « 37 » que ce plan répétait
  confondait le total et les clés réellement lues). C'est l'objet de `task-252`,
  owner-only. Le health check répond `200` parce qu'il ne teste que DynamoDB via
  le rôle IAM — aucune intégration tierce ne fonctionne.
- **Repo passé PUBLIC** : vérifié le 2026-08-13. Conséquences directes — la
  branch protection n'est plus bloquée par le plan GitHub et est **désormais
  configurée** (`task-257`, régime léger : force-push et suppression refusés,
  aucun required check ni required review, `rulesets` toujours `[]`), et tout
  identifiant écrit dans un fichier suivi est désormais public (d'où `task-255`
  et `de3ac86`).
- **Mobile inchangé et redevenu le chemin critique** : aucune build EAS Android
  n'existe, la build iOS du 2026-06-11 a expiré, `Mobile Build & Distribute` est
  rouge faute d'`EXPO_TOKEN`. `task-163` ACs #6-#8, `task-164` et `task-165`
  restent ouverts.
- **Production release** : `docs/RELEASE_LOG.md` reste la source de vérité :
  v1.0.0 `Pre-release`, aucun tag (`git tag -l` vide), aucun build production,
  aucune soumission.
- **Backlog** : **13 tâches non-`Done`** au 2026-09-02 — 62, 118, 145, 164, 165,
  166, 172, 180, 186, 229, 252, 260, 337. `task-262`, `task-238`, `task-261` et
  `task-163` sont passées `Done`, et les 26 tâches ouvertes entre le 2026-08-14 et le
  2026-08-21 (287, 289 à 312) sont toutes closes. `task-212`/`task-213`
  (architecture LLM) restent **archivées** sur `owner_decision: abandoned`.
  Aucune des 13 restantes n'est un gate technique : 4 tâches produit V2 / support
  (62, 118, 145, 229), 3 tâches mobile/device (164, 165, 166), 1 tâche CI en sommeil
  (172), 4 tâches owner-only stores/branding/prod (180, 186, 252, 260), et
  `task-337` (alignement du libellé de quota du paywall sur la formulation store).
  **12 des 13 portent `dispatchable: false` : `task-337` est la seule tâche que le
  dispatcher peut confier à un agent.** Tout le reste est de la main d'œuvre owner
  (devices physiques, dashboards stores, credentials).
- **La surface produit a beaucoup bougé depuis le 2026-08-13** — 12 tâches
  livrées qui changent ce que l'utilisateur voit, donc ce que les screenshots
  stores devront montrer (cf. § 0, « Surface produit V1 ») : consommation
  facturée **en minutes uniquement** (`task-287`), essai gratuit en **fenêtre
  unique de 30 jours** au lieu du mois calendaire (`task-300`/`301`), paywall
  refondu (`task-299`), **cover image + nom du créateur** sur chaque média
  (`task-302`/`304`/`308`), **signal d'engagement** « Continue learning »
  (`task-303`/`305`/`311`), onglet **Library** listant tous les médias
  (`task-306`), et **Inbox reconstruite en écran Home** de rangées de tuiles
  (`task-307`).
- **Rien n'est déployé sur les stores, et ça change la façon d'écrire les tâches** :
  ni App Store, ni Play Store, ni TestFlight, ni Internal Testing ; zéro
  utilisateur hors owner, zéro donnée de production, zéro abonnement actif. Aucune
  couche de compatibilité, aucun fallback « au cas où », aucune migration de
  données n'est justifiable — on supprime, on ne pontifie pas. La règle complète,
  ses deux exceptions et ses conséquences sur l'ordre des tâches sont consignées
  dans `AGENTS.md` (« Nothing is deployed yet — delete legacy instead of bridging
  it ») et `CLAUDE.md`. Toute justification par « les utilisateurs existants
  seraient… » est, dans ce dépôt, une erreur factuelle.

### Chemin critique restant, dans l'ordre

Le plan a basculé : l'infrastructure n'est plus le goulot. Ce qui reste, du plus
bloquant au moins bloquant :

1. **Re-run `pytest -m e2e` contre dev** — dernier gate backend ouvert (Phase 4).
2. **Build Android unique + validations device** — `task-163` ACs #6-#8,
   `task-164`, `task-165`, puis `task-166` clôture la Phase 5.
3. ✅ **Billing réel — fait.** Phase 6, dans l'ordre `task-262` → {`task-238`,
   `task-261`} : les trois tâches sont `Done`. Un achat sandbox a tourné de bout en
   bout sur Play le 2026-09-01 (cycle complet jusqu'à l'`EXPIRATION`) et sur l'App
   Store le 2026-09-02 (`INITIAL_PURCHASE`, `PRODUCT_CHANGE`, `RENEWAL`), avec le tier
   résolu depuis l'entitlement dans les deux cas. `revenucat_events-dev` porte
   32 items, `subscriptions-dev` un abonnement iOS actif. Le
   `REVENUCAT_WEBHOOK_SECRET` n'est plus « à confirmer » : 32 requêtes signées ont
   franchi un Lambda qui répond `401` sur un Bearer invalide.
4. **Owner-only, sans substitut possible** — les credentials du secret prod
   (`task-252` : 37 clés vivantes à pousser dans une coquille vide), le quota
   Lambda prod, les vérifications d'éligibilité du compte Google Play — dont un
   éventuel closed testing de 14 jours qui, s'il s'applique, borne par le bas la
   date de publication Android.
5. **Stores et légal** — nom marketing (`task-186`), icônes (`task-180`), domaine
   tranché puis API/privacy/terms réellement hébergés, listings et review accounts.
   **Les screenshots devront montrer l'UI d'après `task-306`/`307`**, pas l'Inbox
   verticale d'avant le 2026-08-21.
6. **Hygiène, rapide** — pousser les 43 commits locaux (cf. § « État de vérité »,
   dont 10 touchent le backend), puis renseigner
   `EXPO_TOKEN` (dernier reste de `task-258`). Le reste de cette ligne est fait :
   les 5 fichiers `uv.lock` du worktree sont commités (`c05df88`), la branch
   protection est configurée (`task-257`), le workflow de build mobile est
   désarmé (`task-258`) et les comptes E2E résiduels sont purgés (`task-259`).

---

## 0. Périmètre V1 confirmé

### Sources d'ingestion supportées en V1

| Source | Statut code | Bloquant V1 |
|---|---|---|
| Articles web (lecture/extraction) | OK | — |
| **YouTube** | OK — **Apify seul** depuis `task-309` (2026-08-20). La branche yt-dlp est supprimée, pas démotée : mesurée morte depuis Lambda (0 succès sur 12 jobs, `Sign in to confirm you're not a bot` à chaque tentative, ~6,4 s perdues par invocation). **Il n'y a pas de fallback audio** — aucun actor supporté n'expose l'URL audio brute, donc un échec actor marque le job `failed` | — |
| Podcasts (PodcastIndex resolver) | OK | — |
| Audio file (upload direct) | OK | — |
| **X (Twitter)** | OK — worker, resolver, classifier, orchestrator câblés | — |
| **TikTok** | OK — worker dédié + 2-tier rate limiter (pacing + quota horaire). **Seul consommateur restant de yt-dlp**, avec fallback Apify sur IP-block | — |
| **Instagram** | OK — **Apify seul** depuis `task-310` (2026-08-20), résolu dans le worker et non dans la requête API (`task-274`) : Reel/IGTV + Post image/carousel. Comment Scraper et legacy video-post branch supprimés (`task-173`), branche yt-dlp supprimée à son tour | — |
| Shared text | OK | — |
| **Documents (PDF/DOCX/PPTX)** | OK — LlamaParse resolver (primary) + Unstructured resolver (fallback) + document_parsing worker câblés | — |

> Conséquence pour `task-145` (proxy résidentiel V2) : son périmètre se réduit à
> TikTok. Instagram et YouTube ne dépendent plus d'une IP Lambda non bloquée.

### Méthodes d'authentification V1

| Méthode | Statut | Bloquant V1 |
|---|---|---|
| Email + password | OK (backend + mobile) | — |
| **Sign in with Apple** | Code OK — backend + mobile câblés. Obligatoire App Store car Google login présent | OK (chaîne Apple Developer complète provisionnée 2026-06-08 : Service ID, Sign in with Apple Key `.p8`, Team ID, Key ID, Return URL prod renseignés dans `.env`) |
| **Continue with Google** | Code OK — backend + mobile câblés. Backend Web client ID + secret OK dans `.env`. OAuth Web + iOS provisionnés côté Google Cloud. **Android validé sur device le 2026-09-02**, via Credential Manager et le second client déclaré sur le SHA-1 Play App Signing | Reste l'écran de consentement Google à publier en Production en Phase 10 |

Sur l'`aud` des id_tokens mobiles et pourquoi le backend a besoin de
`GOOGLE_NATIVE_AUDIENCE_IOS`/`_ANDROID` en plus du client Web (`task-298`),
voir § 3.2. Le refresh token voyage en JSON, pas en cookie (`task-293`), et la
session d'un utilisateur actif ne s'éteint plus (`task-294`/`295`).

### Surface produit V1

Ce que l'app fait, au-delà de l'ingestion — refondu entre le 2026-08-14 et le
2026-08-21, et **c'est cette UI que les screenshots stores doivent montrer**.

| Domaine | État | Référence |
|---|---|---|
| **Modèle de consommation** | Facturé **en minutes uniquement**, plus en items — un seul compteur lisible par l'utilisateur (`minutes_remaining`). Les minutes audio ne sont comptées qu'une fois par user et par média | `task-250`/`251`/`287`, `core/services/quota_enforcer.py` |
| **Essai gratuit** | **Fenêtre unique de 30 jours** ouverte à `created_at`, une seule allocation (300 min, tier `mix`), fermée à `created_at + duration_days`. Avant `task-300` le compteur se réinitialisait le 1er du mois et distribuait donc deux allocations. Annoncé dans l'app (Account + Home) | `task-300`/`301`, `pricing_config_service.DEFAULT_PRICING_CONFIG.free_trial` |
| **Paywall** | 3 tiers servis depuis la config de pricing, aucune figure en dur, recommandation d'un plan à la hauteur de l'usage, refus nommé explicitement, liens légaux exigés par les stores | `task-299`, `mobile/app/paywall.tsx` |
| **Vignettes média** | Chaque média porte une **cover image** et un **nom de créateur**, extraits par source. Une cover partagée n'est purgée que si plus aucun save ne la référence | `task-302`/`304`/`308`, `core/services/cover_capture.py` |
| **Home** | L'Inbox verticale est remplacée par un écran d'accueil en **rangées de tuiles** : « Continue learning » (piloté par un signal d'engagement récent, purgé au-delà de 90 j) et « Recently added » | `task-303`/`305`/`307`/`311`, `mobile/app/(tabs)/inbox.tsx`, `core/services/engagement_service.py` |
| **Library** | L'onglet recherche est devenu le point d'entrée bibliothèque : il liste **tous** les médias sauvegardés, plus seulement les collections | `task-306`, `mobile/app/(tabs)/search.tsx` (titre d'onglet « Library ») |
| **Collections / AI** | Écran média scindé en onglets **Reader / AI**, écran collection en **Sources / AI** ; artifacts en historique horodaté append-only, y compris au niveau collection | `task-269` à `273`, `290`, `291` |
| **API** | Toutes les routes sont sous `/api/`, le préfixe `/api/v1/` est supprimé | `task-289` |

> À noter : le fichier de l'onglet Home s'appelle toujours `inbox.tsx` et son
> titre d'onglet est toujours « Inbox » ; l'onglet Library est servi par
> `search.tsx`. Les noms de fichiers sont en retard sur les écrans, ce n'est pas
> un bug — juste un piège à la lecture.

---

## 1. Tâches restantes réellement bloquantes V1

Le backend V1 et le scope produit principal sont largement implémentés côté
code. Les tâches restantes ne sont cependant pas seulement des formalités
stores : plusieurs gates techniques et de sécurité doivent être fermées avant
un staging ou une soumission.

### Bloquants P0 avant prod — **tous fermés au 2026-08-13**

| Zone | Tâches / preuve | Statut au 2026-08-13 |
|---|---|---|
| Isolation API Lambda | `task-217` | **Fait (2026-08-06)** — image API ARM64 dédiée (`infrastructure/docker/lambda-api.Dockerfile`), image workers séparée, reserved concurrency configurable, warm-up EventBridge, health gate de release, logs API Gateway enrichis, `docs/API_LAMBDA_RUNTIME.md`. Mesuré le 2026-08-13 : cold 5,2 s / warm 1,0 s |
| Isolation dev/prod | `task-221` (benchmark, `owner_decision: ok`, option B) → `task-237` → `task-248` | **Fait (2026-08-13)** — `envs/{dev,staging,prod}` sur `modules/platform`, un state par env, 100 % des noms suffixés, `scripts/tf_plan_guard.sh`. Dev reste dans `125313707865`, **prod dans le compte dédié `866874944541`** (organisation `o-7sf5u7j5hd`). `staging` détruit, son répertoire conservé comme référentiel jetable |
| Nettoyage legacy AWS | `task-249` | **Fait** — 21 tables DynamoDB non suffixées supprimées ; il ne reste que 26 tables `-dev` + la table de lock du state |
| Sécurité users legacy | `task-222`, `task-224`, `task-253` | **Corrigé et déployé** — 2026-08-05 : `create_user`, `get_user`, `get_user_by_email`, `update_user` et `POST /api/v1/auth/verify-email` supprimés. 2026-08-12 (`task-224`) : `endpoints/users.py` et `DELETE /api/v1/users/{user_id}` supprimés au profit de `DELETE /api/account`, qui déduit le compte du token. 2026-08-13 (`task-253`) : le 404 de `DELETE /api/account` en dev est corrigé et un **startup guard** échoue au boot si une route critique n'est pas montée. Le code est déployé (dernier deploy backend vert : `30cf62c`, 2026-08-29T21:10). Les routes citées ici portaient encore le préfixe `/api/v1/`, supprimé depuis par `task-289`. **Reste** : le run E2E complet (Phase 4) |
| Dérive de dépendances Lambda | `6b22542` | **Corrigé le 2026-08-13, après incident** — l'API dev a répondu 500 sur toutes les routes pendant ~2 h 20 : le startup guard de `task-253` lisait mal `app.routes` sur FastAPI 0.13x, et les Dockerfiles résolvaient `fastapi>=0.104.0` au build (0.141.1 dans l'image contre 0.116.1 dans `uv.lock` et le venv local) — donc irreproductible localement. Les images installent désormais depuis `uv export --frozen`. **Clos le 2026-08-13 par `c05df88`** : la même bascule sur `uv.lock` a été étendue à `api.Dockerfile`, `worker.Dockerfile`, `test-orchestrator.Dockerfile`, `pr.yml` et `main.yml`. Rechute connue depuis : `f06bd62` a dû plafonner `pillow` sous 12.3 pour que l'image worker se construise à nouveau |
| Suppression/export de compte | `mobile/app/settings/delete-account.tsx`, `media_summarizer/core/services/account_deletion_service.py`, `task-224` | **Fait en code (2026-08-12)** — suppression de compte in-app (Account > Delete Account) branchée sur `DELETE /api/account`, qui purge DynamoDB + S3 + Algolia. Le bouton `Export Data` mort est retiré : l'accès et la portabilité passent par `privacy@mediasummarizer.com` sous un mois, documenté dans la privacy policy. Le bouton `Settings` mort reste à traiter hors `task-224` |
| Source + CI | `task-223`, `task-227`, `task-228` | **Fait** — `Main Branch Checks` et `Deploy Lambda Functions` verts sur les push récents (dernier : `30cf62c`, 2026-08-29). Reste hors P0 : `Mobile Build & Distribute` (cf. Phase 7), et 43 commits locaux non poussés (cf. § « État de vérité ») |

### Bloquants release immédiats

| Zone | Tâches | Statut |
|---|---|---|
| Re-run E2E AWS dev | Phase 4 | **Seul gate backend encore ouvert.** Dernier deploy vert : `30cf62c` (2026-08-29T21:10), mais **10 commits backend/infra locaux ne sont pas poussés** (cf. § « État de vérité »). Aucune preuve de `pytest -m e2e` complet depuis le 2026-06-12, alors que `/api/v1/` a disparu, que YouTube et Instagram sont passés en Apify-only et que le contrat média porte désormais cover et créateur. Pousser, puis lancer |
| Mobile dev builds | `task-161`, `task-162`, `task-163` | **Clos.** iOS : `task-161` est `Done`, sur une build du 2026-06-11 expirée le 2026-06-25 — le development client reste installé sur l'iPhone owner. Android : keystore (`task-162`), Client IDs et build en place, `task-163` est `Done` au 2026-09-02 |
| Google OAuth Android | `task-163`, `task-325` | **Clos le 2026-09-02 : le sign in with Google marche sur device, sur l'app installée depuis Play.** Deux clients Android coexistent — celui du 2026-08-13 sur le SHA-1 du keystore EAS (`task-162`, pour les APK posés à la main) et celui du 2026-09-02 sur le SHA-1 Play App Signing (pour tout binaire servi par Play, production incluse). Le flow lui-même a changé le 2026-09-01 (`task-325`) : Google refuse un custom URI scheme pour un client Android, donc l'app signe via **Credential Manager** (module Expo local, `serverClientId` = client Web) et ne lit aucun Client ID Android |
| Validation device non automatisable | `task-164`, `task-165` | À faire sur devices physiques : Apple Sign-In, Google sheet, Safari/Chrome share |
| Maestro V1 | `task-168`, `task-169`, `task-170`, `task-171`, `task-172` | **Plus un bloquant release** — CI en sommeil depuis le 2026-08-13 (`task-254`) le temps que l'UI soit figée ; 168/169/170/171 closes, 172 verrouillée. Cf. Phase 7, section « Maestro E2E CI — en sommeil depuis le 2026-08-13 » |
| Clôture Phase 5 | `task-166` | Mettre ce plan à jour une fois `task-163/164/165` terminées ; la couverture Maestro n'en est plus un prérequis |

### Bloquants pré-soumission stores

| Zone | Tâches | Statut |
|---|---|---|
| Branding app | `task-186` | Nom marketing final requis avant App Store Connect / Play Console |
| App icons | `task-180` | Remplacer les placeholders avant soumission |
| RevenueCat / IAP | **Plus un bloquant : la facturation tourne sur les deux stores.** `task-262`, `task-238` (Android) et `task-261` (iOS) sont `Done`. Ne reste que des métadonnées de soumission, portées par Phase 6 item 3 et Phase 10 : les 13 localisations ASC, la capture de vérification, et le nom marketing (`task-186`) | Prouvé par des achats réels sur les deux stores, pas par de la configuration. **iOS, 2026-09-02** : `INITIAL_PURCHASE` 15:42:41, `PRODUCT_CHANGE` 15:43:00, `RENEWAL` 15:43:00 pour un même utilisateur, et `subscriptions-dev` porte `com.secondbrainlabs.core.mix_monthly` / `platform: ios` / `tier: M` / `status: active` / `auto_renew_status: true`. Le `PRODUCT_CHANGE` n'était pas demandé et vaut cher : il valide le **changement de formule dans le groupe**, donc les niveaux 1/2/3 réglés en ASC. **Android, 2026-09-01** : cycle complet `INITIAL_PURCHASE` → 5 × `RENEWAL` → `CANCELLATION` → `EXPIRATION`, tier `L` résolu depuis l'entitlement. `revenucat_events-dev` contient 32 items, plus 0. Le `REVENUCAT_WEBHOOK_SECRET` est donc validé par l'usage et non plus par une sonde `401`. Les 3 entitlements de tier, l'offering `default` et les 3 packages existent, **chaque tier portant trois produits, un par store**. Côté iOS les trois drapeaux sont verts (`app_store_connect_api_key_configured`, vendor number, `subscription_key_configured`) ; les 3 produits gardent `subscription.duration: null`, ce qui ne gêne rien — voir Phase 6 item 4. Disposition détaillée : `docs/REVENUECAT_ENTITLEMENTS.md` |
| Domaine production | Phase 10 | Revérifié le 2026-08-21, inchangé : `secondbrainlabs.com` **résout** mais redirige en `301` vers `sbl.so` ; `api.secondbrainlabs.com` et `api.mediasummarizer.com` sont toujours en `NXDOMAIN`. Le profil EAS production pointe encore vers le second |
| Store/legal | Phase 10 | Les textes existent au dépôt (`docs/compliance/privacy-policy.md`, `terms-of-service.md`, `apple-app-privacy.md`, `google-play-data-safety.md`, `CHECKLIST.md`) mais **ne sont pas hébergés** : `secondbrainlabs.com/privacy` et `/terms` redirigent vers `sbl.so/...` qui répond **404** (revérifié le 2026-08-21). Liens in-app absents, listings/screenshots/review accounts à finaliser |

### Prérequis de lancement propres au compte prod (issus de `task-248`)

| Zone | Preuve | Statut |
|---|---|---|
| Credentials runtime prod | `task-252` (`dispatchable: false`, owner-only) | **Bloquant dur.** Le secret `media-summarizer-runtime-prod` contient **0 clé**, quand dev en porte 40 dont 37 vivantes (recomptées le 2026-08-21, `task-312`) : sans lui, aucune transcription, résumé, résolution, recherche, achat, ni même session utilisateur valide (`JWT_SECRET_KEY`) |
| Quota Lambda concurrence prod | demande `L-B99A9384`, 10 → 1000 | **PENDING** côté AWS. Un compte neuf plafonne à 10 exécutions concurrentes. Tant que c'est le cas, `envs/prod/main.tf` porte `api_reserved_concurrency = -1` ; **retirer cette ligne** puis plan + apply dès que le quota passe, sinon l'API se dispute 10 exécutions avec 14 workers |
| Réveil de prod | `envs/prod/main.tf` | Trois booléens à passer à `true` (`enable_alarms`, `enable_dashboard`, `enable_worker_polling`) — ~7,20 $/mois. Une prod qui sert de vrais utilisateurs sans alarmes est une faute ; la veille n'est valide qu'avant lancement |

### Décisions à prendre sans bloquer inutilement le premier build interne

| Zone | Tâches | Décision requise |
|---|---|---|
| ~~Architecture LLM production~~ | ~~`task-212`, `task-213`~~ | **Tranché** : `owner_decision: abandoned` sur le benchmark ; les deux tâches sont archivées. La recommandation (Azure OpenAI multi-région) n'est pas retenue pour V1 — le statu quo OpenAI direct est assumé. À rouvrir seulement si le chatbot entre au scope et que le TPM devient contraignant |
| ~~Langue YouTube Apify~~ | ~~`task-216`~~ | **Fait** (`Done`) — la langue du transcript Apify suit la préférence `reading_language` de l'utilisateur |
| Discord community/support | `task-118` | Utile pour soft launch, non bloquant code. |
| TikTok proxy résidentiel | `task-145` | V2, explicitement non bloquant V1. **Périmètre réduit à TikTok** : Instagram n'utilise plus yt-dlp depuis `task-310`, donc plus d'IP-block à contourner de ce côté. |
| Fenêtre TTL `processing_jobs` | `task-242` AC #3 | Implémenté en variable `processing_jobs_ttl_days`, défaut **90 j** (recommandation du benchmark). L'AC reste décochée jusqu'à ce que l'owner tranche entre 30/60/90 |

---

## 2. Comptes et abonnements à créer

| Service | Coût | Pourquoi | Statut |
|---|---|---|---|
| **GitHub** (compte + repo **public** depuis le 2026-08-13) | gratuit | Versioning, CI/CD, releases | Bon : source synchronisée, `Main Branch Checks` et `Deploy Lambda Functions` verts sur le HEAD, environnement `production` créé (branche `main` seule autorisée). Six secrets Actions (`AWS_DEPLOY_ROLE_ARN` + les cinq E2E). Manquent `EXPO_TOKEN`, Apple/App Store Connect et le service account Google Play. Branch protection **configurée** sur `main` depuis le 2026-08-13 (`task-257`, régime léger : force-push et suppression refusés, aucun required check) |
| **AWS** (2 comptes, Organizations `o-7sf5u7j5hd`) | usage-based | DynamoDB, S3, SQS, Lambda, EventBridge | Bon : dev dans `125313707865` (déployé sur le HEAD), prod dans `866874944541` (199 ressources, health `200`, **en veille** et secret vide). Aucune alarme active — par conception dans les deux environnements, pas par défaut de provisioning |
| **Apple Developer Program** | $99/an | Publication App Store, TestFlight, IAP sandbox | OK (payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés) |
| **Google Play Console** | $25 one-time | Publication Play Store, Internal Testing, IAP sandbox | Payé 2026-06-01 ; 4 des 7 portes d'éligibilité franchies au 2026-09-01 (appareil Android physique ✅, numéro de téléphone de contact ✅, identité ✅ aucune action due ni échéance, enregistrement du nom de package ✅ — fait par le premier upload d'AAB via Play App Signing, bien avant l'échéance du 2026-09-30). **App Play créée le 2026-08-31** (`com.secondbrainlabs.core`, déclarée *Sans frais*, le nom de package étant le seul champ définitif du formulaire) et **premier AAB uploadé sur la piste de test interne le 2026-09-01**. **Compte marchand créé le 2026-08-31**, IBAN déposé le même jour, **compte bancaire validé par micro-dépôt et passé en `Principal` le 2026-09-01**. **Informations fiscales : W-8BEN approuvé le 2026-09-01** (0 % sur les royalties de droits d'auteur au titre de l'article 12 §1 de la convention France–États-Unis, attestation d'absence d'activité aux États-Unis enregistrée, valide jusqu'au 31 décembre 2029). **Compte marchand donc complet sur ses trois volets.** Restent ouvertes : adresse publique, closed testing (12 testeurs / 14 jours continus + review ≤7 jours = ~21 jours de plancher calendaire) — runbook `task-260`, détail en Phase 2.2 |
| **Expo / EAS** | gratuit (free tier) | Builds iOS/Android | Partiel : compte/projet OK ; ancienne build iOS expirée. **Deux AAB Android produits le 2026-09-01** (profil `internal`, keystore géré par EAS, API dev) : `versionCode` 4, puis `versionCode` 5 une fois la clé RevenueCat corrigée dans les environnements EAS — le 4 était inexploitable pour la facturation, `EXPO_PUBLIC_*` étant inliné à la compilation. C'est le 5 qui est sur la piste de test interne. Il a fallu corriger un défaut qui rendait *tout* build Release Android impossible, `production` compris : les fichiers `mobile/locales/*.json` étaient plats, donc Expo recopiait les trois clés iOS dans les ressources Android où elles n'existent pas dans la locale par défaut, et `lintVitalRelease` échouait sur 33 erreurs `ExtraTranslation`. Les fichiers sont désormais scindés en sections `ios`/`android`. Les trois environnements EAS **sont peuplés** et portent la vraie clé `goog_` depuis le 2026-09-01. **Un build iOS de distribution store existe aussi** : `790af106`, 1.0.0 (2), commit `ca9cadb`, terminé le 2026-09-01, poussé sur ASC (`6778072060`) par EAS Submit le 2026-09-02 et installé par un beta testeur en TestFlight. Contrairement à ce que ce tableau affirmait, **il porte bien les deux clés RevenueCat et l'API dev** — vérifié le 2026-09-02 en dézippant l'IPA : `Payload/*.app/EXConstants.bundle/app.config` donne `apiBaseUrl: https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`, `revenueCatAppleKey: appl_…`, `revenueCatGoogleKey: goog_…`. `mobile/eas.json` n'en déclare aucune, mais le profil résout les variables de l'environnement EAS, et les valeurs partent dans le manifeste (`extra` de `app.config.ts`), pas dans le bundle JS — les chercher dans `main.jsbundle` ne prouve rien, c'est `EXConstants.bundle/app.config` qu'il faut lire. La CI Maestro injecte la clé Test Store par l'environnement |
| **RevenueCat** | gratuit < $10k MTR | Cross-platform IAP backend | Partiel : projet `proj879a771a` avec 3 entitlements de tier, offering courant et 3 packages tiers (`task-262`, 2026-08-13), désormais servis par les produits Test Store **et** les 3 produits App Store de l'app iOS (`task-261`, 2026-08-13). L'app Play (`appb253c0f75a`) existe depuis le 2026-08-20 et porte ses **3 produits depuis le 2026-09-01**, rattachés aux mêmes entitlements et packages, avec des identifiants de la forme `subscriptionId:basePlanId`. Ses **identifiants de compte de service sont validés depuis le 2026-09-01** (`Valid credentials`) — il ne manquait que l'upload d'un AAB, les permissions et les API Google Cloud étant correctes depuis le départ, ce qu'a prouvé le panneau *Debug error* (2 vérifications sur 3 déjà vertes). **Complet au 2026-09-02** : la clé App Store Connect est en place côté iOS, et un achat sandbox a tourné de bout en bout sur chacun des deux stores (Android le 2026-09-01, iOS le 2026-09-02, avec un changement de formule en prime). Le `REVENUCAT_WEBHOOK_SECRET` est validé par 32 événements reçus, plus par une sonde. Disposition détaillée : `docs/REVENUECAT_ENTITLEMENTS.md` |
| **Google Cloud Console** (OAuth) | gratuit | Sign in with Google : OAuth Client IDs (iOS, Android, Web) + écran de consentement OAuth | Partiel : projet + consent screen Test + OAuth Web backend + OAuth iOS OK ; OAuth Android et publication Production restent à faire |
| **OpenAI** | usage-based | Génération artifacts (summary/notes/flashcards) | OK (compte créé, clé en local dans `.env`) |
| **Deepgram** | usage-based | Transcription audio | OK (compte créé, clé en local dans `.env`) |
| **Algolia** | gratuit < 10k records | Search lexical | OK (App ID + Admin API key + index name en local dans `.env`) |
| **PodcastIndex.org** | gratuit | Resolver podcasts | OK (compte créé, clé+secret en local dans `.env`) |
| **Apify** | usage-based / API token | Resolver Instagram (Reel + Post) + fallback YouTube/TikTok selon source | OK (tokens/actor IDs en local dans `.env`) |
| **LlamaParse** (LlamaIndex Cloud) | gratuit free tier (1000 pages/jour) | Resolver documents primaire (PDF/DOCX/PPTX) | OK (compte créé, clé en local dans `.env`) |
| **Unstructured.io** | 15 000 pages gratuites au début, puis usage-based | Resolver documents fallback | OK (compte créé, clé en local dans `.env`) |
| **X (Developer Platform)** | Free tier OK pour V1 | Lecture API X | OK (compte créé, bearer token en local dans `.env`) |

---

## 3. Variables d'environnement / Secrets à renseigner

Architecture cible : tous les secrets sont consolidés dans une entrée
**AWS Secrets Manager** par environnement
(`media-summarizer-runtime-<env>`) provisionnée par
`infrastructure/terraform/secrets.tf`. Les Lambda functions chargent ce secret
au cold start et injectent chaque clé du JSON comme variable d'environnement —
le code lit toujours via `os.getenv(...)` sans changement.

**État réel au 2026-08-13** : l'isolation Terraform est faite (`task-237`) et le
secret prod **existe** en tant que coquille dans le compte `866874944541`, mais
il contient **0 clé** — c'est l'objet de `task-252` (owner uniquement,
`dispatchable: false`). Dans le compte dev, `aws secretsmanager list-secrets` ne
renvoie que `media-summarizer-runtime-dev` (**40 clés, dont 37 vivantes** —
recomptées clé par clé le 2026-08-21 par `task-312`, qui a corrigé le « 37 »
répété jusque-là ici et dans `docs/DEVBOX_SETUP.md`) et
`media-summarizer-devbox-mobile-env`. `media-summarizer-runtime-staging` a été
supprimé sans fenêtre de récupération par `task-248`, donc son nom est libre si un
staging jetable doit être remonté un jour.

Bootstrap : `terraform -chdir=infrastructure/terraform/envs/<env> apply`. Il n'y a
plus de `terraform.tfvars` à copier (task-237 : un root module par environnement,
valeurs en littéraux dans `envs/<env>/main.tf`) ni de `secret_payload` à remplir
(task-221 §7.3 : un `secret_string` inline fuiterait en clair dans le state).
Terraform ne crée que la coquille vide du secret ; les valeurs y sont poussées
hors-bande par `aws secretsmanager put-secret-value`. Voir
`infrastructure/terraform/README.md`.

Local : **un seul fichier `.env`** à la racine, chargé automatiquement par
`python-dotenv` depuis `media_summarizer/__init__.py` (override=False, donc les
vraies variables d'env priment). Modèle complet : `.env.example` (20 sections
numérotées). Les anciens `.env.dev` et `.env.prod` sont **legacy et gitignorés**
— ne pas les utiliser ni les recréer.

### 3.1 AWS infra

```bash
AWS_DEFAULT_REGION=eu-west-3
AWS_ACCESS_KEY_ID=...              # clé IAM dédiée backend (production hors Lambda)
AWS_SECRET_ACCESS_KEY=...
ARCHIVE_BUCKET=...
AUDIO_BUCKET=...
DOCUMENT_BUCKET=...
FLASHCARDS_BUCKET=...
# Autres buckets/tables/queues : voir .env.example sections 3-5 et terraform/
```

### 3.2 Auth

```bash
JWT_SECRET_KEY=...                     # 32+ bytes random, généré pour la prod
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=365     # fenêtre glissante, reposée à chaque /refresh (task-294)
# Aucune variable COOKIE_* : le refresh token voyage dans le corps JSON de
# register/login/refresh (task-293). Il ne subsiste plus qu'une clé COOKIE_* morte
# dans le secret runtime (COOKIE_DOMAIN) — les trois autres ont été retirées ;
# aucun code ne la lit. Détail dans docs/DEVBOX_SETUP.md § 6.

# Google OAuth (Sign in with Google)
GOOGLE_CLIENT_ID=...                   # Web client ID — audience du flow web /google/callback uniquement
GOOGLE_CLIENT_SECRET=...               # Requis pour le flow web /google/callback
GOOGLE_REDIRECT_URI=https://api.<your-domain>/api/auth/google/callback
GOOGLE_NATIVE_AUDIENCE_IOS=...         # Client ID iOS — `aud` des id_tokens obtenus sur iOS
GOOGLE_NATIVE_AUDIENCE_ANDROID=...     # Client ID Android — `aud` des id_tokens obtenus sur Android

# Apple OAuth (Sign in with Apple)
APPLE_TEAM_ID=...                      # Visible dans Apple Developer Account → Membership
APPLE_KEY_ID=...                       # Du Sign in with Apple Key généré dans Apple Developer
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
APPLE_CLIENT_ID=...                    # Service ID (ex: com.secondbrainlabs.core.signinwithapple)
APPLE_REDIRECT_URI=https://api.<your-domain>/api/auth/apple/callback
```

Côté mobile (`mobile/.env` ou EAS secrets) :

```bash
# Google OAuth client IDs créés dans Google Cloud Console
# Naming attendu par mobile/app.config.ts : suffixe _<PLATFORM>, pas infixe.
EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB=...    # même valeur que GOOGLE_CLIENT_ID côté backend
EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS=...
# Pas de _ANDROID : supprimée par task-325, Credential Manager ne prend pas d'ID
# de client Android (voir ci-dessous).
```

**Quel client émet l'id_token mobile — une réponse par plateforme depuis
`task-325`.**

- **iOS** : `expo-auth-session` fait un flow authorization code + PKCE contre le
  client **iOS**, puis échange le code contre ce même client. L'`aud` de l'id_token
  est donc le client iOS, d'où `GOOGLE_NATIVE_AUDIENCE_IOS` côté backend (task-298).
- **Android** : plus de flow navigateur du tout. Google refuse un custom URI scheme
  comme `redirect_uri` pour un client Android (`Erreur 400 : invalid_request`,
  « Custom URI scheme is not enabled for your Android client »), sans réglage pour le
  réactiver — le flow était donc mort-né. L'app passe par **Credential Manager**
  (module Expo local `mobile/modules/google-credential-manager`,
  `GetSignInWithGoogleOption`), qui prend le client **Web** comme `serverClientId` :
  l'`aud` de l'id_token est le client Web, que `/auth/google/native` accepte déjà
  puisque c'est `GOOGLE_CLIENT_ID`. `GOOGLE_NATIVE_AUDIENCE_ANDROID` n'est donc plus
  exercée par aucun flow.
- Les clients OAuth **Android** restent nécessaires côté Google : Credential Manager
  vérifie l'appelant sur son nom de package **et** le SHA-1 du certificat qui signe
  le binaire installé. Il y en a donc **deux**, sur le même package : SHA-1 du
  keystore EAS (APK posés à la main) et SHA-1 Play App Signing (tout binaire servi
  par Play). Le second a été déclaré le 2026-09-02 et c'est ce qui a débloqué le
  sign-in sur device. Voir Phase 2, item 7 (Google Auth Platform → Clients).

`mobile/.env` est gitignored. Contrairement à l'état noté au 2026-07-31, les trois
environnements EAS `development`, `preview` et `production` **contiennent bien**
des variables `EXPO_PUBLIC_*` (vérifié le 2026-08-13 via `eas env:list`) :
`development` en porte six depuis l'ajout du Client ID Android. Les deux
mécanismes coexistent — `EXPO_PUBLIC_API_BASE_URL` n'existe **que** dans le bloc
`env` inline de `mobile/eas.json`, pas côté serveur.

### 3.3 LLM / Transcription

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-nano-2026-03-17  # défaut V1 ; overrides per-artifact dispo dans .env.example
DEEPGRAM_API_KEY=...
DEEPGRAM_MODEL=nova-3
```

### 3.4 Search

```bash
ALGOLIA_APP_ID=...
ALGOLIA_API_KEY=...                  # admin key (côté backend)
```

Le nom de l'index n'est pas configurable : il vaut `media_items_{ENVIRONMENT}`,
calculé par `utils/algolia_client.py`. La séparation entre environnements est donc
structurelle, pas une variable à renseigner. Il n'y a pas non plus de search-only
key : la recherche passe par le backend, aucune clé Algolia n'atteint le client
(task-312).

### 3.5 Sources d'ingestion

```bash
# Podcasts
PODCASTINDEXORG_API_KEY=...
PODCASTINDEXORG_API_SECRET=...

# X (Twitter)
X_API_BEARER_TOKEN=...               # OAuth 2.0 bearer

# TikTok — pas de clé externe, utilise le natif
TIKTOK_RATE_LIMIT_PER_HOUR=200       # par défaut, à ajuster

# Instagram (via Apify actors)
APIFY_INSTAGRAM_API_TOKEN=...
APIFY_TIMEOUT_SECONDS=60

# Documents — LlamaParse primaire + Unstructured fallback
LLAMAPARSE_API_KEY=...                 # LlamaIndex Cloud
LLAMAPARSE_TIMEOUT_SECONDS=120
LLAMAPARSE_POLL_INTERVAL=2
LLAMAPARSE_MAX_POLLS=60
UNSTRUCTURED_API_KEY=...
UNSTRUCTURED_API_URL=https://api.unstructuredapp.io
UNSTRUCTURED_TIMEOUT_SECONDS=120
```

### 3.6 RevenueCat (billing)

```bash
REVENUCAT_API_KEY=sk_...             # secret API key (backend)
REVENUCAT_PROJECT_ID=...
REVENUCAT_WEBHOOK_SECRET=...         # valeur au choix de l'owner, saisie dans le dashboard RC
```

`REVENUCAT_WEBHOOK_SECRET` n'est pas fourni par RevenueCat : c'est un secret
partagé que l'owner choisit et colle dans RevenueCat → Integrations → Webhooks
(champ Authorization header), puis reporte à l'identique dans `.env` et dans
`media-summarizer-runtime-<env>`. Il n'est pas exposé par l'API v2
(`/v2/projects/<id>/webhooks` → `404`), donc c'est une étape nécessairement
manuelle. Il **est renseigné** au 2026-08-13, à l'identique dans `.env` et dans
`media-summarizer-runtime-dev` : voir Phase 6. Le côté dashboard RevenueCat n'est
vérifiable que par l'owner, l'API ne le lisant pas.

Côté mobile (`mobile/.env` ou EAS secrets) — naming attendu par `mobile/app.config.ts` :

```bash
EXPO_PUBLIC_REVENUCAT_APPLE_KEY=appl_...    # public key iOS (RevenueCat dashboard → Apps → ton app iOS)
EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY=goog_...   # public key Android (idem, app Play Store)
```

Ces deux clés sont **publiques par conception** : elles sont inlinées dans le
bundle JS (préfixe `EXPO_PUBLIC_`), donc extractibles de n'importe quel binaire,
et n'autorisent que les opérations client (lire l'offre, acheter, restaurer).
Elles n'ont rien à faire dans `media-summarizer-runtime-<env>` : le backend ne
lit que les trois variables serveur ci-dessus, dont la secret key `sk_`. Les deux
ensembles sont disjoints, et rien n'est à synchroniser de l'un vers l'autre.

Les deux sont renseignées dans `mobile/.env` au 2026-08-20 — la clé Android
depuis la création de l'app Play Store dans le projet RevenueCat, qui émet une
clé publique à ce moment-là indépendamment de la validation des service
credentials.

### 3.7 Mobile (Expo / EAS)

```bash
EXPO_PUBLIC_API_BASE_URL=https://api.<your-domain>
```

---

## 4. Phases d'exécution (ordre logique)

### Phase 1 — Code & repo (jour 1)

1. ~~Créer un repo GitHub.~~ **Fait** : `MedlockM/second-brain-app`, branche par défaut `main`. Historique purgé des secrets, `.venv-311/` et scratchpads ; `.gitignore` durci. Premier push : 2026-05-27 (HEAD `eb22f0e`, 174 commits, 553 fichiers). **Le repo est passé public** : vérifié le 2026-08-13 (`visibility: PUBLIC`). C'est ce qui motive `task-255` et `de3ac86` (purge de l'email de login et de l'identité de compte des fichiers suivis) — désormais, tout identifiant écrit dans un fichier suivi est public.
2. **GitHub Actions versionnés** : `.github/workflows/pr.yml`, `main.yml`, `deploy-lambda.yml`, `deploy-lambda-env.yml`, `mobile-build-distribute.yml`, `mobile-store-promote.yml`, `mobile-e2e-maestro.yml`.
3. ⚠️ **Source désynchronisée au 2026-09-02** : les 5 fichiers du fix
   `uv.lock` (`pr.yml`, `main.yml`, `api.Dockerfile`, `worker.Dockerfile`,
   `test-orchestrator.Dockerfile`) sont commités depuis `c05df88` — ce point est
   clos. Mais `main` local porte **43 commits d'avance non poussés**, dont 10
   touchent le backend ou l'infra : `origin/main` est sur `30cf62c` et c'est lui
   qui est déployé. Détail des 10 dans § « État de vérité ». À pousser.
4. ✅ **CI verte** (`task-223`, `task-227`, `task-228`) :
   - `Main Branch Checks` **success** sur tous les push récents, dont
     `30cf62c` (2026-08-29) ;
   - `ruff check .` en local → `All checks passed!` ;
   - la config ESLint manquante a été ajoutée et les 20 violations react-hooks
     corrigées, `rules` remises en `error` ;
   - l'interpréteur du venv local est réparé, donc Mypy est rejouable en local
     autant qu'en CI.
5. **GitHub Actions secrets** : six configurés — `AWS_DEPLOY_ROLE_ARN`,
   `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`, `E2E_SEARCH_TEST_TERM`,
   `E2E_REVENUECAT_TEST_KEY`, `E2E_REVENUECAT_APPLE_KEY`. Manquent toujours
   `EXPO_TOKEN` (c'est ce qui fait échouer `Mobile Build & Distribute`),
   Apple/App Store Connect et le service account Google Play. Un environnement
   GitHub `production` existe (créé par `task-248`), restreint à `main`, avec son
   propre `AWS_DEPLOY_ROLE_ARN`.
6. **Branch protection** : **configurée** le 2026-08-13 par `task-257`, en régime
   léger. `branches/main/protection` → `200`, avec `allow_force_pushes: false`,
   `allow_deletions: false`, `required_linear_history: false`,
   `enforce_admins: false`, et **ni** required status checks **ni** required
   pull-request reviews — le flow reste un merge local suivi d'un push direct sur
   `main`, que des required checks rejetteraient. Aucun ruleset (`rulesets` →
   `[]`). Rollback : `gh api -X DELETE repos/:owner/:repo/branches/main/protection`.
7. **Reste à faire** : pousser les 43 commits locaux sur `origin/main`, et
   renseigner `EXPO_TOKEN` (point 5).

### Phase 2 — Comptes externes (jour 1-2)

1. ~~Apple Developer Program.~~ **Fait** : payé 2026-06-01, validé par Apple ; App ID + Sign in with Apple provisionnés.
2. Google Play Console : payé 2026-06-01. **Type de compte : PERSONNEL**
   (constaté le 2026-08-19, reconfirmé par l'owner le 2026-08-31 — fait établi, ne
   plus le redemander). **Sept portes d'éligibilité à franchir
   par l'owner dans la Play Console** — runbook pas-à-pas dans `task-260`,
   qui est aussi l'endroit où consigner les résultats. Les $25 ne donnent qu'un
   compte : ils ne rendent pas le compte apte à publier. Deux portes sont
   franchies au 2026-08-31 ; sur les cinq restantes, la septième devrait se solder
   sans action.

   Ce que « personnel » implique mécaniquement, et qui n'a donc plus à être
   rediscuté : l'adresse développeur affichée publiquement sur la fiche Play est
   une **adresse personnelle** (porte 5), et l'exigence de **closed testing
   s'applique** (porte 6) — le compte datant du 2026-06-01, il tombe après le
   seuil de novembre 2023. Seuls les *paramètres* de ce closed testing (nombre de
   testeurs, durée) restent à lire dans la Play Console.
   1. **Accès à un appareil Android physique — ✅ confirmé le 2026-08-31.**
      Play Console → Accueil → carte « Terminer la configuration de votre compte
      de développeur ». La confirmation passe par l'app mobile Play Console
      installée sur un appareil Android réel et connectée au compte développeur ;
      un émulateur ne convient pas. Effet constaté immédiatement après : le
      bouton *Créer une application* de la Play Console est passé d'inactif à
      actif.
   2. **Numéro de téléphone de contact — ✅ validé le 2026-08-31**, dans la même
      carte de configuration, une fois la porte ci-dessus franchie (elle en était
      le prérequis). Revu sur pièce le même jour sur *Compte de développeur →
      Coordonnées* : téléphone et adresse e-mail de contact portent tous deux la
      pastille « vérifié ». Relevé au même endroit : le *Nom du développeur* est
      déjà `Second Brain Labs` (l'entité légale), ce qui est indépendant du nom
      marketing de l'app que `task-186` doit encore trancher.
   3. **Vérification d'identité du compte développeur — ✅ aucune action due,
      aucune échéance, relevé le 2026-08-31.** Chemin réel : *Validation des
      développeurs Android* → onglet **Identité** (et non « Paramètres → Détails du
      compte développeur », qui n'agrège plus cette information). Cet onglet est
      purement informatif : il reflète le nom légal et l'adresse déjà fournis, sans
      statut de vérification, sans « Action requise », **sans date limite** et sans
      bouton d'action. Le risque de suspension pour dépassement d'échéance — que
      Google applique depuis 2023 — ne pèse donc pas sur ce compte. Nuance : l'écran
      n'affiche pas « Vérifié » non plus, et Google recommande d'ajouter un **site
      web** au compte (« l'ajout d'un site nous aide à valider votre compte »), ce
      qui reste à faire quand le domaine servant la politique de confidentialité de
      `task-43` existera.
   4. **Profil de paiement Google Payments** : obligatoire dès qu'il y a des
      achats intégrés — donc bloquant pour les abonnements de `task-238` et pour
      RevenueCat. Il porte la vérification d'identité du bénéficiaire, les
      informations fiscales et les coordonnées bancaires. Sans lui, les
      abonnements ne sont pas vendables même si l'app est publiée.
      **Tranché le 2026-08-31 : le profil payeur existe et est vérifié, le compte
      marchand n'existe pas.** Les deux objets sont distincts. Le *profil de paiement
      Google* (le payeur, celui qui a réglé les $25) a été ouvert sur
      `payments.google.com/gp/w/home/settings` : `TYPE DE COMPTE : Particulier`,
      **nom validé le 2026-06-02**, **adresse validée le 2026-06-02**. Mais l'écran
      **ne comporte ni section *Informations fiscales*, ni section *Coordonnées
      bancaires*, ni aucune surface de virement** — elles ne sont pas « en attente »,
      elles n'existent pas. Le **compte marchand Google Play** (l'encaisseur), seul
      prérequis dur de `task-238`, **reste donc entièrement à créer**. Le menu Play
      Console n'a aucune entrée « Paiements » parce que le profil payeur vit hors de
      la console, pas parce que rien n'existe.
      **Ordonnancement, corrigé sur la doc Google le 2026-08-31 :** il avait d'abord
      été écrit ici que le compte marchand ne se créait qu'après la création de
      l'app. C'est **faux** — c'était une inférence tirée de l'absence d'entrée
      *Paiements* dans le menu. Play Console Help `answer/7161426` ne conditionne la
      création du profil à **aucune app** : c'est une tâche de compte, à
      **Play Console → Paramètres → Profil de paiement → *Créer un profil de
      paiement***. Il n'existe pas d'entrée *Paiements* de premier niveau, d'où
      l'impression qu'elle manquait. **Cette porte est donc à lancer immédiatement,
      en parallèle du build** — c'est le seul poste administratif à délai Google qui
      ne dépende de rien. Contraintes documentées : l'adresse ne peut pas être une
      boîte postale, le **pays est verrouillé après soumission**, et le compte
      bancaire de versement devra être enregistré dans ce même pays. Les sous-étapes
      bancaires et fiscales ne sont pas documentées publiquement : à relever sur
      pièce, avec leur délai, au moment de les faire.
      **Écran ouvert le 2026-08-31 : c'est un sélecteur, pas une création.** La page
      *Paramètres → Profil de paiement* propose de choisir le profil associé au
      compte et présente **deux profils `Particulier` préexistants** — l'un de
      portée large (YouTube, Cloud, Play, Google Pay), l'autre **dédié à Play**, qui
      est celui dont le nom et l'adresse sont validés depuis le 2026-06-02 — plus une
      option de création. **Aucun n'est coché.** L'action est de **cocher le profil
      dédié à Play**, et surtout **pas** de créer un troisième profil en doublon. Le
      rattachement est difficile à défaire une fois des transactions passées.
      **✅ Compte marchand créé le 2026-08-31.** Le profil public de marchand a été
      soumis et la page affiche désormais l'écran de l'encaisseur (`Google Play Apps`,
      revenus 0,00 €, seuil de versement 1,00 €, paiement mensuel). L'**IBAN a été
      déposé le 2026-08-31** et Google a lancé une **vérification par micro-dépôt** :
      un montant sera viré sur le compte dans les jours suivants, à saisir dans la
      console pour valider le mode de versement. Reste ouvert : les **informations
      fiscales**, dont le statut n'a pas encore été relevé (à chercher sous *Gérer les
      paramètres*). Rien de tout cela ne bloque la création de l'app Play ni sa
      checklist de configuration.
      Deux champs à ne pas rater lors de la saisie, la doc étant formelle
      (`paymentscenter/answer/7162811`) : le **pays du profil et le merchant ID sont
      définitifs** (seul remède en cas d'erreur : créer un nouveau profil et y
      transférer les apps), et le **nom sur les relevés de carte est limité à 14
      caractères** car Google y préfixe `GOOGLE*`. Tout le reste des informations
      publiques — nom d'entreprise, nom de marque, e-mail de support client, site web —
      est **modifiable après coup**.
   5. **Adresse développeur publique** : depuis 2023, l'email et l'adresse
      physique du développeur s'affichent sur la fiche Play. Le compte étant
      **personnel**, cela signifie ici publier une adresse personnelle — ce n'est
      pas une hypothèse, c'est le cas par défaut à trancher. **Deux constats du
      2026-08-31 qui réduisent le problème.** D'abord, le bloc *Informations
      affichées dans votre profil de développeur* ne liste aujourd'hui **que
      l'e-mail développeur**, aucune adresse physique — l'affichage de l'adresse
      étant lié aux apps à achats intégrés, la vérification devra être refaite après
      création du compte marchand. Ensuite, l'échappatoire « passer en compte
      organisation » est **indisponible** : le lien *Modifier le type de compte* est
      grisé dans la console, donc pas de D-U-N-S à engager et une branche de moins
      au calendrier. Restent deux options : accepter, ou domicilier.
   6. **Closed testing préalable — c'est du délai calendaire, et il s'applique.**
      Google impose aux comptes développeur *personnels* créés après novembre 2023
      un test fermé d'environ 12 testeurs pendant 14 jours continus avant de
      pouvoir demander l'accès à la production. Le compte est personnel et date du
      2026-06-01 : les deux conditions sont réunies, **l'exigence s'applique**.
      Elle ne s'achète pas et ne se parallélise pas.
      **Paramètres établis sur la doc Google le 2026-08-31 (`answer/14151465`) :**
      **12 testeurs minimum inscrits en continu pendant 14 jours consécutifs** — la
      continuité est stricte, un désabonnement remet le compteur de la personne à
      zéro. Il faut donc 12 personnes qui restent inscrites 14 jours, pas 12
      inscriptions cumulées. La configuration de l'app doit être **terminée** avant
      de pouvoir démarrer le test fermé. La demande d'accès à la production se fait
      ensuite depuis *Tableau de bord → Demander l'accès à la production*, et sa
      review prend « **seven days or less**, but can occasionally take longer ».
      **Plancher calendaire : ~21 jours** (14 + jusqu'à 7) à compter du démarrage
      effectif du test. Un refus est possible si moins de 12 testeurs inscrits ou
      engagement jugé insuffisant, auquel cas il faut prolonger — prévoir de la
      marge. Jusqu'à l'approbation, les pages *Production* et *Pré-enregistrement*
      restent **désactivées**.
      **Voie rapide à ne pas confondre avec celle-ci :** le *test interne* peut
      démarrer **avant** que la configuration de l'app soit terminée
      (`answer/9845334`). C'est par lui qu'on fait exister le nom de package dont
      `task-238` AC#2 a besoin, sans attendre le test fermé. Même doc : « once you
      upload an artifact, the package name for that app is fixed and cannot be
      changed ».
      Reste à consigner : la **date de démarrage effective** du test fermé.
   7. **Enregistrement des noms de packages — *Android developer verification*,
      découvert le 2026-08-31, très probablement sans action de notre part.**
      Play Console → *Validation des développeurs Android* → onglet *Noms des
      packages*. Programme annoncé par Google le 15 juillet 2026 ; le bandeau
      console menace de supprimer de Google Play, **au 30 septembre 2026**, toute
      app non enregistrée. Vérifié à la source le 2026-08-31 : **Play App Signing
      déclenche l'enregistrement automatique** (Google annonce 99 % des apps
      couvertes), et notre app Play l'utilisera. L'enregistrement manuel ne
      concerne que les apps distribuées exclusivement hors Play et les clés
      auto-gérées. L'échéance du 30 septembre 2026 est en outre **régionale**
      (Brésil, Indonésie, Singapour, Thaïlande, magasins participants, appareils
      certifiés Android 7+) — le déploiement mondial est annoncé pour **2027**.
      `adb install` est explicitement exempté, donc les builds de dev sur device ne
      sont pas concernés ; les builds EAS `distribution: internal` échappent à la
      phase de septembre 2026 mais pas au rollout 2027. **À revérifier en Phase 10**
      une fois l'app créée : elle doit apparaître *Registered* dans cet onglet.
      Détail et sources dans `task-260`, étape 1 bis.
3. ~~AWS account + IAM admin user + facturation alarms.~~ **Fait** : compte AWS, IAM admin `second-brain-app-admin` et billing alarm $50/mois configurés.
4. Expo / EAS account + lien vers le repo : **compte/projet faits**. Une build
   iOS development a terminé le 2026-06-11 sur `8c63765`, mais elle a expiré le
   2026-06-25 et ne représente plus le code courant. Aucune build Android
   n'existe. Aucun env EAS development/preview/production n'est configuré.
5. RevenueCat account + projet + clés backend/mobile : **partiellement fait**.
   `REVENUCAT_WEBHOOK_SECRET` **est renseigné** au 2026-08-13, à l'identique en
   local et dans le secret dev, et le Lambda déployé le charge (sonde `401`).
   Les 3 entitlements de tier, l'offering courant et les 3 packages existent ;
   l'app iOS porte ses 3 produits App Store rattachés, mais sans clé App Store
   Connect, et il n'y a pas d'app Play. Restent à prouver : les abonnements côté
   ASC, la clé ASC, l'app Play, et les tests sandbox.
   Détail et ordre d'exécution en Phase 6.
6. Comptes API tiers : les clés locales documentées restent présentes pour
   **OpenAI**, **Deepgram**, **PodcastIndex.org**, **X Developer Platform**,
   **Apify**, **LlamaParse**, **Unstructured.io** et **Algolia**. Google OAuth
   backend/iOS et Apple OAuth sont renseignés localement. Le **3ᵉ Client ID
   Google (Android)** est provisionné depuis le 2026-08-13 (`task-163`).
   Restent à provisionner/valider : publication du consent screen Google en
   Production, RevenueCat webhook + IAP et secrets runtime staging/prod.
   `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` porte la vraie clé `goog_` dans les trois
   environnements EAS depuis le 2026-09-01 (`task-238`).
7. **Google Cloud Console** (console.cloud.google.com) :
   - ~~Créer un projet~~ **Fait** : projet `media-summarizer` créé. Le nom du projet est un identifiant interne, peu visible aux users.
   - ~~**APIs & Services → OAuth consent screen (Audience)**~~ **Fait** : Type **External**, scopes `openid`, `email`, `profile` uniquement.
   - ~~**OAuth consent screen → Branding**~~ **Fait** : Branding `Second Brain`, support email, developer contact email.
   - ~~**Audience Test + utilisateur test**~~ **Fait** : mode Test configuré avec utilisateur test. La publication en `Production` est faite plus tard, en Phase 10.
   - **Google Auth Platform → Clients → 3 OAuth Client IDs** (l'ancien chemin
     « APIs & Services → Credentials » a été remplacé par cette section ; URL
     directe `console.cloud.google.com/auth/clients`) :
     - ~~**Web**~~ **Fait** : utilisé par le backend pour vérifier l'`aud` du id_token, et réutilisé côté mobile via `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
     - ~~**iOS**~~ **Fait** : avec bundle id du `mobile/app.config.ts` → `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`.
     - ~~**Android**~~ **Fait le 2026-08-13** (`task-163`) : créé avec
       `package=com.secondbrainlabs.core` et le SHA-1 du keystore EAS produit
       par `task-162`, sans qu'aucun build Android n'ait été nécessaire.
       À noter : ce client sert uniquement à ce que Google vérifie la signature
       de l'APK. L'`aud` du id_token reste le client **Web** — c'est bien lui
       que le backend vérifie, et depuis `task-325` c'est aussi le
       `serverClientId` que l'app passe à Credential Manager. L'ID du client
       Android n'entre plus dans l'app : `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` a
       été supprimée de `mobile/eas.json`, `mobile/.env.example` et
       `app.config.ts`, et la variable côté environnement EAS `development` peut
       être supprimée.
     - ~~**Deuxième client Android sur le SHA-1 Play App Signing**~~ **Fait le
       2026-09-02** : le client a été déclaré sur l'empreinte de Play (même
       `package=com.secondbrainlabs.core`, autre SHA-1), et **le sign in with
       Google fonctionne sur l'app Android installée depuis Play** — validé sur
       device par l'owner. C'était bien la cause : Play re-signe l'artefact
       servi, donc l'empreinte que Credential Manager voit sur le téléphone
       n'est pas celle du keystore d'upload EAS.
       Le premier client (SHA-1 keystore EAS, `task-163`) **reste en place** et
       n'est pas redondant : il couvre les APK installés à la main
       (`eas build --profile development|preview`), que Play ne re-signe pas.
       Deux clients Android coexistent donc, tous deux sur le même package, et
       aucun des deux n'entre dans le bundle — l'app ne connaît que le client
       Web (`serverClientId`). Rien à rejouer en Phase 10 : le certificat Play
       App Signing est le même pour la piste interne, le closed testing et la
       production, donc ce client vaut aussi pour le binaire de production.
       - Chemins utilisés — lire le SHA-1 : Play Console → *Test et publication*
         → *Intégrité de l'application* → onglet *Signature de l'application* →
         *Certificat de clé de signature d'application*. Le déclarer : Google
         Cloud Console → *API et services* → *Identifiants* → *Créer des
         identifiants* → *ID client OAuth* → type *Android*.
8. **Apple Developer Portal** (developer.apple.com → Certificates, Identifiers & Profiles) :
   - **Bundle ID figé : `com.secondbrainlabs.core`** (décidé 2026-06-07,
     propagé dans `mobile/app.config.ts`, `mobile/ios-share-extension/`, les
     projets natifs générés et les product IDs RevenueCat). Le plugin custom
     `mobile/plugins/withShareExtension.js` a été supprimé par `task-188` au
     profit du plugin officiel `expo-share-intent`.
   - ~~**Identifiers → App IDs**~~ **Fait** : App ID `com.secondbrainlabs.core` créé, capability "Sign in with Apple" activée.
   - ~~**Identifiers → Services IDs**~~ **Fait** : Service ID `com.secondbrainlabs.core.signinwithapple` créé et return URL backend configurée.
   - ~~**Keys → Sign in with Apple Key**~~ **Fait** : clé `.p8` générée, `APPLE_PRIVATE_KEY`, `APPLE_KEY_ID`, `APPLE_TEAM_ID` renseignés.
   - ~~**Membership**~~ **Fait** : Team ID récupéré.

### Phase 3 — Infrastructure AWS (jour 2-3) — **DEV SEULEMENT : DONE 2026-06-08**

Étapes exécutées (dev) :

1. ✅ `infrastructure/terraform/terraform.tfvars` généré depuis `.env` racine (29 clés `secret_payload`, mode 0600, gitignored par `*.tfvars`). Région `eu-west-3`, `enable_alarms = false` (économise ~$4.20/mois en dev — toggle réversible pour staging/prod).
2. ✅ `terraform init` (provider AWS 5.100.0) puis `terraform plan -out=tfplan-dev` → 139 ressources (185 - 46 alarmes désactivées).
3. ✅ `terraform apply` → **140 ressources créées** : 19 DynamoDB tables, 4 S3 buckets + lifecycle, 25 SQS queues + DLQs, 15 Lambda functions (1 API + 14 workers), 14 SQS event source mappings, API Gateway HTTP API, ECR repository, secret consolidé `media-summarizer-runtime-dev` (29 clés), 13 metric filters, 28 log groups, 7 IAM (roles/policies/attachments), CloudWatch dashboard.
4. ✅ Build + push image Lambda : `docker buildx build --platform linux/arm64 --provenance=false --sbom=false ...` (l'absence de `--provenance=false` produit des manifestes OCI que Lambda refuse). Tags `worker-latest` + `api-latest` poussés dans ECR.
5. ✅ Bugs Terraform corrigés en route : (a) bloc `required_providers` dupliqué dans `dynamodb_quota_tables.tf`, (b) `aws_cloudwatch_log_group.lambda_api` dupliqué dans `monitoring.tf`, (c) 37 blocs `attribute {}` single-line invalides reformatés multi-line, (d) `AWS_DEFAULT_REGION` (env var réservée Lambda) retirée de `lambda_workers.tf` + `lambda_api.tf`, (e) 3 metric filters avec dimensions hardcodées corrigées en JSON path selectors `$.field`.
6. ✅ Bug Dockerfile permissions corrigé (`chmod -R a+rX ${LAMBDA_TASK_ROOT}`) — sans ce fix, l'umask 0600 de l'host propage dans l'image et la Lambda runtime user ne peut pas lire les fichiers.
7. ✅ Bug `media_summarizer/utils/database_async.py:get_session()` corrigé : passait `aws_access_key_id` + `aws_secret_access_key` sans le `aws_session_token` que Lambda injecte → `UnrecognizedClientException`. Maintenant on laisse aioboto3 résoudre les credentials via la chaîne standard (sauf si static creds explicites).
8. ✅ IAM `dynamodb:ListTables` ajoutée (action account-wide) au role `media-summarizer-lambda-api` (utilisée par le `/health` check).

**Résultats dev** :
- API endpoint : `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`
- Health check : `GET /api/health/` → `HTTP 200 {"status":"healthy","database":"connected"}` ✨
- ECR repository : `125313707865.dkr.ecr.eu-west-3.amazonaws.com/media-summarizer-lambda`
- Runtime secret ARN : `arn:aws:secretsmanager:eu-west-3:125313707865:secret:media-summarizer-runtime-dev-OyXaYL`
- Coût mensuel attendu (dev sans trafic) : ~$0.50-1/mois (Secrets Manager $0.40 fixe + reste négligeable).

**État vérifié au 2026-08-13** :

- le health check dev répond `HTTP 200` — **cold 5,2 s, warm 1,0 s** (contre
  25,7 s au déclenchement de `task-217`, désormais `Done`) ;
- les 16 fonctions dev portent `LastModified = 2026-08-13T18:02` : le HEAD est
  bien déployé ;
- dev ne porte plus que **26 tables DynamoDB**, toutes suffixées `-dev`, plus la
  table de lock du state — les 21 tables legacy sont supprimées (`task-249`) ;
- secrets dev : `media-summarizer-runtime-dev` (40 clés, dont 37 vivantes) et
  `media-summarizer-devbox-mobile-env` ;
- **0 alarme CloudWatch active**, mais c'est désormais **voulu** :
  `enable_alarms = false` dans `envs/dev/main.tf` (économie assumée en dev) et les
  trois interrupteurs de coût sont à `false` en prod tant qu'elle est en veille.
  Ce n'est plus un défaut de provisioning mais un item de réveil (Phase 8).

**Blocage staging/prod : résolu (`task-221` → `task-237` → `task-248`)**. La
consigne historique « recopier `terraform.tfvars` avec un autre `environment` »
est morte et remplacée par une racine Terraform par environnement. Ce qui a été
livré :

1. `infrastructure/terraform/envs/{dev,staging,prod}` au-dessus de
   `modules/platform`, chaque racine déclarant une clé de backend et un
   `environment` **littéraux** — `terraform -chdir=envs/prod apply` est
   structurellement incapable d'écrire le state de dev ;
2. 100 % des noms physiques suffixés `-<env>`, migration du state dev par blocs
   `moved` (`scripts/gen_moved_blocks.py`) sans jamais laisser Terraform
   remplacer une table ;
3. `deploy-lambda-env.yml` : déploiement environment-aware, images taguées par
   SHA ;
4. `scripts/tf_plan_guard.sh` : garde-fou de plan. Sa **couche 4** (collision de
   noms avec les autres environnements vivants) devient structurellement
   redondante entre dev et prod, puisqu'une frontière de compte les sépare —
   lancer `tf_plan_guard.sh prod tfplan` **sans** troisième argument ;
5. **décision owner du 2026-08-12 : plus de staging.** Pour un développeur solo,
   maintenir trois environnements n'a pas de valeur. `staging` (vide : 0 ligne sur
   24 tables, 0 objet sur 11 buckets, 0 message sur 26 queues) a été détruit —
   145 ressources — et `prod` a été créé **dans un compte AWS dédié**
   `866874944541` sous l'organisation `o-7sf5u7j5hd`. `envs/staging/` reste au
   dépôt comme référentiel permettant de remonter un staging jetable avant une
   migration risquée.

**Résultats prod (compte `866874944541`, créé le 2026-08-13)** :

- 199 ressources créées ; API `GET /api/health/` → `HTTP 200`
  `{"status":"healthy",…}` en 5,4 s à froid ; worker `search_indexing-prod`
  invoqué à vide → `StatusCode 200`, pas de `FunctionError`.
- Les images Lambda sont tirées de l'ECR de **dev** (`125313707865`) : il a fallu
  trois statements pour l'autoriser (principal de service Lambda de prod, root du
  compte consommateur, et l'autorisation côté IAM prod).
- `database: connected` alors que le secret runtime est **vide** — la route de
  santé ne teste que DynamoDB via les noms de tables injectés par Terraform, pas
  les credentials tiers. Ne jamais lire ce `200` comme « prod fonctionne ».
- Deux prérequis de lancement en découlent : `task-252` (37 credentials vivants) et la
  demande de quota Lambda `L-B99A9384` (10 → 1000), toujours `PENDING`.

### Phase 4 — Tests d'intégration contre AWS dev (jour 3-4) — **NON VALIDÉE, RE-RUN COMPLET REQUIS**

> **Décision 2026-05-28 puis 2026-06-09** : pas de LocalStack (purgé via task-130). Tests E2E directement contre l'API Gateway dev.
>
> **Évolution 2026-06-09 → 2026-06-12** : on n'utilise plus uvicorn local pour les tests d'intégration. L'API + les workers tournent en Lambda sur AWS dev (Phase 3) ; on tape directement l'API Gateway via une suite pytest E2E versionnée (`tests/e2e/`). Les tests qui étaient des skeletons skipped au 2026-06-09 sont maintenant activés en `@pytest.mark.e2e` pour toutes les sources V1 déclarées.

#### Suite E2E pytest (`tests/e2e/`)

- `pytest -m e2e` lance toute la suite contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com` (override via `API_BASE_URL`).
- `tests/e2e/conftest.py` crée un user de test (email horodaté `e2e-test-<ts>-<uuid>@test.local`) au début de session, ingère un article Wikipedia partagé pour les tests d'artifacts, supprime tout en teardown (user + auth_tokens + processing_jobs + artifacts + tags + folders).
- Marqueur `@pytest.mark.e2e` ; suite skipped par défaut (`pytest` sans `-m` lance uniquement les unit tests).
- Détails et runbook : `tests/e2e/README.md`.

#### Statut par source (dernier run complet : 2026-06-12)

> ⚠️ Ce tableau date du dernier run vert. Il ne reflète **pas** le runtime
> courant : depuis, `task-309` et `task-310` ont supprimé les branches yt-dlp
> de YouTube et d'Instagram, et `task-289` a déplacé toutes les routes de
> `/api/v1/` vers `/api/`. C'est exactement ce que le re-run doit revalider.

| Source | Statut E2E | Référence |
|---|---|---|
| Health check API | ✅ passing | `tests/e2e/test_health.py` |
| **Article web** (Wikipedia) | ✅ passing en 15s | `test_phase4_ingestion.py::test_article_reaches_completed` |
| **Artifacts on-demand** : summary, notes, flashcards, quiz | ✅ tous les 4 passing en ~5s chacun | `test_phase4_ingestion.py::test_artifact_*_e2e` |
| **YouTube** (Apify) | ✅ passing depuis task-132 (2026-06-09) ; **chemin unique Apify** depuis `task-309`, sans fallback audio | `test_phase4_other_sources.py::test_youtube_ingestion` |
| Podcast direct audio URL | Test actif, non skipped ; re-run complet requis après derniers changements locaux | `test_phase4_other_sources.py::test_podcast_via_direct_audio_url` |
| Podcast via PodcastIndex / Apple Podcasts URL | Test actif, non skipped ; fixes `task-138`, `task-148`, `task-155`, `task-157` terminés | `test_phase4_other_sources.py::test_podcast_via_podcastindex` |
| X (Twitter) | Test actif, non skipped ; worker/API token configurés | `test_phase4_other_sources.py::test_x_ingestion` |
| TikTok happy path | Test actif, non skipped ; yt-dlp captions + fallback Apify V1 en place | `test_phase4_other_sources.py::test_tiktok_ingestion` |
| Instagram | Test actif, non skipped ; Apify resolver migré et corrigé, **chemin unique Apify** depuis `task-310` | `test_phase4_other_sources.py::test_instagram_ingestion` |
| Document upload (PDF/DOCX/PPTX) | Test actif, non skipped ; endpoint multipart `/api/media/upload` + LlamaParse primary | `test_phase4_other_sources.py::test_document_upload` |

#### Fallback chains E2E (état du code au 2026-08-21)

| Fallback | Statut | Référence |
|---|---|---|
| TikTok yt-dlp IP-block → Apify | Test actif avec sentinel per-request `__e2e_force_ip_block__=1`; `task-185` reste à réconcilier dans le backlog car le code/test semblent déjà présents | `tests/e2e/test_fallback_chains.py::test_tiktok_apify_fallback` |
| Instagram → Apify Reel Scraper → Deepgram push | Test actif ; depuis `task-310` Apify est le chemin unique, le sentinel per-request a été retiré de l'URL soumise | `tests/e2e/test_fallback_chains.py::test_instagram_apify_fallback` |
| Document LlamaParse failure → Unstructured | Test actif avec sentinel filename | `tests/e2e/test_fallback_chains.py::test_document_unstructured_fallback` |
| Deepgram pull→push automatique | Supprimé du scope E2E après `task-158` : les producteurs déclarent explicitement leur mode Deepgram | Commentaire en fin de `tests/e2e/test_fallback_chains.py` |

#### Bugs détectés et fixés en route

Phase 4 a déclenché une cascade de fixes infra/backend :

- **task-119** — Cleanup legacy `ops_alerts` SNS topic + log group dupliqué + `attribute {}` HCL invalide ✅
- **task-120** — Align S3 bucket names env↔terraform + `ProcessingJob.extraction_metadata` field ✅
- **task-121** — Remove deprecated `email` field from summarization worker (legacy SMTP path) ✅
- **task-122** — On-demand artifact pipeline : contract `artifact_id` API↔workers + `media_artifacts` DynamoDB table + worker `quiz` (queue + Lambda + IAM) ✅
- **task-123** — Migrate summarization worker to `artifact_id` contract ✅
- **task-124** — Move `finalize_usage` + `episode_completed` event out of summarization (correctness) ✅
- **task-125** — Audit `JobStatus.SUMMARIZING/NOTIFYING` for dead code removal ✅
- **task-126** — Benchmark YouTube extraction strategies given Lambda IP block ✅
- **task-127** — Split `APIFY_API_TOKEN` per source (Instagram + YouTube separately) ✅
- **task-128** — In-app bug reporting infra ✅
- **task-129** — Migrate YouTube ingestion worker to Apify ✅
- **task-130** — Purge LocalStack runtime + infrastructure ✅
- **task-131** — Fix Apify YouTube actor URL `~` separator + missing `_publish_failure_event` queue ✅
- **task-132** — Fix Apify YouTube actor input payload (HTTP 400 → 200) ✅
- **task-133** — Fix 4 bugs bloquant la complétion Phase 4 : TikTok `mark_extracting`, import circulaire document, fixture podcast, transcript Instagram vide ✅
- **task-134** — Fix TikTok worker : `ProcessingJob.episode_url` inexistant ✅
- **task-135** — Provision queue Instagram manquante en Terraform ✅
- **task-136** — Fix Algolia API key corrompue par commentaire trailing dans Secrets Manager ✅
- **task-137** — Fix Deepgram worker : floats → Decimal pour DynamoDB ✅
- **task-138** — Fix `/api/podcasts/submit` : classification plateforme au lieu de `source_platform=rss` hardcodé ✅
- **task-139** — Fix fallback Deepgram sur CDN URLs bloquées par politiques IP source ✅
- **task-140** — Benchmark TikTok extraction strategies given Lambda IP blocking ✅
- **task-141** — Audit workers + application du fix `mark_extracting`/`episode_url` à Instagram ✅
- **task-142** — Endpoint et pipeline upload audio direct MP3/M4A/WAV ✅
- **task-143** — Fix mismatch queue `EPISODE_COMPLETION_EVENTS_QUEUE` vs `EPISODE_COMPLETED_EVENTS_QUEUE` ✅
- **task-144** — Ajout fallback Apify TikTok V1 ✅
- **task-146** — Migration Instagram vers `InstagramApifyResolver` existant ✅
- **task-147** — Fix `media_completed_events` : event type `episode_completion_status` ignoré ✅
- **task-148** — Fix PodcastIndex resolver : Apple Podcasts URL rejetée après task-138 ✅
- **task-149** — E2E TikTok yt-dlp → Apify fallback ✅
- **task-150** — E2E Instagram Apify → Deepgram fallback ✅
- **task-151** — E2E document LlamaParse → Unstructured fallback ✅
- **task-152** — E2E Deepgram pull→push fallback, ensuite retiré/ajusté par `task-158` ✅
- **task-153** — Fix Instagram Apify resolver : `APIFY_INSTAGRAM_API_TOKEN` manquant ✅
- **task-154** — Provision table `media_watchers` manquante ✅
- **task-155** — Fix PodcastIndex credentials non chargés par Lambda ✅
- **task-156** — Fix Instagram Apify input field `directUrls` ✅
- **task-157** — Fix matching Apple Podcasts `?i=` vers épisodes PodcastIndex ✅
- **task-158** — Deepgram mode explicite par producer/worker ✅
- **task-167** — Mise à jour des fallback-chain E2E après refactor Deepgram mode ✅
- **task-173** — Simplification Instagram : suppression Comment Scraper + legacy video-post branch ✅
- **task-176** — Podcasting 2.0 transcript short-circuit reconnecté ✅
- **task-177** — YouTube fallback chain alignée sur TikTok : yt-dlp → Apify → Deepgram ✅ *(annulée depuis par `task-309` : Apify est le chemin unique, il n'y a plus de chaîne)*
- **task-178** — Fallback Deepgram sur media URL résolue par Apify pour TikTok ✅
- **task-179** — Documentation providers/fallback chains mise à jour ✅

#### Reste à faire

1. ⚠️ **Synchroniser et déployer le code courant** — `Deploy Lambda Functions`
   est vert sur `30cf62c` (2026-08-29T21:10), mais `main` local porte **10
   commits backend/infra non poussés** (cf. § « État de vérité »). À pousser
   **avant** le re-run, sinon la suite s'exécute contre un runtime qui n'est pas
   le HEAD. Deux d'entre eux ajoutent des alarmes CloudWatch : le push déclenche
   le deploy Lambda, pas le `terraform apply`, qui reste à lancer à la main.
2. ✅ **Fermer `task-217` et revalider le cold start API** — `Done` le
   2026-08-06 ; cold 5,2 s / warm 1,0 s mesurés le 2026-08-13. Le health check
   est utilisable comme gate de release (`task-217` AC #7).
3. **Re-run complet AWS dev — SEUL GATE BACKEND ENCORE OUVERT** : `pytest -m e2e`
   contre `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. Aucune preuve
   d'un run complet depuis le 2026-06-12. Ne pas marquer Phase 4 DONE tant que ce
   run n'est pas vert. Deux arguments s'additionnent : l'incident du 2026-08-13
   (dérive `fastapi` entre l'image et `uv.lock`, invisible en local) montre qu'une
   image peut différer du lock, et **le surface d'API a entièrement bougé depuis
   le dernier run** — `/api/v1/` supprimé (`task-289`), YouTube et Instagram
   passés en Apify-only (`task-309`/`310`), quota en minutes (`task-287`),
   covers et créateurs ajoutés au contrat média (`task-304`).
4. **Tester le digest journalier** (EventBridge rule). Pas couvert par l'E2E actuelle.
5. ✅ **Purge des comptes/artifacts E2E orphelins** — `task-246` (purge
   rétrospective) et `task-247` (teardown réellement effectif) sont `Done` :
   `scripts/purge_e2e_accounts.py` et `scripts/delete_e2e_account.py` existent, le
   teardown pytest exporte désormais les variables de tables avant tout import
   `media_summarizer` (sans quoi il échouait en silence), et les jobs Maestro
   appellent la suppression en `if: always()` / `continue-on-error`.
   **Résidus du 2026-08-13 purgés** : `task-259` est `Done` — les deux comptes
   restants (`e2e-task249-1786605697`, `e2e-register-31712425508-1-android`) ont
   été supprimés, et la sélection est passée de préfixes énumérés à un wildcard
   `e2e-*` (`0898b13`) pour fermer l'angle mort qui laissait échapper les
   préfixes ad hoc. Restent par conception dans `users-dev` : le compte owner et
   `e2e-maestro-20260809200952`, compte permanent du secret
   `E2E_TEST_USER_EMAIL`, protégé via `PROTECTED_EMAILS`.
6. ✅ **Backlog réconcilié** au 2026-08-21 : 288 tâches (+ 19 archivées),
   **15 non-`Done`**, aucune incohérence de statut résiduelle — `task-162` et
   `task-262` sont passées `Done`. Liste et lecture : § « État de vérité ».

### Phase 5 — Mobile dev build (jour 4-5) — **EN COURS, NON VALIDÉE AU 2026-08-21 — CHEMIN CRITIQUE**

> Les gates backend étant fermés, cette phase est désormais **ce qui bloque le
> plan**. Elle tient à trois choses : un build Android unique, et deux validations
> manuelles sur device physique.

#### Fait

1. ✅ `task-159` — `scripts/mobile_release_check.sh` ajouté pour valider les prérequis EAS.
2. ✅ `task-160` — `cd mobile && npx expo prebuild` exécuté ; les dossiers natifs iOS/Android existent.
3. ✅ `task-181` — Expo SDK 52 → 55 + `expo-share-intent` 6.x.
4. ✅ `task-187` — Share intent refactoré vers l'API officielle `expo-share-intent` v6.
5. ✅ `task-188` — Fix cold-start race `expo-share-intent` v6 + suppression de la config custom dupliquée.
6. ✅ `task-161` — une build iOS development physique a terminé sur EAS le 2026-06-11
   (`build id 324f110a-8cbe-447c-96bf-2214099348c4`, commit `8c63765`).
   Son artifact a expiré le 2026-06-25, mais le development client reste
   installé et fonctionnel sur l'iPhone owner. Aucun changement natif requis
   n'a été introduit depuis ce build ; task-161 est clôturée sur cette preuve.

7. ✅ 2026-08-13 — `scripts/mobile_release_check.sh` corrigé : il exigeait encore
   `mobile/plugins/withShareExtension.js`, supprimé volontairement par
   `task-188`, et échouait donc à tort alors que le plugin officiel
   `expo-share-intent` est bien configuré (`mobile/app.config.ts:97`). Le script
   passe désormais, avec pour seul `WARN` la variable Android encore vide —
   attendue, elle est levée par `task-163`.
8. ✅ 2026-08-13 — `task-162` : keystore Android créé côté EAS via
   `eas credentials`, **sans aucun build**. SHA-1 :
   `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD`
   (configuration `Build Credentials aRG08ty5Ek`, alias
   `3d6435c18da4d3d15721839b43347b78`). Détail et SHA-256 dans les notes de
   `task-162`.

#### À faire

1. Variables EAS : contrairement à l'état noté au 2026-07-31, les trois
   environnements `development`/`preview`/`production` contiennent bien cinq
   variables `EXPO_PUBLIC_*` (constaté le 2026-08-13 via `eas env:list`).
   `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` a été ajoutée à l'environnement
   `development` le 2026-08-13, qui porte donc six variables. Le trou qui
   subsistait est comblé : `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` valait le
   placeholder `your_revenucat_google_api_key_here` dans les trois
   environnements, et porte la vraie clé `goog_` depuis le **2026-09-01**
   (`task-238`). À noter aussi : `EXPO_PUBLIC_API_BASE_URL` n'existe **que**
   dans le bloc `env` inline de `mobile/eas.json`, pas côté serveur — les deux
   mécanismes coexistent.
2. ~~`task-163`~~ — **`Done` le 2026-09-02.** Les deux OAuth clients Android
   existent (SHA-1 keystore EAS le 2026-08-13, SHA-1 Play App Signing le
   2026-09-02), les AAB sont produits, et le sign in with Google est validé sur
   device sur l'app installée depuis Play. Les deux créations ont dû se faire à
   la main dans l'UI web de la Cloud Console — ni `gcloud` ni aucune API
   publique n'expose la création d'un OAuth client de type Android.
3. `task-164` — validation iOS sur device physique :
   - Sign in with Apple → user créé/lié → inbox.
   - Continue with Google → `ASWebAuthenticationSession` → user créé/lié → inbox.
   - Share intent Safari → share-confirm → submit → vignette inbox.
4. `task-165` — validation Android sur device physique :
   - Continue with Google sans `DEVELOPER_ERROR`.
   - Apple button absent ou no-op clean.
   - Share intent Chrome URL.
   - Share intent texte/audio.
5. **Couverture Maestro (`task-168` à `task-172`) : plus un prérequis de
   Phase 5.** La CI Maestro est en sommeil depuis le 2026-08-13 (`task-254`) le
   temps que l'UI soit figée. `task-168`, `task-169`, `task-170` et `task-171`
   sont closes sur les 3 flows validés ; `task-172` est verrouillée
   (`dispatchable: false`) jusqu'à ce jalon. État des 7 flows, ce qui reste
   provisionné et travail de réactivation : Phase 7, section « Maestro E2E CI —
   en sommeil depuis le 2026-08-13 ».
6. `task-166` — marquer Phase 5 DONE dans ce plan une fois `task-163`,
   `task-164` et `task-165` closes.
7. ✅ **Hygiène backlog** : `task-162` est passée à `Done` le 2026-08-13 — ses
   3 critères étaient cochés et son SHA-1 consigné, seul le statut était en retard.
   Phase 5 ne dépend donc plus que de `task-163` (ACs #6-#8), `task-164` et
   `task-165`.
8. **Rebuild iOS courant** : `task-161` est `Done` sur la preuve du 2026-06-11,
   mais l'artifact a expiré le 2026-06-25 et le HEAD a beaucoup bougé depuis. Un
   rebuild iOS `development` sera de toute façon nécessaire pour `task-164`, ne
   serait-ce que pour tester le code courant.

### Phase 6 — Tests IAP sandbox (jour 5-6) — **validée sur les deux stores le 2026-09-02**

> Le code RevenueCat mobile/backend est implémenté (`task-99`, complété par
> `task-244` et `task-245`) : SDK mobile, paywall 3 tiers, `restorePurchases`,
> endpoint `POST /api/webhooks/revenucat` (6 event types, idempotence par
> `event_id` + TTL 30 j), table `revenucat_events`, `GET /api/entitlements/status`.
> Les routes sont montées (`api/main.py:160,162`, décalées par le sweep
> `/api/v1` → `/api` de `task-289`) et déployées. **Le setup stores et la validation
> sandbox sont faits eux aussi** : un achat réel a tourné de bout en bout sur Play le
> 2026-09-01 et sur l'App Store le 2026-09-02. Ce qui reste n'appartient plus à cette
> phase, ce sont les métadonnées de soumission (Phase 10).

**État vérifié au 2026-09-02** (API RevenueCat v2, AWS dev, `eas env:list`) :

- **`REVENUCAT_WEBHOOK_SECRET` est renseigné**, en local *et* dans
  `media-summarizer-runtime-dev` — mêmes valeurs, comparées par empreinte
  SHA-256 sans jamais les afficher. Le Lambda déployé le charge : `POST /api/webhooks/revenucat` avec un
  Bearer invalide répond `HTTP 401 "Invalid authorization"` — sondé en direct.
  Le `500 "Webhook secret not configured"` que ce plan a longtemps annoncé
  n'existe plus. Le secret n'est pas généré par RevenueCat, c'est une valeur au
  choix de l'owner saisie dans le dashboard ; l'endpoint
  `/v2/projects/<id>/webhooks` répond `404`, donc la valeur collée côté RevenueCat
  → Integrations → Webhooks n'était pas vérifiable par un agent. **Elle l'est
  maintenant par l'usage** : 32 requêtes signées ont franchi un Lambda qui répond
  `401` sur un Bearer invalide. Plus rien à confirmer là-dessus.
- **`revenucat_events-dev` contient 32 items**, et non plus 0. La table est un
  **registre de déduplication**, pas une archive : elle ne garde que `event_id`,
  `event_type`, `user_id`, `processed_at` et un `ttl` (30 j). Aucun payload, donc
  aucun `store` ni `product_id` lisible ici — pour l'origine d'un abonnement, lire
  `platform` et `revenucat_product_id` dans `subscriptions-dev`.
- **Le projet RevenueCat `proj879a771a` est plus avancé que ce que ce plan
  disait** : l'offering `default` (courant) et les 3 packages
  `text_only`/`mix`/`audio_heavy` existent, avec des produits mensuels rattachés.
  Jusqu'au 2026-08-13 ces produits appartenaient **tous** au Test Store
  (`appa51ecf7585`, identifiants `*_test`) : toute la chaîne était câblée sur le
  simulateur RevenueCat, jamais sur StoreKit ni Play Billing. `task-261` a ajouté
  les 3 produits App Store à côté (voir ci-dessous) ; le Play Billing reste
  entièrement à faire (`task-238`).
- **La résolution du tier est entitlement-driven depuis `task-262`**
  (2026-08-13) : le webhook lit le tier dans les entitlement IDs de l'événement
  (`entitlement_ids`, ou `entitlement_id` sur les anciens payloads), plus jamais
  dans un identifiant de produit store. Un entitlement par tier
  (`tier_text_only`/`tier_mix`/`tier_audio_heavy`), un produit rattaché à
  exactement un entitlement ; ajouter un produit store devient une opération
  dashboard, sans changement de code ni deploy Lambda. Un tier non résolvable
  n'est plus avalé en `warning` : il sort en `ERROR`
  (`revenucat.tier_unresolved`) avec le product ID et les entitlement IDs, avec
  metric filter + alarme dans
  `infrastructure/terraform/modules/platform/revenucat_alerts.tf`. Disposition
  complète : `docs/REVENUECAT_ENTITLEMENTS.md`.
- **L'app iOS `app0d4b00c12f`** (bundle `com.secondbrainlabs.core`) est déclarée
  avec une In-App Purchase key et porte depuis le 2026-08-13 les **3 produits**
  `com.secondbrainlabs.core.{text_only,mix,audio_heavy}_monthly` (`task-261`),
  chacun rattaché à son entitlement de tier et au package correspondant de
  l'offering `default`. **Complète depuis le 2026-09-02** : les 3 abonnements
  existent en App Store Connect dans le groupe `Second Brain Plans`, la clé ASC est
  déposée dans RevenueCat, et les trois drapeaux sont verts
  (`app_store_connect_api_key_configured`, `app_store_connect_vendor_number`,
  `subscription_key_configured`). StoreKit résout les trois produits sur le build
  TestFlight, et l'achat a été encaissé. Seul reliquat, inoffensif : les 3 produits
  lisent encore `subscription.duration: null`, champ d'import de catalogue sans effet
  sur l'achat (point 4 ci-dessous).
- **L'app Google Play est complète depuis le 2026-09-01** (sessions owner,
  `task-238`) : `appb253c0f75a`, package `com.secondbrainlabs.core`, service
  credentials `Valid credentials`, et **3 produits** rattachés aux entitlements
  de tier et aux packages de l'offering `default`. Les 3 abonnements Play
  existent avec un forfait de base `monthly` actif et un prix manuel par pays
  (3 / 5 / 9 EUR TTC en France) ; un identifiant de produit Play côté RevenueCat
  s'écrit `subscriptionId:basePlanId`. La **vraie clé `goog_`** est posée dans
  les trois environnements EAS depuis la même date — elle y valait le
  placeholder `your_revenucat_google_api_key_here`, ce qui rendait tout AAB
  antérieur incapable de résoudre un offering, `EXPO_PUBLIC_*` étant inliné à la
  compilation. Les deux ACs qui exigeaient un téléphone sont franchies elles aussi :
  install depuis la piste interne, puis achat en license tester avec le cycle complet
  (`INITIAL_PURCHASE`, cinq `RENEWAL`, `CANCELLATION`, `EXPIRATION`).
- **`subscriptions-dev` porte 4 abonnements réels**, plus la fixture manuelle du
  2026-08-02 qui servait à tester l'UI : trois Android issus des essais du
  2026-09-01/02 (deux `expired`, un `expired` après `CANCELLATION`) et **un iOS
  actif** — `com.secondbrainlabs.core.mix_monthly`, `tier: M`,
  `auto_renew_status: true`. C'est cette ligne qui prouve l'origine App Store : le
  préfixe `com.secondbrainlabs.core.` n'existe que sur l'app iOS du projet.
- **Un fichier `mobile/ios/StoreKit.storekit` est hors périmètre** — il n'existe pas au dépôt et n'a pas à y être créé : il ne servirait
  qu'au test StoreKit dans le simulateur Xcode, et l'owner n'a pas de Mac
  (cf. Phase 7, contrainte de budget CI). La validation iOS est passée par TestFlight
  **seul**, sans compte sandbox : un build TestFlight est déjà en environnement
  sandbox. Ce n'est pas un reste à faire, c'est un hors-sujet.

**Ordre d'exécution** — `task-262` était le préalable des deux autres, elle est
faite :

1. ✅ **`REVENUCAT_WEBHOOK_SECRET`** (owner, fait — constaté le 2026-08-13) : la
   valeur est en place dans `.env` et dans `media-summarizer-runtime-dev` (40 clés
   intactes), les deux identiques, et le Lambda déployé la charge. Le gate est
   franchi : le webhook répond `401` sur un token invalide, plus `500`. **Seul
   reste à confirmer visuellement** que la même valeur figure dans RevenueCat →
   Integrations → Webhooks avec l'URL `…/api/webhooks/revenucat` — l'API v2 ne
   lisant pas les webhooks (`404`), aucun agent ne peut le vérifier.
   Pour mémoire, si cette valeur doit être changée un jour : `put-secret-value`
   remplace tout le JSON, donc passer par `jq` sur la valeur courante et vérifier
   `jq 'length'` = 40 avant push, puis forcer un cold start de
   `media-summarizer-api-dev` (le secret n'est lu qu'à l'init du conteneur et le
   warm-up EventBridge empêche le recyclage spontané ; ré-appliquer la même
   `image_uri` suffit, elle est sous `ignore_changes`).
2. ✅ **`task-262` — résolution du tier par entitlement** (2026-08-13) : trois
   entitlements `tier_text_only` (`entlc5a41cba3a`) / `tier_mix`
   (`entlde3fb9eb65`) / `tier_audio_heavy` (`entlfa93d44749`), un produit
   rattaché à exactement un entitlement ; `PRODUCT_TIER_MAP`, l'entitlement
   `pro`, le legacy `Second Brain Labs Pro` et le scaffolding RevenueCat
   (`monthly`/`yearly`, `$rc_monthly`/`$rc_annual`) supprimés. Le code du webhook
   ne contient plus aucun identifiant de produit store. Reste à vérifier après un
   push sur `main` : que le webhook déployé traite un événement porteur d'un
   entitlement de tier (dépend du point 1, le secret).
3. **`task-261` — iOS** : le **câblage RevenueCat est fait** (2026-08-13) — 3
   produits App Store créés sur `app0d4b00c12f`, rattachés aux entitlements de
   tier et aux packages de l'offering `default`, vérifiable par
   `GET /v2/projects/proj879a771a/entitlements/<id>/products` et
   `GET /v2/projects/proj879a771a/packages/<id>/products`. Reste **uniquement du
   travail owner**, dans cet ordre :
   0. **Le contrat relatif aux applications payantes est signé — `Actif` depuis le
      2026-09-02**, avec le compte bancaire `Actif` et les deux formulaires fiscaux
      envoyés le même jour (« U.S. Certificate of Foreign Status of Beneficial Owner »
      et « U.S. Form W-8BEN », tous deux `Actif`). Cette étape n'est plus bloquante ;
      le reste du point 0 documente la séquence traversée, parce qu'aucun de ces écrans
      ne se rejoue et que plusieurs portent des échéances.

      L'état de départ, relevé le matin du 2026-09-02 dans **App Store Connect →
      Business → Contrats** : « Contrat relatif aux applications **gratuites** » =
      **Actif** (1 sept. 2026 – 1 juin 2027), « Contrat relatif aux applications
      **payantes** » = **Nouveau**. Rien de payant n'est vendable avant qu'il soit
      `Actif`, et **une app à téléchargement gratuit qui vend des abonnements relève du
      contrat payant** : le critère d'Apple est la circulation d'argent, pas le prix du
      téléchargement. C'est le contrat gratuit, seul actif, qui a suffi pour la
      distribution TestFlight du 2026-09-02 — il n'aurait suffi pour aucun abonnement.
      Deux bandeaux d'Apple sur cette page portaient la séquence :
      - bandeau bleu → lien **« Modifier l'entité juridique »** : les informations
        d'entité juridique doivent être complètes *avant* la signature. Prérequis du
        prérequis. Dans cette boîte de dialogue, **Nom**, **Type** (`Particulier`) et
        **Pays ou région** sont grisés — ils viennent de l'inscription au Developer
        Program et seul le support Apple les change ; seuls adresse / ville / code
        postal sont éditables, et c'est suffisant : un particulier peut signer le
        contrat payant. Enregistrer la fiche même sans la modifier est ce qui la
        commet, la fiche datant de l'inscription n'ayant jamais traversé ce
        formulaire. Bandeau toujours présent après enregistrement ⇒ support Apple
        Developer, rien à forcer depuis l'interface.
      - puis signer, et compléter informations fiscales et bancaires dans la même
        section **Business**. Le volet fiscal est le formulaire **« U.S. Certificate
        of Foreign Status of Beneficial Owner »** (équivalent W-8BEN, évite la retenue
        à la source américaine de 30 %), rattaché au contrat *Apps payantes* : nom,
        pays, `Individual/Sole proprietor`, résidence permanente et adresse postale
        sont préremplis depuis l'entité juridique ; le seul champ à saisir est
        **`Title`** = la qualité du signataire, `Owner` pour un développeur
        individuel. **Envoyer est irréversible** (« vous ne pourrez plus apporter de
        modifications à ce formulaire ») — une erreur se corrige au support Apple.
        Le « Pseudo du formulaire fiscal » est une étiquette privée, facultative.
        L'adresse de ce formulaire n'est pas publique : elle va à Apple et au fisc,
        pas sur la fiche App Store. Dans sa *Part II*, la **ligne 10 (« Special rates
        and conditions ») reste vide** — les instructions IRS la réservent aux
        avantages conventionnels exigeant des conditions que la ligne 9 ne couvre
        pas ; la ligne 9 (résidence fiscale française au sens de la convention
        France–États-Unis) suffit à ramener la retenue à 0 % sur les revenus de vente
        d'apps. La *Part III* demande deux cases : la déclaration sous peine de
        parjure, et `I certify that I have the capacity to sign` — cette dernière fait
        partie du bloc signature standard du W-8BEN depuis la révision 2021 et se
        coche même quand on signe pour soi-même.
      - **Échéances portées par le W-8BEN signé le 2026-09-02**, à ne pas
        redécouvrir quand Apple suspendra les versements : validité de trois années
        civiles, donc **expiration le 2029-12-31** avec renouvellement à faire avant ;
        et obligation de redéposer un formulaire **sous 30 jours** si une
        certification devient inexacte — un changement d'adresse, ou le passage de
        l'activité d'un particulier à une société.
      - bandeau rouge → lien **« Compléter les exigences de conformité »** : statut de
        commerçant (DSA). Indépendant du contrat, mais bloquant pour la disponibilité
        dans l'UE. La boîte de dialogue « Conformité à la législation sur les services
        numériques » offre deux réponses, et **c'est « J'ai le statut de commerçant »**
        qu'il faut prendre : le critère du DSA est l'activité commerciale, pas le prix
        du téléchargement. La seconde réponse n'est pas une échappatoire mais un
        retrait — Apple ne distribue pas dans l'UE les apps d'un développeur déclaré
        non-commerçant.
        **Les coordonnées de commerçant (adresse, téléphone, e-mail) sont publiées par
        Apple sur la fiche App Store**, et Apple vérifie le téléphone et l'e-mail par
        code : les deux doivent être opérationnels au moment du formulaire. Ce sont
        bien les coordonnées **de ce formulaire** qui sont publiées, pas l'adresse de
        l'entité juridique ci-dessus (celle-là sert au contrat et aux paiements, et
        doit rester l'adresse réelle). Contrairement au W-8BEN, **ces coordonnées
        restent modifiables** — Apple relance simplement la vérification — donc une
        domiciliation ne bloque pas le lancement ; mais modifiable n'est pas
        effaçable, une adresse personnelle publiée quelques mois aura été aspirée.
        L'e-mail publié doit être une adresse dédiée du domaine, pas une boîte
        personnelle, et c'est la même que celle de la fiche App Store et de la
        politique de confidentialité.
   1. **App Store Connect → Apps → Abonnements** : créer un groupe d'abonnements
      (un seul groupe pour les trois : c'est ce qui rend upgrade/downgrade
      possible sans double facturation), puis les trois abonnements mensuels avec
      les identifiants **exacts** `com.secondbrainlabs.core.text_only_monthly` /
      `…mix_monthly` / `…audio_heavy_monthly` à 3 / 5 / 9 € TTC. Les valeurs
      prêtes à coller (reference names, display names ≤ 30 car., descriptions
      ≤ 45 car., prix) sont dans
      `docs/store-listing/app-store-connect.md`, section « Subscriptions ».
      Aucun identifiant à improviser : ils sont figés, et un product ID ASC est
      définitif.
   2. **Pas d'offre d'essai côté ASC.** Le mois offert du tier Mix est accordé
      côté serveur par ancienneté de compte
      (`quota_enforcer._is_free_trial_active`, `free_trial` dans
      `pricing_config_service`). Ajouter une Introductory Offer dans ASC le
      doublerait — un mois gratuit *facturé* Apple en plus du mois gratuit
      applicatif.
   3. **Screenshot de review + localisation** par abonnement. Ce que ça bloque
      exactement, vérifié dans la référence App Store Connect le 2026-09-02 : la
      **soumission à la revue**, rien d'autre. Sous `Prepare for Submission`, Apple
      écrit « If your In-App Purchase is missing required metadata, complete it before
      adding for review » — donc ni l'import RevenueCat ni la résolution StoreKit en
      sandbox n'en dépendent, contrairement à ce que ce point affirmait. La capture
      est « used for review only and isn't displayed on the App Store », et **une fois
      déposée elle est remplaçable mais pas supprimable**. Apple ne donne pas de
      dimension propre, il renvoie aux specs de captures d'app ; le 640 × 920 vient de
      RevenueCat, qui autorise même un placeholder — « While testing, it's okay to
      upload an empty 640 x 920 image here of whatever you want ». Aucune poule et
      aucun œuf, donc : `mobile/app/paywall.tsx` affiche les trois cartes depuis
      `GET /api/pricing` même quand le store ne résout rien (prix, sélection et bouton
      d'achat éteints), donc une capture prise avant la création des produits est déjà
      valable, et se remplace par une capture avec les prix avant la soumission.
      Compter **jusqu'à 1 h** entre l'écriture des métadonnées et leur apparition en
      sandbox (« It may take up to 1 hour… »).

      **La section `Langue`, elle, est obligatoire** — Apple : « You must include these
      properties for at least one language » — et contrairement au screenshot ces deux
      chaînes sont vues par le client (feuille d'achat, Réglages → Abonnements). Pas
      d'option « s'adapte automatiquement » : Apple sert la localisation correspondant à
      la langue App Store de l'utilisateur et retombe sur la **langue principale de
      l'app** (App Information — la garder sur `Anglais (É.-U.)`), donc le jeu fourni
      *est* la portée. Les 11 locales de `mobile/app.config.ts` sont rédigées prêtes à
      coller dans `docs/store-listing/app-store-connect.md`, § « Localizations — all
      eleven locales », mot pour mot depuis les fichiers de langue de l'app. Trois
      pièges : **13 entrées ASC et non 11** (Apple n'a pas d'espagnol ni de portugais
      génériques — prendre les deux variantes de chaque avec la même chaîne, sinon les
      storefronts latino-américains retombent en anglais) ; l'espagnol Audio-Heavy fait
      **exactement 45 caractères**, avec un repli à 40 noté dans le doc si ASC le
      refuse ; et le display name reste `Reader` / `Mix` / `Audio-Heavy` partout, un nom
      de produit ne se traduit pas.

      Ces descriptions **ne se collent pas telles quelles dans l'app** : la carte du
      paywall doit tenir à 20px à côté d'un prix sur un écran de 375pt. `task-337` a
      donc réparti les deux moitiés plutôt que de recopier la phrase — la ligne
      dominante de la carte (`plan.card.allowance`) dit « {duration} of
      transcription », et la moitié qui ne varie pas d'une formule à l'autre est dite
      une seule fois sous la liste des cartes par `plan.minutesRule` : les articles et
      les pages web ne coûtent aucune minute. C'est aussi la phrase affichée sous la
      jauge de l'onglet Compte, donc les deux écrans ne peuvent pas diverger. Les 11
      fichiers de langue sont alignés ; détail dans
      `docs/store-listing/app-store-connect.md`, § « Why not "N h of audio and video a
      month" ».

      Deux contraintes Apple relevées au même endroit :
      - **Les trois abonnements ne peuvent pas être revus seuls** : « Your first
        auto-renewable subscription must be submitted with a new app version. Your
        first subscription group must also be submitted with a new app version and
        must include an auto-renewable subscription in the same submission. » Ils
        partent dans la même soumission que la 1.0.
      - **En TestFlight le renouvellement est accéléré** : un `RENEWAL` par jour,
        6 au maximum sur une semaine, quelle que soit la durée réelle. Excellent pour
        vérifier la boucle `revenucat_events-dev` → `subscriptions-dev`, mais un
        abonnement de test s'éteint au bout de 6 jours.
      - Le classement des niveaux se fait par le bouton **`Edit Order`** sur la page
        du groupe, « from the one that offers the most (level 1) to the one that
        offers the least » — Audio-Heavy en 1.

      **Ne pas mettre les abonnements dans une soumission maintenant.** Constaté le
      2026-09-02 : le groupe `Second Brain Plans` et les trois abonnements existent, et
      une soumission qui les contient refuse de partir — « ajoutez une version de l'app
      pour la plateforme sélectionnée ». Or y avoir ajouté les produits les met en
      `Ready for Review`, état où « you can edit only the reference name, pricing, and
      availability » : les 13 localisations, le screenshot de review et la durée gèlent,
      dans une soumission impossible à envoyer. Sortie : **App Review → Submissions →
      la soumission → `Cancel Submission` → `Confirm`**, les produits repassent
      `Prepare for Submission`. Détail et enchaînement correct dans
      `docs/store-listing/app-store-connect.md`, § « Do not put the subscriptions in a
      submission before 1.0 is ready ». À noter aussi : le groupe s'appelle
      `Second Brain Plans` — si c'est le nom marketing définitif, `task-186` doit
      passer avant d'écrire les métadonnées de la 1.0 (Phase 10, sous-étape 0).
   4. **App Store Connect → Users and Access → Integrations → App Store Connect
      API** : la clé Admin **existe depuis le 2026-09-01** et est déjà enregistrée
      auprès d'EAS Submit (cf. `mobile/MOBILE_CI_CD.md` § 4) — ne pas en générer une
      seconde, le `.p8` est encore sur la machine dans le répertoire où EAS le range.
      Il reste à le coller dans RevenueCat → **Apps → `Second Brain Labs Core (iOS)`
      → onglet `App Store Connect API`**, avec l'issuer ID (au-dessus du tableau
      `Active` de la page ASC) et le **Vendor Number**, que RevenueCat exige aussi :
      section **`Reports`** de la barre de navigation ASC, coin supérieur gauche sous
      le nom de l'entité juridique, sous la forme `Vendor # 1234567` (rôle Account
      Holder, Admin ou Finance). Puis `Save Changes`. Attention à ne pas confondre
      avec la clé In-App Purchase (`SubscriptionKey_*.p8`) : celle-là est déjà en
      place, `subscription_key_configured: true`. Le `.p8` ne s'écrit **jamais** dans
      un fichier suivi (repo public), pas plus que le key ID ou l'issuer ID.

      ✅ **Fait le 2026-09-02.** `GET /v2/projects/proj879a771a/apps` donne
      `app_store_connect_api_key_configured: true`, `app_store_connect_vendor_number`
      renseigné et `subscription_key_configured: true` — les trois drapeaux iOS sont
      verts. Le rôle exigé est bien celui de la clé en place : RevenueCat demande « at
      least the access level **App Manager** », la clé est Admin.

      **En revanche les 3 produits iOS lisent toujours `subscription.duration: null`**,
      et l'annonce faite ici d'un passage à `P1M` était prématurée. Ce n'est pas un
      blocant : StoreKit résout les produits, la preuve étant que le paywall affiche des
      prix sur le build TestFlight. Ce champ vient de l'import du catalogue par
      RevenueCat, pas de l'achat — que valide la clé In-App Purchase. Comparaison utile :
      les 3 produits Play lisent `duration: P1M` **et** `grace_period_duration: P7D`
      parce qu'ils ont été créés le 2026-09-01, une fois les *service credentials*
      validés ; les 3 produits iOS ont été créés le 2026-08-13, sans clé ASC. Aucune
      page RevenueCat ne documente ni délai d'import ni bouton de réimport, donc :
      revérifier plus tard, et ne rien bloquer là-dessus.
   5. **Pas besoin de compte sandbox pour l'achat de base.** Apple : « Apps
      downloaded from TestFlight will automatically operate in a sandbox
      environment. » Un Sandbox Apple Account ne sert qu'à tester des *scénarios* —
      billing retry, cadence de renouvellement personnalisée — et se crée alors dans
      **Users and Access → Sandbox → Test Accounts**, sur une adresse non rattachée à
      un Apple ID existant.
   6. ✅ **Achat sandbox depuis TestFlight — fait le 2026-09-02.** Sur le build
      1.0.0 (2), le paywall a résolu les trois abonnements et l'achat est passé :
      `INITIAL_PURCHASE` à 15:42:41, puis `PRODUCT_CHANGE` et `RENEWAL` à 15:43:00.
      `subscriptions-dev` porte `com.secondbrainlabs.core.mix_monthly`,
      `platform: ios`, `tier: M`, `status: active`, `auto_renew_status: true`, période
      15:42:57 → **le lendemain** 15:42:57 : le renouvellement accéléré de TestFlight,
      un par jour, **6 au maximum**, puis l'auto-renouvellement se coupe.

      Le `PRODUCT_CHANGE` n'était pas au programme et vaut mieux que l'achat seul : il
      prouve que le **changement de formule à l'intérieur du groupe** fonctionne, donc
      que les niveaux 1/2/3 réglés en ASC font leur travail. Restore Purchases n'émet
      pas d'événement webhook : ce chemin-là ne se vérifie qu'à l'écran.

      **Les prix affichés en dollars sur ce build ne sont pas un bug** — ni de l'app,
      ni d'App Store Connect. C'est un défaut connu et documenté de TestFlight, détaillé
      dans `docs/store-listing/app-store-connect.md` § « The prices shown in TestFlight
      are not trustworthy ». Ne rien corriger : ce qui compte est la devise de la feuille
      d'achat d'Apple, pas celle de la carte.
   7. ✅ Le tour de webhook est bouclé du même coup — voir le point 5 ci-dessous.
4. ✅ **`task-238` — Android : `Done`.** L'app Google Play, les 3 abonnements et leurs
   prix, les 3 produits RevenueCat, la clé `goog_` dans les environnements EAS et l'AAB
   `versionCode` 5 sur la piste interne, plus l'install et l'achat en license tester :
   le cycle complet a tourné le 2026-09-01 (`INITIAL_PURCHASE`, cinq `RENEWAL`,
   `CANCELLATION`, `EXPIRATION`), avec `tier: L` résolu depuis l'entitlement.
5. ✅ **Circuit webhook bouclé sur les deux stores.** `revenucat_events-dev` contient
   32 items et `subscriptions-dev` 4 abonnements, dont un iOS actif. Une limite à
   connaître : `revenucat_events-dev` est un **registre de déduplication**, pas une
   archive de payloads — il ne stocke que `event_id`, `event_type`, `user_id`,
   `processed_at` et un `ttl`. Le `store: app_store` de l'événement n'y est donc pas
   lisible, et la preuve équivalente est dans `subscriptions-dev` : `platform: ios` avec
   un `revenucat_product_id` en `com.secondbrainlabs.core.*`, identifiants qui
   n'existent que sur l'app App Store du projet RevenueCat. Reste à faire une fois, à
   la main sur un appareil connecté : `GET /api/entitlements/status` doit renvoyer
   `is_active: true` avec le `minutes_remaining` du tier.

Le Test Store et ses 3 produits `*_test` **restent en place** :
`mobile/.maestro/07_paywall.yaml` en dépend via `E2E_REVENUECAT_TEST_KEY`. Ils
sont rattachés aux entitlements de tier comme n'importe quel autre produit.

### Phase 7 — CI/CD (jour 6-7)

1. ✅ Workflows versionnés :
   - `.github/workflows/pr.yml` — backend `ruff`/`mypy`, mobile `typecheck`/`lint`.
   - `.github/workflows/main.yml` — checks sur push `main`.
   - `.github/workflows/deploy-lambda.yml` — build/push image Lambda + update functions.
   - `.github/workflows/mobile-build-distribute.yml` — EAS build/submit.
   - `.github/workflows/mobile-store-promote.yml` — promotion stores.
   - `.github/workflows/mobile-e2e-maestro.yml` — Maestro Android/iOS.
2. ⚠️ **État source** : `origin/main` est sur `30cf62c`, `main` local sur
   `e78ce1b` — **43 commits d'avance non poussés, dont 10 backend/infra**
   (cf. § « État de vérité »). Les runs GitHub portent donc sur un état vieux
   de quatre jours.
3. ✅ **Main checks verts** (`task-223`, `task-227`, `task-228`) : `Main Branch
   Checks` est `success` sur tous les push récents. Le pin sur `uv.lock`
   (`c05df88`) a fermé la dernière faille de ce gate — jusque-là la CI installait
   depuis les intervalles de `pyproject.toml` et pouvait donc linter avec un
   `ruff`/`mypy` différent de celui du lock et du poste owner.
4. **Mobile build workflow — désarmé le 2026-08-13** (`task-258`) :
   `.github/workflows/mobile-build-distribute.yml` ne se déclenche plus que sur
   tag `mobile-v*` (build `production` + `eas submit`) ou `workflow_dispatch`
   (défauts `preview` / `submit=false`). Le couple `branches: [main]` + `paths:`
   du trigger `push` est supprimé : un push sur `main` ne construit plus rien et
   ne peut plus soumettre au store. L'étape de notification n'utilise plus que le
   label `bug` (le label `ci/cd` n'existe pas et faisait échouer
   `gh issue create`), le workflow déclare `permissions` (`contents: read`, plus
   `issues: write` sur `notify-failure`), et les deux jobs de build commencent par
   une garde `Require EXPO_TOKEN` qui échoue en quelques secondes avec un message
   explicite. **Reste à faire, owner uniquement** : créer un robot token sur
   https://expo.dev/settings/access-tokens puis `gh secret set EXPO_TOKEN`. Sans
   ce secret le workflow est inoffensif mais non fonctionnel. Contrat de
   déclenchement détaillé dans `mobile/MOBILE_CI_CD.md`.
5. **Secrets GitHub** : six configurés, dont les cinq requis par Maestro
   (`E2E_TEST_USER_EMAIL`/`_PASSWORD`, `E2E_SEARCH_TEST_TERM`,
   `E2E_REVENUECAT_TEST_KEY`, `E2E_REVENUECAT_APPLE_KEY`). Ajouter encore
   `EXPO_TOKEN`, Apple/App Store Connect et le service account Google Play pour
   les workflows de distribution.
6. ✅ **Variables EAS** : les trois environnements sont peuplés (constaté le
   2026-08-13) et `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` y porte la vraie clé
   `goog_` depuis le 2026-09-01 (`task-238`), en remplacement du placeholder.
7. **Maestro CI** : **en sommeil depuis le 2026-08-13** (`task-254`). Plus aucun
   déclenchement automatique ; `workflow_dispatch` est le seul point d'entrée.
   Ce n'est plus un gate de release. État des flows et plan de réactivation dans
   la section ci-dessous. À noter : le dernier run automatique, sur `9cb9da5`, est
   rouge — c'est cohérent avec la mise en sommeil, pas une régression à traiter.
8. ✅ **Branch protection** : **configurée** le 2026-08-13 (`task-257`) en régime
   léger — force-push et suppression refusés sur `main`, `enforce_admins: false`,
   `required_linear_history: false`, et **aucun** required status check ni
   required review. Volontairement pas de `Main Branch Checks` dans les required
   checks : ce workflow ne se déclenche que sur `push: main` et ne tourne jamais
   sur une PR, il resterait donc `expected` pour toujours. Même raison pour
   `Mobile E2E Tests (Maestro)`, en sommeil sur `workflow_dispatch` depuis
   `task-254`. Et des required checks s'appliqueraient aussi aux pushes directs,
   qui sont le flow réel (merge local puis push).
9. Vérifier le rollback Lambda avec deux images API/worker immuables après
   `task-217`, puis documenter l'exercice.

#### Maestro E2E CI — en sommeil depuis le 2026-08-13

**Déclencheur de réactivation** : l'UI est figée, c'est-à-dire qu'aucune refonte
d'écran n'est plus prévue. C'est un jalon produit, pas une date. Les flows
vérifient la copie affichée et des `testID` (`Welcome back`, `Good .*`,
`Continue learning`/`Recently added`, `AI Artifacts`, `Choose Your Plan`,
`Reader`/`Mix`/`Audio-Heavy`, `paywall-screen`, `search-result-card`…) : tant
qu'un écran peut bouger, chaque itération de design casse des selectors et la
remise au vert est à refaire. Illustration : `task-307` a remplacé la liste
verticale de l'Inbox par deux rangées de tuiles, ce qui a périmé l'ancien
sélecteur `YOUR MEDIA` cité ici jusqu'au 2026-08-21.

**Ce qui dort** : uniquement les déclencheurs automatiques `push` (branches
`main`, `second-brain-project`) et `pull_request` de
`.github/workflows/mobile-e2e-maestro.yml`, tous deux filtrés sur `mobile/**`.
Ils sont commentés en place ; les restaurer consiste à retirer les marqueurs de
commentaire. `workflow_dispatch` reste intact avec ses deux inputs `platform`
(`android`/`ios`/`both`) et `flow_filter`.

**Ce qui reste provisionné** — rien n'est à recréer à la réactivation :

- les 7 flows de `mobile/.maestro/`, leurs sous-flows `utils/` et la suite
  `suites/tasks_168_170.yaml` ;
- les runners `.github/scripts/run-android-maestro.sh`,
  `run-ios-maestro.sh` et `.github/scripts/lib/maestro-flows.sh`, ainsi que les
  jobs `android-e2e`, `ios-e2e` et `e2e-summary` ;
- les secrets GitHub Actions `E2E_TEST_USER_EMAIL`, `E2E_TEST_USER_PASSWORD`,
  `E2E_SEARCH_TEST_TERM`, la clé publique RevenueCat Test Store
  `E2E_REVENUECAT_TEST_KEY` et l'override optionnel `E2E_API_BASE_URL` ;
- la fixture persistante sur AWS dev : l'article « Commonplace book », arrivé
  `ready_for_artifacts` et indexé Algolia, rattaché au compte de test.

**État réel des 7 flows au 2026-08-13** — c'est l'information qui coûterait le
plus cher à reconstituer plus tard :

| Flow | État | Détail |
|---|---|---|
| `01_login` | ✅ Vert | Émulateur Android API 33 **et** simulateur iOS 18.5, run `31612429695` (`workflow_dispatch` du 2026-08-12) |
| `06_search` | ✅ Vert | Idem — s'appuie sur la fixture « Commonplace book » indexée Algolia |
| `07_paywall` | ✅ Vert | Idem — vérifie l'affichage des trois tiers, aucun achat déclenché |
| `02_share_intake` | ⏸️ Neutralisé volontairement | Réduit à un smoke test auth, tag `skipped`. Le share natif n'est pas pilotable par Maestro (share sheet hors process). Un fallback Appium ciblé est décrit dans `mobile/E2E_TESTING.md`, à n'activer que si une release est bloquée par cette incertitude |
| `03_inbox_visibility` | ❌ Cassé, jamais exécuté en CI | Amorce par `openLink: "media-summarizer://share?url=…"` puis attend `assertVisible: "Save Link"`. Depuis le 2026-06-11, `redirectSystemPath` dans `mobile/app/+native-intent.tsx` teste `path.includes("://share?")` et redirige vers `/(tabs)/inbox` : « Save Link » n'apparaît jamais, le flow échoue à sa première assertion non optionnelle |
| `04_media_detail_progression` | ❌ Cassé, jamais exécuté en CI | Même amorce, même cause |
| `05_artifact_trigger_action` | ❌ Cassé, jamais exécuté en CI | Même amorce, même cause, plus quatre défauts propres listés ci-dessous |

Le run vert du 2026-08-12 a évité 03/04/05 en passant
`flow_filter: suites/tasks_168_170` : les trois flows verts sont donc les seuls
validés, et « suite verte » n'a jamais voulu dire « 7 flows verts ».

**Travail à prévoir à la réactivation**, en distinguant le réamorçage des bugs
de flow déjà identifiés :

1. **Réamorcer 03/04/05 sur la fixture persistante** (« Commonplace book »,
   `ready_for_artifacts`, indexée Algolia) au lieu de simuler un share par deep
   link : se loguer, atteindre l'item depuis l'inbox ou la recherche, et
   dérouler le scénario à partir de là. Effet de bord bénéfique sur 05 :
   `mediaReady` est vrai d'emblée, ce qui supprime l'attente de 120 s sur
   l'apparition du bouton `Generate`.
2. **Corriger quatre défauts du flow 05**, indépendants de l'UI et donc à
   traiter même après refonte :
   - `tapOn: text: "Generate", index: 0` est ambigu : les cinq tuiles rendent un
     bouton dont le texte est exactement `Generate`
     (`mobile/app/media/[id].tsx:1032`) et l'index se décale dès qu'une tuile
     est `ready`. Cibler l'`accessibilityLabel` `Generate Summary`, déjà exposé
     par le composant.
   - `assertVisible: text: "Summary"` est ambigu avec la tuile
     `Detailed summary`.
   - Aucun `assertNotVisible: "Failed"` après le tap, alors que l'UI rend
     `Failed` + `Retry` en cas d'échec : le flow brûle 180 s d'attente avant de
     tomber sur un diagnostic inutile.
   - L'`extendedWaitUntil` sur la regex `Queued|Generating|Ready` peut être
     satisfait d'emblée par une autre tuile déjà `ready`, et le `tapOn: "View"`
     sans index ouvrirait alors le mauvais artifact.
3. **Reprendre la cible finale**, portée par deux tâches déjà au backlog :
   - `task-171` a été clôturée `Done` le 2026-08-13 sur les 3 flows validés ;
     ses notes consignent ce qui manque (run complet des 7 flows, vert sur les
     deux plateformes).
   - `task-172` (Android bloquant sur PR, iOS en nightly/manuel) est verrouillée
     `dispatchable: false` jusqu'à ce jalon — la déverrouiller consiste à
     retirer cette ligne de son front-matter.

**Contrainte de budget CI, inchangée** : l'owner n'a pas de Mac, donc toute
exécution iOS passe par un runner macOS GitHub Actions, facturé x10 sur les
minutes Actions, sur le plan gratuit (2000 min/mois → ~200 min réelles de
macOS). iOS ne redevient donc **jamais** un required check par PR : Android sur
`ubuntu-latest` couvre les régressions logiques, iOS reste manuel ou nightly.

### Phase 8 — Monitoring & observabilité (jour 7-8)

> Le provisioning Terraform de dashboard/alarms a été ajouté (`task-114`, `task-46`), puis adapté à la migration Lambda, puis complété par `task-242` et `task-243`. La validation restante est opérationnelle : réveiller les alarmes en prod et vérifier les signaux CloudWatch réels.
>
> **État 2026-08-13** : AWS retourne toujours **0 alarme active**, mais c'est
> désormais **une conséquence des interrupteurs de coût, pas un trou de
> provisioning** : `enable_alarms = false` en dev (économie assumée) et les trois
> interrupteurs à `false` en prod tant qu'elle est en veille. Le réveil est un
> `apply` de trois booléens, ~7,20 $/mois (1 topic SNS + 43 alarmes ≈ 3,30 $,
> 1 dashboard ≈ 3,00 $, 14 mappings SQS ≈ 0,90 $). Le tableau par environnement est
> dans `infrastructure/terraform/README.md`, section « Cost switches ».
>
> Deux ajouts récents à valider au réveil :
> - `task-242` — l'archiveur de jobs est **réellement déployé** (code réel à la
>   place du placeholder, 4 jobs archivés dans
>   `s3://media-summarizer-archives-…-dev/2026/08/13/`), le TTL de
>   `processing_jobs-dev` est **ENABLED** (variable `processing_jobs_ttl_days`,
>   défaut 90 j) et l'alarme `job_archiver_silent_failure` est câblée et
>   *fireable*. La fenêtre TTL définitive reste à trancher par l'owner (AC #3).
> - `task-243` — `user_media` est branché sur la rétention, la suppression, le
>   backup et l'observabilité ; `docs/DATA_RETENTION.md` est le document de
>   référence des deux horloges (la bibliothèque d'un utilisateur n'a **pas**
>   d'horloge de rétention), et `scripts/check_purge_at_writers.py` fait échouer la
>   CI si un second écrivain de `purge_at` apparaît.

1. CloudWatch Dashboard à vérifier avec :
   - Latence API (`API_SLOW_REQUEST_THRESHOLD_MS` → alarmes)
   - Profondeur des queues SQS (alarme si DLQ > 0, en particulier `document-parsing-queue`)
   - Taux d'erreur Deepgram / OpenAI / **LlamaParse / Unstructured** (logs structurés `parser=llamaparse|unstructured` + `error_code`)
   - Coût par source (X, TikTok, Instagram, YouTube, podcasts, **documents**)
   - Compteur quota LlamaParse (1000 pages/jour free tier) — alarme si fallback Unstructured déclenché plus de N fois/heure
2. CloudWatch Alarms → SNS → e-mail (`enable_alarms = true` en staging/prod).
3. Vérifier que les logs structurés tombent bien dans CloudWatch Logs Insights.

### Phase 9 — ~~Staging end-to-end~~ → **Validation prod avant ouverture** (jour 8-9)

> **Cette phase a changé de nature le 2026-08-12** (décision owner, cf. `task-248`).
> Il n'y a **plus d'environnement staging** : pour un développeur solo, en
> maintenir un troisième n'apportait rien, et il était de toute façon vide. Le
> couple retenu est **dev + prod dans deux comptes AWS séparés**. `envs/staging/`
> reste au dépôt uniquement comme référentiel permettant de remonter un staging
> **jetable** avant une migration risquée (c'est aussi le seul cas où la couche 4
> de `tf_plan_guard.sh` retrouve son utilité).
>
> Les étapes de validation ci-dessous ne disparaissent pas — elles se font
> désormais **contre prod, avant de l'ouvrir aux utilisateurs**, puisque prod
> existe déjà et n'a jamais servi de trafic.

0. ✅ **Isolation débloquée** : `task-237` + `task-248`, cf. Phase 3.
1. ✅ **L'environnement cible existe** : 199 ressources dans le compte
   `866874944541`, health `HTTP 200`. Il est en veille et son secret est vide.
2. **Peupler le secret runtime prod** (`task-252`, owner) puis réveiller les trois
   interrupteurs de coût. Sans ça, aucune des étapes suivantes n'a de sens.
3. **Lever le plafond de concurrence** : quota `L-B99A9384` (10 → 1000) en
   attente ; retirer ensuite `api_reserved_concurrency = -1` de
   `envs/prod/main.tf` et rappliquer.
4. Créer le vrai endpoint/domaine prod (`api.secondbrainlabs.com`, cf. Phase 10
   §0bis) et l'injecter dans EAS + Maestro.
5. Tester depuis un device physique avec une URL réelle de chaque source.
6. Vérifier qu'aucun credential de dev n'a été recopié dans prod (`task-252`
   l'interdit explicitement).
7. Charger 50-100 URLs en parallèle pour vérifier le scaling SQS / Lambda —
   **après** la levée du quota, sinon la mesure ne mesure que le throttling.
8. Vérifier RevenueCat sandbox → backend webhook contre prod.
9. Mesurer cold/warm API, profondeur SQS, DLQ et coût avant ouverture.

### Phase 10 — Pré-lancement (jour 10+)

0. **Rebrand mobile placeholder name** (cf. task-186) — l'app utilise actuellement le nom legacy `Media Summarizer` partout (display name, slug Expo, scheme deep link, share extension iOS). À exécuter **avant** la sous-étape 1 ci-dessous : tous les textes Apple App Store Connect (App Information, screenshots) et Google Play Console + Google OAuth Branding consomment le nom marketing définitif. Coût ~30 min en pré-distribution, beaucoup plus élevé une fois publié. Ne touche pas le bundle id `com.secondbrainlabs.core` (figé). Voir `task-186` pour la checklist exacte des 8-9 endroits à mettre à jour.

0bis. **Couper l'API du custom domain `api.secondbrainlabs.com`** — pendant le dev (Phase 5), l'app mobile + Apple Sign-In Service ID + `APPLE_REDIRECT_URI` côté backend tapent tous l'URL brute API Gateway `https://jji077bi8e.execute-api.eu-west-3.amazonaws.com`. En Phase 10, on bascule sur le custom domain. Étapes :
   - **État 2026-08-13** : `secondbrainlabs.com` **résout** désormais, mais renvoie
     un `301` vers `sbl.so` (site tiers), et `sbl.so/privacy` comme `sbl.so/terms`
     répondent **404**. `api.secondbrainlabs.com` et `api.mediasummarizer.com`
     sont toujours en `NXDOMAIN`. Le profil EAS production pointe toujours vers
     `https://api.mediasummarizer.com`. Décider d'abord **quel domaine porte le
     produit** — la redirection vers `sbl.so` suggère que `secondbrainlabs.com`
     n'est pas (ou plus) dédié à cette app —, puis appliquer les étapes ci-dessous
     sur le domaine retenu.
   - Le sous-domaine API doit être créé **et** les pages `/privacy` et `/terms`
     réellement servies sur ce même domaine : Apple et Google exigent une URL de
     politique de confidentialité publiquement atteignable, un `404` derrière une
     redirection est un motif de rejet.
   - Le support Terraform existe déjà dans `infrastructure/terraform/modules/platform/lambda_api.tf` (`api_custom_domain`, `api_zone_id`, `aws_acm_certificate`, API Gateway domain mapping, Route53 record conditionnel) : les ressources sont conditionnées par `count` sur ces deux variables, donc vides tant qu'elles ne sont pas renseignées.
   - Passer `api_custom_domain = "api.secondbrainlabs.com"` et `api_zone_id` au bloc `module "platform"` de `infrastructure/terraform/envs/prod/main.tf`, puis `terraform -chdir=infrastructure/terraform/envs/prod apply`.
   - Créer/valider le DNS Cloudflare ou Route53 selon la zone réellement utilisée. Si Cloudflare reste le DNS autoritaire, créer le CNAME vers le `target_domain_name` exposé par Terraform.
   - `terraform apply` puis vérifier `curl https://api.secondbrainlabs.com/api/auth/apple/callback` → HTTP 302.
   - **Apple Developer Portal** → Identifiers → Service IDs → `com.secondbrainlabs.core.signinwithapple` → Configure → ajouter Domain `secondbrainlabs.com` (déjà présent) et Return URL `https://api.secondbrainlabs.com/api/auth/apple/callback` (déjà présent), **retirer** les entrées `jji077bi8e.execute-api.*` ajoutées en Phase 5.
   - **AWS Secrets Manager** → mettre à jour `APPLE_REDIRECT_URI` vers `https://api.secondbrainlabs.com/api/auth/apple/callback`.
   - **`mobile/eas.json`** → profile `development` et `preview` :
     `EXPO_PUBLIC_API_BASE_URL` repasse à
     `https://api.secondbrainlabs.com`. Attention : le profile `production`
     pointe encore vers `https://api.mediasummarizer.com` au 2026-07-31 ;
     l'aligner sur le domaine choisi avant build production.
   - Rebuild EAS dev + preview pour propager la nouvelle URL aux binaires.

1. **Apple App Store Connect** (appstoreconnect.apple.com) :
   - **App Information** : nom marketing affiché aux users (à figer en Phase 10 ; ≠ Bundle ID `com.secondbrainlabs.core`), sous-titre (30 chars max), catégorie primaire/secondaire, contact info, copyright. C'est l'équivalent Apple du "Branding" Google OAuth.
   - **Pricing & Availability** : free vs paid, pays/régions, App Store distribution.
   - **App Privacy** : remplir le questionnaire détaillé sur les données collectées + leur usage. Apple est strict — toute imprécision peut entraîner un rejet ou un retrait post-launch.
   - **App Review Information** : compte de démo (login + password) pour le reviewer Apple, notes éventuelles, contact.
   - **Version 1.0** : screenshots (5 par device-size requis : 6.9", 6.5", iPad), description (4000 chars), promotional text, mots-clés (100 chars), URL support, URL marketing, URL politique de confidentialité publiquement hébergée.
   - **Build** : sélectionner la build TestFlight déjà uploadée + validée. Elle doit venir du profil EAS **`production`**, jamais `internal` : `internal` porte `EXPO_PUBLIC_API_BASE_URL` = API dev (`jji077bi8e.execute-api...`), c'est le profil des builds de test TestFlight. Vérifier au passage que l'URL du profil `production` est bien le domaine retenu en 0bis.
   - **Soumettre pour review** (1-3 jours, parfois plus).
2. **Google Play Store** :
   - Play Console : assets, description, classification, politique de confidentialité.
   - Closed Testing → Open Testing → Production rollout.
3. **Google Auth Platform (OAuth consent screen → Audience)** :
   - Vérifier le **Branding** : App name = nom marketing (ex. `Second Brain`, **pas** le nom interne du projet GCP), logo, support email, developer contact email.
   - Confirmer que les **scopes** demandés sont uniquement `openid`, `email`, `profile` (non-sensitive). Si d'autres scopes sont ajoutés (Drive, Gmail, etc.), prévoir 4-6 semaines de **vérification Google** + politique de confidentialité publique + vidéo de démo.
   - Section **État de la publication** : cliquer **« Publier l'application »** pour passer de `Test` (limité aux 100 utilisateurs whitelistés) à `Production` (n'importe qui peut se connecter avec Google).
   - Pour les scopes basiques (notre cas), la publication est immédiate sans validation Google supplémentaire — un avertissement "App non vérifiée" peut apparaître initialement chez certains users, à monitorer.
4. **Légal** — les textes sont **rédigés au dépôt**, ce qui reste est l'hébergement
   et le câblage in-app. Présents depuis le 2026-08-12 :
   `docs/compliance/privacy-policy.md`, `terms-of-service.md`,
   `apple-app-privacy.md` (réponses au questionnaire App Privacy),
   `google-play-data-safety.md` et `CHECKLIST.md`.
   - Politique de confidentialité hébergée publiquement — **pas fait** : le
     chemin `/privacy` répond 404 derrière une redirection (cf. §0bis).
   - CGU avec mention RevenueCat / abonnements — texte prêt, hébergement à faire.
   - Conformité RGPD : droit à l'oubli **implémenté** (cf. ci-dessous) ; accès et
     portabilité traités manuellement par mail sous un mois.
   - Ajouter les liens Privacy/Terms sur login/register et Account.
   - **Fait (`task-224`, 2026-08-12)** : suppression de compte in-app
     (Account > Delete Account → `DELETE /api/account`) qui purge DynamoDB, S3 et
     l'index Algolia ; l'ancienne `DELETE /api/v1/users/{user_id}`, qui ne
     supprimait que la ligne `users`, est supprimée. Le bouton `Export Data` mort
     est retiré, l'accès (art. 15) et la portabilité (art. 20) sont traités
     manuellement par mail sous un mois, documenté en privacy policy §8.
   - **Prérequis déploiement** : appliquer Terraform (`s3:DeleteObject` sur le
     bucket bug-reports) **avant** de déployer l'API, sinon tout user ayant joint
     une capture d'écran reçoit un 500 au lieu d'une suppression. En dev, le code
     est déployé depuis le 2026-08-13 et `task-253` a corrigé le 404 de la route ;
     à revérifier lors du réveil de prod.
   - **État 2026-08-21, inchangé** : `secondbrainlabs.com/privacy` et `/terms`
     renvoient un `301` vers `sbl.so/...`, qui répond **404**.
     `api.secondbrainlabs.com` et `api.mediasummarizer.com` sont en `NXDOMAIN`.
5. **Site landing minimal** (optionnel) : `<your-domain>` avec CTA App Store / Play Store.
6. **Soft launch** : un seul pays, 100 users, observer 1 semaine avant rollout global.

---

## 5. Ce qui reste **bloqué** sur des credentials externes / owner-only

Les comptes principaux sont largement provisionnés. Les blocages restants sont surtout liés aux stores, aux builds EAS interactifs et aux dashboards tiers.

- [x] AWS account + IAM admin user `second-brain-app-admin` (AdministratorAccess) + alarme billing $50/mois (us-east-1) configurée
- [x] Organisation AWS `o-7sf5u7j5hd` + compte membre prod `866874944541` créés au
  2026-08-13 (`task-248`), profil `[profile prod]` ajouté hors dépôt dans
  `~/.aws/config`. **Irréversibles** : une organisation ne se supprime qu'après
  sortie de tous ses comptes membres, et un compte AWS ne se supprime pas avant
  90 jours de fermeture
- [ ] **Les 37 credentials runtime vivants du secret prod** (`task-252`, owner uniquement,
  `dispatchable: false`) — prod est une coquille vide sans eux : ni transcription,
  ni résumé, ni résolution, ni recherche, ni achat, ni session utilisateur valide
- [ ] **Quota Lambda concurrence du compte prod** : demande `L-B99A9384` (10 → 1000)
  `PENDING` côté AWS. Retirer ensuite `api_reserved_concurrency = -1` de
  `envs/prod/main.tf` et rappliquer
- [x] Apple Developer Program payé ($99) au 2026-06-01, validé par Apple
- [x] **Apple Sign in with Apple Service ID + Key (.p8) + App ID + Team ID + Key ID** provisionnés au 2026-06-08 (cf. Phase 2.8) — toutes les vars Apple dans `.env` renseignées : `APPLE_CLIENT_ID` (Service ID), `APPLE_PRIVATE_KEY` (PEM single-line), `APPLE_REDIRECT_URI` prod, `APPLE_TEAM_ID`, `APPLE_KEY_ID`.
- [ ] Google Play Console payé ($25) au 2026-06-01 — **sept portes d'éligibilité
  du compte, deux franchies au 2026-08-31** : accès à un appareil Android
  physique ✅ 2026-08-31 (via l'app mobile Play Console) et numéro de téléphone de
  contact ✅ 2026-08-31. Restent ouvertes : identité développeur, profil de
  paiement Google Payments, adresse développeur publique, closed testing
  ~12 testeurs / 14 jours, et l'enregistrement des noms de packages (échéance
  Google 2026-09-30 — automatique via Play App Signing, à revérifier en Phase 10).
  Cf. Phase 2.2 et `task-260`
- [x] Google Cloud Console : projet `media-summarizer` créé, OAuth consent screen configuré (Branding `Second Brain`, External, scopes openid+email+profile), mode Test avec utilisateur test ajouté, **3 OAuth Client IDs créés (Web backend + iOS + Android au 2026-08-13)** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` dans `.env` racine ; `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` + `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` dans `mobile/.env` (naming aligné avec `mobile/app.config.ts`, corrigé 2026-06-08)
- [x] Google Cloud Console **Android OAuth Client IDs — les deux** :
  - le 2026-08-13 (`task-163`), `package=com.secondbrainlabs.core` + SHA-1 du
    keystore EAS `38:D5:13:F4:2F:A9:DA:74:2F:A1:39:E3:17:9A:22:A8:59:58:DD:FD`,
    qui couvre les APK installés à la main ;
  - le 2026-09-02, même package + SHA-1 **Play App Signing**, qui couvre tout
    binaire servi par Play (piste interne, closed testing, production). C'est ce
    second client qui a débloqué le sign in with Google sur device.

  Aucun de ces IDs n'entre dans le bundle : `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`
  a été supprimée par `task-325`, Credential Manager prend le client **Web** comme
  `serverClientId`
- [ ] Google Cloud Console **publication OAuth (Test → Production)** à faire en Phase 10 juste avant le lancement
- [x] X Developer App approuvée + bearer token (en local dans `.env`)
- [x] Apify API tokens + actor IDs obtenus — en local dans `.env` (Instagram Reel/Post, YouTube, TikTok selon fallback chain)
- [x] LlamaParse API key obtenue (free tier 1000 pages/jour) — en local dans `.env`
- [x] Unstructured.io API key obtenue (15 000 pages gratuites au démarrage) — en local dans `.env`
- [x] PodcastIndex API key + secret obtenus (en local dans `.env`)
- [x] OpenAI API key + budget configuré (en local dans `.env`)
- [x] Deepgram API key + budget configuré (en local dans `.env`)
- [x] Algolia App créée (App ID + Admin API key en local dans `.env`). **Pas de
  variable de nom d'index ni de search-only key** : l'index vaut
  `media_items_{ENVIRONMENT}`, calculé par `utils/algolia_client.py`, et la
  recherche est proxifiée par le backend (`task-312`)
- [x] RevenueCat — **circuit d'achat réel validé sur les deux stores** (`task-262`,
  `task-238`, `task-261` toutes `Done`). Play le 2026-09-01, App Store le 2026-09-02 :
  `revenucat_events-dev` porte 32 événements et `subscriptions-dev` un abonnement iOS
  actif au tier `M`. Le `REVENUCAT_WEBHOOK_SECRET` est donc validé par l'usage, et non
  plus par la sonde `401`. L'offering `default`, ses 3 packages de tier et les 3
  entitlements existent, chacun servi par trois produits — un par store. Côté iOS les
  3 abonnements existent en ASC dans le groupe `Second Brain Plans` et la clé App
  Store Connect est déposée dans RevenueCat ; côté Play, 3 abonnements avec forfait de
  base actif et testeur de licence configuré. Côté app, les entrées UI existent
  (`task-244` : CTA d'upgrade dans Account + déclenchement sur refus de quota ;
  `task-245` : l'état d'abonnement est consommé par l'UI). Reste une seule
  vérification, à la main sur un appareil connecté : la propagation vers les quotas,
  c'est-à-dire `GET /api/entitlements/status` qui renvoie `is_active: true` et le
  `minutes_remaining` du tier
- [x] Pricing admin secret généré au 2026-06-08 (`PRICING_ADMIN_SECRET` en local dans `.env`, requis pour `PUT /api/pricing/admin`)
- [x] Build iOS EAS **de distribution store** : `790af106-040c-4798-9599-68ad5b6f0770`,
  profil `internal`, `distribution: store`, 1.0.0 build **2**, commit `ca9cadb`,
  terminée le **2026-09-01 20:07**. Poussée vers App Store Connect par EAS Submit
  (`25324d9b-6bd2-46ab-8fa3-c0bbc541c462`, ASC App ID `6778072060`) le
  **2026-09-02 11:54**, statut `finished`, et **distribuée en TestFlight à un beta
  testeur qui a installé l'app**. Le build n'est donc plus un bloquant : la 1.0 a un
  binaire à sélectionner. Ce qui reste avant `Add for Review`, ce sont les
  métadonnées de version — cf. la sous-étape 3 de Phase 6 et l'hébergement des URLs
- [ ] EAS iOS **development** build courante : la dernière est du 2026-08-23
  (`cd22ba7a`), donc postérieure au HEAD de `task-161` mais pas au HEAD actuel. Sans
  objet pour la soumission ; utile seulement pour un dev client sur device
- [x] SHA-1 keystore Android via `eas credentials`, sans build (`task-162`,
  2026-08-13) — aucun build consommé, cf. notes de `task-162`
- [x] Build Android EAS : deux AAB produits le **2026-09-01** avec le profil
  `internal` (`versionCode` 4 puis 5), keystore géré par EAS, API dev. Le 5 est
  sur la piste de test interne Play ; le 4 portait encore le placeholder de clé
  RevenueCat. Aucune build de profil `development` n'a été consommée
- [x] Variables EAS development/preview/production : les trois environnements sont
  peuplés, et `EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY` y porte la vraie clé `goog_`
  depuis le **2026-09-01** (`task-238`). Elle y valait le placeholder jusque-là,
  ce qui rendait tout AAB inexploitable pour la facturation — le profil `internal`
  résout l'environnement `production` et les `EXPO_PUBLIC_*` sont figées à la
  compilation
- [ ] Nom marketing final : requis avant `task-186`, App Store Connect, Play Console et Google OAuth Branding
- [ ] Icônes finales : `task-180`, requis avant soumission stores
- [ ] Domaines : décider quel domaine porte le produit (`secondbrainlabs.com`
  redirige aujourd'hui vers `sbl.so`), puis rendre le sous-domaine API, `/privacy`,
  `/terms` et l'URL support réellement publics avant la build production
- [x] Architecture LLM production : **tranché** — `owner_decision: abandoned` sur le
  benchmark `task-212` ; `task-212` et `task-213` sont archivées, le statu quo
  OpenAI direct est assumé pour V1
- [x] Branch protection sur `main` : **tranché et appliqué** le 2026-08-13
  (`task-257`) — régime léger, force-push et suppression refusés, aucun required
  check ni required review pour ne pas casser le flow merge local + push direct

---

## 6. Risques connus

| Risque | Mitigation |
|---|---|
| Apple rejette l'app car Google login présent sans Sign in with Apple | Sign in with Apple câblé côté mobile. À vérifier sur build TestFlight avant soumission. |
| Quota Deepgram explosé par un user TikTok abusif | Rate limiter TikTok 2-tier déjà en place + quota par user **compté en minutes réelles** (`task-251`, `task-287`), les minutes audio n'étant facturées qu'une fois par user et par média. |
| Apify API down | **Risque nettement plus lourd depuis `task-309`/`310`** : Apify est le chemin **unique** de YouTube et d'Instagram, et le fallback IP-block de TikTok. Une panne Apify met donc trois sources sur quatre à `failed` (visible, sans cascade). Surveiller en CloudWatch ; Apify corrige ses scrapers en 24-72 h en général. |
| Quota LlamaParse free tier (1000 pages/jour) dépassé | Fallback Unstructured automatique dans le worker `document_parsing`. Si Unstructured aussi épuisé : job `failed` avec message clair, surveiller en CloudWatch. |
| RevenueCat webhook drop | Réconciliation possible via `GET /api/entitlements/status` qui requête RevenueCat directement. Le drop *silencieux* aujourd'hui possible (tier non résolu → `warning` puis `return`, sans alarme) est traité par `task-262` : résolution par entitlement, et log `error` explicite quand elle échoue. |
| URL X privée / supprimée | Worker X retourne `failed` proprement, message d'erreur à l'utilisateur. |
| ~~API interactive indisponible après longue inactivité~~ | **Traité** (`task-217`, 2026-08-06) : image API minimale, reserved concurrency configurable, warm-up EventBridge, health gate de release. Cold 5,2 s / warm 1,0 s au 2026-08-13. |
| ~~Collision/destruction entre dev/staging/prod~~ | **Traité** (`task-237`, `task-248`) : une racine Terraform par environnement, 100 % des noms suffixés, et surtout **une frontière de compte AWS** entre dev et prod — un plan lancé avec les identifiants de prod ne peut rien toucher dans dev. |
| ~~CRUD users legacy non authentifié~~ | **Traité** (`task-222`, `task-224`, `task-253`) : surface legacy supprimée, `DELETE /api/account` déduit le compte du token et purge DynamoDB + S3 + Algolia, startup guard contre les routes silencieusement absentes. |
| État local non poussé sur GitHub | **Aggravation au 2026-09-02** : `main` local est sur `e78ce1b`, `origin/main` sur `30cf62c` — **43 commits d'écart, dont 10 backend/infra**, contre un seul au 2026-08-21. Le runtime dev n'est donc pas le HEAD, et le fix de matching webhook de `task-334` n'a jamais tourné en vrai : les achats sandbox du 2026-09-01/02 ont été traités par le code d'avant. Le risque n'est pas théorique, il se répète — pousser après chaque session de merge, avant tout run E2E. |
| Dérive silencieuse entre l'image Lambda et le lockfile | **Cause de l'incident du 2026-08-13** (API dev 500 sur toutes les routes, ~2 h 20) : les Dockerfiles résolvaient les intervalles de `pyproject.toml` au build, donc chaque build produisait une image différente et aucune exécution locale ne pouvait reproduire le bug. Mitigation : installer depuis `uv export --frozen` — **fait partout depuis `c05df88`** (les trois images et les deux workflows). Le risque n'est pas éteint pour autant : `f06bd62` a dû plafonner `pillow` sous 12.3 pour que l'image worker se construise à nouveau. |
| Un health check vert lu comme « l'environnement fonctionne » | `GET /api/health/` ne teste que DynamoDB via le rôle IAM. Prod répond `200` avec un secret runtime **vide**. Ne jamais s'en servir comme preuve qu'un environnement est opérationnel — seul un E2E complet l'établit. |
| Prod ouverte alors qu'elle est en veille | Trois booléens (`enable_alarms`, `enable_dashboard`, `enable_worker_polling`) à repasser à `true`, plus le quota de concurrence et le secret runtime. Une prod servant de vrais utilisateurs sans alarmes est une faute ; la veille n'est acceptable qu'avant lancement. |
| CI donnant un faux sentiment de sécurité | Gates verts au 2026-08-21. Rester vigilant sur trois points : ne pas remettre de `|| true`, ne pas mettre le workflow Maestro en sommeil dans les required checks, et pin les outils via `uv.lock` pour que la CI lint avec les mêmes versions que le poste owner. |
| Build mobile sans secrets runtime | Les trois environnements EAS sont peuplés et portent la vraie clé `goog_` depuis le 2026-09-01 ; restent `EXPO_PUBLIC_REVENUCAT_APPLE_KEY` (seulement dans `mobile/.env`) et `EXPO_TOKEN` côté GitHub Actions. Une variable `EXPO_PUBLIC_*` étant inlinée à la compilation, un placeholder côté EAS produit un binaire silencieusement inerte : l'AAB `versionCode` 4 a dû être jeté pour cette raison. `mobile/.env` gitignored ne constitue pas une configuration de build distante. |
| Domaine/légal indisponible | Textes légaux rédigés (`docs/compliance/`) mais **non hébergés** : `/privacy` et `/terms` répondent 404 derrière une redirection vers `sbl.so`. Trancher le domaine, héberger, puis vérifier les URLs depuis un réseau externe avant soumission. |
| ~~Branch protection indisponible~~ | **Traité** (`task-257`, 2026-08-13) : `main` refuse le force-push et la suppression. Régime léger assumé — pas de required check, parce qu'un required check s'applique aussi aux pushes directs et que `Main Branch Checks` ne tourne jamais sur une PR. Rollback : `gh api -X DELETE repos/:owner/:repo/branches/main/protection`. |
| Repo public et fuite d'identifiants | Le dépôt est public depuis peu. `task-255` et `de3ac86` ont purgé l'email de login et l'identité de compte des fichiers suivis ; l'email racine du compte AWS prod est volontairement absent du dépôt. Tout ajout de credential dans un fichier suivi est désormais une fuite publique immédiate. |

---

## Appendice A — Commandes utiles

```bash
# Build mobile dev
cd mobile && npx expo prebuild
eas build --platform ios --profile development

# Build mobile preview (TestFlight / Internal)
npm run build:ios:preview
npm run build:android:preview

# Run E2E contre AWS dev (Phase 4)
API_BASE_URL=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com pytest -m e2e

# Lint & type checks
ruff check .
mypy media_summarizer
cd mobile && npm run typecheck && npm run lint

# Apply infra — un root module par environnement depuis task-237, le state et les
# noms de ressources sont séparés. Jamais depuis infrastructure/terraform/ : ce
# n'est pas un root module.
terraform -chdir=infrastructure/terraform/envs/dev plan
terraform -chdir=infrastructure/terraform/envs/dev apply

# Prod vit dans un autre compte AWS (task-248) : le profil est obligatoire.
AWS_PROFILE=prod terraform -chdir=infrastructure/terraform/envs/prod plan -out=tfplan
# Garde-fou de plan. Sans 3e argument pour prod : la couche 4 (collision de noms)
# est structurellement redondante entre deux comptes séparés.
scripts/tf_plan_guard.sh prod tfplan

# Deploy Lambda containers — deux images distinctes depuis task-217
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda-api.Dockerfile .
docker buildx build --platform linux/arm64 --provenance=false --sbom=false -f infrastructure/docker/lambda.Dockerfile .

# Purge des comptes E2E orphelins (task-246 / task-247)
python scripts/purge_e2e_accounts.py
python scripts/delete_e2e_account.py <email>
```

## Appendice B — Liens internes

- `AGENTS.md` — guardrails projet
- `CLAUDE.md` — convention de création de tâches
- `.env.example` — gabarit complet des variables (20 sections numérotées)
- `infrastructure/terraform/README.md` — runbook Secrets Manager + Lambda deployment
- `infrastructure/terraform/modules/platform/secrets.tf` — coquille du secret consolidé `media-summarizer-runtime-<env>` (valeurs poussées hors-bande)
- `docs/API_LAMBDA_RUNTIME.md` — runtime API isolé, warm-up, seuil et procédure d'activation de la provisioned concurrency (`task-217`)
- `docs/DATA_RETENTION.md` — les deux horloges de rétention (`task-243`)
- `docs/REVENUECAT_ENTITLEMENTS.md` — disposition entitlements / offering / packages (`task-262`)
- `docs/INGESTION_WORKERS_PROVIDERS.md` — providers et chaînes de fallback par source
- `docs/compliance/` — privacy policy, terms of service, réponses App Privacy (Apple) et Data Safety (Google Play), checklist
- `docs/research/task-221-terraform-multi-env-isolation/README.md` — architecture d'isolation validée (option B)
- `docs/DEVBOX_SETUP.md` — reconstruire un poste de dev complet
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` — détails techniques mobile
- `docs/PRODUCTION_RELEASE_RUNBOOK.md` — procédure de release
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — pipeline d'ingestion
- `infrastructure/terraform/` — provisioning AWS
