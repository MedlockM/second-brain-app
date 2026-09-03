# Devbox Setup

Reconstruire un poste de développement complet à partir d'un clone du repo et
d'un accès AWS. Écrit pour un changement de machine, mais valable pour tout
nouveau poste.

Ce document ne couvre **pas** :

- provisionner ou modifier un environnement AWS → `infrastructure/terraform/README.md`
- publier une release mobile → `docs/PRODUCTION_RELEASE_RUNBOOK.md` et `mobile/MOBILE_CI_CD.md`
- lancer la suite E2E → `tests/e2e/README.md`

Règle qui traverse tout le document : **aucune valeur de credential n'est écrite
ici**, seulement le moyen de la récupérer. Le repo est public (`AGENTS.md`).

---

## Table of Contents

- [1. Ce qui ne se régénère pas](#1-ce-qui-ne-se-régénère-pas)
- [2. Prérequis outils](#2-prérequis-outils)
- [3. Accès à re-créer](#3-accès-à-re-créer)
- [4. Profils AWS](#4-profils-aws)
- [5. Backend Python](#5-backend-python)
- [6. Reconstruire le `.env`](#6-reconstruire-le-env)
- [7. Mobile](#7-mobile)
- [8. Terraform](#8-terraform)
- [9. Checklist de vérification](#9-checklist-de-vérification)
- [10. Angles morts](#10-angles-morts)

---

## 1. Ce qui ne se régénère pas

Presque tout se reconstruit. **Une seule exception** à transférer hors ligne (clé
USB ou gestionnaire de mots de passe — **jamais** un service en ligne) :

| Fichier | Pourquoi | Alternative si perdu |
|---|---|---|
| `~/.aws/credentials` | Porte l'access key du profil `second-brain-app`, la seule valeur qui authentifie. AWS ne l'affiche qu'à la création et ne la stocke nulle part sous forme récupérable | Créer une nouvelle access key dans IAM, puis **supprimer l'ancienne** (voir §4) |

Son voisin `~/.aws/config` n'en est pas une : il ne contient aucun secret et vit
dans le repo (`infrastructure/aws/config.example`, §4).

Et si vous vous demandez pourquoi `credentials` ne peut pas rejoindre Secrets
Manager comme les 35 credentials tiers : lire un secret exige d'être déjà
authentifié auprès d'AWS, or c'est précisément ce que ce fichier fournit. Un
coffre ne peut pas contenir sa propre clé. La sortie de cette impasse est AWS IAM
Identity Center (`aws sso login`, credentials temporaires dans
`~/.aws/sso/cache/`), qui supprimerait le fichier au lieu de le déplacer — chantier
non engagé à ce jour.

Tout le reste se retrouve : le `.env` racine depuis Secrets Manager (§6), le
`mobile/.env` depuis EAS (§7), les dossiers natifs mobiles par `expo prebuild`,
le venv par `uv`, les providers Terraform par `terraform init`.

**Ne transférez pas** l'ancien `.env` racine ni l'ancien `mobile/.env` : ils
dérivent silencieusement du template et de l'infra. Les reconstruire prend deux
minutes et garantit qu'ils sont à jour.

---

## 2. Prérequis outils

Versions connues comme fonctionnelles (relevées sur le poste de référence) :

| Outil | Version | Contrainte |
|---|---|---|
| Python | 3.10 | `pyproject.toml` : `requires-python = ">=3.10"` |
| `uv` | 0.9.17 | Gère le venv et les dépendances |
| Terraform | 1.9.8 | `envs/*/main.tf` : `required_version = ">= 1.9"` |
| Node.js | 20 | `NODE_VERSION: "20"` dans les workflows mobiles |
| npm | 10.8 | Fourni avec Node 20 |
| AWS CLI | v2 | `secretsmanager`, `sts`, `dynamodb` |
| `jq` | 1.7 | Utilisé par `scripts/tf_plan_guard.sh` |
| `gh` | 2.45 | Opérations GitHub |
| `eas-cli` | **22.0.0 exactement** | `npm install -g eas-cli@22.0.0` — même pin que les workflows mobiles (`EAS_CLI_VERSION`). Une version flottante met la machine sur une autre majeure que la CI, et la règle de décision OTA repose sur des flags qu'un bump de majeure peut déplacer (`mobile/MOBILE_CI_CD.md`, « Pinning the EAS CLI ») |

Docker n'est pas requis : le développement cible l'environnement AWS dev, pas
LocalStack (déprécié par task-130).

---

## 3. Accès à re-créer

| Accès | Comment |
|---|---|
| AWS, compte dev `125313707865` | Access key du profil `second-brain-app` (transférée, ou nouvelle via IAM) |
| AWS, compte prod `866874944541` | Aucune clé propre : assumption de rôle depuis les clés dev (§4) |
| GitHub | `gh auth login` |
| Expo / EAS | `eas login` — donne accès aux variables d'environnement et aux credentials de build |

---

## 4. Profils AWS

Les deux fichiers suivent des chemins opposés, parce qu'un seul des deux contient
un secret.

**`~/.aws/config` est dans le repo** — aucune valeur qui authentifie, uniquement
des identifiants de ressources que `envs/prod/main.tf` porte déjà en clair :

```bash
install -m 600 -D infrastructure/aws/config.example ~/.aws/config
```

Il déclare `second-brain-app` (compte dev, porteur des clés) et `prod`, qui n'a
pas de clés propres et assume le rôle que AWS Organizations crée dans chaque
compte membre — détail dans `infrastructure/terraform/README.md`, section
« Two accounts, one set of keys ». Le fichier commente chaque profil ; le lire
vaut mieux que le recopier ici, sinon les deux divergent.

Une seule valeur mérite d'être personnalisée : `role_session_name`, c'est ce qui
apparaît dans CloudTrail côté prod.

**`~/.aws/credentials` n'y sera jamais.** À écrire à la main, avec le seul jeu de
clés du projet :

```ini
[second-brain-app]
aws_access_key_id     = <access key>
aws_secret_access_key = <secret>
```

Si la clé est perdue : IAM → utilisateur → *Security credentials* → créer une
access key, la coller ici, puis **supprimer l'ancienne**. Les deux peuvent
coexister le temps de la bascule ; laisser traîner l'ancienne, c'est un
credential actif hors de votre contrôle.

Vérification :

```bash
aws sts get-caller-identity --profile second-brain-app --query Account --output text  # 125313707865
aws sts get-caller-identity --profile prod --query Account --output text              # 866874944541
```

Piège connu : un `AWS_REGION` exporté dans le shell prime sur le `region` du
profil. La région du projet est `eu-west-3`.

---

## 5. Backend Python

```bash
uv venv --clear --python 3.10 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Utiliser les binaires du venv directement (`.venv/bin/ruff`, `.venv/bin/mypy`)
plutôt que d'activer le venv : reproductible et sans risque de prendre un outil
global.

---

## 6. Reconstruire le `.env`

Le template `.env.example` est la référence : il porte les vrais noms de
ressources dev et documente chaque variable. Ce qu'il ne peut pas contenir, ce
sont les credentials tiers — ils vivent dans Secrets Manager.

```bash
cp .env.example .env
```

Puis injecter les credentials depuis le secret runtime dev, sans jamais les
écrire dans un fichier intermédiaire :

```bash
AWS_PROFILE=second-brain-app aws secretsmanager get-secret-value \
  --secret-id media-summarizer-runtime-dev --region eu-west-3 \
  --query SecretString --output text \
| .venv/bin/python -c '
import json, re, sys
secret = json.load(sys.stdin)
lines = open(".env", encoding="utf-8").read().splitlines()
out, injected = [], []
for line in lines:
    m = re.match(r"^([A-Z_0-9]+)=", line)
    if m and m.group(1) in secret:
        injected.append(m.group(1))
        out.append(f"{m.group(1)}={secret[m.group(1)]}")
    else:
        out.append(line)
open(".env", "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"injected {len(injected)} of {len(secret)} secret keys")
# Anything reported here stayed out of the .env: the line is commented out or
# absent from the template. Never silent -- a missing credential otherwise shows
# up much later as an opaque 401 from a third party.
skipped = sorted(set(secret) - set(injected))
print("skipped:", ", ".join(skipped) or "none")
'
chmod 600 .env
```

Le secret dev contient 40 clés, dont **35 vivantes** — les cinq autres sont
mortes, personne ne les lit. Une seule valeur est vide, `COOKIE_DOMAIN`, et c'est
précisément une des mortes ; `REVENUCAT_WEBHOOK_SECRET` **est renseignée** depuis
le 2026-08-13. L'injection saute normalement deux noms, tous deux morts :

- `COOKIE_DOMAIN` — **clé morte** depuis task-293 : le refresh token voyage dans
  le corps JSON de register/login/refresh, plus dans un cookie httpOnly, et aucun
  code ne lit de variable `COOKIE_*`. Elle a quitté `.env.example` ; inutile de la
  reconstituer.
- `ALGOLIA_INDEX_NAME` — **clé morte**, aucun code ne la lit. Le nom d'index vaut
  `media_items_{ENVIRONMENT}`, calculé par `utils/algolia_client.py`. Elle traîne
  dans le secret depuis task-205 ; inoffensive, mais ne pas la reconstituer.

Les trois autres mortes n'apparaissent **pas** dans `skipped:` : elles sont encore
déclarées dans `.env.example`, donc injectées.

- `APIFY_INSTAGRAM_COMMENT_ACTOR_ID` — le Comment Scraper a disparu du resolver
  Instagram avec task-173 ; la clé ne sert plus à rien mais ne casse rien.
- `REVENUCAT_API_KEY` et `REVENUCAT_PROJECT_ID` — **mortes au sens du runtime**
  (relevé le 2026-09-03) : `config.py:84` et `:86` les affectent et aucun autre
  code ne les consomme. `REVENUCAT_API_KEY` reste néanmoins utile **à vous**,
  depuis le `.env`, comme bearer de l'API v2 RevenueCat pour inspecter le
  dashboard (`docs/REVENUECAT_ENTITLEMENTS.md`). C'est un credential
  d'outillage, pas de runtime — d'où son absence du secret prod (`task-252`).

Tout autre nom listé par `skipped:` est un vrai manque à investiguer.

Deux règles qui évitent des heures de débogage :

- **Ne jamais mettre de commentaire sur la même ligne qu'une valeur entre
  guillemets.** `APPLE_PRIVATE_KEY="…"  # PEM inline` a déjà été recopié tel quel
  dans Secrets Manager, guillemets et commentaire compris, ce qui casse Apple
  Sign-In côté Lambda (task-136). Les commentaires vont sur la ligne au-dessus.
- **Ne pas modifier les noms de ressources à la main.** Ils sont
  environment-specific et sans fallback dans le code : une variable manquante ou
  périmée lève au moment de l'import. Pour un autre environnement, les lire
  depuis Terraform (§8) plutôt que d'éditer le suffixe.

---

## 7. Mobile

```bash
cd mobile
npm ci                                          # postinstall applique patch-package
eas env:pull development --path .env            # sinon le défaut est .env.local
npx expo prebuild --platform android --clean    # régénère android/, debug.keystore inclus
```

Les valeurs `EXPO_PUBLIC_*` vivent dans les variables d'environnement EAS
(`eas env:list development`). Une copie de secours du fichier complet est dans le
secret AWS `media-summarizer-devbox-mobile-env` — jamais lu par une Lambda ni par
Terraform, uniquement une cible de restauration.

Sur les keystores : `mobile/android/app/debug.keystore` porte les credentials de
debug publics d'Android et est réécrit à chaque `prebuild` — rien à sauvegarder.
Le keystore d'**upload**, lui, est géré par EAS (`eas credentials`), pas par ce
repo.

---

## 8. Terraform

Un root module par environnement, state en S3 :

```bash
terraform -chdir=infrastructure/terraform/envs/dev init
```

**Ne jamais lancer Terraform depuis `infrastructure/terraform/`** : ce n'est pas
un root module. L'ancienne disposition à root unique, où l'on copiait un
`terraform.tfvars` et éditait `environment` pour changer de cible, a disparu avec
task-237. Il n'existe plus aucun fichier de variables : chaque
`envs/<env>/main.tf` porte ses valeurs en littéraux. Si vous trouvez une doc qui
demande de créer un `terraform.tfvars`, elle est périmée.

Les noms de ressources sont lisibles depuis les outputs, ce qui évite de les
deviner :

```bash
terraform -chdir=infrastructure/terraform/envs/dev output -json bucket_names
terraform -chdir=infrastructure/terraform/envs/dev output -json table_names
terraform -chdir=infrastructure/terraform/envs/dev output -json queue_names
```

Le plan et l'apply passent par le guard d'isolation — voir
`infrastructure/terraform/README.md`.

---

## 9. Checklist de vérification

Dans l'ordre ; chaque étape suppose la précédente.

```bash
# Identités AWS
aws sts get-caller-identity --profile second-brain-app --query Account --output text
aws sts get-caller-identity --profile prod --query Account --output text

# Le .env est complet et l'app démarre (PRESTART_INFRA_CHECK teste l'accès S3 réel)
.venv/bin/python -c "from media_summarizer.api.main import app; print('IMPORT_OK', len(app.routes))"

# Toute variable lue par le code est déclarée dans .env.example
.venv/bin/python scripts/check_env_example_complete.py

# Lint et types
.venv/bin/ruff check media_summarizer tests scripts
.venv/bin/mypy media_summarizer

# API en local
.venv/bin/uvicorn media_summarizer.api.main:app --port 8000 &
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/docs   # 200

# Terraform
terraform -chdir=infrastructure/terraform/envs/dev init
terraform -chdir=infrastructure/terraform/envs/dev validate

# Mobile
cd mobile && npx eas env:list development && npm run typecheck
```

`IMPORT_OK` est le contrôle le plus utile : le code lit ses noms de ressources
via `required_env()`, sans fallback, donc un import réussi prouve que le `.env`
est complet et cohérent avec l'infra déployée. Attendu aujourd'hui :
`IMPORT_OK 73`.

La procédure §6 a été validée en entier le 2026-08-13 depuis ce poste : 35 des 37
clés injectées (les 2 sautées sont celles listées plus haut), `IMPORT_OK 73`, puis
boot `uvicorn` avec `PRESTART_INFRA_CHECK=1` et `GET /docs` → `200`. Ce dernier
point est ce qui prouve le plus : le check infra tape réellement AWS, donc un
`200` valide les 48 noms de ressources contre l'environnement dev déployé.

---

## 10. Angles morts

Ce qui reste manuel ou fragile, à connaître avant le prochain déménagement :

- **`~/.aws/credentials`** est le seul fichier réellement irremplaçable sans
  passer par la console AWS.
- **Historique des dispatches** (`.claude/dispatch-runs/`) : gitignoré, perdu avec
  le disque. C'est de la trace d'exécution, sans valeur pour reprendre.
- **`EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID`** n'existe plus (task-325) : Android
  signe via Credential Manager, qui prend le client **Web** comme `serverClientId`.
  Une ligne restée dans un `mobile/.env` local est simplement ignorée.
- **`EXPO_PUBLIC_REVENUCAT_GOOGLE_KEY`** est renseignée dans `mobile/.env` depuis
  le 2026-08-20 (vraie clé publique `goog_`, l'app Play Store existant désormais
  dans le projet RevenueCat). Le SDK Android est donc configuré pour de vrai,
  mais il ne résout encore aucune offre : les produits Google Play n'existent pas
  (`task-238`). L'état de cette variable côté environnements EAS n'a pas été
  revérifié depuis.
- **`EXPO_PUBLIC_REVENUCAT_APPLE_KEY`** peut temporairement porter la clé du
  **Test Store** plutôt que la clé `appl_` de l'App Store : c'est la seule façon
  de voir le paywall avec de vrais prix tant que les abonnements n'existent pas
  dans App Store Connect. Bascule locale et volontaire — vérifier laquelle des
  deux est en place avant de conclure quoi que ce soit sur un build.
- **Branches locales non poussées** : le dépôt distant ne garde que ce qui a été
  poussé. Avant de débrancher, `git push --all origin` et vérifier que chaque
  branche a un upstream (`git config --global push.autoSetupRemote true` évite le
  problème à la racine).
