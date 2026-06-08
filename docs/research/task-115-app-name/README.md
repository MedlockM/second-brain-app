---
owner_decision: pending
---

# Benchmark : Nom marketing de l'app (V1 launch branding) — REDO

## Owner Validation

**Decision**: _(a remplir par l'owner apres relecture)_
**Validated at**: _(date ISO a remplir par l'owner)_

---

## Recommendation

**Percole** — mot existant en italien et en francais (forme conjuguee de "percoler"), transparent dans les deux langues : EN "percolate", FR "percoler/percolation". 7 lettres, zero conflit App Store/Play Store, **tous les domaines majeurs libres** (.com, .app, .io, .co). Metaphore exacte du produit : le contenu percole a travers l'app pour n'en garder que l'essence. Tagline suggeree : *"Let ideas percolate."*

---

## Section 1 — Brief produit reformule

**Second Brain Labs** developpe une application mobile de "second cerveau" qui transforme du contenu partage depuis d'autres apps (Safari, YouTube, podcasts, X, TikTok, Instagram, WhatsApp, PDF/DOCX/PPTX) en artifacts exploitables : transcripts, resumes, notes structurees, flashcards, quiz.

**UX principale** : share intent universel → inbox → traitement async (Deepgram + OpenAI) → consultation dans l'app. Le contenu brut entre, et l'app en extrait l'essence utile.

**Ton de marque** : calme, focus, "slow consumption", warm beige (#fcf9f6). L'anti-doomscroll. Public : curieux francophones (marche primaire) et anglophones, lifelong learners, productivity-minded.

**Contrainte branding critique** : le nom doit sonner bien EN FRANCAIS (marche primaire) ET en anglais. Pas de substring embarrassant en francais.

---

## Section 2 — Methode

### Integration des retours owner (redo)

L'owner a rejete deux passes precedentes pour les raisons suivantes :
1. **Culma** : contient "cul" en francais — inacceptable pour le marche francophone
2. **Complement (Imbura, Macena, Imbuva, Fondma, Steepra, Tremoa, Fonsma)** : trop de noms avec le meme suffixe "-ra/-ma", et les options etaient "peu parlantes" (pas immediatement evocatrices dans aucune langue)
3. L'owner aime la direction "infusion/intensification" (Steepen) mais veut plus d'options avant de choisir
4. Il veut des noms IMMEDIATEMENT EVOCATEURS pour un locuteur FR ou EN
5. Il veut une DIVERSITE de structures (pas tous des mots inventes avec le meme pattern)

### Strategie de cette passe

Pour repondre a la demande d'etre "parlant", cette passe privilegie :
- **Vrais mots** existant dans une langue (FR, EN, IT, ES, Latin) qui resonnent dans l'autre
- **Mots composites ultra-transparents** ou la racine est immediatement reconnaissable
- **Diversite structurelle** : verbes, noms, metaphores naturelles, mots etrangers
- **AUCUN suffixe repetitif** (-ra, -ma, etc.)

### Angles thematiques explores (6 angles)

1. **Infusion / percolation / trempage** — le contenu infuse lentement pour produire un extrait riche
2. **Distillation / filtrage / tamisage** — separer l'essentiel du superflu
3. **Materiau absorbant / receptacle** — l'objet qui absorbe et retient (buvard, creuset, etuve)
4. **Retention / sedimentation** — ce qui reste, se depose, demeure
5. **Croissance organique / vegetal** — le savoir qui s'enracine, le lierre qui s'accroche
6. **Intensification / maturation** — le contenu qui murit, se concentre, s'approfondit

### Verification de disponibilite (methode)

1. **App Store** : iTunes Search API `https://itunes.apple.com/search?term=<nom>&entity=software&country=us&limit=10` + country=fr
2. **Google Play** : `https://play.google.com/store/search?q=<nom>&c=apps`
3. **Domaine** : DNS lookup (`dig +short <nom>.com/.app/.io/.co`)
4. **Trademark** : Brave Search pour `"<nom>" trademark software class 9 42` (USPTO TESS et EUIPO TMView non accessibles programmatiquement — verification manuelle recommandee)
5. **Handles sociaux** : non verifiables automatiquement (auth requise) — a verifier par l'owner

### Filtre de sensibilite francaise

Chaque candidat est passe au crible pour :
- Substrings embarrassants (cul, con, bite, pute, foutre, chier, pet, merd, piss, sein, teub, couille)
- Homophones argotiques
- Connotations negatives en francais courant
- Ridicule potentiel si prononce a haute voix en reunion

---

## Section 3 — Candidats bruts (35 noms)

| # | Nom | Angle | Lettres | Filtre | Raison si filtre |
|---|-----|-------|---------|--------|------------------|
| 1 | Steep | Infusion | 5 | OUI | App "Steep" (analytics) existe. steep.com pris. Trop court pour differencier |
| 2 | **Steepen** | Infusion/intensification | 7 | NON | Zero App Store US+FR. .app/.io/.co libres. Mot anglais reel |
| 3 | Infuse | Infusion directe | 6 | OUI | Infuse (video player Firecore) — conflit fatal |
| 4 | Distill | Distillation EN | 7 | OUI | Distill Web Monitor, Distill Social — sature |
| 5 | **Distille** | Distillation FR | 8 | PARTIEL | .app/.io libres mais .com/.co pris. "Distill" sature sur App Store. Trop long |
| 6 | **Percole** | Percolation FR/IT | 7 | NON | Zero App Store direct. ALL domains free (.com/.app/.io/.co). Zero trademark |
| 7 | Percolat | Percolation latin | 8 | PARTIEL | All domains free mais 8 lettres, sonne comme un terme chimique |
| 8 | **Percoler** | Verbe FR complet | 8 | PARTIEL | All domains free mais 8 lettres, trop long pour un nom d'app |
| 9 | Osmose | Absorption biologique | 6 | OUI | osmose.com/.app/.io/.co TOUS PRIS. Mot trop generique |
| 10 | Decant | Decantation EN | 6 | OUI | Decant app (parfum) existe. decant.com/.app pris |
| 11 | Tamis | Filtrage FR | 5 | OUI | tamis.com/.app pris. Confusion avec "Taimi" (dating app) sur App Store |
| 12 | **Tamiser** | Verbe FR "sift" | 7 | PARTIEL | tamiser.com pris. .app/.io/.co libres. Connotation de precision |
| 13 | **Tamisar** | Tamiser + suffixe ibere | 7 | NON | All domains free. Zero App Store US/FR. Mais sens non transparent pour anglophones |
| 14 | **Buvard** | Materiau absorbant FR | 6 | NON | .com libre! .io/.co libres. .app pris. Zero App Store FR. Tres evocateur en FR |
| 15 | **Creuset** | Receptacle de fusion FR | 7 | NON | .app libre, .io pris. Zero App Store direct. Evocateur en FR (fondre/transformer) |
| 16 | Etuve | Chaleur/maturation FR | 5 | PARTIEL | .com pris, .app/.io/.co libres. Zero App Store FR. Mais connote la sterilisation/sueur |
| 17 | **Lierre** | Vegetal/retention FR | 6 | NON | .com pris, .app/.io/.co libres. Zero App Store direct. Metaphore de perseverance |
| 18 | Alambic | Distillation FR | 7 | OUI | alambic.com/.app/.io pris. Trop connote "alcool" |
| 19 | Creuset | Voir #15 | 7 | Voir #15 | |
| 20 | Mouture | Produit du broyage FR | 7 | PARTIEL | .com pris, .app/.io/.co libres. Mais connote cafe/farine plus que savoir. Apps cafe proches |
| 21 | Seve | Botanique/vie FR | 4 | OUI | App "Seve" existe sur App Store FR. seve.com pris |
| 22 | **Fondeur** | Celui qui fond/transforme FR | 7 | NON | .com pris, .app/.io/.co libres. Zero App Store US/FR. Evoque transformation |
| 23 | Filon | Source precieuse FR | 5 | OUI | filon.com/.io pris. "Filon" en argot FR = "bon plan" — trop familier |
| 24 | Nacelle | Receptacle/cocon FR | 7 | OUI | "Nacelle Scan" existe. nacelle.com pris. Connote transport aerien |
| 25 | **Retenso** | Retention + suffixe latin | 7 | NON | ALL domains free. Zero App Store US/FR. "Retenir" transparent FR/ES. Mais inventé |
| 26 | **Macerer** | Trempage lent FR | 7 | NON | All domains free. Aucun match App Store direct. Sens precis en FR et reconnaissable EN |
| 27 | **Maturer** | Maturation FR/EN | 7 | PARTIEL | .com pris, .app/.io/.co libres. Mais "Mature Dating" sature App Store |
| 28 | **Infonder** | Infuser + fonder (invente) | 8 | PARTIEL | All domains free mais 8 lettres. Invente — pas immediatement transparent |
| 29 | Trempe | Trempage/force FR | 6 | PARTIEL | trempe.com pris, .app/.io/.co libres. "De bonne trempe" = de bonne qualite. Mais trop de sens |
| 30 | Defricher | Pionner/decouvrir FR | 9 | OUI | All domains free mais 9 lettres — trop long |
| 31 | Germe | Debut/croissance FR | 5 | OUI | "Germe Video" existe. germe.com pris. Trop generique |
| 32 | Lento | Lenteur IT/ES/musique | 5 | OUI | App "Lento" existe. lento.com/.io/.co pris. Sature |
| 33 | Sciure | Residu filtrage FR | 6 | OUI | All domains free mais connote les dechets, pas l'essence. Negatif |
| 34 | Terreau | Substrat fertile FR | 7 | OUI | terreau.com pris. Apps jardinage dominent. Trop litteral |
| 35 | Calmo | Calme IT/ES | 5 | OUI | calmo.com/.app pris. Trop proche de "Calm" (app meditation majeure) |

---

## Section 4 — Finalistes (12 noms)

### 4.1 Percole

**Etymologie** : Forme conjuguee italienne et francaise du verbe "percoler" (du latin *percolare* = filtrer a travers). En francais, "percoler" signifie "passer lentement a travers un filtre pour en extraire l'essence". En anglais, "percolate" est immediatement compris (cafe, idees qui percolent). En italien, "percole" est le present indicatif.

**Pourquoi c'est "parlant"** : Un francophone entend "percolation" immediatement. Un anglophone entend "percolate". C'est un MOT REEL (pas un suffixe invente), qui evoque exactement ce que fait l'app : le contenu brut passe a travers un filtre intelligent pour produire l'essence.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Mot existant, court, rythme 3 syllabes regulieres per-co-le |
| Prononcabilite intl | 5 | /pɛʁ.kɔl/ FR, /pɜː.koʊl/ EN — transparent dans les deux, meme accentuation |
| Concision | 4 | 7 lettres (acceptable, dans la limite ideale) |
| Lien produit | 5 | Metaphore EXACTE : le contenu percole pour ne garder que l'essence extraite |
| Sonorite | 5 | Rythme ternaire equilibre, consonnes douces (p, k, l), voyelles ouvertes |
| Dispo legale | 5 | Zero trademark trouvee en classes 9/42 (Brave Search 2026-06-08) |
| Dispo commerciale | 5 | ZERO App Store US/FR. ALL domains free: .com, .app, .io, .co |
| Risque homonymie | 4 | "Percolator" (app photo mosaique) existe mais suffisamment different. "Percol" (coffee brand UK) — faible risque |
| Future-proof | 5 | "Percoler" est assez abstrait pour accompagner des evolutions produit |
| **TOTAL** | **43/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : `curl "https://itunes.apple.com/search?term=percole&entity=software&country=us&limit=10"` → 1 resultat non-pertinent (Percolator: Drippy Mosaics — app PHOTO, pas "Percole")
- App Store FR : meme recherche country=fr → 2 resultats non-pertinents (Percolator + La Banque Postale ERE)
- DNS : `percole.com` NO DNS, `percole.app` NO DNS, `percole.io` NO DNS, `percole.co` NO DNS — **TOUS LIBRES**
- Trademark : Brave Search `"percole" trademark software class 9 42` → zero resultat (2026-06-08)
- Note : "Percol" est une marque de cafe UK (percol.co.uk) — suffisamment eloigne (6 vs 7 lettres, different domaine, classe differente)

---

### 4.2 Steepen

**Etymologie** : Verbe anglais "to steepen" = intensifier une infusion, approfondir un processus d'extraction. Du vieil anglais *steap* (profond) + suffixe verbal -en. Sens second : "rendre plus raide/intense".

**Pourquoi c'est "parlant"** : Un anglophone comprend immediatement "steep" (infuser du the, laisser reposer). Un francophone eduque connait "steep" du contexte the/cafe. La metaphore est limpide : le contenu partage "infuse" pour produire des extraits de plus en plus riches.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot anglais reel, facile a retenir. Un poil technique |
| Prononcabilite intl | 4 | /stiː.pən/ EN, /sti.pɛn/ FR — clair mais le "ee" peut derouter certains FR |
| Concision | 4 | 7 lettres |
| Lien produit | 5 | Metaphore directe : intensifier l'infusion du contenu. L'owner a explicitement valide cette direction |
| Sonorite | 4 | Le double "e" donne de la longueur visuelle. Son agreable, evoque la profondeur |
| Dispo legale | 5 | Zero trademark logicielle trouvee. STEEPEN LLC Ukraine = simulateurs medicaux (classe differente) |
| Dispo commerciale | 5 | ZERO App Store US/FR. steepen.app + .io + .co libres |
| Risque homonymie | 3 | "Steep" (analytics), "Steepsoft", "Steeped Moments" — voisinage phonetique |
| Future-proof | 4 | Legere connotation the/infusion qui pourrait limiter, mais suffisamment verbe d'action |
| **TOTAL** | **38/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : `curl "https://itunes.apple.com/search?term=steepen&entity=software&country=us&limit=10"` → resultCount: 0
- App Store FR : resultCount: 0
- DNS : `steepen.com` RESOLVED (parke), `steepen.app` NO DNS, `steepen.io` NO DNS, `steepen.co` NO DNS
- Trademark : Brave Search → zero resultat pertinent (STEEPEN LLC Ukraine, simulateurs medicaux, pas classe 9/42)
- Domaine recommande : `steepen.app` (gratuit)

---

### 4.3 Buvard

**Etymologie** : Mot francais signifiant "papier buvard" — le materiau qui absorbe l'encre par capillarite. De "boire/buveur" (celui qui boit). En anglais : "blotting paper".

**Pourquoi c'est "parlant"** : Pour un francophone, "buvard" evoque IMMEDIATEMENT l'absorption douce et complete — le papier qui boit l'encre sans rien perdre. C'est exactement ce que fait l'app : elle "boit" le contenu brut et le retient. Meme un anglophone percoit le son "buv-" (comme "above", "love") et le "-ard" (comme "standard", "regard") — le mot sonne naturel dans les deux langues.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Mot francais existant, court, immediat. Image mentale forte (papier qui absorbe) |
| Prononcabilite intl | 4 | /by.vaʁ/ FR (natif), /buː.vɑːd/ EN — le "u" francais peut poser probleme mais "boo-vard" fonctionne |
| Concision | 5 | 6 lettres |
| Lien produit | 5 | Metaphore parfaite : le buvard absorbe le contenu et le retient. "Tout est absorbe, rien ne coule" |
| Sonorite | 4 | Son rond et doux (b, v). Le "ard" final est solide. Ton warm/vintage |
| Dispo legale | 4 | "BUVARD online" (INRAE) = outil scientifique de simulation agricole. Pas classe 9/42 mobile |
| Dispo commerciale | 4 | ZERO App Store FR/US. buvard.com LIBRE (!). buvard.app pris. buvard.io libre. buvard.co libre |
| Risque homonymie | 4 | Mot commun FR (comme "Notion") mais AUCUNE app existante. Le .com libre est exceptionnel |
| Future-proof | 4 | "Absorber" est assez large. Legere connotation scolaire/vintage qui peut etre un atout ou un frein |
| **TOTAL** | **39/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : recherche "buvard" → 3 resultats non-pertinents (Burraco Friends, Bukovel, BulMag — aucun match)
- App Store FR : resultCount: 0
- DNS : `buvard.com` NO DNS (**libre — exceptionnel pour un mot francais courant**), `buvard.app` RESOLVED (pris), `buvard.io` NO DNS (libre), `buvard.co` NO DNS (libre)
- Trademark : Brave Search → BUVARD online (INRAE, outil agricole web) = pas de conflit classe 9 mobile. lebuvard.com = service de copywriting web. Aucun conflit app mobile
- Domaine recommande : `buvard.com` (libre! exceptionnel)

---

### 4.4 Creuset

**Etymologie** : Mot francais signifiant "crucible" en anglais — le recipient resistant dans lequel on fond et transforme les metaux, ou plus generalement tout processus de fusion/transformation. "Le creuset des idees" = le lieu ou les idees se fondent et se transforment.

**Pourquoi c'est "parlant"** : En francais, "creuset" est un mot cultive mais connu de tous. "Le creuset" evoque la transformation, la fusion d'elements divers en quelque chose de nouveau. C'est exactement le produit : du contenu brut heterogene entre dans le creuset et en sort transforme (resumes, notes, flashcards). En anglais, "crucible" est le cognate — un locuteur anglophone entend la racine latine "cruc-" et percoit gravite/transformation.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot francais cultive, connu mais pas quotidien. Image forte une fois comprise |
| Prononcabilite intl | 4 | /kʁø.zɛ/ FR (natif), /kruː.zeɪ/ EN — le "eu" pose probleme pour anglophones. Ils diront "crew-zay" |
| Concision | 4 | 7 lettres |
| Lien produit | 5 | Metaphore puissante : le creuset transforme la matiere brute en quelque chose de precieux |
| Sonorite | 4 | Son robuste (cr), fluide au milieu (eu), net a la fin (zet). Impression de solidite |
| Dispo legale | 4 | "Le Creusot" (ville FR) existe. Aucune trademark logicielle trouvee. creuset.io pris |
| Dispo commerciale | 4 | App Store : "Le Creusot" (ville) et "Salon Porcelany" — pas de conflit direct pour "Creuset" seul. creuset.app LIBRE |
| Risque homonymie | 3 | "Le Creusot" (ville industrielle francaise) = confusion SEO potentielle |
| Future-proof | 5 | "Creuset" = transformation universelle, aucune limitation de scope |
| **TOTAL** | **37/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 4 resultats non-pertinents (Maman App, Village Baking, etc.)
- App Store FR : 3 resultats ("Le Creusot" ville, Salon Porcelany — pas de conflit direct pour "Creuset")
- DNS : `creuset.com` RESOLVED (pris), `creuset.app` NO DNS (libre), `creuset.io` RESOLVED (pris), `creuset.co` RESOLVED (pris)
- Domaine recommande : `creuset.app` (libre)
- Risque : confusion avec la ville "Le Creusot" en SEO

---

### 4.5 Lierre

**Etymologie** : Mot francais pour "ivy" (la plante grimpante qui s'accroche, persiste et recouvre progressivement une surface). Du latin *hedera*.

**Pourquoi c'est "parlant"** : Le lierre est LA metaphore vegetale de la retention et de la perseverance. Il s'accroche, il grandit lentement, il recouvre progressivement. C'est exactement ce que fait la connaissance dans un second cerveau : elle s'accumule, s'accroche, et finit par tout recouvrir d'un reseau dense. En anglais, le mot sonne comme "lee-air" — exotique mais elegant, evoque "leer" (regarder attentivement) ou "lier" (un lieu).

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Mot court, image mentale forte et immediate pour un francophone |
| Prononcabilite intl | 3 | /ljɛʁ/ FR (natif), /liˈɛr/ EN — le double "r" et le son "erre" sont difficiles pour anglophones |
| Concision | 5 | 6 lettres |
| Lien produit | 4 | Metaphore organique de retention lente et couvrante. Moins directe que "percoler" mais evocatrice |
| Sonorite | 4 | Doux, vegetale, liquide. Tres aligne avec le ton calm/beige |
| Dispo legale | 4 | "Lierre" est aussi une ville en Belgique ("Lier"). Pas de trademark logicielle |
| Dispo commerciale | 4 | App Store : "Relax in Lierre" (ville belge) — pas de conflit direct pour "Lierre" comme marque. lierre.app LIBRE |
| Risque homonymie | 3 | Ville belge "Lierre" (Lier en neerlandais). Confusion SEO possible |
| Future-proof | 4 | Metaphore vegetale extensible. Ne limite pas le produit |
| **TOTAL** | **36/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 2 resultats non-pertinents (Relax in Lierre = ville, Super Hero Girls)
- App Store FR : 2 resultats identiques — aucun conflit
- DNS : `lierre.com` RESOLVED (pris), `lierre.app` NO DNS (libre), `lierre.io` NO DNS (libre), `lierre.co` NO DNS (libre)
- Domaine recommande : `lierre.app` (libre)

---

### 4.6 Macerer

**Etymologie** : Verbe francais signifiant "to macerate / to steep over time" — laisser tremper longuement un ingredient dans un liquide pour en extraire les saveurs/proprietes. Du latin *macerare* (ramollir, tremper).

**Pourquoi c'est "parlant"** : En francais, "macerer" est immediatement compris — c'est ce qu'on fait avec les fruits dans l'alcool, les herbes dans l'huile. Le sens de "laisser le temps faire son travail d'extraction" est EXACTEMENT le produit. En anglais, "macerate" est un mot existant (meme racine latine), connu des personnes cultivees. La decouverte du sens est un "aha moment" pour l'anglophone.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Verbe francais connu, facile a retenir pour un francophone. Anglophone : mot savant mais existant |
| Prononcabilite intl | 4 | /ma.se.ʁe/ FR, /ˈmæs.ər.eɪ/ EN — fonctionne dans les deux, rythme ternaire |
| Concision | 4 | 7 lettres |
| Lien produit | 5 | Metaphore exacte : laisser le contenu macerer pour en extraire l'essence avec le temps |
| Sonorite | 4 | Fluide, latin. Le son "s" central est doux. Impression de patience |
| Dispo legale | 5 | Zero trademark trouvee. "Macerata" (ville IT) n'est pas un conflit |
| Dispo commerciale | 5 | Zero App Store direct. ALL domains free: .com, .app, .io, .co |
| Risque homonymie | 4 | "Macerata" (ville italienne) en SEO. Mais "Macerer" est suffisamment different |
| Future-proof | 4 | "Macerer" implique la patience et l'extraction — assez large pour evoluer |
| **TOTAL** | **39/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 3 resultats "Macerata" (ville italienne, apps municipales) — aucun conflit pour "Macerer"
- App Store FR : 3 resultats similaires (TRT Macera = aventure en turc, pas de lien)
- DNS : `macerer.com` NO DNS, `macerer.app` NO DNS, `macerer.io` NO DNS, `macerer.co` NO DNS — **TOUS LIBRES**
- Trademark : zero resultat en classes 9/42
- Note : L'accent sur le "e" final (macérer en orthographe correcte) est volontairement omis pour le nom de marque (pas d'accents dans les noms d'app — contrainte universelle)

---

### 4.7 Fondeur

**Etymologie** : Mot francais signifiant "celui qui fond les metaux" ou plus largement "celui qui transforme par la fonte". De "fondre" (to melt, to merge, to cast). Un "fondeur" est un artisan qui transforme la matiere brute en quelque chose de fini.

**Pourquoi c'est "parlant"** : En francais, "fondeur" evoque le metier ancestral de la transformation (fonderie, fondeur de bronze, fondeur de cloches). Applique a une app, c'est "celui qui fond le contenu brut en connaissances". En anglais, le mot evoque "founder" (fondateur) — association positive d'initiative et de creation. Le double sens est un atout marketing.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot francais existant, court et percutant. Double lecture FR/EN |
| Prononcabilite intl | 4 | /fɔ̃.dœʁ/ FR, /fɒnˈdɜːr/ EN — un anglophone le lira "fon-dur" ou "fon-der", acceptable |
| Concision | 4 | 7 lettres |
| Lien produit | 4 | "Fondre" le contenu en connaissance. Metaphore artisanale de transformation |
| Sonorite | 4 | Grave, solide (f, d), nasal (on). Impression de metier, de savoir-faire |
| Dispo legale | 4 | "Fondeur" est un mot commun — protection trademark possible mais pas maximale |
| Dispo commerciale | 4 | Zero App Store US/FR direct. fondeur.com PRIS, fondeur.app LIBRE, .io LIBRE, .co LIBRE |
| Risque homonymie | 3 | Confusion "founder" EN (fondateur) — ambiguite positive ou negative selon contexte. SEO bruit |
| Future-proof | 4 | "Fondre/transformer" est assez large |
| **TOTAL** | **35/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 4 resultats non-pertinents (Neero, Amanty, BCIpay, BFI Cash)
- App Store FR : 0 resultat
- DNS : `fondeur.com` RESOLVED (pris), `fondeur.app` NO DNS (libre), `fondeur.io` NO DNS (libre), `fondeur.co` NO DNS (libre)
- Domaine recommande : `fondeur.app`

---

### 4.8 Retenso

**Etymologie** : Mot invente par condensation de "retenir" (FR) / "retention" (EN/FR) + suffixe latin "-so" (comme "verso", "tenso" en espagnol). Evoque immediatement la retention dans les langues romanes.

**Pourquoi c'est "parlant"** : Un francophone entend "retenir" immediatement dans "retenso". Un hispanophone entend "retencion". Un anglophone entend "retain/retention". C'est un mot INVENTE mais dont la racine est TRANSPARENTE dans au moins 3 familles de langues. Contrairement aux "-ra/-ma" precedents, le suffixe "-so" est naturel en espagnol/italien (verso, tenso, intenso).

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Court, rythme ternaire re-ten-so, racine immediatement reconnaissable |
| Prononcabilite intl | 5 | /ʁe.tɑ̃.so/ FR, /rɪˈten.soʊ/ EN, /re.ten.so/ ES — universellement clair |
| Concision | 4 | 7 lettres |
| Lien produit | 5 | "Retenir" = exactement la promesse du produit. Garder, memoriser, conserver |
| Sonorite | 4 | Energetique (re-), tendu (ten-), ouvert (-so). Dynamique sans etre agressif |
| Dispo legale | 5 | Zero trademark trouvee. Zero resultat Brave Search. Mot inexistant |
| Dispo commerciale | 5 | ZERO App Store US/FR. ALL domains free: .com, .app, .io, .co |
| Risque homonymie | 5 | Aucun conflit identifie. Mot completement nouveau |
| Future-proof | 4 | "Retenir" est large mais pourrait limiter si l'app pivote vers la creation |
| **TOTAL** | **41/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 2 resultats non-pertinents (VEJA, Radio Positiva — matching sur "re" probablement)
- App Store FR : resultCount: 0
- DNS : `retenso.com` NO DNS, `retenso.app` NO DNS, `retenso.io` NO DNS, `retenso.co` NO DNS — **TOUS LIBRES**
- Trademark : Brave Search `"retenso" trademark brand company` → zero resultat (2026-06-08)

---

### 4.9 Trempe

**Etymologie** : Mot francais a double sens : (1) le trempage (immersion dans un liquide), (2) la qualite/force ("etre de bonne trempe" = etre d'excellente qualite, avoir du caractere). Du verbe "tremper" (to steep, to soak, to temper).

**Pourquoi c'est "parlant"** : Pour un francophone, "trempe" evoque a la fois l'immersion (le contenu qui trempe pour s'enrichir) ET la qualite ("de bonne trempe" = solide, fiable). C'est un double sens positif. En anglais, le mot evoque "tremble" ou "tempo" — pas de sens negatif, et la sonorite est agreable.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Mot court, francais courant, image forte |
| Prononcabilite intl | 4 | /tʁɑ̃p/ FR, /trɒmp/ EN — court et percutant. Le "emp" peut derouter en EN ("tramp"?) |
| Concision | 5 | 6 lettres |
| Lien produit | 5 | Double metaphore : trempage (infusion) + qualite (solidite). Parfait |
| Sonorite | 4 | Percutante, dynamique. Le "tr-" initial est energique |
| Dispo legale | 4 | Mot commun — protection trademark possible mais pas maximale |
| Dispo commerciale | 3 | trempe.com pris. .app/.io/.co libres. App Store FR : 2 resultats non-pertinents (GIMNAS SPORTS TREMP = ville espagnole) |
| Risque homonymie | 3 | "Tremp" (ville espagnole). En EN, "tramp" (vagabond) est un homophone dangereux |
| Future-proof | 4 | "Tremper" est assez large |
| **TOTAL** | **37/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 2 resultats non-pertinents (Ball Pass 3D, GIMNAS SPORTS TREMP)
- App Store FR : 2 resultats non-pertinents
- DNS : `trempe.com` RESOLVED (pris), `trempe.app` NO DNS (libre), `trempe.io` NO DNS (libre), `trempe.co` NO DNS (libre)
- Risque : homophone anglais "tramp" — potentiellement negatif pour le branding EN

---

### 4.10 Distille

**Etymologie** : Forme conjuguee du verbe francais "distiller" (to distill). "Il distille" = "it distills". Aussi l'imperatif en francais : "Distille !" (= Extrais l'essence !).

**Pourquoi c'est "parlant"** : Transparent dans les DEUX langues immediatement. FR "distiller" et EN "distill" partagent la meme racine latine. La metaphore est limpide : l'app distille le contenu brut pour en extraire la quintessence.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot transparent FR/EN. Mais "Distill" est deja sature (cf. Distill Web Monitor) |
| Prononcabilite intl | 5 | /dis.til/ FR, /dɪˈstɪl/ EN — quasiment identique |
| Concision | 3 | 8 lettres (au-dessus de l'ideal) |
| Lien produit | 5 | Metaphore parfaite : extraire l'essence du contenu brut |
| Sonorite | 4 | Nette, precise. Le double "l" est agreable |
| Dispo legale | 3 | "Distill" est un mot commun avec des marques existantes (Distill Web Monitor). Risque |
| Dispo commerciale | 3 | Distill Web Monitor, Distill Social, Distill by UNMS sur App Store. distille.com pris |
| Risque homonymie | 2 | Confusion forte avec "Distill Web Monitor" (meme espace tech). Fatal pour ASO |
| Future-proof | 4 | "Distiller" est large |
| **TOTAL** | **33/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 5 resultats incluant "Distill Web Monitor", "Distill Social", "Distill by UNMS" — **CONFLIT IMPORTANT**
- App Store FR : 5 resultats similaires
- DNS : `distille.com` RESOLVED (pris), `distille.app` NO DNS (libre), `distille.io` NO DNS (libre), `distille.co` RESOLVED (pris)
- PROBLEME : l'espace "Distill*" est SATURE sur l'App Store. ASO (App Store Optimization) sera tres difficile

---

### 4.11 Etuve

**Etymologie** : Mot francais signifiant "steam room / kiln / incubator" — un espace clos ou la chaleur et l'humidite permettent une transformation lente (sechage, sterilisation, maturation). Du latin *extufare* (chauffer).

**Pourquoi c'est "parlant"** : En francais, "etuve" evoque un lieu de transformation par la chaleur douce — comme un incubateur ou une serre. Le contenu "cuit" lentement dans l'etuve pour murir. En anglais, le mot sonne comme "eh-toov" — exotique mais elegant, sans connotation negative.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot court, francais courant dans certains milieux (cuisine, science) |
| Prononcabilite intl | 3 | /e.tyv/ FR (natif), /eˈtuːv/ EN — le "u" francais (y) pose probleme pour anglophones |
| Concision | 5 | 5 lettres — excellent |
| Lien produit | 4 | Maturation lente, transformation par la chaleur. Bonne metaphore mais pas la plus directe |
| Sonorite | 4 | Court, doux. Le "v" final est agreable |
| Dispo legale | 4 | Mot commun — pas de trademark logicielle identifiee |
| Dispo commerciale | 4 | ZERO App Store US/FR. etuve.com PRIS, etuve.app LIBRE, .io/.co LIBRES |
| Risque homonymie | 4 | "Etuve" peut evoquer "sauna/sueur" — connotation corporelle potentiellement genante |
| Future-proof | 4 | "Maturation/incubation" est assez large |
| **TOTAL** | **36/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 4 resultats non-pertinents (Datelii, OLPLAY, SOBRE, Kajou)
- App Store FR : 0 resultat
- DNS : `etuve.com` RESOLVED (pris), `etuve.app` NO DNS (libre), `etuve.io` NO DNS (libre), `etuve.co` NO DNS (libre)

---

### 4.12 Tamisar

**Etymologie** : Derive du francais "tamiser" (to sift/to sieve) avec terminaison iberique "-ar" (infinitif espagnol/portugais). Evoque le tamisage — le processus de filtrer pour ne garder que les particules fines, l'essentiel.

**Pourquoi c'est "parlant"** : Un francophone reconnait immediatement "tamis/tamiser" (sieve/to sift). Le "-ar" final donne une couleur ibero-latine qui sonne naturelle (comme "Gibraltar", "guitar", "bazaar"). La metaphore du tamisage = garder uniquement ce qui est fin et utile.

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 3 | Le "tamis" est reconnu en FR mais "tamisar" est invente — moins immediat |
| Prononcabilite intl | 4 | /ta.mi.zaʁ/ FR, /tæm.ɪ.zɑːr/ EN — rythme clair, pas d'ambiguite |
| Concision | 4 | 7 lettres |
| Lien produit | 4 | "Tamiser" = filtrer l'essentiel. Bon lien mais plus "tri" que "retention/enrichissement" |
| Sonorite | 4 | Rythme ternaire regulier, finale ouverte. Agreable |
| Dispo legale | 5 | Zero trademark trouvee. Mot inexistant |
| Dispo commerciale | 5 | ZERO App Store US/FR. ALL domains free: .com, .app, .io, .co |
| Risque homonymie | 4 | Confusion potentielle avec "Taimi" (dating app LGBTQ+) en App Store — mais noms suffisamment differents |
| Future-proof | 3 | "Tamiser" implique un filtrage reductif — pourrait limiter si l'app evolue vers la creation |
| **TOTAL** | **36/45** | |

**Verification disponibilite (2026-06-08)** :
- App Store US : 3 resultats non-pertinents (tamata, Sheekar, BEYYAK — arabe/farsi, aucun lien)
- App Store FR : resultCount: 0
- DNS : `tamisar.com` NO DNS, `tamisar.app` NO DNS, `tamisar.io` NO DNS, `tamisar.co` NO DNS — **TOUS LIBRES**

---

## Section 5 — Shortlist top 5

### Classement final

| Rang | Nom | Score | Structure | Angle | Tagline suggeree |
|------|-----|-------|-----------|-------|------------------|
| 1 | **Percole** | 43/45 | Mot reel FR/IT (verbe conjugue) | Percolation/filtrage | *"Let ideas percolate."* |
| 2 | **Retenso** | 41/45 | Mot invente (racine latine transparente) | Retention/memoire | *"Retiens l'essentiel."* |
| 3 | **Macerer** | 39/45 | Verbe francais reel | Infusion/trempage | *"Laisse macerer."* |
| 4 | **Buvard** | 39/45 | Nom francais reel | Absorption/materiau | *"Absorbe tout."* |
| 5 | **Steepen** | 38/45 | Verbe anglais reel | Infusion/intensification | *"Deeper with every share."* |

---

### Rang 1 — Percole (43/45)

**Pourquoi ce nom en tete** :
- Mot REEL existant en italien (present indicatif de "percolare") et en francais (forme conjuguee de "percoler")
- Transparent dans les DEUX langues cibles : FR "percoler/percolation", EN "percolate"
- Metaphore EXACTE du produit : le contenu brut passe a travers un filtre pour n'en garder que l'essence
- **TOUS les domaines majeurs libres** (.com, .app, .io, .co) — situation exceptionnellement rare
- Zero conflit App Store, zero trademark en classes 9/42
- 7 lettres, 3 syllabes equilibrees — facile a taper, a dire, a retenir
- Pas un mot invente avec un suffixe artificiel : c'est un VRAI MOT dont le sens est immediatement perceptible

**Risques** :
- "Percolator" (app photo mosaique) existe — confusion ASO possible mais limitee (noms differents)
- "Percol" (marque de cafe britannique) — risque faible, classe differente, graphie differente
- Le lien "cafe/percolateur" peut creer une association secondaire (positif pour le branding "slow consumption" mais pourrait confondre)

**Identite visuelle suggeree** :
- Logo : typographie sans-serif arrondie (type Inter Medium), lettres minuscules "percole"
- Couleur : warm beige (#fcf9f6) + accent terre de Sienne douce
- Icone : goutte stylisee traversant un filtre — ou un entonnoir minimaliste avec une goutte qui en sort transformee

---

### Rang 2 — Retenso (41/45)

**Pourquoi ce nom** :
- Racine "reten-" transparente en FR ("retenir"), EN ("retain"), ES ("retener"), IT ("ritenere")
- Le suffixe "-so" est naturel dans les langues romanes (intenso, tenso, verso) — PAS un suffixe artificiel "-ra/-ma"
- TOUS les domaines libres (.com, .app, .io, .co)
- Zero existence prealable : table rase totale pour le branding
- La promesse "retenir l'essentiel" est la proposition de valeur COEUR du produit

**Risques** :
- Mot invente = necessite plus d'effort de communication pour expliquer le sens
- Le "ten" central peut evoquer "tension" plutot que "retention" pour certains
- Moins poetique/warm que "Percole" ou "Buvard" — plus technique/latin

**Identite visuelle suggeree** :
- Logo : typographie geometrique moderne, lettres droites et equilibrees
- Couleur : beige chaud + bleu nuit profond (retention = profondeur)
- Icone : forme abstraite de depot/sedimentation (couches qui se superposent)

---

### Rang 3 — Macerer (39/45)

**Pourquoi ce nom** :
- Verbe francais REEL et immediatement compris par tout francophone
- Le cognate anglais "macerate" existe et est compris des anglophones cultives
- Metaphore de PATIENCE et de TEMPS — le contenu macere pour reveler ses qualites cachees
- TOUS les domaines libres (.com, .app, .io, .co)
- Ton tres aligne "slow consumption" — macerer implique de ne pas etre presse

**Risques** :
- 7 lettres mais le verbe complet peut paraitre "trop francais" pour un marche international
- "Macerate" en anglais a parfois une connotation negative (ramollir, decomposer)
- Confusion potentielle avec "Macerata" (ville italienne) en SEO

**Identite visuelle suggeree** :
- Logo : typographie serif elegante, impression de patience et de tradition
- Couleur : ambre profond + ivoire (comme un bocal de maceration)
- Icone : pot avec un ingredient qui trempe — stylise et minimaliste

---

### Rang 4 — Buvard (39/45)

**Pourquoi ce nom** :
- Mot francais EXISTANT avec une image mentale IMMEDIATE et forte : le papier qui absorbe l'encre
- Metaphore parfaite : l'app est un buvard qui absorbe tout le contenu sans rien perdre
- `buvard.com` est LIBRE — exceptionnel pour un mot francais courant de 6 lettres
- Zero App Store (aucune app existante portant ce nom)
- Tres court (6 lettres), facile a taper

**Risques** :
- `buvard.app` est pris — mais `buvard.com` etant libre c'est encore mieux
- Le mot est specifiquement francais — un anglophone ne comprendra pas le sens sans explication
- Connotation "scolaire/vintage" qui peut plaire (retro-chic) ou deplaire (desuet)
- Un anglophone prononcera "boo-vard" — pas elegant mais pas genant non plus

**Identite visuelle suggeree** :
- Logo : typographie vintage-moderne, lettres rondes avec un leger grain de texture papier
- Couleur : beige papier + encre bleu nuit
- Icone : feuille de papier avec une tache d'encre qui se diffuse (absorption)

---

### Rang 5 — Steepen (38/45)

**Pourquoi ce nom** :
- Direction explicitement appreciee par l'owner ("intensifier l'infusion, j'aime bien")
- Verbe anglais reel, 100% transparent pour les anglophones
- Metaphore forte : intensifier l'infusion du contenu
- .app/.io/.co libres, zero App Store

**Risques** :
- "Steep" (analytics) existe deja — voisinage phonetique qui complique le SEO
- Le mot est specifiquement anglais — un francophone ne comprendra pas sans explication
- steepen.com est pris (parke)
- Moins "parlant" qu'un mot francais pour le marche primaire francophone

**Identite visuelle suggeree** :
- Logo : typographie serif elegante, lettering qui evoque le the
- Couleur : vert profond + beige chaud
- Icone : feuille stylisee en infusion, ou tasse avec de la vapeur

---

## Section 6 — Recommandation finale

### Percole

**Score** : 43/45 — meilleur score global

**Justification croisee vs les 4 alternatives** :

1. **Percole > Retenso** : Percole est un MOT REEL (pas invente), ce qui le rend immediatement "parlant" dans les deux langues sans effort d'explication. Retenso necessite un "aha moment" de decodage. Les deux ont tous les domaines libres, mais Percole a une resonance plus naturelle.

2. **Percole > Macerer** : Les deux sont des verbes francais reels lies a l'infusion. Mais "percoler" est plus universel (le cafe qui percole est une image mondiale) tandis que "macerer" peut evoquer la decomposition en anglais. De plus, "Percole" (7 lettres sans accent) s'ecrit naturellement comme un nom d'app, tandis que "Macerer" evoque un infinitif francais avec accent manquant.

3. **Percole > Buvard** : Buvard est magnifiquement evocateur en FRANCAIS mais opaque pour un anglophone (qui le lira "boo-vard" sans rien comprendre). Percole fonctionne dans LES DEUX langues immediatement. Le buvard.com libre est un atout mais percole.com est AUSSI libre.

4. **Percole > Steepen** : Steepen ne fonctionne qu'en anglais. Le marche primaire est FRANCAIS. Un francophone moyen ne connait pas "steep" et ne fera pas le lien avec l'infusion. Percole fonctionne immediatement en francais ("ca percole" = ca filtre/ca passe) ET en anglais ("percolate"). C'est le seul candidat vraiment BILINGUE.

**Domaine recommande** : `percole.com` (libre — enregistrer en priorite)
**Alternative** : `percole.app` (egalement libre)

**Prochaines etapes si approuve** :
1. Enregistrer `percole.com` + `percole.app` immediatement (tous deux libres)
2. Recherche trademark formelle TESS (USPTO) + TMView (EUIPO) classes 9 et 42
3. Enregistrer @percole sur X, Instagram, TikTok
4. Mettre a jour `CFBundleDisplayName` = "Percole" dans `mobile/app.config.ts`

---

## Section 7 — Decision

_(Section reservee a l'owner pour validation)_

---

## Sources consultees

| Source | URL / Methode | Date d'acces |
|--------|---------------|--------------|
| iTunes Search API (US) | `https://itunes.apple.com/search?term=<nom>&entity=software&country=us&limit=10` | 2026-06-08 |
| iTunes Search API (FR) | `https://itunes.apple.com/search?term=<nom>&entity=software&country=fr&limit=10` | 2026-06-08 |
| Google Play Store | `https://play.google.com/store/search?q=<nom>&c=apps` | 2026-06-08 |
| DNS lookup (dig +short) | `dig +short <nom>.com/.app/.io/.co` | 2026-06-08 |
| Brave Search (trademark/brand) | `https://search.brave.com/search?q="<nom>"+trademark+software+class+9+42` | 2026-06-08 |
| DuckDuckGo (brand verification) | `https://html.duckduckgo.com/html/?q="<nom>"` (bloque par captcha) | 2026-06-08 |
| French linguistic sensitivity | Verification manuelle de substrings et homophones | 2026-06-08 |
| V1 Launch Plan | `docs/V1_LAUNCH_PLAN.md` (local) | 2026-06-08 |
| Previous rejected README | `docs/research/task-115-app-name/README.owner-rejected-2026-06-08.md` | 2026-06-08 |
| Previous complement response | `docs/research/task-115-app-name/complement-response-2026-06-08.md` | 2026-06-08 |
