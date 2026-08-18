# Error handling: de l'API a l'UI

## Objectif
Fournir une experience utilisateur claire sans exposer des details techniques, tout en gardant une observabilite solide pour l'equipe (logs, monitoring, support).

## Principes clefs
- L'utilisateur voit uniquement ce qui est actionnable.
- Les erreurs internes restent generiques cote UI.
- Le front utilise des codes internes pour choisir un message humain.
- Les logs et le monitoring contiennent le detail technique (pas l'UI).

## Taxonomie simple (actionnable vs non-actionnable)
- Actionnable: l'utilisateur peut resoudre (session expiree, validation, ressource non trouvee, permission insuffisante).
- Non-actionnable: l'utilisateur ne peut rien faire (bug, exception, panne, timeout serveur, dependance indisponible).

## API: contrat d'erreur standard
### Mapping HTTP
- 4xx: erreurs client, souvent actionnables
- 5xx: erreurs serveur, non actionnables

### Enveloppe de reponse
Exemple JSON (non visible directement par l'utilisateur final):
```json
{
  "error": {
    "code": "SESSION_EXPIRED",
    "message": "Session expired",
    "request_id": "req_123456"
  }
}
```

### Regles
- 5xx: message generique (ex: "Error"), pas de details techniques.
- 4xx: code stable pour le front + message court pour debug (pas affiche tel quel).
- Toujours renvoyer un `request_id` pour l'investigation.
- Ne jamais renvoyer stack traces, details SQL, noms internes.

## UI: messages utilisateur
### Regles
- Afficher des messages courts, empathiques et orientes action.
- Ne jamais afficher les codes internes.
- Proposer une action (CTA) quand possible.

### Exemples
- 401/SESSION_EXPIRED: "Votre session a expire. Veuillez vous reconnecter."
- 403/NOT_AUTHORIZED: "Vous n'avez pas les droits pour cette action."
- 404/NOT_FOUND: "Element introuvable."
- 422/VALIDATION_ERROR: "Veuillez corriger les champs en erreur."
- 5xx/UNKNOWN: "Une erreur est survenue. Merci de reessayer."

### Recommandations UX
- Un seul message visible a la fois.
- Pas de jargon technique.
- Afficher un identifiant de suivi si necessaire (ex: "Reference: req_123456").

## Logs: detail technique et securite
### Regles
- Logs structures (JSON) avec: request_id, user_id, endpoint, method, status, error_code.
- Niveau: ERROR pour 5xx, WARN pour 4xx non attendus, INFO pour 4xx attendus.
- Redaction/masquage des donnees sensibles (PII, tokens, credentials).
- Conserver le detail technique en interne (stack trace, contexte).

### Exemple de log structure
```json
{
  "level": "ERROR",
  "request_id": "req_123456",
  "user_id": "user_789",
  "error_code": "DB_TIMEOUT",
  "message": "Database timeout after 30s",
  "path": "/api/summaries",
  "status": 500
}
```

## Monitoring et alerting
### Indicateurs utiles
- Taux de 5xx par endpoint
- Latence P95/P99
- Erreurs par dependance (DB, API tierces)
- Taux d'erreur par version deployee

### Alertes
- Pic de 5xx au-dessus d'un seuil
- Degradation soudaine de la latence
- Echecs repetes sur un meme job

## Support et diagnostic
- Afficher un `request_id` cote UI (optionnel, mais utile pour le support).
- Journaliser une trace complete cote serveur.
- Documentation interne: mapping error_code -> cause probable -> action.

## Checklist de mise en place
- [ ] Definir un catalogue de codes d'erreur internes stables
- [ ] Mapper les codes aux messages UI
- [ ] Forcer les 5xx a retourner un message generique
- [ ] Ajouter request_id partout (API, logs, UI)
- [ ] Mettre en place logs structures
- [ ] Mettre en place alertes sur 5xx et latence

## Regle d'or
Si l'utilisateur peut agir -> message explicite + action.
Si l'utilisateur ne peut pas agir -> message generique + lien support si besoin.
