#!/usr/bin/env bash

# Runs the Maestro iOS suite one flow at a time so each flow gets its own JUnit
# case, and records which flows passed so the next attempt replays only what is
# still red.
#
# A flow is skipped when the marker file already holds its name plus the hash of
# the flow and every sub-flow it pulls in. Editing one flow therefore replays
# that flow only: a green 01_login stays green while 07_paywall is iterated on.
# The app binary is covered separately by the workflow's cache key.

set -euo pipefail

readonly flow_dir="mobile/.maestro"
readonly report_dir="maestro-ios-reports"
readonly passed_file="${MAESTRO_PASSED_FILE:-.maestro-ios-passed}"

# Expand a suite file (a flow whose steps are only `runFlow:` entries) into the
# flows it chains, so the suite stays the single source of truth for its scope.
expand_flow() {
  local flow="$1"
  local step_count run_flow_count

  step_count=$(grep -cE '^- [a-zA-Z]+:' "$flow" || true)
  run_flow_count=$(grep -cE '^- runFlow: ' "$flow" || true)

  if [[ "$step_count" -eq 0 || "$run_flow_count" -ne "$step_count" ]]; then
    printf '%s\n' "$flow"
    return
  fi

  # References are relative to the suite file. Maestro accepts the resulting
  # path verbatim, and `basename` still yields the flow name for reports.
  local base referenced
  base=$(dirname "$flow")
  while read -r referenced; do
    printf '%s/%s\n' "$base" "$referenced"
  done < <(sed -nE 's/^- runFlow: (.+)$/\1/p' "$flow")
}

# Every file a flow depends on: itself, then each `runFlow:` target, resolved
# relative to the referring file and followed recursively.
collect_dependencies() {
  local flow="$1"
  shift
  # `${@:+...}` keeps this valid under `set -u` on the first, argument-less call.
  local seen=(${@:+"$@"})

  local previous
  for previous in ${seen[@]:+"${seen[@]}"}; do
    [[ "$previous" == "$flow" ]] && return
  done

  printf '%s\n' "$flow"
  seen+=("$flow")

  [[ -f "$flow" ]] || return

  local base referenced
  base=$(dirname "$flow")
  while read -r referenced; do
    collect_dependencies "${base}/${referenced}" "${seen[@]}"
  done < <(sed -nE 's/^[[:space:]]*(- )?(runFlow|file): (.+)$/\3/p' "$flow")
}

flow_fingerprint() {
  local flow="$1"
  collect_dependencies "$flow" \
    | sort -u \
    | while read -r dependency; do
        [[ -f "$dependency" ]] && cat "$dependency"
      done \
    | shasum -a 256 \
    | cut -c1-12
}

flows=()
if [[ -n "${FLOW_FILTER:-}" ]]; then
  while IFS= read -r expanded; do
    flows+=("$expanded")
  done < <(expand_flow "$flow_dir/${FLOW_FILTER}.yaml")
else
  while IFS= read -r flow; do
    flows+=("$flow")
  done < <(find "$flow_dir" -maxdepth 1 -name '*.yaml' ! -name 'config.yaml' | sort)
fi

mkdir -p "$report_dir"
touch "$passed_file"

echo "Flows to run: ${flows[*]}"

failed=0
for flow in "${flows[@]}"; do
  name=$(basename "$flow" .yaml)
  marker="${name}:$(flow_fingerprint "$flow")"

  if grep -qxF "$marker" "$passed_file"; then
    echo "::notice::Skipping ${name}: already passed unchanged against this app build."
    # Keep the artifact complete: a skipped flow is a flow that passed earlier
    # against this same app build and flow content.
    cat > "${report_dir}/${name}.xml" <<XML
<?xml version='1.0' encoding='UTF-8'?>
<testsuites>
  <testsuite name="${name}" tests="1" failures="0" skipped="1">
    <testcase name="${name}" classname="${name}" file="${flow}">
      <skipped message="Passed on an earlier attempt against this app build; not replayed."/>
    </testcase>
  </testsuite>
</testsuites>
XML
    continue
  fi

  echo "::group::maestro test ${flow}"
  if maestro test "$flow" \
    --env=TEST_USER_EMAIL="$TEST_USER_EMAIL" \
    --env=TEST_USER_PASSWORD="$TEST_USER_PASSWORD" \
    --env=MAESTRO_RUN_ID="$MAESTRO_RUN_ID" \
    --env=SEARCH_TEST_TERM="$SEARCH_TEST_TERM" \
    --env=API_BASE_URL="$API_BASE_URL" \
    --env=SHARE_TEST_URL="$SHARE_TEST_URL" \
    --format=junit \
    --output="${report_dir}/${name}.xml"; then
    printf '%s\n' "$marker" >> "$passed_file"
  else
    echo "::error::Maestro flow ${name} failed."
    failed=1
  fi
  echo "::endgroup::"
done

exit "$failed"
