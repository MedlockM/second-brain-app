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

Les trois clés Apple `.p8` du poste **étaient** dans ce tableau jusqu'au
2026-09-11. Elles n'y sont plus : leur PEM vit désormais dans Secrets Manager, et
le §7 les réécrit sur disque. Apple ne les retélécharge pourtant qu'une fois —
c'est le coffre qui a changé, pas Apple.

| Clé Apple | Où elle est sauvegardée |
|---|---|
| *Sign in with Apple* | `APPLE_PRIVATE_KEY` du secret runtime ; le `.env` reconstruit la récupère (§6) |
| *App Store Connect API* | `ASC_PRIVATE_KEY` du secret `media-summarizer-devbox` (§7) |
| *In-App Purchase* | `APPLE_IAP_PRIVATE_KEY` du même secret (§7) |

Les trois ont été vérifiées identiques au `.p8` du disque, octet pour octet, le
2026-09-11. Le tableau de leurs consommateurs est dans `mobile/MOBILE_CI_CD.md`.

Ce qui rend la manœuvre possible sans contradiction : l'argument du « coffre qui
ne peut pas contenir sa propre clé » (plus bas) vaut **uniquement** pour
`~/.aws/credentials`. Tout le reste, une fois authentifié auprès d'AWS, se lit.
Étendre cet argument aux clés Apple était le raccourci qui les laissait dehors.

Contrepartie à connaître : qui obtient les clés AWS obtient maintenant aussi
l'accès App Store Connect **Admin**. Deux compromissions distinctes n'en font
plus qu'une. Arbitrage assumé — sur un poste solo, les deux vivaient déjà sur le
même disque.

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
| Bedrock, pour les agents | `~/.config/claude-bedrock/env` : `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `ANTHROPIC_MODEL`. Le token se régénère dans la console Bedrock ; les deux autres valeurs se relisent ici |

### Outillage des agents, hors repo

`scripts/dispatch_backlog.sh` et `scripts/testflight_triage.sh` sont versionnés,
mais trois de leurs dépendances vivent hors du dépôt et ne suivent pas le clone.
Aucune n'est un secret irremplaçable ; toutes bloquent le script si elles
manquent.

- **`~/.local/bin/claude-bedrock`** — prérequis dur des deux scripts
  (`command -v claude-bedrock`, sinon arrêt). Wrapper d'une dizaine de lignes :
  il source `~/.config/claude-bedrock/env`, exporte `CLAUDE_CODE_USE_BEDROCK=1`
  et fait `exec claude "$@"`. À réécrire à la main, avec `chmod +x`.
- **La registration MCP `asc-testflight`** dans `~/.claude.json` — porte
  `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`, `ASC_READ_ONLY` et
  `ASC_REDACT_PII`. C'est aussi, à défaut de variables d'environnement, la source
  que lit `scripts/testflight_feedback.py` : les deux identifiants ne sont donc
  écrits qu'à cet endroit, jamais dans un fichier tracké.
- **`~/.config/systemd/user/testflight-triage.{service,timer}`** — le
  déclencheur de 9h00, plus `loginctl enable-linger` pour qu'il survive au
  logout. Les unités ne sont pas versionnées ; leurs réglages structurants sont
  décrits un par un dans `mobile/MOBILE_CI_CD.md`, section « The trigger — a user
  systemd timer ». Les recopier depuis l'ancien poste évite de réinventer le
  `Environment=PATH`, qui dépend de la version de node installée.

Rien à sauvegarder en revanche du côté de `.testflight-feedback/` : le triage
borne sa collecte par `--since-hours` et non par un état sur disque, donc un
dossier absent se recrée au run suivant sans rien rejouer à tort.

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
secret AWS `media-summarizer-devbox`.

Sur les keystores : `mobile/android/app/debug.keystore` porte les credentials de
debug publics d'Android et est réécrit à chaque `prebuild` — rien à sauvegarder.
Le keystore d'**upload**, lui, est géré par EAS (`eas credentials`), pas par ce
repo.

### Le secret `media-summarizer-devbox`

Créé à la main le 2026-09-11, **hors Terraform**, et lu par personne : ni Lambda,
ni Terraform, ni code applicatif. Sa seule raison d'être est qu'un humain remonte
une machine. Il porte quinze clés : les sept `EXPO_PUBLIC_*` ci-dessus, les deux
clés Apple de §1 avec leur Key ID, et les trois valeurs de `claude-bedrock`.

Restaurer les deux `.p8` et le wrapper Bedrock, sans qu'aucune valeur ne passe
par un fichier intermédiaire ni par la ligne de commande :

```bash
mkdir -p ~/.appstoreconnect/private_keys ~/.config/claude-bedrock
aws secretsmanager get-secret-value --secret-id media-summarizer-devbox \
  --region eu-west-3 --query SecretString --output text \
| python3 -c '
import json, os, stat, sys
s = json.load(sys.stdin)
home = os.path.expanduser("~")
# AWS_REGION, pas BEDROCK_AWS_REGION : le wrapper doit exporter le nom que lit le
# SDK. La cle est renommee DANS le secret pour quun export naif de lensemble ne
# repointe pas tout le projet sur la region de Bedrock. Valeurs entre guillemets,
# comme loriginal.
env = ("export AWS_BEARER_TOKEN_BEDROCK=\"" + s["AWS_BEARER_TOKEN_BEDROCK"] + "\"\n"
       "export AWS_REGION=\"" + s["BEDROCK_AWS_REGION"] + "\"\n"
       "export ANTHROPIC_MODEL=\"" + s["ANTHROPIC_MODEL"] + "\"\n")
targets = [
    (home + "/.appstoreconnect/private_keys/AuthKey_" + s["ASC_KEY_ID"] + ".p8", s["ASC_PRIVATE_KEY"]),
    (home + "/Documents/SubscriptionKey_" + s["APPLE_IAP_KEY_ID"] + ".p8", s["APPLE_IAP_PRIVATE_KEY"]),
    (home + "/.config/claude-bedrock/env", env),
]
for path, content in targets:
    open(path, "w").write(content)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    print("écrit", path)
print("ASC_ISSUER_ID =", s["ASC_ISSUER_ID"], "(pour la registration MCP, §3)")
'
```

Rejoué le 2026-09-11 contre un `HOME` bidon : les deux `.p8` ressortent identiques
à l'octet près, en `600`. Deux pièges rencontrés en l'écrivant, tous deux évités
dans la forme ci-dessus — une f-string ne peut pas contenir de backslash
(`SyntaxError` en 3.10/3.11, d'où les concaténations), et comparer le résultat
avec `diff` **imprime la clé privée dans le terminal** : utiliser `cmp -s`.

**Le piège de la région.** `claude-bedrock` exporte `AWS_REGION=us-east-1`, la
région de Bedrock, alors que l'infra du projet est en `eu-west-3`. Un shell qui
a sourcé cet `env` fait lire au code la mauvaise région, et l'erreur se présente
comme une table DynamoDB absente. C'est pourquoi la clé est stockée sous
`BEDROCK_AWS_REGION` dans le secret : elle ne peut pas repeupler `AWS_REGION` par
accident, seul le wrapper la remet sous son vrai nom.

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
`IMPORT_OK 68`.

La procédure §6 a été rejouée en entier le 2026-09-11 depuis ce poste : 38 des 40
clés injectées (les 2 sautées sont celles listées plus haut), `IMPORT_OK 68`, puis
boot `uvicorn` avec `PRESTART_INFRA_CHECK=1` et `GET /docs` → `200`. Ce dernier
point est ce qui prouve le plus : le check infra tape réellement AWS, donc un
`200` valide les noms de ressources contre l'environnement dev déployé.

Le compte de routes et le compte de clés bougent à chaque tâche ; ils datent la
dernière vérification, ils ne sont pas un contrat. Ce qui compte est que l'import
passe et que `/docs` réponde `200`.

Cette validation a aussi montré pourquoi le `.env` ne se transfère pas (§1) : le
`.env` du poste de référence avait dérivé au point de ne plus démarrer du tout —
il lui manquait `USER_PUSH_TOKENS_TABLE`, que le template porte. Le `.env`
reconstruit boote, l'ancien non.

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
- **`scripts/check_env_example_complete.py` échoue au 2026-09-11** sur sept
  variables lues par le code et absentes du template :
  `ARTICLE_FETCH_TIMEOUT_SECONDS`, `ARTIFACT_INTERNAL_STALL_SECONDS`, les quatre
  `INSTAGRAM_IMAGE_*` et `MEDIA_IDEMPOTENCE_RECONCILE_APPLY`. Les sept sont des
  `os.environ.get(..., défaut)` : elles ne bloquent aucun démarrage, et le boot
  §9 passe malgré le rouge. C'est une dette de documentation, pas une panne — ne
  pas la confondre avec un `.env` incomplet, qui lui lève au moment de l'import.
- **Branches locales non poussées** : le dépôt distant ne garde que ce qui a été
  poussé. Avant de débrancher, `git push --all origin` et vérifier que chaque
  branche a un upstream (`git config --global push.autoSetupRemote true` évite le
  problème à la racine). Les branches `worktree-agent-*` laissées par le
  dispatcher sont l'exception : leur contenu est repris sur `main` au merge, et ce
  qui reste sur la branche est l'état antérieur à la relecture. Vérifier avant de
  pousser par réflexe (`git log main..<branche>`), plutôt que d'archiver une
  variante périmée.
