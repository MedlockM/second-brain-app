---
id: task-260
title: >-
  Runbook owner — confirm the Google Play account eligibility gates before any
  Android publication
status: To Do
assignee: []
created_date: '2026-08-13 19:01'
updated_date: '2026-09-03 10:14'
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

**`dispatchable: false` posé le 2026-08-21.** L'avertissement ci-dessus n'existait que dans cette description : le front-matter, lui, ne portait pas le verrou, si bien que `scripts/dispatch_backlog.sh` — qui construit sa denylist en lisant `dispatchable: false` dans le front-matter et rien d'autre — laissait cette tâche éligible au dispatch. Sans dépendance non résolue et en priorité `high`, elle serait partie en tête de la sélection de la Phase 1. Le verrou est maintenant là où le script le lit.

## Pourquoi cette tâche

Les $25 payés le 2026-06-01 achètent un compte développeur, pas le droit de publier. Le repo ne contient aucune preuve d'où en sont les vérifications d'éligibilité — l'information « en cours » n'a pas été actualisée depuis juin 2026. Ce runbook sert à établir cet état, puis à le consigner. Il est possible que tout soit déjà fait : dans ce cas la tâche consiste seulement à le prouver et à le dater.

L'étape 4 est la seule qui coûte du **temps calendaire** et non de l'administratif. Faites-la en premier si vous n'en lisez qu'une.

**Constaté le 2026-08-19 (screenshot owner) — une cinquième porte que ce runbook ignorait.** L'accueil de la Play Console affiche le bandeau « Pour publier des applis, terminez la configuration de votre compte de développeur » et deux actions ouvertes : *Confirmer que vous avez accès à un appareil mobile Android* et *Valider votre numéro de téléphone de contact*. La première est l'étape 0 bis ci-dessous ; elle exige un **appareil Android physique**, ce que le runbook d'origine ne mentionnait nulle part. Relevé au même endroit : le compte est de type **personnel** — fait désormais porté par l'étape 0 elle-même et par la Phase 2.2 du plan de lancement, plus par cette parenthèse (c'est en y restant enterré qu'il s'est fait redemander le 2026-08-31).

## ⛔ Ce qui ne doit jamais entrer dans le repo

Le dépôt est **public**. Ne consignez nulle part, dans aucun fichier suivi : adresse postale, numéro de téléphone, numéro de pièce d'identité, D-U-N-S, coordonnées bancaires, identifiants fiscaux, email racine du compte, emails des testeurs. Ce qui se consigne est uniquement du **statut** : « vérifié », « en attente depuis le JJ/MM », « non applicable », plus une date.

---

## Étape 0 — Type de compte : ✅ RÉGLÉ, le compte est PERSONNEL

**Fait établi. Ne pas redemander à l'owner, ne pas rouvrir cette étape.** Le champ
*Type de compte* vit sur Play Console → menu latéral **Compte de développeur** →
carte **À propos de vous** (et non sous « Paramètres » comme l'indiquait le chemin
d'origine). Relevé le **2026-08-19** sur screenshot de l'owner, reconfirmé
explicitement le **2026-08-31**, puis **revu sur pièce le 2026-08-31** sur un
second screenshot de cette page : `Type de compte = Personnel`.
Consigné dans `docs/V1_LAUNCH_PLAN.md` Phase 2.2, première ligne du point 2.

Ce que cette réponse **tranche définitivement** pour les étapes en aval — ce sont
des conséquences mécaniques, pas des hypothèses à revérifier :

- **Étape 3** : l'adresse développeur publique sera une **adresse personnelle**.
  La question n'est pas « est-ce le cas ? » mais « accepte-t-on, domicilie-t-on, ou
  passe-t-on en organisation ? ».
- **Étape 4** : l'exigence de **closed testing s'applique** (compte personnel +
  création postérieure à novembre 2023). Seuls ses paramètres — nombre de testeurs
  et durée — restent à lire dans la Play Console.

## Étape 0 bis — Confirmer l'accès à un appareil Android physique (bloquant dur, ajouté le 2026-08-19)

Play Console → **Accueil** → carte *Terminer la configuration de votre compte de développeur* → *Confirmer que vous avez accès à un appareil mobile Android* → **Afficher les détails**.

Google demande d'installer l'**application mobile Play Console** sur un appareil Android et de s'y connecter avec le compte développeur. Tant que ce n'est pas fait, le bandeau « Pour publier des applis, terminez la configuration de votre compte de développeur » reste affiché et **aucune publication n'est possible** — cette porte est en amont de l'étape 4, pas à côté.

Conséquences pour ce projet :

- **Un émulateur ne convient pas.** Le libellé exige « un véritable appareil mobile Android » et la vérification s'appuie sur l'attestation d'appareil ; un AVD n'est pas certifié Play Protect. L'émulateur reste utilisable pour `task-163` et `task-165` (tester l'app), **pas** pour cette porte-ci. À confirmer sur pièce si vous tentez malgré tout.
- **Il suffit d'un accès temporaire, pas d'un achat.** L'app Play Console se connecte avec *votre* compte Google : installer l'app sur l'appareil d'un proche, s'y connecter, confirmer, puis se déconnecter suffit. Compter 5 minutes.
- La validation du **numéro de téléphone de contact** listée juste en dessous dans la même carte dépend des autres validations (identité + documents approuvés par Google) : elle se débloque après, elle ne se traite pas isolément.

## Étape 1 — Vérification d'identité du compte développeur

> ⚠️ **Chemin corrigé le 2026-08-31 sur screenshot owner.** Le chemin d'origine
> (« Paramètres → Détails du compte développeur → section Vérification de
> l'identité ») **n'existe plus** : Google a sorti la vérification d'identité de la
> page compte pour en faire une entrée de menu autonome. La page *Compte de
> développeur* ne contient plus aucune section de ce nom — elle ne porte que
> *À propos de vous*, *Coordonnées*, *Profil du développeur* et *Comptes de
> développeur associés*.

Play Console → menu latéral gauche → **Validation des développeurs Android**
(entrée détachée en bas de la barre, sous *Aide*) → **onglet « Identité »**.

⚠️ Cette page a **deux onglets** et s'ouvre par défaut sur le mauvais. *Noms des
packages* (onglet par défaut) concerne l'enregistrement des packages — sujet
distinct, traité à l'étape 1 bis ci-dessous. La vérification d'identité est sous
**Identité**. C'est là qu'il faut lire le statut et l'éventuelle échéance.

### ✅ Relevé le 2026-08-31 — aucune action due, aucune échéance

L'onglet *Identité* est **purement informatif**. Il affiche le nom légal et l'adresse
en précisant qu'ils « sont issus de votre compte de développeur Play Console », plus
un lien *Afficher dans le compte de développeur*. Il ne porte **ni statut de
vérification, ni mention « Action requise » ou « En attente », ni échéance, ni aucun
bouton d'action**.

Conclusion consignée : **rien n'est demandé à l'owner sur cette porte au 2026-08-31,
et aucune date limite ne pèse sur le compte.** C'est cohérent avec le fait que la
carte « Terminer la configuration de votre compte de développeur » ne bloque plus la
création d'app depuis le franchissement des portes 1 et 2. Le risque de suspension
évoqué ci-dessous ne s'est donc pas matérialisé.

⚠️ Nuance à ne pas gommer : l'écran ne dit pas non plus « Vérifié ». Il ne fait que
refléter une identité déjà fournie. Et sur *Détails du compte → À propos de vous*,
Google affiche un encart « **L'ajout d'un site nous aide à valider votre compte** » —
signe qu'une marge de validation subsiste. Voir l'étape 1 ter.

Grille d'origine, conservée pour le cas où un statut apparaîtrait plus tard :

- Si le statut est **Vérifié** : relevez la date, passez à l'étape 2.
- Si le statut est **Action requise** ou **En attente** : fournissez ce qui est demandé (nom légal, adresse, téléphone, pièce d'identité ; pour un compte organisation, également le D-U-N-S). Comptez plusieurs jours de traitement côté Google.
- Si une **échéance** est affichée, notez-la : Google suspend les comptes qui la dépassent, et une suspension rendrait toutes les étapes suivantes sans objet.

## Étape 1 ter — Renseigner un site web (non bloquant, mais Google le réclame pour valider)

*Détails du compte → À propos de vous → champ Site Web*, aujourd'hui vide avec la case
« Je n'ai pas de site Web » cochée. Google y affiche : « Nous vous recommandons
d'ajouter un site qui vous représente — **l'ajout d'un site nous aide à valider votre
compte** ».

Ce n'est pas une porte fermée, c'est un levier. Et il ne coûte presque rien puisque
`task-43` (Done) a déjà produit le paquet de conformité : la politique de
confidentialité et les CGU doivent de toute façon être servies à des URLs publiques
pour la fiche Play. Le domaine qui les héberge fait un site développeur valable.

À faire quand ce domaine existe — pas avant, un lien mort dessert la validation.

## Étape 1 bis — Enregistrement des noms de packages (septième porte, découverte le 2026-08-31)

Même page, **onglet « Noms des packages »**. Cette porte n'existait pas dans le
runbook d'origine : elle vient du programme *Android developer verification* annoncé
par Google le **15 juillet 2026**. Le bandeau de la Play Console annonce que « toutes
les applis Play non enregistrées d'ici le **30 septembre 2026** seront supprimées de
Google Play dans le monde entier ».

**Conclusion, après vérification à la source : cette porte ne nous concerne
probablement pas, et il ne faut rien enregistrer manuellement.** Vérifié le
2026-08-31 sur `developer.android.com/developer-verification` et sa FAQ :

- **Play App Signing déclenche l'enregistrement automatique.** La FAQ est explicite :
  « I use Play App Signing, are my apps claimed automatically? — Yes. […] Your
  eligible apps will be part of the automatic registration process. » Google
  annonce enregistrer ainsi **99 %** des apps. Notre app Play utilisera Play App
  Signing (Google le génère à la création de l'app — c'est déjà noté dans `task-163`,
  section *Important*, comme la raison pour laquelle un 2ᵉ OAuth Client ID Android
  sera nécessaire en Phase 10). L'onglet *Noms des packages* affiche donc une liste
  vide simplement parce qu'**aucune app n'existe encore**, pas parce qu'une action
  est due.
- **L'enregistrement manuel sert à deux cas qui ne sont pas les nôtres** : les apps
  distribuées *exclusivement hors Play*, et les clés de signature que le développeur
  gère lui-même hors Play App Signing.
- **L'échéance du 30 septembre 2026 est régionale, pas mondiale.** Elle couvre
  **Brésil, Indonésie, Singapour, Thaïlande**, sur appareils certifiés Android 7+, et
  uniquement via les *magasins participants* (Play, HONOR, OPPO, Galaxy Store, Palm,
  V-Appstore, GetApps). Le déploiement mondial et l'extension à toutes les apps sont
  annoncés pour **2027**. Le bandeau console est donc plus alarmant que la règle.
- **ADB est explicitement exempté** : « Apps installed using ADB won't require
  verification ». L'installation de l'APK de dev sur device (`task-163` AC#7,
  `adb install`) n'est concernée en rien.
- **Les builds EAS `distribution: internal`** (installation par URL/QR, hors magasin)
  ne sont pas couverts par la phase du 30 septembre 2026 — « if users sideload your
  app directly, these new verification requirements won't apply to your app yet » —
  mais le sont par le rollout 2027. À reconsidérer à ce moment-là, pas maintenant.

**Ce qui reste à faire ici : rien d'autre que relever le statut.** Ne pas cliquer sur
*Enregistrer le nom de package*. Enregistrer manuellement `com.secondbrainlabs.core`
avant que l'app Play existe risquerait de le rattacher au keystore EAS plutôt qu'à la
clé Play App Signing, ce qui créerait exactement le genre de désalignement de SHA
contre lequel `task-163` met déjà en garde.

**Point à revérifier en Phase 10**, une fois l'app créée : que l'app apparaît bien
comme *Registered* dans cet onglet grâce à Play App Signing. Si elle n'y est pas, il
faudra enregistrer package + clé — et le format de fingerprint attendu (SHA-1 ou
SHA-256) n'est documenté ni sur la page d'overview ni sur la FAQ, il faudra le lire
dans le formulaire. Les deux empreintes sont récupérables du keystore EAS avec
`keytool -list -v` ou `apksigner verify --print-certs`.

## Étape 2 — Profil de paiement Google Payments (bloquant pour les abonnements)

Play Console → **Paiements** → **Profil de paiement**, puis les sous-sections *Informations fiscales* et *Coordonnées bancaires*.

> ⚠️ **Chemin corrigé le 2026-08-31, et une hypothèse de la veille invalidée.** Le
> menu latéral de ce compte **ne comporte aucune entrée « Paiements »** (Accueil,
> Conformité aux règles, Utilisateurs et autorisations, Gestion des commandes,
> Télécharger des rapports, Compte de développeur, Journal d'activité, Paramètres,
> Aide, Validation des développeurs Android). On en avait déduit que le profil de
> paiement n'existait pas encore : **c'est faux, au moins en partie.**
>
> *Détails du compte → À propos de vous* indique noir sur blanc que « votre nom légal
> et votre adresse **sont issus du profil de paiement Google** », et propose un lien
> **Afficher le profil de paiement** (sortie vers `payments.google.com`). Un profil de
> paiement existe donc bel et bien — logique, il a servi à régler les $25. Il n'a
> simplement pas d'entrée dans le menu Play Console parce qu'il vit hors de celle-ci.
>
> **Le vrai chemin est donc : *Compte de développeur → Détails du compte → À propos de
> vous* → lien *Afficher le profil de paiement*.**

### La distinction qui décide de tout ici : payeur ≠ encaisseur

Ne pas conclure de ce qui précède que l'étape 2 est réglée. Google a **deux objets
distincts**, et seul le second permet de vendre :

1. **Le profil de paiement Google** (*Google payments profile*) — l'identité de
   facturation qui *dépense*. C'est lui qui a payé les $25 et dont Play Console tire
   le nom légal et l'adresse. **Il existe.**
2. **Le compte marchand Google Play** (*merchant account*) — l'objet qui *encaisse*,
   avec informations fiscales et coordonnées bancaires. C'est **lui** le prérequis dur
   des abonnements de `task-238`. Rien dans les écrans relevés le 2026-08-31 ne prouve
   qu'il existe.

C'est le prérequis dur des abonnements : sans profil de paiement vérifié, **`task-238` ne peut pas aboutir** — on ne crée pas de produit d'abonnement Play sans lui — et RevenueCat n'aura rien à valider côté Android. L'app pourrait être publiée sans, mais rien ne serait vendable.

- Vérifiez les trois éléments séparément : identité du bénéficiaire, informations fiscales, compte bancaire. L'un peut être validé et les autres non.
- Le nom du bénéficiaire doit correspondre au titulaire du compte bancaire, sinon la validation échoue et reste en attente sans explication claire.
- Notez le statut de chacun et la date.

### ✅ Relevé le 2026-08-31 — c'est le profil **payeur**, le compte marchand n'existe pas

Écran ouvert : `payments.google.com/gp/w/home/settings` (Google centre de paiement,
onglets *Activité / Modes de paiement / Abonnements et services / Adresses /
Paramètres*). Statut des trois volets attendus, **relevé le 2026-08-31** :

| Volet | Statut |
| --- | --- |
| Identité du bénéficiaire | ✅ **nom validé le 2026-06-02**, **adresse validée le 2026-06-02** (badges « Validé le » de Google) |
| Informations fiscales | ❌ **section absente de l'écran** — pas « en attente » : elle n'existe pas |
| Coordonnées bancaires | ❌ **section absente de l'écran** — idem |

⚠️ **Ce tableau décrit l'état du matin du 2026-08-31, avant création du compte marchand.
Pour l'état courant, voir la section « Compte marchand créé » plus bas.**

Les sections présentes sont *Profil de paiement pour Google Pay*, *Paramètres généraux
(Google Pay)*, *Profil de paiement*, *Utilisateurs du profil de paiement* (1
utilisateur, contact principal), *Paramètres de confidentialité* et *État du profil de
paiement* — dont la seule action offerte est **« Clôturer le profil de paiement »**.
Aucune section de virement, de fiscalité ni de rapport de revenus.

**Conclusion : c'est bien le profil payeur (objet 1), pas le compte marchand (objet 2).**
La distinction posée ci-dessus est confirmée, et l'objet bloquant pour `task-238` reste
entièrement à créer.

#### Le piège de l'onglet *Modes de paiement* — moyen de paiement ≠ moyen d'encaissement

Objection soulevée par l'owner le 2026-08-31 et tranchée ici, car elle se reposera :
l'onglet **Modes de paiement** du centre de paiement **n'est pas vide** — une carte
bancaire y est enregistrée (aucun détail de carte n'est consigné ici, repo public). Cela
ne contredit pas ce qui précède, cela l'appuie :

- Une carte est un instrument **sortant**. C'est elle qui a réglé les $25. Le libellé de
  l'écran le dit : « Modes de paiement dans Google **Wallet** ».
- Google ne verse **jamais** de revenus Play sur une carte. Les paiements marchands
  partent en **virement vers un compte bancaire** (IBAN/BIC) et exigent en plus des
  **formulaires fiscaux**. Ces deux objets sont absents de tous les écrans relevés.

Donc la présence d'une carte est une preuve *de plus* que ce profil est le payeur.
Ne pas la relire comme « les coordonnées bancaires sont déjà déposées ».

Autres faits relevés sur le même écran, à ne pas reperdre :

- **`TYPE DE COMPTE : Particulier`** — troisième confirmation indépendante du compte
  personnel (après le relevé du 2026-08-19 et la reconfirmation owner du 2026-08-31).
  Voir l'étape 0 : fait établi, ne plus le redemander.
- Un **crayon d'édition existe** à côté de `TYPE DE COMPTE` dans le centre de paiement,
  alors que le lien *Modifier le type de compte* de la Play Console est grisé (étape 3).
  **Ne pas y toucher** : ce sont deux objets distincts, le type du profil de paiement ne
  commande pas le type du compte développeur Play, et Google ne permet pas de convertir
  un profil de paiement après création — la manip ne peut donc que casser le profil qui
  a réglé les $25, sans rien débloquer.
- `PAYS/RÉGION` renseigné (France), `LANGUE DES DOCUMENTS` renseignée.
- **Le champ `N° DE TÉLÉPHONE` du profil de paiement est vide**, alors que le numéro de
  contact de la Play Console a bien été validé le 2026-08-31 (étape 0 bis). Deux champs
  distincts. Non bloquant à ce stade, mais à renseigner si la création du compte
  marchand le réclame.

### ✅ Ordonnancement tranché par la doc Google le 2026-08-31 : **créable dès maintenant, aucune app requise**

Une inférence fausse a été posée puis retirée le même jour. De l'absence de fiscal et de
bancaire, et de l'absence d'entrée *Paiements* dans le menu, on avait déduit que le compte
marchand ne se créait qu'après la création de l'app. **La doc Google dit l'inverse.**

Source : *Play Console Help — « Create a payments profile »*
(`support.google.com/googleplay/android-developer/answer/7161426`), consultée le
2026-08-31. Elle ne conditionne la création du profil à **aucune** existence d'app : c'est
décrit uniquement comme une tâche de compte, dans les réglages.

**Chemin documenté — c'est sous *Paramètres*, pas sous *Paiements* :**

> Play Console → **Paramètres** → **Profil de paiement** → *Créer un profil de paiement*,
> puis, dans le menu déroulant sous « Profil de paiement », de nouveau
> *Créer un profil de paiement*.

C'est ce qui explique que l'entrée soit restée introuvable : on cherchait une entrée de
menu *Paiements* de premier niveau, qui n'existe pas. L'entrée **Paramètres**, elle, est
bien présente dans le menu latéral de ce compte.

Ce que le formulaire demande d'après la doc : nom légal et adresse légale (**les boîtes
postales sont refusées** — « We don't allow you to use a PO box address »), contact
principal, informations commerciales publiques (site web, catégorie de produit, e-mail de
support client, nom affiché sur les relevés bancaires des acheteurs). **Le pays est
verrouillé après soumission** ; le reste des informations publiques reste modifiable.

Deux précisions de la doc qui comptent pour la suite :

- Le **compte bancaire devra être enregistré dans le même pays que le profil de
  paiement**. Le pays étant définitif, ne pas se tromper à la soumission.
- Le profil se **lie automatiquement à la Play Console** après création. Si un profil de
  paiement ou un compte marchand existait déjà, il est déjà lié.

⚠️ Ce que la doc consultée **ne** détaille **pas** : les sous-étapes de dépôt des
**coordonnées bancaires** et des **informations fiscales**. Elles n'apparaissent dans aucun
des index d'aide parcourus le 2026-08-31 (`topic/16285`, `topic/9857752`) — elles
surviennent à l'intérieur du parcours lui-même. À relever sur pièce au moment de le faire,
avec le délai que Google annonce, plutôt qu'à deviner ici.

**Conséquence pratique : c'est le premier poste à lancer, et il est lançable aujourd'hui,
en parallèle du build.** Il porte un délai de traitement Google et ne dépend de rien.

#### ✅ Écran ouvert le 2026-08-31 : c'est un **sélecteur**, pas un formulaire de création

Chemin confirmé sur pièce : Play Console → **Paramètres** → **Profil de paiement**
(`play.google.com/console/u/0/developers/<id>/paymentssettings`). La doc décrivait un
parcours de création ; la réalité de ce compte est différente et plus simple.

L'écran affiche « Choisissez le profil de paiement qui sera associé à ce compte ou à cette
transaction. Les profils de paiement sont partagés et utilisés pour tous les produits
Google », puis **trois boutons radio** — et **aucun n'est coché** :

1. Un profil **`Particulier`** de portée large : « pour YouTube, Cloud, Play et Google
   Pay ». C'est celui que le centre de paiement rattache à Google Pay.
2. Un profil **`Particulier`** de portée étroite : « **pour Play** ». C'est celui dont le
   nom et l'adresse portent la pastille **« Validé le 2 juin 2026 »**, soit le lendemain
   du paiement des $25 le 2026-06-01.
3. *Créer un profil de paiement*.

**Ce qu'il faut faire : cocher le profil dédié à Play (option 2). Surtout ne pas cliquer
« Créer un profil de paiement »** — cela produirait un troisième profil en doublon, alors
que l'identité requise est déjà validée sur un profil existant.

Motifs du choix, à conserver pour ne pas le rejouer : c'est le profil porteur de
l'identité que Google a validée pour l'inscription développeur, et isoler les revenus Play
des dépenses YouTube/Cloud simplifie les formulaires fiscaux comme la comptabilité.

⚠️ **Deux lectures possibles de l'absence de coche, et l'action est la même dans les
deux.** Soit aucun profil n'est encore rattaché au compte développeur — auquel cas ce clic
est l'action manquante ; soit un profil l'est déjà et cet écran ne pré-sélectionne
simplement pas — auquel cas cocher celui qui correspond est un no-op. Dans les deux cas,
cocher **celui dont l'identité est validée** est le geste sûr. Ce rattachement étant
difficile à défaire une fois des transactions passées, vérifier l'ID avant de valider.

Reste inconnu après ce clic : où se déposent les **coordonnées bancaires** et les
**informations fiscales**, et avec quel délai. À relever sur pièce.

#### ⚠️ Piège d'écran du centre de paiement — la carte du haut n'est pas le profil consulté

Constaté le 2026-08-31, après une confusion : la carte **« Profil de paiement pour Google
Pay »**, en haut de `payments.google.com/gp/w/home/settings`, est une **préférence globale
Google Pay**. Elle affiche **le même ID quel que soit le profil ouvert**. Le profil
réellement consulté est celui du champ `ID DU PROFIL DE PAIEMENT`, dans la section
« Profil de paiement » **plus bas**. Lire l'ID en haut conduit à croire que les deux
profils n'en font qu'un.

Départage des deux profils, relevé sur deux captures du même écran :

| | Profil de portée large | Profil dédié Play |
| --- | --- | --- |
| Libellé dans le sélecteur | « pour YouTube, Cloud, Play et Google Pay » | « **pour Play** » |
| `TYPE DE COMPTE` | `Particulier` | `Particulier` |
| `NOM` | forme courte, **aucune pastille de validation** | forme légale complète, **« Validé le 2 juin 2026 »** |
| `ADRESSE` | — | **« Validé le 2 juin 2026 »** |

**Le profil dédié Play est donc bien celui à cocher**, et un troisième indice le confirme :
*Compte de développeur → Détails du compte → À propos de vous* affiche comme nom légal la
**forme complète** — celle du profil dédié Play — en précisant qu'elle est « issue du
profil de paiement Google ». La Play Console est donc **déjà adossée à ce profil-là** ; le
cocher confirme un état existant plutôt qu'il ne le change.

#### ✅ Le formulaire *Profil public de marchand* — valeurs arrêtées le 2026-08-31

Après sélection du profil, la page *Paramètres → Profil de paiement* déroule un formulaire
**Profil public de marchand → Informations publiques de l'entreprise**. La case *Utiliser
le nom, les coordonnées et l'adresse comme informations juridiques de l'entreprise* est
cochée par défaut : les informations juridiques restent donc celles de la **personne
physique**. Quatre champs obligatoires, un facultatif. Valeurs retenues :

| Champ | Valeur | Motif |
| --- | --- | --- |
| Nom de l'entreprise | `Second Brain Labs` | Identique au *Nom du développeur* déjà enregistré en Play Console. Une divergence entre l'éditeur affiché sur la fiche et le nom porté par le reçu génère des litiges. |
| Site Web (facultatif) | ⛔ **laisser vide** | Le champ est facultatif. **Ne PAS y mettre `secondbrainlabs.com` : il appartient à un tiers**, cf. l'avertissement sous ce tableau. Renseigner un site étranger dans un champ que Google affiche aux acheteurs, c'est les envoyer chez quelqu'un d'autre. À remplir quand un domaine sera acheté ; c'est effectivement le levier de l'étape 1 ter (« l'ajout d'un site nous aide à valider votre compte »), donc à reprendre à ce moment-là. |
| Produits ou services vendus | menu déroulant — entrée la plus proche de *logiciels / contenus ou services numériques* | Options non relevées ; à consigner au moment du choix. |
| E-mail du service client | ⛔ **pas `support@secondbrainlabs.com`** — utiliser une adresse que vous contrôlez réellement, quitte à créer un alias sur une boîte existante | **Champ public** : visible des acheteurs sur leurs reçus. Ne jamais y mettre l'e-mail racine du compte, **ni une adresse sur un domaine que vous ne possédez pas** : le courrier des acheteurs partirait chez son propriétaire. |
| Nom sur les relevés de carte | `Second Brain Labs` | 17 caractères, sous la limite usuelle de 22. Un libellé reconnaissable réduit les contestations — recommandation explicite de la doc Google. |

🛑 **L'owner ne possède aucun domaine (énoncé le 2026-09-03). `secondbrainlabs.com`
appartient à un tiers.** Les deux champs marqués ⛔ ci-dessus sont **publics** —
Google les affiche aux acheteurs sur leurs reçus — et les remplir avec ce domaine
enverrait vos clients et leur courrier chez son propriétaire.

**Ce runbook a affirmé le contraire, et il faut comprendre pourquoi.** Le relevé DNS
du 2026-08-31 disait : « `secondbrainlabs.com` résout **et** porte des
enregistrements **MX Google Workspace** fonctionnels », et en concluait que le
domaine était utilisable, l'alias `support@` restant « à créer côté Workspace ».
Les deux observations sont vraies ; l'inférence est fausse. **Résoudre en DNS et
recevoir du courrier prouve que quelqu'un exploite le domaine, pas que c'est
vous** — et les MX Workspace étaient précisément ceux de son propriétaire. Le
signal contraire était sous les yeux dans la même ligne : le `301` vers `sbl.so`,
un domaine étranger, qui refuse aujourd'hui la connexion. La seule preuve de
propriété d'un domaine est la facture du registrar. Cf. `docs/V1_LAUNCH_PLAN.md`,
Phase 10 §0bis.

⚠️ **Anomalie mise au jour par ce champ, à traiter hors de cette tâche.** La politique de
confidentialité désigne `privacy@mediasummarizer.com` comme adresse d'accès et de
portabilité des données, sous un mois. Or **`mediasummarizer.com` est en `NXDOMAIN`
complet** (revérifié le 2026-09-03) : le domaine n'existe pas, l'adresse est morte. Un
canal RGPD injoignable dans un document légal. `task-43` est marquée `Done` mais son
livrable porte ce défaut. **Ne pas la rebasculer sur `secondbrainlabs.com`** comme
la version précédente de cette note le prescrivait — ce serait remplacer une
adresse morte par l'adresse d'un tiers. Attendre l'achat d'un domaine ; le
document n'est de toute façon pas hébergé, donc pas publié.

**Note à l'owner, hors périmètre Google** : la case juridique cochée fait vendre en
personne physique. Le formulaire fiscal qui suit le confirmera, et la vente d'abonnements
en France suppose une immatriculation (micro-entreprise). Rien à faire sur cet écran.

#### ✅✅ Compte marchand **créé** le 2026-08-31 — IBAN déposé, vérification par micro-dépôt en cours

Le formulaire *Profil public de marchand* a été soumis, et la page *Paramètres → Profil de
paiement* affiche désormais l'écran de l'**encaisseur** : blocs *Vos revenus* (0,00 €,
**seuil de versement 1,00 €**, paiement mensuel), *Transactions* (aucune), *Mode de
paiement* et *Paramètres* — ce dernier nommant le profil `Google Play Apps`, 1 utilisateur.
Le bloc *Mode de paiement* est explicite : « Ajoutez un mode de paiement **pour recevoir
vos revenus** ». La distinction payeur/encaisseur poursuivie toute la journée est donc
matérialisée à l'écran, et les deux objets coexistent bien.

**L'IBAN a été déposé le 2026-08-31.** Google annonce à l'owner une **vérification par
micro-dépôt** : un montant sera viré sur le compte bancaire « dans les jours à venir », et
**l'owner devra le saisir dans la console** pour valider le compte de versement.

État des trois volets au 2026-08-31 en fin de journée :

| Volet | Statut |
| --- | --- |
| Identité du bénéficiaire | ✅ validée le 2026-06-02 |
| Coordonnées bancaires | ✅✅ **complet le 2026-09-01** : micro-dépôt reçu, montant saisi, compte validé **et passé en `Principal`** |
| Informations fiscales | ✅ **W-8BEN approuvé le 2026-09-01**, 0 % sur les royalties, valide jusqu'au 31 décembre 2029. Taïwan laissé vide (non applicable). Détail plus bas |

**Ce que l'owner doit faire, et c'est à échéance :**

1. Surveiller le compte bancaire les prochains jours, relever le montant crédité par Google.
2. Le saisir dans la console pour valider le mode de versement.
3. **Relever au passage l'échéance et le nombre d'essais autorisés** qu'affiche l'écran de
   saisie : les vérifications par micro-dépôt sont en général bornées dans le temps et en
   nombre de tentatives. Ni l'un ni l'autre n'a été vérifié dans la doc — à lire sur pièce,
   pas à supposer.
4. Consigner la date de validation effective ici et en Phase 2.2.

##### ✅ Procédure du micro-dépôt, établie sur la doc Google le 2026-09-01

Source : *Centre de paiement*, `paymentscenter/answer/7161378`, lue le 2026-09-01.

- Mécanisme : « Google procède à un virement d'un faible montant sur votre compte
  bancaire ».
- **Délai : « Le traitement de ce virement par votre banque peut prendre jusqu'à trois jours
  ouvrés. »** C'est le chiffre qui manquait au calendrier de cette porte.
- Montant : « **inférieur à 1 USD** et sera converti dans la devise locale » — donc quelques
  centimes d'euro, pas un montant repérable au premier coup d'œil sur un relevé.
- Libellé sur le relevé : « **Virement Google [nom figurant sur votre relevé de carte de
  paiement]** » — c'est le descripteur choisi au moment du profil public de marchand, limité
  à 14 caractères.
- **Chemin de saisie du montant** (payments.google.com, pas la Play Console) :
  *Abonnements et services* → « Services marchands » → **Informations sur le compte** →
  section « Mode de paiement » → **Gérer les modes de paiement** → repérer le compte →
  **Corriger** → « sélectionnez dans le menu déroulant le montant que Google a viré sur
  votre compte » → **Valider**.
- Étape que tout le monde oublie : après validation, **définir le compte comme *Principal***
  (il est sur *Aucun* par défaut). **Un compte validé mais non principal ne reçoit rien.**
  Chemin relu sur `answer/7161378` le 2026-09-01, côté **Play Console** et non
  payments.google.com : icône **Paramètres** → **Paramètres de paiement** → rubrique **« Mode
  de paiement »** → **Sélectionner un mode de paiement** (libellé « Gérer les modes de
  paiement » sur l'UI actuelle) → repérer le compte → **flèche vers le bas** « pour changer
  son statut et le définir sur **Principal** au lieu de **Aucun** ».
- Le montant est **à choisir dans une liste déroulante**, pas à saisir librement. Le point 3
  ci-dessus reste ouvert : la doc **ne dit rien** du nombre de tentatives ni d'une échéance —
  à relever sur pièce.

Deux cas de figure documentés qui ne s'appliquent pas ici : la validation instantanée
(réservée aux marchands américains payés par TEF) et les pays payés par virement
électronique, où « aucun virement test ne sera envoyé ».

Rien n'oblige à attendre cette validation pour avancer : la création de l'app Play et la
checklist de configuration ne dépendent pas du mode de versement.

#### ✅ Informations fiscales : la section existe, et voici son chemin (doc lue le 2026-09-01)

La question « est-ce que ça existe vraiment » est tranchée : **oui**. Sources :
`googleplay/android-developer/answer/7163598` (saisie), `answer/138000` (TVA), et
`answer/7161426` qui les référence toutes deux depuis le parcours *Paramètres de paiement*.

**Chemin selon la doc :** Play Console → icône **Paramètres** → **Paramètres de paiement** →
dans la section « Profil de paiement », chercher « **Informations fiscales : [votre pays]** »
→ **Modifier** → **Ajouter des infos fiscales** → répondre aux questions → **Envoyer** →
**Enregistrer**.

> ⚠️ **Chemin réel, corrigé sur screenshot owner le 2026-09-01.** La doc décrit une
> génération d'interface antérieure. La page `/paymentssettings` de la Play Console
> n'énumère **pas** « Informations fiscales : [pays] » à plat : elle présente quatre cartes
> — *Vos revenus*, *Transactions*, *Mode de paiement*, *Paramètres*. Le volet fiscal est
> derrière la carte *Paramètres* → **Gérer les paramètres**, avec le profil public de
> marchand et les contacts. C'est aussi pourquoi la section a paru absente le 2026-08-31 :
> elle n'est pas au premier niveau, et le compte marchand n'existait pas encore.
>
> Règle générale que ce cas illustre pour la troisième fois sur cette tâche : quand la doc
> Google et l'écran divergent, **l'écran fait foi** — la doc Play/paiements est régulièrement
> en retard d'une refonte d'UI. Ne jamais réécrire un chemin d'après la doc seule sans
> l'avoir vu confirmé sur un screenshot.

**Ce qui est déjà écarté pour un particulier résidant en France :**

- **Pas de TVA à gérer.** Avec le système de facturation Google Play, « Google est chargé de
  déterminer, facturer et reverser la TVA sur tous les achats de services et contenus
  numériques » des clients de l'UE, et « Vous n'avez pas à calculer ni à envoyer la TVA
  séparément ». Ce régime « s'applique même si vous n'êtes pas établi dans l'Union
  européenne ».
- **Pas de numéro de TVA à fournir.** La doc n'en exige un que pour l'Arabie saoudite,
  Taïwan, la Thaïlande, le Cambodge et quelques autres — jamais pour l'UE.
- Conséquence sur les prix : la France fait partie des pays où « toutes les taxes, y compris
  la TVA, doivent être incluses dans le prix » — les prix des trois abonnements de
  `task-238` se saisissent donc **TTC**.

##### ✅✅ Centre fiscal ouvert le 2026-09-01 — deux juridictions, et **aucune n'est bloquante**

Écran relevé : `/paymentssettings?place=TAX_CENTER`, fil d'Ariane « Paiements > Paramètres >
Gérer les informations fiscales ». Il contient **exactement deux cartes de juridiction**,
toutes deux sur « Aucune information fiscale enregistrée » avec un bouton « Ajouter des
infos fiscales » :

| Juridiction | Statut à l'écran | Verdict |
| --- | --- | --- |
| Taïwan | aucune information enregistrée | **non applicable** — voir ci-dessous |
| États-Unis | aucune information enregistrée | **à remplir** (W-8BEN) |

Deux constats qui comptent plus que les cartes elles-mêmes :

- **Aucune carte France, aucune carte UE.** Confirmation par l'écran de la conclusion tirée
  de la doc juste au-dessus : il n'y a pas de volet fiscal européen à remplir, Google porte
  la TVA.
- **Ni l'une ni l'autre n'est en erreur ni en état bloquant** : pas de bandeau rouge, pas de
  « action requise » sur ces cartes. **Correction d'une affirmation posée plus tôt le même
  jour** (et propagée dans `task-238`) : le volet fiscal **ne bloque pas** la création des
  abonnements Play. Le seul bandeau bloquant du compte marchand reste celui du compte
  bancaire — « Validez votre compte … pour pouvoir payer ou être payé ».

**Taïwan — à ignorer.** `answer/138000` (lu le 2026-09-01) porte sur le **numéro de TVA
taïwanais**, demandé aux développeurs **établis à Taïwan**, et non à ceux qui y vendent :
« Votre statut fiscal détermine les taxes qui vous sont facturées à Taïwan ». La sanction
documentée de l'abstention — « Si vous ne fournissez pas votre numéro de TVA taïwanais,
Google peut appliquer une TVA de 5 % sur les frais de service » — vise donc le même public.
Un particulier résidant en France n'a pas de numéro de TVA taïwanais à donner. À vérifier
d'un coup d'œil en ouvrant la carte : si le premier champ demande ce numéro, refermer.

**États-Unis — à remplir, formulaire W-8BEN.** `answer/7161649` (lu le 2026-09-01) est
explicite sur le public : « L'IRS demande aux marchands internationaux qui vendent aux
États-Unis de fournir le certificat de statut d'étranger », et « vous devez envoyer le
certificat de statut d'étranger (formulaire W-8BEN) **depuis votre profil de paiement** ».
Sa finalité est énoncée : « pour être exemptés de l'obligation de déclaration fiscale dans
ce pays ». C'est donc une **exonération**, pas une imposition — le remplir est ce qui évite
le traitement américain, l'omettre est ce qui l'attire.

**Aucun taux de retenue n'est documenté côté Google** (`7163598`, `7161649`, `138000`,
`7161426`) : ni 24 %, ni 30 %, ni taux conventionnel. Le 1099-K qu'elles citent (seuils
« plus de 20 000 USD en ventes brutes » **et** « plus de 200 opérations de paiement par an »)
est une déclaration, pas un prélèvement.

##### ✅ Le taux existe, mais il est chez l'IRS — pas chez Google (lu le 2026-09-01)

Source : *Instructions for Form W-8BEN* (Rev. 10-2021), `irs.gov/pub/irs-pdf/iw8ben.pdf`,
page 3. **Correction d'une phrase écrite plus haut le même jour** (« aucun taux de retenue à
la source n'est documenté ») : c'était vrai des pages Google, pas de la source primaire.

- **Taux en cas d'absence de formulaire :** « If you do not provide this form, the
  withholding agent may have to withhold at the **30% rate** (under chapters 3 and 4),
  backup withholding rate, or the rate applicable under section 1446. »
- **Assiette :** revenus de source américaine uniquement — « an amount from **sources within
  the United States** that is fixed or determinable annual or periodical (FDAP) income ».
  Donc les ventes Play réalisées aux États-Unis, pas le chiffre d'affaires mondial.
- **Le formulaire ne part pas à l'IRS.** « **Do not send Form W-8BEN to the IRS.** Instead,
  give it to the person who is requesting it from you. » La page Google FR (`7163598`) écrit
  « Vous devez envoyer le certificat de statut d'étranger (formulaire W-8BEN) **à l'IRS** » —
  c'est trompeur : l'agent de retenue, ici, c'est **Google**. La saisie dans le centre de
  paiement *est* la transmission.
- **Obligation :** « **Submit Form W-8 BEN when requested by the withholding agent or
  payer** » (`irs.gov/forms-pubs/about-form-w-8-ben`) — indépendamment de toute demande de
  taux réduit. Google le demande. Donc c'est dû.
- **Deux champs anticipés, confirmés sur les instructions** (pages 6-7) : la **ligne 6a**
  « foreign tax identifying number (**FTIN**) issued to you by your jurisdiction of tax
  residence » — le numéro fiscal français ; et la **Partie II, ligne 9**, « If you are
  claiming treaty benefits as a resident of a foreign country with which the United States
  has an income tax treaty ». La ligne 5 (SSN/ITIN américain) n'a pas à être remplie : « If
  you are claiming treaty benefits, you are generally required to provide an ITIN **if you do
  not provide** a tax identifying number issued to you by your jurisdiction of tax residence
  on line 6 » — le FTIN dispense de l'ITIN.

##### ✅ Le formulaire W-8BEN de Play, champ par champ (écran owner + doc, 2026-09-01)

Le parcours est un assistant en 4 étapes sous *Profil de paiement* → **Informations fiscales**.
Ce qui se remplit, et pourquoi :

| Étape / champ | Valeur | Justification |
| --- | --- | --- |
| 1 · Nom du bénéficiaire effectif | nom civil de la personne physique | `7163598` : « Particuliers et entreprises individuelles : indiquez vos nom et prénom officiels » |
| 1 · Nom commercial / entité transparente | **vide** | facultatif, aucune entité |
| 1 · Pays de citoyenneté | France | — |
| 1 · **Numéro d'identification fiscale étranger** | **numéro fiscal français (13 chiffres)** | c'est la ligne **6a** du W-8BEN, « foreign tax identifying number (FTIN) issued to you by your jurisdiction of tax residence » |
| 1 · ITIN / SSN américain | **vide** | ligne 5 ; le FTIN en dispense (cf. citation plus haut). Aucun identifiant américain à demander |
| 2 · Adresse | adresse de résidence réelle | — |
| 2 · « boîte postale ou aux bons soins d'un autre destinataire ? » | **Non** | l'écran était sur *Oui* alors que l'adresse est un domicile réel. Instructions W-8BEN ligne 3 : « Do not show the address of a financial institution, **a post office box**, or an address used solely for mailing purposes » |
| 3 · Taux de retenue réduit | **Oui**, résident de **France** | l'écran affiche lui-même « France et les États-Unis sont unis par une convention fiscale » |
| 3 · Conditions et tarifs spéciaux | **cocher « Autres royalties liées aux droits d'auteur » uniquement** | voir ci-dessous |

**Le type de revenu Play, tranché par la doc Google.** L'écran propose trois cases et n'explique
pas laquelle vise Play. `youtube/answer/10391362` (même outil fiscal, lu le 2026-09-01) le dit :
« Autres royalties liées aux droits d'auteur (Programme Partenaire YouTube **et Google Play**,
par exemple) » et, séparément, « Services (comme Google AdSense) ». Donc **royalties de droits
d'auteur**, pas « revenus de services ou d'autres entreprises » (réservé à AdSense), pas
cinéma/TV. Le libellé de la case le corrobore en citant *Play Pass*.

Ne rien cocher tout en répondant « Oui » à la question du taux réduit ne réclame rien : la
retenue de 30 % reste applicable. La même page donne les taux par défaut de l'outil en
l'absence d'informations fiscales — « 30 % des revenus américains » pour un compte
d'entreprise hors États-Unis, et « **24 % du total des revenus générés à l'échelle
mondiale** » pour un **compte individuel**, ce qui est le cas ici. C'est l'argument décisif :
ne pas remplir cet écran expose l'assiette mondiale, pas seulement l'assiette américaine.

**Taux conventionnel affiché et vérifié le 2026-09-01 : Article 12 §1, `0 %`.** L'écran
propose un couple (article, paragraphe) + taux ; il a été recoupé sur les textes primaires,
et il est exact — mais pas pour la raison qu'on croirait.

- Le **texte de 1994** (IRS, `irs-trty/france.pdf`, Article 12) ne donne pas 0 % au §1 : son
  §2 plafonne la retenue américaine à « 5 percent of the gross amount of the royalties » et
  l'exonération est au **§3**.
- Le **protocole de 2009** (Trésor, `Treaty-France-Pr2-1-13-2009.pdf`, Article III) a réécrit
  l'article : « Paragraph 1 of Article 12 (Royalties) … shall be deleted and replaced by the
  following: “Royalties arising in a Contracting State and beneficially owned by a resident of
  the other Contracting State **shall be taxable only in that other State**.” », et
  « Paragraphs 2, 3, 4, and 5 … shall be **deleted** ». Le plafond de 5 % a disparu et
  l'exonération est passée **dans le §1**. D'où le couple affiché par Google.
- La nouvelle définition des royalties (nouveau §2) couvre nommément « **any software** » :
  les revenus d'une application y entrent sans discussion.
- Le nouveau **§3** est la seule exception, et c'est le texte exact de la case à cocher de
  l'écran : l'exonération tombe si le bénéficiaire « carries on business in the other
  Contracting State … through a **permanent establishment** situated therein ». Aucun
  établissement stable aux États-Unis ici → case cochée à juste titre.

**Étape 4 · « Activités et services effectués aux États-Unis » → `Non`, + case de
certification à cocher.** Le message qui apparaît sous *Non* n'est pas un avertissement mais
la certification qui rend la réponse effective : « les prestations fournies à Google ou ses
sociétés affiliées s'effectueront exclusivement en dehors des États-Unis, et … toute
main-d'œuvre ou tout capital (installations et autres outils compris) … seront situés
physiquement en dehors des États-Unis ». Elle est vraie ici : owner en France, aucun salarié,
et **toute l'infra AWS est sur `eu-west-3` (Paris)** — vérifié dans
`infrastructure/terraform/envs/{dev,staging,prod}/main.tf` et
`.github/workflows/deploy-lambda.yml`.

Critère confirmé par la doc (`youtube/answer/10390801`) : « Les "activités aux États-Unis"
désignent la prestation de services aux États-Unis », exemples donnés « Employer des
personnes ou posséder du matériel aux États-Unis qui contribuent à générer des revenus ».

Coût d'un « Oui » par erreur : la même page indique que le **W-8ECI** est « utilisé par les
personnes déclarant avoir perçu des revenus effectivement liés à des opérations commerciales
américaines », avec « un numéro d'identification fiscale américain **obligatoire** ». Un Oui
fait donc basculer du W-8BEN au W-8ECI, exige un ITIN inexistant et fait tomber le 0 %.

> ⚠️ **Contrainte durable créée par cette certification.** Elle est rédigée au futur
> (« s'effectueront », « seront situés »). Déplacer le backend vers une région AWS
> **américaine** invaliderait la déclaration et obligerait à refaire ce formulaire. Tant que
> ce W-8BEN est en vigueur, `eu-west-3` (ou toute région hors États-Unis) est un choix
> contraint, pas un détail d'implémentation. À rappeler dans toute tâche qui toucherait à la
> région AWS.

Leçon de méthode, la même que pour les chemins d'UI : le texte de traité publié par l'IRS est
la version **d'origine**, les protocoles vivent ailleurs (Trésor). Vérifier un article de
convention sans lire les protocoles conduit à conclure « 5 % » là où la réponse est 0 %.

##### ✅✅ Résultat : W-8BEN **Approuvé** le 2026-09-01 — porte fiscale franchie

État relevé à l'écran, carte *États-Unis* :

| Élément | Valeur |
| --- | --- |
| Formulaire | **W-8BEN**, état **`Approuvé`** (approbation immédiate, sans instruction manuelle) |
| Date d'envoi | 1er septembre 2026 |
| **Expiration** | **31 décembre 2029** |
| Taux — *Autres droits d'auteur* | **0 %**, `Déclaré` |
| Taux — *Cinéma et télévision* | **0 %**, `Déclaré` |
| Taux — *Par défaut (Services)* | **30 %** |
| Documents supplémentaires | **Attestation d'absence d'activité aux États-Unis** |
| Déclaration fiscale | transmission dématérialisée, aucun document émis |
| Taïwan | laissé vide, conforme |

Trois points qui pourraient inquiéter et qui sont normaux :

- **La date d'expiration n'est pas arbitraire** et confirme que le formulaire a été traité
  correctement. Instructions W-8BEN, page 3 : « a Form W-8BEN will remain in effect … for a
  period starting on the date the form is signed and ending on the **last day of the third
  succeeding calendar year** ». Signé le 2026-09-01 → 31 décembre 2029. À renouveler avant
  cette date.
- **Le 0 % sur *Cinéma et télévision* apparaît alors que la case n'a pas été cochée**, et
  c'est exact : le protocole de 2009 a supprimé les §2 à §5, donc la distinction film/autres
  royalties et le plafond de 5 % n'existent plus. Toutes les royalties relèvent du §1 à 0 %.
- **Le « 30 % par défaut pour Services » est inerte.** Il ne vise que des revenus de type
  AdSense, non générés ici, et surtout : un revenu de services n'est de source américaine que
  si les services sont *rendus* aux États-Unis — ce que l'attestation d'absence d'activité
  écarte. Les revenus Play sont classés en royalties de droits d'auteur, donc à 0 %.

**Obligation de mise à jour à ne pas oublier** (instructions W-8BEN, page 3) : « If a change
in circumstances makes any information on the Form W-8BEN you have submitted incorrect, you
must notify the withholding agent … **within 30 days** of the change ». Combiné à la
certification de l'étape 4, cela fixe la contrainte encadrée ci-dessus : un déménagement de
l'infra vers une région AWS américaine ouvrirait un délai de 30 jours pour refaire ce
formulaire.

**Chemin réel du centre fiscal** (écran, pas doc) : Play Console → icône **Paramètres** →
**Paramètres de paiement** → carte **Paramètres** → **Gérer les paramètres** → **Gérer les
informations fiscales**, soit directement `/paymentssettings?place=TAX_CENTER`. Puis carte
**États-Unis** → **Ajouter des infos fiscales**. Le chemin de la doc (`7163598` : section
« Profil de paiement » → ligne « Informations fiscales : [pays] » → *Modifier*) décrit une UI
antérieure et ne correspond à rien à l'écran.

Le bloc « Déclaration fiscale » de la carte États-Unis (préférences d'envoi des documents,
avec la mention « Il se peut que vous ne soyez pas concerné par ces documents de déclaration
fiscale en raison de votre statut fiscal ou parce que vous n'avez pas reçu de paiements
éligibles ») est **informatif** : aucune action n'y est due.

**Deux avertissements de la doc, à ne pas prendre à la légère :**

- Sur l'identifiant fiscal d'un particulier : « **le nombre de tentatives pour fournir des
  informations correctes est limité** ». Ne pas remplir cet écran à l'aveugle.
- En cas d'identifiant fiscal manquant ou erroné, Google prévoit « la **retenue des
  paiements** et la **suspension du traitement des transactions** ».

**Alerte à traiter, relevée le 2026-08-31 :** le bandeau du centre de paiement affiche
**« 1 alerte critique »** lorsque le profil de portée large est ouvert (absente sur le
profil dédié Play). Non identifiée à ce stade. À ouvrir et consigner : une alerte critique
sur un profil de paiement peut bloquer les versements.

## Étape 3 — Décider de l'adresse développeur publique

> ⚠️ **Chemin corrigé le 2026-08-31 sur screenshot owner.** Deux endroits, tous
> deux sur Play Console → menu latéral **Compte de développeur** (pas « Paramètres ») :
> la carte **Coordonnées**, dont le sous-bloc *Informations affichées dans votre
> profil de développeur* liste ce qui est public, et la carte **Profil du
> développeur** (« Consultez les informations qui constituent votre profil public
> sur Google Play et configurez votre page publique de développeur »), qui est
> l'écran de décision.

**Constat au 2026-08-31, qui allège peut-être beaucoup cette étape.** Sur le
screenshot, le bloc *Informations affichées dans votre profil de développeur* ne
liste **qu'une adresse e-mail de développeur** (vérifiée). Aucune adresse physique
n'y figure — l'adresse postale n'apparaît que sous *À propos de vous* → « Nom légal
et adresse », qui est la donnée d'identité fournie à Google, pas une donnée publiée.

Il ne faut pas en conclure trop vite que l'adresse ne sera jamais publiée : la règle
Google lie l'affichage de l'adresse physique au fait de distribuer une app **payante
ou avec achats intégrés**, ce qui sera notre cas (`task-238`). Il est donc plausible
que l'exigence n'apparaisse qu'au moment où le profil marchand et les abonnements
existent, et que l'écran actuel ne la montre pas encore.

**Ce qui reste à faire ici est donc précis** : ouvrir la carte *Profil du
développeur* et lire ce que Google annonce comme effectivement public, puis noter si
l'adresse physique en fait partie ou non. Si elle n'en fait pas partie et qu'aucun
avertissement ne mentionne les apps payantes, cette étape se solde par « adresse non
publiée à ce stade — à revérifier après création du profil marchand » et les trois
options ci-dessous deviennent sans objet pour l'instant.

Trois options étaient prévues, à trancher **avant** de remplir la fiche Store — revenir en arrière après publication est plus lourd. **Il n'en reste que deux au 2026-08-31** :

1. L'accepter en l'état.
2. Utiliser une adresse de domiciliation ou une boîte postale, si elle est acceptée comme adresse de contact.
3. ~~Passer le compte en **organisation**~~ — **option indisponible, constatée le
   2026-08-31.** Sur *Détails du compte → À propos de vous*, le lien **« Modifier le
   type de compte » est grisé** (accompagné d'une infobulle « ? » dont le contenu
   reste à lire). Le basculement personnel → organisation n'est donc pas actionnable
   en l'état, et la démarche D-U-N-S (gratuite, jusqu'à 28 jours selon Dun &
   Bradstreet) n'a pas à être engagée. Si l'infobulle explique une condition
   levable, le noter — sinon cette branche est fermée et le calendrier s'en trouve
   allégé d'autant.

Consignez la décision et sa raison — pas l'adresse elle-même.

## Étape 4 — Vérifier l'exigence de closed testing (le seul poste à délai calendaire)

Play Console → **Tests** → **Test fermé**, et l'écran de demande d'*accès à la production*.

Google impose aux comptes développeur **personnels** créés après novembre 2023 un test fermé d'environ **12 testeurs pendant 14 jours continus** avant d'autoriser la demande d'accès à la production. Le compte est **personnel** (étape 0, réglé) et date du 2026-06-01 : les deux conditions sont réunies, **l'exigence s'applique**. Ce qui reste à établir ici n'est donc pas *si* elle s'applique, mais **avec quels paramètres**.

⚠️ Les seuils et le périmètre de cette règle ont changé plusieurs fois : **la Play Console est la seule source de vérité**, pas cette description ni le plan de lancement. Lisez ce qu'affiche l'écran d'accès à la production pour *votre* compte.

### ✅ Paramètres établis sur la doc Google le 2026-08-31

Source : *Play Console Help*, `answer/14151465`, consultée le 2026-08-31. S'applique aux
comptes **personnels créés après le 13 novembre 2023** — c'est le cas de ce compte
(2026-06-01). Chiffres cités mot pour mot :

- **12 testeurs minimum**, « opted in **continuously** for at least **14 days** ».
- La continuité est stricte : un testeur qui se désinscrit puis se réinscrit repart de
  zéro — « the 14 days must be consecutive to count toward the minimum requirement of 12
  continuous opted-in testers ». **Il faut donc 12 personnes qui ne touchent à rien
  pendant 14 jours**, pas 12 inscriptions cumulées.
- Prérequis : « **Complete app setup** before you can start a closed test ».
- Après les 14 jours, la demande d'accès à la production se fait depuis
  **Tableau de bord → *Demander l'accès à la production*** — trois parties (le test
  fermé, l'app, la préparation à la production). Attention : *Ignorer* ou quitter sans
  cliquer *Suivant*/*Appliquer* **perd la saisie**.
- Review de cette demande : « **usually takes seven days or less**, but can occasionally
  take longer ». Un refus possible si moins de 12 testeurs inscrits ou engagement jugé
  insuffisant → **il faut continuer à tester**, donc prévoir de la marge.
- L'approbation débloque la page **Production** et l'**Open testing**. Jusque-là,
  *Production* et *Pré-enregistrement* restent **désactivés**.

**Plancher calendaire : 14 jours + jusqu'à 7 jours de review = ~21 jours** à partir du
démarrage effectif du test fermé. C'est le chemin critique de la publication Android, et
rien ne le raccourcit.

Deux faits utiles trouvés au passage (`answer/9845334`, même date) :

- **Le test interne, lui, peut démarrer avant que la configuration de l'app soit
  terminée** : « start an internal test before completing app setup », y compris pour des
  apps « not fully configured ». C'est la voie rapide pour faire *exister* le nom de
  package dont `task-238` AC#2 a besoin, **sans attendre le test fermé**.
- « Once you upload an artifact, the **package name for that app is fixed and cannot be
  changed** » — confirme le diagnostic de `task-238` : c'est le premier artefact uploadé
  qui fixe `com.secondbrainlabs.core`, pas la création de l'app.
- Les listes de testeurs se créent sous **Tests et versions → Tests → Test fermé →
  *Gérer la piste* → onglet *Testeurs* → *Créer une liste d'e-mails***, par saisie
  séparée par virgules ou upload CSV (⚠️ un CSV **écrase** les adresses précédentes, et
  le format UTF-8 **avec BOM** est refusé). Alternative : un Google Group.

Reste à établir sur pièce : la **date de démarrage effective** du test fermé (AC#5).

Si l'exigence s'applique :

1. Notez le nombre exact de testeurs et la durée exigés, tels qu'affichés.
2. Elle ne s'achète pas et ne se parallélise pas : elle borne par le bas la date de publication Android. Comptez au minimum les 14 jours **plus** le délai de review de la demande d'accès.
3. ~~Elle nécessite un build Android installable et un groupe de testeurs — donc `task-163` (build Android unique) doit être faite avant de démarrer le compteur, et `task-258` doit avoir désarmé le workflow de build avant qu'un `EXPO_TOKEN` ne soit posé, sous peine de soumissions involontaires.~~ **Les deux préalables sont levés au 2026-09-02** : `task-163` et `task-258` sont `Done`, et `EXPO_TOKEN` a été posé le 2026-09-02 à `17:13:47Z` sans risque de soumission involontaire — `mobile-build-distribute.yml` ne se déclenche plus que sur un tag `mobile-v*` ou un `workflow_dispatch`, jamais sur un push de branche.
4. Reportez la date de démarrage réelle dans `docs/V1_LAUNCH_PLAN.md`, Phase 2.2 : c'est elle qui détermine la date de lancement Android la plus proche.
5. **Ne démarrez pas le compteur des 14 jours avant que `task-340` ait livré un binaire OTA-capable sur la piste interne** (décision owner du 2026-09-02, « OTA d'abord, closed testing ensuite »). Installer `expo-updates` est un changement natif : tout binaire installé avant n'a pas de runtime d'update, ne recevra jamais d'OTA, et doit être réinstallé une fois. Recruter 12 testeurs d'abord, c'est leur demander une réinstallation en plein milieu des 14 jours continus — exactement ce que Google mesure. L'ordre inverse coûte quelques jours de décalage sur l'horloge et rien d'autre.

   Ce n'est **pas** une dépendance de front-matter, volontairement : cette tâche porte aussi les étapes 1 à 3 (identité, profil de paiement, adresse publique), dont le profil de paiement est le poste le plus urgent du runbook et un bloquant dur pour `task-238`. Les mettre derrière une migration mobile serait retarder l'urgent pour l'ordonner. Seul le **démarrage du test fermé** attend `task-340`.

## Étape 5 — Consigner le résultat

Mettez à jour `docs/V1_LAUNCH_PLAN.md` en trois endroits déjà prévus pour ça : la **Phase 2, point 2** (les six portes détaillées), la ligne **Google Play Console** du tableau des comptes externes, et la ligne Google Play Console de la checklist des comptes en fin de document. Remplacez « à confirmer par l'owner » par le statut réel et sa date pour chacune des six portes.

**Règle de fond, née du 2026-08-31** : dès que l'owner communique un fait qui ne vit que dans une console tierce — type de compte, statut d'une vérification, valeur affichée dans un dashboard — il s'écrit **immédiatement** dans le plan de lancement, dans la même session. Un fait qui reste dans la conversation est un fait qu'on redemandera. C'est exactement ce qui est arrivé au type de compte : relevé le 2026-08-19, nulle part consigné, redemandé le 2026-08-31. Si une porte est encore en attente côté Google, écrivez-le avec la date de dépôt : un « en attente depuis le 2026-08-13 » est une information utile, un « en cours » sans date ne l'est pas — c'est précisément ce qui a rendu cette tâche nécessaire.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le type de compte (personnel ou organisation) est consigné dans `docs/V1_LAUNCH_PLAN.md`, Phase 2.2
- [x] #2 Le statut de la vérification d'identité du compte développeur est consigné avec sa date — vérifié, ou en attente depuis une date précise, ou action requise avec l'échéance affichée par Google
- [x] #3 Le statut du profil de paiement Google Payments est consigné pour ses trois volets séparément (identité du bénéficiaire, informations fiscales, coordonnées bancaires), chacun avec sa date
- [ ] #4 La décision sur l'adresse développeur publique est consignée avec sa raison (acceptée telle quelle, domiciliation, ou passage en compte organisation) — sans l'adresse elle-même
- [ ] #5 L'exigence de closed testing est tranchée sur la base de ce qu'affiche la Play Console : applicable ou non, et si applicable le nombre de testeurs et la durée exacts, plus la date de démarrage visée ou effective
- [x] #6 La ligne « Google Play Console » du tableau des comptes externes du plan ne contient plus « à confirmer par l'owner » mais l'état réel
- [x] #7 Aucune donnée personnelle n'a été écrite dans un fichier suivi : ni adresse, ni téléphone, ni pièce d'identité, ni D-U-N-S, ni coordonnées bancaires ou fiscales, ni email des testeurs — vérifiable par un `git diff` relu avant commit
- [x] #8 Si le closed testing s'applique, `task-238` porte une note indiquant que sa partie Play reste bloquée tant que le profil de paiement n'est pas vérifié
- [x] #9 La confirmation d'accès à un appareil Android physique (étape 0 bis) est faite via l'app mobile Play Console, et son statut est consigné avec sa date ; si elle reste ouverte, le bloquant est écrit tel quel dans `docs/V1_LAUNCH_PLAN.md` Phase 2.2 — sans identifier l'appareil ni son propriétaire
- [x] #10 Le statut de la validation du numéro de téléphone de contact est consigné avec sa date, sans le numéro lui-même
- [x] #11 Le statut de l'onglet « Noms des packages » de la page Validation des développeurs Android est consigné, avec la conclusion sur l'échéance du 30 septembre 2026 : soit l'enregistrement est automatique via Play App Signing et aucune action n'est due, soit un enregistrement manuel est requis et son périmètre est écrit dans `docs/V1_LAUNCH_PLAN.md`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Progrès — 2026-08-31 (owner, Play Console)

Deux portes franchies, les deux dernières de la carte « Terminer la configuration de votre compte de développeur ».

**Étape 0 bis — accès à un appareil Android physique : ✅ fait le 2026-08-31.** L'owner dispose désormais d'un appareil Android. App mobile Play Console installée dessus, connexion avec le compte développeur, confirmation validée. Ni l'appareil ni son propriétaire ne sont identifiés ici (repo public), conformément à l'AC#7.

**Validation du numéro de téléphone de contact : ✅ faite le 2026-08-31**, immédiatement après, dans la même carte — confirmant qu'elle était bien en aval de la porte appareil et non traitable isolément. Le numéro lui-même n'est pas consigné.

**Effet observable, et c'est le signal qui compte** : le bouton *Créer une application* de la Play Console est passé d'inactif (grisé) à actif. La carte de configuration du compte ne bloque donc plus la création d'app — ce qui débloque `task-238` AC#1 côté interface. Attention à ne pas surinterpréter : un bouton actif n'est pas un droit de publier. Les portes 3 à 6 (identité, profil de paiement, adresse publique, closed testing) restent à relever et conditionnent respectivement la survie du compte, la vente d'abonnements et la date de publication.

**Consigné dans `docs/V1_LAUNCH_PLAN.md`** : Phase 2.2 (les six portes sont désormais numérotées 1 à 6, les deux franchies en tête avec leur date), le tableau des comptes externes, et la checklist des comptes en fin de document. Les mentions « quatre vérifications » y sont remplacées par « six portes ».

**Reste ouvert sur cette tâche** : étapes 1 (identité), 2 (profil de paiement — le plus urgent, délai Google de plusieurs jours et bloquant dur pour `task-238`), 3 (adresse développeur publique) et 4 (paramètres du closed testing, seul poste à délai calendaire).

**Étape 0 fermée le 2026-08-31 (AC#1).** Le type de compte est **personnel** : relevé le 2026-08-19, reconfirmé par l'owner le 2026-08-31, et désormais écrit en tête du point 2 de la Phase 2 du plan de lancement. L'owner a signalé — à juste titre — qu'il l'avait déjà notifié une première fois : le fait vivait dans la conversation et dans une phrase parenthétique de cette description, jamais à l'endroit qui fait référence. L'étape 0 est réécrite pour porter la réponse plutôt que la question, et les étapes 3 et 4 n'expriment plus de conditionnel sur le type de compte : l'adresse publique **sera** personnelle, et le closed testing **s'applique**.

## Chemins de console périmés — corrigés le 2026-08-31 (screenshot owner)

Ce runbook a été écrit contre une organisation de la Play Console que Google a
remaniée depuis. **Trois des cinq chemins étaient faux**, tous pour la même raison :
ils passaient par « Paramètres → Détails du compte développeur », un écran qui
n'agrège plus ces informations. Corrigés dans la description :

- **Étape 0 (type de compte)** → menu latéral **Compte de développeur** → carte
  *À propos de vous*.
- **Étape 1 (vérification d'identité)** → **entrée de menu autonome « Validation des
  développeurs Android »**, en bas de la barre latérale sous *Aide*. Elle ne vit plus
  du tout dans la page compte, ce qui explique que l'owner n'ait trouvé aucune
  section de ce nom.
- **Étape 3 (adresse publique)** → menu latéral **Compte de développeur** → carte
  *Coordonnées* (sous-bloc *Informations affichées dans votre profil de
  développeur*) et carte *Profil du développeur* pour l'écran de décision.
- **Étape 1 (suite)** → la page *Validation des développeurs Android* a **deux
  onglets** et s'ouvre sur *Noms des packages*. L'identité est sous l'onglet
  **Identité** — l'owner est tombé sur le premier onglet et n'a rien trouvé qui
  ressemble à une vérification d'identité, ce qui est normal.
- **Étape 2 (profil de paiement)** → chemin réel : *Compte de développeur → Détails du
  compte → À propos de vous* → lien *Afficher le profil de paiement*, qui sort vers
  `payments.google.com/gp/w/home/settings`. Le menu latéral **n'a pas d'entrée
  « Paiements »** parce que le profil payeur vit hors de la console. L'hypothèse
  « le compte marchand n'existe pas encore et n'apparaîtra qu'après création de l'app »
  a été **confirmée sur pièce le 2026-08-31** (voir la section dédiée plus bas).

**Relevés au passage sur ce screenshot, sans action requise** — statuts seuls,
aucune donnée personnelle n'étant reprise ici conformément à l'AC#7 :

- *Type de compte* = **Personnel** (confirme l'étape 0 sur pièce).
- *Adresse e-mail de contact* et *Numéro de téléphone* : tous deux **vérifiés**
  (pastilles vertes) — le second confirme l'AC#10 visuellement.
- *Nom du développeur* = `Second Brain Labs`, déjà l'entité légale. Sans rapport avec
  le nom marketing de l'app que `task-186` doit trancher : ce sont deux champs
  distincts, et celui-ci n'a pas à changer.
- Le bloc *Informations affichées dans votre profil de développeur* ne liste **que
  l'e-mail développeur** — aucune adresse physique. Voir l'étape 3 réécrite : cela
  allège peut-être fortement la décision d'adresse publique, mais l'affichage de
  l'adresse étant lié aux apps à achats intégrés, la vérification doit être refaite
  après création du profil marchand.

## Septième porte découverte le 2026-08-31 — *Android developer verification* (AC#11)

Un second screenshot owner, de la page *Validation des développeurs Android*, a
révélé une exigence que ce runbook ignorait entièrement : l'**enregistrement des noms
de packages et des clés de signature**, programme annoncé par Google le 15 juillet
2026, avec un bandeau annonçant la suppression de Google Play de toute app non
enregistrée **au 30 septembre 2026**.

Instruction ajoutée en **étape 1 bis** de la description, avec le raisonnement
complet et les sources. Conclusion : **rien à faire, et surtout rien à enregistrer
manuellement.** Play App Signing produit l'enregistrement automatique (99 % des apps
selon Google), l'échéance de septembre 2026 est régionale (4 pays, magasins
participants) et non mondiale contrairement à ce que suggère le bandeau, `adb install`
est explicitement exempté, et l'onglet vide s'explique par l'absence d'app, pas par
une action due. Enregistrer le package avant que l'app Play existe risquerait de le
rattacher au keystore EAS au lieu de la clé Play App Signing — le désalignement de SHA
contre lequel `task-163` met déjà en garde pour la Phase 10.

Sources vérifiées le 2026-08-31 : `developer.android.com/developer-verification` et
`developer.android.com/developer-verification/guides/faq`. À noter pour plus tard : le
**format de fingerprint attendu** (SHA-1 ou SHA-256) n'est documenté sur aucune des
deux pages — il faudra le lire dans le formulaire si un enregistrement manuel devient
nécessaire.

**Ce qui borne réellement le calendrier Android reste le closed testing**, pas cette
échéance. Le rollout mondial de la vérification est annoncé pour 2027 ; il touchera
alors les builds EAS `distribution: internal`, à reconsidérer à ce moment-là.

## Porte identité fermée le 2026-08-31 (AC#2), et deux corrections en cascade

Deux screenshots owner de plus — onglet *Identité* de la validation des développeurs
Android, puis *Détails du compte → À propos de vous*.

**AC#2 : aucune action due, aucune échéance.** L'onglet *Identité* est purement
informatif : il reflète le nom légal et l'adresse « issus de votre compte de
développeur Play Console », avec un simple lien de renvoi. Pas de statut, pas
d'« Action requise », **pas de date limite**, aucun bouton. La crainte principale du
runbook — une échéance dépassée entraînant la suspension du compte, ce qui aurait rendu
toutes les autres étapes sans objet — est levée. À nuancer : l'écran n'affiche pas
« Vérifié » non plus ; il ne fait que refléter des données déjà là.

**Correction sur l'étape 2 — l'hypothèse « pas de profil de paiement » était fausse.**
La veille, l'absence d'entrée « Paiements » dans le menu latéral nous avait fait
supposer qu'aucun profil n'existait. *À propos de vous* dit le contraire : le nom légal
et l'adresse « sont issus du **profil de paiement Google** », avec un lien *Afficher le
profil de paiement* vers `payments.google.com`. Le profil existe ; il n'est simplement
pas dans le menu Play Console parce qu'il vit ailleurs. La distinction utile a été
ajoutée à l'étape 2 : le profil **payeur** (qui a réglé les $25) existe, le compte
**marchand** (qui encaisse, porte le fiscal et le bancaire, et conditionne
`task-238`) n'est prouvé par rien.

**Correction sur l'étape 3 — l'option « organisation » est fermée.** Le lien *Modifier
le type de compte* est **grisé**. Le basculement personnel → organisation n'est pas
actionnable, donc pas de D-U-N-S à lancer (jusqu'à 28 jours) : une branche de calendrier
disparaît, et la décision d'adresse publique se réduit à accepter ou domicilier.

**Étape 1 ter ajoutée — le site web.** Google affiche « l'ajout d'un site nous aide à
valider votre compte », et le champ est vide avec « Je n'ai pas de site Web » coché.
Non bloquant, mais gratuit à obtenir : `task-43` (Done) exige déjà des URLs publiques
pour la politique de confidentialité et les CGU de la fiche Play. Le domaine qui les
servira fera un site développeur valable — à renseigner quand il existera, pas avant.

**Relevé annexe, sans action** : le champ *Nom du développeur* vaut `Second Brain Labs`
et Google le décrit comme « le nom que les utilisateurs verront sur Google Play […] Il
peut être différent de votre nom ». C'est bien le nom public de l'éditeur, distinct du
nom marketing de l'app que `task-186` doit trancher. Aucun des deux n'a à être aligné
sur l'autre.

## Porte profil de paiement tranchée le 2026-08-31 (AC#3) — et une inversion d'ordre

Le centre de paiement (`payments.google.com/gp/w/home/settings`) a été ouvert. Résultat :
**profil payeur vérifié, compte marchand inexistant.** Identité du bénéficiaire validée
le 2026-06-02 (nom et adresse portent chacun un badge « Validé le » de Google), mais
**aucune section *Informations fiscales*, aucune section *Coordonnées bancaires*, aucune
surface de virement ou de revenus** sur l'écran. Ce ne sont pas des volets « en attente »
qu'on pourrait relancer : ils n'existent pas. La seule action offerte par le bloc *État du
profil de paiement* est « Clôturer le profil de paiement ».

La distinction payeur ≠ encaisseur posée le matin est donc confirmée sur pièce.

**⚠️ Ce paragraphe portait une erreur, corrigée le même jour — lire l'étape 2 de la
description, qui fait foi.** Il en avait été déduit que le compte marchand ne pouvait pas
se créer avant l'app, et donc que la porte 4 passait en aval de `task-238` AC#1. **Faux.**
L'inférence tirée de l'absence d'entrée *Paiements* dans le menu latéral a été démentie par
la doc Google (`answer/7161426`) puis par l'écran lui-même : le parcours vit à
**Paramètres → Profil de paiement**, ne demande aucune app, et déroule directement le
formulaire *Profil public de marchand*. La porte 4 est donc **à lancer immédiatement, en
parallèle du build** — c'est le seul poste administratif à délai Google qui ne dépende de
rien.

Ce qu'il faut retenir de la séquence des erreurs de la journée : « le menu ne montre pas X »
n'autorise pas à conclure « X n'est pas faisable ». Deux fois de suite, une entrée
manquante a été lue comme une impossibilité, alors que l'objet vivait simplement ailleurs
— hors console la première fois, sous *Paramètres* la seconde.

Trois relevés annexes du même écran :

- `TYPE DE COMPTE : Particulier` — **troisième** confirmation indépendante du compte
  personnel. L'étape 0 est close pour de bon.
- Un crayon d'édition existe sur ce `TYPE DE COMPTE`, là où la Play Console grise
  *Modifier le type de compte*. Consigné comme **piège** : objets distincts, conversion
  impossible côté Google, et rien à gagner — la manip ne peut que casser le profil qui a
  réglé les $25.
- Le `N° DE TÉLÉPHONE` du profil de paiement est **vide**, alors que le numéro de contact
  Play Console est validé depuis ce matin. Deux champs distincts ; non bloquant, mais à
  renseigner si la création du compte marchand le réclame.
<!-- SECTION:NOTES:END -->
