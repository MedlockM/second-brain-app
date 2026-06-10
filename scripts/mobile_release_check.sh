#!/usr/bin/env bash
# Validate EAS build prerequisites for the mobile app.
# Run this before any `eas build` invocation to catch config issues early.
#
# Usage:
#   bash scripts/mobile_release_check.sh
#
# Exit codes:
#   0 — all checks pass
#   1 — one or more checks failed
#
# Prerequisites:
#   - jq installed (for JSON validation)

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

ERRORS=0

echo "=== Mobile Release Pre-flight Check ==="
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

# Keys that are allowed to be empty (deferred to later tasks)
OPTIONAL_KEYS="EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID"

if [ ! -f "${ENV_EXAMPLE}" ]; then
  fail "mobile/.env.example not found — cannot validate env vars"
  ERRORS=$((ERRORS + 1))
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

    # Check if key is optional
    IS_OPTIONAL=false
    for opt_key in ${OPTIONAL_KEYS}; do
      if [ "${KEY}" = "${opt_key}" ]; then
        IS_OPTIONAL=true
        break
      fi
    done

    if [ -z "${VALUE}" ]; then
      if [ "${IS_OPTIONAL}" = true ]; then
        warn "${KEY} is empty (allowed — deferred)"
      else
        fail "${KEY} is missing or empty in mobile/.env"
        ENV_OK=false
        ERRORS=$((ERRORS + 1))
      fi
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

BUNDLE_FILES=(
  "mobile/app.config.ts"
  "mobile/plugins/withShareExtension.js"
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
