---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Challenge du système de pricing de bout en bout

> Répertoire provisoire. Le brief demande `docs/research/task-<NN>-pricing-challenge/` ; aucun
> numéro ne m'a été attribué et la session n'était pas interactive. Le prochain libre est
> **task-383** (`backlog/tasks/` s'arrête à `task-382`). Un `git mv` suffit.

## Owner Validation

**Decision**:

**Validated at**:

---

## Recommendation

**Il faut refondre, pas rapiécer : remplacer la minute par un crédit, ramener trois formules à un
palier gratuit permanent plus deux payants, facturer un forfait par envoi en plus du volume, et
sortir le nom des formules de la config pour le mettre dans les onze catalogues.** La grille de
remplacement, son barème vérifié ligne à ligne contre le coût mesuré, son arithmétique de marge et
sa copy sont en **§ La refonte proposée**. Les quatre axes qui suivent en sont la preuve, pas la
livraison.

Le diagnostic qui impose cette forme : l'unité facturée est juste pour le seul chemin sur lequel
elle a été calibrée (l'audio transcrit par Deepgram) et fausse d'un facteur 2 à 10 sur les trois
autres chemins qui débitent le même compteur. Au plafond, sur un usage 100 % YouTube, les trois
tiers actuels sont déficitaires : −1,22 € sur Reader, −13,17 € sur Mix, −33,74 € sur Audio-Heavy,
contre des nets de 2,125 / 3,542 / 6,375 €. Ce n'est pas un cas pathologique : c'est l'usage
nominal de la source mise en avant.

Par force décroissante :

1. **`captions_minutes: 1` casse l'équivalence sur laquelle repose tout le filet de sécurité.**
   Une vidéo YouTube de 3 h débite 1 minute (0,00664 € de budget). Ce qu'elle coûte dépend de ce que
   l'utilisateur demande, et **elle est déficitaire dès le cas le plus dépouillé** :

   | Scénario, vidéo de 3 h (~36 k tokens) | Coût réel | Ratio vs 0,00664 € débités |
   |---|---|---|
   | Rien demandé, pas de traduction (Apify + `review_blurb`) | 0,0106 € | **1,60×** |
   | Les deux appels automatiques (+ traduction) | 0,0245 € | **3,69×** |
   | Les cinq artefacts demandés une fois chacun | **0,0562 €** | **8,46×** |

   Un seul appel LLM est **systématique** (`review_blurb`), un est **conditionnel** (la traduction,
   seulement si la langue des sous-titres diffère de `reading_language`) et cinq sont **à la
   demande** — correction d'une affirmation antérieure de ce document, qui parlait de « sept appels
   automatiques » : voir § R.6 pour la nature exacte de chacun. La thèse validée en task-287 —
   « chaque euro de coût variable débite le même compteur » — est fausse par construction pour la
   source qui porte le produit, et elle l'est **même quand l'utilisateur ne demande rien**. Détail et
   arithmétique : § Axe 2.

2. **Le coût de la minute déclaré dans la config cite le mauvais produit Deepgram.** La source
   inscrite est « $0.0077/min » (`pricing_config_service.py:154-157`) : c'est le **tarif *streaming*
   régulier** de nova-3, aujourd'hui affiché en promotion à $0.0048/min. Le chemin réellement
   utilisé est le **batch** (`POST /v1/listen`, `deepgram_worker.py:192-203`), facturé
   **$0.0043/min** monolingue et **$0.0052/min** multilingue. Le coût réel de la minute est donc
   **0,003703 €**, pas 0,00664 € : la config **surestime de 1,79×** le seul chiffre qu'elle prétend
   sourcer. Erreur conservatrice sur l'audio — et c'est exactement ce qui masque les deux chemins
   sous-facturés.

3. **La bascule LlamaParse → Unstructured multiplie par 9,7 le coût d'une page sans toucher au
   compteur — et elle arrive trois fois plus vite que la config ne le croit.** Le tarif réellement
   facturé n'est plus une déduction : il est **mesuré** le 2026-09-09 sur les 35 jobs de
   l'organisation LlamaCloud (`/api/v1/beta/usage-metrics`, § Sources). Le repo appelle l'**API v1**
   (`llamaparse_resolver.py:36`) sans envoyer de mode (`:191-194` n'envoie que `result_type:
   markdown` et `language: en`), et le fournisseur facture ce défaut **3,000 crédits/page —
   exactement, sur 92 pages et 28 jobs documentaires** : `parse_page_with_llm`, rapporté depuis le
   2026-08-29 sous le nom `tier: cost_effective`. Soit **0,003225 €/page** contre 0,001328 €
   débités : **le chemin documentaire est sous-facturé 2,4×**, et non excédentaire de 23 % comme
   l'affirmait ce document. Corollaire :
   `monthly_capacity: 10000` **pages** n'achète que **3 333 pages**, `capacity_unit: "pages"` est la
   mauvaise unité (le fournisseur compte des crédits), et à épuisement le 402 est traité comme
   n'importe quel `ParseError` et bascule sur Unstructured à **$0.015/page** = 0,012916 €. Le
   garde-fou censé arrêter ça (`llamaparse.stop_pct: 90`) est **du code mort** :
   `document_parsing/worker.py:256` appelle `record_spend` et **jamais** `spend_allowed`.

4. **Les 15 % de commission sont désormais l'hypothèse de travail : la candidature au Small Business
   Program est déposée.** Déposée par l'owner le **2026-09-09**, sur consigne explicite de traiter la
   réduction comme acquise pour tous les calculs de ce document. Les trois prérequis étaient remplis,
   relevé App Store Connect → **Business** du même jour : *Contrat relatif aux applications payantes*
   → **Actif**, tous les pays ou régions, 2 sept. 2026 – 1 juin 2027 ; *Contrat relatif aux
   applications gratuites* → Actif ; compte bancaire BNP Paribas SA (3423), devise EUR / redevances
   USD → Actif ; W-8BEN et *U.S. Certificate of Foreign Status of Beneficial Owner* → Actif ;
   DSA → Active. Deux conséquences à tenir :

   - **L'horloge n'est pas la nôtre.** Textuellement : « Your proceeds will be adjusted **fifteen
     (15) days after the end of the fiscal calendar month in which your enrollment is approved** ».
     Une approbation en septembre produit donc son effet **vers le 15 novembre 2026**. Entre le
     lancement et cette date les nets sont ceux de 30 %, soit **−17,6 %** (3,542 → 2,917 ;
     6,375 → 5,250). Ce n'est pas une raison de dimensionner à 30 % — c'est une raison de ne pas
     lancer un palier dont la marge à 30 % serait négative, ce que la grille de § R.3 respecte :
     même à 30 % et **au plafond**, elle rend encore **+1,117 €** sur Standard et **+1,650 €** sur
     Intensif.
   - **Rien n'en est écrit dans le dépôt.** « Small Business Program » n'apparaît que dans task-65
     (mai 2026) et **jamais dans `docs/V1_LAUNCH_PLAN.md`**, qui couvre pourtant l'IBAN, le seuil de
     versement et le statut de trader DSA. Côté Google Play les 15 % sont automatiques sur les
     abonnements auto-renouvelables — l'asymétrie n'est écrite nulle part. La date d'approbation est
     à consigner dès qu'elle arrive.

   **La grille de la refonte est dimensionnée à 15 %**, et son risque au plafond est calé sur le même
   ratio variable/net que la version à 30 % — donc elle ne devient pas plus fragile si l'approbation
   traîne, elle devient seulement moins généreuse que ce qu'elle pourrait être.

5. **Deux leviers de coût sont mesurés sur la facture OpenAI elle-même, et aucun des deux ne touche
   au produit.** Le coût LLM n'est plus une estimation : `cached_tokens` est **persisté** dans
   `media_artifacts-dev` (90 générations, § R.6) et **l'export `/v1/organization/costs` du
   2026-06-01 au 2026-09-09** donne la facture réelle, ligne par ligne, token par token (§ R.6, § 3.9).
   Total de toute la consommation OpenAI du projet sur ces trois mois : **0,4464 €**. Trois choses
   en sortent. D'abord, **le prompt caching rapporte −7,6 %**, pas les −56 % que ce document
   annonçait : 8 appels sur 90 touchent le cache et 43 % des appels ont un prompt sous le seuil de
   1 024 tokens. Ensuite, **la traduction est 60,4 % de la facture — et 98,9 % de ce montant est de
   la sortie**, pour un ratio sortie/entrée de **9,40×** facturé sur trois mois. Le cache ne peut
   rien y faire : il ne remise que l'entrée, et l'entrée ne pèse que 1,1 % du coût de ce poste. Le
   gisement est ailleurs : **`reasoning_effort` n'existe nulle part dans le dépôt**, donc les deux
   appels paient le raisonnement par défaut de la famille `gpt-5` **au tarif de sortie** ; le borner
   vaut **−69,2 %** sur les traductions mesurées, soit environ **−0,19 € sur 0,45 €** de facture
   totale. Enfin `review_blurb` — le seul appel que 100 % des ingestions paient, **36,7 % de la
   facture LLM tracée en base** — passe de 0,000685 € à 0,000177 € par appel sur `gpt-5-nano`, soit
   **−74,1 % mesuré** contre −74,9 % modélisé. Ces trois changements sont des variables et deux
   lignes de payload ; ils ne changent ni un prix, ni une allocation, ni un écran.

6. **Il n'existe aucune surface de gestion d'abonnement.** La seule entrée est
   `account.tsx:200-228`, qui pousse `/paywall` **dans tous les états, y compris pour un abonné
   actif** ; la carte d'état n'affiche ni prix, ni montant de renouvellement, ni lien de
   résiliation ; et l'unique route vers le centre d'abonnements du store
   (`STORE_SUBSCRIPTIONS_URL`) est câblée **sur l'écran de suppression de compte**
   (`delete-account.tsx:23,104`), en contradiction avec sa propre docstring.

7. **Le prix absolu du tier haut est battu par un concurrent direct et vivant.** Snipd Premium :
   **$6.99/mois** pour **900 min/mois** de traitement IA sur les épisodes non pré-traités, IA
   illimitée sur 1 M+ épisodes déjà traités, import YouTube et chat inclus, **plus un palier
   gratuit permanent** (2 épisodes/semaine). Audio-Heavy demande 9 € TTC (~$10,45) pour 720 min.

**Arbitrages que j'accepte explicitement, et qui survivent au challenge :**

- **Le taux de change 0,86 EUR/USD est juste.** Référence BCE du 2026-09-08 : 1 EUR = 1,1614 USD,
  soit 1 USD = 0,8611 EUR. Écart avec la constante de `llm_pricing.py:20` : **−0,13 %**. Rien à
  corriger.
- **`_MODEL_PRICES` est exact pour les deux modèles qu'il connaît.** `gpt-5-nano`
  $0.05/$0.005/$0.40 et `gpt-5.4-nano` $0.20/$0.02/$1.25 correspondent au centième près aux tarifs
  publiés aujourd'hui.
- **Le refus de la matrice comparative (task-376) tient.** Ses cinq implémentations de référence ont
  bien été consultées et aucune n'affiche de matrice ; l'argument arithmétique (4 colonnes ≈ 60 pt)
  et l'argument de fond (« toutes les formules font tout ») restent valides. Je ne le contredis pas.
- **Le tarif horaire affiché est dans la devise du store, pas en euros.** `buildHourlyRate` reçoit
  `pkg.product.price` et `pkg.product.currencyCode` (`paywall.tsx:420-422`) : pas de bug de devise.
- **La directive 3.1.2 n'impose pas de lien de résiliation dans l'app.** Vérifié dans le texte
  d'aujourd'hui : l'énumération « how to cancel » est en **4.9 (Apple Pay)**, qui ne s'applique pas
  aux abonnements IAP. 3.1.2(c) délègue à la Schedule 2 de l'ADPLA. Mon hypothèse de départ était
  fausse et je la retire — l'absence de lien est un problème **produit**, pas un risque de rejet.
- **Aucune couche de compatibilité n'est proposée.** Rien n'est en circulation qu'on ne puisse
  réémettre : chaque correction ci-dessous supprime ou remplace en un coup.

---

## La refonte proposée

Cette section est le livrable. Les quatre axes qui la suivent sont l'instruction du dossier ; ici
c'est la grille de remplacement, avec l'arithmétique qui la justifie et l'endroit où chaque
changement s'applique. Tous les chiffres viennent des tarifs relevés en § Sources et sont
recalculés, jamais recopiés.

### R.1 Pourquoi la minute doit céder la place au crédit

Le problème n'est pas que la minute soit mal convertie : c'est qu'**aucun taux unique ne peut
couvrir à la fois l'audio et le texte**, parce que le coût n'a pas une composante mais deux.

Décomposition du coût réel d'une source, obtenue en faisant varier la longueur à barème constant
(tarifs OpenAI et Deepgram de § Sources, traduction rendue conditionnelle) :

```
coût(source) = 0,00592 €  (plancher, indépendant de la longueur)
             + 0,903 €/million de tokens  (volume, les 6 générateurs)
             + acquisition  (Deepgram 0,003703 €/min | Apify 0,0043 € forfait | LlamaParse /page | 0)
```

Deux conséquences, et elles condamnent l'unité actuelle :

1. **Le plancher de 0,00592 € par source ne s'exprime pas en durée.** Il est le même pour une note
   de 200 mots et pour un podcast de 3 h, parce qu'il est fait des *tokens de sortie* des six
   générateurs. Une unité qui est une durée ne peut, par construction, pas porter un coût fixe par
   objet — c'est exactement pourquoi `text_file_minutes: 0` et le « Free » du paywall sont faux :
   ils facturent zéro une chose qui coûte 0,0059 € au minimum.

   *Précision apportée après vérification du pipeline* : ce plancher est celui d'une source dont les
   cinq artefacts sont demandés. Si l'utilisateur ne demande **rien**, le seul appel qui part est
   `review_blurb`, dont la sortie ne coûte que **0,000129 €** (§ R.6). Le forfait de 2 crédits n'est
   donc pas dimensionné sur le pire cas : il est dimensionné sur **la source qui sert**, ce qui est
   le seul cas qui intéresse un produit dont la promesse est justement de générer ces artefacts. Une
   source envoyée puis jamais ouverte est sur-facturée, et c'est assumé — c'est la contrepartie d'un
   barème qu'un acheteur peut lire en une ligne.
2. **La même minute de contenu coûte 22× plus cher en audio qu'en texte.** Une minute d'audio à
   transcrire : 0,003703 € (Deepgram) + 0,00018 € (LLM) = **0,003883 €**. Une minute de contenu
   livrée en texte : **0,00018 €**. Un taux unique appelé « minute » mentira d'un facteur 22 dans
   un sens ou dans l'autre, quelle que soit la valeur qu'on lui donne.

D'où le crédit — non pas comme du jargon, mais comme la seule unité capable de porter un plancher
*et* trois taux de volume différents :

> **1 crédit = 0,005 € de budget fournisseur.** Ancré sur l'intuition que la copy actuelle a déjà
> construite : **1 crédit ≈ 1 minute d'audio transcrit**.

Ce n'est pas un abandon de la thèse de task-287 (« un seul compteur »), c'est ce qui la rend
tenable : le compteur reste unique, il change juste de taux de change.

### R.2 Le barème

Cinq lignes, chacune adossée à un coût mesuré. Le forfait de 2 crédits est ce qui rend le reste
honnête : il paie le plancher, donc plus rien n'est « gratuit ».

| Ce que l'utilisateur envoie | Ce que ça coûte |
|---|---|
| **Tout envoi**, quel qu'il soit | **2 crédits** |
| + audio ou vidéo qu'il faut transcrire | **+ 1 crédit par minute commencée** |
| + vidéo dont on achète les sous-titres (YouTube…) | **+ 1 crédit par 20 minutes commencées** |
| + document (PDF, photo de page) | **+ 1 crédit par page** |
| + article, page web, post, note, fichier texte | **rien de plus** |
| Génération sur un dossier entier | **1 crédit par 3 sources** |

Vérification contre le coût réel, dans l'hypothèse **prudente** (aucun *cache hit* de prompt,
traduction rendue conditionnelle). « Couverture » = ce qui est facturé ÷ ce que ça coûte :

| Source | Facturé | Coût réel | Couverture |
|---|---|---|---|
| Podcast 60 min | 62 crédits = 0,3100 € | 0,2386 € | **130 %** |
| Podcast 180 min | 182 crédits = 0,9100 € | 0,7041 € | **129 %** |
| Vidéo YouTube 20 min | 3 crédits = 0,0150 € | 0,0138 € | **108 %** |
| Vidéo YouTube 3 h | 11 crédits = 0,0550 € | 0,0427 € | **129 %** |
| Article, page web, note | 2 crédits = 0,0100 € | 0,0077 € | **129 %** |
| PDF 10 pages (LlamaParse à **3 crédits/page**) | 12 crédits = 0,0600 € | 0,0442 € | **136 %** |
| PDF 10 pages (**repli Unstructured**) | 12 crédits = 0,0600 € | 0,1409 € | **43 %** |

Le barème couvre tout entre 108 % et 136 %, sauf une ligne — et cette ligne ne se corrige pas par
le prix. Facturer la page au coût d'Unstructured (2,6 crédits/page) ferait payer 28 crédits un PDF
de 10 pages à tous les utilisateurs pour couvrir une panne de LlamaParse. **La réponse est de
supprimer le repli**, pas de le tarifer : voir R.4.

La ligne documentaire est celle qui a le plus bougé depuis la première version de ce document, et
c'est le seul endroit où le barème a été **re-dérivé plutôt que confirmé** : à 3 crédits/page — le
tarif v1 le moins cher qui produise du markdown, cf. argument 3 — la page coûte 0,003225 € en
acquisition, contre 0,005 € facturés par le crédit de page, soit **155 % sur le seul terme
d'acquisition**. Le 1 crédit/page du barème tient donc, alors que le `document_pages_per_minute: 5`
d'aujourd'hui ne tenait pas.

**Le barème est dimensionné sans cache, et c'est maintenant un choix mesuré, plus une prudence.** Sur
les 90 générations de `media_artifacts-dev`, le prompt caching ne récupère que **7,6 %** du coût LLM
(§ R.6, point 3) : 8 appels sur 90 touchent, 43 % ont un prompt sous le seuil de 1 024 tokens
qu'OpenAI exige, et le TTL relevé — `in_memory`, ~5–10 min d'inactivité, 1 h au maximum, pas de
rétention étendue 24 h sur `gpt-5.4-nano` — confine le gain à **l'intérieur d'une rafale**. Un
utilisateur qui demande un résumé aujourd'hui et des flashcards demain paie deux fois l'entrée
pleine. Compter sur le cache dans un barème aurait donc été une erreur de 7,6 %, pas de 56 %.

### R.3 La grille de paliers

Trois formules dont deux ne diffèrent que par un nombre, sans moyen de connaître son propre
volume : c'est le vrai défaut de compréhensibilité, et il ne se règle pas par de la copy. Il se
règle par un **palier gratuit permanent**, qui est l'instrument avec lequel l'acheteur mesure sa
consommation avant de choisir.

Dimensionnée à **15 % de commission**, la candidature au Small Business Program étant déposée
(cf. argument 4). Les allocations sont calées sur le **même ratio variable/net au plafond** que la
version à 30 % de la première mouture de ce document (51 % et 57 %) : la réduction de commission est
donc rendue à l'utilisateur en crédits, pas encaissée en marge. C'est un choix, et il est
réversible à la baisse sans changer un prix.

| Palier | Prix TTC | Crédits/mois | Net 15 % | Var. au plafond | Marge 15 % | Marge si 30 % |
|---|---|---|---|---|---|---|
| **Découverte** | gratuit | **40** | — | 0,20 € | −0,20 € | −0,20 € |
| **Standard** | **5,00 €** | **360** | 3,542 € | 1,80 € (51 %) | **+1,742 €** | +1,117 € |
| **Intensif** | **9,00 €** | **720** | 6,375 € | 3,60 € (56 %) | **+2,775 €** | +1,650 € |

La colonne de droite est ce qui rend la grille sûre : **elle reste bénéficiaire au plafond même si
l'approbation Apple n'arrive jamais.** Aucune des trois formules actuelles n'a cette propriété.

Ce que chaque palier veut dire pour quelqu'un qui n'a jamais mesuré sa consommation :

| | Découverte (40) | Standard (360) | Intensif (720) |
|---|---|---|---|
| Podcasts / audio | 38 min | **≈ 6 h** | **≈ 11 h 30** |
| Vidéos YouTube d'1 h | 8 | 72 | 144 |
| Articles, pages web, notes | 20 | 180 | 360 |
| PDF de 10 pages | 3 | 30 | 60 |

**Annuel, −20 %** : Standard **47,99 €/an** (net 33,99 €), Intensif **85,99 €/an** (net 60,91 €).
Readwise annonce −24 % sur son propre annuel (« Save 24% », $12.99 → $9.99), donc −20 % est dans la
norme du segment. C'est un produit plus un package, sans code
(`docs/REVENUECAT_ENTITLEMENTS.md:223-242`).

**Recharge consommable, 100 crédits pour 2,99 €** : coût 0,50 €, net à 15 % **2,118 €**, marge
1,618 € soit **76 %** — meilleure marge que l'abonnement, parce qu'elle n'engage aucun quota au-delà
d'elle-même. Sa raison d'être n'est pas le revenu : c'est de transformer le mur `out_of_minutes` en
un choix. Un refus qui ne propose que « attendre le mois prochain ou passer au palier supérieur » est
un refus qui perd l'usage du jour.

**Seuil de rentabilité**, contre les 38,10 €/mois de charge fixe mesurée (31,91 € de task-287, la
seule baseline mesurée, + ~7,20 $/mois d'observabilité prod), **abonnés supposés au plafond** — donc
le pire cas, pas le cas nominal :

| | à 15 % (hypothèse retenue) | si l'approbation traîne (30 %) |
|---|---|---|
| Abonnés Standard nécessaires | **22** | 35 |
| Abonnés Intensif nécessaires | **14** | 24 |

Et à l'échelle, sur Standard, avec une hypothèse de charge de **35 % du plafond** (hypothèse
explicite, aucune donnée ne l'appuie — voir § Questions restées ouvertes) :

| Abonnés | Revenu net | Variable | Fixe | Résultat |
|---|---|---|---|---|
| 10 | 35,42 € | 6,30 € | 38,10 € | **−8,98 €** |
| 100 | 354,17 € | 63,00 € | 38,10 € | **+253,07 € (71,5 %)** |
| 1 000 | 3 541,67 € | 630,00 € | 38,10 € | **+2 873,57 € (81,1 %)** |

Le modèle ne bascule pas sur le coût variable : il bascule sur la charge fixe, entre 14 et 22
abonnés au plafond, ou **une douzaine** au facteur de charge de 35 %. Avec ~12 testeurs beta
aujourd'hui, **c'est ça la cible du lancement**, pas un chiffre de croissance.

Un poste échappe pourtant à ce raisonnement, et il faut le nommer ici parce qu'il change la
signification du crédit : **les records Algolia sont un stock, pas un flux** (§ 3.6). Le crédit paie
l'*acquisition* d'une source ; ce qui paie sa *conservation* dans l'index de recherche, mois après
mois, c'est l'abonnement lui-même. Mesuré sur dev, l'ordre de grandeur est faible — 1,87 records par
source, donc **+0,013 €/mois de loyer par abonné et par mois d'ancienneté** — mais il est monotone
croissant et il n'existe aucune règle de rétention par âge dans le code. À 20 sources/mois, un
abonné Standard de deux ans coûte 0,31 €/mois de loyer d'index, soit 9 % de son net. C'est
supportable et ça n'invalide rien ; c'est simplement le seul terme que ni une recharge ni un crédit
ne peuvent couvrir, et il justifie que le palier gratuit soit **compté en crédits et borné en
stock** plutôt qu'illimité en conservation.

### R.4 Ce qui disparaît, et pourquoi

- **Le palier à 3 € (`text_only` / « Reader »).** Sa raison d'être était « seulement du texte », une
  catégorie qui cesse d'exister dès que le texte est mesuré. Même à 15 % de commission son net est de
  2,125 € : il faudrait **18 abonnés au minimum** — avant tout coût variable — pour couvrir la seule
  infrastructure, et son pire cas YouTube est déficitaire (§ 2.2a). Le remplaçant du bas de gamme est
  le palier gratuit, pas un palier payant à marge nulle.
- **L'essai gratuit de 30 jours.** Il coûte jusqu'à **2,89 €** de dépense fournisseur réelle par
  essayeur (300 min × 0,00964 €) pour un revenu de zéro, et surtout : sur l'App Store un essai
  introductif **s'obtient en souscrivant** — moyen de paiement, engagement, écran d'achat. Il ne
  permet donc **pas** à l'acheteur de mesurer sa consommation avant de décider, qui est précisément
  le service qu'on attend de lui. Le palier gratuit permanent le rend, à 0,20 €/mois/utilisateur.
- **Le repli Unstructured.** 43 % de couverture même avec le barème corrigé, et il se déclenche sur
  *n'importe quelle* `ParseError` (`docs/INGESTION_WORKERS_PROVIDERS.md:509`), y compris le HTTP 402
  d'un pool épuisé. Quand LlamaParse ne répond pas, le document attend ou est refusé — il n'est pas
  traité en silence à 3,7× le prix.
- **`name_fr`.** Mauvaise forme, pas mauvaise valeur : **un champ pour onze locales**. Le nom d'une
  formule est de la copy, donc une clé i18n. Voir R.5.
- **`captions_minutes`, `document_pages_per_minute`, `text_file_minutes`, `folder_sources_per_minute`,
  `minutes_per_month`, `max_minutes_per_item`.** Remplacés, pas conservés. Attention : le docstring
  de `_merge_defaults` (`pricing_config_service.py:210-214`) est explicite — une clé de premier
  niveau retirée des defaults **reste dans la table** jusqu'à sa suppression. Il faut donc les
  supprimer dans `pricing_config-dev` *et* `pricing_config-prod`, pas seulement dans le code.

Aucune couche de compatibilité n'est nécessaire : rien n'est en circulation qu'on ne puisse
réémettre, et un testeur ne détient que le build qu'il a installé.

### R.5 Comment on le dit à quelqu'un qui ne connaît rien

Le paywall actuel est meilleur que ce que l'axe 1 laissait croire : il a déjà une table de coûts en
langage humain (`plan.cost.*`), un sélecteur « Choose how much you send each month », et un badge
**RECOMMENDED FOR YOU** calculé sur l'usage réel (`plan.rec.cappedNextUp`, `plan.rec.covering`…).
L'architecture de la copy n'est pas à refaire. **Ce qu'elle dit est faux, voilà le problème.**

Contraintes que toute proposition doit respecter, lues dans `mobile/src/i18n/en.ts:1-14` : clés
plates en `point.namespace`, familles de pluriel `<base>.one` / `<base>.other` lues par `tCount` via
`Intl.PluralRules` — **jamais un compte collé à un suffixe fixe** —, l'arabe déclare **six**
catégories, et une clé présente dans `en` doit être présente dans les dix autres catalogues.

| Clé | Aujourd'hui | Ce qu'il faut, et pourquoi |
|---|---|---|
| `plan.cost.captions.label` | « A YouTube video, **whatever its length** » | Supprimer la clause. Elle **vend le bug comme un avantage** : c'est la ligne qui promet le forfait à 8,5× de perte. |
| `plan.cost.value.free` | « Free » | **Supprimer la clé.** Plus rien n'est gratuit — le forfait de 2 crédits paie le plancher de 0,0059 €. |
| `paywall.costHeading` | « What it costs in minutes » | Neutre en unité : « Ce que chaque envoi coûte ». |
| `plan.tier.name.{free,standard,heavy}` | *(absent — vient de `name`/`name_fr`)* | **Nouvelles clés.** Le rendu le plus long est l'allemand : c'est lui qui fixe la largeur de carte. |
| `plan.card.equivalent.{one,other}` | *(absent)* | **La ligne la plus utile de la carte** : « ≈ 5 h de podcast ou 150 articles par mois ». Famille de pluriel obligatoire. |
| `plan.card.allowance` | « {duration} per month » | « {credits} crédits par mois » — famille de pluriel. |
| `quota.refusal.noPlan` | annonce la fin d'un forfait à qui n'en a jamais eu | Scinder : un message pour « jamais abonné », un pour « forfait terminé ». |
| `quota.refusal.topUp` | *(absent)* | Seconde action sur le mur : « Ajouter 100 crédits — 2,99 € ». C'est ce qui fait du refus un choix. |
| `plan.cta.startFree` | *(absent)* | Le palier gratuit a besoin d'un CTA qui ne dise pas « acheter ». |

Trois règles de rédaction qui tiennent dans les onze locales :

1. **Un chiffre, jamais un mécanisme.** « 1 crédit par minute » se traduit ; « conversion d'unité de
   transcription » ne se traduit pas et ne se comprend pas.
2. **Toujours le crédit *avec* son équivalent humain.** Le crédit seul est opaque ; « 300 crédits
   ≈ 5 h de podcast » est lisible sans rien savoir du produit.
3. **Pas de mise en page qui suppose des espaces entre les mots.** Le japonais et le chinois n'en
   ont pas : l'équivalence doit être une chaîne entière, pas deux fragments concaténés à l'écran.

### R.6 Le levier de coût qui n'est pas un levier de prix

Avant de changer un prix, il y a de la facture LLM à récupérer sans toucher au produit. Mais d'abord
il faut dire exactement **ce qui part, et quand** — ce que ce document affirmait faux, et que
l'inspection du pipeline tranche.

**Il n'existe que deux sites d'appel LLM dans tout le code** : `artifact_generator/worker.py:159`
(un appel = un type d'artefact sur tout le corpus, `:12-17`, stratégie S1 de task-269) et
`transcript_translation.py:320`. Sept appels sont donc *possibles* par source, mais leur régime
diffère :

| Appel | Modèle réel | Régime | Coût, source de 3 h | Coût, vidéo d'1 h |
|---|---|---|---|---|
| `review_blurb` | `gpt-5.4-nano` | **systématique**, un par observateur du média | 0,006306 € | 0,002344 € |
| traduction du transcript | `gpt-5-nano` | **conditionnel** : seulement si `detected_language` ≠ `reading_language` | 0,013897 € | 0,004983 € |
| `notes` | `gpt-5.4-nano` | à la demande | 0,007789 € | 0,003827 € |
| `summary_detailed` | `gpt-5.4-nano` | à la demande | 0,007467 € | 0,003504 € |
| `quiz` | `gpt-5.4-nano` | à la demande | 0,007467 € | 0,003504 € |
| `flashcards` | `gpt-5.4-nano` | à la demande | 0,007252 € | 0,003289 € |
| `summary_short` | `gpt-5-nano` | à la demande | 0,001682 € | 0,000691 € |
| **Total si tout part** | | | **0,051858 €** | **0,022143 €** |
| **dont automatique** | | | **0,020203 €** | **0,007326 €** |

Trois faits qui en découlent, et qui déplacent le levier :

1. **Le seul appel systématique est `review_blurb`, et il tourne sur le modèle le plus cher.**
   `media_completed_worker.py:110-142` le déclenche à la fin de l'ingestion, une fois pour le
   soumetteur canonique (`:293-296`) **et une fois par observateur** du même média (`:372-377`). Sa
   sortie est minuscule et bornée par construction : `MAX_POINTS = 4`, un hook de 60–100 caractères,
   des points de 35–65, `MAX_TOTAL_CHARS = 700` (`review_blurb.py:39-56`), soit ~120 tokens de
   sortie. **Tout son coût est de l'input**, et l'input n'a aucune raison d'être payé au tarif
   `gpt-5.4-nano` ($0.20/1M) pour produire quatre puces. Le basculer sur `gpt-5-nano` ($0.05/1M) fait
   passer l'appel de 0,006306 € à **0,001585 €** sur une source de 3 h, soit **−74,9 %** — et
   −74,6 % sur une vidéo d'1 h. C'est **le seul levier qui s'applique à 100 % des ingestions**, et il
   coûte une variable d'environnement.
2. **La traduction est le premier poste, mais elle est déjà conditionnelle.** `transcript_translation.py:1-31`
   est explicite : l'étape 2 ne traduit *« only when `detected_language` differs from the user's
   `reading_language` »*, après un `langdetect` local et gratuit. Ce document affirmait qu'elle était
   automatique : c'est faux, et je le retire. Ce qui reste vrai est sa forme : **c'est le seul appel
   dont la sortie est aussi longue que l'entrée**, puisqu'il réémet le transcript entier sans
   découpage (`:296`, « the 400k-token window covers any realistic transcript »). Son coût est donc
   dominé par l'output à $0.40/1M. Le levier n'est plus « la rendre conditionnelle » mais **« ne pas
   traduire le transcript brut »** : les cinq artefacts en sont tirés et pourraient être générés
   directement dans la langue de lecture, ce qui économise 0,0139 € par source de 3 h traduite.
3. **Le prompt caching rapporte −7,6 %, et c'est maintenant mesuré, plus modélisé.** `cached_tokens`
   n'est pas seulement journalisé : il est **persisté** dans `media_artifacts-dev`
   (`media_artifact.py:127-133,195-202`), donc lisible sans attendre l'owner. Sur les **90
   générations** que la table porte au 2026-09-09 :

   | Ce qui est mesuré | Valeur |
   |---|---|
   | appels avec `cached_tokens > 0` | **8 / 90** (8,9 %) |
   | tokens de prompt cachés | 58 368 / 414 866 = **14,1 %** |
   | coût réel (cache inclus) | **0,110110 €** |
   | coût si le cache n'avait jamais touché | 0,119149 € |
   | **économie effective** | **0,009039 €, soit −7,6 %** |
   | borne haute théorique (100 % du prompt caché dès que prompt ≥ 1 024 tk) | −48,5 % |

   Le cache réalise donc **16 %** de son potentiel. Trois causes, toutes vérifiables :
   **(a)** 39 appels sur 90 (**43 %**) ont un prompt sous le seuil de 1 024 tokens qu'OpenAI exige
   pour cacher quoi que ce soit — inéligibles par construction, et ce sont les articles courts, pas
   les vidéos. **(b)** Quand il touche, il touche fort — de **60,4 % à 95,4 %** du prompt : ce n'est
   pas un demi-succès à améliorer, c'est un tout-ou-rien dont le tirage est le routage. **(c)** La
   médiane des intervalles entre deux générations sur dev est de **4,9 min**, juste au bord du TTL
   relevé par l'owner (`in_memory`, ~5–10 min d'inactivité, 1 h au maximum ; ni `gpt-5.4-nano` ni
   `gpt-4o-mini` ne figurent dans la liste des modèles à rétention étendue 24 h — `gpt-5.4` y est,
   `gpt-5.4-nano` non, ce sont deux modèles distincts). Le **−56 % que ce document annonçait est
   retiré** : le mesuré est −7,6 %, et même le plafond théorique reste sous la moitié.
   Un point s'ajoute, et la facture OpenAI corrige ici une erreur que ce document a portée :
   **la traduction n'est pas « hors cache », elle est hors d'atteinte du cache.** Le raisonnement
   « elle n'envoie aucun `prompt_cache_key` (zéro occurrence dans `transcript_translation.py`), donc
   elle ne cache rien » était faux : `prompt_cache_key` est un *hint de routage*, pas une condition
   d'éligibilité, et OpenAI cache automatiquement tout préfixe de ≥ 1 024 tokens. L'export
   `/v1/organization/costs` le montre — la ligne `gpt-5-nano-2025-08-07, cached input` porte
   **12 928 tokens**, dont **zéro** ne vient des artefacts (les 10 `summary_short`, seul artefact sur
   ce modèle, ont `cached_tokens = 0` sur les 10). Ces 12 928 tokens sont donc de la traduction, soit
   **15,7 %** de son prompt. Et l'économie correspondante est de **0,19 %** de son coût. La raison
   est structurelle et vaut mieux que l'argument faux qu'elle remplace : **le cache ne remise que
   l'entrée, et l'entrée ne pèse que 1,1 % du coût de la traduction** (§ point 4). Le premier poste
   de coût ne peut donc rien attendre du cache — non parce que le cache ne le touche pas, mais parce
   qu'il ne touche pas là où l'argent part. Le barème de § R.2 est dimensionné sans cache, ce qui
   reste le bon choix.
4. **Le vrai gisement n'est pas le cache, c'est le raisonnement que personne n'a borné.**
   `reasoning_effort` n'apparaît **nulle part** dans le dépôt — ni dans `media_summarizer/`, ni
   `infra/`, ni `mobile/`. Les deux payloads sont minimaux : `model` + `messages` (+ `response_format`
   et `prompt_cache_key` côté artefacts, `worker.py:139-148`). Or `gpt-5-nano` et `gpt-5.4-nano` sont
   des modèles de raisonnement : à défaut d'instruction, ils raisonnent au réglage par défaut et
   **ces tokens sont facturés au tarif de sortie** — 8× l'entrée sur `gpt-5-nano`, 6,25× sur
   `gpt-5.4-nano`. Les 17 traductions journalisées sur les 14 jours de rétention CloudWatch le
   montrent en clair : ratio sortie/entrée agrégé de **4,50**, dont **97,3 % du coût est de la
   sortie**. Mais le ratio n'est pas proportionnel — il s'effondre avec la taille :

   | Entrée | n | Ratio sortie/entrée |
   |---|---|---|
   | < 1 000 tokens | 14 | **11,39** |
   | ≥ 1 000 tokens | 3 | 2,93 |
   | le plus gros cas mesuré (9 283 tk, en→fr) | 1 | **1,12** |

   La régression donne `sortie ≈ 3 402 + 1,58 × entrée` (R² 0,416, 17 points) : **un plancher de
   ~3 400 tokens de sortie par appel, indépendant de la longueur**. Deux conséquences opposées, et
   il faut les garder séparées. Sur une **vidéo longue** ce plancher s'amortit : à 9 283 tokens le
   ratio mesuré est 1,12, donc l'hypothèse « sortie ≈ entrée » que ce document utilise pour la
   traduction **tient** et n'a pas à être révisée. Sur une **source courte** il domine tout : une
   traduction de 458 tokens en a produit 7 699, soit 16,8×. Envoyer `reasoning_effort: "minimal"`
   ramènerait la sortie de traduction à ~1,3× l'entrée, soit **−69,2 %** sur les 17 appels mesurés —
   sur le poste qui est déjà le premier. Le même défaut travaille côté artefacts : `summary_short`
   dépense **92 %** de son coût en sortie pour un résumé *court* (ratio 1,39), `notes` 83 %,
   `quiz` 58 %. Seul `review_blurb` en est exempt (ratio 0,02, 13 % du coût en sortie), ce qui
   confirme le point 1 : son coût est de l'entrée, et le levier est le modèle, pas la sortie.

   **La facture OpenAI confirme ce plancher sur trois mois, pas sur 14 jours de logs.** L'export
   `/v1/organization/costs` du 2026-06-01 au 2026-09-09 ventile la consommation par modèle et par
   type de token. En retirant la part attribuable aux artefacts (déduite type par type, § tableau
   ci-dessous), le résidu `gpt-5-nano` — c'est-à-dire la traduction — vaut **69 489 tokens d'entrée
   pleine + 12 928 cachés pour 774 714 tokens de sortie**, soit un ratio **9,40×** facturé. Cette
   sortie coûte $0,3099 sur les $0,3134 du poste : **98,9 % du coût de la traduction est de la
   sortie**, et l'entrée 1,1 %. Le plancher de raisonnement n'est donc pas un artefact de la fenêtre
   CloudWatch : il est **la structure de coût du poste principal**, mesurée sur toute l'histoire du
   projet. C'est ce qui fait de `reasoning_effort` le premier levier en euros absolus, devant le
   basculement de `review_blurb`.

Ce que les 90 générations coûtent réellement, par type — à comparer aux estimations du tableau
ci-dessus, qui bornaient la sortie au lieu de la mesurer :

| Type | Modèle | n | Entrée | Sortie | Sortie/entrée | Coût mesuré | Part du coût en sortie |
|---|---|---|---|---|---|---|---|
| `review_blurb` | `gpt-5.4-nano` | 59 | 228 613 | 4 938 | 0,02 | 0,040389 € | 13 % |
| `flashcards` | `gpt-5.4-nano` | 5 | 75 542 | 9 176 | 0,12 | 0,022857 € | 43 % |
| `quiz` | `gpt-5.4-nano` | 8 | 51 678 | 9 303 | 0,18 | 0,017382 € | 58 % |
| `notes` | `gpt-5.4-nano` | 6 | 32 171 | 10 193 | 0,32 | 0,013202 € | 83 % |
| `summary_short` | `gpt-5-nano` | 10 | 18 551 | 25 804 | 1,39 | 0,009673 € | 92 % |
| `summary_detailed` | `gpt-5.4-nano` | 2 | 8 311 | 4 817 | 0,58 | 0,006607 € | 78 % |
| **Total** | | **90** | **414 866** | **64 231** | | **0,110110 €** | **46 %** |

Deux chiffres à retenir de ce tableau. `review_blurb` pèse **36,7 %** de toute la facture LLM de dev
à lui seul — ce que 59 appels sur 90 laissaient prévoir, et ce qui confirme qu'il est le bon endroit
pour agir. Et son coût mesuré est de **0,000685 € par appel** pour un prompt moyen de 3 874 tokens et
83 tokens de sortie : le basculer sur `gpt-5-nano` le ramène à 0,000177 €, soit **−74,1 % mesuré sur
les 59 appels réels** — à comparer au −74,9 % modélisé du point 1. Les deux méthodes convergent, ce
qui est la meilleure raison de faire ce changement en premier.

#### La facture OpenAI, du 2026-06-01 au 2026-09-09

Le tableau ci-dessus mesure ce que la base journalise. L'export `/v1/organization/costs` fourni par
l'owner le 2026-09-09 mesure ce qui a été **facturé**, et sur une fenêtre trois fois plus large. Les
deux se recoupent, ce qui permet de valider l'instrumentation et d'attribuer le reste.

| Ligne facturée | Entrée pleine | Entrée cachée | Sortie | Sortie/entrée | Coût |
|---|---|---|---|---|---|
| `gpt-5.4-nano-2026-03-17` — les 5 artefacts hors `summary_short` | 520 274 | 58 368 | 71 313 | 0,12 | $0,194363 |
| `gpt-5-nano-2025-08-07` — traduction + `summary_short` | 88 040 | 12 928 | 800 518 | **7,93** | $0,324674 |
| **Total** | **608 314** | **71 296** | **871 831** | | **$0,519037 = 0,4464 €** |

Trois lectures, dans l'ordre de ce qu'elles changent :

| Ce que la facture établit | Conséquence |
|---|---|
| **Les six tarifs de `_MODEL_PRICES` sont exacts.** `amount / quantity` reconstruit $0,20 / $0,02 / $1,25 sur `gpt-5.4-nano` et $0,05 / $0,005 / $0,40 sur `gpt-5-nano` — **écart nul sur les six**, à la précision de l'export | La question de l'**uplift régional de 10 %** est tranchée : il n'est **pas appliqué**. `llm_pricing.py:22-25` n'a rien à corriger (question 7 close) |
| **`cost_eur` journalisé est juste.** Recalculé depuis les tarifs facturés sur les 90 générations : 0,110114 € contre 0,110110 € en base, soit **+0,0037 %** (arrondis) | `estimate_llm_cost_eur` déduit correctement le cached input. Aucun correctif à porter sur le calcul |
| **La traduction est 60,4 % de la facture** (0,2695 € sur 0,4464 €), les artefacts tracés en base 24,7 %, les artefacts antérieurs à la fenêtre de la table 14,9 % | Le poste principal du coût LLM n'est ni le résumé ni les flashcards : c'est **la traduction du transcript brut**, et elle est presque entièrement de la sortie |

Deux réserves sur cette confrontation, qui limitent ce qu'on peut en tirer sans la fausser :

- **L'export ne ventile pas par clé API.** `api_key_id` et `user_email` sont `null` sur les 105
  lignes, et tout est sur un projet unique (`Default project`). On ne peut donc pas prouver que ces
  0,4464 € viennent tous du backend `-dev` plutôt que d'un essai manuel de l'owner. L'indice contraire
  est fort : **seuls les deux modèles du dépôt apparaissent**, aucun `gpt-4o`, aucun embedding, aucun
  Whisper — la contamination hors-dépôt est donc nulle ou négligeable.
- **La séparation traduction / `summary_short` est déduite, pas lue.** Les deux partagent
  `gpt-5-nano` et la facture ne distingue pas l'appelant. Le résidu de 774 714 tokens de sortie est
  obtenu en soustrayant les 25 804 tokens des 10 `summary_short` tracés en base ; si une part du
  résidu était en réalité des `summary_short` antérieurs à la fenêtre de la table, le ratio de la
  traduction serait **plus élevé encore** (`summary_short` mesure 1,39×, contre 9,40× pour le
  résidu). La borne est donc conservatrice.

Un piège dormant, à noter parce qu'il coûte de l'argent le jour où il se réveille :
`generators/notes.py:102` est le **seul** générateur dont le défaut en dur diverge —
`gpt-4o-mini-2024-07-18` au lieu de `gpt-5.4-nano-2026-03-17` — et `gpt-4o-mini` est **absent de
`_MODEL_PRICES`** (`llm_pricing.py:22-25`), donc facturé au `_FALLBACK_PRICE`. Il est inoffensif
aujourd'hui parce que le secret positionne `OPENAI_MODEL` ; il devient un coût invisible le jour où
quelqu'un retire cette variable. La famille `*_LLM_MODEL` est du même bois : elle n'existe que dans
`.env.example`, aucun secret runtime ne la porte (`review_blurb.py:20-23`).

**Cette résolution est maintenant vérifiée en console, et elle contredit une affirmation du
backlog.** La Lambda `media-summarizer-worker-artifact_generator-dev` porte **51 variables
d'environnement, dont aucune ne contient `MODEL` ni `OPENAI`** ; le secret runtime
`media-summarizer-runtime-dev` porte **40 clés, dont exactement deux de configuration de modèle** :
`OPENAI_MODEL = gpt-5.4-nano-2026-03-17` et `DEEPGRAM_MODEL = nova-3`. Ni `SUMMARY_SHORT_LLM_MODEL`
ni `TRANSLATION_LLM_MODEL` n'existent nulle part au runtime, donc leurs défauts de code
(`gpt-5-nano-2025-08-07` dans les deux cas) sont ce qui tourne — ce que la facture confirme, puisque
`gpt-5-nano` y représente 62,6 % du montant. En revanche l'AC de **task-370** conclut que « la Lambda
ne définit ni `QUIZ_LLM_MODEL` ni `OPENAI_MODEL`, donc le défaut de `default_model` s'applique » :
la prémisse est juste, la conclusion est fausse — le secret injecte `OPENAI_MODEL`, et c'est
précisément ce qui empêche `notes` de partir sur `gpt-4o-mini`. L'absence totale de `gpt-4o-mini` de
la facture sur trois mois le prouve indépendamment du code.

### R.7 Où chaque changement s'applique

| Quoi | Où, exactement |
|---|---|
| Barème, paliers, plafonds | `DEFAULT_PRICING_CONFIG` (`pricing_config_service.py:42-190`) **puis** `PUT /api/pricing/admin` (Bearer `PRICING_ADMIN_SECRET`), effet sous 5 min de TTL |
| Clés retirées | **Suppression explicite** dans les tables `pricing_config-dev` et `pricing_config-prod` — cf. R.4 |
| Réponse publique | `pricing.py:92-146` : `tier_order` codé en dur à retirer, `name_fr` et `price_ttc_eur` à retirer (morts, cf. axe 1) |
| Noms et copy | `mobile/src/i18n/{ar,de,en,es,fr,hi,it,ja,nl,pt,zh}.ts` — onze catalogues, `en` d'abord car il dérive le type `TranslationKey` |
| Produits et packages | RevenueCat, sans code : `POST /v2/projects/proj879a771a/products`, puis `…/entitlements/<entitlement>/actions/attach_products`, puis `…/packages/<package>/actions/attach_products` (`docs/REVENUECAT_ENTITLEMENTS.md:144-160`). L'étape 1 réussit même si le produit n'existe pas encore côté store. |
| Commission 15 % Apple | **Déposé le 2026-09-09.** Reste à relever la date d'approbation : App Store Connect → **Business**, et le mail Apple de confirmation. Effet 15 jours après la fin du mois fiscal d'approbation |
| Commission 15 % Google | Rien à faire : automatique sur les abonnements auto-renouvelables |
| `review_blurb` sur `gpt-5-nano` | Secret `media-summarizer-runtime-<env>` : le générateur lit `os.environ.get("OPENAI_MODEL", …)` (`review_blurb.py:100-101`), donc un modèle par artefact demande d'abord de **rendre la famille `*_LLM_MODEL` réelle** — elle n'existe qu'en `.env.example` (`:20-23`). Sinon changer `OPENAI_MODEL` déplace **cinq** générateurs à la fois |
| `reasoning_effort` sur les deux appels | **Deux payloads, deux fichiers** : `transcript_translation.py:310-315` et `artifact_generator/worker.py:139-148`. Ajouter `"reasoning_effort": "minimal"` — le mot n'existe nulle part dans le dépôt aujourd'hui, donc les deux appels paient le réglage par défaut de la famille `gpt-5`, facturé au tarif de sortie |
| Mode LlamaParse | `llamaparse_resolver.py:191-194` : envoyer le mode **explicitement** dans la charge utile d'upload. Aujourd'hui l'absence de mode achète le défaut du fournisseur — mesuré à `cost_effective` / 3 crédits/page, publié nulle part, et modifiable sans qu'une ligne du dépôt change |
| Repli document | `parse_document_with_fallback` : supprimer la branche Unstructured ; câbler `spend_allowed` avant l'appel LlamaParse (`document_parsing/worker.py:253-259`) ; compter en **crédits**, pas en pages |
| Pools Apify | **Trois comptes FREE distincts** (§ 2.3), donc 15 $/mois de capacité réelle contre un compteur unique. Console Apify, par compte : **Settings → Billing** pour le plan et la limite d'usage ; **Settings → Integrations** pour le token. Le plafond de 50 transcripts/jour est côté **acteur**, pas côté compte |
| Pool Algolia | À créer dans `provider_pools` avec **deux** unités (requêtes/mois et records en stock) ; corriger `providers.search.plan: "build_free"` → le plan relevé est **Free** ; supprimer les deux index orphelins `transcripts` et `transcripts_user_4cd1abcb-…` dans **Search → Index** |

---

## Axe 1 — Compréhensibilité par un client naïf

### 1.1 Les noms de formule affichés ne sont ceux d'aucune locale — le champ traduit est mort deux fois

La config porte bien `name` **et** `name_fr` (`pricing_config_service.py:51-52, 62-63, 72-73`) et
l'API sert les deux (`pricing.py:99-100`). Mais **aucun consommateur ne lit `name_fr`** :

- `planCopy.ts:135` construit la carte avec `tier.name`, jamais `tier.name_fr` ;
- `subscriptionDisplay.ts:29-33` ré-encode les trois noms **en dur, en anglais** :
  `{S: "Reader", M: "Mix", L: "Audio-Heavy"}`, avec une docstring qui revendique le choix
  (« Deliberately **not** translated ») ;
- côté types, `name_fr` n'existe que dans l'interface `pricingService.ts:21` — **lu nulle part
  ailleurs dans `mobile/`** (grep exhaustif sur `mobile/src` et `mobile/app`).

Conséquence : les **11 locales** affichent « Reader », « Mix », « Audio-Heavy ». Ce n'est pas
l'arbitrage documenté (« un plan acheté comme *Reader* s'appelle *Reader* partout ») qui est en
cause — c'est qu'il est pris **deux fois, dans deux fichiers, dont un contredit la config**. Soit
`name_fr` disparaît de la config et de l'API, soit il est lu. Les deux à la fois est un défaut.

Sur le fond des noms : **« Reader » est trompeur maintenant.** L'identifiant interne est
`text_only` et le nom promet de la lecture, mais le tier porte depuis task-287 **60 minutes** —
exactement un podcast d'une heure. Un acheteur naïf lit « Reader / 60 min » et doit deviner que ces
minutes servent à de l'audio. En arabe (RTL) et en japonais/chinois (sans espaces) le problème
empire : un nom propre latin non traduit au milieu d'une phrase traduite ne porte aucun sens
lexical, alors que « Mix » est au moins arithmétiquement descriptif.

### 1.2 La minute est un jeton déguisé en durée, et l'écran le dit — à un endroit

Le test décisif, tel que posé : **3 h de YouTube = 1 minute ; 3 h de podcast = 180 minutes.** C'est
un rapport de **180×** sur la même durée perçue. La minute n'est donc pas une durée, c'est un
**jeton de budget fournisseur**, et son taux de change dépend de la plateforme d'origine.

Ce qui est à créditer : **l'app ne le cache pas.** `buildCostTable` (`planCopy.ts:546-616`) rend
sept lignes issues de `unit_conversion`, dont `plan.cost.captions.label` =
« **Une vidéo YouTube, quelle que soit sa durée** » face à `plan.cost.value.realLength` =
« Sa durée réelle » pour l'audio. La règle est écrite, en français, sans jargon, avec un chiffre.
C'est mieux que la plupart des produits à unité abstraite.

Ce qui reste un problème : **le tableau est sous les cartes, la carte porte « 720 min ».** La
dominante de l'écran est une durée ; la nuance qui la rend fausse d'un facteur 180 est plus bas.
Et surtout, **`buildHourlyRate` produit un prix à l'heure** (`planCopy.ts:104-115`,
`(prix × 60) / minutes` → 3,00 / 1,00 / 0,75 €/h) qui **renforce** la lecture « durée » alors que
la moitié des sources ne consomment pas de minutes du tout. Un tarif horaire sur une unité qui
n'est pas une durée est la formulation la plus trompeuse de l'écran.

Comment les produits grand public vendent une unité abstraite — références vérifiées :

| Produit | Unité vendue | Ce qu'il fait de bien |
|---|---|---|
| **Snipd** ($6.99/mois) | « AI processing (900min/month) » | Nomme la minute **et** la borne du gratuit en épisodes/semaine, donc en objets comptables par l'utilisateur |
| **Readwise** ($9.99/mois annuel, $12.99 mensuel) | **rien de compté** | Supprime le problème : aucune unité à comprendre |
| **Google One** (cité par task-376 §3.0) | « Standard (200 GB) » | La carte porte la quantité, ce qu'elle achète est dit **une fois, ailleurs** — c'est le modèle que `buildPlanCard` revendique suivre |

L'enseignement : le seul concurrent qui métrique **nomme aussi une seconde unité** que l'acheteur
sait compter (des épisodes). Ici il n'y en a qu'une, et son taux de change varie de 1 à 180.

### 1.3 Ce que l'acheteur naïf doit deviner

- **Que `text_only` à 3 € achète de l'audio.** 60 minutes = un podcast d'une heure, alors que
  l'identifiant interne dit « texte seulement » et le nom affiché dit « Reader ».
- **Qu'un article ne coûte rien.** C'est dit (`plan.minutesRule` : « Les articles et les pages web
  n'en coûtent aucune »), mais dans une règle, pas dans la dominante.
- **Que 720 minutes ne bornent pas la génération d'artefacts.** Rien ne le dit, et c'est vrai :
  les générations mono-item sont gratuites (`quota_enforcer.py:1033-1050` ne débite que
  `scope == "folder"`).
- **Quel plan correspond à sa consommation.** Il ne la connaît pas encore. Voir § Axe 4.4.

**Ce qu'il faut créditer, en contrepartie — et qui corrige une insuffisance de ma première lecture :
le paywall n'est pas muet, il est faux.** L'architecture de la copy fait déjà les trois bonnes
choses :

- une **table de coûts en langage humain**, pas en jargon : `plan.cost.free.label` « Articles, web
  pages, X posts », `plan.cost.duration.label` « Audio, video, reels, voice notes »,
  `plan.cost.document.label` « A document or a photo of a page ». Aucun de ces libellés ne dit
  « ingestion », « parsing » ni « artefact » ;
- un sélecteur cadré sur l'usage et non sur la mécanique : `paywall.selectorLabel` « Choose how much
  you send each month » ;
- une **recommandation calculée sur la consommation réelle**, avec cinq branches
  (`plan.rec.cappedNextUp`, `plan.rec.cappedLargest`, `plan.rec.overLargest`, `plan.rec.trialFloor`,
  `plan.rec.covering`) et un badge `plan.badge.recommended` « RECOMMENDED FOR YOU ».

Le défaut n'est donc pas un défaut de pédagogie, et la refonte n'a pas à refaire cette structure :
elle a à corriger ce qu'elle affirme. Deux libellés sont activement trompeurs —
`plan.cost.captions.label` « A YouTube video, **whatever its length** », qui vend comme un avantage
la ligne qui perd 8,5×, et `plan.cost.value.free` « Free » sur des chemins qui coûtent 0,0059 € au
minimum. Voir § R.5 pour le remplacement clé par clé.

### 1.4 Le mot « transcription » a bien disparu des surfaces de vente

Vérifié dans `mobile/src/i18n/fr.ts` : aucune occurrence sous `plan.*` ni `paywall.*`. Le mot ne
survit que dans les surfaces de **lecture** (`transcript.*`, `artifacts.refusal.folderEmpty`,
`mediaError.noTranscriptAvailable`), où il désigne un objet que l'utilisateur a sous les yeux — ce
qui est légitime. `minutesRule()` ne le nomme plus. **Ce point du brief est clos : le nettoyage a
été fait.**

### 1.5 Les refus disent quoi faire — sauf un

`quota_enforcer.py` ne produit aucune phrase : il renvoie des figures typées
(`QuotaCheckResult.params`) et deux codes seulement, `out_of_minutes` (403) et `item_too_long`
(413). Les phrases sont construites côté client (`quotaError.ts`), chaque branche a un repli sans
chiffre, et `quotaErrorOffersUpgrade` n'est vrai que pour `out_of_minutes` — donc on ne propose pas
un upgrade là où il ne résout rien. **C'est la bonne architecture** et les deux formulations
françaises sont actionnables (« Passez à une formule supérieure », « Découpez-le en parties plus
courtes »).

L'exception : **`quota.refusal.noPlan` = « Votre formule *a pris fin*. Abonnez-vous pour continuer
à enregistrer dans votre bibliothèque. »** Ce message part sur tout `has_plan: false`, donc aussi
sur un utilisateur qui **n'a jamais eu de formule** — à qui on annonce la fin de quelque chose
qu'il n'a jamais eu. Deux cas, deux phrases.

---

## Axe 2 — Pertinence du filet de sécurité

### 2.1 La thèse à tester

task-287 (`owner_decision: ok`, 2026-08-18) : *« le plafond de minutes est le filet de sécurité,
parce que chaque euro de coût variable débite le même compteur »*, et la config l'inscrit
(`pricing_config_service.py:44-47`) : « the worst case a subscriber can cost is
minutes × 0.00664 ».

**Cette thèse est fausse.** Cinq chemins débitent le compteur ; un seul le débite au bon taux.

| Chemin | Coût réel de l'unité | Ce que le compteur débite | Écart |
|---|---|---|---|
| Audio Deepgram batch | 0,003703 €/min (mono) | 0,00664 €/min | **0,56× — sur-débité** |
| YouTube 3 h (`captions_minutes: 1`) | 0,0106 € minimum → 0,0562 € tout demandé | 0,00664 € | **1,60× à 8,46×** |
| Document sous LlamaParse | 0,003225 €/page (3 crédits) | 0,001328 €/page | **2,4×** |
| Document, repli Unstructured | 0,012916 €/page | 0,001328 €/page | **9,7×** |
| Génération d'artefact mono-item | 0,0033 à 0,0038 €/appel | **0,00 €** | **∞** |

La ligne LlamaParse est nouvelle : elle était donnée excédentaire de 23 % dans la première version de
ce document, sur l'hypothèse d'un tarif à 1 crédit/page. Le relevé de consommation du 2026-09-09
donne le tarif réel — **3,000 crédits/page mesurés** sur 92 pages (§ 3.4). Le chemin documentaire
n'est **plus** le seul chemin non-audio correctement calibré : il n'y en a aucun.

### 2.2 Pire cas réellement autorisé, chemin par chemin

Les garde-fous de la couche 2 **ne refusent rien** : `_note_burst_guards`
(`quota_enforcer.py:802-858`) se contente d'émettre `quota.burst_guard_tripped` à la ligne 840.
task-287 §3.3 spécifiait une **mise en file** ; elle n'a pas été implémentée. Il n'y a donc **aucun
mur** en couche 2, et le plafond de minutes est le seul frein.

**a) 100 % YouTube.** Coût par vidéo de 3 h, transcript ~36 k tokens, item Apify à **$0.005** (tarif
de `starvibe~youtube-video-transcript`, l'acteur réellement configuré — cf. § 3.3). Deux régimes,
selon que l'utilisateur demande les cinq artefacts ou rien du tout :

| Formule | Vidéos/mois au plafond | Coût, rien demandé (0,0106 €) | Coût, tout demandé (0,0562 €) | Net 15 % | Résultat, tout demandé |
|---|---|---|---|---|---|
| Reader (60 min) | 60 | 0,64 € | 3,37 € | 2,125 € | **−1,25 € (−59 %)** |
| Mix (300 min) | 300 | 3,18 € | 16,85 € | 3,542 € | **−13,31 € (−376 %)** |
| Audio-Heavy (720 min) | 720 | 7,63 € | 40,43 € | 6,375 € | **−34,06 € (−534 %)** |

Atteignable : `items_per_day: 60` autorise 1 800 items/mois, très au-dessus de 720. Deux lectures :

- Au régime **« tout demandé »**, les trois tiers sont déficitaires, et le cache de prompt ne les
  sauve pas : **il vaut −7,6 % mesuré** sur les 90 générations de dev (§ R.6, point 3), là où il
  faudrait −376 % sur Mix. Il n'existe donc aucune colonne « cache maximal » planifiable, et celle que
  la première version de ce document présentait comme telle est retirée.
- Au régime **« rien demandé »**, Reader tient de justesse (+1,49 €), Mix de très peu (+0,36 €) et
  **Audio-Heavy est encore déficitaire** : 7,63 € de coût contre 6,375 € de net, soit **−1,26 €**
  pour un utilisateur qui ne consomme aucun artefact. C'est le résultat le plus dur de cette section,
  parce qu'il ne dépend d'aucune hypothèse sur le comportement : il suffit d'envoyer.

**b) 100 % documents.** Le plafond de minutes borne bien le *nombre* de pages (1 min / 5 pages), mais
au mauvais taux unitaire — et depuis l'obtention de la table de tarifs v1, **le chemin documentaire
est déficitaire avant même le repli** :

| Formule | Pages max/mois | Coût LlamaParse (3 cr/page) | Résultat sous LlamaParse | Coût Unstructured | Résultat sous Unstructured |
|---|---|---|---|---|---|
| Reader (net 2,125 €) | 300 | 0,97 € | **+1,16 €** | 3,87 € | **−1,75 €** |
| Mix (net 3,542 €) | 1 500 | 4,84 € | **−1,30 €** | 19,37 € | **−15,83 €** |
| Audio-Heavy (net 6,375 €) | 3 600 | 11,61 € | **−5,24 €** | 46,50 € | **−40,12 €** |

Les deux colonnes de coût ne comptent que l'acquisition : le plancher LLM par source s'y ajoute, donc
les deux déficits sont des minorants. Et l'épuisement du pool n'est plus une hypothèse d'échelle,
c'est une hypothèse d'**un seul utilisateur** : 10 000 crédits/mois à 3 crédits/page valent
**3 333 pages**, contre 3 600 pages au plafond documentaire d'Audio-Heavy. **Un abonné suffit à vider
le pool partagé.** Une fois vide, *tous* les utilisateurs basculent sur Unstructured jusqu'au cycle
suivant — et la dotation gratuite d'Unstructured est de 10 000 pages **une seule fois à la création
du compte**, pas un renouvellement mensuel ; ensuite c'est $0.015/page « no hard cutoff ».

Une atténuation, à porter au crédit du fournisseur : **re-parser le même fichier dans les 48 h est
gratuit** (cache de parse). Cela ne change rien au pire cas ci-dessus — des pages distinctes — mais
cela veut dire qu'un *retry* ou une reprise après échec ne coûte rien, donc qu'il ne faut pas les
chiffrer comme un coût.

**c) Le plancher LLM de chaque source, à zéro minute — et non les régénérations.** Correction d'une
affirmation antérieure de ce document : **un artefact n'est pas régénérable**. `build_artifact_id`
est un hash de (type, sources triées) **sans composante temporelle** (`artifact_service.py:13`), et
`:1146` renvoie l'existant dès qu'il n'est pas `FAILED`. Il n'existe aucun chemin de `force` ou
d'`overwrite`, seulement la reprise d'une entrée en échec. Les 1 500 générations/mois autorisées par
`generations_per_day: 50` ne peuvent donc pas venir d'un même média régénéré : il faut **300 sources
distinctes × 5 types**.

Le trou est ailleurs, et il est structurel : ces 300 sources peuvent toutes arriver par un chemin
qui débite **0 minute** (article, page web, post, note, fichier texte), et chacune porte quand même
un **plancher de 0,00592 €** — les tokens de *sortie* des six générateurs, indépendants de la
longueur. Au plafond réellement autorisé par `items_per_day: 60`, soit 1 800 sources/mois :

| Régime, 1 800 articles/mois à ~2 000 tokens | Coût mensuel des seuls chemins « gratuits » |
|---|---|
| Aucun artefact demandé (`review_blurb` seul) | **0,85 €** |
| Les cinq artefacts demandés sur chaque source | **13,21 €** |
| Idem, après bascule de `review_blurb` sur `gpt-5-nano` (§ R.6) | 12,59 € |

Contre un net de 2,125 € sur la formule la plus basse. Trois choses à en tirer, dans cet ordre :

1. **Au régime « tout demandé », le texte « gratuit » coûte 6,2× le net du premier palier.** C'est la
   preuve qu'aucune unité de *durée* ne peut porter ce coût, et c'est ce qui fonde le forfait de
   2 crédits par envoi en § R.2.
2. **Même au régime « rien demandé », il coûte 0,85 €**, soit 40 % du net d'un palier qui doit en
   plus payer sa part des 38,10 € de charge fixe. La borne inférieure n'est pas zéro.
3. La première version de ce document donnait 15,31 € / 12,38 € / 10,99 € en faisant varier le cache
   et la traduction. Les deux dernières lignes n'étaient pas exploitables : le cache est borné à une
   rafale (§ R.6) et la traduction était **déjà** conditionnelle. Le levier réel est ailleurs — c'est
   le modèle de `review_blurb`, seul appel que 100 % des sources paient.

Aucun garde-fou n'intervient dans aucun de ces régimes : le compteur ne bouge pas et le burst guard
ne fait que journaliser.

**Ce que le plafond protège réellement :** le seul chemin Deepgram. Un podcast de 3 h débite
1,1952 € et coûte 0,7179 € (0,8574 € en multilingue) — marge **+0,4773 €**. C'est le chemin sur
lequel 0,00664 € a été calibré, et il est confortable **précisément parce que le chiffre est 1,79×
trop élevé**.

### 2.3 Les pools partagés n'ont pas d'alarme, et l'un est bloquant

Le garde-fou de couche 3 revendique (`provider_pool_guard.py:13-15`) qu'au seuil il émet
`provider_pool.threshold_reached`, « which is what a CloudWatch alarm watches so the owner can
upgrade the plan ». **Cette alarme n'existe pas.** Un grep de `infrastructure/` sur
`provider_pool|burst_guard|threshold_reached` ne renvoie rien, et `enable_alarms = false` sur les
**trois** environnements (`envs/dev/main.tf:58`, `envs/staging/main.tf:86-88`,
`envs/prod/main.tf`) — donc le topic SNS et l'abonnement e-mail sont `count = 0`
(`pipeline_alerts.tf:16-33`) et **n'existent pas**. Sur un projet dont le canal d'alerte est le
mail, la promesse est non tenue deux fois.

Pire, la nature du plan Apify n'est pas celle que la config déclare. Apify **Free** = **$5/mois
inclus** et à épuisement « you'll be blocked until the next billing cycle » : ce n'est pas un pool
à surveiller, c'est un **mur dur** qui coupe YouTube, Instagram et le repli TikTok **pour tous les
utilisateurs**. Sur un plan payant au contraire l'overage est facturé automatiquement, sans
plafond sauf limite configurée dans la facturation — c'est là qu'est l'exposition non bornée.

**Et le pool n'a pas la forme que le code lui donne.** Relevé en lecture seule sur l'API Apify le
2026-09-09 (`GET /v2/users/me`, `GET /v2/users/me/limits`) : il y a **trois comptes Apify FREE
distincts**, un par plateforme — `nurturing_zeta` pour YouTube, `rapturous_mantis` pour TikTok,
`kneaded_goodness` pour Instagram. Trois conséquences que `provider_pool_guard` ne modélise pas :

- **La capacité réelle est de 15 $/mois, pas 5.** Le docstring du garde-fou (`:4-8`) raisonne sur
  *un* crédit de $5, et il n'existe qu'**un seul compteur `apify_results`** (`:35-42`) pour les trois
  comptes. Un pool unique au-dessus de trois budgets séparés se trompe forcément : il bloque YouTube
  parce qu'Instagram a consommé, ou il laisse passer parce qu'il croit avoir de la marge sur un
  compte qui n'est pas celui qu'on va appeler.
- **L'unité est intenable.** `capacity_unit: "results"` avec `monthly_capacity: 1160` suppose un prix
  par résultat unique. Les trois plateformes ont trois acteurs, donc trois prix. Un compteur de
  résultats ne se convertit pas en dollars sans savoir *lequel* des trois on a débité.
- **1 160 est faux même pour YouTube seul.** L'acteur configuré est facturé **$5.00/1 000 résultats**
  (§ 3.3), donc $5 achètent exactement **1 000** vidéos, pas 1 160.

**Un quatrième plafond n'est modélisé nulle part** : l'acteur YouTube porte, sur le plan gratuit
d'Apify, une limite propre de **50 transcripts par jour**. Or `burst_guards.items_per_day: 60`
autorise **un seul utilisateur** à dépasser cette limite à lui tout seul. Le refus viendra donc du
fournisseur, pas du produit — et sous la forme d'un échec d'ingestion, pas d'un message de quota.
Sur le mois, le crédit de $5 mord avant (1 000 vidéos contre 1 500 autorisées par 50/jour), mais
c'est le plafond journalier qui casse en premier une journée chargée.

Enfin, **task-287 chiffre « Apify Starter 29,00 USD » dans le plancher fixe alors que la config
déclare `plan: "free"`** — l'un des deux est faux, et Starter est aujourd'hui à **$19/mois**.

**Et il manque un pool entier : Algolia.** `provider_pools` déclare Apify et LlamaParse
(`provider_pool_guard.py:35-42`), pas Algolia, alors que c'est le troisième fournisseur à quota
partagé du pipeline et le seul dont l'épuisement ne coûte pas de l'argent mais **casse une
fonctionnalité**. Il a de plus la particularité d'avoir **deux compteurs de natures différentes** —
un flux mensuel de requêtes, un **stock** cumulatif de records — dont aucun ne se remet à zéro de la
même façon. Détail et mesures en § 3.6.

### 2.4 La commission de 15 % : automatique chez Google, sur candidature chez Apple

> **État au 2026-09-09** : la candidature au Small Business Program **a été déposée** par l'owner, et
> la consigne est de traiter la réduction comme acquise dans tous les calculs de ce document. Ce qui
> suit reste vrai comme description du mécanisme et de son calendrier — c'est le calendrier qui
> importe désormais, pas l'éligibilité.

- **Google Play** : « 15% for automatically renewing subscription products purchased by
  subscribers », « regardless of revenue earned by the developer each year ». Et pour l'EEE/UK/US
  à partir du 30 juin 2026 : abonnements auto-renouvelables à « 10% + 5% billing fee » — soit
  **15 % net, même résultat**. Rien à faire.
- **App Store** : 15 % **seulement via le Small Business Program**, qui n'est pas automatique. Il
  faut être *Account Holder*, accepter le dernier *Paid Apps agreement* dans App Store Connect,
  déclarer les *Associated Developer Accounts*, puis attendre l'approbation ; l'effet est
  « fifteen (15) days after the end of the fiscal calendar month in which your enrollment is
  approved ». Seuil : 1 M USD de **proceeds** (net de commission), année civile précédente **et**
  année en cours ; au-dessus, le taux standard s'applique « to future sales » ; en dessous à
  nouveau, requalification « the year after ». Bonus applicable ici : pour les *alternative terms*
  UE et les abonnements **après leur première année**, Apple annonce 10 %.

Chemin exact, tel qu'il est libellé aujourd'hui :
**developer.apple.com → App Store → Small Business Program → « Get started today. » → « Enroll
now »** (fait le 2026-09-09), et vérification du prérequis dans **App Store Connect → Business →
Contrats** → *Contrat relatif aux applications payantes* — l'ancien libellé « Agreements, Tax, and
Banking » n'existe plus dans l'UI d'aujourd'hui.

Impact tant que l'approbation n'est pas effective : **−17,6 % sur les nets**, soit 2,917 € au lieu de
3,542 € sur Standard et 5,250 € au lieu de 6,375 € sur Intensif. La grille de § R.3 reste
bénéficiaire au plafond dans cet intervalle (+1,117 € et +1,650 €), ce qui est précisément le test
qu'aucune des trois formules actuelles ne passe.

### 2.5 Les 20 % de TVA sont un chiffre français, pas un net

`revenue_model.tva_pct: 20.0` et le nom `revenue_net_eur` masquent que le montant dépend du marché
de l'acheteur. Le prix TTC est fixé par palier de store et **ne change pas** d'un pays à l'autre en
zone euro : c'est la TVA qui varie, donc le net varie avec elle. Recalcul à 15 % de commission,
prix TTC identiques :

| Marché | Taux | Net Reader | Net Mix | Net Audio-Heavy |
|---|---|---|---|---|
| France | 20 % | 2,125 € | 3,542 € | 6,375 € |
| Allemagne | 19 % | 2,143 € | 3,571 € | 6,429 € |
| Irlande | 23 % | 2,073 € | 3,455 € | 6,220 € |
| Hongrie | 27 % | 2,008 € | 3,346 € | 6,024 € |

L'amplitude est faible (±3 %) et ne change aucune conclusion : **le problème n'est pas la TVA,
c'est la commission et le taux de change de la minute.** Mais `revenue_net_eur` doit être renommé
ou documenté comme « net France » — un chiffre stocké sous un nom faux finit copié.

*Taux de TVA non vérifiés en source primaire cette session ; voir § Ce que je n'ai pas pu vérifier.*

### 2.6 L'essai gratuit : à quel taux de conversion est-il rentable ?

Un essai = 30 jours, tier `mix`, 300 minutes, budget fournisseur **non récupérable**, une seule
fenêtre par inscription (`free_trial`, task-300). Coût maximal d'un essai selon l'usage :

| Usage de l'essai | Coût du budget fournisseur |
|---|---|
| 300 min d'audio Deepgram batch | 1,11 € (+ 0,05 € de LLM) ≈ **1,16 €** |
| 300 vidéos YouTube de 3 h | **16,71 €** (sans cache) |
| 1 500 pages sous LlamaParse (3 crédits/page mesurés, § 3.4) | **4,84 €** |
| 1 500 pages sous Unstructured | **19,37 €** |

Rentabilité, si un converti reste 12 mois sur Mix (3,542 €/mois = 42,50 € de net) :
avec un essai « audio » à 1,16 €, il faut convertir **1 essai sur 37** ; avec un essai
« YouTube » à 16,71 €, **1 sur 3**. Le taux de conversion requis varie donc d'un facteur 14 selon
ce que l'essayeur importe — ce qui est la même faille qu'en 2.2, appliquée à l'acquisition. **Tant
que le taux de change de la minute n'est pas corrigé, aucun taux de conversion cible n'est
calculable**, et c'est le vrai argument contre l'essai à 300 minutes.

Le tier moyen est-il le bon compromis ? Non, pour une raison indépendante : offrir `mix` en essai
puis proposer `text_only` à 3 € demande à l'utilisateur d'**accepter une division par 5 de son
allocation** au moment de payer. Snipd résout ça avec un **palier gratuit permanent, faible et
compté en objets** (2 épisodes/semaine) qui n'établit jamais une référence haute. C'est la
structure à copier — pas l'essai généreux.

### 2.7 L'absence de produit annuel

Neuf produits, tous mensuels (`docs/REVENUECAT_ENTITLEMENTS.md:33-43`), et la scaffolding
`$rc_annual` a été **supprimée** par task-262 (`:223-242`, « There is no yearly tier »). Ce que
cette absence coûte, avec les chiffres du seul comparable dont je dispose : Readwise vend
$9.99/mois en annuel contre **$12.99 en mensuel**, soit « Save 24 % », et vante « lock in your
price for life ». Autrement dit un concurrent accepte de **céder 24 %** pour obtenir 12 mois
d'avance — ce qui achète trois choses qui manquent ici : de la trésorerie avant le premier mois de
coûts fournisseurs, la suppression du churn mensuel, et **une commission Apple réduite à 10 %
après la première année** sur les *alternative terms* UE, qui ne se déclenche jamais si personne ne
reste 12 mois sur le même produit.

Ajouter un annuel est **un produit + un package attaché à une entitlement existante**, sans code
ni déploiement (`docs/REVENUECAT_ENTITLEMENTS.md:144-162, 241-242`). Le coût de l'absence est donc
entièrement un coût d'opportunité, et il est mesurable dès le premier abonné.

### 2.8 Le prix absolu 3 / 5 / 9 €, et « 3 € × N » pour un développeur seul

| Produit | Prix | Ce qu'il donne | Palier gratuit |
|---|---|---|---|
| **Second Brain** Audio-Heavy | 9,00 € TTC | 720 min/mois | Essai 30 j |
| **Snipd** Premium | $6.99 ≈ 6,02 € | **900 min/mois** + IA illimitée sur 1 M+ épisodes + import YouTube + chat | **Permanent** (2 épisodes/sem.) |
| **Readwise** (avec Reader) | $12.99 mensuel / $9.99 annuel | Illimité, non métré | Aucun (essai 30 j) |

Le tier haut est donc **plus cher et moins généreux qu'un concurrent direct**, et le tier bas à
3 € est en dessous de tout le marché comparé. Pour un développeur seul, « 3 € × N » est le mauvais
modèle pour une raison arithmétique déjà démontrée par task-287 §1.6 : le **plancher fixe** domine.
Avec un plancher mesuré de 31,91 €/mois (AWS 6,90 € + Apify 25,01 €) il faut ~15 abonnés Reader
pour couvrir les seuls frais fixes — et ce plancher est **dev seul**, `envs/prod/main.tf` chiffrant
~$7,20/mois d'observabilité prod à rallumer « as a prerequisite of taking the first paying user ».
Le paramètre qui décide de la viabilité n'est pas le prix, c'est le **nombre d'abonnés au-dessus du
plancher** — et le tier à 3 € est celui qui met le plus de temps à l'atteindre.

---

## Axe 3 — Pertinence des entrées de coût

Chaque chiffre de `DEFAULT_PRICING_CONFIG` confronté au tarif public d'aujourd'hui.

### 3.1 `cost_per_minute_eur: 0.00664` — mauvais produit, 1,79× trop haut

La config source son chiffre ainsi (`pricing_config_service.py:153-157`) : « Deepgram Nova-3
pay-as-you-go at $0.0077/min, converted at 0.86 EUR/USD ». La page tarifaire d'aujourd'hui donne :

| Ligne de produit nova-3 | PAYG | Growth |
|---|---|---|
| Pre-recorded (batch) **monolingue** | **$0.0043/min** | $0.0036/min |
| Pre-recorded (batch) **multilingue** | **$0.0052/min** | $0.0043/min |
| Streaming monolingue | promo **$0.0048** / régulier **$0.0077** | — |

Le chemin utilisé est le batch : `deepgram_worker.py:192-203` et `:402-413` font un `POST` sur
`https://api.deepgram.com/v1/listen` avec des paramètres de requête, jamais un WebSocket.
**$0.0077/min est le tarif streaming régulier** — la config a sourcé la mauvaise ligne du même
tableau. Au taux BCE d'hier :

- monolingue : $0.0043 × 0,8611 = **0,003703 €/min** → la config est **1,79× trop haute** ;
- multilingue : $0.0052 × 0,8611 = **0,004478 €/min** → **1,48× trop haute**.

Le worker envoie `detect_language=true` par défaut (`deepgram_worker.py:85, 122`) ; je n'ai pas pu
vérifier si Deepgram facture cette option au tarif multilingue. La fourchette honnête est donc
**0,0037–0,0045 €/min**, et 0,00664 est faux dans les deux cas. Diarisation : « Included » en
pre-recorded, et `DEEPGRAM_DIARIZE` est à `false` de toute façon. Unité de facturation et
arrondi : la page a une FAQ « Does Deepgram charge for silence or round up audio time? » **sans
réponse visible** — non vérifiable.

Conséquence pour les plafonds : à 0,003703 €/min, le pire cas *audio* d'Audio-Heavy est
720 × 0,003703 = **2,67 €** sur 6,375 € de net, soit 42 % — et non les 94 % que le commentaire de
`pricing_config_service.py:76-77` invoque pour justifier 720 au lieu de 900. **À 900 minutes le
pire cas audio serait de 3,33 €, soit 52 % du net.** Le raisonnement qui a produit 720 s'appuie sur
un chiffre 1,79× trop haut ; la contrainte réelle sur `audio_heavy` n'est pas l'audio.

### 3.2 Les modèles LLM déclarés : deux justes, un faux, deux manquants

Tarifs vérifiés aujourd'hui, USD / 1 M de tokens :

| Modèle | Input | Cached input | Output | Existe ? |
|---|---|---|---|---|
| `gpt-5-nano` | $0.05 | $0.005 | $0.40 | oui — **conforme à `llm_pricing.py:22-25`** |
| `gpt-5.4-nano` | $0.20 | $0.02 | $1.25 | oui — **conforme** |
| `gpt-4o-mini` | $0.15 | $0.075 | $0.60 | oui — **absent de `_MODEL_PRICES`** |

Trois écarts entre la config et le code exécuté :

1. **`notes_model` déclare la bonne valeur pour la mauvaise raison, et le danger est ailleurs que je
   ne l'ai d'abord écrit.** La config déclare `gpt-5.4-nano` (`pricing_config_service.py:163`) et
   `generators/notes.py:102` porte le défaut en dur **`gpt-4o-mini-2024-07-18`** (docstring `:3`),
   seul générateur à diverger. J'en avais conclu que les notes tournaient sur `gpt-4o-mini` et
   payaient un cached input 3,75× sous-évalué. **C'est faux, et la facture le réfute** : aucune ligne
   `gpt-4o-mini` sur trois mois. La résolution effective, vérifiée en console le 2026-09-09, est que
   le secret runtime `media-summarizer-runtime-dev` porte `OPENAI_MODEL = gpt-5.4-nano-2026-03-17` —
   la Lambda `artifact_generator-dev`, elle, ne définit aucune variable de modèle sur ses 51 entrées.
   Le défaut divergent est donc **masqué**, pas actif. Ce qui reste vrai et vaut la correction 13 :
   `gpt-4o-mini` n'étant pas dans `_MODEL_PRICES`, `_prices_for` retomberait sur `_FALLBACK_PRICE`
   (`llm_pricing.py:26`), et le jour où quelqu'un retire `OPENAI_MODEL` du secret, `notes` part seul
   sur un autre modèle avec un coût mal attribué. La réponse est de supprimer le défaut divergent,
   pas de provisionner le tarif d'un modèle que rien n'appelle.
2. **Deux appels LLM n'apparaissent nulle part dans la config, et ce sont les deux seuls qui ne
   demandent l'avis de personne.** Le sixième artefact `review_blurb`
   (`generators/review_blurb.py:100-101`, `gpt-5.4-nano-2026-03-17`) est déclenché **à chaque
   ingestion** par `media_completed_worker._trigger_review_blurb` (`:110-142`), une fois pour le
   soumetteur canonique (`:293-296`) **et une fois par observateur** du média (`:372-377`) ; c'est
   **le seul appel LLM systématique du pipeline**. La **traduction du transcript**
   (`transcript_translation.py:73-75`, `gpt-5-nano-2025-08-07`) est **conditionnelle** : le module
   énonce lui-même qu'il ne traduit *« only when `detected_language` differs from the user's
   `reading_language` »* (`:1-31`), après un `langdetect` local et gratuit. `providers.llm` n'en cite
   aucun des deux, et ne cite pas non plus `quiz_model`. Un modèle de coût qui ne nomme pas le seul
   appel que 100 % des sources paient ne peut pas être juste.
3. **`providers.llm` n'est lu par personne.** Aucun consommateur : les générateurs lisent
   `os.environ.get("OPENAI_MODEL", "<défaut en dur>")`. Les quatre clés sont de la config
   décorative, ce qui explique qu'elles aient pu dériver sans que rien ne casse.

**Coût réel par artefact sur un média *typique* (3 h, ~36 k tokens de transcript)** — c'est le
chiffre que le brief demande, et il n'existe nulle part dans le dépôt :

| Appel | Modèle réel | Régime | Coût |
|---|---|---|---|
| `review_blurb` | `gpt-5.4-nano` | **systématique** | 0,006306 € |
| traduction du transcript | `gpt-5-nano` | conditionnel (langue ≠ lecture) | **0,013897 €** |
| `summary_short` | `gpt-5-nano` | à la demande | 0,001682 € |
| `summary_detailed` | `gpt-5.4-nano` | à la demande | 0,007467 € |
| `notes` | `gpt-5.4-nano` (défaut en dur `gpt-4o-mini`, cf. ci-dessus) | à la demande | 0,007789 € |
| `flashcards` | `gpt-5.4-nano` | à la demande | 0,007252 € |
| `quiz` | `gpt-5.4-nano` | à la demande | 0,007467 € |
| **Total, les sept** | | | **0,051858 €** |
| **Total des seuls appels non demandés** | | | **0,020203 €** |

La traduction est **l'appel le plus cher du pipeline**, parce que sa sortie est le transcript
entier ($0.40/1M en output) sans découpage (`transcript_translation.py:296`). Aucun document du dépôt
ne le chiffre. Mais **elle ne part pas toujours**, et l'appel qui part toujours est `review_blurb` —
c'est lui le levier, cf. § R.6.

Ces sept lignes sont des **estimations**, bornées par les contraintes de prompt. Le tableau
**mesuré** — 90 générations réelles, avec leurs tokens d'entrée, de sortie et cachés — est en § R.6,
et il déplace une conclusion : sur les artefacts de dev, **46 % du coût est de la sortie**, jusqu'à
92 % pour `summary_short`. Le modèle ci-dessus suppose des sorties courtes ; le mesuré montre qu'elles
ne le sont pas, parce que le raisonnement y est compté.

Une réserve levée, une réserve renforcée, une réserve intacte :

- **Le TTL du cache de prompt est connu, et son effet réel est maintenant mesuré.** Relevé owner du
  2026-09-09 : sur `gpt-5.4-nano` et `gpt-4o-mini` le cache est `in_memory`, ~5–10 min d'inactivité,
  **1 h au maximum**, et **aucun des deux** n'est dans la liste des modèles à rétention étendue 24 h —
  `gpt-5.4` y figure, `gpt-5.4-nano` et `gpt-5.4-mini` non, ce sont des modèles distincts. Sur les
  90 générations de `media_artifacts-dev`, le gain effectif est de **−7,6 %** (§ R.6, point 3). La
  colonne « cache maximal » que ce document affichait est supprimée. Corollaire pour le point 1
  ci-dessus : la sous-évaluation de 3,75× du cached input de `gpt-4o-mini` **ne coûte rien du tout**.
  Non parce que le cache touche peu, mais parce que **`gpt-4o-mini` n'est jamais appelé** — il
  n'apparaît sur aucune ligne de la facture des trois derniers mois. C'est du code mort, pas une
  erreur de tarif : il se supprime (correction 13), il ne se provisionne pas.
- **`reasoning_effort` n'est envoyé sur aucun des deux appels** — le mot n'existe nulle part dans le
  dépôt. Les deux modèles étant des modèles de raisonnement, les tokens de raisonnement sont produits
  au réglage par défaut et **facturés au tarif de sortie**. C'est ce qui explique que le tableau
  ci-dessus sous-estime les artefacts à sortie structurée, et c'est le levier de la correction 3c.
- **L'uplift régional n'est pas appliqué, et c'est maintenant établi par la facture.** La page
  signale « a 10% uplift for models released on or after March 5, 2026 » sur les endpoints régionaux,
  et `gpt-5.4-nano-2026-03-17` serait concerné. L'export `/v1/organization/costs` du 2026-06-01 au
  2026-09-09 permet de reconstruire le tarif réellement appliqué par `amount / quantity` sur chacune
  des six lignes facturées : $0,20 / $0,02 / $1,25 sur `gpt-5.4-nano` et $0,05 / $0,005 / $0,40 sur
  `gpt-5-nano` — **les six tarifs de `_MODEL_PRICES` au centime près, aucune majoration**. La
  troisième réserve tombe donc, et avec elle la question 7. Ce qui reste vrai : le jour où un endpoint
  régional serait câblé, l'uplift s'appliquerait sans qu'aucune ligne du dépôt ne change, et le seul
  détecteur serait ce même recalcul `amount / quantity`.
- **La facture valide aussi le calcul, pas seulement les tarifs.** Le `cost_eur` journalisé sur les
  90 générations (0,110110 €) recalculé depuis les tarifs facturés donne 0,110114 €, soit
  **+0,0037 %** — un écart d'arrondi. `estimate_llm_cost_eur` déduit correctement le cached input.
  Ce qu'il ne fait pas : **`ArtifactLlmUsage` ne persiste pas le modèle** (`media_artifact.py:127-133`,
  quatre champs : `prompt_tokens`, `cached_tokens`, `completion_tokens`, `cost_eur`). L'attribution
  d'un coût à un modèle passe donc par une déduction depuis `artifact_type`, et deviendra impossible
  sur l'historique le jour où un `*_LLM_MODEL` sera positionné. Correction 3d ci-dessous.

### 3.3 Apify : mauvaise unité, trois comptes pour un compteur, et un acteur qui n'est pas celui qu'on croit

**Quel acteur tourne réellement, et à quel prix.** Question restée ouverte dans la première version
de ce document, tranchée par vérification directe le 2026-09-09 :

- Le secret `media-summarizer-runtime-dev` porte
  `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = starvibe~youtube-video-transcript`.
- Les **11** jobs YouTube de `processing_jobs-dev` qui enregistrent un identifiant d'acteur ont tous
  tourné sur `starvibe`, le plus récent le **2026-09-06**.
- L'acteur `scrape-creators~best-youtube-transcripts-scraper` est bien **supporté** par le code
  (`youtube_ingestion_worker.py:29-55`, dialecte `videoUrls` / `transcript_only_text`,
  `supports_language: False`) mais **n'est configuré nulle part**. L'acteur `scrape-creators` qui
  *est* configuré est celui de **TikTok**.

Donc le tarif à retenir est celui de `starvibe` : **$5.00 / 1 000 résultats = 0,004300 €/vidéo**, et
`_parse_apify_transcript` ne lit que `items[0]` (`:409-466`) — **un résultat par vidéo**, jamais plus.
C'est bien ce que chiffrait task-287 (`README.md:91,155`), et c'est aussi ce qui rend la ligne YouTube
du barème de § R.2 juste sans retouche.

**L'arbitrage d'acteur, chiffré.** `scrape-creators` est cinq fois moins cher au résultat
(**$1.00/1 000 = 0,000860 €**), soit 0,003440 € d'économie par vidéo. Mais il déclare
`supports_language: False`, donc il ne peut pas choisir la piste de sous-titres et task-192 fait
traduire en aval (`:33-37`, `:481-491`) — une traduction qui coûte **0,004983 € sur une vidéo d'1 h**
et 0,013897 € sur 3 h. **L'acteur « cinq fois moins cher » est donc plus cher dès qu'il force une
traduction** : `starvibe` se rembourse s'il l'évite plus de ~72 % du temps sur des vidéos d'1 h, et
bien plus souvent encore sur des vidéos longues. Conclusion : garder `starvibe`, et ne pas présenter
l'écart de prix par résultat comme une économie.

**Le reste des faits Apify, inchangés ou corrigés :**

- Plans réels : Free **$0 / $5 inclus**, Starter **$19**, Scale **$199**, Business **$999** (−10 %
  en annuel). Le crédit inclus **n'est pas reportable** : « unused usage credits … expire at the end
  of the billing cycle ».
- **La nature du crédit** est un montant en dollars de « platform usage », pas un nombre de
  résultats. L'acteur est *pay-per-result*, l'usage plateforme est inclus dans le prix au résultat, et
  ses données sont retenues 7 jours (`dataRetentionDays: 7`) — donc rien à payer côté stockage.
  `monthly_capacity: 1160` reste faux : à $5.00/1 000, $5 achètent **1 000** vidéos.
- **Trois comptes FREE, un seul compteur** (§ 2.3) : `nurturing_zeta` (YouTube), `rapturous_mantis`
  (TikTok), `kneaded_goodness` (Instagram). Capacité réelle **$15/mois**, répartie en trois budgets
  étanches que `apify_results` agrège en un seul nombre.
- **Un plafond d'acteur non modélisé** : **50 transcripts/jour** sur le plan gratuit, quand
  `burst_guards.items_per_day: 60` autorise un utilisateur seul à le dépasser.
- **Coût marginal au-delà** : sur un plan payant, « the excess usage will be added to your next
  invoice » sans changement de plan, plafonné seulement par « the usage limit configured in the
  billing ». Sur le plan gratuit, **blocage** jusqu'au cycle suivant.
- **Contradiction interne à trancher** : la config déclare `plan: "free"` ; task-287 §1.6 chiffre
  « Apify Starter 29.00 USD » dans le plancher fixe réel. Les deux ne peuvent pas être vrais, et
  Starter est à $19 aujourd'hui, pas $29.
- Par-plateforme : la facturation est **par résultat** sur YouTube (transcript) et Instagram
  (`resultsLimit: 1`), et sur TikTok l'appel Apify n'a lieu **qu'en repli d'un blocage IP**. Aucun
  acteur du pipeline n'est facturé à la durée. Le sens de la conversion `captions_minutes: 1` (un item
  = un frais forfaitaire) est donc juste ; c'est sa **valeur** qui est fausse.

**Apify est-il le premier poste ? Non — il est le deuxième, et il ne devient premier que dans un cas.**
Décomposition d'une vidéo d'1 h (12 875 tokens de transcript) dont l'utilisateur **ne demande aucun
artefact**, donc le régime minimal du produit. La ligne Algolia est un loyer mensuel, pas un coût
d'acquisition ; elle est comptée ici au premier mois pour donner l'ordre de grandeur :

| Poste | Coût | Part | Coût si les sous-titres sont déjà dans la langue de lecture |
|---|---|---|---|
| traduction du transcript (`gpt-5-nano`) | 0,004983 € | **40,6 %** | — |
| **Apify** (`starvibe`, 1 résultat) | 0,004300 € | **35,0 %** | 0,004300 € — **59,0 %** |
| `review_blurb` (`gpt-5.4-nano`) | 0,002344 € | 19,1 % | 0,002344 € — 32,2 % |
| Algolia (1,87 records, § 3.6) | 0,000643 € | 5,2 % | 0,000643 € — 8,8 % |
| **Total** | **0,012269 €** | | **0,007287 €** |
| Couvert par les 0,00664 € débités | | **54 %** | **91 %** |

Le LLM pèse 0,007326 €, soit **1,70× Apify**. Apify ne passe premier que lorsque la traduction ne
part pas — c'est-à-dire quand la langue des sous-titres coïncide avec `reading_language` — et dans ce
cas la vidéo est presque à l'équilibre (91 % couvert). **Le poste principal est le LLM, pas Apify**, et
c'est exactement pourquoi facturer une durée forfaitaire ne peut pas marcher : le terme dominant est
proportionnel à la longueur du transcript, celui qu'un forfait ignore.

### 3.4 LlamaParse : crédits ≠ pages, et le tarif réel est 2,4× le budget de la page

La table de tarifs par mode a été fournie par l'owner le 2026-09-09
(`.claude/skills/llamaparse-pricing/references/pricing.md`) ; elle est **aussi en ligne**, à une URL
que ce document donnait pour morte : https://developers.llamaindex.ai/llamaparse/general/pricing.
Les deux concordent. Mais aucune des deux ne publie le **défaut du mode v1**, qui est le seul chiffre
dont dépend l'arithmétique de cette section. Il a donc été **mesuré**, le 2026-09-09, sur la
consommation réelle de l'organisation LlamaCloud du dépôt.

- Free **10 000 crédits/mois**, Starter **$50/mois** (40 K crédits), Pro $500 (400 K). Prix du
  crédit : **1 000 crédits = $1.25** en Amérique du Nord **comme** en Europe, soit
  **0,001076 €/crédit**. Pas de prime régionale.
- **Le repo appelle l'API v1**, pas v2: `llamaparse_resolver.py:36` pointe sur
  `https://api.cloud.llamaindex.ai/api/parsing`. C'est donc la table **v1 (modes)** qui s'applique,
  pas la table v2 (tiers). Confirmé job par job : `api_version = "v1"` dans les paramètres résolus.
- **L'upload n'envoie aucun mode** (`:191-194` : uniquement `result_type: markdown` et
  `language: en`) — vérifié côté fournisseur et non plus seulement dans le code :
  `GET /api/v1/parsing/job/{id}/parameters` sur deux jobs récents rend **17 champs non nuls sur 140**,
  et `parse_mode`, `tier`, `premium_mode`, `fast_mode` n'en font pas partie.
- **Ce défaut est facturé 3,000 crédits/page.** Exactement, pas en moyenne : **92 pages
  documentaires, 276 crédits, 28 jobs**, du 2026-06-09 au 2026-09-06. Les `properties` de chaque
  métrique nomment le mode appliqué — `parse_page_with_llm` (`model: openai-gpt-4o-mini`) jusqu'au
  2026-08-14, puis `tier: cost_effective` à partir du 2026-08-29. **Même prix des deux côtés de la
  bascule** : le fournisseur a renommé sa nomenclature de facturation, pas son barème.

| Tarif v1 | € / page | Couverture des 0,001328 € débités | Ce que `monthly_capacity: 10000` achète vraiment |
|---|---|---|---|
| **3 crédits — `cost_effective`, le défaut mesuré** | **0,003225** | **41 %** (coût = 2,4× le débit) | **3 333 pages** |
| 10 crédits — Agentic | 0,010764 | 12 % | 1 000 pages |
| 45 crédits — Agentic Plus / Layout Agent | 0,048437 | 3 % | 222 pages |

Le tarif à 1 crédit (« Parse without AI ») ne figure pas dans cette table : il « outputs spatial text
only — **no markdown** », le dépôt demande du markdown, et la mesure confirme qu'il n'est pas celui
qui est appliqué. Les deux lignes au-dessus de 3 crédits, elles, restent utiles : ce sont les prix
qu'achèterait la correction 2b si elle envoyait un autre mode que le défaut actuel.

Quatre conséquences, par ordre de coût si on les ignore :

1. **Le « seul chemin non-audio correctement calibré, +23 % de marge » n'existe pas.** Cette
   affirmation de la première version de ce document ne tenait qu'au tarif de 1 crédit. Elle est
   maintenant réfutée par la mesure, pas seulement par déduction : le chemin documentaire est
   **sous-facturé 2,4×**.
2. **`capacity_unit: "pages"` est la mauvaise unité** (`pricing_config_service.py:140-146`). Le
   fournisseur compte des crédits, le garde-fou compte des pages
   (`provider_pool_guard.record_spend(..., units=pages)` depuis `document_parsing/worker.py:253-260`).
   À 3 crédits/page le pool croit avoir dépensé **le tiers** de ce qu'il a dépensé : `alarm_pct: 60`
   se déclenche après l'épuisement réel et `stop_pct: 90` jamais.
3. **`stop_pct` est de toute façon du code mort.** Ce même bloc appelle `record_spend` et **jamais**
   `spend_allowed` — vérifié, `spend_allowed` n'apparaît nulle part dans
   `workers/document_parsing/worker.py`, alors que `apify_adapter.py:212-214` le câble correctement
   pour Apify. Le 402 d'épuisement est donc traité comme n'importe quel `ParseError` et **bascule sur
   Unstructured** à 9,7× le débit. L'épuisement arrivant 3× plus tôt que la config ne le croit, ce
   repli n'est pas un incident : c'est le **régime normal** après la 3 333ᵉ page du mois.
4. **Le stockage retenu est un poste à zéro — mesuré, plus supposé.** Le barème existe bien
   (**100 crédits/GB/jour**, 0,1 crédit/MB/jour, snapshot quotidien du stock retenu de chaque projet)
   et l'upload de ce dépôt n'envoie ni expiration ni durée de rétention — il ne *peut* pas : les
   **115 champs** du corps de `POST /api/v1/parsing/upload` (schéma OpenAPI) n'en comportent aucun.
   Le cas ne s'applique pourtant pas, pour une raison plus solide : **un upload de parsing ne crée
   aucun fichier dans le magasin du projet.** `GET /api/v1/files` et `GET /api/v1/beta/files` sur le
   projet `Default` rendent **0 fichier**, et sur toute la durée de vie de l'organisation
   l'agrégat d'usage ne contient **qu'un seul type d'événement, `pages_parsed`** — aucun
   `stored_file_mb`, aucun `stored_file_count`, alors que ces deux compteurs existent dans
   l'énumération du fournisseur. Les fichiers d'entrée vivent dans le bucket de travail de LlamaCloud
   (`s3://llama-platform-file-parsing/…`, visible dans les paramètres de job), qui n'est pas le
   magasin facturé. **Conséquence : ni ligne de stockage à modéliser, ni consommation du plafond de
   10 000 fichiers / 10 GB du plan gratuit.**

Trois points annexes :

- **XLSX est facturé à la feuille, pas à la page** (1 crédit/feuille) — vérifié : **8 feuilles,
  8 crédits, 7 jobs**. Et le mode n'y change **rien** : les jobs `fast`, `parse_page_with_llm` et
  `parse_page_with_agent` sur tableur sont tous à 1 crédit, alors que le dernier vaut 45 à 90 crédits
  sur un document. La facturation d'un tableur suit le type de fichier, pas le mode demandé. Or XLSX
  atteint LlamaParse (`docs/INGESTION_WORKERS_PROVIDERS.md:484`) et `record_spend` lui débite
  `page_count` pages — une troisième unité dans le même compteur.
- **Une image est facturée comme un document** : un `.jpg` du 2026-09-06 apparaît en
  `file_type: document`, 1 page, 3 crédits. Le chemin photo-de-page n'a donc pas de barème à part.
- `language: "en"` est **codé en dur** dans l'upload sur une app à 11 locales. Un PDF français est
  parsé avec un indice de langue anglais. Effet coût indirect seulement — **re-parser le même fichier
  dans les 48 h est gratuit** (cache de parse) — mais c'est un défaut de qualité sur un chemin payant.

**Ce que la mesure ne garantit pas, et qui justifie la correction 2b.** Le défaut est *aujourd'hui*
`cost_effective`. Deux relevés du même jour montrent qu'il est révocable sans préavis :
l'organisation porte un drapeau `show_parse_v1: true` **réévalué par le fournisseur** — horodaté
`legacy_v1_evaluated_at: 2026-09-09T15:32Z` — et la nomenclature de facturation a déjà changé sous le
dépôt le 2026-08-29, cette fois-là à barème constant. Envoyer `parse_mode` explicitement ne fait pas
baisser le prix d'un centime ; ça fige le prix. C'est la seule raison de le faire, et elle suffit.

**Ordre de grandeur du réel.** Toute l'histoire de l'organisation depuis le 2026-05-27 tient en
**284 crédits = $0,355 = 0,3053 €** (100 pages ou feuilles, 35 jobs), dont l'essentiel provient des
benchmarks de ce dépôt. Le plafond de 10 000 crédits/mois n'a jamais été approché — ce qui n'infirme
rien de ce qui précède : le déficit se joue au **taux unitaire**, pas au volume actuel.

### 3.5 Unstructured : le repli est 9,7× le budget de la page

- Free : « Start processing your data with 10,000 free pages », « No card required » — **une
  dotation unique à la création du compte**, pas un quota mensuel.
- Ensuite : **$0.015/page**, « The page does not describe a hard cutoff ». Soit **0,012916 €/page**
  contre 0,001328 € débités : **9,7×**.
- Ce qui déclenche la bascule : **n'importe quel `ParseError`** de LlamaParse — « rate limit,
  timeout, API error, auth error, network error » (`docs/INGESTION_WORKERS_PROVIDERS.md:509`), donc
  y compris le 402 d'épuisement. Le repli n'est pas un incident rare, c'est le régime permanent
  après le 10 000ᵉ crédit du mois.

### 3.6 Algolia : deux compteurs de natures différentes, dont un stock que rien ne libère

Tarifs relevés le 2026-09-09. Plan gratuit : **10 K requêtes de recherche/mois**, **50 K records
inclus**, index **1 GB**, taille de record max **10 KB**, 1 application, 20 index. Premier palier
payant (Grow) : **100 K** records inclus, overage **$0.50/1 K requêtes** et **$0.40/1 K records**.

**La distinction que la config manque est la nature des deux compteurs**, et la page tarifaire est
explicite : les records sont un **stock** — « store a certain number of records at any given time »,
facturés au mensuel sur le **maximum atteint dans le mois, moins les trois jours les plus hauts** —
tandis que les recherches sont un **flux mensuel** qui se remet à zéro. Un crédit d'ingestion peut
payer un flux ; il ne peut pas payer un stock qui ne redescend jamais.

**Que le stock ne redescende jamais est un fait de code, pas une hypothèse.** La purge des médias ne
part que de `account_deletion_service.purge_account` ou du TTL de `user_media`, fixé à 30 jours
**après que l'utilisateur a supprimé la ligne** (`media_purge_service.py:1-20`). Il n'existe **aucune
rétention par âge** : un média ingéré et jamais supprimé reste indexé indéfiniment.

**Combien de records par source ? Mesuré, pas estimé.** `search_indexing.py:11-12,32-35` découpe les
transcripts en records de moins de 10 KB (`_MAX_CHUNK_TEXT_BYTES = 9500`), et
`utils/algolia_client.py:66-137` ne déclare **aucun replica ni tri annexe** — donc pas de
multiplication des records. Relevé en lecture seule sur `media_items_dev` (`/1/indexes/…/browse`) le
2026-09-09 :

| Mesure sur dev | Valeur |
|---|---|
| Records parcourus | 166 |
| Sources distinctes | 89 |
| Records par source | min **1**, médiane **1**, moyenne **1,87**, max **22** |

Mon estimation antérieure (≈ 6 records par source) était **trois fois trop haute** : le corpus de dev
est dominé par des sources courtes, une seule dépasse 20 records. À 1,87 records/source, un record
d'overage coûtant 0,000344 €/mois, cela donne :

| Poste | À 100 abonnés | À 1 000 abonnés |
|---|---|---|
| Recherches (90/mois/abonné) | 9 000 → **dans le gratuit** | 90 000 → **34,40 €/mois** (0,97 % du net) |
| Records ajoutés (20 sources/mois/abonné) | 3 740/mois → plafond Free atteint en **13 mois** | 37 400/mois → plafond Free atteint en **1,3 mois**, Grow en 2,7 mois |
| Loyer d'index par abonné | +0,013 €/mois par mois d'ancienneté | idem |

Trois lectures, et la première n'est pas celle que j'attendais :

1. **Algolia est bien dimensionné et bon marché.** Le `algolia_build_free: 0.0` de
   `infra_cost_baseline` est juste en substance : même à 1 000 abonnés, recherches et records réunis
   restent sous 5 % du net. La première version de ce document présentait le poste comme un risque ;
   la mesure ne le confirme pas, et je corrige.
2. **Ce qui est faux, c'est la forme du garde-fou, pas le montant.** Algolia n'est pas dans
   `provider_pools` (§ 2.3), et son épuisement sur le plan gratuit ne coûte pas d'argent : il **casse
   la recherche**, silencieusement, pour tout le monde. C'est le seul des quatre fournisseurs à quota
   partagé dont la panne est fonctionnelle. Le plafond arrive à **50 000 / 1,87 ≈ 26 700 sources
   indexées**, toutes utilisateurs confondus — un nombre atteint bien avant les 130 utilisateurs de la
   décision task-53.1.
3. **La décision de task-53.1 reste prise sur le mauvais critère.** « algolia car gratuit jusqu'à 130
   users avec > 250 docs de 36 kb par user » (ligne 9) raisonne en **taille d'index**, alors qu'un
   document de 36 KB devient plusieurs records, que le quota inclus est de 50 K records et non des
   ~110 K déduits, et que la contrainte de flux (10 K recherches/mois) n'est pas mentionnée du tout.

Deux points de propreté relevés le même jour :

- **`providers.search.plan: "build_free"` est un libellé périmé** : le plan affiché aujourd'hui est
  **Free**, « Build » n'existe plus dans la nomenclature Algolia.
- **Deux index orphelins subsistent** à côté de `media_items_dev` : `transcripts` et
  `transcripts_user_4cd1abcb-…`. Ils consomment du quota de records pour rien. La clé
  `ALGOLIA_INDEX_NAME` est morte de son côté — le nom est construit en dur en
  `media_items_{ENVIRONMENT}` (`algolia_client.py:66-137`).

Le backend appelle `search_single_index` (`search_indexing.py:389`), **une requête par recherche
utilisateur** : le mobile passe par le backend (`searchService.ts:69,97` → `endpoints/search.py:148,169`),
il n'y a pas de SDK Algolia côté app, donc pas de recherche à la frappe. Le comportement du plan
gratuit à dépassement (bloqué, throttlé ou facturé) n'est pas documenté sur la page — non vérifié.

### 3.7 Le baseline d'infrastructure : 72 % d'une machine qui n'existe pas

`infra_cost_baseline` (`pricing_config_service.py:180-189`) déclare 14,6 €/mois à 100 users, dont
**`ec2_t4g_small: 10.55`**. Or :

- **Aucune instance EC2 n'est provisionnée.** Inventaire de `infrastructure/terraform/` : zéro
  `aws_instance`, zéro occurrence de `t4g` ou `ec2`. Ce qui existe : 5 fonctions Lambda,
  28 files SQS, 21 tables DynamoDB, 13 buckets S3, API Gateway v2, 1 topic SNS, 1 vault de backup,
  1 planificateur EventBridge. L'API est passée sur Lambda avec task-105
  (`docs/API_LAMBDA_RUNTIME.md:5-11`).
- **task-287 §1.6 avait déjà retiré ce baseline** et qualifié 0,145 €/user de « roughly 2x too
  high », sur la base de trois mois de Cost Explorer mesurés par l'owner (5,93 / 8,11 / 4,90 USD
  TTC). Le module docstring (`:5-6`) prétend pourtant que les défauts dérivent de task-287.

**Quatre baselines incompatibles coexistent dans le dépôt** :

| Source | Baseline @100u | Statut |
|---|---|---|
| `pricing_config_service.py:182` | 14,6 €/mois (0,145 €/user) | **en production dans la config** |
| task-65 `compute.py` (0,190 €/user) | 19,04 €/mois | benchmark validé |
| task-53.1 README ligne 36 | 57,5 €/mois (EC2 10,55 + Typesense 43 + misc 4) | benchmark validé |
| task-287 §1.6 (mesuré) | 31,91 €/mois de plancher fixe | benchmark validé, le seul mesuré |

Le 10,55 € de l'EC2 fantôme s'est propagé par **deux** benchmarks avant d'atteindre la config.

Les 4 €/mois de « aws_misc » ne couvrent pas ce qui tourne : `variables.tf` chiffre lui-même
`enable_alarms` à ~$3.30/mo (43 alarmes), `enable_dashboard` à ~$3.00/mo (« the single largest line
item of an idle environment ») et `enable_worker_polling` à ~$0.90/mo — soit **~$7.20/mo pour la
seule observabilité**, que `envs/prod/main.tf` éteint en la déclarant explicitement temporaire :
« THE MOTHBALLING IS TEMPORARY AND ENDS AT LAUNCH … Waking prod up is a prerequisite of taking the
first paying user, not a follow-up to it ». **Le plancher mesuré de 31,91 € est un plancher *dev
seul*** : personne n'a chiffré la duplication au lancement (SQS polling, CloudWatch, Secrets
Manager, PITR, vault, log groups de prod).

**Le stockage n'apparaît dans aucun modèle, et il croît sans borne.** Sur les 11 buckets de contenu
(`modules/platform/s3.tf`), **deux seulement** portent une règle d'expiration, toutes deux limitées
à un préfixe de staging d'upload (`documents_upload_staging:173-185`,
`audio_upload_staging:194-206`), plus une sur les covers (`:218). **Neuf buckets n'ont aucune
expiration** : audio, transcripts, summaries, summary_short, summary_detailed, notes, flashcards,
quiz, review_blurb, documents. S'y ajoutent le PITR sur ~21 tables, un AWS Backup hebdomadaire à
90 jours sur 3 tables, et un export mensuel `ExportTableToPointInTime` en GLACIER_IR conservé
**365 jours** (`backup_library.tf`). C'est un coût monotone croissant, proportionnel au contenu
ingéré et jamais libéré, absent de `infra_cost_baseline`. Je n'ai pas pu récupérer le tarif S3 par
GB-mois pour eu-west-3 (voir § Ce que je n'ai pas pu vérifier), donc je ne le chiffre pas — mais sa
**structure** suffit à conclure : c'est le seul poste dont le modèle ignore jusqu'au signe de la
dérivée.

### 3.8 Coût par utilisateur à 10 / 100 / 1 000, et le point de bascule

Avec le seul plancher mesuré (31,91 €/mois, dev seul, task-287 §1.6), et un coût variable par
abonné Mix pris à deux régimes — l'audio pur au tarif Deepgram batch corrigé, et le régime YouGube
au plafond :

| Abonnés Mix | Fixe/user | Variable/user (audio pur) | Variable/user (YouTube au plafond) | Net/user | Résultat (audio) | Résultat (YouTube) |
|---|---|---|---|---|---|---|
| 10 | 3,19 € | 1,16 € | 16,71 € | 3,542 € | **−0,81 €** | **−16,36 €** |
| 100 | 0,32 € | 1,16 € | 16,71 € | 3,542 € | **+2,06 €** | **−13,49 €** |
| 1 000 | 0,03 € | 1,16 € | 16,71 € | 3,542 € | **+2,35 €** | **−13,20 €** |

Deux lectures, et elles pointent dans des directions opposées :

- **En régime audio, le modèle bascule vers ~14 abonnés Mix** et l'échelle règle le problème.
  C'est la conclusion de task-287, et elle est juste — mieux que juste, puisque le coût de la
  minute est 1,79× plus bas qu'annoncé.
- **En régime YouTube, l'échelle n'arrange rien** : le déficit par utilisateur est constant et
  **grandit** avec le nombre d'abonnés. Aucun palier ne le rattrape. C'est la définition d'un
  problème de tarification, pas d'un problème de charge.

Et à 1 000 abonnés les plafonds gratuits ont sauté depuis longtemps, dans cet ordre :

| Plafond | Quand il tombe | Ce qu'il coûte ensuite |
|---|---|---|
| **LlamaParse** 10 000 crédits = 3 333 pages (§ 3.4) | **1 abonné** au plafond documentaire | bascule silencieuse sur Unstructured à 9,7× — ou Starter à **$50/mois** |
| **Apify** $5/mois par compte, et **50 transcripts/jour** par acteur (§ 3.3) | 1 000 vidéos/mois, ou 1 utilisateur à `items_per_day: 60` | blocage jusqu'au cycle suivant — ou Starter à **$19/mois** |
| **Algolia** 50 K records en **stock** (§ 3.6) | ~26 700 sources indexées, tous utilisateurs confondus | overage $0.40/1 K records/mois, ou Grow |
| **Algolia** 10 K recherches/mois | ~111 abonnés à 90 recherches/mois | 34,40 €/mois à 1 000 abonnés |

Les marches ne sont pas linéaires, et surtout **elles ne tombent pas dans l'ordre du nombre
d'abonnés** : LlamaParse casse au premier utilisateur documentaire intensif, Algolia au vingt-sept
millième document. Un pool unique indexé sur le nombre d'utilisateurs ne peut pas modéliser ça.

### 3.9 Ce qui est mesuré, ce qui reste modélisé

Mise à jour du 2026-09-09 : une partie de ce que ce document déclarait non mesurable l'a été, par
appels **en lecture seule** aux API des fournisseurs et aux tables `-dev`. La liste exacte, pour que
la frontière soit lisible :

| Fournisseur | Ce qui est **mesuré** | Ce qui reste **modélisé** |
|---|---|---|
| AWS | task-287 §1.6, trois mois de Cost Explorer relevés par l'owner (2026-06 : 5,93 USD TTC dont SQS 2,37 et CloudWatch 2,23 ; 2026-07 : 8,11 ; 2026-08 au 18 : 4,90) | le coût du stockage S3/PITR (§ 3.7) |
| Apify | **trois comptes FREE**, plans et limites lus sur `/v2/users/me` et `/v2/users/me/limits` ; l'acteur configuré (`starvibe`) lu dans le secret ; **11 jobs YouTube** de `processing_jobs-dev` confirmant l'acteur, le plus récent le 2026-09-06 | la consommation réelle en dollars du mois écoulé |
| Algolia | **166 records sur 89 sources** dans `media_items_dev` (`/browse`), soit 1,87 records/source ; la liste des index, dont deux orphelins ; le plan affiché | le volume de recherches réel des testeurs |
| LlamaParse | la table de tarifs v1 complète (skill `llamaparse-pricing`, et la page en ligne retrouvée), **le mode par défaut réellement facturé** (`cost_effective`, **3,000 crédits/page** sur 92 pages / 28 jobs), **1 crédit/feuille** sur 8 feuilles, **zéro stockage retenu** (aucun `stored_file_mb`, 0 fichier dans le projet), consommation totale **284 crédits = 0,3053 €** | rien de ce que ce document utilise ; le seul inconnu restant est la **durée de validité** du défaut (drapeau `show_parse_v1` réévalué côté fournisseur) |
| OpenAI | **414 866 tokens d'entrée et 64 231 de sortie sur 90 générations**, coût 0,110110 €, taux de `cached_tokens` **14,1 %** (`media_artifacts-dev`) ; **17 traductions** avec leurs tokens (CloudWatch, 14 j) ; **1,795 tokens/mot** sur 14 articles | la relation **durée d'audio → tokens** (aucune durée de média n'est journalisée, cf. ci-dessous) |
| Deepgram | les tarifs publics | la facturation de `detect_language=true`, l'arrondi |

**Ce qui a basculé du modélisé au mesuré.** `cached_tokens` n'attendait pas l'owner : il est
persisté dans `media_artifacts-dev` (`media_artifact.py:127-133`), et les 90 générations que la table
porte donnent le taux réel (§ R.6, point 3). Le volume de tokens non plus : la relation
**mots → tokens** se mesure en croisant `extraction_metadata.word_count` de `processing_jobs-dev`
avec le `prompt_tokens` du `review_blurb` du même `media_item_id`. Sur 14 articles, elle vaut
**1,795 tokens/mot**, avec une régression `prompt ≈ 482 + 1,653 × mots` — le terme fixe étant le
prompt d'instruction. Les plus gros prompts réellement observés, par plateforme : **12 160 tokens**
pour une vidéo YouTube, **21 939** pour un épisode de podcast, **11 416** pour un document,
**52 130** pour un article de 31 218 mots (Wikipédia).

**Ce qui reste modélisé, et pourquoi ça ne peut pas se mesurer ici.** L'estimation de **36 k tokens
pour 3 h** sur laquelle repose l'axe 2 n'est pas vérifiable dans le dépôt, parce que **la durée réelle
d'un média n'est journalisée nulle part**. `processing_jobs-dev` porte `total_duration` et
`transcription_duration`, mais ce sont des durées d'**exécution** (1 à 31 s), et le
`duration_seconds` de `transcription_metadata` aussi (1,4 à 11,9 s). Le produit facture à la minute
une grandeur qu'il n'écrit pas à côté du job : c'est un défaut d'instrumentation avant d'être une
lacune de mesure, et il se corrige en une ligne au moment du débit.

Ce qui reste possible en attendant, c'est de **borner** l'hypothèse plutôt que de la déclarer
inconnue. À 150 mots/minute de parole et au ratio mesuré de 1,795 tokens/mot, une heure d'audio fait
~16 200 tokens ; mais 1,795 est mesuré sur du **français écrit**, et l'anglais parlé tourne plutôt
autour de 1,3 token/mot, ce qui ramène à ~11 700 tokens/heure. **L'hypothèse de 12 000 tokens/heure
du document est donc juste pour de l'anglais et sous-estime le français d'environ 35 %** — elle est
conservatrice dans le sens qui compte, puisqu'un transcript français coûterait plus que ce que
l'axe 2 annonce. Le facteur 8,46× n'est pas menacé par le bas.

Ce qui n'existe toujours pas : **aucune facture** de Deepgram, Apify, Unstructured ou Algolia.
OpenAI en a une (§ R.6). LlamaParse a mieux qu'un état de compte et moins qu'une facture : le
**détail de consommation par job**, crédits et pages compris — 284 crédits sur toute la vie du
compte, entièrement absorbés par le plan gratuit, donc rien n'a jamais été facturé. C'est suffisant
pour établir le **taux unitaire**, qui est tout ce dont ce document a besoin (§ 3.4).

**Un dernier constat, sur le compteur qui porte tout ça.** `user_usage_monthly-dev` compte 86 lignes,
et leur schéma se lit en deux couches. Les **5 lignes récentes** sont écrites par le code actuel :
clé `period` en `trial:<date>` ou `sub:<date>`, avec `minutes_used`, `cost_eur_estimated` et
`settled_jobs` (les jetons d'idempotence, `quota_usage_db.py:109-132`) — le mécanisme fonctionne. Les
**81 autres** (94 %) sont en `YYYY-MM` et portent cinq attributs qui **n'existent nulle part dans le
code** : `articles_count` (68 lignes), `youtube_count` (25), `documents_count` (14),
`audio_minutes_used` (14), `collection_source_units` (1). Aucun n'est lu, aucun n'est écrit. Sous la
règle du projet — rien n'est déployé, donc rien n'a à être migré — ces 81 lignes se **suppriment**.
À noter au passage, sans en faire une alarme : une ligne porte `period = sub:2029-09-01`, une échéance
en 2029 qui vient d'un abonnement de sandbox RevenueCat, `period_key` dérivant du `period_end` de
l'abonnement (`quota_enforcer.py:590-596`).

Cette table donne aussi le seul **point de calibration de bout en bout** disponible : la ligne
`trial:2026-08-19` porte `minutes_used = 104` et `cost_eur_estimated = 0,7686 €`. Or 104 × 0,00664 =
0,69056 €, et la différence — **0,0780 €** — est le coût LLM réel des générations de cet utilisateur,
soit 71 % des 0,110110 € mesurés sur toute l'histoire de dev. La formule du compteur est donc bien
« minutes × `cost_per_minute_eur` + coût LLM constaté », ce qui confirme que **`cost_eur_estimated`
mélange un budget supposé et une dépense réelle**. Il ne peut pas servir à valider le budget
fournisseur : les 0,69056 € sont censés couvrir Deepgram, et sans facture Deepgram cette moitié
reste une hypothèse.

---

## Axe 4 — La surface « gérer mon abonnement »

### 4.1 Il n'y a pas d'écran de gestion : il y a une page de vente

task-376 a arbitré « deux écrans » (§8) : Account porte l'état et « c'est elle qui devient la
« gestion de l'abonnement » au sens propre », `/paywall` porte l'offre. **L'implémentation ne
respecte pas cet arbitrage.** `account.tsx:200-228` est la seule entrée vers l'abonnement, et son
`onPress` est `router.push("/paywall")` **dans tous les états**, y compris pour un abonné actif dont
le libellé est `account.subscription.manage` = « **Changer de formule** ». task-376 §8.3 l'avait
anticipé : « Le libellé `manage` devient donc le moins juste des trois et doit être revu par
task-377 ». Il ne l'a pas été, et le problème n'est pas le libellé : c'est que la destination est un
écran de vente.

Le parti pris Account/paywall est **le bon** — les cinq références vérifiées par task-376 §3.0
séparent état et offre. Ce qui manque est le contenu de la moitié « état ».

### 4.2 Ce que la carte d'état ne dit pas

`SubscriptionStatusCard.tsx:163-218` rend, pour un abonné actif : le nom du tier, une puce de
statut, `minutes_remaining`, une date de recharge (`getResetDateLabel`), une `UsageBar` et
`minutesRule()`. Vérifié absent :

- **le prix.** Aucune occurrence de prix dans le composant. L'utilisateur qui veut savoir combien il
  paie doit ouvrir `/paywall` et lire le prix du store.
- **le montant et la date exacte du prochain prélèvement.** `resetDate` est la date de recharge du
  compteur, ce qui n'est pas nécessairement la date de facturation, et rien ne l'appelle un
  prélèvement.
- **ce qui arrive aux médias déjà importés en cas de rétrogradation.** Rien, nulle part, ni dans la
  carte, ni dans les catalogues i18n. C'est la question qu'un abonné se pose avant de descendre de
  formule, et l'app n'y répond pas — alors que la réponse est simple et rassurante (le débit a lieu
  à l'ingestion, la bibliothèque n'est pas relue).
- **un chemin de résiliation.** `STORE_SUBSCRIPTIONS_URL` existe (`legal.ts:25-30`) avec une
  docstring qui promet « every "cancel anytime" sentence points here » — et il est importé
  **uniquement** par `settings/delete-account.tsx:23`, utilisé à `:104`. La phrase du paywall,
  `paywall.cancelAnytime` = « Résiliez à tout moment dans votre compte {store} », est du **texte
  brut** (`paywall.tsx:655-657`), pas un lien. Un abonné iOS doit passer par Apple, et le seul
  endroit où l'app le lui propose est l'écran de **suppression de compte**.

À l'inverse, ce que la carte dit honnêtement, et qu'il faut garder : **la fin de l'essai est
nommée** (`subscription.resetLabel.trialEnds` = « FIN DE L'ESSAI »), les quatre états de recharge
sont distingués, et `paywall.renewalTerms` porte bien la formulation complète du renouvellement
24 h avant échéance, sous `canPurchase` (`paywall.tsx:598-625`) avec les liens Terms et Privacy.

### 4.3 Confrontation à la règle du store, telle qu'elle est écrite aujourd'hui

Mon hypothèse de départ était qu'un chemin de résiliation manquant expose à un rejet 3.1.2. **Elle
est fausse et je la retire.** La 3.1.2 d'aujourd'hui contient : 3.1.2(a) *Permissible uses*,
3.1.2(b) *Upgrades and Downgrades* (« Users should have a seamless upgrade/downgrade experience »),
3.1.2(c) *Subscription Information* (« Before asking a customer to subscribe, you should clearly
describe what the user will get for the price »), qui **délègue** les obligations énumérées à la
Schedule 2 de l'ADPLA. L'énumération « The length of the renewal term … How to cancel » est en
**4.9 Apple Pay**, qui ne régit pas les IAP auto-renouvelables.

Trois conséquences :

1. **L'absence de lien de résiliation est un défaut produit, pas un risque de rejet.** Elle reste à
   corriger, mais elle ne bloque pas une soumission. Ne pas la traiter comme un blocant.
2. **3.1.2(b) est satisfaite** : le changement de formule passe par le groupe d'abonnement, et un
   `PRODUCT_CHANGE` réel a été exercé en sandbox (`docs/REVENUECAT_ENTITLEMENTS.md:55-58`).
3. **3.1.2(c) est satisfaite et bien faite** : le paywall décrit l'allocation, le plafond par import
   et le tableau des conversions avant l'achat, depuis `GET /api/pricing`.
   Le mécanisme natif recommandé, si le lien de résiliation est ajouté, est
   `AppStore.showManageSubscriptions(in:)` côté StoreKit 2, ou le lien
   `https://apps.apple.com/account/subscriptions` que `legal.ts` porte déjà.

### 4.4 « 212 minutes restantes » est-il actionnable, et l'alerte à 80 % est au mauvais endroit

Un nombre de minutes restantes n'est actionnable que si l'utilisateur sait ce qu'une minute achète.
Le tableau des conversions qui l'explique est sur `/paywall`, pas sur Account : sur l'écran d'état,
« 212 min » est un nombre nu. `minutesRule()` en dit une partie (« les articles n'en coûtent
aucune ») mais pas la règle qui compte pour prévoir (« une vidéo YouTube en coûte une, quelle que
soit sa durée »).

Et **l'avertissement à 80 % n'est pas sur l'écran qui porte la jauge.**
`MinutesWarningBanner.tsx:35` lit `warning_threshold_reached` et rend
`quota.warning.{trial,monthly}[WithDate]` — mais il n'est monté qu'à `inbox.tsx:348`. Un abonné qui
consulte sa consommation sur Account voit une `UsageBar` à 85 % **sans aucun avertissement**, alors
que le composant qui le formule existe. Accessoirement, `UsageBar` (`SubscriptionStatusCard.tsx:227-253`)
est masquée aux lecteurs d'écran et renvoie `null` quand `minutes_included <= 0` : pour un
utilisateur non-voyant, la jauge n'existe pas et le seul canal restant est le bandeau — qui est sur
un autre onglet.

**Trois formules dont deux ne diffèrent que par un nombre de minutes n'aident pas à choisir** quand
on ne connaît pas encore sa consommation. `buildPlanGuidance` tente de répondre avec
`USAGE_SIGNAL_RATIO = 0.25`, mais il ne peut recommander qu'à partir d'un usage **déjà observé** —
donc jamais au moment qui compte, la première visite. C'est exactement le problème que le palier
gratuit permanent de Snipd résout : on découvre sa consommation avant de choisir. Le tarif horaire
(3,00 / 1,00 / 0,75 €/h) est la seule aide disponible à la première visite, et il est excellent en
tant que révélateur de la forme de l'offre — mais il repose sur l'assimilation minute ≈ durée que
l'axe 1 invalide.

---

## Ce qui doit changer

Du plus coûteux si ignoré au plus cosmétique. « **B** » = bug (code ≠ config), « **M** » = erreur
de modèle (le chiffre est faux), « **A** » = arbitrage produit (le chiffre est juste, le choix se
discute).

| # | Type | Correction | Emplacement | Priorité |
|---|---|---|---|---|
| **0** | **A** | **Trancher la refonte de § La refonte proposée** : le crédit à la place de la minute, un forfait de 2 crédits par envoi, Découverte gratuit 40 / **Standard 5 € 360** / **Intensif 9 € 720**, annuel à −20 %, recharge consommable 100 crédits à 2,99 €. **Les corrections 1, 15, 16 et 19 sont absorbées par cette décision** et ne se font pas séparément : les traiter une à une revient à recalibrer deux fois, ce que la règle « les nettoyages d'abord » interdit. | § R.7 donne l'emplacement ligne à ligne | **Bloque le lancement** |
| 1 | **M** | Cesser de facturer 1 minute forfaitaire une vidéo YouTube — **absorbé par la correction 0** (barème : 2 crédits + 1 par 20 min commencées, couverture 108–129 %). Si la refonte est refusée, le minimum vital est de facturer YouTube **à sa durée**, car le coût dominant est le LLM en aval, proportionnel à la longueur du transcript. | `unit_conversion.captions_minutes` dans DynamoDB `pricing_config-<env>` + `docs/research/task-287-…/README.md` (thèse à corriger) + `plan.cost.captions.*` dans les 11 catalogues i18n | **Bloque le lancement** |
| 2 | **B** | Appeler `provider_pool_guard.spend_allowed` avant LlamaParse, comme `apify_adapter.py:212-214` le fait pour Apify, **et compter en crédits** : à 3 crédits/page le pool croit avoir dépensé le tiers du réel, donc `alarm_pct: 60` se déclenche après l'épuisement et `stop_pct: 90` jamais. Sans cet appel, l'épuisement bascule silencieusement sur un fournisseur 9,7× plus cher, et il arrive **dès le premier abonné documentaire intensif** (3 333 pages, pas 10 000). | `media_summarizer/workers/document_parsing/worker.py` (avant `:156`, et `:253-260` pour l'unité) + `provider_pools.llamaparse.capacity_unit` | **Bloque le lancement** |
| 2b | **B** | **Envoyer le mode LlamaParse explicitement** dans la charge utile d'upload : `parse_mode=parse_page_with_llm`, qui est le défaut mesuré le 2026-09-09 — donc **à coût rigoureusement nul**, 3 crédits/page avant comme après. Ce qu'on achète est la stabilité : le défaut n'est publié nulle part, l'organisation porte un drapeau `show_parse_v1` réévalué par le fournisseur, et sa nomenclature de facturation a déjà changé sous le dépôt le 2026-08-29. Le mode est une décision de prix : il appartient à la requête. | `media_summarizer/infrastructure/resolvers/llamaparse_resolver.py:191-194` | **Bloque le lancement** |
| 3 | **M** | **Fait le 2026-09-09** : la candidature au Small Business Program est déposée. Reste à **relever et consigner la date d'approbation** — l'effet est décalé de « fifteen (15) days after the end of the fiscal calendar month in which your enrollment is approved », soit ~15 novembre 2026 pour une approbation en septembre. Jusque-là les nets sont ceux de 30 % (−17,6 %). | Confirmation Apple par mail + App Store Connect → **Business**. Trace à écrire dans `docs/V1_LAUNCH_PLAN.md`, qui ne mentionne pas le programme | Haute |
| 3b | **M** | **Basculer `review_blurb` sur `gpt-5-nano`.** C'est le seul appel LLM que 100 % des ingestions paient, et **13 % seulement de son coût est de la sortie** — donc tout est dans l'input à $0.20/1M, pour produire quatre puces. **Mesuré sur les 59 appels réels de dev** : 0,000685 €/appel, soit **36,7 % de toute la facture LLM**, ramenés à 0,000177 € — **−74,1 %**, contre −74,9 % modélisé sur une source de 3 h. Les deux méthodes convergent, ce qui en fait le changement le mieux étayé du document ; ~8,50 €/mois au plafond de `items_per_day: 60`. Prérequis : rendre la famille `*_LLM_MODEL` réelle, sinon `OPENAI_MODEL` déplace cinq générateurs à la fois. | `generators/review_blurb.py:100-101` + secret `media-summarizer-runtime-<env>` | Haute |
| 3c | **B** | **Envoyer `reasoning_effort: "minimal"` sur les deux appels LLM.** Le mot n'existe **nulle part** dans le dépôt : les deux payloads sont minimaux, donc `gpt-5-nano` et `gpt-5.4-nano` raisonnent au réglage par défaut et **ces tokens sont facturés au tarif de sortie** — 8× l'entrée, 6,25× respectivement. Mesuré sur 17 traductions : un plancher de **~3 400 tokens de sortie par appel indépendant de la longueur** (`sortie ≈ 3 402 + 1,58 × entrée`), qui donne un ratio de **11,4× sous 1 000 tokens d'entrée** contre 1,12× à 9 283. Gain **−69,2 %** sur les traductions mesurées. **La facture OpenAI confirme sur trois mois** : le résidu `gpt-5-nano` — la traduction — facture 774 714 tokens de sortie pour 82 417 d'entrée (ratio **9,40×**), **98,9 % de son coût est de la sortie**, et le poste pèse **60,4 % de toute la facture** (0,2695 € sur 0,4464 €). C'est donc **le premier levier en euros absolus**, devant 3b. Côté artefacts, `summary_short` dépense **92 %** de son coût en sortie pour un résumé *court*. À vérifier après coup sur la qualité des sorties structurées : c'est le seul de ces changements qui peut dégrader un résultat. | `media_summarizer/core/services/transcript_translation.py:310-315` + `media_summarizer/workers/artifact_generator/worker.py:139-148` | Haute |
| 3d | **B** | **Persister le modèle dans `ArtifactLlmUsage`.** La structure porte quatre champs — `prompt_tokens`, `cached_tokens`, `completion_tokens`, `cost_eur` — et **pas le nom du modèle**, alors que `worker.py:321` l'a sous la main (`model = generator.default_model`) et que `_read_llm_usage` le reçoit en paramètre pour calculer le coût. Conséquence : attribuer un euro facturé à un modèle exige de déduire le modèle depuis `artifact_type` en relisant le code, et l'historique devient inattribuable dès qu'un `*_LLM_MODEL` bouge — c'est-à-dire dès la correction 3b. Un champ `model: str` réglé au même endroit que `cost_eur`. | `media_summarizer/core/models/media_artifact.py:127-133` + `workers/artifact_generator/worker.py:204-220` | Moyenne |
| 4 | **B** | Créer le filtre de métrique et l'alarme sur `provider_pool.threshold_reached` et `quota.burst_guard_tripped`, et passer `enable_alarms = true` avec `alert_email` renseigné — au moins sur prod. Le seul canal d'alerte du projet est le mail, et il n'existe pas (topic SNS `count = 0`). | `infrastructure/terraform/modules/platform/` (nouveau `.tf` sur le modèle de `revenucat_alerts.tf`) + `envs/prod/main.tf`, `envs/dev/main.tf` | **Bloque le lancement** |
| 5 | **M** | Corriger `cost_per_minute_eur` : **0,0037 €/min** (batch monolingue) ou 0,0045 € (multilingue), et réécrire le commentaire de source, qui cite aujourd'hui le tarif *streaming*. Puis re-dériver `minutes_per_month` d'`audio_heavy` : le raisonnement qui a produit 720 au lieu de 900 s'appuie sur un chiffre 1,79× trop haut. | `pricing_config_service.py:153-157` + `tiers.audio_heavy.minutes_per_month` + DynamoDB `pricing_config-<env>` | Haute |
| 6 | **B** | Faire refuser les burst guards, ou les supprimer. `_note_burst_guards` ne journalise (`quota_enforcer.py:840`) alors que task-287 §3.3 spécifiait une mise en file : les 1 800 sources/mois autorisées par `items_per_day: 60` sur les chemins à 0 minute coûtent **10,99 à 15,31 €** de plancher LLM, soit cinq fois le net du premier palier. Un garde-fou qui n'arrête rien n'est pas une couche 2. | `media_summarizer/core/services/quota_enforcer.py:802-858` | Haute |
| 7 | **M** | Refaire le pool Apify sur la réalité relevée : **trois comptes FREE distincts** (`nurturing_zeta` YouTube, `rapturous_mantis` TikTok, `kneaded_goodness` Instagram), donc **$15/mois** de capacité répartie en trois budgets étanches, contre **un seul** compteur `apify_results` plafonné à 1 160 « résultats » — une unité qui ne se convertit pas en dollars quand trois acteurs ont trois prix. Corriger aussi la valeur : à $5.00/1 000, $5 achètent **1 000** vidéos, pas 1 160. Et **modéliser le plafond d'acteur de 50 transcripts/jour**, que `burst_guards.items_per_day: 60` laisse dépasser par un seul utilisateur. | `provider_pools.apify` (config + DynamoDB) + `provider_pool_guard.py:35-42,125-149` ; console Apify, **par compte** : Settings → Billing (plan, usage limit) ; corriger `docs/research/task-287-…/README.md` §1.6 (« $29 ») | Haute |
| 7b | **A** | **Garder `starvibe~youtube-video-transcript`** et cesser de traiter `scrape-creators~best-youtube-transcripts-scraper` comme l'option économique. Il est cinq fois moins cher au résultat (0,000860 € contre 0,004300 €) mais `supports_language: False` force une traduction en aval qui coûte 0,004983 € sur une vidéo d'1 h : `starvibe` se rembourse dès qu'il évite la traduction plus de ~72 % du temps. Si l'un des deux doit disparaître, c'est le dialecte non configuré. | `youtube_ingestion_worker.py:29-55` ; `docs/INGESTION_WORKERS_PROVIDERS.md:199-200,208` (qui désigne le mauvais acteur comme déployé) | Haute |
| 8 | **M** | Remplacer `infra_cost_baseline` par le plancher mesuré, et y ajouter les deux postes absents : l'observabilité prod à rallumer (~$7.20/mo) et le **stockage**. Supprimer `ec2_t4g_small` : la machine n'existe pas. Aligner les quatre baselines contradictoires du dépôt sur celui de task-287. | `pricing_config_service.py:180-189` + DynamoDB (`_merge_defaults` ne supprime pas une clé retirée des défauts : suppression explicite requise) + `docs/research/task-53.1-…/README.md:36` + `docs/research/task-65-…/compute.py` | Haute |
| 9 | **B** | Ajouter des règles de cycle de vie sur les neuf buckets de contenu sans expiration, ou décider explicitement de la rétention. Aujourd'hui c'est le seul poste dont le modèle ignore jusqu'au sens de la variation. | `infrastructure/terraform/modules/platform/s3.tf` | Haute |
| 10 | **B** | Trancher `name_fr` : soit `planCopy.ts` et `subscriptionDisplay.ts` le lisent, soit il disparaît de la config et de l'API. Idem `price_ttc_eur`, déclaré dans `pricingService.ts:31` et lu nulle part. Deux champs servis publiquement que personne ne consomme. | `pricing_config_service.py` + `pricing.py:99-100` + `mobile/src/lib/planCopy.ts:135` + `mobile/src/lib/subscriptionDisplay.ts:29-33` + `mobile/src/services/pricingService.ts:21,31` | Moyenne |
| 11 | **B** | Faire d'Account une vraie surface de gestion : prix payé, montant et date du prochain prélèvement, réponse à « que deviennent mes médias si je descends de formule », et **lien vers `STORE_SUBSCRIPTIONS_URL`**. Le changement de formule reste sur `/paywall` ; la gestion cesse d'y renvoyer. | `mobile/src/components/SubscriptionStatusCard.tsx`, `mobile/app/(tabs)/account.tsx:200-228`, `mobile/src/constants/legal.ts` (déjà prêt), 11 catalogues i18n | Moyenne |
| 12 | **B** | Monter `MinutesWarningBanner` sur Account, où vit la jauge. Aujourd'hui il n'est monté qu'à `inbox.tsx:348`, donc un abonné à 85 % ne voit aucun avertissement là où il regarde sa consommation — et un utilisateur de lecteur d'écran n'en voit aucun du tout, `UsageBar` étant masquée. | `mobile/app/(tabs)/account.tsx` | Moyenne |
| 13 | **B** | **Supprimer `providers.llm` et purger `gpt-4o-mini` du dépôt.** Le bloc n'a aucun consommateur — les générateurs lisent `os.environ`. Et `gpt-4o-mini` n'est **jamais appelé** : il n'apparaît sur aucune ligne de la facture des trois derniers mois. Donc ne pas « l'ajouter à `_MODEL_PRICES` » comme la première version de ce tableau le proposait — ce serait provisionner un tarif pour un modèle mort. Ce qui se supprime : le bloc `providers.llm`, le fallback en dur `gpt-4o-mini-2024-07-18` de `notes.py:102` (aligné sur `OPENAI_MODEL` comme les quatre autres générateurs), et la ligne `gpt-4o-mini` du tableau de tarifs de ce document. | `pricing_config_service.py:159-164` + `workers/artifact_generator/generators/notes.py:99-104` | Moyenne |
| 14 | **A** | Créer un produit annuel sur les trois entitlements. Un produit + un package, aucun code, aucun déploiement. Achète de la trésorerie avant le premier mois de coûts fournisseurs, supprime le churn mensuel, et ouvre les 10 % Apple après un an sur les *alternative terms* UE. Readwise cède 24 % pour ça. | Console RevenueCat (`proj879a771a`, offering `default`) + App Store Connect → *Second Brain Plans* + Play Console → Monetize → Subscriptions ; procédure dans `docs/REVENUECAT_ENTITLEMENTS.md:144-162` | Moyenne |
| 15 | **A** | Remplacer l'essai de 30 jours à 300 minutes par un **palier gratuit permanent, faible, compté en objets** (sur le modèle des 2 épisodes/semaine de Snipd). Résout trois choses d'un coup : la division par 5 de l'allocation au moment de payer, le budget fournisseur non récupérable par inscription, et l'impossibilité de choisir une formule sans connaître sa consommation. | `free_trial` (config + DynamoDB) + `quota_enforcer._active_subscription` + `plan.*` / `paywall.*` dans les 11 catalogues i18n | Moyenne |
| 16 | **A** | Revoir le prix d'Audio-Heavy, ou son allocation. À 9 € TTC pour 720 min il est plus cher et moins généreux que Snipd à $6.99 pour 900 min + IA illimitée sur le catalogue pré-traité. Le tarif de la minute étant 1,79× trop haut, l'allocation a de la marge — mais seulement après la correction n° 1. | `tiers.audio_heavy` (config + DynamoDB) + prix dans App Store Connect et Play Console | Moyenne |
| 17 | **M** | Ajouter Algolia à `provider_pools` avec **deux** compteurs, parce qu'il en a deux de natures différentes : les recherches sont un **flux** mensuel (10 K sur le gratuit, ~111 abonnés à 90/mois), les records un **stock** cumulatif (50 K, soit ~26 700 sources indexées à 1,87 records/source **mesurés** sur dev) que rien ne libère — `media_purge_service.py:1-20` ne purge que sur suppression explicite ou TTL de 30 jours *après* suppression, il n'existe aucune rétention par âge. C'est le seul des quatre fournisseurs partagés dont l'épuisement ne coûte pas d'argent mais **casse la recherche**. Corriger au passage `providers.search.plan: "build_free"` (le plan est **Free**) et supprimer les deux index orphelins `transcripts` et `transcripts_user_4cd1abcb-…`. | `provider_pools` et `providers.search` (config + DynamoDB) + `docs/research/task-53.1-lexical-search/README.md:9,36` ; console Algolia → **Search → Index** | Moyenne |
| 18 | **B** | Séparer `quota.refusal.noPlan` en deux messages : « votre formule a pris fin » pour un abonnement expiré, et une invitation neutre pour qui n'a jamais souscrit. Aujourd'hui on annonce à un nouvel utilisateur la fin de quelque chose qu'il n'a jamais eu. | 11 catalogues `mobile/src/i18n/` + branche correspondante de `mobile/src/lib/quotaError.ts` | Basse |
| 19 | **B** | Renommer `revenue_net_eur` en `revenue_net_eur_fr`, ou documenter que c'est un net français. Un chiffre stocké sous un nom faux finit copié. | `pricing_config_service.py:54,65,76` + DynamoDB | Basse |
| 19b | **B** | **Journaliser la durée du média au moment du débit**, et supprimer les 81 lignes de schéma mort de `user_usage_monthly`. Le produit facture à la minute une grandeur qu'il n'écrit nulle part : `total_duration` et `transcription_duration` de `processing_jobs` sont des durées d'**exécution** (1 à 31 s), pas de contenu — d'où l'impossibilité de vérifier l'hypothèse « 36 k tokens pour 3 h » sur laquelle repose tout l'axe 2. Une minute déjà calculée par `minutes_for_seconds` et écrite à côté du job résoudrait la question définitivement. Sur les 86 lignes du compteur mensuel, **81 (94 %)** sont en `period: YYYY-MM` et portent cinq attributs absents du code (`articles_count`, `youtube_count`, `documents_count`, `audio_minutes_used`, `collection_source_units`) : rien n'est déployé, donc ils se suppriment. | `quota_enforcer.minutes_for_seconds` (`:162`) + écriture dans `processing_jobs` ; purge de `user_usage_monthly-<env>` | Basse |
| 20 | **B** | Retirer `tier_order` codé en dur (`pricing.py:93`), qui contredit le classement par allocation de `quota_enforcer._active_subscription` : un quatrième tier ajouté dans DynamoDB serait invisible du paywall tout en étant honoré par l'enforcer. Ordonner par `minutes_per_month`. | `media_summarizer/api/endpoints/pricing.py:93` | Basse |
| 21 | **B** | Rendre `language` dynamique dans l'upload LlamaParse (`llamaparse_resolver.py:193`), aujourd'hui `"en"` en dur sur une app à 11 locales. Défaut de qualité sur un chemin payant. | `media_summarizer/infrastructure/resolvers/llamaparse_resolver.py:191-194` | Basse |

---

## Questions restées ouvertes

Ma recommandation d'abord dans chaque cas. Les trois premières conditionnent la refonte ; les
suivantes, le reste du dossier. **Les questions auxquelles la session du 2026-09-09 a répondu ont été
retirées de cette liste** et leurs réponses sont dans les sections concernées — l'acteur Apify
réellement déployé (§ 3.3), le plan Apify (§ 2.3), la table de tarifs LlamaParse (§ 3.4), le TTL du
cache de prompt (§ R.6), le dépôt de la candidature SBP (§ 2.4), les records Algolia par source
(§ 3.6), **le taux réel de `cached_tokens` et le volume de tokens** (§ R.6 point 3 et § 3.9 — ils
étaient lisibles dans `media_artifacts-dev` et CloudWatch, sans rien demander à l'owner).

1. **Le crédit remplace-t-il la minute ?** Recommandation : **oui**. L'argument n'est pas
   esthétique : un coût fixe par source ne s'exprime pas en durée, et une minute de contenu coûte 22×
   plus en audio qu'en texte. Aucune valeur de « minute » ne peut être juste sur les deux. Si tu
   refuses, la conséquence assumée est que le texte reste sous-facturé et qu'il faut descendre
   `items_per_day` de 60 à ~12 pour borner l'exposition — sachant qu'à 12 on passe aussi sous le
   plafond d'acteur Apify de 50/jour, ce qui n'est pas un hasard.
2. **Supprime-t-on le palier à 3 € ?** Recommandation : **oui**, il perd sa raison d'être (« seulement
   du texte » n'existe plus dès que le texte est mesuré) et même à 15 % son net de 2,125 € exigerait
   18 abonnés pour couvrir la seule infrastructure, avant tout coût variable. Il est remplacé par
   Découverte, gratuit.
3. **Veux-tu la recharge consommable (100 crédits, 2,99 €) ?** Recommandation : **oui**. **76 %** de
   marge à 15 % de commission, et c'est ce qui transforme le mur en choix. Question ouverte parce
   qu'elle ajoute un type de produit (consommable) à côté des abonnements, donc un chemin d'achat de
   plus à tenir.
4. **Rends-tu la baisse de commission à l'utilisateur, ou l'encaisses-tu ?** La grille de § R.3 la
   rend : elle passe de 300/600 crédits (dimensionnés à 30 %) à **360/720** en gardant le même ratio
   variable/net au plafond. L'alternative — garder 300/600 et encaisser — donne des marges de
   +2,042 € et +3,375 € au plafond, soit un seuil de rentabilité de 19 et 12 abonnés au lieu de 22 et
   14. Recommandation : **rendre**, parce que le produit est en beta et que l'allocation est ce que
   les testeurs comparent à Snipd. Mais c'est ta décision, et elle se prend sans toucher à un prix.
5. **Le facteur de charge de 35 % du plafond est une hypothèse de ma part, sans aucune donnée.**
   C'est le seul chiffre de § R.3 que je n'ai pas mesuré. Recommandation : le remplacer par la
   consommation réelle des ~12 testeurs beta avant de figer les allocations — c'est gratuit et ça
   existe déjà en base.
6. **`reasoning_effort: "minimal"` dégrade-t-il les sorties structurées ?** Recommandation :
   **l'appliquer d'abord à la traduction**, où il n'y a rien à raisonner et où le gain mesuré est de
   −69,2 %, puis aux artefacts un par un en regardant le résultat. C'est le seul des changements de
   coût de ce document qui peut abîmer une sortie, donc le seul qui demande un jugement sur la qualité
   plutôt qu'un calcul. `quiz` et `flashcards` sont les deux où je me méfierais le plus.
7. **~~La facture OpenAI du mois écoulé.~~ Close le 2026-09-09.** L'owner a fourni l'export
   `/v1/organization/costs` du 2026-06-01 au 2026-09-09 (101 buckets journaliers, sans trou ni
   chevauchement, 24 jours actifs). Il répond aux trois questions que celle-ci portait :
   `_MODEL_PRICES` est exact sur les six tarifs, l'uplift régional n'est pas appliqué (question 13
   close également), et `cost_eur` journalisé colle à +0,0037 %. Total facturé sur trois mois :
   **0,4464 €**, dont **60,4 % pour la traduction**. Détail en § R.6, « La facture OpenAI ».
8. **~~Le mode LlamaParse réellement facturé.~~ Close le 2026-09-09 — rien à faire de ton côté.**
   Ni le tableau de bord ni `num_pages_billed` n'étaient nécessaires : ce champ appartient d'ailleurs
   à LlamaExtract, pas à Parse, et le v1 que le dépôt appelle n'expose pas le `expand=usage` du v2.
   La lecture s'est faite sur `/api/v1/beta/usage-metrics` avec la clé `-dev` : le défaut est
   **`cost_effective`, 3,000 crédits/page** sur 92 pages et 28 jobs, et le **stockage retenu est un
   poste à zéro** (aucun événement `stored_file_mb`, 0 fichier dans le magasin du projet). Détail et
   conséquences en § 3.4 ; commandes en § Sources. Ce qui reste, et qui est une décision et non une
   lecture : **envoyer le mode explicitement** (correction 2b), parce que le défaut est révocable.
9. **Numéro de tâche pour ce répertoire.** Recommandation : **task-384**, le prochain libre.
   *Corrigé le 2026-09-09* — `task-383` était libre au moment où cette question a été écrite, il est
   depuis attribué (« Faire entrer la description Instagram/TikTok et YouTube dans le corpus des
   artefacts »). Un `git mv docs/research/pricing-challenge docs/research/task-384-pricing-challenge`
   suffit.
10. **Marché de lancement.** J'ai recalculé les nets sur FR / DE / IE / HU et l'amplitude est de
   ±3 % : la question ne change aucune conclusion, mais elle décide de quoi `revenue_net_eur` est le
   net. Hypothèse retenue faute de réponse : **France seule**.
11. **Ambition de volume à 12 mois.** Elle décide de la priorité relative entre la correction n° 1
   (tarification, qui ne s'améliore pas avec l'échelle) et les corrections 8-9 (infra, qui
   s'améliorent). Hypothèse retenue : **quelques dizaines d'abonnés**, donc n° 1 d'abord.
12. **Trois questions que la refonte tranche, listées pour que tu puisses la contredire sur chacune
   séparément.** (a) *Tolérance à un tier d'appel déficitaire* → la refonte dit non et supprime le
   3 €. (b) *Palier gratuit permanent plutôt qu'essai de 30 jours* → oui, 40 crédits. (c) *Plafond
   de prix acceptable* → **les prix ne montent pas** : 5 € et 9 € sont conservés, ce sont les
   allocations qui sont re-dérivées (360 et 720 crédits, contre 300 et 720 minutes). C'était pour moi
   la contrainte à respecter : refondre l'unité sans demander plus d'argent au même utilisateur.
13. **~~Utilisez-vous un endpoint OpenAI régional ?~~ Close le 2026-09-09 — non.** La page tarifaire
    annonce « a 10% uplift for models released on or after March 5, 2026 », ce qui inclut
    `gpt-5.4-nano-2026-03-17`. Le recalcul `amount / quantity` sur les six lignes de l'export de
    facturation rend exactement les tarifs de base : **aucune majoration n'est appliquée**. Rien à
    corriger dans `llm_pricing.py:22-25`.

---

## Ce que je n'ai pas pu vérifier

Sans complaisance : la liste qui suit est la mesure exacte de ce que ce document n'est pas. Elle a
**rétréci** le 2026-09-09 — ce qui a pu être vérifié en autonomie ce jour-là est passé dans les
sections concernées et n'apparaît plus ici ; le partage exact entre mesuré et modélisé est en § 3.9.

- **Une seule facture fournisseur existe : OpenAI.** L'owner a fourni le 2026-09-09 l'export
  `/v1/organization/costs` du 2026-06-01 au 2026-09-09 — **0,4464 €**, ligne par ligne, token par
  token (§ R.6). Il **ne manque plus rien** côté OpenAI : tarifs validés, calcul validé, répartition
  établie. Restent sans aucun montant facturé : **Deepgram, Apify, Unstructured, Algolia**. Ce qui
  existe pour eux, en plus des trois mois de Cost Explorer AWS de task-287 §1.6, est de l'état de
  compte, pas de la facture : les trois comptes Apify, l'inventaire de l'index Algolia, l'acteur
  réellement configuré (§ 3.9). **LlamaParse a quitté cette liste le 2026-09-09** : sa consommation
  est relevée job par job, crédits compris (284 crédits, 0,3053 €), ce qui donne le taux unitaire —
  même si le plan gratuit fait qu'aucune facture n'existe. Le facteur 8,46× de l'axe 2 est robuste au sens où
  il tient sur toute la plage 12 k–60 k tokens, il n'est **mesuré** nulle part, et je ne le présente
  pas autrement. **Deepgram est désormais le seul trou qui compte** : c'est le poste dont dépend la
  validité de `cost_per_minute_eur`, et le compteur d'usage mélange ce budget supposé au coût LLM réel
  (§ 3.9), donc il ne peut pas servir à le vérifier.
- **L'attribution de la facture à une clé.** L'export ne ventile ni par clé API ni par utilisateur —
  `api_key_id` et `user_email` sont `null` sur les 105 lignes, et tout tient sur un projet unique
  (`Default project`). Rien n'y distingue donc le backend `-dev` d'un essai manuel. L'indice
  d'intégrité est fort — **seuls les deux modèles du dépôt apparaissent**, aucun `gpt-4o`, aucun
  embedding, aucun Whisper — mais c'est un indice, pas une ventilation. De même, la séparation
  traduction / `summary_short` dans les 60,4 % est **déduite** par soustraction, les deux partageant
  `gpt-5-nano` : elle est conservatrice (§ R.6, deuxième réserve), pas exacte.
- **La durée réelle d'un média, donc la conversion durée → tokens.** Les tokens, eux, sont maintenant
  mesurés : 414 866 en entrée sur 90 générations, et 1,795 token/mot sur 14 articles (§ 3.9). Ce qui
  manque est l'autre moitié du rapport — **aucune durée de contenu n'est journalisée** ;
  `total_duration` et `transcription_duration` de `processing_jobs` sont des durées d'exécution.
  L'hypothèse de 12 000 tokens/heure reste donc une hypothèse, mais **bornée par le haut et par le
  bas** : ~11 700 pour de l'anglais parlé, ~16 200 pour du français au ratio mesuré. Le sens de
  l'erreur est connu — l'axe 2 sous-estime le français. **C'est la première incertitude du dossier**,
  celle qui a remplacé le TTL du cache à ce rang, et elle se referme en écrivant une minute à côté du
  job (correction 19b).
- **La part de raisonnement dans les tokens de sortie.** Les tokens de sortie sont mesurés
  (64 231 sur 90 générations, § R.6), mais `completion_tokens` **agrège la réponse et le
  raisonnement**, et ni `worker.py:204-220` ni le log de traduction ne lisent
  `completion_tokens_details.reasoning_tokens`. Le plancher de ~3 400 tokens que la régression fait
  apparaître est donc **attribué** au raisonnement par déduction — c'est l'explication parcimonieuse
  (aucun `reasoning_effort` n'est envoyé, les deux modèles sont des modèles de raisonnement), pas une
  lecture directe. Le gain de −69,2 % de la correction 3c en dépend : si l'écart venait d'autre chose,
  il serait plus faible.
- **La représentativité des 90 générations et des 17 traductions.** Elles sont mesurées, mais sur
  **dev**, sur un corpus dominé par des articles et des documents courts : `review_blurb` y voit un
  prompt moyen de 3 874 tokens, là où une vidéo d'1 h en fait ~12 000. Les **taux** (13 % du coût de
  `review_blurb` en sortie, 14,1 % de cache, ratio de 1,12 sur la plus grosse traduction) sont les
  chiffres à réutiliser ; les **totaux en euros** ne décrivent que dev et n'extrapolent rien. Les
  17 traductions viennent en outre des 14 jours de rétention CloudWatch seulement — au-delà, les logs
  n'existent plus.
- **Le traitement facturable de `detect_language=true` chez Deepgram.** Monolingue et multilingue
  ont des tarifs distincts ; je ne sais pas lequel s'applique quand on demande la détection. D'où la
  fourchette 0,0037–0,0045 €/min plutôt qu'un chiffre.
- **L'unité de facturation et l'arrondi de Deepgram.** La FAQ « Does Deepgram charge for silence or
  round up audio time? » est présente sans réponse visible.
- **Le tarif S3 par GB-mois pour eu-west-3.** La page de tarification d'AWS ne rend pas ses tables
  au fetch. Le stockage est donc argumenté structurellement (9 buckets sur 11 sans expiration, PITR
  sur ~21 tables, exports GLACIER_IR à 365 jours) et **pas chiffré**. C'est le trou le plus gênant
  de l'axe 3 : je peux prouver que le poste croît sans borne, pas dire combien il coûte.
- **Le comportement d'Algolia à dépassement du plan gratuit** (bloqué, throttlé ou facturé). La page
  ne le dit que pour les plans payants. La question compte plus qu'ailleurs : c'est le seul pool dont
  l'épuisement casse une fonctionnalité au lieu de coûter de l'argent (§ 3.6).
- **La représentativité du 1,87 records/source.** Le chiffre est mesuré, mais sur le corpus de **dev**
  (166 records, 89 sources), dominé par des sources courtes — une seule dépasse 20 records. Une
  population qui importe surtout des podcasts de 3 h aurait une moyenne bien plus haute.
- **Les taux de TVA du tableau 2.5.** Repris de mémoire, non vérifiés en source primaire cette
  session. L'amplitude de ±3 % ne change aucune conclusion, mais les taux eux-mêmes ne sont pas
  sourcés.
- **Le texte de la Schedule 2 de l'ADPLA**, à laquelle 3.1.2(c) délègue les obligations de
  divulgation énumérées. Ma conclusion « 3.1.2 n'impose pas de lien de résiliation » porte sur le
  texte des guidelines seul.
- **Toute vérification visuelle.** Aucun simulateur, aucun appareil, aucune capture. Les
  conclusions de l'axe 4 sont lues dans le code, pas vues à l'écran.
- **Le comportement réel du système sous charge.** Je n'ai exécuté aucun test et déclenché aucune
  ingestion. Les relevés du 2026-09-09 sont des **lectures** : secrets, `Scan` sur
  `media_artifacts-dev`, `processing_jobs-dev`, `user_media-dev`, `user_usage_monthly-dev` et
  `user_usage_daily-dev`, `filter-log-events` sur CloudWatch, API Apify et Algolia en `GET`. Aucune
  écriture, aucun appel LLM, aucun appel facturé.

---

## Sources

### Tarifs et normes, avec date de consultation

Toutes consultées le **2026-09-09**.

| Source | URL | Ce qui en est tiré |
|---|---|---|
| Deepgram Pricing | https://deepgram.com/pricing | nova-3 batch mono $0.0043/min, multi $0.0052/min ; streaming régulier $0.0077 / promo $0.0048 ; diarisation « Included » en pre-recorded ; crédit de $200 à l'inscription |
| OpenAI API Pricing | https://developers.openai.com/api/docs/pricing (301 depuis platform.openai.com/docs/pricing) | `gpt-5-nano` $0.05/$0.005/$0.40 ; `gpt-5.4-nano` $0.20/$0.02/$1.25 ; `gpt-4o-mini` $0.15/$0.075/$0.60 ; uplift de 10 % sur endpoints régionaux pour les modèles ≥ 2026-03-05 |
| **Facture OpenAI — export de consommation** | 4 fichiers `cost_<début>_<fin>.json` de l'API `/v1/organization/costs`, **fournis par l'owner le 2026-09-09**, couvrant le 2026-06-01 → 2026-09-09 en 101 buckets journaliers (105 lignes de résultat) | Tarifs réellement appliqués reconstruits par `amount / quantity` : **identiques à `_MODEL_PRICES` sur les six lignes, aucun uplift régional**. Total **$0,519037 = 0,4464 €**, dont 62,6 % sur `gpt-5-nano`. Ne ventile **pas** par clé API (`api_key_id` et `user_email` à `null`) |
| Apify Pricing | https://apify.com/pricing | Free $0 / $5 inclus, bloqué à épuisement ; Starter $19 ; Scale $199 ; Business $999 ; overage facturé sur plans payants ; crédits non reportables |
| LlamaIndex Pricing | https://www.llamaindex.ai/pricing | Free 10 K crédits, Starter $50 / 40 K, Pro $500 / 400 K ; 1 000 crédits = $1.25 ; « Basic Parsing: as low as 1 credit » |
| **LlamaParse / LlamaCloud — table de tarifs par mode** | https://developers.llamaindex.ai/llamaparse/general/pricing — **la page est en ligne**, à cette URL et non plus sous `/python/cloud/…` ; identique à `.claude/skills/llamaparse-pricing/references/pricing.md` fournie par l'owner le 2026-09-09 | 1 000 crédits = $1.25 en Amérique du Nord **et** en Europe ; table **v1 (modes)** : « Parse without AI » 1, Cost-effective / « Parse page with LLM » **3**, Agentic 10, Agentic Plus / Layout Agent 45, presets 90 ; Layout extraction **+3/page** ; audio 3 crédits/min ; XLSX **1 crédit/feuille** ; stockage retenu **100 crédits/GB/jour** (0,1/MB), gratuit si expiration ou rétention envoyée ; **re-parse gratuit sous 48 h** ; « Fast (1 credit) outputs spatial text only — **no markdown** ». **Le défaut du mode v1 n'y figure pas** — ni dans le schéma OpenAPI, où `parse_mode` est `ParsingMode \| null` sans valeur par défaut |
| LlamaCloud Billing and Usage | https://developers.llamaindex.ai/llamaparse/general/billing | overage $1.25/1 000 crédits ; épuisement du plan gratuit → **HTTP 402** « You've exceeded the maximum number of credits for your plan » ; tableau de bord : **Settings → Billing → Usage**, qui affiche « usage breakdown by product and mode » (et → Pricing, → Invoices) ; plan gratuit **10 000 fichiers / 10 GB** de stock retenu. Le lien « via the API » de cette page est **mort** (`/cloud-api-reference/get-project-usage-…`, retombe sur l'index, endpoint absent de l'OpenAPI) : l'endpoint vivant est `/api/v1/beta/usage-metrics` |
| **LlamaCloud — schéma OpenAPI** | https://api.cloud.llamaindex.ai/api/openapi.json (145 chemins) | `GET /api/v1/beta/usage-metrics` et `/aggregate` (dimensions `day, project_id, event_type, tier` ; champs `value`, `credits`, `event_aggregation_key` = job_id ; **une fenêtre de dates est obligatoire**, sinon `400`) ; `GET /api/v1/parsing/job/{id}/parameters` et `/details` ; les **115 champs** de `POST /api/v1/parsing/upload`, dont **aucun** d'expiration ou de rétention ; énumération des `event_type`, dont `stored_file_mb` et `stored_file_count` |
| Unstructured Pricing | https://unstructured.io/pricing | 10 000 pages gratuites **à la création du compte** ; puis $0.015/page ; « no hard cutoff » |
| Algolia Pricing | https://www.algolia.com/pricing, **relevé owner (capture) le 2026-09-09** | Free : 10 K recherches/mois, **50 K records**, index 1 GB, record max 10 KB, 1 application, 20 index ; Grow : 100 K records inclus, overage **$0.50/1 K recherches** et **$0.40/1 K records** ; les records sont un **stock** — « store a certain number of records at any given time », facturé sur le maximum du mois **moins les trois jours les plus hauts** ; les recherches sont un flux mensuel |
| **Apify — page de l'acteur YouTube** | relevé owner (capture) le **2026-09-09** | tarification *pay-per-result*, **$5.00 / 1 000 résultats**, usage plateforme inclus, `dataRetentionDays: 7` ; plafond d'acteur de **50 transcripts/jour** sur le plan gratuit |
| **OpenAI — TTL du cache de prompt** | relevé owner le **2026-09-09** | `gpt-5.4-nano` et `gpt-4o-mini` : cache `in_memory`, TTL typique **~5–10 min d'inactivité**, **1 h au maximum**, réutilisation rafraîchissante ; **rétention étendue 24 h non supportée** — la liste officielle mentionne `gpt-5.4` mais **ni** `gpt-5.4-nano` **ni** `gpt-5.4-mini`, qui sont des modèles distincts |
| App Store Small Business Program | https://developer.apple.com/app-store/small-business-program/ | 15 % ; seuil 1 M USD de *proceeds* ; inscription **non automatique** (« Get started today. » → « Enroll now », `…/small-business-program/enroll/`) ; les trois prérequis énumérés (Account Holder, dernier *Paid Apps agreement* / Schedule 2, *Associated Developer Accounts*) ; effet « fifteen (15) days after the end of the fiscal calendar month in which your enrollment is approved » ; 10 % UE après la première année sur les *alternative terms* |
| App Store Connect → **Business** → **Contrats** | relevé par l'owner le **2026-09-09** (capture) | *Contrat relatif aux applications payantes* **Actif**, tous pays, 2 sept. 2026 – 1 juin 2027 ; *applications gratuites* Actif, 1 sept. 2026 – 1 juin 2027 ; BNP Paribas SA (3423) EUR/USD Actif ; W-8BEN + *U.S. Certificate of Foreign Status of Beneficial Owner* Actif ; DSA Active sur 27 pays ; 175 pays ou régions. **Prérequis SBP remplis** |
| Candidature au Small Business Program | **déposée par l'owner le 2026-09-09** ; consigne explicite de traiter les 15 % comme acquis dans ce document | date d'approbation **non encore connue** ; effet 15 jours après la fin du mois fiscal d'approbation |
| Google Play service fees | https://support.google.com/googleplay/android-developer/answer/112622 | 15 % sur les abonnements auto-renouvelables « regardless of revenue » ; EEE/UK/US dès le 2026-06-30 : « 10% + 5% billing fee » |
| App Store Review Guidelines | https://developer.apple.com/app-store/review/guidelines/ | 3.1.2(a)(b)(c) *in extenso* ; l'énumération « How to cancel » est en **4.9 Apple Pay**, pas en 3.1.2 |
| BCE, taux de référence EUR/USD | https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html | 1 EUR = **1,1614 USD** au **2026-09-08** → 1 USD = 0,8611 EUR |
| Snipd Pricing | https://www.snipd.com/pricing | Premium $6.99/mois, « AI processing (900min/month) », IA illimitée sur 1 M+ épisodes ; palier gratuit permanent 2 épisodes/semaine |
| Readwise Pricing | https://readwise.io/pricing | $9.99/mois en annuel ($119.88/an, « Save 24% ») ; $12.99 en mensuel ; Reader inclus ; essai 30 jours, pas de palier gratuit |

Non atteignable : la table de tarification S3 par région (https://aws.amazon.com/s3/pricing/, tables
non rendues). La table crédits-par-mode de LlamaParse avait été déclarée inatteignable
(`/python/cloud/llamaparse/general/pricing/index.md`, 404) : **c'était une URL périmée, pas une page
disparue** — la bonne est `/llamaparse/general/pricing`, cf. ligne dédiée ci-dessus. Elle a été
retrouvée le 2026-09-09 via les endpoints de recherche de la documentation
(`/api/grep?q=…`, `/api/read?path=…`, `/api/list?path=…`, JSON, sans clé), qui restent le moyen le
plus court d'y naviguer. `WebSearch` n'était disponible dans aucune des deux sessions : seules des URL
connues ou dérivées de ces endpoints ont pu être consultées, ce qui limite la comparaison
concurrentielle aux trois produits ci-dessus.

### Relevés effectués en autonomie le 2026-09-09 — tous en lecture seule

| Relevé | Commande / endpoint | Résultat retenu |
|---|---|---|
| Acteur YouTube réellement configuré | Secrets Manager, `media-summarizer-runtime-dev` | `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = starvibe~youtube-video-transcript` |
| Acteur effectivement exercé | `processing_jobs-dev`, jobs YouTube portant un identifiant d'acteur | **11 jobs, tous `starvibe`**, le plus récent le **2026-09-06** |
| Comptes Apify | `GET /v2/users/me`, `GET /v2/users/me/limits` sur les trois tokens | **trois comptes FREE** : `nurturing_zeta` (YouTube), `rapturous_mantis` (TikTok), `kneaded_goodness` (Instagram) — $5/mois chacun |
| Index Algolia | `GET /1/indexes`, puis `/1/indexes/media_items_dev/browse` | 166 records sur **89 sources distinctes** → 1,87 records/source (médiane 1, max 22) ; deux index orphelins `transcripts` et `transcripts_user_4cd1abcb-…` ; plan affiché **Free** |
| **Tarif LlamaParse réellement facturé** | `GET /api/v1/beta/usage-metrics?organization_id=…&day_on_or_after=2026-05-01&page_size=1000`, clé `LLAMAPARSE_API_KEY` du secret `-dev` | **35 métriques**, un seul `event_type` : `pages_parsed`. Documents : **92 pages, 276 crédits, 3,000 crédit/page exactement** sur 28 jobs. `properties` nomme le mode : `parse_page_with_llm` (`openai-gpt-4o-mini`) jusqu'au 2026-08-14, `tier: cost_effective` depuis le 2026-08-29, **même prix**. Tableurs : **8 feuilles, 8 crédits**, 1/feuille quel que soit le mode (`fast`, `parse_page_with_llm`, `parse_page_with_agent`). Un `.jpg` compte comme `file_type: document` à 3 crédits. Total vie du compte : **284 crédits = $0,355 = 0,3053 €** |
| **Absence de mode dans la requête, côté fournisseur** | `GET /api/v1/parsing/job/{id}/parameters` sur deux jobs du 2026-09-06 | **17 champs non nuls sur 140** ; ni `parse_mode`, ni `tier`, ni `premium_mode`, ni `fast_mode`. `api_version = "v1"`, `lang = "en"`, fichiers d'entrée sous `s3://llama-platform-file-parsing/…` |
| **Stockage retenu LlamaParse** | `…/usage-metrics/aggregate?group_by=event_type` ; `GET /api/v1/files` et `/api/v1/beta/files?project_id=…` | **poste inexistant** : aucun `stored_file_mb` ni `stored_file_count` dans l'agrégat, **0 fichier** dans le magasin du projet `Default`. Ni facturation à 100 crédits/GB/jour, ni consommation du plafond 10 000 fichiers / 10 GB |
| **Fragilité du défaut** | `GET /api/v1/organizations` | l'organisation utilisée porte `feature_flags: {show_parse_v1: true, legacy_v1_evaluated_at: "2026-09-09T15:32Z"}` — l'accès au v1 est un **drapeau réévalué par le fournisseur**, pas un acquis |
| Sites d'appel LLM | lecture du code | **deux** : `artifact_generator/worker.py:159` et `transcript_translation.py:320`. Un seul déclenchement automatique : `media_completed_worker._trigger_review_blurb` (`:110-142`, appelé `:293-296` et `:372-377`) |
| **Tokens et cache OpenAI** | `Scan` sur `media_artifacts-dev` (95 items, **90** avec `llm_usage`) | 414 866 tokens d'entrée, 64 231 de sortie, **58 368 cachés (14,1 %)** sur **8 appels / 90** ; coût 0,110110 € ; **39 appels (43 %) sous le seuil de cache de 1 024 tokens** ; `review_blurb` = 59 appels et **36,7 %** du coût |
| **Traductions** | `filter-log-events` sur `/aws/lambda/media-summarizer-worker-transcript_translation-dev`, motif `translation.completed`, rétention **14 j** | **17** traductions (`gpt-5-nano-2025-08-07`, paires ar→fr / en→fr / it→fr) ; 19 772 tokens d'entrée, **89 006 de sortie** ; ratio **4,50** agrégé mais **11,39** sous 1 000 tk d'entrée contre **1,12** à 9 283 tk ; régression `sortie ≈ 3 402 + 1,58 × entrée` |
| **`reasoning_effort`** | `grep` sur `media_summarizer/`, `infra/`, `mobile/` | **zéro occurrence** — les deux payloads LLM sont `model` + `messages` (+ `response_format` / `prompt_cache_key`), donc le réglage par défaut de la famille `gpt-5` est facturé au tarif de sortie |
| **Mots → tokens** | croisement de `extraction_metadata.word_count` (`processing_jobs-dev`) avec le `prompt_tokens` du `review_blurb` du même `media_item_id` | **1,795 token/mot** sur 14 articles ; `prompt ≈ 482 + 1,653 × mots` ; plus gros prompts observés : YouTube **12 160**, podcast **21 939**, document **11 416**, article **52 130** (31 218 mots) |
| **Durée des médias** | `Scan` sur `processing_jobs-dev` (78 jobs) et `user_media-dev` (72 items) | **aucune durée de contenu n'est journalisée** : `total_duration` et `transcription_duration` valent 1 à 31 s (durées d'exécution), `user_media-dev` n'a aucun champ de durée |
| **Compteur d'usage** | `Scan` sur `user_usage_monthly-dev` (86 lignes) et `user_usage_daily-dev` (3 lignes) | **5 lignes** au schéma courant (`period` en `trial:`/`sub:`, avec `minutes_used`, `cost_eur_estimated`, `settled_jobs`) ; **81 lignes** en `YYYY-MM` portant cinq attributs absents du code ; une ligne `sub:2029-09-01` ; calibration : `minutes_used = 104` et `cost_eur_estimated = 0,7686 €` → 104 × 0,00664 = 0,69056 €, reste **0,0780 €** de LLM réel |
| **Facture OpenAI** | 4 exports `/v1/organization/costs` fournis par l'owner (`cost_2026-06-01_2026-07-01` → `cost_2026-09-02_2026-09-09`), 101 buckets journaliers, 105 lignes de résultat | **$0,519037 = 0,4464 €** du 2026-06-01 au 2026-09-09, 24 jours actifs, juillet entier à zéro. Six lignes tarifaires, deux modèles, aucun autre. `amount / quantity` rend les six tarifs de `_MODEL_PRICES` **au centime**, donc **pas d'uplift régional** |
| **Répartition de la facture** | soustraction des artefacts tracés (déduits type par type) du total facturé par modèle | traduction **60,4 %** (0,2695 €, ratio sortie/entrée **9,40×**, dont **98,9 % du coût en sortie**), artefacts en base 24,7 %, artefacts antérieurs à la fenêtre de la table 14,9 % |
| **Cache de la traduction** | ligne `gpt-5-nano-2025-08-07, cached input` de l'export, croisée avec les `cached_tokens = 0` des 10 `summary_short` | **12 928 tokens cachés** viennent de la traduction, soit 15,7 % de son prompt — l'affirmation « hors cache par construction » de la première version est **fausse**. L'économie correspondante est de **0,19 %**, parce que le cache ne remise que l'entrée |
| **Variables de modèle au runtime** | `lambda get-function-configuration` sur `media-summarizer-worker-artifact_generator-dev` + `secretsmanager get-secret-value` sur `media-summarizer-runtime-dev` (noms de clés listés, seules les deux valeurs de *modèle* lues — aucune valeur sensible) | **51 variables Lambda, aucune contenant `MODEL` ni `OPENAI`** ; **40 clés dans le secret**, dont `OPENAI_MODEL = gpt-5.4-nano-2026-03-17` et `DEEPGRAM_MODEL = nova-3`. Aucun `*_LLM_MODEL` nulle part → les défauts de code s'appliquent pour la traduction et `summary_short`. Contredit l'AC de **task-370** |
| **Exactitude de `cost_eur`** | recalcul des 90 générations aux tarifs facturés | 0,110114 € contre 0,110110 € en base, **+0,0037 %** — `estimate_llm_cost_eur` est juste, cached input inclus |

Une précaution de méthode : la première tentative de comptage Algolia est passée par une requête à
facettes et a renvoyé « 0 source distincte » — `attributesForFaceting` utilise
`filterOnly(media_item_id)`, ce qui désactive les compteurs de facette. Le chiffre retenu vient de
`/browse`, qui énumère les records.

### Références de code

**Configuration et API**
`media_summarizer/core/services/pricing_config_service.py:5-6` (docstring attribuant les défauts à
task-287), `:42-190` (`DEFAULT_PRICING_CONFIG`), `:44-47` (thèse du pire cas), `:51-52,62-63,72-73`
(`name`/`name_fr`), `:54,65,76` (`revenue_net_eur`), `:76-77` (justification de 720 min), `:93-109`
(`unit_conversion`), `:120-126` (`burst_guards`), `:132-147` (`provider_pools`), `:153-157` (source
Deepgram), `:159-164` (`providers.llm`), `:169-172` (`search`), `:175-179` (`revenue_model`),
`:180-189` (`infra_cost_baseline`), `:200-223` (`_merge_defaults`).
`media_summarizer/api/endpoints/pricing.py:93` (`tier_order` en dur), `:97-104` (charge utile
publique), `:126-128` (`min_minutes_per_transcription` retenu), `:144` (`currency: "EUR"`).

**Quotas et garde-fous**
`media_summarizer/core/services/quota_enforcer.py:802-858` et `:840`
(`quota.burst_guard_tripped`, journalisation seule), `:1033-1050` (`record_generation`, débit sur
`scope == "folder"` uniquement).
`media_summarizer/core/services/provider_pool_guard.py:13-15` (alarme CloudWatch promise), `:166-176`.
`media_summarizer/core/services/audio_quota_gate.py` (portail partagé pré-Deepgram).
`media_summarizer/infrastructure/apify_adapter.py:214` (seul appel à `spend_allowed`).
`media_summarizer/workers/document_parsing/worker.py:156-176` (bascule sur repli), `:253-259`
(`record_spend` sans `spend_allowed`).

**Coûts LLM et fournisseurs**
`media_summarizer/core/services/llm_pricing.py:20` (`USD_EUR = 0.86`), `:22-25` (`_MODEL_PRICES`),
`:26` (`_FALLBACK_PRICE`), `:41-56` (facturation du cached input).
`media_summarizer/workers/artifact_generator/generators/notes.py:3,102` (`gpt-4o-mini-2024-07-18`),
`summary_short.py:69`, `summary_detailed.py:80`, `flashcards.py:65`, `quiz.py:111`,
`review_blurb.py:101`.
`media_summarizer/core/services/artifact_service.py:116-138` (`REQUESTABLE` / `INTERNAL` /
`GENERATABLE`), `media_summarizer/core/services/review_blurb_service.py:29`
(déclenchement automatique).
`media_summarizer/workers/transcription/deepgram_worker.py:81,85-86,95-98` (drapeaux), `:119-130`
(paramètres de requête), `:192-203` et `:402-413` (appels batch).
`media_summarizer/infrastructure/resolvers/llamaparse_resolver.py:191-194` (charge utile d'upload).
`media_summarizer/core/services/search_indexing.py:389` (`search_single_index`).

**Mobile**
`mobile/src/lib/planCopy.ts:104-115` (`buildHourlyRate`), `:132-167` (`buildPlanCard`, `tier.name`),
`:546-616` (`buildCostTable`).
`mobile/src/lib/subscriptionDisplay.ts:29-33` (`TIER_LABELS` en dur).
`mobile/src/services/pricingService.ts:21,31` (`name_fr`, `price_ttc_eur` déclarés, non lus).
`mobile/app/(tabs)/account.tsx:97-107` (libellés), `:200-228` (unique entrée, `push("/paywall")`).
`mobile/src/components/SubscriptionStatusCard.tsx:163-218` (branche active), `:227-253` (`UsageBar`).
`mobile/src/components/MinutesWarningBanner.tsx:35,115-121` ; `mobile/app/(tabs)/inbox.tsx:348`
(seul point de montage).
`mobile/app/paywall.tsx:90-94` (imports `legal`), `:420-422` (prix et devise du store), `:598-625`
(bloc légal), `:633-659` et `:655-657` (`cancelAnytime` en texte brut).
`mobile/src/constants/legal.ts:25-30` (`STORE_SUBSCRIPTIONS_URL`) ;
`mobile/app/settings/delete-account.tsx:23,104` (seul consommateur).
`mobile/src/lib/quotaError.ts` (phrases construites côté client) ; `mobile/src/i18n/fr.ts`
(`plan.*`, `paywall.*`, `quota.refusal.noPlan`, `subscription.resetLabel.*`).

**Infrastructure**
`infrastructure/terraform/` : aucun `aws_instance`, aucune occurrence de `t4g` ou `ec2` ; aucune
occurrence de `provider_pool`, `burst_guard` ou `threshold_reached`.
`modules/platform/s3.tf:173-185,194-206,218` (les trois seules règles d'expiration) ;
`modules/platform/archiving.tf` ; `modules/platform/backup_library.tf` ;
`modules/platform/variables.tf` (`enable_alarms` ~$3.30/mo, `enable_dashboard` ~$3.00/mo,
`enable_worker_polling` ~$0.90/mo) ; `modules/platform/pipeline_alerts.tf:16-33`
(topic et abonnement en `count = 0`) ; `envs/prod/main.tf` (mothballing, ~$7.20/mo, « ENDS AT
LAUNCH ») ; `envs/dev/main.tf:58,60` ; `envs/staging/main.tf:86-88`.

**Documents du dépôt**
`docs/research/task-287-consumption-model/README.md` §1.6 (Cost Explorer mesuré, plancher 31,91 €,
retrait du baseline EC2), §1.7, §3.3 (couche 2 = mise en file, alarme à 60 %).
`docs/research/task-250-audio-minutes-quota-accuracy/README.md` §2.5 (`audio_heavy` déficitaire à
0,0094 €/min, renvoi explicite à « a separate task revisiting task-65's assumptions »), §2.6, §3.1,
§3.3.
`docs/research/task-65-pricing-v1-benchmark/README.md:132,645` et `compute.py:88,255`
(0,003 €/min, 15 % Small Business Program) ; `README.owner-rejected-2026-05-13.md:21,118`.
`docs/research/task-53.1-lexical-search/README.md:9` (décision owner), `:36` (quatrième baseline).
`docs/research/task-376-subscription-screen-redesign/README.md` §3.0 (cinq implémentations de
référence), §3.2 (arithmétique de la matrice), §8 et §8.3 (deux écrans, libellé `manage`), §9.
`docs/REVENUECAT_ENTITLEMENTS.md:14-18,33-43,55-58,85-94,144-162,223-242` (neuf produits mensuels,
`PRODUCT_CHANGE` exercé, ajout d'un produit sans code, « There is no yearly tier »).
`docs/INGESTION_WORKERS_PROVIDERS.md:199-200,208` (dialectes d'acteurs, $0.005/item, acteur déployé),
`:487-492` (formats texte à zéro page), `:509` (déclencheurs du repli Unstructured),
`:1023-1028` (modèles réels par artefact).
`docs/API_LAMBDA_RUNTIME.md:5-11` (API sur Lambda). `docs/V1_LAUNCH_PLAN.md:196-197,1277-1286`
(essai, paywall, prix ASC) — et **aucune mention du Small Business Program**.
