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
| _(aucun pour l'instant)_ | | | | | |
