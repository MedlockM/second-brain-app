# Plan d'Implémentation Produit Mobile - Media Summarizer

> Note de cadrage: ce document conserve du contexte de conception initial. Pour l'état d'avancement, l'ordonnancement réel et les priorités, le backlog fait foi.

## Sommaire

1. [Décisions Stratégiques à Trancher](#décisions-stratégiques-à-trancher)
2. [Matrice de Réutilisation de l'Existant](#matrice-de-réutilisation-de-lexistant)
3. [Chantier 1: Architecture Cible (Hexagonale, Extensible)](#chantier-1-architecture-cible-hexagonale-extensible)
4. [Chantier 2: Ingestion Universelle de Liens (Share URL -> Media Item)](#chantier-2-ingestion-universelle-de-liens-share-url---media-item)
5. [Chantier 3: Podcasts Multi-Plateformes (Réutilisation PodcastIndex)](#chantier-3-podcasts-multi-plateformes-réutilisation-podcastindex)
6. [Chantier 4: Articles, YouTube, Instagram/TikTok](#chantier-4-articles-youtube-instagramtiktok)
7. [Chantier 5: Post-Transcription "NotebookLM-like" (Résumé/Flashcards/Notes)](#chantier-5-post-transcription-notebooklm-like-résuméflashcardsnotes)
8. [Chantier 6: Retrait Spotify Sync & Playlist Tracking](#chantier-6-retrait-spotify-sync--playlist-tracking)
9. [Chantier 7: Retrait Emails Résumés/Quiz et Découplage de Finalisation](#chantier-7-retrait-emails-résumésquiz-et-découplage-de-finalisation)
10. [Chantier 8: Application Mobile Share-First (Stores)](#chantier-8-application-mobile-share-first-stores)
11. [Chantier 9: Qualité, Sécurité, Observabilité, Coûts](#chantier-9-qualité-sécurité-observabilité-coûts)
12. [Chantier 10: Publication App Store & Play Store](#chantier-10-publication-app-store--play-store)
13. [Plan d'Exécution Phasé](#plan-dexécution-phasé)
14. [Checklists de Validation](#checklists-de-validation)
15. [Annexe: Mapping Variables d'Environnement](#annexe-mapping-variables-denvironnement)

---

## Décisions Stratégiques à Trancher

### Décisions Produit
1. Priorité UX: flux centré sur le partage depuis n'importe quelle app mobile, d'abord pour les liens, avec extension en cours pour certains contenus partagés non-URL (notamment WhatsApp texte/audio).
2. Expérience post-transcription: le backlog V1 cible `summary_short`, `summary_detailed`, `notes` et `flashcards`; les résumés et notes restent à la demande, tandis que les flashcards sont prévues en auto-génération post-transcript.
3. Politique de coûts: cadrer le volume de médias traités par utilisateur / fenêtre temporelle; les artefacts V1 réutilisent une génération unique par média quand ils existent déjà, qu'ils soient demandés explicitement ou pré-générés selon le backlog.
4. Niveau de fidélité attendu par type média:
   - Article: extraction + nettoyage, sans paraphrase destructive.
   - Podcast / vidéo audio: transcription la plus littérale possible.
   - YouTube: transcript source prioritaire, fallback audio-to-text.

### Décisions Techniques
1. Stack mobile:
   - Option A (recommandée): React Native (Expo + modules natifs share extension) pour maximiser la réutilisation TypeScript des services front existants.
   - Option B: Flutter (alignement fort avec le pattern `mobile-share` de `fiches-veille/mobile-share`).
2. Architecture backend: hexagonale (ports/adapters) avec orchestration asynchrone par jobs.
3. API canonique unique: exposer `/api/media/*` et `/api/artifacts/*` (pas de versionnement d'endpoint en pré-production).
4. Politique legacy: suppression directe des chemins obsolètes, sans fallback de rétrocompatibilité.
5. Modèle de stockage: séparer `MediaItem` (contenu source + transcript) et `MediaArtifact` (types pilotés par le backlog V1: `summary_short`, `summary_detailed`, `notes`, `flashcards`; quiz hors V1).
6. Strategie E2E mobile: **Maestro-first** pour l'automatisation des parcours critiques, validation manuelle maintenue sur devices reels, fallback Appium strictement cible si blocage durable sur iOS share extension.

---

## Matrice de Réutilisation de l'Existant

### Réutilisation Forte (conserver et adapter)
1. Pipeline audio existant:
   - `media_summarizer/workers/download_worker.py`
   - `media_summarizer/workers/transcription/deepgram_worker.py`
2. Intégration PodcastIndex:
   - `media_summarizer/utils/podcast_index.py`
   - endpoints actuels `media_summarizer/api/endpoints/podcast_search.py`
3. Idempotence + fan-out:
   - `media_summarizer/core/services/episode_submission.py`
   - `media_summarizer/utils/episode_idempotence.py`
   - `media_summarizer/utils/episode_watchers.py`
   - cible produit: conserver les primitives utiles et supprimer les branches legacy de compatibilité runtime.
4. Génération LLM d'artefacts:
   - `media_summarizer/workers/summarization/summarization_worker.py`
   - socle d'artefacts textuels existant à étendre selon le backlog V1 (`task-64`, `task-68`, `task-71`, `task-72`)
5. Socle infra/worker:
   - `media_summarizer/workers/base_worker.py`
   - S3/SQS utils + Terraform queues/tables déjà en place.

### Réutilisation Partielle (refactor nécessaire)
1. Modèle `ProcessingJob` (`media_summarizer/core/models/processing_job.py`):
   - aujourd'hui centré podcast + summary/quiz + fin via email.
   - à étendre pour `media_type`, `transcript_status`, `artifact_statuses`, `notes_s3_key`.
2. Endpoint de restitution (`media_summarizer/api/endpoints/episodes.py`):
   - aujourd'hui filtre uniquement les jobs ayant *summary + quiz*.
   - à rendre compatible artefacts optionnels et on-demand.
3. Matching Spotify -> PodcastIndex:
   - logique de matching utile dans `playlist_sync.py` / `tosum_sync.py`.
   - à extraire en composant générique de résolution d'épisodes podcast.

### À Retirer
1. Sync compte Spotify / playlists tracking:
   - `media_summarizer/api/endpoints/spotify_sync.py`
   - `media_summarizer/api/endpoints/spotify_playlists.py`
   - portions Spotify dans `auth_social.py`, `user.py`, `utils/spotify.py`
   - infra `infrastructure/terraform/dynamodb_spotify_follows.tf`, `infrastructure/terraform/aws/spotify_sync.tf`
2. Email résumés/quizzes:
   - `media_summarizer/workers/notification/email_worker.py` (partie completion content)
   - templates quiz email
   - couplages d'événements qui dépendent de l'email pour marquer `completed`.

---

## Chantier 1: Architecture Cible (Hexagonale, Extensible)

### 1.1 Objectif
Mettre en place une architecture qui permet d'ajouter de nouvelles plateformes média sans réécrire le coeur métier.

### 1.2 État Actuel
- Backend orienté podcast avec chemin principal: submit épisode -> download -> transcription -> summarization -> (optionnel quiz/email).
- Couplage fort entre "fin de traitement" et notifications email.

### 1.3 Changements à Réaliser
1. Créer le noyau applicatif (use cases) avec ports:
   - `UrlClassifierPort`
   - `ContentResolverPort`
   - `TranscriptionPort`
   - `ArtifactGeneratorPort`
   - `ArtifactStorePort`
2. Créer les adapters par type:
   - `article_resolver`
   - `podcast_resolver`
   - `youtube_resolver`
   - `instagram_resolver` (`instagram.default`)
   - `tiktok_resolver` (`tiktok.default`)
3. Définir contrats domain:
   - `MediaItem` (id, url, media_type, source_platform, raw_payload, transcript)
   - `MediaArtifact` (id, media_item_id, type, params, content, status)
4. Établir convention d'ajout d'un nouveau provider:
   - fichier adapter + tests + enregistrement dans un registry unique.

### 1.4 Variables d'Environnement
```bash
MEDIA_URL_CLASSIFIER_MODE=rule_based
MEDIA_INGESTION_TIMEOUT_SECONDS=120
MEDIA_ARTIFACT_DEFAULT_LANGUAGE=auto
```

### 1.5 Critères d'Acceptation
- [ ] Ajout d'un nouveau resolver possible sans modifier le coeur métier.
- [ ] Chemin d'ingestion identique côté API, quel que soit le média.
- [ ] Contrats de domain et de ports testés.

### 1.6 Tests
- Unitaires sur le registry + routing type média.
- Contrats adapters (fixtures par plateforme).

### 1.7 Risques et Mitigations
- Risque: architecture trop abstraite trop tôt.
  - Mitigation: démarrer avec 4 adapters cibles (article/podcast/youtube/social) et factoriser ensuite.

### 1.8 Livrables
- [ ] Package `core/media_ingestion/*` avec ports/use-cases.
- [ ] Registry adapters documenté.

---

## Chantier 2: Ingestion Universelle de Liens (Share URL -> Media Item)

### 2.1 Objectif
Créer un endpoint unique d'entrée pour recevoir n'importe quel lien partagé.

### 2.2 État Actuel
- Entrées API fragmentées (podcast search/submit).
- Flux principalement basé sur `feed_id + episode_guid`.

### 2.3 Changements à Réaliser
1. Ajouter `POST /api/media/ingest-url`:
   - input: `url`, `source_app` (optionnel), `locale`.
   - output: `media_item_id`, `job_id`, `initial_status`.
2. Ajouter `GET /api/media/{media_item_id}` pour le suivi.
3. Étendre le job model pour inclure:
   - `media_type`, `source_platform`, `normalized_url`, `transcript_s3_key`.
4. Dédoublonnage:
   - clé unique `media_key` dérivée d'URL canonique (`normalized_url`), commune à tous les types de médias.
   - aucun fallback runtime `episode_guid` conservé en cible.
5. Cache de contenu brut:
   - si `media_key` déjà traité, réutiliser `transcription_s3_key` existant (stocké sur S3) et éviter une nouvelle transcription.
   - le cache doit fonctionner quel que soit le mode d'extraction (article, podcast, YouTube transcript, audio social via yt-dlp + Deepgram).

### 2.4 Variables d'Environnement
```bash
MEDIA_INGESTION_ENABLED=true
MEDIA_DUPLICATE_WINDOW_DAYS=30
```

### 2.5 Critères d'Acceptation
- [ ] Une URL article/podcast/youtube/tiktok/instagram crée bien un `media_item`.
- [ ] Même URL re-partagée réutilise le contenu existant (idempotence).
- [ ] En cas de doublon déjà traité, le transcript est relu depuis S3 via la clé existante sans repasser par le pipeline de transcription.
- [ ] Aucun chemin legacy runtime `episode_guid` n'est requis pour l'ingestion canonique.

### 2.6 Tests
- Intégration API + DB + queue pour les 5 types d'URL.

### 2.7 Risques et Mitigations
- Risque: collisions de normalisation URL.
  - Mitigation: normaliseur dédié avec tests de non-régression.

### 2.8 Livrables
- [ ] Endpoints `/api/media/*`.
- [ ] Schémas OpenAPI canoniques (sans versionnement).
- [ ] Spécification de normalisation URL et génération `media_key`.

Note backlog:
- Le flux canonique URL reste `POST /api/media/ingest-url`.
- Le support des contenus partagés non-URL (`POST /api/media/ingest-shared-content`) est un chantier parallèle en cours via `task-61`, principalement pour WhatsApp texte/audio.

---

## Chantier 3: Podcasts Multi-Plateformes (Réutilisation PodcastIndex)

### 3.1 Objectif
Conserver le coeur PodcastIndex existant tout en ajoutant des resolvers par plateforme podcast.

### 3.2 État Actuel
- `feed_id/episode_guid` issus de la recherche PodcastIndex interne.
- Résolution audio via `enclosureUrl` depuis `get_episodes_by_feed_id`.
- Matching fuzzy déjà en production (Spotify sync services).

### 3.3 Changements à Réaliser
1. Créer des resolvers plateforme -> clés PodcastIndex:
   - Spotify, Apple Podcasts, Deezer, RSS direct.
2. Pipeline de résolution:
   - URL plateforme -> metadata épisode/show -> lookup PodcastIndex -> `feed_id`, `episode_guid` -> `enclosureUrl`.
3. Réutiliser `submit_episode_for_user` pour orchestration aval (download/transcription).
4. Extraire la logique de matching depuis `playlist_sync.py`/`tosum_sync.py` vers un module partagé.

### 3.4 Variables d'Environnement
```bash
PODCAST_RESOLVER_MAX_CANDIDATES=10
PODCAST_MATCH_MIN_SCORE=0.60
PODCASTINDEXORG_API_KEY=...
PODCASTINDEXORG_API_SECRET=...
```

### 3.5 Critères d'Acceptation
- [ ] Une URL Spotify/Apple/Deezer menant à un épisode retourne un audio URL valide.
- [ ] Le taux de matching est mesuré et loggé (succès/échecs par plateforme).

### 3.6 Tests
- Fixtures de liens réels par plateforme.
- Tests de matching fuzzy sur titres multi-langues.

### 3.7 Risques et Mitigations
- Risque: APIs plateforme limitées / non disponibles sans auth.
  - Mitigation: fallback scraping metadata minimal + RSS lookup + amélioration progressive.

### 3.8 Livrables
- [ ] `podcast_platform_resolvers/*`.
- [ ] Métriques de résolution par source.

---

## Chantier 4: Articles, YouTube, Instagram/TikTok

### 4.1 Objectif
Supporter les autres médias demandés en privilégiant fidélité au contenu source.

### 4.2 État Actuel
- Le backend dispose déjà de connecteurs dédiés pour article, YouTube, Instagram et TikTok.
- Le travail restant côté mobile consiste à consommer ces flux canoniques et à garder la documentation alignée sur le runtime Deepgram actuel.

### 4.3 Référence Backend Actuelle
1. Article:
   - extractor dédié avec nettoyage DOM/pub/navigation.
   - stockage texte brut + métadonnées d'extraction.
2. YouTube:
   - resolver queue-first dédié avec `youtube-transcript-api` en cascade: transcripts manuels, puis transcripts auto-générés.
   - fallback audio via `yt-dlp` utilisé comme bibliothèque Python pour résoudre une URL audio distante, puis envoi dans le pipeline Deepgram si aucun transcript exploitable n'est disponible.
3. Instagram/TikTok:
   - Instagram: resolver dédié `instagram.default`, résolution `media_url` via `getinsaver`, puis envoi à Deepgram.
   - TikTok: extraction via `yt-dlp` (méthode A), fallback `audio_only`, puis envoi dans le pipeline Deepgram.
   - appliquer un rate limiting global côté TikTok pour rester sous `100 requêtes / heure`.
4. Standardiser sortie en `raw_text` + `transcript_source` (native_transcript / deepgram).

### 4.4 Variables d'Environnement
```bash
YOUTUBE_INGESTION_QUEUE=youtube-ingestion-queue
YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS=20
YTDLP_TIMEOUT_SECONDS=30
DEEPGRAM_API_KEY=...
GETINSAVER_API_BASE_URL=https://getinsaver.com/api/v1
GETINSAVER_API_KEY=...
GETINSAVER_TIMEOUT_SECONDS=20
TIKTOK_RATE_LIMIT_PER_HOUR=100
ARTICLE_EXTRACTOR_MODE=readability
```

### 4.5 Critères d'Acceptation
- [ ] Article: texte propre extrait pour 90%+ des pages de test.
- [ ] YouTube: transcript manuel prioritaire, transcript auto en fallback, puis Deepgram en dernier recours.
- [ ] Instagram: `media_url` résolu puis transcrit via Deepgram.
- [ ] TikTok: méthode A `yt-dlp` utilisée en premier, fallback `audio_only` disponible, sans dépasser le plafond de `100 requêtes / heure`.

### 4.6 Tests
- Intégration par connecteur avec URLs de référence.
- Tests de robustesse sur timeouts/rate-limits.

### 4.7 Risques et Mitigations
- Risque légal/TOS selon plateformes.
  - Mitigation: cadrage légal + mécanismes de retrait + journal d'usage.

### 4.8 Livrables
- [ ] Connecteurs article/youtube/social.
- [ ] Documentation limitations par plateforme.

---

## Chantier 5: Post-Transcription "NotebookLM-like" (Résumé/Flashcards/Notes)

### 5.1 Objectif
Permettre à l'utilisateur, après transcription, de déclencher ou consulter les artefacts V1 selon leur mode de disponibilité.

### 5.2 État Actuel
- Le backend a déjà basculé vers un modèle transcript-first avec artefacts à la demande.
- Le socle canonique actuellement exposé en runtime couvre encore `summary`, `quiz` et `notes`, mais le backlog V1 a depuis convergé vers `summary_short`, `summary_detailed`, `flashcards` et `notes`, avec quiz explicitement hors V1.
- Le reste du scope sur ce chantier porte surtout sur `task-35`, `task-64`, `task-68`, `task-69`, `task-71`, `task-72`, `task-65` et les finitions mobile associées.

### 5.3 Changements à Réaliser
1. Consolider le modèle "transcript-first":
   - transcription devient le vrai jalon `ready_for_artifacts`.
2. Maintenir les API artefacts canoniques:
   - `POST /api/media/{id}/artifacts`
   - `GET /api/media/{id}/artifacts`
   - `GET /api/artifacts/{artifact_id}`
3. Faire évoluer les types d'artefacts vers la cible V1 backlog:
   - `summary_short` et `summary_detailed` via extension du `summarization_worker` (`task-68`);
   - `notes` comme artefact natif déjà disponible;
   - `flashcards` en génération post-transcript dédiée (`task-64`);
   - `quiz` retiré du scope V1 et nettoyé via `task-71`.
4. Mettre en place la réutilisation canonique des artefacts:
   - un artefact déjà généré pour un média est réutilisé, sans relancer de génération inutile;
   - la politique exacte de quotas/pricing reste cadrée par le backlog (`task-35`, `task-65`).
5. Front mobile:
   - écran transcription avec actions cohérentes avec les artefacts V1 (résumé court/détaillé, notes, flashcards selon disponibilité).

### 5.4 Variables d'Environnement
```bash
ARTIFACT_GENERATION_ENABLED=true
ARTIFACT_TYPES_ALLOWED=summary_short,summary_detailed,notes,flashcards
NOTES_LLM_MODEL=<provider/model chosen via task-72>

# quota/pricing: à figer via task-35 et task-65
# pas de variable canonique figée dans ce plan à ce stade
```

### 5.5 Critères d'Acceptation
- [ ] Une transcription disponible permet de déclencher les artefacts on-demand supportés.
- [ ] Summary Short + Summary Detailed + Notes coexistent pour un même média.
- [ ] Les flashcards V1 sont disponibles selon la stratégie backlog post-transcript.
- [ ] Un artefact déjà généré est réutilisé plutôt que régénéré.
- [ ] Aucun artefact on-demand n'est imposé automatiquement.

### 5.6 Tests
- Unitaires: génération/prompt/parsing par artefact.
- Intégration: workflow transcript ready -> artifact created.
- E2E mobile: actions utilisateur successives sur un même transcript.

### 5.7 Risques et Mitigations
- Risque: explosion coût LLM.
  - Mitigation: quotas, cache, modèles différenciés par artefact.

### 5.8 Livrables
- [ ] API artefacts canoniques.
- [ ] `notes-worker`.
- [ ] Écrans mobile post-transcription.

---

## Chantier 6: Retrait Spotify Sync & Playlist Tracking

### 6.1 Objectif
Supprimer complètement la fonctionnalité de sync playlist Spotify.

### 6.2 État Actuel
- Le retrait du scope Spotify sync/playlist tracking est déjà clôturé dans le backlog (`task-13`).
- Cette section conserve surtout la trace du périmètre supprimé et des points de nettoyage historiquement concernés.

### 6.3 Changements à Réaliser
1. API:
   - retirer routes spotify sync/playlists du router principal.
2. Domain:
   - retirer champs spotify du `User` si plus nécessaires.
3. Services/workers:
   - retirer `playlist_sync`, `tosum_sync`, workers spotify_sync.
4. Front:
   - retirer `SpotifyIntegrationHome`, `SpotifyPlaylists`, `SpotifyService`.
5. Infra:
   - retirer tables/queues/lambdas et policies associées.

### 6.4 Variables d'Environnement
```bash
SPOTIFY_FEATURE_ENABLED=false
```

### 6.5 Critères d'Acceptation
- [ ] Aucun endpoint Spotify exposé en production.
- [ ] Aucune tâche planifiée Spotify active.
- [ ] UI mobile/web sans section Spotify.

### 6.6 Tests
- Tests de non-régression API auth + ingestion hors Spotify.

### 6.7 Risques et Mitigations
- Risque: dépendances cachées dans auth/social.
  - Mitigation: audit `rg -n "spotify"` + suppression guidée.

### 6.8 Livrables
- [ ] Code Spotify sync retiré.
- [ ] Infra nettoyée.

---

## Chantier 7: Retrait Emails Résumés/Quiz et Découplage de Finalisation

### 7.1 Objectif
Retirer l'envoi email de contenu tout en conservant un workflow job cohérent.

### 7.2 État Actuel
- Le découplage de la finalisation job vis-à-vis des emails de contenu est déjà clôturé dans le backlog (`task-14`).
- Cette section documente le refactor cible/historique plutôt qu'un blocage encore ouvert.

### 7.3 Changements à Réaliser
1. Redéfinir la finalisation:
   - job `completed` quand transcription (ou artefact demandé) est persisté, sans dépendre d'un email.
2. Retirer envois `summary_content` / `quiz` vers email queue.
3. Simplifier `episode_completed_worker`:
   - conserver idempotence/fan-out technique si utile,
   - supprimer obligations de notification email.
4. Garder seulement les emails nécessaires au compte (ex: vérification email/auth), si requis produit.
5. Supprimer les chemins legacy restants autour de `episode_submission.py`/`episode_guid`:
   - migrer tous les appelants sur le modèle canonique `media_key`,
   - retirer les fallback runtime de compatibilité.

### 7.4 Variables d'Environnement
```bash
ENABLE_CONTENT_EMAIL_NOTIFICATIONS=false
ENABLE_AUTH_EMAILS=true
```

### 7.5 Critères d'Acceptation
- [ ] Plus aucun résumé/quiz envoyé par email.
- [ ] Les jobs atteignent `completed` sans worker email.
- [ ] Les minutes/usage sont finalisées correctement.

### 7.6 Tests
- Intégration du cycle terminal sans email queue.
- Tests de facturation minute pool sur succès/échec.

### 7.7 Risques et Mitigations
- Risque: jobs bloqués en `notifying`.
  - Mitigation: migration des statuts + script de correction batch.

### 7.8 Livrables
- [ ] Workflow de finalisation découplé de l'email.
- [ ] Nettoyage templates/queues emails de contenu.

---

## Chantier 8: Application Mobile Share-First (Stores)

### 8.1 Objectif
Livrer une app mobile qui reçoit des contenus via le menu Partager (Android/iOS), d'abord les liens, puis les payloads non-URL explicitement couverts par le backlog, avant de piloter ingestion + artefacts.

### 8.2 État Actuel
- Front web React existant, non orienté partage natif mobile.
- Référence de workflow "share-first" disponible dans `fiches-veille/mobile-share` (Flutter).

### 8.3 Changements à Réaliser
1. Implémenter le flux share-first:
   - Android Share Intent
   - iOS Share Extension
   - extension des entrypoints aux payloads WhatsApp texte/audio selon `task-61`
2. Écrans MVP:
   - Inbox partages reçus
   - Détail média + transcription
   - Actions artefacts alignées avec le backlog V1 (summary short/detailed, notes, flashcards selon disponibilité)
   - Historique et recherche
3. Offline-first:
   - file locale des contenus partagés en attente d'upload/sync.
4. Auth + session:
   - réutiliser backend auth existant (JWT/refresh).
5. Inspirer la mécanique de `mobile-share`:
   - réception native + persistance locale + sync asynchrone.

### 8.4 Variables d'Environnement
```bash
MOBILE_DEEP_LINK_SCHEME=mediasummarizer
MOBILE_API_BASE_URL=https://api.yourdomain.com
MOBILE_ENABLE_SHARE_EXTENSION=true
```

### 8.5 Critères d'Acceptation
- [ ] L'app apparaît dans le menu "Partager" iOS/Android.
- [ ] Le contenu partagé pris en charge par le backlog est visible dans l'app en <3 secondes.
- [ ] L'utilisateur peut accéder aux artefacts V1 supportés depuis une transcription, selon leur mode de disponibilité (on-demand ou post-transcript).

### 8.6 Tests
- E2E mobile automatise en Maestro sur Android/iOS pour les parcours critiques share-first.
- Validation manuelle sur devices reels (apps source representatives: Chrome, YouTube, Instagram, TikTok, WhatsApp) pour confirmer le comportement share entrant.
- Tests offline/online sync.

### 8.7 Risques et Mitigations
- Risque: divergences iOS/Android share APIs.
  - Mitigation: abstraction par couche "ShareAdapter" + tests natifs dédiés.

### 8.8 Livrables
- [ ] App mobile MVP installable TestFlight/Internal Testing.
- [ ] Extensions de partage iOS/Android.

---

## Chantier 9: Qualité, Sécurité, Observabilité, Coûts

### 9.1 Objectif
Sécuriser le passage à l'échelle multi-connecteurs et maîtriser le coût LLM/transcription.

### 9.2 État Actuel
- Bonne base de tests workers podcast/transcription/summarization.
- Observabilité partielle, forte dépendance au pipeline historique.

### 9.3 Changements à Réaliser
1. Tests:
   - contract tests par connecteur.
   - e2e multi-media share->transcript->artifact.
2. Observabilité:
   - métriques par type média, taux de réussite extraction, latence par étape.
3. Sécurité:
   - validation URL renforcée et blocage domaines malveillants.
4. Coûts:
   - budgets, quotas de traitement et alertes d'anomalie alignés avec la revue pricing backlog (`task-35`, `task-48`, `task-65`).

### 9.4 Variables d'Environnement
```bash
OBS_METRICS_ENABLED=true
LLM_DAILY_BUDGET_USD=200
URL_SAFETY_SCAN_ENABLED=true
```

### 9.5 Critères d'Acceptation
- [ ] Dashboards et alertes disponibles par type média.
- [ ] SLO transcription et artefacts définis et monitorés.

### 9.6 Tests
- charge sur files SQS et workers.
- chaos testing (timeouts APIs externes).

### 9.7 Risques et Mitigations
- Risque: régressions sur pipeline podcast existant.
  - Mitigation: suite de non-régression obligatoire avant chaque release.

### 9.8 Livrables
- [ ] Dashboards + alerting + runbooks.
- [ ] Budget guardrails actifs.

---

## Chantier 10: Publication App Store & Play Store

### 10.1 Objectif
Publier la version mobile en production sur les stores.

### 10.2 État Actuel
- Pas de pipeline publication store active pour cette nouvelle app.

### 10.3 Changements à Réaliser
1. CI/CD mobile:
   - builds signés Android/iOS.
   - déploiement tracks internes + release progressive.
2. Compliance:
   - Privacy policy, Terms, Data Safety (Play), App Privacy (Apple).
3. Store assets:
   - screenshots, description, keywords, icônes.
4. Release process:
   - TestFlight beta -> App Store review.
   - Internal testing -> Closed testing -> Production Play Store.

### 10.4 Variables d'Environnement
```bash
APPSTORE_CONNECT_API_KEY=...
PLAY_CONSOLE_SERVICE_ACCOUNT_JSON=...
MOBILE_RELEASE_CHANNEL=internal
```

### 10.5 Critères d'Acceptation
- [ ] Build iOS uploadé TestFlight sans erreur.
- [ ] Build Android publié en Internal testing.
- [ ] App validée sur stores et disponible en production.

### 10.6 Tests
- smoke tests release candidate sur devices physiques.

### 10.7 Risques et Mitigations
- Risque: rejet store (permissions share/audio).
  - Mitigation: dossier conformité + wording clair sur usage des contenus.

### 10.8 Livrables
- [ ] App iOS et Android publiées.
- [ ] Runbook release et hotfix.

---

## Plan d'Exécution Phasé

### Directives appliquées (MAJ 2026-03-01)
1. API canonique unique sans versionnement: `/api/media/*` et `/api/artifacts/*`.
2. Pré-production: suppression directe des chemins legacy, sans fallback de rétrocompatibilité.
3. Résolution podcast: une tâche resolver par plateforme.
4. Le fallback resolver est inclus dans les tâches plateforme; l'observabilité est couverte dans le chantier transverse.
5. Référence mobile unique: ADR stack share-first `docs/ADR/mobile-stack-share-first.md`.
6. Référence test mobile unique: ADR strategie E2E `docs/ADR/mobile-e2e-test-strategy-maestro-first.md`.

### Base acquise (déjà terminée)
- `task-13`: retrait Spotify sync/playlist tracking.
- `task-14`: découplage finalisation jobs vs email de contenu.
- `task-15`: migration identité `media_key` pour idempotence/watchers.
- `task-16`: extraction utilitaires de matching podcast.
- `task-17`: garde duplicate per-user en modèle `media_key`.

### Convention de statut (sync Backlog au 2026-03-27)
- `[DONE]`: tâche terminée dans le backlog.
- `[IN PROGRESS]`: tâche en cours dans le backlog.
- `[TODO]`: tâche à faire dans le backlog.

Rappel:
- cette section est le snapshot d'exécution à jour;
- les sections "Chantier" ci-dessus peuvent conserver du contexte de conception même quand une partie du scope est déjà clôturée dans le backlog.

### Phase 0 (Semaine 1): Alignement et cadrage
Objectif: verrouiller les décisions structurantes.
- `[DONE]` `task-18` Décider stack mobile et figer ADR (React Native Expo vs Flutter) -> `docs/ADR/mobile-stack-share-first.md`.
- `[DONE]` `task-19` Figer contrats API canoniques + types domain (`MediaItem`, `MediaArtifact`, statuts, erreurs).

### Phase 1 (Semaines 2-4): Coeur backend + ingestion
Objectif: établir le socle d'ingestion canonique et supprimer le legacy runtime.
- `[DONE]` `task-20` Implémenter noyau hexagonal media ingestion (ports/use-cases/registry).
- `[DONE]` `task-21` Implémenter URL classifier + routing vers resolver.
- `[DONE]` `task-10` Implémenter `POST /api/media/ingest-url`.
- `[DONE]` `task-22` Implémenter `GET /api/media/{media_item_id}`.
- `[DONE]` `task-23` Purger chemins legacy ingestion/completion runtime.
- `[IN PROGRESS]` `task-6` Finaliser logging structuré sur les nouveaux flux backend/workers.

### Phase 2 (Semaines 5-6): Connecteurs média
Objectif: couvrir les plateformes cibles avec résolveurs dédiés.
- `[DONE]` `task-9` Architecture de rate limiting PodcastIndex (prérequis Spotify/Apple/Deezer).
- `[DONE]` `task-24` Socle commun des podcast resolvers.
- `[DONE]` `task-25` Resolver Spotify -> PodcastIndex -> `audio_url`.
- `[DONE]` `task-26` Resolver Apple Podcasts -> PodcastIndex -> `audio_url`.
- `[DONE]` `task-27` Resolver Deezer -> PodcastIndex -> `audio_url`.
- `[DONE]` `task-28` Resolver RSS direct -> `audio_url` (+ enrichissement PodcastIndex opportuniste).
- `[DONE]` `task-29` Connecteur Article.
- `[DONE]` `task-30` Connecteur YouTube.
- `[DONE]` `task-31` Connecteur Instagram.
- `[DONE]` `task-54` Connecteur TikTok.
- `[DONE]` `task-51` Migration transcription active de Whisper vers Deepgram, déconnexion du runtime Whisper.
- `[DONE]` `task-52` Alignement ingestion share-first sur Deepgram, retrait des hypothèses Whisper résiduelles.
- `[DONE]` `task-59` Connecteur X (Twitter) via API v2.
- `[IN PROGRESS]` `task-61` Connecteur WhatsApp (texte partagé + audio).
- `[TODO]` `task-55` Prioriser les transcripts RSS Podcasting 2.0 avant la transcription audio.
- `[TODO]` `task-60` Ingestion de posts LinkedIn publics via browser headless / User-Agent réaliste.
- `[TODO]` `task-70` Benchmark + implémentation OCR pour images et PDF scannés.

### Phase 3 (Semaines 7-8): Post-transcription à la demande
Objectif: artefacts transcript-first, réutilisation canonique, cadrage quotas/pricing et nettoyage du scope V1.
- `[DONE]` `task-32` Désactiver auto-génération `summary/quiz` dans le pipeline.
- `[DONE]` `task-11` Commande on-demand des artefacts `summary`/`quiz`.
- `[DONE]` `task-12` Génération `notes` comme artefact natif.
- `[DONE]` `task-33` Endpoints lecture artefacts (`/api/media/{id}/artifacts`, `/api/artifacts/{id}`).
- `[DONE]` `task-34` Stockage/idempotence/cache artifacts avec audit de réutilisation obligatoire.
- `[TODO]` `task-35` Définir et implémenter des quotas de traitement media plutôt que des quotas de génération d'artefacts.
- `[TODO]` `task-49` Renommer les identifiants épisode-centriques en nommage media-agnostique dans toute la codebase.
- `[TODO]` `task-64` Artefact Flashcards (Q/R simple, auto-généré post-transcript).
- `[TODO]` `task-68` Summary Short + Detailed (deux modes de résumé).
- `[TODO]` `task-69` Onglet Brut — transcript/texte extrait/OCR brut accessible via API.
- `[TODO]` `task-71` Supprimer le quiz worker et toutes les références quiz.
- `[TODO]` `task-72` Benchmark LLM pour la génération d'artefacts.

### Phase 4 (Semaines 9-11): Mobile share-first
Objectif: livrer l'expérience mobile native complète et les premiers usages bibliothèque/V1 côté app.
Note backlog:
- `task-61` est déjà en cours, mais sa fermeture dépend encore des entrypoints natifs mobile (`task-37`, `task-38`, `task-39`) et de la validation device sur WhatsApp texte/audio.
- `[TODO]` `task-36` Mobile foundation (shell, navigation, auth/refresh session).
- `[TODO]` `task-37` Android Share Intent -> inbox app.
- `[TODO]` `task-38` iOS Share Extension -> inbox app.
- `[TODO]` `task-39` Écrans share-first (inbox, détail média, transcript, actions artefacts, historique).
- `[TODO]` `task-40` Offline queue + sync/retry réseau.
- `[TODO]` `task-7` Validation UX mobile complète (small/standard devices, erreurs/retry).
- `[TODO]` `task-41` Validation E2E mobile manuelle (matrice apps source + devices).
- `[TODO]` `task-56` In-app digest (daily + weekly) avec résumés courts.
- `[TODO]` `task-63` Spaced Repetition FSRS sur Flashcards.
- `[TODO]` `task-66` Dossiers hiérarchiques (organisation des médias).
- `[TODO]` `task-67` Tags utilisateur (métadonnées médias).
- `[TODO]` `task-74` Recherche sur métadonnées (titre, tags, source, dossier) — volet metadata de la recherche V1.
- `[TODO]` `task-53.1` Recherche lexicale full-text sur transcripts (Typesense Cloud) — volet full-text complémentaire. Permet à l'utilisateur de retrouver un média via le contenu parlé/écrit du transcript, pas seulement par ses métadonnées. Isolation multi-tenant par `user_id` via scoped API keys. Validée 2026-04-28.

### Phase 5 (Semaines 12-13): Release stores
Objectif: publication progressive puis production.
- `[TODO]` `task-42` CI/CD mobile signing + distribution interne (TestFlight/Internal Testing).
- `[TODO]` `task-50` Automatisation E2E mobile (Maestro-first) sur builds internes + fallback Appium cible si requis.
- `[TODO]` `task-43` Compliance stores (privacy policy, terms, data safety/app privacy).
- `[TODO]` `task-44` Assets store + metadata + pre-review QA.
- `[TODO]` `task-45` Publication production + runbook hotfix/rollback.

### Chantier transverse (en parallèle des phases)
Objectif: qualité opérationnelle, sécurité et maîtrise des coûts.
- `[TODO]` `task-46` Dashboards/SLO/alerting ingestion -> transcription -> artifacts.
- `[DONE]` `task-47` URL safety hardening (validation stricte + blocage domaines malveillants).
- `[TODO]` `task-48` Guardrails coûts LLM/transcription/artefacts.
- `[TODO]` `task-65` Benchmark coûts unitaires + proposition pricing V1.
- `[DONE]` `task-53` Cadrer l'implémentation de la recherche media pour le MVP.
- `[TODO]` `task-53.1` Cadrer la recherche lexicale par utilisateur dans la base de transcripts media.
- `[TODO]` `task-58` Abonnement flux RSS — auto-ingestion des nouveaux items dans le pipeline. (post-V1 confirmé)
- `[TODO]` `task-62` Ingestion de newsletters par email. (post-V1 confirmé)
- `[TODO]` `task-73` Analyse cloud provider (AWS vs alternatives).

---

## Checklists de Validation

### Checklist Fonctionnelle
- [ ] Lien partagé depuis app tierce -> ingestion réussie.
- [ ] Partage WhatsApp texte/audio -> ingestion via le flux shared-content quand `task-61` est clôturée.
- [ ] Transcription brute fidèle disponible.
- [ ] Summary Short / Summary Detailed disponibles selon le scope backlog.
- [ ] Flashcards V1 disponibles selon la stratégie post-transcript backlog.
- [ ] Génération fiche de notes on-demand OK.

### Checklist Réutilisation Existant
- [ ] Pipeline `download_worker` réutilisé.
- [ ] Pipeline `transcription/deepgram_worker.py` réutilisé.
- [ ] `podcast_index.py` réutilisé.
- [ ] Logique de matching podcast extraite depuis `playlist_sync.py` / `tosum_sync.py`.
- [ ] `summarization_worker.py` réutilisé/étendu pour les résumés V1.
- [ ] `quiz/worker.py` retiré du scope V1 si `task-71` est exécutée.
- [ ] Aucun fallback runtime legacy (`episode_guid` / compatibilité `episode_submission.py`) actif en cible.

### Checklist Suppressions Demandées
- [x] Spotify playlists tracking retiré backend/frontend/infra. (`task-13` Done)
- [x] Envoi emails résumé/quiz retiré. (`task-14` Done)

### Checklist Store Readiness
- [ ] Build signing iOS/Android validé.
- [ ] Suite E2E mobile automatisee (Maestro) executee sur builds internes avec resultats exploitables.
- [ ] Politique de confidentialité publiée.
- [ ] Crash-free session rate cible atteinte.

---

## Annexe: Mapping Variables d'Environnement

### Nouvelles Variables
```bash
# ingestion canonique
MEDIA_INGESTION_ENABLED=true
MEDIA_INGESTION_TIMEOUT_SECONDS=120
MEDIA_DUPLICATE_WINDOW_DAYS=30

# Connecteurs
YOUTUBE_INGESTION_QUEUE=youtube-ingestion-queue
YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS=20
YTDLP_TIMEOUT_SECONDS=30
ARTICLE_EXTRACTOR_MODE=readability

# Artefacts
ARTIFACT_GENERATION_ENABLED=true
ARTIFACT_TYPES_ALLOWED=summary_short,summary_detailed,notes,flashcards
NOTES_LLM_MODEL=<provider/model chosen via task-72>
# quota/pricing: TBD via task-35 et task-65

# Notifications
ENABLE_CONTENT_EMAIL_NOTIFICATIONS=false
ENABLE_AUTH_EMAILS=true

# Mobile
MOBILE_DEEP_LINK_SCHEME=mediasummarizer
MOBILE_API_BASE_URL=https://api.yourdomain.com
MOBILE_ENABLE_SHARE_EXTENSION=true
```

### Variables à Déprécier
```bash
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI
SPOTIFY_SYNC_MAX
SPOTIFY_LISTEN_THRESHOLD_PERCENT
ENABLE_QUIZ_EMAIL
```

---

## Note de challenge finale

Ce plan évite de recoder le coeur technique le plus coûteux en réutilisant la chaîne audio/transcription, PodcastIndex, idempotence et workers LLM existants. Le principal refactor critique est le découplage de la finalisation métier actuellement liée à l'email, indispensable pour passer à un produit mobile centré sur la transcription et les artefacts à la demande.
