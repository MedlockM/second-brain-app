# Registre des feedbacks beta TestFlight

Un feedback par ligne, une fois qu'il est **tranché**. Ce fichier n'est pas un journal d'activité :
c'est la moitié durable du mécanisme de déduplication du triage quotidien.

## Comment il est lu

`.claude/agents/feedback-triage.md` considère qu'un feedback est **nouveau** si et seulement si son
`Feedback-Id` n'apparaît **ni** ici **ni** dans le message de commit d'une branche `feedback/*`.
Les deux ensembles se répartissent la mémoire :

| Où | Ce que ça veut dire |
|---|---|
| branche `feedback/*` vivante | proposition préparée, **en attente** de la décision de l'owner |
| ligne dans ce fichier | **tranché**, ne reviendra jamais |
| nulle part | nouveau, à traiter au prochain run |

La dédup est donc ancrée sur des **identifiants**, jamais sur la date du run précédent — la
convention posée par l'en-tête de `.github/workflows/mobile-build-watch.yml`, « parce que le
planificateur dérive et laisse tomber des runs ». Conséquence pratique : un matin manqué se rattrape
tout seul, et il n'existe aucun fichier d'état à réparer.

Un **no-go** s'inscrit ici comme un go. C'est ce qui l'empêche d'être reproposé le lendemain, puis
tous les jours suivants.

## Ce qu'on n'écrit pas ici

Le dépôt est public (`AGENTS.md`, « Never write secrets or account identity »). Donc :

- **jamais** l'e-mail ni le nom d'un testeur — les `Feedback-Id` d'Apple sont opaques et ne
  désignent personne ;
- **jamais** le `logText` brut d'un crash : il porte des chemins de conteneur et des identifiants
  d'incident. Seul le diagnostic qu'on en tire est écrit ;
- **jamais** de capture d'écran. Elles restent dans `.testflight-feedback/`, gitignoré, et l'owner
  les a déjà dans TestFlight.

## Issues possibles

| Issue | Sens |
|---|---|
| `merged` | go de l'owner, branche mergée sur `main` |
| `declined` | no-go de l'owner, branche supprimée — la raison est obligatoire |
| `no-action` | rien d'exploitable dans le feedback (vide, ou capture sans commentaire ni indice) |
| `backlog` | demandait un design ou un choix technique non tranché ; parti en tâche de backlog, dont l'id est en note |

## Feedbacks tranchés

| Feedback-Id | Date | Type | Build | Issue | Diagnostic / raison |
|---|---|---|---|---|---|
| `AEkNxirFwx5dX-XQa_sLdtM` | 2026-09-04 | bug | 4 | `merged` | Splash jamais masqué sur un cold start par partage : `preventAutoHideAsync()` au niveau module, seul `hideAsync()` dans la route `/`, que `+native-intent` court-circuite vers `/(tabs)/inbox`. `SplashGate` sous `AuthProvider` + `initAuth()` qui ne peut plus rester bloqué sur un `SecureStore` en échec. |
| `APfAZXNH8eTYJKcG1KxlZh4` | 2026-09-04 | ui | 6 | `merged` | Écart de section hérité par chaque rangée de tuiles (`marginBottom` du slot) + `minHeight: 112` et `justifyContent: flex-start`. Porté en `rowGap`/`marginBottom` sur la grille : ≈ 72 → ≈ 39 px entre rangées. Repro en Display Zoom (320 pt). |
| `AFmAenXhNBmN8_vbnUeTEts` | 2026-09-04 | ui | 6 | `merged` | Pas un padding manquant mais un débordement de 32 pt : encadré en `flex: 1`, enfants à hauteur intrinsèque, résumé dimensionné pour 390 pt. La carte mesure sa boîte et abaisse le plafond de lignes par puce (2 à 320 pt, 3 conservé à 390 pt). `Bullets.tsx` passe en `rowGap`, ce qui touche aussi l'écran Artefacts. |
| `AMJ0KSQjGg3YQ0EeAOegfk8` | 2026-09-04 | amélioration | 6 | `backlog` | Vignette d'un média partagé absente jusqu'à la fin de la transcription. Rien de local à afficher : `InboxItem` ne porte aucun URI de fichier, la tuile lit `image_url`/`media_image` du serveur. Owner : émission plus tôt côté backend plutôt que plombage de l'URI local, donc tâche unique sans benchmark → **task-353**. |
