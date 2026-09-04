---
owner_decision: pending   # pending | ok | abandoned | redo | more
---

# Benchmark : publier les pages légales exigées par le paywall, sans domaine possédé

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — texte libre décrivant la décision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes précises de correction à intégrer au prochain passage)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Option A1 — acheter un `.com`, mettre la zone chez Cloudflare, servir deux pages statiques sur Cloudflare Pages depuis le dépôt, et exposer l'adresse de contact via Cloudflare Email Routing.**

**Coût douze mois : ~11 $** (le seul poste non nul est l'enregistrement du nom de domaine). Hébergement 0 $, TLS 0 $, DNS 0 $, adresse de contact 0 $.

Quatre arguments, dans l'ordre de force :

1. **Le domaine n'est pas un coût imputable aux pages légales.** Il est déjà un prérequis dur de trois autres choses écrites au dépôt : le host de l'API (`api.<domaine>`, support Terraform déjà présent — `docs/V1_LAUNCH_PLAN.md:1771`), l'adresse **publiée par Apple** au titre du formulaire commerçant DSA (`docs/V1_LAUNCH_PLAN.md:1261-1272`), et la vérification de domaine Sign in with Apple, qui exige de servir `/.well-known/apple-developer-domain-association.txt` sur le domaine (`docs/V1_LAUNCH_PLAN.md:1775`). Le coût **marginal** des deux pages légales, une fois le domaine acheté, est nul — et le même site statique sert aussi ce fichier `.well-known`, l'URL de support (métadonnée obligatoire côté Apple) et l'URL marketing.
2. **Deux des URL de métadonnées Apple ne sont pas modifiables sans nouvelle version.** Vérifié deux fois sur la documentation Apple : le tableau d'éditabilité ne coche pas « Editable » pour Privacy Policy URL ni pour Support URL, et la page d'aide conclut « Any changes to the URLs releases with your next app version ». Le bon moment pour figer le nom d'hôte définitif est donc **avant** la première soumission — c'est-à-dire maintenant, où rien n'a été soumis et où le changement coûte zéro.
3. **Les sous-domaines gratuits ne sont interdits par aucune règle de store, mais deux des trois candidats sont interdits par leurs propres CGU.** GitHub Pages : « GitHub Pages is not intended for or allowed to be used as a free web hosting service to run your online business […] or providing commercial software as a service (SaaS) », plus « GitHub reserves the right at all times to reclaim any GitHub subdomain ». Vercel Hobby : « Hobby teams are restricted to non-commercial personal use only ». Les pages légales d'une app à abonnement payant tombent dans ces clauses. Cloudflare Pages est le seul des trois dont la page de limites n'énonce que des limites techniques.
4. **Les textes existent déjà et sont plus exacts qu'un générateur ne peut l'être.** `docs/compliance/privacy-policy.md` (199 lignes) et `terms-of-service.md` (213 lignes) nomment les sous-traitants réels. Or Google exige que la politique décrive les pratiques effectives « not limited by the data disclosed in the Data safety section » : un questionnaire de générateur ne sait pas que Deepgram et OpenAI sont dans le chemin. Payer 60 à 180 $/an à un générateur achète une **veille juridique** et un hébergement, pas une conformité — et livre en prime une URL sur le domaine du fournisseur, ce qui contredit l'argument 2.

**Compromis explicitement acceptés :**

- **Un renouvellement annuel à ne pas oublier.** C'est le seul vrai risque de l'option : un domaine expiré fait tomber `/privacy`, `/terms`, l'API et l'adresse de contact d'un coup. Mitigation : auto-renouvellement activé avec une carte valide, et le mail est déjà le canal d'alerte du projet.
- **Le DNS reste hors Terraform.** Il l'est déjà : aucune ressource `aws_route53_zone` n'existe dans `infrastructure/terraform`. Mettre la zone chez Cloudflare ne dégrade donc aucune couverture IaC existante ; ça ajoute deux enregistrements à créer à la main (validation ACM et `api`), parce que le module crée le certificat en `validation_method = "DNS"` **sans** créer l'enregistrement de validation, et parce que l'alias `aws_route53_record.api` est conditionné à `api_zone_id`, qui restera vide (`infrastructure/terraform/modules/platform/lambda_api.tf:249-294`).
- **Une variante A2 existe** — tout chez AWS : zone dans Route53, pages en S3 + CloudFront, le tout dans Terraform. Elle fait fonctionner l'alias `api` tel qu'il est déjà écrit, coûte 6 $/an de plus (zone hébergée Route53 à 0,50 $/mois), demande un module Terraform neuf pour deux fichiers HTML, et **perd Email Routing**, qui exige que la zone soit chez Cloudflare. Comme l'adresse publiée est une obligation DSA vérifiée par code, perdre le transfert d'e-mail gratuit coûte plus cher que gagner un enregistrement Terraform. À noter, un panachage est possible : la documentation Cloudflare précise qu'un **sous-domaine** peut pointer sur un projet Pages sans que la zone soit chez Cloudflare (« If you are deploying to a subdomain, it is not necessary for your site to be a Cloudflare zone »), seul l'apex l'exige.
- **Aucune preuve de terrain n'est produite ici.** Voir §2 et §9 : les moteurs de recherche joignables depuis cet environnement ont tous servi des défis anti-robots ou des résultats hors sujet. Ce benchmark ne s'appuie donc que sur les textes normatifs et sur les CGU des hébergeurs — datés et vérifiables — et refuse de présenter du folklore comme un fait constaté.

---

## 0. Deux affirmations du dépôt à corriger

Ces deux points changent la portée du problème. Ils sont signalés ici pour la tâche d'implémentation ; **aucun fichier de `mobile/` n'est modifié par ce benchmark**.

### 0.1 La citation « guideline 3.1.2 » est imprécise

L'en-tête de `mobile/src/constants/legal.ts` et la description de la tâche attribuent l'obligation de liens sur l'écran d'achat à la **guideline 3.1.2 d'Apple** et à « la politique d'abonnement de Google Play ». Le texte de la guideline 3.1.2 (consulté le 2026-09-04) ne contient pas cette phrase, et la politique **Subscriptions** de Google Play n'en contient aucune non plus. La chaîne réelle est celle-ci.

| Ce qui oblige | Texte exact | Source (consultée le 2026-09-04) |
|---|---|---|
| Liens Privacy Policy **et** Terms of Use accessibles **dans l'app**, au titre de la divulgation d'un abonnement auto-renouvelable | « You clearly and conspicuously disclose to users the following information regarding Your auto-renewing subscription: Title […] Length […] Price […] **Links to Your Privacy Policy and Terms of Use must be accessible within Your Licensed Application.** » | Apple Developer Program License Agreement, **Schedule 2, §3.8(b)** — <https://developer.apple.com/programs/apple-developer-program-license-agreement/> |
| Lien politique de confidentialité en métadonnée **et** dans l'app | « All apps must include a link to their privacy policy in the App Store Connect metadata field **and within the app** in an easily accessible manner. » | App Review Guidelines **5.1.1(i)** — <https://developer.apple.com/app-store/review/guidelines/> |
| URL fonctionnelles à la soumission | « Submissions to App Review […] should be final versions with all necessary metadata and **fully functional URLs** included; placeholder text, **empty websites**, and other temporary content should be scrubbed before submission. » | App Review Guidelines **2.1(a)**, même URL |
| App **et** métadonnées doivent porter les deux liens | « Please note that your app and App Store metadata must include links to your Terms of Use and Privacy Policy. » | Apple, page Subscriptions — <https://developer.apple.com/app-store/subscriptions/> |
| Côté Google : lien dans la Play Console **et** lien **ou texte** dans l'app | « All apps must post a privacy policy link in the designated field within Play Console, and a privacy policy link **or text** within the app itself. » | Play, politique **User Data** — <https://support.google.com/googleplay/android-developer/answer/10144311> |

Conséquences pratiques :

- **La substance du commentaire est juste** — l'écran d'achat doit porter les liens, et c'est contractuel (Schedule 2 §3.8(b)), pas seulement éditorial — mais **la référence est fausse**. À corriger dans une tâche de documentation.
- **Google n'exige aucun lien vers des conditions d'utilisation.** L'obligation « Terms of Use » est purement Apple. Ce n'est pas une raison de retirer le lien côté Android, mais ça change ce qui est bloquant : sans page de conditions, c'est iOS qui casse, pas Android.
- **Google accepte du *texte* in-app** à la place d'un lien. Un écran natif portant la politique satisferait le volet in-app côté Play — mais **pas** le champ URL de la Play Console, ni la métadonnée Apple. Une URL publique reste inévitable dans tous les cas de figure.

### 0.2 « Une URL embarquée ne se corrige que par une nouvelle version » est faux pour cette app

La description de la tâche pose cette prémisse (dimension 7). Elle est vraie pour **une** des trois surfaces, et fausse pour les deux autres.

| Surface | Modifiable comment | Preuve |
|---|---|---|
| `TERMS_URL`, `PRIVACY_POLICY_URL`, adresse de contact — constantes JS | **OTA**, sans build ni review | `mobile/app.config.ts` déclare `updates.url = https://u.expo.dev/<projectId>` et `runtimeVersion.policy = "fingerprint"` ; changer une chaîne ne déplace pas l'empreinte native, donc l'update est servi au binaire installé. `mobile/eas.json` : profil `production` → `channel: "production"`. Quotas de l'offre gratuite : 1 000 MAU, updates illimités (`mobile/MOBILE_CI_CD.md`) |
| **App Store Connect → Privacy Policy URL** (et **Support URL**) | **Nouvelle version obligatoire** | Tableau « Required, localizable, and editable properties » : Privacy Policy URL et Support URL sont Required + Localizable, colonne *Editable* **vide** ; le tableau se définit lui-même comme listant « the properties that can be localized and edited at any time without submitting a new version of your app ». Confirmé par la page « Manage app privacy » : « **Any changes to the URLs releases with your next app version.** » |
| **Play Console → Privacy Policy** | **Immédiat**, sans release | « If you've previously added a privacy policy and want to make changes, you'll see and select **Manage** instead of Start » — <https://support.google.com/googleplay/android-developer/answer/9859455> |

S'y ajoute une nuance déjà documentée au dépôt : les binaires installés avant le 2026-09-03 (TestFlight `1.0.0 (2)`, piste interne Play `1.0.0 (5)`) **ne recevront jamais d'OTA** et devront être remplacés une fois (`mobile/MOBILE_CI_CD.md`). Ça ne change rien à l'analyse : ils ne sont pas en production.

**Ce que ça implique pour le choix** : le seul artefact réellement collant est l'URL de politique de confidentialité côté Apple. Elle est gratuite à poser correctement aujourd'hui et coûte une version après la première soumission. C'est l'argument décisif pour choisir l'hôte définitif **avant** de soumettre, plutôt que de partir sur un sous-domaine gratuit et de migrer ensuite.

---

## 1. Le cahier des charges réel : ce que les règles contraignent, c'est la page, pas l'hôte

Extrait des textes cités en §0.1 et de la politique **User Data** de Google, voici la liste exhaustive des critères qu'une option doit satisfaire. C'est la grille utilisée dans le tableau du §3.

**Sur le lien :**

1. Présent dans le champ de métadonnée du store (App Store Connect **et** Play Console) — Apple 5.1.1(i), Play User Data.
2. Présent **dans l'app**, « in an easily accessible manner » — Apple 5.1.1(i) ; et pour un abonnement, accessible dans l'app avec le titre, la durée et le prix — ADPLA Schedule 2 §3.8(b).
3. **Fonctionnel** au moment de la review, sans page vide ni contenu provisoire — Apple 2.1(a).

**Sur la page (Google, politique User Data, verbatim) :** « Please make sure your privacy policy is available on an active, publicly accessible and non-geofenced URL (no PDFs) and is non-editable. » Soit quatre critères indépendants, plus quatre critères de contenu :

4. **Active** — répond, pas de 404.
5. **Publiquement accessible** — pas de mur de connexion, pas de « Request access ».
6. **Non géo-restreinte** — joignable depuis les territoires de distribution.
7. **Pas un PDF.**
8. **Non modifiable** (par le visiteur).
9. Contenu : « Developer information and a privacy point of contact **or a mechanism to submit inquiries** ».
10. Contenu : types de données collectées, partagées, et avec qui ; procédures de sécurité ; politique de conservation et de suppression.
11. **Étiquetage clair** : « Clear labeling as a privacy policy (for example, listed as "privacy policy" in title) ».
12. **Identification** : « The entity […] named in the app's Google Play store listing must appear in the privacy policy or the app must be named in the privacy policy ».

**Rien, dans aucun de ces textes, ne porte sur le nom d'hôte.** Ni Apple ni Google n'exigent que l'URL soit sur un domaine appartenant à l'éditeur, ni qu'elle soit « cohérente avec l'éditeur ». Le critère 12 est la seule exigence de cohérence, et elle porte sur le **contenu** de la page (le nom de l'entité ou de l'app doit y figurer), pas sur son hôte.

Deux remarques qui découlent directement de cette grille :

- **Le critère 8 (« non-editable ») est celui qui disqualifie les documents partagés.** Un lien Google Docs en `/edit`, ou un partage réglé « peut modifier », échoue par construction. Un document « publié sur le web » (`/pub`) ou une page Notion publiée en lecture seule satisfont la lettre du critère. La différence entre les deux n'est pas un détail de configuration : c'est la différence entre conforme et non conforme.
- **Le critère 7 (« no PDFs ») est absolu** et disqualifie l'idée, tentante, de déposer les `.md` du dépôt convertis en PDF quelque part.

### 1bis. Ce qu'Apple héberge déjà pour vous, et qui réduit le périmètre

Deux faits vérifiés qui changent le nombre de pages à publier :

- **Sans EULA personnalisée, l'EULA standard d'Apple s'applique** : « Apple provides a standard end-user license agreement (EULA) that applies in all countries and regions. If you don't provide a custom EULA, the standard EULA is applied to your app and the license agreement link isn't shown on your App Store product page. » (<https://developer.apple.com/help/app-store-connect/manage-app-information/provide-a-custom-license-agreement>). Ce texte est hébergé par Apple à <https://www.apple.com/legal/internet-services/itunes/dev/stdeula/> (HTTP 200 le 2026-09-04). Le volet **métadonnée** de l'obligation « Terms of Use » est donc satisfait sans rien publier.
- Une EULA personnalisée se saisit **en texte brut** dans App Store Connect (« enter your custom EULA as a plain text document. All HTML tags are stripped »), et ce champ-là **est** modifiable à tout moment (tableau d'éditabilité, ligne License Agreement, colonne *Editable* cochée).

Conséquence : le **strict minimum** publiable est **une seule page**, la politique de confidentialité, le lien « conditions d'utilisation » du paywall pointant sur l'EULA standard hébergée par Apple. Ce benchmark ne le recommande pas — l'EULA standard couvre la licence de l'application, pas un service serveur avec abonnement, tarification et usage acceptable, et le projet a déjà rédigé ses propres conditions — mais l'owner doit savoir que le nombre de pages à héberger est un choix, pas une contrainte, et que sur un hébergeur statique la deuxième page coûte 0 $ et zéro minute de plus.

---

## 2. La question du nom d'hôte : ce que la règle exige contre ce que l'examen observe

### 2.1 Côté règle écrite : rien n'impose un domaine

Recherche faite dans les quatre textes normatifs (App Review Guidelines intégrales, ADPLA, politique User Data de Google, politique Subscriptions de Google) : **aucune occurrence** d'une exigence de nom d'hôte, de domaine propre, ou de cohérence entre le domaine et l'éditeur. La grille du §1 est exhaustive. Un `*.pages.dev`, un `*.github.io`, un `sites.google.com/view/...` ou un `*.notion.site` qui satisfait les douze critères satisfait la règle écrite.

### 2.2 Côté pratique d'examen : ce que ce benchmark peut et ne peut pas affirmer

**Ce qu'il ne peut pas.** L'AC#2 demande des faits datés sur les refus constatés. Je n'en produis aucun, et c'est un choix. Les moteurs de recherche joignables depuis cet environnement ont tous échoué : DuckDuckGo (HTML et lite), Mojeek, Ecosia et plusieurs instances SearXNG ont servi des défis anti-robots ou des 429 ; Reddit et l'API Stack Exchange sont inaccessibles ; Brave Search a répondu à quatre requêtes puis est passé en 429 puis en captcha ; Bing ignore les opérateurs entre guillemets et a renvoyé, sur deux requêtes ciblées, dix résultats sans rapport (Wikipédia, CNIL, dictionnaires). Je n'ai donc **aucun rapport de refus de première main, daté et vérifiable** à citer. Écrire « on constate que Notion passe » ou « les examinateurs refusent les sous-domaines gratuits » serait de l'opinion déguisée en source, ce que la tâche interdit explicitement.

**Ce qu'il peut, et qui vaut mieux qu'une anecdote.** Trois faits contractuels, datés, opposables, qui tranchent la question des sous-domaines gratuits sans passer par la pratique d'examen :

| Fait | Texte exact | Source (consultée le 2026-09-04) |
|---|---|---|
| GitHub Pages interdit contractuellement l'usage commercial | « GitHub Pages is intended to host static web pages, but primarily as a showcase for personal and organizational projects. GitHub Pages is **not intended for or allowed to be used** as a free web hosting service to run your online business, e-commerce site, or any other website that is primarily directed at either facilitating commercial transactions or **providing commercial software as a service (SaaS)**. » | <https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features> |
| …et se réserve la reprise du sous-domaine | « GitHub reserves the right at all times to reclaim any GitHub subdomain » | même page |
| Vercel Hobby interdit l'usage commercial | « Hobby teams are restricted to **non-commercial personal use only**. All commercial usage of the platform requires either a Pro or Enterprise plan. Commercial usage is defined as any Deployment that is used for the purpose of financial gain of anyone involved in any part of the production of the project » | <https://vercel.com/docs/limits/fair-use-policy> |
| Cloudflare Pages, offre gratuite : uniquement des limites techniques | « Below are limits observed by the Cloudflare Free plan » — 500 builds/mois, 1 build simultané, 20 000 fichiers par site, 25 Mio par fichier, 100 domaines personnalisés par projet. Aucune clause d'usage non commercial sur cette page. | <https://developers.cloudflare.com/pages/platform/limits/> |

Ce que ça implique : le risque, pour un sous-domaine gratuit, **ne vient pas de la review**, il vient de l'hébergeur. Une page légale hébergée en violation des CGU de son hébergeur est une page qui peut disparaître sur signalement, et l'URL qui la désigne est gravée dans une métadonnée Apple non modifiable sans nouvelle version (§0.2). C'est un risque asymétrique : gain 11 $, perte potentielle une version bloquée avec une politique de confidentialité 404.

**Deux mécanismes de refus, en revanche, sont écrits noir sur blanc** et suffisent à classer les options sans anecdote :

- Apple 2.1(a) parle de « **empty websites** » et de contenu provisoire à nettoyer. Une page légale minimale n'est pas un site vide, mais une URL qui pointe sur un espace de démarrage d'hébergeur, un « coming soon » ou une page sans le texte attendu tombe dans cette phrase.
- Google, critères 5 et 8 du §1 : un lien de partage mal réglé qui affiche « Demander l'accès », ou un document dont le visiteur peut modifier le contenu, échoue sur la lettre du texte.

**Comment obtenir la preuve de terrain, si l'owner la veut.** Elle est disponible à coût nul et sans anticipation : le champ **Privacy Policy URL** peut être renseigné dans App Store Connect et le champ Play Console rempli avant toute soumission ; la review de la première soumission est elle-même l'observation. En cas de refus, le Resolution Center d'Apple et le motif de rejet Play citent le critère exact — ce sont les seules sources de première main qui vaudront quelque chose pour ce projet.

---

## 3. Tableau comparatif

Sept options, couvrant les cinq familles demandées. « Grille §1 » = les douze critères de règle écrite. « Risque propre » = ce que l'option ajoute comme risque au-delà de la règle.

| # | Option | Famille | Hôte de l'URL | Grille §1 | Risque propre à l'option | Coût 12 mois | Déménagement ultérieur |
|---|---|---|---|---|---|---|---|
| **A1** | Domaine acheté + Cloudflare Pages, zone chez Cloudflare | Domaine acheté + hébergement statique | `<domaine>` (apex ou sous-domaine), contrôlé par le projet | ✅ les 12 | Oubli de renouvellement (tout tombe : pages, API, e-mail) | **~11 $** (domaine seul) | Aucun besoin : l'hôte change derrière une URL stable. 301 possible indéfiniment |
| **A2** | Domaine acheté + S3 + CloudFront, zone dans Route53 | Domaine acheté + hébergement statique | `<domaine>`, contrôlé par le projet | ✅ les 12 | Surface Terraform neuve (bucket, OAC, distribution, certificat en `us-east-1`, invalidations) pour deux fichiers HTML | **~17 $** (domaine + zone Route53 6 $) | Idem A1 |
| **B** | Cloudflare Pages sur `*.pages.dev`, sans domaine | Pages d'un hébergeur de code | `<projet>.pages.dev` | ✅ les 12 | URL marquée fournisseur ; adresse de contact obligatoirement hors domaine ; ne résout ni le host API ni le `.well-known` Sign in with Apple | **0 $** | Le projet Pages peut porter un `_redirects` en 301 tant que le compte vit — mais l'URL Apple exige **une nouvelle version** |
| **C** | GitHub Pages sur `<compte>.github.io` | Pages d'un hébergeur de code | `<compte>.github.io` | ✅ les 12 sur le papier | ❌ **Interdit par les CGU** (usage commercial / SaaS) et sous-domaine reprenable à tout moment par GitHub | **0 $** | Idem B, plus le risque de perdre le sous-domaine sans préavis |
| **D** | Générateur + hébergement fournisseur (iubenda, Termly) | Générateur/hébergeur payant | `iubenda.com/...` ou domaine Termly | ✅ les 12, sous réserve du critère 12 (nommer l'entité/l'app) | Lock-in : l'URL appartient au fournisseur ; arrêt de l'abonnement = page morte ; texte généré moins exact que celui du dépôt | **60 $ à 180 $/an** (détail §4) | Résiliation = page morte, donc **une nouvelle version** côté Apple. Aucun 301 possible |
| **E** | Google Sites (`sites.google.com/view/...`) | Service de site tiers | `sites.google.com` | ✅ les 12 | Contenu hors dépôt (dérive avec `docs/compliance/*.md`) ; URL marquée fournisseur ; aucune redirection possible | **0 $** | Aucun 301 : déménager casse l'ancienne URL, donc **une nouvelle version** côté Apple |
| **F** | Document publié : Google Docs « publier sur le web », ou page Notion publiée | Document partagé publiquement | `docs.google.com/.../pub` ou `*.notion.site` | ⚠️ conforme **seulement** si publié en lecture seule ; un lien `/edit` ou un partage « peut modifier » échoue au critère 8, un partage restreint échoue au critère 5 | Le réglage de partage est le point de rupture, et il est silencieux : personne ne prévient quand la page repasse en privé | **0 $** | Aucun 301. Idem E |

Lecture du tableau : **quatre options sur sept satisfont la règle écrite** (A1, A2, B, E, et F sous condition), **une est disqualifiée par les CGU de son hébergeur** (C), et **une est disqualifiée par son coût au regard de ce qu'elle apporte** (D, voir §6). Le classement se fait donc sur les deux dernières colonnes, pas sur la conformité.

---

## 4. Coût sur douze mois, poste par poste

Tous les tarifs relevés le 2026-09-04 sur les pages officielles des fournisseurs.

| Poste | A1 | A2 | B | C | D (iubenda / Termly) | E | F |
|---|---|---|---|---|---|---|---|
| Nom de domaine `.com`, 1re année | 11,08 $ (Porkbun, « .COM from $11.08 ») ou au coût registre via Cloudflare Registrar | idem | — | — | — | — | — |
| Renouvellement annuel | même ordre, au coût registre chez un registrar sans marge | idem | — | — | — | — | — |
| DNS | 0 $ (Cloudflare) | 6 $ (Route53 : 0,50 $/zone/mois) | 0 $ | 0 $ | 0 $ | 0 $ | 0 $ |
| Hébergement des pages | 0 $ (Pages, offre gratuite) | ~0 $ (S3 + CloudFront ; deux fichiers HTML, trafic négligeable) | 0 $ | 0 $ | inclus | 0 $ | 0 $ |
| Certificat TLS | 0 $ (automatique) | 0 $ (ACM) | 0 $ | 0 $ | 0 $ | 0 $ | 0 $ |
| Adresse de contact | 0 $ (Email Routing, « Available on Free and Paid plans ») | 0 $ à 0 $ selon fournisseur choisi (§7) | boîte grand public : 0 $ | 0 $ | 0 $ | 0 $ | 0 $ |
| Abonnement générateur | — | — | — | — | **59,88 €/an** (iubenda Essentials, 4,99 €/site/mois facturé à l'année) pour politique + cookies ; le générateur *Terms and Conditions* est un produit distinct, sur les paliers supérieurs affichés à 19–21 €/site/mois, soit ~240 €/an. **Termly** : offre gratuite = 1 politique ; Starter 10 $/site/mois à l'année = **120 $/an** (2 politiques) ; Pro+ 15 $/site/mois à l'année = **180 $/an** (politiques illimitées) | — | — |
| **Total 12 mois** | **~11 $** | **~17 $** | **0 $** | **0 $** | **60 $ à 240 $** | **0 $** | **0 $** |

Notes de fiabilité sur ces chiffres :

- Le prix Porkbun est affiché « from $11.08 » : c'est un prix d'appel, à revérifier au panier pour le nom retenu (les noms « premium » sont facturés autrement).
- Cloudflare Registrar est décrit comme « At-cost domain registration and renewal […] Only pay the registration and renewal fees charged by your registry » : pas de tarif affiché sur la page produit, donc pas de chiffre cité ici. C'est le seul mécanisme qui garantit l'absence de marge à l'année 2, là où beaucoup de registrars pratiquent un prix d'appel puis un renouvellement plus élevé.
- Les hausses de prix de gros du registre `.com` programmées par Verisign existent mais **n'ont pas pu être vérifiées dans cette passe** (la page de Verisign a redirigé vers son accueil). Budgéter une dérive de quelques dollars sur trois ans, sans chiffre ici.
- Pour A2, le palier gratuit permanent de CloudFront n'a pas pu être extrait de la page de tarifs (rendu JavaScript). Le coût réel est de l'ordre de quelques centimes par mois pour deux fichiers, mais le chiffre exact du palier gratuit reste à vérifier si l'option est retenue.
- Le prix Route53 est vérifié : « $0.50 per hosted zone per month for the first 25 hosted zones ».
- Termly affichait le 2026-09-04 un code promotionnel temporaire ; les montants ci-dessus sont les tarifs de base hors promotion.

---

## 5. Effort de mise en place et de mise à jour

### 5.1 Chemins exacts dans les consoles (intitulés relevés le 2026-09-04)

**Cloudflare — acheter le domaine** (<https://developers.cloudflare.com/registrar/get-started/register-domain/>) : « In the Cloudflare dashboard, go to the **Register domains** page. In the search box, enter the domain name you wish to register, and select **Search**. […] Select **Purchase** on the domain you wish to register. »

**Cloudflare — publier les pages** (<https://developers.cloudflare.com/pages/configuration/custom-domains/>) : « In the Cloudflare dashboard, go to the **Workers & Pages** page. Select your Pages project > **Custom domains**. Select **Set up a domain**. Provide the domain that you would like to serve your Cloudflare Pages site on and select **Continue**. » Deux précisions de cette même page, décisives pour le choix A1/A2 :

- apex (`<domaine>` nu) : « you will need to add your site as a Cloudflare zone and configure your nameservers » ;
- sous-domaine (`legal.<domaine>`, `www.<domaine>`) : « If you are deploying to a subdomain, **it is not necessary for your site to be a Cloudflare zone** » — un CNAME suffit, la zone peut donc rester ailleurs.

**Cloudflare — l'adresse de contact** (<https://developers.cloudflare.com/email-routing/setup/email-routing-addresses/>) : « In the Cloudflare dashboard, go to **Compute > Email Service > Email Routing**. Select **Routing Rules**. » C'est là que se créent les adresses personnalisées et leur destination.

**App Store Connect — l'URL de politique de confidentialité** (<https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy>) : « In **Apps**, select the app you want to view. In the sidebar, select **App privacy**. Next to **Privacy Policy**, click **Edit**. Enter the privacy policy URL […] Click **Save**. » Suivi de l'avertissement déjà cité : « Any changes to the URLs releases with your next app version. »

**App Store Connect — l'EULA** (<https://developer.apple.com/help/app-store-connect/manage-app-information/provide-a-custom-license-agreement>) : « In **Apps**, select the app you want to view. In the sidebar, under **General**, click **App Information**. On the left, in the **General Information** section, click **Edit** next to **License Agreement**. » Ne rien y toucher laisse s'appliquer l'EULA standard (§1bis).

**Play Console — l'URL de politique de confidentialité** (<https://support.google.com/googleplay/android-developer/answer/9859455>) : « Open Play Console and go to the **App content** page (**Policy and programs > App content**). Under "**Privacy Policy**," select **Start**. […] If you've previously added a privacy policy and want to make changes, you'll see and select **Manage** instead of Start. Enter the URL hosting the privacy policy online. **Save** your changes. »

### 5.2 Qui met à jour, et par quel chemin

| Option | Mise en place | Corriger une clause deux mois plus tard |
|---|---|---|
| **A1** | Acheter le domaine, déléguer les serveurs de noms, créer le projet Pages, brancher le dépôt, ajouter le domaine personnalisé, créer la règle de routage e-mail. Ordre de grandeur : une heure, une seule fois. | Éditer le markdown au dépôt, pousser : le build Pages redéploie. Le texte reste versionné et relisible en diff — c'est la seule option où une clause modifiée laisse une trace dans l'historique |
| **A2** | Idem, plus un module Terraform neuf (bucket, OAC, distribution, certificat `us-east-1`, invalidation au déploiement) | Même chose, plus une invalidation CloudFront à déclencher |
| **B** | Créer le projet Pages, brancher le dépôt. Vingt minutes | Idem A1 |
| **C** | Activer Pages sur un dépôt. Vingt minutes | Idem A1 — mais sur un hébergement dont les CGU interdisent l'usage |
| **D** | Répondre au questionnaire du générateur, publier, coller l'URL fournisseur | Se reconnecter chez le fournisseur, éditer dans son back-office. Le texte **sort du dépôt** : plus de diff, plus de revue, et divergence garantie avec `docs/compliance/` |
| **E** | Créer le site, coller le texte dans l'éditeur, publier | Rouvrir l'éditeur Google Sites et recoller. Même problème de divergence que D |
| **F** | Coller le texte dans un document, régler le partage, publier | Éditer le document. Le risque n'est pas l'effort mais le réglage de partage, qui peut changer sans bruit |

Le point qui départage réellement A/B/C d'un côté et D/E/F de l'autre n'est pas la durée de mise en place — elles se valent — mais **où vit le texte**. Les textes légaux du projet existent déjà au dépôt et sont la source de vérité invoquée par `docs/compliance/CHECKLIST.md` ; toute option qui les recopie dans un back-office tiers crée deux versions qui divergeront, et c'est celle du dépôt que les prochaines tâches liront.

---

## 6. Génération du contenu : ce qu'un générateur achète réellement

Trois faits, puis la conclusion.

**1. Le contenu existe déjà, et il est spécifique.** `docs/compliance/privacy-policy.md` (199 lignes), `terms-of-service.md` (213 lignes), `apple-app-privacy.md` (160 lignes) et `google-play-data-safety.md` (188 lignes) sont rédigés, et la matrice de `docs/compliance/CHECKLIST.md` fait correspondre chaque flux de données à sa déclaration. Les sous-traitants réels y sont nommés.

**2. Ce que Google vérifie, un générateur ne peut pas le savoir.** La politique User Data exige que la politique divulgue les pratiques effectives « **not limited by the data disclosed in the Data safety section** », qu'elle expose un point de contact ou un mécanisme de demande, qu'elle soit étiquetée comme politique de confidentialité, et qu'elle nomme l'entité de la fiche Play ou l'app. Un questionnaire de générateur produit un texte à partir de ce qu'on lui déclare : il ne découvre pas que la chaîne d'ingestion passe par un fournisseur de transcription et un fournisseur de LLM. La charge d'exactitude reste entière sur l'owner dans les deux cas.

**3. Ce que le générateur vend vraiment.** Trois choses : des gabarits, une **veille** (« Our legal team monitors global privacy laws and publishes updates to keep your policies compliant » — Termly), et un hébergement. Aucun n'est un conseil juridique, et aucun des deux fournisseurs examinés ne prétend le contraire. Tarifs relevés le 2026-09-04 : iubenda Essentials 4,99 €/site/mois facturé à l'année (**59,88 €/an**) pour le générateur politique + cookies, le générateur *Terms and Conditions* étant un produit distinct dont le prix n'est pas affiché sur sa page produit et dont les paliers voisins sont à 19–21 €/site/mois (**~240 €/an**) ; Termly gratuit pour « 1 basic legal policy », Starter 10 $/site/mois à l'année (**120 $/an**, 2 politiques, 10 éditions), Pro+ 15 $/site/mois à l'année (**180 $/an**, illimité).

**Conclusion.** Le générateur est **le mauvais achat pour ce projet précis**, pour trois raisons cumulées : les textes existent et sont plus exacts qu'un gabarit ; l'URL produite appartient au fournisseur, donc une résiliation casse une métadonnée Apple non modifiable sans nouvelle version (§0.2) ; et il déplace la source de vérité hors du dépôt, où elle divergera de `docs/compliance/`. Si l'owner veut un regard juridique, la dépense pertinente est **une relecture ponctuelle par un avocat** sur les textes existants — un achat unique, pas un abonnement mensuel à un gabarit.

---

## 7. L'adresse de contact de confidentialité

### 7.1 Ce que les règles exigent

- **Google, politique User Data** : la politique doit contenir « Developer information and a privacy point of contact **or a mechanism to submit inquiries** ». Une adresse **ou** un formulaire. Aucune exigence de domaine.
- **Apple, 5.1.1(i)** : la politique doit « explain its data retention/deletion policies and describe how a user can revoke consent and/or request deletion of the user's data ». Aucune exigence de domaine non plus.

**Réponse directe à l'AC#4 : une adresse chez un fournisseur grand public ne viole aucune règle de store.** Ni Apple ni Google n'imposent que l'adresse publiée soit sur un domaine possédé.

### 7.2 Ce qui, dans ce projet, tranche contre l'adresse grand public

Trois faits internes, plus contraignants que les règles des stores :

1. **Le formulaire commerçant DSA fait publier l'adresse par Apple.** `docs/V1_LAUNCH_PLAN.md:1261-1272` : « Les coordonnées de commerçant (adresse, téléphone, e-mail) sont publiées par Apple sur la fiche App Store », Apple vérifie téléphone et e-mail par code, et « modifiable n'est pas effaçable, une adresse personnelle publiée quelques mois aura été aspirée ». Le plan enregistre déjà la décision : « L'e-mail publié doit être une adresse dédiée du domaine, pas une boîte personnelle, et c'est la même que celle de la fiche App Store et de la politique de confidentialité. » Une adresse grand public contredit donc une décision déjà prise, et l'expose sur une page publique indexée.
2. **L'app construit un `mailto:` dessus.** `mobile/app/settings/delete-account.tsx` compose `mailto:${PRIVACY_CONTACT_EMAIL}?subject=Data%20request` et affiche l'adresse : c'est l'unique route d'accès et de portabilité, l'app n'ayant pas d'export en libre-service. L'adresse doit donc réellement recevoir, et recevoir des pièces jointes.
3. **L'adresse figure aussi dans le texte de la politique.** La changer coûte un OTA **et** une réédition de page **et** une mise à jour du formulaire DSA. Une adresse **redirigée** évite ce coût pour toujours : la boîte de destination change sans que l'adresse publiée bouge.

### 7.3 Les formes possibles, et leur coût

| Forme | Coût | Reçoit | Émet | Ce que ça implique |
|---|---|---|---|---|
| Adresse dédiée sur le domaine acheté, transférée par **Cloudflare Email Routing** | 0 $ — « Email Routing for handling incoming emails […] **Available on Free and Paid plans** » | oui | non (l'envoi sortant relève de l'offre Workers payante) | Exige que la zone soit chez Cloudflare. Adresse publiée stable à vie, destination modifiable en un clic. **Forme recommandée** |
| Adresse dédiée sur le domaine + **Zoho Mail** offre gratuite | 0 $ — « Mail Free, gratuit pour toujours, aucune carte bancaire requise : jusqu'à 5 utilisateurs, adresse e-mail personnalisée pour un domaine, 5 Go » ; **IMAP/POP/ActiveSync non inclus** (webmail et app mobile seulement) | oui | oui | Le choix si répondre *depuis* l'adresse compte. Une boîte de plus à surveiller, alors que le mail est déjà le canal d'alerte du projet |
| Adresse chez un fournisseur grand public | 0 $ | oui | oui | Conforme aux règles des stores, mais publie une identité personnelle sur la fiche App Store, contredit la décision du plan de lancement, et ne peut plus être changée à moindre frais (§7.2 point 3) |
| Formulaire web à la place d'une adresse | 0 $ en apparence | — | — | Autorisé par Google (« a mechanism to submit inquiries ») mais **pas** par le chemin in-app existant : `delete-account.tsx` ouvre un `mailto:`. Il faudrait un backend de formulaire, donc plus de pièces mobiles pour moins de fonction |

**Recommandation** : une adresse de rôle dédiée sur le domaine acheté, transférée gratuitement vers une boîte existante. La valeur exacte (partie locale et domaine) est une décision de l'owner et sera écrite par la tâche d'implémentation depuis le champ `Decision` — elle n'est délibérément pas inscrite ici, le dépôt étant public.

**Sur l'objection WHOIS** : acheter un domaine en nom propre expose en principe les coordonnées du titulaire. Les registrars appliquent aujourd'hui une occultation par défaut, et Cloudflare documente une page « WHOIS redaction » dans les options d'enregistrement du registrar — mais **le détail de cette page n'a pas pu être extrait dans cette passe**. À vérifier sur la page du registrar retenu avant l'achat, pas après.

---

## 8. Pérennité et coût de déménagement, option par option

Rappel du §0.2 : trois surfaces, trois coûts de changement très différents. La question « que coûte un déménagement » se décompose donc en « peut-on garder l'ancienne URL vivante pendant la transition ? ».

| Option | Peut-on rediriger l'ancienne URL ? | Coût du déménagement | Risque de disparition subie |
|---|---|---|---|
| **A1 / A2** | Sans objet : l'URL ne bouge pas, seul l'hébergement derrière change | **Nul.** Changer de Cloudflare Pages à S3 se fait en changeant un enregistrement DNS, sans toucher ni les stores ni l'app | Uniquement l'oubli de renouvellement du domaine |
| **B** (`*.pages.dev`) | Oui, un fichier `_redirects` en 301 tant que le projet Pages existe | **Une nouvelle version iOS** pour l'URL de métadonnée Apple, plus un OTA pour les liens in-app. Le champ Play se corrige immédiatement | Faible tant que le compte vit ; le nom de projet est repris si le projet est supprimé |
| **C** (`*.github.io`) | Oui en théorie, non si le sous-domaine est reprise | **Une nouvelle version iOS**, et sans préavis contractuel : « GitHub reserves the right at all times to reclaim any GitHub subdomain » | **Élevé** : usage explicitement interdit par les CGU (§2.2) |
| **D** (générateur hébergé) | Non | **Une nouvelle version iOS** dès la résiliation de l'abonnement | Lié au paiement : une carte expirée fait 404 sur une politique de confidentialité |
| **E** (Google Sites) | Non — l'éditeur ne fait pas de 301 | **Une nouvelle version iOS** | Faible, mais l'URL est définitivement marquée fournisseur |
| **F** (document publié) | Non | **Une nouvelle version iOS** | **Moyen à élevé** : le réglage de partage est le point de rupture, et rien ne prévient quand il change |

Deux conclusions :

- **Les options gratuites ne sont pas irréversibles, elles sont chères à réverser** : une version iOS supplémentaire, review comprise, pour économiser 11 $. Et la version ne peut pas être « juste » une correction d'URL : c'est un build EAS, une soumission et une review.
- **Le moment présent est le seul où le choix est gratuit.** Rien n'a été soumis ; les deux binaires en circulation seront remplacés de toute façon. Toute autre fenêtre coûtera au minimum une version.

---

## 9. Ce qui n'a pas pu être vérifié dans cette passe

Liste explicite, pour que l'owner sache ce qui est sourcé et ce qui ne l'est pas.

1. **Aucun rapport de refus de première main, daté.** Cause : tous les moteurs de recherche joignables ont servi des défis anti-robots, des 429, ou des résultats sans rapport ; Reddit et l'API Stack Exchange sont inaccessibles depuis cet environnement. Aucune anecdote n'est citée en conséquence. C'est la principale limite de ce benchmark, et elle porte sur l'AC#2 : le volet « règle écrite » est intégralement sourcé, le volet « pratique constatée » ne l'est pas.
2. **Les hausses programmées du prix de gros `.com`** (la page de Verisign a redirigé vers son accueil).
3. **Le palier gratuit permanent de CloudFront** (page de tarifs rendue en JavaScript).
4. **Le prix du générateur *Terms and Conditions* d'iubenda** : absent de sa page produit ; seuls les paliers voisins de la grille tarifaire sont cités.
5. **Le détail de l'occultation WHOIS** chez Cloudflare Registrar (page non extraite).
6. **Les intitulés exacts de l'écran de création d'une adresse personnalisée** dans Email Routing : seul le chemin `Compute > Email Service > Email Routing > Routing Rules` est vérifié.
7. **Les CGU d'abonnement libre-service de Cloudflare** n'ont pas été auditées : l'absence de clause d'usage non commercial est constatée sur la page de limites de Pages, pas sur le contrat.
8. **Notion** : la page d'aide « public pages and web publishing » a répondu HTTP 500 à deux reprises ; l'option F est donc décrite au niveau du mécanisme (publication en lecture seule contre partage restreint), sans citation de l'éditeur.

---

## 10. Sources

Toutes consultées le **2026-09-04**.

**Apple**

- App Review Guidelines (2.1(a), 3.1.2, 5.1.1(i)) — <https://developer.apple.com/app-store/review/guidelines/>
- Apple Developer Program License Agreement, Schedule 2 §3.8(b) — <https://developer.apple.com/programs/apple-developer-program-license-agreement/>
- Auto-renewable subscriptions, exigences de l'écran d'achat — <https://developer.apple.com/app-store/subscriptions/>
- « Required, localizable, and editable properties » — <https://developer.apple.com/help/app-store-connect/reference/app-information/required-localizable-and-editable-properties>
- « Manage app privacy » — <https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy>
- « Provide a custom license agreement » — <https://developer.apple.com/help/app-store-connect/manage-app-information/provide-a-custom-license-agreement>
- Licensed Application End User License Agreement (EULA standard) — <https://www.apple.com/legal/internet-services/itunes/dev/stdeula/>

**Google**

- Politique **User Data** — <https://support.google.com/googleplay/android-developer/answer/10144311>
- « Prepare your app for review » (chemin Play Console) — <https://support.google.com/googleplay/android-developer/answer/9859455>
- Politique **Subscriptions** — <https://support.google.com/googleplay/android-developer/answer/9900533>
- Politique **Payments** — <https://support.google.com/googleplay/android-developer/answer/9858738>
- Section **Data safety** — <https://support.google.com/googleplay/android-developer/answer/10787469>
- Google Sites, « Publish & share your site » — <https://support.google.com/sites/answer/6372880>

**Hébergement, domaine, e-mail**

- Cloudflare Pages, limites de l'offre gratuite — <https://developers.cloudflare.com/pages/platform/limits/>
- Cloudflare Pages, domaines personnalisés (apex contre sous-domaine) — <https://developers.cloudflare.com/pages/configuration/custom-domains/>
- Cloudflare Registrar, « at-cost » — <https://www.cloudflare.com/products/registrar/> ; enregistrer un domaine — <https://developers.cloudflare.com/registrar/get-started/register-domain/>
- Cloudflare Email Service / Email Routing, disponibilité en offre gratuite — <https://developers.cloudflare.com/email-routing/> ; adresses et règles — <https://developers.cloudflare.com/email-routing/setup/email-routing-addresses/>
- GitHub, « Terms for Additional Products and Features », section Pages — <https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features>
- Vercel, « Fair Use Guidelines », usage commercial — <https://vercel.com/docs/limits/fair-use-policy>
- Porkbun, tarifs des domaines (« .COM from $11.08 ») — <https://porkbun.com/products/domains>
- Amazon Route 53, tarifs (0,50 $/zone/mois) — <https://aws.amazon.com/route53/pricing/>
- Amazon CloudFront, tarifs — <https://aws.amazon.com/cloudfront/pricing/>
- Zoho Mail, grille tarifaire (offre gratuite) — <https://www.zoho.com/mail/zohomail-pricing.html>
- iubenda, tarifs — <https://www.iubenda.com/en/pricing>
- Termly, tarifs — <https://termly.io/pricing/>

**Dépôt**

- `mobile/src/constants/legal.ts`, `mobile/app/paywall.tsx`, `mobile/app/settings/delete-account.tsx` (lecture seule)
- `mobile/app.config.ts` (`updates.url`, `runtimeVersion: fingerprint`), `mobile/eas.json`, `mobile/MOBILE_CI_CD.md`
- `docs/compliance/` : `privacy-policy.md`, `terms-of-service.md`, `apple-app-privacy.md`, `google-play-data-safety.md`, `CHECKLIST.md`
- `docs/V1_LAUNCH_PLAN.md` : lignes 248-249 (aucun domaine possédé), 1261-1272 (coordonnées commerçant DSA publiées), 1745-1781 (Phase 10 §0bis), 1930-1932
- `infrastructure/terraform/modules/platform/lambda_api.tf:249-294` (certificat ACM, mapping API Gateway, alias Route53 conditionné à `api_zone_id`)
