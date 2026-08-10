#!/usr/bin/env bash

# Runs the Maestro iOS suite one flow at a time so each flow gets its own JUnit
# case, and so a flow that already passed for this exact app + flow fingerprint
# is not replayed on the next attempt.

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

  if grep -qxF "$name" "$passed_file"; then
    echo "::notice::Skipping ${name}: already passed for this app and flow fingerprint."
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
    printf '%s\n' "$name" >> "$passed_file"
  else
    echo "::error::Maestro flow ${name} failed."
    failed=1
  fi
  echo "::endgroup::"
done

exit "$failed"
