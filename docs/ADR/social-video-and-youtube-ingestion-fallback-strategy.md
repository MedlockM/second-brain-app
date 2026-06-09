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
Strategie retenue:
- utiliser `https://getinsaver.com/api/`
- recuperer le `media_url`
- transmettre ce `media_url` a Deepgram pour transcription

Fallback:
- aucun fallback supplementaire n'est retenu dans cet ADR

Rationale:
- le plan free couvre le besoin initial (`1000` requetes par jour)
- l'objectif pour Instagram est de convertir rapidement l'URL source en URL media directement exploitable
- on evite d'ajouter une seconde chaine de resolution tant que ce provider couvre le besoin

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

### YouTube
Strategie retenue:
- utiliser une cascade en trois niveaux
- privilegier les sous-titres avant toute extraction audio

Ordre des fallbacks:

| Niveau | Source | Outil | Declencheur du fallback |
| --- | --- | --- | --- |
| 1 | Sous-titres manuels | `youtube-transcript-api` | Aucun transcript manuel trouve |
| 2 | Sous-titres auto-generes | `youtube-transcript-api` | Aucun transcript auto trouve |
| 3 | Transcription audio | `yt-dlp` + Deepgram | Dernier recours |

Regles d'usage:
- si un transcript manuel est disponible, il est utilise sans passer aux niveaux suivants
- si aucun transcript manuel n'est disponible, tenter les sous-titres auto-generes
- si aucun transcript exploitable n'est disponible via `youtube-transcript-api`, extraire l'audio avec `yt-dlp` puis transcrire via Deepgram

## Principes transverses
- `native_transcript` reste la source prioritaire chaque fois qu'elle existe
- Deepgram est la solution de transcription audio de recours pour ces plateformes
- les fallbacks doivent etre traces explicitement dans les metadonnees d'ingestion pour savoir quelle strategie a ete utilisee
- une fois une strategie validee pour une plateforme, on ne maintient pas de chemin legacy parallele sans besoin explicite

## Consequences
- le resolver YouTube doit exposer explicitement la cascade `manual -> auto -> audio`
- le resolver TikTok doit integrer un fallback `audio_only` sans changer de famille d'outil
- l'ingestion Instagram depend d'un provider unique (`getinsaver`) sans mecanisme de secours additionnel a ce stade
- l'observabilite doit permettre d'identifier:
  - le niveau de fallback declenche
  - le provider/outillage utilise
  - les refus ou attentes lies au rate limiting TikTok

## Hors perimetre de cet ADR
- le detail du code d'integration concret pour chaque provider
- le choix fin des files, workers ou parametrages d'execution
- un eventuel fallback supplementaire Instagram si `getinsaver` devient insuffisant

## References internes
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `docs/ADR/podcastindex-rate-limiting.md`
