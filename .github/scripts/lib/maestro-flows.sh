#!/usr/bin/env bash

# Shared flow-runner for the Maestro suites, sourced by the per-platform
# scripts. It runs one flow per Maestro invocation so each flow gets its own
# JUnit case, and records which flows passed so the next attempt replays only
# what is still red.
#
# A flow is skipped when the marker file already holds its name plus the hash of
# the flow and every sub-flow it pulls in. Editing one flow therefore replays
# that flow only: a green 01_login stays green while 07_paywall is iterated on.
# The app binary is covered separately by the workflow's cache key.
#
# The caller sets, before sourcing:
#   report_dir        where JUnit reports and hierarchy dumps are written
#   passed_file       marker file listing "<flow>:<hash>" of passing flows
#   platform_label    used in log messages ("iOS" / "Android")
#   infrastructure_errors  regex of failures worth retrying (optional)
# and may define `recover_device`, called between retries.

readonly flow_dir="mobile/.maestro"
readonly max_attempts=3

# macOS ships shasum, Linux images ship both; prefer whichever exists so the
# same fingerprint helper works on either runner.
sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256
  else
    sha256sum
  fi
}

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
    | sha256 \
    | cut -c1-12
}

# The flows a run covers: the filter's suite expanded into its members, or every
# top-level flow when no filter is given.
resolve_flows() {
  if [[ -n "${FLOW_FILTER:-}" ]]; then
    expand_flow "$flow_dir/${FLOW_FILTER}.yaml"
  else
    find "$flow_dir" -maxdepth 1 -name '*.yaml' ! -name 'config.yaml' | sort
  fi
}

run_flows() {
  local flows=()
  local flow
  while IFS= read -r flow; do
    flows+=("$flow")
  done < <(resolve_flows)

  mkdir -p "$report_dir"
  touch "$passed_file"

  echo "Flows to run: ${flows[*]}"

  local failed=0
  local name marker log attempt
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

    log="${report_dir}/${name}.log"

    for attempt in $(seq 1 "$max_attempts"); do
      echo "::group::maestro test ${flow} (attempt ${attempt}/${max_attempts})"

      if maestro test "$flow" \
        --env=TEST_USER_EMAIL="$TEST_USER_EMAIL" \
        --env=TEST_USER_PASSWORD="$TEST_USER_PASSWORD" \
        --env=MAESTRO_RUN_ID="$MAESTRO_RUN_ID" \
        --env=SEARCH_TEST_TERM="$SEARCH_TEST_TERM" \
        --env=API_BASE_URL="$API_BASE_URL" \
        --env=SHARE_TEST_URL="$SHARE_TEST_URL" \
        --format=junit \
        --output="${report_dir}/${name}.xml" 2>&1 | tee "$log"; then
        printf '%s\n' "$marker" >> "$passed_file"
        echo "::endgroup::"
        break
      fi

      if [[ -n "${infrastructure_errors:-}" ]] \
        && grep -qE "$infrastructure_errors" "$log" \
        && [[ "$attempt" -lt "$max_attempts" ]]; then
        echo "::warning::${name} hit ${platform_label} driver/device trouble; recovering and retrying."
        echo "::endgroup::"
        if declare -F recover_device >/dev/null; then
          recover_device
        fi
        continue
      fi

      echo "::error::Maestro flow ${name} failed."
      failed=1
      # Names the screen the flow actually ended on, which the JUnit assertion
      # message alone never says. Carries no credentials and no screenshot, so it
      # is safe to publish from a public repository.
      maestro hierarchy > "${report_dir}/${name}-hierarchy.json" 2>&1 || true
      # A driver that never starts produces no JUnit file at all, which reads as
      # "flow never ran" in the artifact. Record the reason instead.
      if [[ ! -f "${report_dir}/${name}.xml" ]]; then
        cat > "${report_dir}/${name}.xml" <<XML
<?xml version='1.0' encoding='UTF-8'?>
<testsuites>
  <testsuite name="${name}" tests="1" failures="1">
    <testcase name="${name}" classname="${name}" file="${flow}">
      <failure message="Maestro produced no report; the ${platform_label} driver never started.">$(tail -c 2000 "$log" | tr -d '\000' | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')</failure>
    </testcase>
  </testsuite>
</testsuites>
XML
      fi
      echo "::endgroup::"
      break
    done

    rm -f "$log"
  done

  return "$failed"
}
