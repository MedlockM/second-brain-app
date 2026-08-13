---
id: task-252
title: Provision the 37 runtime credentials of the prod secret (owner only)
status: To Do
assignee: []
created_date: '2026-08-13 07:30'
labels:
  - infra
  - security
  - release
  - phase-10
  - blocker-launch
  - owner-only
dependencies:
  - task-248
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUEL — OWNER UNIQUEMENT. NE JAMAIS DISPATCHER VERS UN SUBAGENT.**
>
> Cette tâche demande 37 credentials tiers que **seul l'owner détient** : comptes
> RevenueCat/Deepgram/OpenAI/Apify, clés Apple, secrets Google. Aucun agent ne
> peut les obtenir, et aucun agent ne doit tenter de les fabriquer, de les
> deviner ou de recopier ceux de dev. Le verrou `dispatchable: false` du
> front-matter est là pour ça — il est lu par `scripts/dispatch_backlog.sh`
> (denylist impérative injectée dans le prompt du dispatcher), indépendamment du
> statut, de la priorité, des labels et des dépendances.

## Pourquoi cette tâche existe

Elle recueille le seul reste-à-faire du critère #7 de task-237 (« a staging
environment is created and **its runtime secret is provisioned** »), volontairement
suspendu à la clôture de cette dernière le 2026-08-13. Sans elle, ce travail ne
serait plus tracé nulle part : task-248 le mentionne uniquement dans sa section
« Non traité, hors périmètre ».

Sans ces credentials, **prod est une coquille vide** exactement comme staging l'est
aujourd'hui : le health check répond `200` parce que la connexion DynamoDB passe
par le rôle IAM, mais toute intégration tierce échoue — pas de transcription
(Deepgram), pas de résumé (OpenAI), pas de résolution TikTok/Instagram/YouTube
(Apify), pas de recherche (Algolia), pas d'achat (RevenueCat), et surtout aucune
session utilisateur valide (`JWT_SECRET_KEY`).

C'est un **bloquant de lancement dur**, à traiter en Phase 10.

## État constaté le 2026-08-13 (vérifié côté AWS, région eu-west-3)

- `media-summarizer-runtime-dev` contient **37 clés**, dont 2 vides et
  légitimement vides : `COOKIE_DOMAIN` (aucun domaine public ne résout encore) et
  `REVENUCAT_WEBHOOK_SECRET`.
- `media-summarizer-runtime-staging` contient **0 clé**. Ce secret sera **détruit**
  par task-248 (`--force-delete-without-recovery`, son AC #2) : le nom porte le
  token d'environnement, qui est `ForceNew`. Ne rien y peupler — ce serait du
  travail jeté.
- Le secret prod visé n'existe donc pas encore ; il est créé par l'apply de
  `envs/prod/`, d'où la dépendance sur task-248.

## Les 37 clés à peupler

Relevé sur dev le 2026-08-13. **Ne pas recopier les valeurs de dev** : le
benchmark task-221 §7.3 l'interdit, et une clé partagée signifie même index
Algolia, même facturation Apify/OpenAI, et un `JWT_SECRET_KEY` commun qui rendrait
un token dev valide en prod.

| Groupe | Clés | Doit impérativement différer de dev ? |
|---|---|---|
| Auth applicative | `JWT_SECRET_KEY` | **Oui, critique** — sinon un token dev ouvre prod |
| Algolia | `ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `ALGOLIA_INDEX_NAME` | **Oui** — index distinct, sinon les contenus dev polluent la recherche prod |
| RevenueCat | `REVENUCAT_API_KEY`, `REVENUCAT_PROJECT_ID`, `REVENUCAT_WEBHOOK_SECRET` | **Oui** — clés **live**, pas sandbox (exige les produits App Store validés, Phase 6) |
| Deepgram | `DEEPGRAM_API_KEY`, `DEEPGRAM_MODEL` | Clé oui (facturation séparée) ; le modèle peut être identique |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | Clé oui (facturation séparée) ; le modèle peut être identique |
| Apify | `APIFY_YOUTUBE_API_TOKEN`, `APIFY_TIKTOK_API_TOKEN`, `APIFY_INSTAGRAM_API_TOKEN` + les 5 actor IDs (`APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`, `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID`, `APIFY_INSTAGRAM_POST_ACTOR_ID`, `APIFY_INSTAGRAM_REEL_ACTOR_ID`, `APIFY_INSTAGRAM_COMMENT_ACTOR_ID`) | Tokens oui ; les actor IDs sont publics et identiques |
| Documents | `LLAMAPARSE_API_KEY`, `UNSTRUCTURED_API_KEY` | Oui (facturation séparée) |
| Apple Sign-In | `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`, `APPLE_NATIVE_AUDIENCE`, `APPLE_REDIRECT_URI` | `APPLE_REDIRECT_URI` **oui** (domaine prod) ; le reste dépend du Service ID retenu |
| Google Sign-In | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | `GOOGLE_REDIRECT_URI` **oui** (domaine prod) |
| Podcast Index | `PODCASTINDEXORG_API_KEY`, `PODCASTINDEXORG_API_SECRET` | Recommandé |
| X / Twitter | `X_API_BEARER_TOKEN` | Recommandé |
| Canny (feedback) | `CANNY_BOARD_TOKEN`, `CANNY_SSO_PRIVATE_KEY` | Recommandé |
| Admin pricing | `PRICING_ADMIN_SECRET` | **Oui** — un secret admin partagé donne accès prod depuis dev |
| Cookies | `COOKIE_DOMAIN` | Oui — dépend du domaine prod, qui ne résout pas encore |

## Dépendances de fait, au-delà de task-248

Trois clés ne peuvent pas être remplies avant que d'autres travaux aboutissent —
c'est une contrainte réelle, pas une excuse :

- `COOKIE_DOMAIN`, `APPLE_REDIRECT_URI`, `GOOGLE_REDIRECT_URI` attendent le
  domaine public (`api.secondbrainlabs.com` ne résout pas — Phase 10, étape 0bis
  de `docs/V1_LAUNCH_PLAN.md`).
- Les clés RevenueCat **live** exigent les produits App Store validés (Phase 6).

Il est donc parfaitement acceptable de peupler cette tâche en deux passes : les
34 clés indépendantes d'abord, les 3 liées au domaine ensuite. Le noter dans les
notes plutôt que de laisser la tâche ouverte sans qu'on sache ce qui manque.

## Comment procéder

Le secret est géré par Terraform (`modules/platform/secrets.tf`) via
`secret_payload`. Piège documenté dans `infrastructure/terraform/README.md` et
task-134 : un `lifecycle { ignore_changes }` porte sur la valeur, donc **ajouter
une clé à `terraform.tfvars` ne la pousse pas** — la valeur doit être poussée à
la main (`aws secretsmanager put-secret-value`) ou l'`ignore_changes` contourné
explicitement. Ne pas committer les valeurs : `terraform.tfvars` est gitignoré,
seul `terraform.tfvars.example` est suivi et ne contient que des placeholders.

Piège à connaître, mesuré sur task-136 : une valeur collée avec un commentaire
en fin de ligne ou un espace final est acceptée par Secrets Manager et casse
l'intégration silencieusement. Vérifier chaque valeur sensible après écriture
(`get-secret-value | jq -r .CLE | wc -c`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le secret runtime de prod contient les 37 clés relevées sur dev, aucune absente
- [ ] #2 Aucune valeur n'est identique à celle de dev pour JWT_SECRET_KEY, PRICING_ADMIN_SECRET, ALGOLIA_INDEX_NAME et les clés RevenueCat, vérifié par comparaison des deux secrets
- [ ] #3 Les clés RevenueCat sont les clés live du projet, pas les clés sandbox
- [ ] #4 Aucune valeur ne porte d'espace final ni de commentaire résiduel, vérifié clé par clé sur les valeurs sensibles
- [ ] #5 Aucune valeur n'est committée dans le dépôt ; seul terraform.tfvars.example est mis à jour, avec des placeholders
- [ ] #6 Les clés qui dépendent du domaine public (COOKIE_DOMAIN, APPLE_REDIRECT_URI, GOOGLE_REDIRECT_URI) sont soit renseignées, soit listées dans les notes comme restant à faire avec leur bloquant
- [ ] #7 Une invocation réelle prouve qu'au moins une intégration tierce fonctionne en prod avec ces credentials, et non la seule lecture du secret
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-13 — Tâche créée à la clôture de task-237 pour ne pas perdre la trace du
seul reste-à-faire de son critère #7. Le critère #7 de task-237 est marqué
**suspendu**, pas satisfait : staging existe bien et `enable_alarms` est conforme
à la décision de mise en veille du 2026-08-12, mais le secret runtime n'a jamais
été peuplé — et il ne doit pas l'être sur staging, que task-248 va détruire.
<!-- SECTION:NOTES:END -->
