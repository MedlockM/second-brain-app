# ADR - Strategie de fallback pour l'ingestion Instagram, TikTok et YouTube

## Statut
Acceptee

## Date
2026-03-15

## Decision
Nous retenons une strategie d'ingestion en cascade, specifique par plateforme, pour Instagram, TikTok et YouTube.

Le principe commun est le suivant:
- privilegier d'abord la source la plus fidele et la moins couteuse en traitement
- n'utiliser la transcription audio que lorsqu'aucune source textuelle exploitable n'est disponible
- garder des fallbacks explicites et determines par plateforme

## Contexte
- Le produit doit supporter l'ingestion de contenus courts sociaux et de videos YouTube via URL partagee.
- Les strategies d'extraction ne sont pas equivalentes selon les plateformes:
  - Instagram: besoin principal = recuperer un `media_url` exploitable rapidement.
  - TikTok: extraction via `yt-dlp`, avec contrainte de quota a respecter.
  - YouTube: les sous-titres natifs doivent etre privilegies avant tout recours a l'audio.
- Le projet est pre-production: on privilegie une implementation directe, sans conserver de chemins legacy inutiles.

## Decision par plateforme

### Instagram
Strategie retenue (mise a jour task-108, 2026-05-28):
- utiliser Apify comme provider unique (Instagram Reel Scraper + Post Scraper + Comment Scraper)
- Reels/videos: recuperer `downloadedVideo` ou `videoUrl` puis transmettre a Deepgram pour transcription
- Posts images (single + carrousel): recuperer `displayUrl`, `images`, `childPosts` puis envoyer au pipeline OCR/vision
- Caption: extraite du champ `caption` de tous les scrapers, persistee comme contenu textuel
- Commentaires: recuperes via Comment Scraper avec pagination (best-effort, non-bloquant)

Fallback:
- aucun fallback retenu pour V1 (decision owner task-107: Apify seul, pas de second provider)
- l'architecture hexagonale permet de reintroduire un adapter fallback plus tard si necessaire

Rationale:
- Apify couvre les 4 dimensions de contenu Instagram (video, images, caption, commentaires)
- le provider precedent ne couvrait que les Reels et ne retournait ni captions ni commentaires ni images
- un seul provider reduit la surface d'integration et les secrets a gerer en V1

### TikTok (superseded -- see V1 below)

> **NOTE**: The section below is the original V0 strategy retained at initial ADR creation.
> It has been superseded by the V1 strategy that follows, validated via task-140 benchmark.

~~Strategie retenue:~~
~~- voie principale: utiliser l'approche A via `yt-dlp` en mode sous-titres natifs seuls~~
~~- fallback: reutiliser `yt-dlp` en mode extraction `audio_only`~~

### TikTok extraction (V1, post-task-140)

Strategie retenue apres validation du benchmark task-140 (owner decision: hybrid yt-dlp + Apify actor en fallback pour la V1):

**Primary path**: yt-dlp native subtitle extraction (unchanged from V0)

**Cascade de fallback (3 branches selon le type d'echec)**:

| Etape | Condition | Action |
| --- | --- | --- |
| 1 | yt-dlp reussit | Extraire sous-titres natifs ou audio URL (existant) |
| 2a | yt-dlp echoue avec IP block (status 10204 / "IP address is blocked") | Appeler l'acteur Apify TikTok transcript via `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` |
| 2b | yt-dlp echoue pour toute autre raison (geo, deleted, rate limit, parse error) | Deepgram URL fallback via extraction audio yt-dlp (existant) |
| 3 | Apify echoue apres IP block | Marquer le job comme echec non-retryable avec message utilisateur explicite |

**Pourquoi Apify en fallback IP-block uniquement**:
- La majorite des videos TikTok passent toujours via yt-dlp depuis les IPs Lambda
- Le blocage IP (status 10204) est specifique aux videos recentes/populaires depuis des IPs datacenter
- Apify ajoute 3-10s de latence et un cout par appel -- ne doit etre declenche que sur echec IP confirme
- Les autres echecs yt-dlp (video privee, geo-restriction) ne seraient pas resolus par Apify

**Configuration**:
- `APIFY_TIKTOK_API_TOKEN`: token API Apify (secret)
- `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID`: identifiant de l'acteur Apify a invoquer
- `APIFY_TIKTOK_TIMEOUT_SECONDS`, `APIFY_TIKTOK_POLL_INTERVAL_SECONDS`, `APIFY_TIKTOK_MAX_POLLS`

**Codes d'erreur ajoutes**:
- `apify_actor_failed` (non-retryable: auth 401/403, config invalide)
- `apify_quota_exceeded` (retryable: 429)
- `apify_timeout` (retryable: 5xx, network, poll exhausted)
- `tiktok_ip_blocked_unrecoverable` (non-retryable: yt-dlp ET Apify ont echoue)

**V2 (task-145)**: Migration vers residential proxy comme fallback primaire au lieu d'Apify, avec Apify comme escalation de dernier recours.

Contraintes de rate limiting (inchangees):
- imposer un plafond global de `100 requetes / heure` vers TikTok
- traiter cette contrainte comme un garde-fou d'architecture, au meme niveau que la protection deja mise en place pour Podcasts
- eviter que des rafales de partages provoquent des echecs par quota ou des comportements non deterministes
- completer ce garde-fou par un debit cible de l'ordre de `1 requete toutes les 2 a 3 secondes` par IP lorsque l'execution sort du chemin purement synchrone

Implication d'implementation:
- les appels TikTok via `yt-dlp` doivent passer par une strategie gouvernee de rate limiting global
- l'attente de quota ne doit pas degrader inutilement le chemin synchrone de prise en charge de l'URL
- la distinction entre `native_subtitles_found`, `native_subtitles_absent`, `rate_limited`, `extractor_failed`, `apify_tiktok` doit etre exposee dans les resultats d'ingestion
- `yt-dlp` doit etre maintenu a jour regulierement, car la robustesse de cette approche depend directement des evolutions de son extracteur TikTok

### YouTube (SUPERSEDED -- see V1 post-task-126 section below)

~~Strategie retenue:~~
~~- utiliser une cascade en trois niveaux~~
~~- privilegier les sous-titres avant toute extraction audio~~

~~Ordre des fallbacks:~~

| Niveau | Source | Outil | Declencheur du fallback |
| --- | --- | --- | --- |
| ~~1~~ | ~~Sous-titres manuels~~ | ~~`youtube-transcript-api`~~ | ~~Aucun transcript manuel trouve~~ |
| ~~2~~ | ~~Sous-titres auto-generes~~ | ~~`youtube-transcript-api`~~ | ~~Aucun transcript auto trouve~~ |
| ~~3~~ | ~~Transcription audio~~ | ~~`yt-dlp` + Deepgram~~ | ~~Dernier recours~~ |

**Status: SUPERSEDED by task-126/task-129 (June 2026). YouTube now blocks all cloud provider IPs, making `youtube-transcript-api` and `yt-dlp` non-functional from Lambda.**

### YouTube extraction (V1, post-task-126)

Strategie retenue:
- Apify YouTube Transcript actor as primary and sole extraction method
- Deepgram fallback only if the Apify actor exposes a usable audio URL (currently: no)
- `youtube-transcript-api` and `yt-dlp` removed from the YouTube pipeline entirely

Contexte:
- YouTube systematically blocks AWS Lambda IP ranges (`eu-west-3`), making both `youtube-transcript-api` and `yt-dlp` non-functional from cloud environments
- task-126 benchmarked 10 strategies; owner chose Apify for infrastructure consolidation (already used for Instagram via task-108) and billing isolation via separate Apify accounts

Principe:
- Single call to the Apify YouTube Transcript actor (configured via `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`)
- Actor handles anti-bot measures internally (residential proxies, browser attestation)
- Returns transcript as timed segments or flat text
- On actor failure: job marked as failed with appropriate user message
- No audio fallback path (the actor does not expose raw audio URLs)

Observabilite:
- CloudWatch metric `apify_youtube_api_calls{outcome}` tracks success/failure rates
- CloudWatch metric `apify_youtube_credits_consumed` tracks per-call cost
- Alarm on failure rate > 10% over 5 minutes

Amendements posterieurs (la cascade courante fait foi dans `docs/INGESTION_WORKERS_PROVIDERS.md`):
- task-177: yt-dlp est redevenu le chemin primaire, Apify est le fallback declenche sur IP-block, Deepgram le fallback quand aucun sous-titre n'existe
- task-216: la langue cible vient de `User.reading_language` (override possible par requete), plus d'une variable d'environnement globale. Le worker supporte plusieurs dialectes d'actor Apify; seul `starvibe~youtube-video-transcript` accepte un input `language` (ISO 639-1). Le controle de langue sur le chemin Apify n'est actif qu'une fois `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` bascule sur cet actor dans le secret runtime (voir "Rollout prerequisite" dans `docs/INGESTION_WORKERS_PROVIDERS.md`)

References:
- `docs/research/task-126-youtube-extraction/README.md` (benchmark and owner decision)
- `media_summarizer/workers/youtube_ingestion_worker.py` (implementation)

## Principes transverses
- `native_transcript` reste la source prioritaire chaque fois qu'elle existe
- Deepgram est la solution de transcription audio de recours pour ces plateformes
- les fallbacks doivent etre traces explicitement dans les metadonnees d'ingestion pour savoir quelle strategie a ete utilisee
- une fois une strategie validee pour une plateforme, on ne maintient pas de chemin legacy parallele sans besoin explicite

## Consequences
- le resolver YouTube doit exposer explicitement la cascade `manual -> auto -> audio`
- le resolver TikTok doit integrer un fallback `audio_only` sans changer de famille d'outil
- l'ingestion Instagram depend d'un provider unique (Apify) sans mecanisme de secours additionnel a ce stade
- l'observabilite doit permettre d'identifier:
  - le niveau de fallback declenche
  - le provider/outillage utilise
  - les refus ou attentes lies au rate limiting TikTok

## Hors perimetre de cet ADR
- le detail du code d'integration concret pour chaque provider
- le choix fin des files, workers ou parametrages d'execution
- un eventuel fallback supplementaire Instagram si Apify devient insuffisant

## References internes
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `docs/ADR/podcastindex-rate-limiting.md`
