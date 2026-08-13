---
id: task-260
title: >-
  Runbook owner — confirm the four Google Play account eligibility gates before
  any Android publication
status: To Do
assignee: []
created_date: '2026-08-13 19:01'
labels:
  - release
  - owner-only
  - blocker-launch
  - phase-10
dependencies: []
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
⚠️ **MANUEL — OWNER UNIQUEMENT. NE JAMAIS DISPATCHER VERS UN SUBAGENT.**

Toutes les étapes se passent dans la Play Console derrière l'authentification de l'owner, et plusieurs manipulent des données d'identité et bancaires. Aucun agent ne peut y accéder, et aucun agent ne doit tenter de les reconstituer.

## Pourquoi cette tâche

Les $25 payés le 2026-06-01 achètent un compte développeur, pas le droit de publier. Le repo ne contient aucune preuve d'où en sont les vérifications d'éligibilité — l'information « en cours » n'a pas été actualisée depuis juin 2026. Ce runbook sert à établir cet état, puis à le consigner. Il est possible que tout soit déjà fait : dans ce cas la tâche consiste seulement à le prouver et à le dater.

L'étape 4 est la seule qui coûte du **temps calendaire** et non de l'administratif. Faites-la en premier si vous n'en lisez qu'une.

## ⛔ Ce qui ne doit jamais entrer dans le repo

Le dépôt est **public**. Ne consignez nulle part, dans aucun fichier suivi : adresse postale, numéro de téléphone, numéro de pièce d'identité, D-U-N-S, coordonnées bancaires, identifiants fiscaux, email racine du compte, emails des testeurs. Ce qui se consigne est uniquement du **statut** : « vérifié », « en attente depuis le JJ/MM », « non applicable », plus une date.

---

## Étape 0 — Déterminer le type de compte (2 minutes, conditionne les étapes 3 et 4)

Play Console → **Paramètres** → **Détails du compte développeur** → champ *Type de compte*.

Notez si le compte est **personnel** ou **organisation**. Les étapes 3 et 4 ne s'appliquent pas de la même façon selon la réponse, et il vaut mieux le savoir avant d'engager quoi que ce soit.

## Étape 1 — Vérification d'identité du compte développeur

Play Console → **Paramètres** → **Détails du compte développeur** → section *Vérification de l'identité*.

- Si le statut est **Vérifié** : relevez la date, passez à l'étape 2.
- Si le statut est **Action requise** ou **En attente** : fournissez ce qui est demandé (nom légal, adresse, téléphone, pièce d'identité ; pour un compte organisation, également le D-U-N-S). Comptez plusieurs jours de traitement côté Google.
- Si une **échéance** est affichée, notez-la : Google suspend les comptes qui la dépassent, et une suspension rendrait toutes les étapes suivantes sans objet.

## Étape 2 — Profil de paiement Google Payments (bloquant pour les abonnements)

Play Console → **Paiements** → **Profil de paiement**, puis les sous-sections *Informations fiscales* et *Coordonnées bancaires*.

C'est le prérequis dur des abonnements : sans profil de paiement vérifié, **`task-238` ne peut pas aboutir** — on ne crée pas de produit d'abonnement Play sans lui — et RevenueCat n'aura rien à valider côté Android. L'app pourrait être publiée sans, mais rien ne serait vendable.

- Vérifiez les trois éléments séparément : identité du bénéficiaire, informations fiscales, compte bancaire. L'un peut être validé et les autres non.
- Le nom du bénéficiaire doit correspondre au titulaire du compte bancaire, sinon la validation échoue et reste en attente sans explication claire.
- Notez le statut de chacun et la date.

## Étape 3 — Décider de l'adresse développeur publique

Play Console → **Paramètres** → **Détails du compte développeur** → *Coordonnées du développeur*.

Depuis 2023, l'email et l'adresse physique du développeur s'affichent publiquement sur la fiche Play. Pour un compte personnel, cela signifie **publier votre adresse personnelle**.

Trois options, à trancher **avant** de remplir la fiche Store — revenir en arrière après publication est plus lourd :

1. L'accepter en l'état.
2. Utiliser une adresse de domiciliation ou une boîte postale, si elle est acceptée comme adresse de contact.
3. Passer le compte en **organisation**, ce qui évite l'adresse personnelle mais exige un numéro D-U-N-S (démarche gratuite mais qui prend de l'ordre de 1 à 2 semaines).

Consignez la décision et sa raison — pas l'adresse elle-même.

## Étape 4 — Vérifier l'exigence de closed testing (le seul poste à délai calendaire)

Play Console → **Tests** → **Test fermé**, et l'écran de demande d'*accès à la production*.

Google impose aux comptes développeur **personnels** créés après novembre 2023 un test fermé d'environ **12 testeurs pendant 14 jours continus** avant d'autoriser la demande d'accès à la production. Le compte datant du 2026-06-01, l'exigence s'applique très probablement s'il est personnel (étape 0).

⚠️ Les seuils et le périmètre de cette règle ont changé plusieurs fois : **la Play Console est la seule source de vérité**, pas cette description ni le plan de lancement. Lisez ce qu'affiche l'écran d'accès à la production pour *votre* compte.

Si l'exigence s'applique :

1. Notez le nombre exact de testeurs et la durée exigés, tels qu'affichés.
2. Elle ne s'achète pas et ne se parallélise pas : elle borne par le bas la date de publication Android. Comptez au minimum les 14 jours **plus** le délai de review de la demande d'accès.
3. Elle nécessite un build Android installable et un groupe de testeurs — donc `task-163` (build Android unique) doit être faite avant de démarrer le compteur, et `task-258` doit avoir désarmé le workflow de build avant qu'un `EXPO_TOKEN` ne soit posé, sous peine de soumissions involontaires.
4. Reportez la date de démarrage réelle dans `docs/V1_LAUNCH_PLAN.md`, Phase 2.2 : c'est elle qui détermine la date de lancement Android la plus proche.

## Étape 5 — Consigner le résultat

Mettez à jour `docs/V1_LAUNCH_PLAN.md` en deux endroits déjà prévus pour ça : la **Phase 2, point 2** (les quatre vérifications détaillées) et la ligne **Google Play Console** du tableau des comptes externes. Remplacez « à confirmer par l'owner » par le statut réel et sa date pour chacune des quatre portes. Si une porte est encore en attente côté Google, écrivez-le avec la date de dépôt : un « en attente depuis le 2026-08-13 » est une information utile, un « en cours » sans date ne l'est pas — c'est précisément ce qui a rendu cette tâche nécessaire.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le type de compte (personnel ou organisation) est consigné dans `docs/V1_LAUNCH_PLAN.md`, Phase 2.2
- [ ] #2 Le statut de la vérification d'identité du compte développeur est consigné avec sa date — vérifié, ou en attente depuis une date précise, ou action requise avec l'échéance affichée par Google
- [ ] #3 Le statut du profil de paiement Google Payments est consigné pour ses trois volets séparément (identité du bénéficiaire, informations fiscales, coordonnées bancaires), chacun avec sa date
- [ ] #4 La décision sur l'adresse développeur publique est consignée avec sa raison (acceptée telle quelle, domiciliation, ou passage en compte organisation) — sans l'adresse elle-même
- [ ] #5 L'exigence de closed testing est tranchée sur la base de ce qu'affiche la Play Console : applicable ou non, et si applicable le nombre de testeurs et la durée exacts, plus la date de démarrage visée ou effective
- [ ] #6 La ligne « Google Play Console » du tableau des comptes externes du plan ne contient plus « à confirmer par l'owner » mais l'état réel
- [ ] #7 Aucune donnée personnelle n'a été écrite dans un fichier suivi : ni adresse, ni téléphone, ni pièce d'identité, ni D-U-N-S, ni coordonnées bancaires ou fiscales, ni email des testeurs — vérifiable par un `git diff` relu avant commit
- [ ] #8 Si le closed testing s'applique, `task-238` porte une note indiquant que sa partie Play reste bloquée tant que le profil de paiement n'est pas vérifié
<!-- AC:END -->
