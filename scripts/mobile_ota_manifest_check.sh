#!/usr/bin/env bash
# Verify that the update EAS *serves* carries the API base URL its build profile
# declares. Run it right after `eas update`.
#
# Why the manifest and not the JS bundle. No application file dereferences
# `process.env.EXPO_PUBLIC_API_BASE_URL`: mobile/app.config.ts reads it at
# *config* time into `extra.apiBaseUrl`, and the app reads
# `Constants.expoConfig.extra.apiBaseUrl` (mobile/src/constants/config.ts), which
# expo-constants resolves from `manifest.extra.expoClient`
# (node_modules/expo-constants/build/Constants.js). The value therefore travels in
# the **update manifest** and is never inlined into mobile/dist/. The step that
# used to `grep -raqF "$EXPO_PUBLIC_API_BASE_URL" dist/` was checking a place the
# value cannot be, so it failed every OTA it ever gated — twice on both platforms
# on 2026-09-04, on updates whose manifests were correct.
#
# Usage:
#   bash scripts/mobile_ota_manifest_check.sh --profile internal --platform ios \
#        --runtime-version <fingerprint-hash> [--project-id <uuid>] [--attempts N]
#
#   bash scripts/mobile_ota_manifest_check.sh --profile internal --platform ios \
#        --manifest-file <path>
#     Offline form: check a manifest already in hand (a curl capture, or a
#     fabricated one to prove the guard still fails). No network, no project id.
#
# The runtime version to pass is the native fingerprint hash. app.config.ts sets
# `runtimeVersion: { policy: "fingerprint" }`, so the hash `eas
# fingerprint:generate` prints and the `runtimeVersion` of the published update
# are the same string — verified 2026-09-04 against the manifests u.expo.dev
# served for the two fingerprints computed by workflow run 33879183625.
#
# That equality is also what makes this guard catch the precedence trap described
# in mobile/MOBILE_CI_CD.md: `extra` is part of the fingerprint (@expo/fingerprint
# only drops it under `SourceSkips.ExpoConfigExtraSection`, which nothing sets
# here), so an `eas update` that resolved a *different* API URL publishes under a
# *different* runtime version — and asking for the profile's own fingerprint then
# comes back 404, which this script reports as a failure.
#
# Exit codes:
#   0 — the served manifest carries exactly the profile's API base URL
#   1 — it does not, or no manifest could be read
#   2 — bad usage
#
# Prerequisites: jq, curl (fetch mode), npx + mobile/node_modules (only to resolve
# the project id, and only when --project-id is not given).

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { printf "${GREEN}[PASS]${NC} %s\n" "$1"; }
fail() { printf "${RED}[FAIL]${NC} %s\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MOBILE_DIR="${REPO_ROOT}/mobile"
EAS_JSON="${MOBILE_DIR}/eas.json"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/mobile_ota_manifest_check.sh --profile <name> --platform <ios|android>
       --runtime-version <hash> [--project-id <uuid>] [--attempts <n>]
  bash scripts/mobile_ota_manifest_check.sh --profile <name> --platform <ios|android>
       --manifest-file <path>

  --profile          Build profile of mobile/eas.json whose EXPO_PUBLIC_API_BASE_URL
                     and channel the served manifest must match (e.g. internal).
  --platform         Platform to request the manifest for.
  --runtime-version  The published update's runtime version, i.e. the native
                     fingerprint hash (`eas fingerprint:generate -e <profile>`).
  --project-id       EAS project id. Resolved from the exported app config when
                     omitted.
  --attempts         Fetch attempts before giving up (default 3, 5 s apart).
  --manifest-file    Check this file instead of fetching. Accepts either a raw
                     multipart response body or a bare manifest JSON.
EOF
}

PROFILE=""
PLATFORM=""
RUNTIME_VERSION=""
PROJECT_ID=""
MANIFEST_FILE=""
ATTEMPTS=3

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --platform)
      PLATFORM="${2:-}"
      shift 2
      ;;
    --runtime-version)
      RUNTIME_VERSION="${2:-}"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --manifest-file)
      MANIFEST_FILE="${2:-}"
      shift 2
      ;;
    --attempts)
      ATTEMPTS="${2:-}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument '$1'"
      usage
      exit 2
      ;;
  esac
done

if [ -z "${PROFILE}" ] || [ -z "${PLATFORM}" ]; then
  fail "--profile and --platform are both required"
  usage
  exit 2
fi

case "${PLATFORM}" in
  ios | android) ;;
  *)
    fail "--platform must be 'ios' or 'android' (got '${PLATFORM}')"
    exit 2
    ;;
esac

if [ -z "${MANIFEST_FILE}" ] && [ -z "${RUNTIME_VERSION}" ]; then
  fail "--runtime-version is required unless --manifest-file is given"
  usage
  exit 2
fi

if [ -n "${MANIFEST_FILE}" ] && [ ! -f "${MANIFEST_FILE}" ]; then
  fail "--manifest-file '${MANIFEST_FILE}' does not exist"
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  fail "jq is not installed (required to read mobile/eas.json and the manifest)"
  exit 1
fi

if [ ! -f "${EAS_JSON}" ]; then
  fail "mobile/eas.json not found"
  exit 1
fi

# ------------------------------------------------------------------
# What the profile declares
#
# `extends` is followed the way scripts/mobile_release_check.sh follows it:
# development-simulator carries neither an env block nor a channel of its own.
# ------------------------------------------------------------------
JQ_LOOKUP='def lookup($root; $name; $path):
  $root.build[$name] as $p
  | if $p == null then "__NO_SUCH_PROFILE__"
    elif ($p | getpath($path) // null) != null then ($p | getpath($path) | tostring)
    elif ($p.extends // null) != null then lookup($root; $p.extends; $path)
    else "__ABSENT__"
    end;'

profile_field() {
  jq -r --arg name "${PROFILE}" --argjson path "$1" \
    "${JQ_LOOKUP}"' lookup(.; $name; $path)' "${EAS_JSON}"
}

EXPECTED_URL="$(profile_field '["env","EXPO_PUBLIC_API_BASE_URL"]')"
CHANNEL="$(profile_field '["channel"]')"

case "${EXPECTED_URL}" in
  __NO_SUCH_PROFILE__)
    fail "Build profile '${PROFILE}' is not defined in mobile/eas.json (known: $(jq -r '.build | keys | join(", ")' "${EAS_JSON}"))"
    exit 1
    ;;
  __ABSENT__)
    fail "Build profile '${PROFILE}' sets no EXPO_PUBLIC_API_BASE_URL in mobile/eas.json"
    printf "       There is nothing to compare the served manifest against, and app.config.ts\n"
    printf "       now refuses to resolve without that variable — no fallback host exists.\n"
    exit 1
    ;;
esac

if [ "${CHANNEL}" = "__ABSENT__" ]; then
  fail "Build profile '${PROFILE}' declares no update channel in mobile/eas.json"
  printf "       Nothing published from it can be served, so there is no manifest to check.\n"
  exit 1
fi

echo "=== OTA manifest check ==="
echo "Profile:          ${PROFILE}"
echo "Channel:          ${CHANNEL}"
echo "Platform:         ${PLATFORM}"
echo "Expected API URL: ${EXPECTED_URL}  (mobile/eas.json, build.${PROFILE}.env)"
echo ""

# ------------------------------------------------------------------
# The manifest: fetched from the update server, or read from a file
# ------------------------------------------------------------------

# A manifest response is `multipart/mixed` even at protocol version 0 (measured
# 2026-09-04): CRLF-delimited parts named "manifest" and "extensions", each part
# one line of compact JSON. A bare JSON body is accepted too, so a manifest
# captured or fabricated by hand can be fed in with --manifest-file.
extract_manifest_json() {
  local body="$1" json
  if jq -e . "${body}" >/dev/null 2>&1; then
    cat "${body}"
    return 0
  fi
  json="$(tr -d '\r' < "${body}" |
    awk '/name="manifest"/ { in_part = 1; next } in_part && /^\{/ { print; exit }')"
  if [ -n "${json}" ] && printf '%s' "${json}" | jq -e . >/dev/null 2>&1; then
    printf '%s' "${json}"
    return 0
  fi
  return 1
}

BODY_FILE=""
HEADER_FILE=""
cleanup() {
  [ -n "${BODY_FILE}" ] && rm -f "${BODY_FILE}"
  [ -n "${HEADER_FILE}" ] && rm -f "${HEADER_FILE}"
  return 0
}
trap cleanup EXIT

if [ -n "${MANIFEST_FILE}" ]; then
  BODY_FILE="$(mktemp)"
  cat "${MANIFEST_FILE}" > "${BODY_FILE}"
  echo "Manifest source:  ${MANIFEST_FILE} (offline, no fetch)"
else
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl is not installed (required to fetch the manifest)"
    exit 1
  fi

  # The endpoint the installed binary polls. Read out of the exported config
  # rather than rebuilt from a pasted UUID, so a stale copy cannot make this
  # check interrogate a project that publishes nothing.
  if [ -z "${PROJECT_ID}" ]; then
    if ! PUBLIC_CONFIG="$(cd "${MOBILE_DIR}" && npx --no-install expo config --type public --json)"; then
      fail "Could not export the app config (npx expo config --type public --json)"
      printf "       Run it from mobile/ to see why, or pass --project-id explicitly.\n"
      exit 1
    fi
    PROJECT_ID="$(printf '%s' "${PUBLIC_CONFIG}" | jq -r '.extra.eas.projectId // empty')"
    RESOLVED_URL="$(printf '%s' "${PUBLIC_CONFIG}" | jq -r '.extra.apiBaseUrl // empty')"
    if [ -z "${PROJECT_ID}" ]; then
      fail "The exported app config carries no extra.eas.projectId"
      exit 1
    fi
    echo "Project id:       ${PROJECT_ID}  (exported app config)"
    echo "Config extra:     ${RESOLVED_URL:-<empty>}  (this checkout, for reference)"
  else
    echo "Project id:       ${PROJECT_ID}  (--project-id)"
  fi

  UPDATE_URL="https://u.expo.dev/${PROJECT_ID}"
  BODY_FILE="$(mktemp)"
  HEADER_FILE="$(mktemp)"
  HTTP_CODE=""
  for attempt in $(seq 1 "${ATTEMPTS}"); do
    HTTP_CODE="$(curl -sS --max-time 30 \
      -o "${BODY_FILE}" -D "${HEADER_FILE}" -w '%{http_code}' \
      -H "expo-platform: ${PLATFORM}" \
      -H "expo-channel-name: ${CHANNEL}" \
      -H "expo-runtime-version: ${RUNTIME_VERSION}" \
      "${UPDATE_URL}" || true)"
    if [ "${HTTP_CODE}" = "200" ]; then
      break
    fi
    if [ "${attempt}" -lt "${ATTEMPTS}" ]; then
      echo "Attempt ${attempt}/${ATTEMPTS}: HTTP ${HTTP_CODE:-<none>} — retrying in 5 s (CDN propagation)."
      sleep 5
    fi
  done

  echo "Manifest source:  ${UPDATE_URL} (runtime ${RUNTIME_VERSION}, HTTP ${HTTP_CODE:-<none>})"

  if [ "${HTTP_CODE}" != "200" ]; then
    fail "The update server serves no manifest for channel '${CHANNEL}', platform '${PLATFORM}', runtime version '${RUNTIME_VERSION}' (HTTP ${HTTP_CODE:-<none>})."
    printf "       Response: %s\n" "$(head -c 300 "${BODY_FILE}" | tr -d '\n')"
    printf "       Either nothing was published, or the publish resolved a different\n"
    printf "       runtime version than this profile's fingerprint — which happens when\n"
    printf "       'eas update' resolves other EXPO_PUBLIC_* values than the profile does\n"
    printf "       (the EAS environment wins over eas.json on the update path; see\n"
    printf "       mobile/MOBILE_CI_CD.md). Devices holding this profile's binaries would\n"
    printf "       then never receive the update. Check 'eas env:list' for a key defined\n"
    printf "       on both sides.\n"
    exit 1
  fi
fi

if ! MANIFEST_JSON="$(extract_manifest_json "${BODY_FILE}")"; then
  fail "Could not read a manifest out of the response body"
  if [ -n "${HEADER_FILE}" ]; then
    printf "       %s\n" "$(grep -i '^content-type:' "${HEADER_FILE}" | tr -d '\r' || true)"
  fi
  printf "       First 300 bytes: %s\n" "$(head -c 300 "${BODY_FILE}" | tr -d '\n')"
  exit 1
fi

MANIFEST_ID="$(printf '%s' "${MANIFEST_JSON}" | jq -r '.id // "<none>"')"
MANIFEST_CREATED="$(printf '%s' "${MANIFEST_JSON}" | jq -r '.createdAt // "<none>"')"
MANIFEST_RUNTIME="$(printf '%s' "${MANIFEST_JSON}" | jq -r '.runtimeVersion // "<none>"')"

# The one path that matters: expo-constants exposes `manifest.extra.expoClient`
# as `Constants.expoConfig`, so this is literally the string the running app
# concatenates its request URLs from.
SERVED_URL="$(printf '%s' "${MANIFEST_JSON}" | jq -r '.extra.expoClient.extra.apiBaseUrl // empty')"

echo "Update id:        ${MANIFEST_ID}"
echo "Created at:       ${MANIFEST_CREATED}"
echo "Runtime version:  ${MANIFEST_RUNTIME}"
echo "Served API URL:   ${SERVED_URL:-<absent>}"
echo ""

if [ -z "${SERVED_URL}" ]; then
  fail "The served manifest carries no extra.expoClient.extra.apiBaseUrl."
  printf "       The app would have no API host at all: Config.API_BASE_URL throws on\n"
  printf "       startup (mobile/src/constants/config.ts) — there is no fallback host.\n"
  printf "       Roll the update back now:\n"
  printf "         cd mobile && eas update:rollback\n"
  printf "         cd mobile && eas update:roll-back-to-embedded --channel %s --platform %s\n" "${CHANNEL}" "${PLATFORM}"
  exit 1
fi

if [ "${SERVED_URL}" != "${EXPECTED_URL}" ]; then
  fail "The served manifest points the app at another host than profile '${PROFILE}' declares."
  printf "       served:   %s\n" "${SERVED_URL}"
  printf "       expected: %s  (mobile/eas.json, build.%s.env)\n" "${EXPECTED_URL}" "${PROFILE}"
  printf "       This update is ALREADY LIVE on channel '%s'. Roll it back now:\n" "${CHANNEL}"
  printf "         cd mobile && eas update:rollback\n"
  printf "         cd mobile && eas update:roll-back-to-embedded --channel %s --platform %s\n" "${CHANNEL}" "${PLATFORM}"
  printf "       Then look for an EXPO_PUBLIC_API_BASE_URL defined in the EAS environment\n"
  printf "       ('eas env:list'): on the update path it overrides eas.json.\n"
  exit 1
fi

pass "Channel '${CHANNEL}' serves ${SERVED_URL} to ${PLATFORM} on runtime ${MANIFEST_RUNTIME}."
exit 0
