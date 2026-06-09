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

### TikTok
Strategie retenue:
- voie principale: utiliser l'approche A via `yt-dlp` en mode sous-titres natifs seuls
- fallback: reutiliser `yt-dlp` en mode extraction `audio_only`

Cascade de fallback:
1. tenter l'extraction des sous-titres natifs avec `yt-dlp`
2. si la methode A echoue, relancer via `yt-dlp` en extraction audio seule
3. envoyer l'audio obtenu au pipeline de transcription existant

Details de l'approche A:
- execution attendue en mode `--write-subs --skip-download`, avec conversion vers un format exploitable (`srt` ou `vtt`) sans telecharger la video complete
- l'integration programmatique doit privilegier l'usage de `yt-dlp` comme bibliotheque plutot que comme simple CLI, afin de recuperer les metadonnees et les sous-titres demandes en memoire
- `yt-dlp` est retenu car il implemente deja une cascade interne de recuperation des captions TikTok sur trois chemins:
  - `video.cla_info.caption_infos` comme source principale
  - `video.subtitleInfos` comme fallback de compatibilite
  - les donnees web issues de `__UNIVERSAL_DATA_FOR_REHYDRATION__` en dernier recours
- les formats natifs TikTok peuvent etre du JSON proprietaire ou du `WebVTT`; la conversion en format standard fait partie du perimetre de l'outil choisi

Conditions de succes:
- si des sous-titres natifs sont recuperes via l'approche A, ils deviennent la source `native_transcript` et le pipeline s'arrete sans extraction audio
- l'absence de captions natives doit etre distingee d'un echec technique d'acces TikTok, afin de declencher le bon fallback et de conserver une observabilite exploitable

Contraintes de rate limiting:
- imposer un plafond global de `100 requetes / heure` vers TikTok
- traiter cette contrainte comme un garde-fou d'architecture, au meme niveau que la protection deja mise en place pour Podcasts
- eviter que des rafales de partages provoquent des echecs par quota ou des comportements non deterministes
- completer ce garde-fou par un debit cible de l'ordre de `1 requete toutes les 2 a 3 secondes` par IP lorsque l'execution sort du chemin purement synchrone
- prevoir la reutilisation de cookies/session et la possibilite de proxies residents rotatifs si TikTok durcit ses mecanismes anti-bot

Implication d'implementation:
- les appels TikTok via `yt-dlp` doivent passer par une strategie gouvernee de rate limiting global
- l'attente de quota ne doit pas degrader inutilement le chemin synchrone de prise en charge de l'URL
- la distinction entre `native_subtitles_found`, `native_subtitles_absent`, `rate_limited` et `extractor_failed` doit etre exposee dans les resultats d'ingestion
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
