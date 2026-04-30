---
owner_decision: redo
---

# Benchmark: Couts Unitaires + Proposition Pricing V1 (REDO 2026-04-29)

## Owner Validation

**Decision**: il faut remplacer la section concernant l'ocr par une section plus globale sur le parsing de documents en prenant en compte le cout de la solution de parsing validée task-90 (il faut prévoir le mode cost effective pour llamaparser (cf leur documentation à propos) et équivalent pour unstructured api. Souviens toi que la stratégie est llamaparser free tier jusqu'à épuisement puis unstructured api en fallback sur les 15 000 pages offertes puis switch sur pay as you go quand c'est épuisé).Aussi dans les estimations de cout en fonction des types de media et des quotas par type de media il faut considérer que les videos youtubes ne seront pas toutes transcrites par le transcripteur à 0.003€/min mais dans la plupart des cas on récupérera directement le transcript (captions ou ASR) depuis youtube. Prévoir 5% des cas où s'active le fallback et on où on doit transcrire le fichier mp3 de la vidéo youtube. Quand tu parles de rate limiting je veux que tu le chiffres concrètement en vue de la future implémentation. Refais une passe sur tout le benchmark afin de refaire tous les calculs totaux. 
**Validated at**: _(to be filled by owner)_

---

## Executive Summary

Cette reprise integre la decision validee dans `task-72` pour les modeles LLM:

- `summary_short`: `gpt-5-nano-2025-08-07`
- `summary_detailed`, `flashcards`, `notes`: `gpt-5.4-nano-2026-03-17`

Le cout LLM V1 complet passe a **0,0052 EUR par media** pour les 4 artefacts (`summary_short`, `summary_detailed`, `flashcards`, `notes`). C'est plus cher que l'ancienne hypothese Gemini Flash-Lite (~0,0015 EUR pour 3 artefacts), mais la transcription reste le cout dominant.

**Recommandation pricing actualisee:**

| Offre | Prix | Garde-fou recommande | Cout moyen / seuil |
|-------|------|----------------------|--------------------|
| Free trial | 0 EUR, 1 mois | Pas de quota marketing, monitoring + anti-abus | **2,99 EUR/user** en moyenne |
| Standard | 5 EUR/mois | **15 audio/video + 50 articles/textes + 10 OCR** | Cout 3,20 EUR, marge **36,1%** |
| Premium | 10 EUR/mois | Positionnement "fair use" plutot que vrai illimite | Non rentable sous 20% au-dela de profils detailles ci-dessous |

**Conclusion principale:** le tier 10 EUR ne doit pas etre vendu comme illimite sans garde-fou. Il reste rentable pour une utilisation intensive realiste si on surveille le mix media, mais un utilisateur audio-heavy devient non rentable sous 20% de marge des **73 medias/mois** environ.

---

## 1. Hypotheses Sources et Donnees Validees

### 1.1 Decisions projet prises en compte

| Sujet | Decision / hypothese | Source projet |
|-------|----------------------|---------------|
| Transcription audio/video | **0,0030 EUR/min** | Feedback owner dans `README.owner-rejected-2026-04-29.md` |
| Artefacts V1 | `summary_short`, `summary_detailed`, `flashcards`, `notes` | `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` |
| Modeles LLM | `summary_short`: GPT-5 nano; autres artefacts: GPT-5.4 nano | `docs/research/task-72-llm-artifact-benchmark/README.md` |
| OCR V1 | OCR dedie, pas LLM multimodal primaire | `docs/research/task-70-ocr-benchmark/README.md` |
| Pricing owner cible | 1 mois gratuit, puis 5 EUR avec quotas ou 10 EUR "theoriquement sans quota" si rentable | Rejet owner du 2026-04-29 |

### 1.2 Sources externes revues

- OpenAI API pricing: https://openai.com/api/pricing/
- OpenAI `gpt-5.4-nano`: https://developers.openai.com/api/docs/models/gpt-5.4-nano
- OpenAI release `gpt-5.4 mini and nano`: https://openai.com/index/introducing-gpt-5-4-mini-and-nano/
- USD/EUR spot historique du jour: https://www.x-rates.com/historical/?amount=1&date=2026-04-29&from=USD
- AWS Textract pricing: https://aws.amazon.com/textract/pricing/
- Google Cloud Vision pricing: https://cloud.google.com/vision/pricing

### 1.3 Conversion devise

Hypothese de calcul: **1 USD = 0,86 EUR**.

Ce taux est arrondi pour rester lisible. Les couts LLM et OCR etant faibles face a la transcription, une variation de change de +/-5% ne change pas la recommandation de quotas.

---

## 2. Couts Unitaires Actualises

### 2.1 Transcription

Base owner: **0,0030 EUR/min d'audio ou video processee**.

| Media | Hypothese | Cout transcription |
|-------|-----------|--------------------|
| Podcast long / video longue | 45 min | **0,135 EUR** |
| YouTube moyen | 25 min | **0,075 EUR** |
| TikTok / reel court | 1 min | **0,003 EUR** |
| WhatsApp audio | 3 min | **0,009 EUR** |
| Article / texte / OCR | pas d'audio | **0 EUR** |

### 2.2 LLM par artefact

Tarifs OpenAI retenus:

| Modele | Input | Output | Usage |
|--------|-------|--------|-------|
| GPT-5 nano | 0,05 USD / 1M tokens | 0,40 USD / 1M tokens | `summary_short` |
| GPT-5.4 nano | 0,20 USD / 1M tokens | 1,25 USD / 1M tokens | `summary_detailed`, `flashcards`, `notes` |

Calculs par artefact:

| Artefact | Modele | Input | Output | Cout USD | Cout EUR |
|----------|--------|-------|--------|----------|----------|
| `summary_short` | GPT-5 nano | 1 000 | 300 | 0,000170 | **0,000146** |
| `summary_detailed` | GPT-5.4 nano | 3 000 | 1 500 | 0,002475 | **0,002129** |
| `flashcards` | GPT-5.4 nano | 2 000 | 800 | 0,001400 | **0,001204** |
| `notes` | GPT-5.4 nano | 2 500 | 1 200 | 0,002000 | **0,001720** |
| **Total V1 complet** | mix task-72 | - | - | **0,006045** | **0,005199** |

**Lecture:** le cout complet des artefacts V1 est arrondi a **0,0052 EUR/media**.

Si `notes` n'est pas genere automatiquement pour tous les medias, le cout `summary_short + summary_detailed + flashcards` tombe a **0,00348 EUR/media**. Les calculs ci-dessous utilisent volontairement le cout V1 complet, plus prudent.

### 2.3 OCR

Hypothese maintenue: **0,0014 EUR/page** apres conversion, sur une base comparable AWS Textract / Google Cloud Vision a 0,0015 USD par page ou unite.

Hypothese media OCR moyen: **3 pages**.

**Cout OCR par media:** 3 x 0,0014 = **0,0042 EUR**.

### 2.4 Infrastructure

Hypothese conservee du benchmark precedent pour 100 utilisateurs actifs:

| Poste | Cout mensuel / user |
|-------|---------------------|
| S3 storage | 0,12 EUR |
| DynamoDB | 0,02 EUR |
| SQS | 0,00 EUR |
| Compute workers amortis | 0,60 EUR |
| **Total infra** | **0,74 EUR/user/mois** |

Sensibilite:

- A 50 users, l'infra peut monter vers **1,20 EUR/user/mois**.
- A 200 users, elle peut descendre vers **0,30 EUR/user/mois**.
- Les marges ci-dessous utilisent **0,74 EUR** pour rester comparables au benchmark precedent.

### 2.5 Cout complet par type de media

| Type media | Transcription | LLM V1 complet | OCR | Total |
|------------|---------------|----------------|-----|-------|
| Podcast / video longue 45 min | 0,1350 | 0,0052 | - | **0,1402 EUR** |
| YouTube moyen 25 min | 0,0750 | 0,0052 | - | **0,0802 EUR** |
| TikTok / reel 1 min | 0,0030 | 0,0052 | - | **0,0082 EUR** |
| Article / texte | - | 0,0052 | - | **0,0052 EUR** |
| WhatsApp audio 3 min | 0,0090 | 0,0052 | - | **0,0142 EUR** |
| Image / PDF scanne 3 pages | - | 0,0052 | 0,0042 | **0,0094 EUR** |

**Point important:** le changement LLM penalise surtout les medias texte et OCR en relatif, mais la rentabilite globale reste pilotee par l'audio/video long.

---

## 3. Cout Moyen du Mois Gratuit Sans Quota

### 3.1 Profils d'usage free trial

| Profil | Hypothese mensuelle | Cout media | Infra | Total |
|--------|---------------------|------------|-------|-------|
| Casual | 10 audio/video 45 min + 20 articles + 3 OCR | 1,53 EUR | 0,74 EUR | **2,27 EUR** |
| Moderate | 20 audio/video 35 min + 40 articles + 5 OCR | 2,46 EUR | 0,74 EUR | **3,20 EUR** |
| Intensive | 30 audio/video 40 min + 60 articles + 10 OCR | 4,16 EUR | 0,74 EUR | **4,90 EUR** |

### 3.2 Moyenne ponderee

Distribution prudente:

- 50% casual
- 35% moderate
- 15% intensive

Calcul:

```text
(0,50 x 2,27) + (0,35 x 3,20) + (0,15 x 4,90) = 2,99 EUR/user
```

**Cout moyen attendu du mois gratuit:** **2,99 EUR par utilisateur trial**.

### 3.3 Lecture business

Le mois gratuit sans quota est acceptable pour lancer si:

- la conversion trial -> paid est surveillee des le depart;
- un anti-abus existe: limite journaliere, detection bulk import, alerte cout individuel;
- le marketing "sans quota" ne veut pas dire absence de rate limiting technique.

Sans carte bancaire et avec acquisition froide, le risque de cout est eleve. Avec carte bancaire ou waitlist qualifiee, le cout moyen de 2,99 EUR reste defendable.

---

## 4. Tier Standard 5 EUR avec Marge 30%

### 4.1 Budget cout

| Ligne | Montant |
|-------|---------|
| Prix | 5,00 EUR |
| Marge cible | 30% |
| Cout maximum total | 3,50 EUR |
| Infra | 0,74 EUR |
| Budget media disponible | **2,76 EUR** |

### 4.2 Quotas possibles

| Scenario | Quotas | Cout total | Marge |
|----------|--------|------------|-------|
| Conservateur | 15 audio/video + 40 articles + 8 OCR | 3,13 EUR | 37,4% |
| Recommande | **15 audio/video + 50 articles + 10 OCR** | **3,20 EUR** | **36,1%** |
| Max audio raisonnable | 16 audio/video + 50 articles + 10 OCR | 3,34 EUR | 33,3% |
| Limite proche 30% | 17 audio/video + 45 articles + 8 OCR | 3,43 EUR | 31,3% |
| Trop agressif | 18 audio/video + 40 articles + 8 OCR | 3,57 EUR | 28,6% |

### 4.3 Recommandation Standard

Recommander:

- **15 podcasts/videos par mois** sur base 45 min moyenne;
- **50 articles/textes par mois**;
- **10 images/PDF scannes par mois**.

Marge attendue: **36,1%**.

Pourquoi ne pas monter directement a 17 audio/video:

- la moyenne 45 min peut etre depassee par les podcasts longs;
- l'infra a bas volume peut etre superieure a 0,74 EUR/user;
- le cout LLM peut augmenter si `notes` devient plus long ou si retries JSON sont necessaires;
- il faut garder une reserve pour Stripe, support, logs, monitoring et variations de change.

### 4.4 Variante credits

Pour eviter trois compteurs visibles, on peut exprimer le Standard en credits:

| Media | Credits |
|-------|---------|
| Audio/video long 45 min | 10 credits |
| Article / texte | 0,4 credit |
| OCR 3 pages | 0,7 credit |

Allocation Standard: **150 credits/mois**.

Cette variante est plus flexible mais plus difficile a expliquer. Pour V1, des quotas par type de media sont plus clairs et plus faciles a monitorer.

---

## 5. Tier Premium 10 EUR: Seuils de Non-Rentabilite

### 5.1 Budget cout

| Ligne | Montant |
|-------|---------|
| Prix | 10,00 EUR |
| Marge minimale acceptable | 20% |
| Cout maximum total | 8,00 EUR |
| Infra | 0,74 EUR |
| Budget media disponible | **7,26 EUR** |

Equation de cout:

```text
cout_total =
  (audio_45min x 0,1402)
+ (articles x 0,0052)
+ (ocr_3pages x 0,0094)
+ 0,74
```

### 5.2 Seuils par profil

| Profil | Mix | Dernier point >=20% marge | Premier point <20% marge |
|--------|-----|---------------------------|---------------------------|
| Audio-heavy | 70% audio/video, 25% articles, 5% OCR | **72 medias** = 50 audio + 18 articles + 4 OCR => 7,88 EUR cout, 21,2% marge | **73 medias** = 51 audio + 18 articles + 4 OCR => 8,02 EUR cout, 19,8% marge |
| Balanced | 40% audio/video, 50% articles, 10% OCR | **121 medias** = 48 audio + 61 articles + 12 OCR => 7,90 EUR cout, 21,0% marge | **122 medias** = 49 audio + 61 articles + 12 OCR => 8,04 EUR cout, 19,6% marge |
| Text-heavy | 25% audio/video, 65% articles, 10% OCR | **184 medias** = 46 audio + 120 articles + 18 OCR => 7,98 EUR cout, 20,2% marge | **185 medias** = 47 audio + 120 articles + 18 OCR => 8,12 EUR cout, 18,8% marge |

### 5.3 Interpretation

Le 10 EUR peut donner une experience "quasi illimitee" pour les utilisateurs texte-heavy, mais pas pour les gros consommateurs de podcasts/videos longs.

Le risque principal n'est pas le nombre total de medias, c'est le nombre de minutes audio/video:

- 50 medias audio/video de 45 min = 2 250 minutes traitees;
- cout transcription seul = 6,75 EUR;
- avec LLM + infra, on est deja proche du seuil de 20% de marge.

### 5.4 Recommandation Premium

Ne pas lancer en "vrai illimite" sans garde-fou.

Recommandation produit:

- message public: **Premium 10 EUR: usage intensif avec fair use**;
- pas de quota dur visible au depart si l'UX doit rester premium;
- monitoring individuel obligatoire;
- alertes internes a 6 EUR et 7,50 EUR de cout mensuel;
- throttling ou contact user si l'utilisateur depasse durablement les seuils.

Garde-fou technique defendable:

| Limite fair use | Cout si tout est consomme |
|-----------------|---------------------------|
| 45 audio/video 45 min + 100 articles + 20 OCR | **7,76 EUR cout total**, marge **22,4%** |

Ce garde-fou permet jusqu'a **165 medias/mois** pour un usage text-heavy, tout en evitant le scenario audio-heavy non rentable.

---

## 6. Comparaison avec Concurrents

| Concurrent | Prix indicatif | Limite dominante | Positionnement face a nous |
|------------|----------------|------------------|----------------------------|
| Snipd Premium | ~6,99 EUR/mois | 900 min audio/mois | Standard est moins cher mais avec moins d'audio; Premium peut depasser en valeur si mix multi-media |
| Otter.ai Pro | ~8,49 EUR/mois | 1 200 min transcription/mois | Produit centre transcription; nous ajoutons articles, OCR, notes, flashcards |
| Readwise Full | ~9,99 USD/mois | lecture/highlights, pas audio natif equivalent | Premium 10 EUR est comparable si l'audio/video est une vraie valeur |
| mymind | >10 EUR/mois selon plan | capture visuelle/knowledge base | Notre Standard 5 EUR est plus accessible; Premium doit assumer fair use |

Positionnement recommande:

- **Standard 5 EUR**: entree accessible, quotas lisibles, bon fit etudiants/pros modere.
- **Premium 10 EUR**: pas "unlimited" pur; vendre la capacite intensive multi-media et la priorite de traitement.

---

## 7. Recommandation Finale

### 7.1 Offre a lancer

Lancer avec:

1. **Mois gratuit**
   - 1 mois;
   - pas de quota marketing;
   - rate limit technique et monitoring cout;
   - cout moyen attendu: **2,99 EUR/user**.

2. **Standard 5 EUR/mois**
   - **15 audio/video**;
   - **50 articles/textes**;
   - **10 OCR**;
   - marge attendue: **36,1%**.

3. **Premium 10 EUR/mois**
   - lancement seulement si le wording "fair use" est accepte;
   - seuils de monitoring bases sur cout individuel;
   - garde-fou interne: **45 audio/video + 100 articles + 20 OCR** ou equivalent cout;
   - marge attendue au garde-fou: **22,4%**.

### 7.2 Decision a prendre par owner

Le choix strategique se resume ainsi:

| Option | Avis |
|--------|------|
| Free trial + Standard 5 EUR seulement | **Recommande pour V1 launch**: simple, marge saine, limite le risque |
| Ajouter Premium 10 EUR des le launch avec fair use | Viable si le messaging assume que "illimite" veut dire usage raisonnable |
| Premium 10 EUR vraiment sans quota ni fair use | **Non recommande**: audio-heavy non rentable a partir d'environ 73 medias/mois |

### 7.3 Impact du nouveau routing LLM

Par rapport au benchmark precedent:

- le cout moyen du mois gratuit passe de **2,82 EUR** a **2,99 EUR**;
- le Standard recommande passe de **15/40/8** a **15/50/10** tout en gardant **36,1%** de marge;
- le seuil Premium balanced descend d'environ **125 medias** a **121 medias**;
- le seuil Premium text-heavy descend d'environ **200 medias** a **184 medias**;
- le vrai changement business reste limite car l'audio/video domine le cout.

---

## 8. Risques et Mitigations

### 8.1 LLM retries et JSON

`flashcards` et `notes` peuvent necessiter validation JSON/retry.

Mitigation:

- budgeter 10-20% de marge LLM supplementaire dans les dashboards;
- stocker les artefacts par fingerprint pour eviter toute regeneration inutile;
- monitorer cout par artefact et taux de retry.

### 8.2 Audio long

Les podcasts de 90-120 min cassent les moyennes.

Mitigation:

- compter les audio/video en minutes dans le backend, meme si le pricing visible est par media;
- plafonner ou avertir au-dela de 45 min dans les calculs de fair use;
- ajouter une limite journaliere pour eviter l'import massif.

### 8.3 Infra bas volume

Le cout infra de 0,74 EUR/user suppose environ 100 users.

Mitigation:

- commencer avec workers plus petits;
- autoscaling agressif;
- revoir les marges a 25, 50, 100, 200 users.

### 8.4 Stripe, TVA, frais platform

Les calculs ci-dessus sont des couts techniques, pas une marge comptable complete.

Decision owner a clarifier avant implementation billing:

- les prix 5 EUR / 10 EUR sont-ils TTC ou HT?
- faut-il integrer frais Stripe et taxes dans la marge cible?

Si 5 EUR est TTC en France, la marge technique reste utile mais la marge business reelle sera inferieure.

---

## 9. Sources

### Projet

- `docs/research/task-72-llm-artifact-benchmark/README.md`
- `docs/research/task-70-ocr-benchmark/README.md`
- `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md`
- `docs/CANONICAL_MEDIA_API_CONTRACT.md`
- `docs/research/task-65-pricing-v1-benchmark/README.owner-rejected-2026-04-29.md`

### Fournisseurs

- OpenAI pricing: https://openai.com/api/pricing/
- OpenAI `gpt-5.4-nano`: https://developers.openai.com/api/docs/models/gpt-5.4-nano
- OpenAI `gpt-5.4 mini/nano` release: https://openai.com/index/introducing-gpt-5-4-mini-and-nano/
- AWS Textract pricing: https://aws.amazon.com/textract/pricing/
- Google Cloud Vision pricing: https://cloud.google.com/vision/pricing
- USD/EUR historical: https://www.x-rates.com/historical/?amount=1&date=2026-04-29&from=USD
