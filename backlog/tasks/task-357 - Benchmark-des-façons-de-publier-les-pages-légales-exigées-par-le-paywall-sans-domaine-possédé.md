---
id: task-357
title: >-
  Benchmark des façons de publier les pages légales exigées par le paywall, sans
  domaine possédé
status: To Do
assignee: []
created_date: '2026-09-04 15:26'
labels:
  - benchmark
  - mobile
  - compliance
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Recherche exhaustive des façons de publier deux pages publiques — **conditions d'utilisation** et **politique de confidentialité** — joignables depuis l'écran d'achat de l'app, sachant que **le projet ne possède aucun domaine**.

## Pourquoi cette question se pose

`mobile/src/constants/legal.ts` fait aujourd'hui pointer `TERMS_URL` et `PRIVACY_POLICY_URL` vers deux chemins d'un domaine qui **n'appartient pas au projet** (voir la note « aucun domaine n'est possédé » : la résolution DNS ne prouve pas la propriété). Une adresse de contact de confidentialité est exposée sur ce même domaine.

L'enjeu n'est pas cosmétique et le fichier le documente lui-même : la guideline **3.1.2 d'Apple** et la politique d'abonnement de **Google Play** exigent que l'écran d'achat porte des liens **fonctionnels** vers ces deux pages ; des métadonnées renseignées dans App Store Connect ou la Play Console ne suffisent pas, et **un lien qui répond 404 est rejeté exactement comme un lien manquant**. C'est donc un bloquant de première soumission.

## Dimensions à couvrir

1. **Acceptation par les stores** — c'est le critère qui prime. Pour chaque option, chercher des faits vérifiables sur les rejets constatés : une page derrière un mur de connexion, un lien de partage Notion ou Google Docs, un raccourcisseur, un sous-domaine gratuit sont-ils acceptés en pratique ? Citer des sources datées, pas des impressions.
2. **Le nom d'hôte** — un sous-domaine gratuit (type pages d'un hébergeur de code) est-il acceptable, ou l'examen attend-il un domaine cohérent avec l'éditeur ? Distinguer ce que les règles **exigent** de ce que les examinateurs **observent**.
3. **Coût réel sur un an** — achat et renouvellement d'un nom de domaine le cas échéant, hébergement, certificat, et le coût nul quand il l'est.
4. **Effort de mise en place et de mise à jour** — publier est une chose, corriger une clause deux mois plus tard en est une autre. Qui peut mettre à jour, par quel chemin.
5. **Génération du contenu** — options qui fournissent aussi le texte (générateurs de politiques, services payants au mois) versus hébergement seul. Ce que ces générateurs valent juridiquement, et ce qu'ils coûtent.
6. **L'adresse de contact de confidentialité** — une politique doit exposer un moyen de contact, et la section « accès / portabilité » de l'app y renvoie déjà. Traiter le cas d'une adresse sur un domaine possédé versus une adresse chez un fournisseur grand public : est-ce accepté, et quelles conséquences.
7. **Pérennité et réversibilité** — ce qu'il en coûte de déménager les pages ensuite, sachant qu'une URL imprimée dans un binaire déjà distribué ne se corrige que par une nouvelle version.

## Contraintes du projet à intégrer

- Développeur solo, sans équipe ni budget d'infrastructure dédié ; le mail est le canal d'alerte, il n'y a pas d'astreinte.
- L'app est en TestFlight et sur la piste interne Android, **jamais soumise à un store** : la contrainte est la **première** soumission, pas une migration.
- Les deux URL sont lues depuis un seul fichier, donc le coût de changement côté code est faible ; le coût est ailleurs — dans le fait de publier et de tenir les pages.

## Livrable

Un `docs/research/task-XXX-<description-courte>/README.md` avec le front-matter de décision (`owner_decision: pending`), le tableau comparatif, et une recommandation argumentée. **Aucune implémentation** : ni modification de `legal.ts`, ni achat, ni publication. La tâche d'implémentation liée s'en chargera après votre décision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tableau comparatif d'au moins 5 options couvrant les familles distinctes : domaine acheté + hébergement statique, pages d'un hébergeur de code, générateur/hébergeur de politiques payant, page d'un service de site tiers, document partagé publiquement
- [ ] #2 Pour chaque option, l'acceptation par l'App Store et par Google Play est documentée par des sources vérifiables et datées, en distinguant la règle écrite de la pratique d'examen constatée
- [ ] #3 Coût sur douze mois chiffré par option, renouvellement de domaine inclus quand il y en a un
- [ ] #4 Le cas de l'adresse de contact de confidentialité est traité explicitement, y compris l'option d'une adresse hors domaine possédé
- [ ] #5 Le coût de déménagement ultérieur des pages est évalué pour chaque option, en tenant compte du fait qu'une URL embarquée dans un binaire distribué n'est corrigeable que par une nouvelle version
- [ ] #6 Recommandation finale argumentée avec compromis explicites, dans un README portant `owner_decision: pending` en front-matter
- [ ] #7 Aucun fichier de `mobile/` n'est modifié par cette tâche
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-09-04, mode **initial** (aucun dossier `docs/research/task-357-*` n'existait, aucun `README.owner-rejected-*`, aucune `complement-request-*`).

Livrable : `docs/research/task-357-legal-pages-hosting/README.md` (front-matter `owner_decision: pending`, section `Owner Validation` laissée vide pour l'owner).

Contenu produit :
- **§0, deux affirmations du dépôt corrigées.** (a) L'obligation de liens sur l'écran d'achat ne vient pas de la guideline 3.1.2 mais de l'**ADPLA Schedule 2 §3.8(b)** (« Links to Your Privacy Policy and Terms of Use must be accessible within Your Licensed Application »), complétée par les guidelines 5.1.1(i) et 2.1(a) ; Google n'exige **aucun** lien vers des conditions d'utilisation et accepte du *texte* in-app. (b) La prémisse « une URL embarquée ne se corrige que par une nouvelle version » est fausse pour les constantes JS (EAS Update, `runtimeVersion: fingerprint`) et vraie seulement pour les URL de métadonnées App Store Connect (Privacy Policy URL et Support URL ne sont pas éditables sans nouvelle version).
- **§1**, grille de 12 critères extraite des textes normatifs : aucun ne porte sur le nom d'hôte. §1bis : sans EULA personnalisée, l'EULA standard d'Apple s'applique, donc le périmètre minimal publiable est **une** page.
- **§2**, règle écrite contre pratique constatée, avec un encadré d'honnêteté : **aucun rapport de refus daté n'a pu être obtenu** (moteurs de recherche tous en défi anti-robot / 429 / hors sujet depuis cet environnement). Les CGU des hébergeurs remplacent l'anecdote.
- **§3**, tableau comparatif de **7 options** couvrant les 5 familles demandées (domaine acheté + Cloudflare Pages ; tout-AWS Route53/S3/CloudFront ; `*.pages.dev` ; `*.github.io` ; générateur hébergé ; service de site tiers ; document publié).
- **§4** coûts douze mois par poste, **§5** chemins de clics exacts (Cloudflare, App Store Connect, Play Console), **§6** ce qu'un générateur achète réellement, **§7** adresse de contact de confidentialité (4 formes comparées ; aucune adresse réelle écrite, le dépôt étant public), **§8** coût de déménagement par option, **§9** liste explicite de ce qui n'a pas pu être vérifié, **§10** sources datées du 2026-09-04.

Recommandation : **option A1** — acheter un `.com`, zone chez Cloudflare, deux pages statiques sur Cloudflare Pages depuis le dépôt, adresse de contact via Cloudflare Email Routing ; **~11 $ sur douze mois**, hébergement, TLS, DNS et transfert d'e-mail à 0 $. Compromis acceptés listés dans le README (renouvellement annuel, DNS hors Terraform, variante A2 tout-AWS écartée, absence de preuve de terrain).

**La recommandation attend la validation de l'owner** : `owner_decision` reste `pending`, la tâche reste `To Do`, et aucune case d'AC n'est cochée. Aucun fichier de `mobile/` n'a été modifié (AC#7) — la tâche d'implémentation liée est task-358.
<!-- SECTION:NOTES:END -->
