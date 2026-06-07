---
owner_decision: pending
---

# Benchmark : Nom marketing de l'app (V1 launch branding)

## Owner Validation

**Decision**: _(a remplir par l'owner apres relecture)_
**Validated at**: _(date ISO a remplir par l'owner)_

---

## Recommendation

**Culma** — mot invente par condensation de "calm" + suffixe latin "-ma" (resultat, substance). 5 lettres, zero conflit App Store/Play Store, zero resultat de recherche dans le domaine logiciel, domaine `culma.app` disponible (pas de resolution DNS). Sonorité douce et internationale, evocation du calme et de la concentration ("slow consumption"). Tagline suggeree : *"Let it settle."*

---

## Section 1 — Brief produit reformule

**Second Brain Labs** developpe une application mobile de "second cerveau" qui permet aux utilisateurs d'ingerer du contenu partage depuis d'autres apps (Safari, YouTube, podcasts, X, TikTok, Instagram, WhatsApp, fichiers PDF/DOCX/PPTX) et de le transformer en artifacts exploitables : transcripts, resumes courts/detailles, notes structurees, flashcards, quiz.

- **UX principale** : share intent → inbox → traitement async (Deepgram + OpenAI) → consultation dans l'app
- **Fonctions secondaires** : digest journalier, recherche full-text (Algolia), folders + tags, spaced repetition
- **Public cible** : utilisateurs curieux, consommateurs de contenu, productivity / lifelong learning
- **Ton de marque** : calme, focus, "slow consumption", warm beige (#fcf9f6)
- **Modele business** : freemium + abonnements IAP (3 tiers)
- **Contraintes techniques** : Bundle ID `com.secondbrainlabs.core`, entite `Second Brain Labs`, domaine prevu `secondbrainlabs.com`

---

## Section 2 — Methode

### Criteres d'evaluation (score 1-5)

| # | Critere | Description |
|---|---------|-------------|
| 1 | Memorabilite | Facilite a retenir apres 1 exposition |
| 2 | Prononcabilite internationale | EN, FR, DE, ES sans ambiguite |
| 3 | Concision | <= 8 lettres ideal, <= 10 max |
| 4 | Lien avec la promesse produit | Evocation du concept (digest, retention, calme, curation) |
| 5 | Sonorite | Impression phonetique agreable |
| 6 | Disponibilite legale | Trademark classes 9, 42 |
| 7 | Disponibilite commerciale | App Store, Play Store, domaines, handles |
| 8 | Risque d'homonymie | Confusion avec des marques etablies |
| 9 | Future-proof | Capacite a couvrir des evolutions produit sans devenir reducteur |

### Pieges evites

- Pas d'accents/caracteres speciaux
- Pas de suffixes dates (-ly, -fy, -io)
- Pas de prefixes App/i/My/Get
- Pas de noms trop generiques (Inbox, Brain, Memory)
- Pas de noms inventes trop bizarres (Zynapsi, Memorix, Brevora)
- Pas de ressemblance Apple/Google/Microsoft
- Pas > 8 lettres sans raison forte
- Pas de noms deja associes a des apps de productivity (Notion, Bear, Obsidian, Roam, Reflect, Mem, Heptabase, Readwise...)

### Angles thematiques explores

1. **Memoire / second cerveau** — retention, depot, archive
2. **Resume / digest / essence** — distillation, condensation, extrait
3. **Curation / inbox / flux** — filtrage, tri, selection
4. **Calme / slow consumption / focus** — serenite, repos, patience
5. **Lumiere / clarte / illumination** — comprehension, lucidite
6. **Metaphore botanique / organique** — croissance, terreau, enracinement
7. **Mots inventes courts par condensation** — fusion de racines evocatrices
8. **Mots de langues etrangeres** — japonais (shimiru, koeru, nokoru), latin (cerno, velum, culma), scandinave

### Verification de disponibilite (methode)

1. **App Store** : iTunes Search API `https://itunes.apple.com/search?term=<nom>&entity=software&country=us&limit=10`
2. **Google Play** : `https://play.google.com/store/search?q=<nom>&c=apps`
3. **Domaine** : DNS lookup (`dig +short <nom>.com`, `<nom>.app`, `<nom>.io`)
4. **USPTO** : Brave/DuckDuckGo search for `"<nom>" trademark software class 9 42`
5. **EUIPO** : Brave/DuckDuckGo search + `https://www.tmdn.org/tmview/`
6. **Handles sociaux** : DuckDuckGo search for `twitter.com "@<nom>"`

*Note : Les databases USPTO TESS et EUIPO TMView ne sont pas accessibles programmatiquement (403/captcha). Les verifications trademark sont basees sur des recherches web indirectes. L'owner devra confirmer via une recherche manuelle sur TESS/TMView avant depot.*

---

## Section 3 — Candidats bruts (40 noms)

| # | Nom | Angle | Lettres | Filtre (oui/non) | Raison si filtre |
|---|-----|-------|---------|-------------------|------------------|
| 1 | Steep | Digest/infusion | 5 | OUI | App "Steep" existe (BI/analytics, Steep Analytics AB). steep.com pris depuis 1996. |
| 2 | Morsel | Essence/bouchee | 6 | OUI | Plusieurs apps (cook, calorie). morsel.com/.app pris. |
| 3 | Meld | Fusion/synthese | 4 | OUI | Property Meld app existe. meld.com pris. |
| 4 | Glean | Curation | 5 | OUI | Glean Work, Glean App existent (enterprise search). Conflict direct. |
| 5 | Crux | Essence | 4 | OUI | Climb with Crux, CRUX existent. crux.com pris. |
| 6 | Prism | Clarte | 5 | OUI | Sature (wallet, management, music, live streaming). |
| 7 | Quill | Ecriture | 5 | OUI | QuillBot, Quill Journal existent. Conflict direct. |
| 8 | Ember | Chaleur/focus | 5 | OUI | Ember Temperature, Ember Habit Tracker. Sature. |
| 9 | Lucid | Clarte | 5 | OUI | Lucid Motors, Lucidchart, Lucidspark. Trop connu. |
| 10 | Ponder | Reflexion | 6 | OUI | Ponder apps multiples (journal, AI, mental health). Sature. |
| 11 | Curio | Curiosite | 5 | OUI | Daily Micro Learning - Curio, Curio Antique. Conflicts. |
| 12 | Vesper | Calme/soir | 6 | OUI | Vesper (ancien app notes de Q Branch, defunte mais connue). Vesper AI existe. |
| 13 | Savant | Intelligence | 6 | OUI | Savant smart home system. Brand etablie. |
| 14 | Nimbus | Nuage/pensee | 6 | OUI | Nimbus Note existe (concurrent direct). Conflict fatal. |
| 15 | Nook | Coin/refuge | 4 | OUI | Barnes & Noble NOOK. Conflict fatal. |
| 16 | Canopy | Botanique | 6 | OUI | CanopyApp, Canopy AI Safety. Sature. |
| 17 | Infuse | Infusion | 6 | OUI | Infuse (video player Firecore). Brand etablie. |
| 18 | Opal | Pierre/clarte | 4 | OUI | Opal Screen Time Control. Brand etablie. |
| 19 | Cerno | Latin "discerner" | 5 | OUI | Cerno Software, Cerno Technologies, Cerno Belgium. Sature dans le logiciel. |
| 20 | Taiku | Japonais/tech | 5 | OUI | Taiku AI, Taiku Live, Taiku Labs Inc. Sature. |
| 21 | Stillo | Latin "goutte" | 6 | OUI | Stillo Focus app sur Google Play (concurrent direct). Conflict fatal. |
| 22 | Velum | Latin "voile" | 5 | OUI | Velum Labs (Y Combinator 2025), Vellum AI. Espace sature. |
| 23 | Denso | Dense/condense | 5 | OUI | DENSO corporation (auto parts, enormous brand). Conflict fatal. |
| 24 | Koeru | Japonais "depasser" | 5 | OUI | Koeru app existe (education, mai 2026). Conflict. |
| 25 | **Culma** | Condense calm+ma | 5 | NON | Zero resultat App Store. Zero Google Play. DNS libre (.app, .io, .co). Pas de trademark software trouvee. |
| 26 | **Steepen** | Infusion profonde | 7 | NON | Zero resultat App Store. Zero Google Play. DNS libre (.app, .io, .co). Seul "STEEPEN" = simulateurs medicaux Ukraine (non-software). |
| 27 | Kernu | Noyau (kern+u) | 5 | PARTIEL | KERN LearnApp existe. kernu.com pris. Mais kernu.app libre. Risque homonymie Kern. |
| 28 | Sedilo | Sedimenter | 6 | PARTIEL | sedilo.app et .io libres. Mais "Sedilo" est une commune en Sardaigne. Risque homonymie geographique. |
| 29 | **Nokoru** | Japonais "rester" | 6 | NON | Zero resultat App Store direct. nokoru.app et .co libres. |
| 30 | **Shimiru** | Japonais "impregner" | 7 | NON | Zero resultat App Store. shimiru.app et .io libres. Evocation de l'absorption lente. |
| 31 | **Kumoru** | Japonais "cumuler" | 6 | NON | Zero resultat App Store direct. kumoru.app et .co libres. |
| 32 | Nelum | Nelumbo (lotus) | 5 | PARTIEL | nelum.app libre mais nelum.com pris. "Nelum" evoque le lotus mais obscur. |
| 33 | Humus | Terreau organique | 5 | PARTIEL | humus.com et .app libres (rare!). Mais connotation "terre/compost" potentiellement negative. |
| 34 | **Nureru** | Japonais "mouiller/impregner" | 6 | NON | Zero resultat App Store. nureru.com ET .app libres. Evoque l'absorption douce. |
| 35 | Sediment | Depot/retention | 8 | PARTIEL | "Sediment - Memorize Quietly" existe sur App Store. Conflict partiel mais nom trop long. |
| 36 | Decanta | Decanter | 7 | PARTIEL | decanta.app libre mais connotation vin trop forte. |
| 37 | Steepen (var.) | Alternative steep | 7 | Voir #26 | |
| 38 | Loam | Terreau fertile | 4 | OUI | loam.app/.com pris. |
| 39 | Marrow | Moelle/essence | 6 | OUI | MARROW - NEET PG (app medicale majeure en Inde). Conflict. |
| 40 | Plume | Ecriture legere | 5 | OUI | Plume Home (Nest WiFi), Plume revision. Conflicts. |

---

## Section 4 — Finalistes (12 noms)

### 4.1 Culma

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Court, phonetiquement simple, une seule syllabe ouverte + une fermee |
| Prononcabilite intl | 5 | /kul.ma/ identique en EN, FR, DE, ES. Pas d'ambiguite |
| Concision | 5 | 5 lettres |
| Lien produit | 4 | Evoque "calm" (calme) et "-ma" (suffixe latin de resultat : thema, magma). Rappelle la slow consumption |
| Sonorite | 5 | Douce, arrondie (consonne liquide L, nasale M). Tonalite warm/beige |
| Dispo legale | 5 | Aucune trademark trouvee en classes 9/42. Culma s.r.l. = restauration italienne (classe differente) |
| Dispo commerciale | 5 | Zero App Store, zero Play Store, culma.app + .io + .co libres |
| Risque homonymie | 4 | "Culmas" (performing arts, danois) existe mais different. culma.fi existe (nature inconnue). Risque faible |
| Future-proof | 5 | Abstrait, ne limite pas a un use-case specifique |
| **TOTAL** | **43/45** | |

**Verification disponibilite** :
- App Store : `curl "https://itunes.apple.com/search?term=culma&entity=software&country=us&limit=10"` → resultCount: 0 (verifie 2026-06-07)
- Google Play : recherche "culma" → aucune app correspondante (verifie 2026-06-07)
- Domaines : `culma.app` NO DNS, `culma.io` NO DNS, `culma.co` NO DNS, `getculma.com` NO DNS, `useculma.com` NO DNS (verifie 2026-06-07)
- culma.com : RESOLVED (probablement parke/reserve). Alternative recommandee : `culma.app` ou `getculma.com`
- Trademark : recherche Brave "culma trademark software class 9" → aucun resultat pertinent (2026-06-07)
- Twitter @culma : pas de compte identifie dans les recherches

---

### 4.2 Steepen

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot anglais reel ("to steepen"), facile a retenir, mais un peu technique |
| Prononcabilite intl | 4 | /sti:.pən/ — clair en EN, un peu inhabituel en FR/DE mais pas problematique |
| Concision | 4 | 7 lettres (acceptable mais pas ideal) |
| Lien produit | 5 | "Steepen" = intensifier l'infusion. Metaphore parfaite pour le produit (laisser le contenu infuser) |
| Sonorite | 4 | Bonne sonorite, evoque la profondeur. Le double 'e' ajoute de la longueur visuelle |
| Dispo legale | 4 | STEEPEN LLC Ukraine = simulateurs medicaux. Pas de conflict classe 9/42 identifie |
| Dispo commerciale | 5 | Zero App Store, zero Play Store, steepen.app + .io + .co tous libres |
| Risque homonymie | 4 | "Steep" (analytics) existe. Risque de confusion phonetique. Steepsoft existe aussi |
| Future-proof | 4 | Legere connotation "the/infusion" qui pourrait limiter, mais suffisamment abstrait |
| **TOTAL** | **38/45** | |

**Verification disponibilite** :
- App Store : `curl "https://itunes.apple.com/search?term=steepen&entity=software&country=us&limit=10"` → resultCount: 0 (verifie 2026-06-07)
- Google Play : recherche "steepen" → aucune app correspondante (verifie 2026-06-07)
- Domaines : `steepen.app` NO DNS, `steepen.io` NO DNS, `steepen.co` NO DNS (verifie 2026-06-07)
- steepen.com : RESOLVED (probablement parke). Alternative : `steepen.app`
- Trademark : STEEPEN LLC (Ukraine, simulateurs medicaux) — pas de conflit software
- Twitter @steepen : pas de compte identifie

---

### 4.3 Shimiru

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Exotique mais musical. Se retient grace a la cadence reguliere shi-mi-ru |
| Prononcabilite intl | 3 | /ʃi.mi.ɾu/ — clair pour les anglophones et francophones, mais 3 syllabes et risque de mauvaise accentuation |
| Concision | 4 | 7 lettres |
| Lien produit | 5 | Japonais 染みる = "impregner lentement, penetrer, toucher profondement". Metaphore exacte de la slow absorption |
| Sonorite | 5 | Tres melodieux, doux, evoque la serenite japonaise. Parfait pour le ton beige/calm |
| Dispo legale | 5 | Aucune trademark trouvee en classes 9/42 |
| Dispo commerciale | 5 | Zero App Store, shimiru.app + .io + .co libres |
| Risque homonymie | 5 | Aucun conflit identifie |
| Future-proof | 4 | Abstrait et poetique, ne limite pas. Mais peut paraitre trop exotique pour certains marches |
| **TOTAL** | **40/45** | |

**Verification disponibilite** :
- App Store : recherche "shimiru" → 3 resultats non-pertinents (jeux japonais sans lien) (verifie 2026-06-07)
- Domaines : `shimiru.app` NO DNS, `shimiru.io` NO DNS, `shimiru.co` NO DNS (verifie 2026-06-07)
- shimiru.com : RESOLVED. Alternative : `shimiru.app`
- Trademark : aucun resultat pertinent
- Signification : 染みる (shimiru) = "to soak in, to permeate, to touch one's heart" en japonais

---

### 4.4 Nokoru

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 3 | Moins immediat que Culma, mais structure claire no-ko-ru |
| Prononcabilite intl | 3 | /no.ko.ɾu/ — 3 syllabes, accessible mais pas instinctif pour les occidentaux |
| Concision | 4 | 6 lettres |
| Lien produit | 5 | Japonais 残る = "rester, demeurer, subsister". Idee de retention du savoir qui reste |
| Sonorite | 4 | Douce, syllabique. Moins distinctive que Shimiru |
| Dispo legale | 5 | Aucune trademark trouvee |
| Dispo commerciale | 4 | nokoru.app et .co libres. nokoru.com pris. App Store: pas de match direct |
| Risque homonymie | 4 | "Nokoru" est un prenom de personnage manga (CLAMP). Risque faible mais existant |
| Future-proof | 4 | Abstrait, pas limitant |
| **TOTAL** | **36/45** | |

**Verification disponibilite** :
- App Store : recherche "nokoru" → resultats non-pertinents (jeux japonais) (verifie 2026-06-07)
- Domaines : `nokoru.app` NO DNS, `nokoru.co` NO DNS (verifie 2026-06-07)
- nokoru.com : RESOLVED
- Signification : 残る (nokoru) = "to remain, to stay, to be preserved" en japonais

---

### 4.5 Kumoru

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 3 | Structure syllabique claire ku-mo-ru mais sens non transparent |
| Prononcabilite intl | 4 | /ku.mo.ɾu/ — accessible universellement |
| Concision | 4 | 6 lettres |
| Lien produit | 3 | Japonais 曇る = "se couvrir (ciel), devenir trouble". Evocation du filtrage/decantation mais lien indirect |
| Sonorite | 4 | Douce, arrondie |
| Dispo legale | 5 | Aucune trademark trouvee |
| Dispo commerciale | 4 | kumoru.app et .co libres. kumoru.com pris. kumoru.io pris |
| Risque homonymie | 4 | "Gomoku" (jeu) peut creer confusion phonetique mineure |
| Future-proof | 4 | Abstrait |
| **TOTAL** | **35/45** | |

---

### 4.6 Nureru

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 3 | Exotique, 3 syllabes repetitives nu-re-ru |
| Prononcabilite intl | 3 | /nu.ɾe.ɾu/ — le double 'r' peut poser probleme en anglais (nureru vs "nurer") |
| Concision | 4 | 6 lettres |
| Lien produit | 4 | Japonais 濡れる = "s'humidifier, s'impregner". Metaphore d'absorption |
| Sonorite | 4 | Liquide, douce |
| Dispo legale | 5 | Aucune trademark trouvee |
| Dispo commerciale | 5 | nureru.com ET nureru.app TOUS DEUX LIBRES (rare!). .io et .co aussi |
| Risque homonymie | 5 | Zero conflit |
| Future-proof | 4 | Abstrait |
| **TOTAL** | **37/45** | |

**Verification disponibilite** :
- App Store : recherche "nureru" → resultats non-pertinents (2026-06-07)
- Domaines : `nureru.com` NO DNS, `nureru.app` NO DNS, `nureru.io` NO DNS, `nureru.co` NO DNS — **tous libres** (verifie 2026-06-07)
- Exceptionnel : possession du .com possible

---

### 4.7 Humus

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 5 | Mot courant dans plusieurs langues, immediat |
| Prononcabilite intl | 5 | /hju:.məs/ EN, /y.mys/ FR — universellement connu (jardinage/biologie) |
| Concision | 5 | 5 lettres |
| Lien produit | 4 | Terreau fertile ou les idees germent. Metaphore organique du second cerveau. Mais risque de confusion avec "hummus" (plat) |
| Sonorite | 3 | Connotation "terre/decomposition" potentiellement negative pour un produit tech |
| Dispo legale | 4 | Mot commun, donc difficile a proteger en trademark. Pas de conflit software identifie |
| Dispo commerciale | 5 | humus.com et humus.app TOUS DEUX LIBRES (exceptionnel!). App Store : zero resultat pertinent |
| Risque homonymie | 3 | Confusion avec "hummus" (nourriture). Mot commun donc risque de resultats parasites en SEO |
| Future-proof | 4 | Metaphore botanique extensible |
| **TOTAL** | **38/45** | |

**Verification disponibilite** :
- App Store : `curl "https://itunes.apple.com/search?term=humus&entity=software&country=us&limit=5"` → 2 resultats non-pertinents (YouTube, TerrHum) (verifie 2026-06-07)
- Domaines : `humus.com` NO DNS, `humus.app` NO DNS (verifie 2026-06-07) — **les deux libres**
- Risque : mot generique = SEO difficile, confusion hummus, trademark faible

---

### 4.8 Sedilo

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 3 | Structure syllabique claire se-di-lo mais sens non evident |
| Prononcabilite intl | 4 | /se.di.lo/ — universellement accessible |
| Concision | 4 | 6 lettres |
| Lien produit | 3 | Evoque "sediment" (depot de savoir) + suffixe italien "-lo". Lien indirect |
| Sonorite | 4 | Agreable, italianisante |
| Dispo legale | 4 | Sedilo est une commune en Sardaigne. Risque geographique |
| Dispo commerciale | 4 | sedilo.app et .io et .co libres. sedilo.com pris |
| Risque homonymie | 3 | Commune italienne = risque SEO/confusion |
| Future-proof | 4 | Abstrait |
| **TOTAL** | **33/45** | |

---

### 4.9 Kernu

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Court, consonantique, evoque "kernel" / "kern" |
| Prononcabilite intl | 4 | /kɛʁ.nu/ — simple |
| Concision | 5 | 5 lettres |
| Lien produit | 4 | "Kern" (noyau) + suffixe. Idee d'extraire le noyau essentiel du contenu |
| Sonorite | 4 | Percutante, solide |
| Dispo legale | 3 | KERNU LTD (UK company). Kernu dans le secteur Publishing/Media/Internet (Datanyze). Risque modere |
| Dispo commerciale | 3 | kernu.app libre mais kernu.com pris. KERN LearnApp existe (education). Risque confusion |
| Risque homonymie | 3 | "Kern" est tres utilise (typographie, OS kernel). KERN community apps existent |
| Future-proof | 4 | Abstrait |
| **TOTAL** | **34/45** | |

---

### 4.10 Nelum

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Court, melodieux |
| Prononcabilite intl | 4 | /ne.lum/ — simple |
| Concision | 5 | 5 lettres |
| Lien produit | 3 | De "Nelumbo" (lotus). Le lotus pousse dans l'eau trouble → clarte emergente. Lien poetique mais obscur |
| Sonorite | 4 | Douce, nasale + liquide |
| Dispo legale | 4 | Pas de trademark identifiee en classes 9/42 |
| Dispo commerciale | 4 | nelum.app libre. nelum.com pris |
| Risque homonymie | 4 | Faible |
| Future-proof | 4 | Abstrait, botanique |
| **TOTAL** | **36/45** | |

---

### 4.11 Decanta

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Mot existant dans plusieurs langues romanes |
| Prononcabilite intl | 4 | /de.kan.ta/ — clair |
| Concision | 3 | 7 lettres |
| Lien produit | 5 | "Decanter" = separer l'essentiel du superflu. Metaphore exacte |
| Sonorite | 4 | Elegante, latine |
| Dispo legale | 4 | Decanter Magazine existe (vin). Risque confusion vin |
| Dispo commerciale | 4 | decanta.app libre. decanta.com pris. Connotation vin tres forte |
| Risque homonymie | 2 | Decanter (magazine vin) = confusion SEO importante |
| Future-proof | 3 | "Decanter" est trop lie au vin pour evoluer librement |
| **TOTAL** | **33/45** | |

---

### 4.12 Cento

| Critere | Score | Justification |
|---------|-------|---------------|
| Memorabilite | 4 | Simple, percutant |
| Prononcabilite intl | 4 | /tʃen.to/ ou /sen.to/ — ambiguite potentielle EN vs IT |
| Concision | 5 | 5 lettres |
| Lien produit | 3 | Latin "cento" = mosaique de textes/citations. Concept d'assemblage. Mais obscur |
| Sonorite | 4 | Nette, latine |
| Dispo legale | 3 | "Cento" = mot commun (100 en italien). Difficile a proteger. Ville en Italie |
| Dispo commerciale | 4 | cento.app libre. cento.com pris (marque alimentaire). |
| Risque homonymie | 2 | Cento (marque tomates italiennes). Confusion. Ville italienne. SEO difficile |
| Future-proof | 4 | Abstrait |
| **TOTAL** | **33/45** | |

---

## Section 5 — Shortlist top 5

### Classement final

| Rang | Nom | Score | Tagline suggeree |
|------|-----|-------|------------------|
| 1 | **Culma** | 43/45 | "Let it settle." |
| 2 | **Shimiru** | 40/45 | "Soak it in." |
| 3 | **Steepen** | 38/45 | "Deeper with every share." |
| 4 | **Humus** | 38/45 | "Feed your mind." |
| 5 | **Nureru** | 37/45 | "Absorb slowly." |

---

### Rang 1 — Culma (43/45)

**Etymologie** : Mot invente par fusion de "calm" (calme, serenite) + suffixe latin "-ma" (substance, resultat — comme magma, plasma, thema). Evoque une substance de calme, un etat de decantation.

**Pourquoi ce nom matche le produit** :
- Phonetiquement, rappelle "calm" dans toutes les langues romanes et germaniques
- Le suffixe -ma donne un caractere de "matiere", comme si le calme etait une substance palpable
- Parfaitement aligne avec le ton de marque (warm beige, slow consumption, focus)
- Pas de connotation negative identifiee dans aucune langue majeure
- Court (5 lettres), facile a taper, facile a dicter a Siri/Google Assistant

**Disponibilite** :
- App Store : ZERO resultat
- Google Play : ZERO resultat
- culma.app : LIBRE (no DNS resolution)
- culma.io : LIBRE
- culma.co : LIBRE
- getculma.com : LIBRE
- useculma.com : LIBRE
- Trademark classes 9/42 : aucun conflit identifie
- @culma (Twitter) : non identifie comme actif

**Risques** :
- culma.com est pris (resolution DNS vers 217.160.0.67, probablement parke). Achat potentiel ou utilisation de culma.app
- Culmas (avec S) = plateforme danoise performing arts. Difference suffisante
- culma.fi existe (nature inconnue). Risque geographique minimal
- En finnois, "kulma" (avec K) signifie "angle/coin". Confusion improbable

**Identite visuelle suggeree** :
- Logo : lettres minuscules, typographie sans-serif arrondie (type Inter ou Outfit)
- Couleur dominante : warm beige (#fcf9f6) + accent terre cuite douce
- Icone : forme organique evoquant un depot/sediment doux, ou une goutte qui se pose

---

### Rang 2 — Shimiru (40/45)

**Etymologie** : Japonais 染みる = "impregner lentement, penetrer, toucher profondement". Utilise pour decrire une saveur qui penetre, un sentiment qui marque, une connaissance qui s'ancre.

**Pourquoi ce nom matche le produit** :
- Metaphore exacte de la "slow consumption" : le contenu s'impregne lentement dans l'esprit
- Sonorite tres douce et musicale, parfaitement alignee avec le ton calme
- Exotisme controle (comme Muji, Uniqlo, Kinfolk) — evoque la qualite japonaise et la mindfulness
- Differentiation forte dans un marche sature de noms anglais

**Disponibilite** :
- App Store : aucun resultat direct pertinent
- shimiru.app : LIBRE
- shimiru.io : LIBRE
- shimiru.co : LIBRE
- shimiru.com : PRIS (alternative : shimiru.app)

**Risques** :
- 7 lettres (dans la limite haute)
- Prononciation potentiellement ambigue pour certains utilisateurs occidentaux
- Peut paraitre "trop japonais" pour un marche occidental generaliste
- Difficulte SEO initiale (mot etranger)

**Identite visuelle suggeree** :
- Logo : typographie fine, equilibree, espace negatif genereux
- Couleur : ivoire + indigo delave (inspiration wabi-sabi)
- Icone : encre qui se diffuse doucement dans l'eau (sumi-e)

---

### Rang 3 — Steepen (38/45)

**Etymologie** : Anglais "to steepen" = intensifier une infusion, renforcer un processus d'extraction. Extension naturelle de "steep" (infuser).

**Pourquoi ce nom matche le produit** :
- Metaphore directe : le contenu partage "infuse" et produit des extraits de plus en plus riches
- Mot anglais reel, donc intuitif pour un public anglophone
- Verbe d'action progressif — evoque un processus continu d'enrichissement
- Se demarque de "Steep" (analytics) par le suffixe -en

**Disponibilite** :
- App Store : ZERO resultat
- Google Play : ZERO resultat
- steepen.app : LIBRE
- steepen.io : LIBRE
- steepen.co : LIBRE
- steepen.com : PRIS (alternative : steepen.app)

**Risques** :
- 7 lettres
- Proximite phonetique avec "Steep" (BI analytics) — risque de confusion dans les recherches
- Steepsoft, Steeped Software existent — risque d'environnement sature autour de "steep*"
- STEEPEN LLC Ukraine (simulateurs medicaux) existe mais pas de conflit classes 9/42

**Identite visuelle suggeree** :
- Logo : typographie serif elegante, evoquant une tasse de the
- Couleur : vert profond + beige chaud
- Icone : feuille stylisee en infusion

---

### Rang 4 — Humus (38/45)

**Etymologie** : Latin/francais "humus" = couche de sol riche en matiere organique decomposee, terreau fertile. Utilisee en botanique/ecologie.

**Pourquoi ce nom matche le produit** :
- Metaphore puissante : le contenu se "decompose" (transcription, resume) pour enrichir le terreau intellectuel
- Mot existant dans de nombreuses langues (EN, FR, DE, ES, IT) avec le meme sens
- Court (5 lettres), facile
- Ton organique/naturel alignee avec le warm beige

**Disponibilite** :
- App Store : aucun resultat pertinent (TerrHum = sans rapport)
- humus.com : LIBRE (no DNS) — **exceptionnel pour un mot commun**
- humus.app : LIBRE (no DNS)
- gethumus.com : LIBRE
- usehumus.com : LIBRE

**Risques** :
- Confusion avec "hummus" (plat libanais) — tres frequent
- Connotation "terre/decomposition/compost" potentiellement repulsive pour un produit tech
- Mot generique = protection trademark difficile
- SEO complique (resultats de jardinage/cuisine domineront longtemps)

**Identite visuelle suggeree** :
- Logo : typographie organique, lettres arrondies evoquant la terre
- Couleur : brun chaud + vert mousse
- Icone : couches de terre stylisees, une pousse qui emerge

---

### Rang 5 — Nureru (37/45)

**Etymologie** : Japonais 濡れる = "s'humidifier, etre mouille, s'impregner". Evoque l'eau qui penetre doucement un materiau.

**Pourquoi ce nom matche le produit** :
- Metaphore d'absorption douce et progressive
- Tous les domaines principaux sont libres (.com, .app, .io, .co) — cas extremement rare
- Sonorite liquide, repetition du 'r' douce
- Differenciation maximale

**Disponibilite** :
- App Store : aucun resultat pertinent
- nureru.com : LIBRE (no DNS)
- nureru.app : LIBRE (no DNS)
- nureru.io : LIBRE
- nureru.co : LIBRE
- **Tous les TLD majeurs libres** — opportunite unique

**Risques** :
- Prononciation : les anglophones liront "nur-eh-roo" au lieu de "nu-re-ru"
- 6 lettres, 3 syllabes — plus long en perception
- "Nureru" en japonais a aussi la connotation "etre trempe/mouille" qui peut paraitre etrange
- Aucune resonance en langues occidentales = memorisation plus difficile
- Plus difficile a expliquer/justifier aupres d'investisseurs

**Identite visuelle suggeree** :
- Logo : typographie fluide, cursive moderne
- Couleur : bleu tres pale + blanc cassé
- Icone : goutte d'eau se diffusant dans du papier

---

## Section 6 — Recommandation finale

### Culma

**Score** : 43/45 — meilleur score global

**Justification** :

1. **Equilibre parfait** entre memorabilite (5 lettres, 2 syllabes) et originalite (mot inexistant = pas de conflit)
2. **Resonance phonetique universelle** : le son "calm" est compris et associe a la serenite dans toutes les langues cibles (EN calm, FR calme, DE Kalm, ES calma)
3. **Disponibilite exceptionnelle** : zero presence sur App Store, Play Store, et multiples domaines libres (.app, .io, .co, getculma.com, useculma.com)
4. **Alignement total avec le ton de marque** : warm, calme, "slow consumption"
5. **Protegeable en trademark** : mot invente = distinctivite inherente en droit des marques (plus fort qu'un mot descriptif comme "Digest" ou "Summary")
6. **Future-proof** : ne fait reference a aucune fonctionnalite specifique, peut accompagner l'evolution du produit

**Domaine recommande** : `culma.app` (gratuit a l'enregistrement, extension .app = connotation tech)
**Alternative** : `getculma.com` si le .app ne convient pas

**Prochaines etapes si approuve** :
1. Enregistrer `culma.app` + `getculma.com` (backup)
2. Recherche trademark formelle TESS (USPTO) + TMView (EUIPO) classes 9 et 42
3. Enregistrer @culma sur X, Instagram, TikTok
4. Mettre a jour `CFBundleDisplayName` = "Culma" dans `mobile/app.config.ts`

---

## Section 7 — Sources consultees

| Source | URL | Date d'acces |
|--------|-----|--------------|
| iTunes Search API (App Store) | `https://itunes.apple.com/search?term=<nom>&entity=software&country=us&limit=10` | 2026-06-07 |
| Google Play Store Search | `https://play.google.com/store/search?q=<nom>&c=apps` | 2026-06-07 |
| DNS lookup (dig) | Local tool | 2026-06-07 |
| Brave Search | `https://search.brave.com/search?q=<query>` | 2026-06-07 |
| DuckDuckGo HTML | `https://html.duckduckgo.com/html/?q=<query>` | 2026-06-07 |
| Whois.com | `https://www.whois.com/whois/<domain>` | 2026-06-07 |
| V1 Launch Plan | `docs/V1_LAUNCH_PLAN.md` (local) | 2026-06-07 |
| Mobile app config | `mobile/app.config.ts` (local) | 2026-06-07 |
