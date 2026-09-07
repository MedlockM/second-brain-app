---
id: task-367
title: >-
  Collecter et stocker le fuseau horaire IANA de l'utilisateur pour les
  notifications de Digest
status: Done
assignee: []
created_date: '2026-09-06 16:11'
labels:
  - mobile
  - backend
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Pourquoi maintenant, et séparément

Le Digest sera notifié à **18h30 heure locale** de l'utilisateur (daily) et **lundi 9h30 locale** (weekly). Or aucun fuseau horaire n'est stocké nulle part dans le dépôt : tout le digest raisonne en UTC. 18h30 UTC, c'est 20h30 à Paris et 13h30 à New York.

Cette tâche ne fait que **collecter et stocker le fuseau**. Elle n'envoie aucune notification et ne dépend d'aucun choix de chemin de livraison : elle peut donc partir avant le benchmark, et c'est souhaitable — au moment où les notifications seront livrées, les fuseaux seront déjà connus pour les testeurs actifs, au lieu d'un premier envoi manqué.

## Le moyen est déjà dans le dépôt

`expo-localization` est **déjà installé** (`~55.0.18`) et déjà utilisé pour la détection de langue dans `mobile/src/i18n/index.tsx`. Son `getCalendars()[0].timeZone` renvoie le fuseau IANA de l'OS.

**Aucune dépendance nouvelle, donc aucun build EAS** : le fingerprint ne bouge pas, la tâche part en OTA.

## Ce qui est décidé et n'est pas à rediscuter

- **On stocke le nom IANA** (`"Europe/Paris"`), **jamais un décalage horaire**. Un `+02:00` stocké serait faux six mois par an ; le nom IANA gère l'heure d'été sans aucune logique côté serveur.
- **Le champ se range sur `User`**, à côté de `reading_language` (`media_summarizer/core/models/user.py`), avec la même mécanique de persistance et de lecture.
- **Rafraîchi à chaque passage de l'app au premier plan**, pas seulement à l'inscription : un utilisateur qui voyage voit ses notifications suivre, sans rien faire.
- **Aucune question posée à l'utilisateur, aucun écran de réglage.** Si le fuseau doit un jour être modifiable à la main, ce sera une autre tâche.
- L'écriture ne part que si la valeur a changé : pas d'écriture DynamoDB à chaque foreground.

## Le cas « fuseau inconnu »

Un compte qui n'a pas rouvert l'app depuis la livraison n'a pas de fuseau. Décision owner : **on ne notifie pas** tant qu'on ne sait pas, plutôt que de replier sur UTC et de sonner à 20h30 chez lui. Le champ reste donc légitimement vide et les consommateurs doivent le tolérer.

Le premier passage au premier plan règle le cas.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de valeur par défaut fabriquée, pas de rétro-remplissage à UTC, pas de migration des comptes existants : le champ est vide jusqu'à ce que l'app le renseigne.

## Notes pour l'owner (pas des ACs)

- Cette tâche seule ne produit rien de visible : elle remplit une colonne. Sa vérification est une lecture DynamoDB.
- Le déploiement se joue au push sur `main`. Comme aucune dépendance native n'est touchée, c'est une OTA et non un build.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le modèle User de media_summarizer/core/models/user.py porte un champ de fuseau horaire optionnel, persisté et relu comme reading_language, sans valeur par défaut fabriquée
- [x] #2 L'app lit le fuseau IANA via getCalendars()[0].timeZone d'expo-localization et le transmet au serveur, sans ajouter aucune dépendance au mobile
- [x] #3 La valeur transmise est un nom IANA et jamais un décalage horaire, et le serveur rejette une valeur qui n'est pas un identifiant IANA reconnu
- [x] #4 Le fuseau est réévalué à chaque passage de l'application au premier plan, et n'est écrit que s'il diffère de la valeur déjà stockée
- [x] #5 Aucun écran de réglage ni aucune question n'est ajouté à l'interface pour ce fuseau
- [x] #6 Un compte sans fuseau connu reste valide : le champ demeure vide, sans rétro-remplissage ni repli sur UTC
- [ ] #7 Le trajet complet est vérifié sur l'environnement -dev : après un passage au premier plan, l'enregistrement utilisateur en DynamoDB -dev porte le nom IANA attendu
- [x] #8 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The field is `iana_timezone`, not `timezone`

Two reasons, both cheap to respect now and expensive later:

- **`timezone` is a DynamoDB reserved word.** Every future `ProjectionExpression`
  or `FilterExpression` over `users-*` would have needed an
  `ExpressionAttributeNames` alias — the Digest scheduler that will read this
  column is exactly such a caller. (Verified the hard way: the AWS CLI scan used
  to check the starting state of `users-dev` needed `#tz` before it would run.)
- **It would shadow `datetime.timezone` inside `user.py`,** the very module the
  field lives in, where `datetime.now(timezone.utc)` appears four times.

The explicit name also carries the invariant — IANA name, never an offset — at
every call site, which is the one thing about this field that must not be
forgotten.

### No new dependency, on either side

`expo-localization` was already installed and already read (`getLocales()` for
the interface language), so the mobile half is a `getCalendars()[0].timeZone`
call: the fingerprint does not move and this ships OTA.

Server-side, validation goes through `zoneinfo.available_timezones()`, i.e. the
tz database the runtime already carries. Checked inside the actual base image
rather than assumed:

```
docker run --rm --entrypoint python public.ecr.aws/lambda/python:3.11 \
  -c "import zoneinfo; print(len(zoneinfo.available_timezones()))"
→ 597,  /usr/share/zoneinfo present
```

So no `tzdata` package is needed, and the accepted set follows tzdata releases
instead of a hand-maintained list.

### Rejecting an offset happens on both sides, for different reasons

`normalize_iana_timezone` (`media_summarizer/utils/timezones.py`) is the
authority: it rejects `"+02:00"`, `"UTC+2"`, `"GMT+02:00"`, `"GMT+1"`, unknown
zones, non-strings, and the two tz-directory entries that name no region
(`localtime`, `Factory`). Lookups stay **case-sensitive** — IANA names are, so
lower-casing the way `reading_language` does would turn `"Europe/Paris"` into a
rejection.

The client filters offsets too, and that is not redundant. Expo's own type
documentation lists `'GMT+1'` as a possible answer from `timeZone`; sending it
would mean a request the backend refuses on *every* foreground pass, forever.
`getDeviceTimezone` therefore keeps only values that either carry a region path
(`Europe/Paris`, `Etc/GMT+2`) or are purely alphabetic (`UTC`).

### "Only written when it changed" is enforced twice

The client compares the device zone against what it knows the backend holds, and
`PATCH /api/auth/me` additionally skips the `put_item` when no value actually
moves. The server-side half is what makes the guarantee true regardless of the
client, and it applies to `reading_language` as well: a no-op PATCH no longer
rewrites the row. Nothing reads `users.updated_at`, so nothing depended on that
write happening.

The client-side "already sent" memo is **keyed by account id**, because
`UserPreferencesProvider` outlives a sign-out: unkeyed, a second account signing
in on the same device would be skipped as already-synced.

### Five hand-built session payloads became one projection

`{"id": ..., "email": ..., "reading_language": ...}` was copy-pasted into
register, login, refresh and the two native social logins. Adding a second
profile field to five literals is one forgotten call site per field, so they now
go through `AuthUser.from_user()`.

### AC#7 — what was verified, and what is left to the owner

Not reachable from the worktree: it needs this code **deployed** (it deploys on
push to `main`, after this agent is gone) *and* a physical device foreground
pass. Left unticked per AGENTS.md.

What was verified against the real `-dev` infrastructure instead — the data
layer, end to end, through the production code path:

- All **18 real `users-dev` rows** rehydrate through the patched `User` model
  with `iana_timezone is None`, and re-serialising them omits the attribute
  entirely. No row carried it before and none carries it after: no back-fill,
  no UTC fallback (AC#1 read half, AC#6).
- A throwaway row driven through `database_async.create_user` →
  `update_user` → `get_user_by_id` against the real `users-dev` table came back
  `None`, then `'Europe/Paris'`, then `'America/New_York'` (the travelling case),
  with `reading_language` intact throughout. The probe row was deleted and the
  table re-verified at 18 rows / 0 occurrences of the attribute.
- `normalize_iana_timezone` accepts `Europe/Paris`, `America/New_York` (padded),
  `UTC`, `Etc/GMT+2` and rejects `+02:00`, `UTC+2`, `GMT+02:00`, `GMT+1`,
  `GMT-8`, `europe/paris`, `localtime`, `Factory`, `''`, `None`, `42`,
  `Mars/Olympus`.

**Owner follow-up after this merges and `main` is pushed** (OTA, not a build):
open the app on a device, then confirm the row carries the zone:

```
aws dynamodb get-item --table-name users-dev --region eu-west-3 \
  --key '{"id":{"S":"<your dev user id>"}}' \
  --projection-expression "iana_timezone"
```

Then change the device time zone in system settings, background and re-foreground
the app, and re-run the same read to see it follow.

### Not done, deliberately

No automated tests (AGENTS.md: none unless explicitly requested). The checks
above were run as throwaway scripts against real `-dev` resources and deleted;
nothing test-shaped was committed.
<!-- SECTION:NOTES:END -->
