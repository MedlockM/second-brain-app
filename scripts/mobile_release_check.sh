#!/usr/bin/env bash
# Validate EAS build prerequisites for the mobile app.
# Run this before any `eas build` invocation to catch config issues early.
#
# Usage:
#   bash scripts/mobile_release_check.sh                 # general pre-flight
#   bash scripts/mobile_release_check.sh <build-profile>  # gate one build profile
#
# With a build profile (`preview`, `internal`, `production`, …) the script acts
# as a gate on that profile: the host of its EXPO_PUBLIC_API_BASE_URL must
# resolve, otherwise the run fails. That is the form CI uses, because
# EXPO_PUBLIC_* values are inlined into the JS bundle at build time — a host
# with no DNS ships a binary that installs fine and fails every network call.
#
# Without an argument nothing is gated on DNS: a non-resolving host is reported
# as a warning so the script stays usable as a plain local pre-flight.
#
# Exit codes:
#   0 — all checks pass
#   1 — one or more checks failed
#   2 — bad usage
#
# Prerequisites:
#   - jq installed (reads eas.json)
#   - getent (glibc, always present — used for DNS resolution)

set -euo pipefail

# ------------------------------------------------------------------
# Color helpers
# ------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { printf "${GREEN}[PASS]${NC} %s\n" "$1"; }
fail() { printf "${RED}[FAIL]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }

# ------------------------------------------------------------------
# Resolve paths relative to repo root
# ------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MOBILE_DIR="${REPO_ROOT}/mobile"

# ------------------------------------------------------------------
# Optional build-profile argument
# ------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: bash scripts/mobile_release_check.sh [<build-profile>]

  <build-profile>  A build profile of mobile/eas.json (preview, internal,
                   production, development, development-simulator). When given,
                   the API host of that profile must resolve or the script fails.
EOF
}

PROFILE=""
case "${1:-}" in
  "") ;;
  -h | --help)
    usage
    exit 0
    ;;
  -*)
    fail "Unknown option '$1'"
    usage
    exit 2
    ;;
  *)
    PROFILE="$1"
    ;;
esac

if [ "$#" -gt 1 ]; then
  fail "Too many arguments — one build profile at most"
  usage
  exit 2
fi

ERRORS=0

echo "=== Mobile Release Pre-flight Check ==="
if [ -n "${PROFILE}" ]; then
  echo "Target build profile: ${PROFILE} (API host DNS is a hard gate)"
else
  echo "No build profile given: DNS problems are reported, not gated."
fi
echo ""

# ------------------------------------------------------------------
# 1. eas.json valid JSON
# ------------------------------------------------------------------
EAS_JSON="${MOBILE_DIR}/eas.json"

if ! command -v jq &>/dev/null; then
  fail "jq is not installed (required to validate eas.json)"
  ERRORS=$((ERRORS + 1))
elif [ ! -f "${EAS_JSON}" ]; then
  fail "mobile/eas.json not found"
  ERRORS=$((ERRORS + 1))
elif jq . "${EAS_JSON}" >/dev/null 2>&1; then
  pass "mobile/eas.json is valid JSON"
else
  fail "mobile/eas.json is not valid JSON"
  ERRORS=$((ERRORS + 1))
fi

# ------------------------------------------------------------------
# 2. app.config.ts present
# ------------------------------------------------------------------
APP_CONFIG="${MOBILE_DIR}/app.config.ts"

if [ -f "${APP_CONFIG}" ]; then
  pass "mobile/app.config.ts exists"
else
  fail "mobile/app.config.ts not found"
  ERRORS=$((ERRORS + 1))
fi

# ------------------------------------------------------------------
# 3. .env filled (based on .env.example)
# ------------------------------------------------------------------
ENV_EXAMPLE="${MOBILE_DIR}/.env.example"
ENV_FILE="${MOBILE_DIR}/.env"

if [ ! -f "${ENV_EXAMPLE}" ]; then
  fail "mobile/.env.example not found — cannot validate env vars"
  ERRORS=$((ERRORS + 1))
elif [ ! -f "${ENV_FILE}" ] && [ -n "${PROFILE}" ]; then
  # Profile mode is the CI / cloud-build form: the build environment comes from
  # the profile's own `env` block in eas.json plus the EAS env vars, never from
  # a local dotenv. A CI runner has no mobile/.env and must not fail for it.
  warn "mobile/.env not found — skipped: profile '${PROFILE}' takes its env from eas.json and the EAS env vars"
elif [ ! -f "${ENV_FILE}" ]; then
  fail "mobile/.env not found — copy from .env.example and fill in values"
  ERRORS=$((ERRORS + 1))
else
  ENV_OK=true
  while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "${line}" || "${line}" == \#* ]] && continue

    # Extract key (everything before the first '=')
    KEY="${line%%=*}"

    # Only check EXPO_PUBLIC_* keys
    [[ "${KEY}" != EXPO_PUBLIC_* ]] && continue

    # Read value from .env
    VALUE=""
    if grep -q "^${KEY}=" "${ENV_FILE}" 2>/dev/null; then
      VALUE="$(grep "^${KEY}=" "${ENV_FILE}" | head -1 | cut -d'=' -f2-)"
    fi

    if [ -z "${VALUE}" ]; then
      fail "${KEY} is missing or empty in mobile/.env"
      ENV_OK=false
      ERRORS=$((ERRORS + 1))
    fi
  done < "${ENV_EXAMPLE}"

  if [ "${ENV_OK}" = true ]; then
    pass "All required EXPO_PUBLIC_* env vars are set in mobile/.env"
  fi
fi

# ------------------------------------------------------------------
# 4. Bundle ID intact across config files
# ------------------------------------------------------------------
BUNDLE_ID="com.secondbrainlabs.core"

# mobile/plugins/withShareExtension.js a été supprimé par task-188 : le partage
# passe désormais par le plugin officiel expo-share-intent, déclaré dans
# app.config.ts. Ne pas le remettre ici.
BUNDLE_FILES=(
  "mobile/app.config.ts"
  "mobile/ios-share-extension/Info.plist"
)

BUNDLE_OK=true
for rel_path in "${BUNDLE_FILES[@]}"; do
  full_path="${REPO_ROOT}/${rel_path}"
  if [ ! -f "${full_path}" ]; then
    fail "Bundle ID check: ${rel_path} not found"
    BUNDLE_OK=false
    ERRORS=$((ERRORS + 1))
  elif grep -q "${BUNDLE_ID}" "${full_path}"; then
    : # OK
  else
    fail "Bundle ID '${BUNDLE_ID}' not found in ${rel_path}"
    BUNDLE_OK=false
    ERRORS=$((ERRORS + 1))
  fi
done

if [ "${BUNDLE_OK}" = true ]; then
  pass "Bundle ID '${BUNDLE_ID}' present in all config files"
fi

# ------------------------------------------------------------------
# 5. Expo SDK version
# ------------------------------------------------------------------
PACKAGE_JSON="${MOBILE_DIR}/package.json"

if [ ! -f "${PACKAGE_JSON}" ]; then
  fail "mobile/package.json not found"
  ERRORS=$((ERRORS + 1))
elif ! command -v jq &>/dev/null; then
  warn "jq not available — cannot read Expo SDK version from package.json"
else
  EXPO_VERSION="$(jq -r '.dependencies.expo // empty' "${PACKAGE_JSON}")"
  if [ -z "${EXPO_VERSION}" ]; then
    fail "expo dependency not found in mobile/package.json"
    ERRORS=$((ERRORS + 1))
  else
    printf "  Expo SDK version: ${GREEN}%s${NC}\n" "${EXPO_VERSION}"
    # Warn if not ~55.x
    if [[ "${EXPO_VERSION}" == *"55"* ]]; then
      pass "Expo SDK is on expected major version (55)"
    else
      warn "Expo SDK version '${EXPO_VERSION}' does not match expected ~55.x"
    fi
  fi
fi

# ------------------------------------------------------------------
# 6. The API base URL a build would inline actually resolves
#
# EXPO_PUBLIC_* variables are inlined into the JS bundle by Expo's babel
# transform at build time. A host with no DNS therefore produces a binary that
# builds, submits and installs without a single signal, then fails every
# network call — the failure that made AAB versionCode 4 unusable. Gate on it
# before `eas build` spends one of the 15 monthly builds of the free tier and
# before `eas submit` pushes the artifact to a store.
#
# `getent hosts` on purpose, not `dig`/`nslookup`: those come from dnsutils,
# which is not installed on `ubuntu-latest`. getent is glibc, always present,
# covers A and AAAA, and uses the system resolver.
# ------------------------------------------------------------------

# Shared jq helper: a profile's EXPO_PUBLIC_API_BASE_URL, following `extends`
# (development-simulator carries no env block of its own).
JQ_API_URL_DEF='def api_url($root; $name):
  $root.build[$name] as $p
  | if $p == null then "__NO_SUCH_PROFILE__"
    elif ($p.env.EXPO_PUBLIC_API_BASE_URL // null) != null then $p.env.EXPO_PUBLIC_API_BASE_URL
    elif ($p.extends // null) != null then api_url($root; $p.extends)
    else "__NO_URL__"
    end;'

profile_api_url() {
  jq -r --arg name "$1" "${JQ_API_URL_DEF}"' api_url(.; $name)' "${EAS_JSON}"
}

# One TSV line per distinct API URL: "<url>\t<profiles using it>".
all_api_urls() {
  jq -r "${JQ_API_URL_DEF}"' . as $root
    | [ $root.build | keys[] | { profile: ., url: api_url($root; .) } ]
    | map(select(.url | startswith("__") | not))
    | group_by(.url)
    | map([ .[0].url, (map(.profile) | join(", ")) ] | @tsv)
    | .[]' "${EAS_JSON}"
}

url_host() {
  local host="${1#*://}" # drop the scheme
  host="${host%%/*}"     # drop the path
  host="${host##*@}"     # drop any userinfo
  printf '%s' "${host%%:*}"
}

host_resolves() {
  local host="$1" attempts="${2:-1}" i
  for ((i = 1; i <= attempts; i++)); do
    if [ -n "$(getent hosts "${host}" 2>/dev/null || true)" ]; then
      return 0
    fi
    if [ "${i}" -lt "${attempts}" ]; then
      sleep 2
    fi
  done
  return 1
}

if ! command -v jq &>/dev/null || [ ! -f "${EAS_JSON}" ]; then
  # Already counted as a failure by check 1; nothing left to read the URL from.
  warn "API host check skipped — needs jq and mobile/eas.json"
elif [ -n "${PROFILE}" ]; then
  API_URL="$(profile_api_url "${PROFILE}")"
  case "${API_URL}" in
    __NO_SUCH_PROFILE__)
      fail "Build profile '${PROFILE}' is not defined in mobile/eas.json (known: $(jq -r '.build | keys | join(", ")' "${EAS_JSON}"))"
      ERRORS=$((ERRORS + 1))
      ;;
    __NO_URL__)
      fail "Build profile '${PROFILE}' sets no EXPO_PUBLIC_API_BASE_URL in mobile/eas.json"
      printf "       The build would silently fall back to the default baked into app.config.ts.\n"
      ERRORS=$((ERRORS + 1))
      ;;
    *)
      API_HOST="$(url_host "${API_URL}")"
      if host_resolves "${API_HOST}" 3; then
        pass "API host '${API_HOST}' of profile '${PROFILE}' resolves (${API_URL})"
      else
        fail "API host '${API_HOST}' of profile '${PROFILE}' resolves to no address"
        printf "       EXPO_PUBLIC_API_BASE_URL=%s (mobile/eas.json)\n" "${API_URL}"
        printf "       That value is inlined into the JS bundle: the build would succeed, the\n"
        printf "       submission would succeed, and every network call of the installed app\n"
        printf "       would fail on DNS. Refusing to build.\n"
        ERRORS=$((ERRORS + 1))
      fi
      ;;
  esac
else
  # No profile: report, never gate. Keeps a bare run usable as a pre-flight.
  DNS_OK=true
  while IFS=$'\t' read -r api_url api_profiles; do
    [ -z "${api_url}" ] && continue
    api_host="$(url_host "${api_url}")"
    if ! host_resolves "${api_host}" 1; then
      warn "API host '${api_host}' resolves to no address — used by profile(s): ${api_profiles}"
      printf "       Run this script with that profile name to gate a build on it.\n"
      DNS_OK=false
    fi
  done < <(all_api_urls)

  if [ "${DNS_OK}" = true ]; then
    pass "Every EXPO_PUBLIC_API_BASE_URL host in mobile/eas.json resolves"
  fi
fi

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
if [ "${ERRORS}" -eq 0 ]; then
  printf "${GREEN}All checks passed.${NC}\n"
  exit 0
else
  printf "${RED}%d check(s) failed.${NC} Fix the issues above before running eas build.\n" "${ERRORS}"
  exit 1
fi
