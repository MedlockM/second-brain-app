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
readonly build_dir="mobile/ios/build"
readonly max_attempts=3

# Running one flow per invocation means one XCUITest runner start-up per flow,
# and that hand-off is the flakiest part of the iOS stack: the driver sometimes
# never answers, or the simulator drops mid-launch. Both are runner faults, not
# product faults, so they are retried against a freshly rebooted simulator
# instead of being reported as a failing flow.
readonly infrastructure_errors='IOSDriverTimeoutException|DeviceUnreachableException|driver not ready in time|became unreachable'

simulator_udid() {
  xcrun simctl list devices available \
    | grep 'iPhone 16 (' \
    | head -1 \
    | grep -oE '[0-9A-F-]{36}'
}

# A stuck driver survives the Maestro process that spawned it, so the simulator
# is shut down and rebooted, then the app is reinstalled: the reboot wipes the
# installed bundle on some Xcode versions and a missing app looks like yet
# another unreachable device.
recover_simulator() {
  local udid app_path
  udid=$(simulator_udid)
  if [[ -z "$udid" ]]; then
    echo "::warning::No iPhone 16 simulator found; skipping recovery."
    return
  fi

  pkill -f 'maestro-driver-ios' 2>/dev/null || true
  xcrun simctl shutdown "$udid" 2>/dev/null || true
  sleep 5
  xcrun simctl boot "$udid" 2>/dev/null || true
  xcrun simctl bootstatus "$udid" -b

  app_path=$(find "$build_dir" -name '*.app' -path '*/Release-iphonesimulator/*' | head -1)
  if [[ -n "$app_path" ]]; then
    xcrun simctl install "$udid" "$app_path"
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

    if grep -qE "$infrastructure_errors" "$log" && [[ "$attempt" -lt "$max_attempts" ]]; then
      echo "::warning::${name} hit an iOS driver/simulator fault; recovering and retrying."
      echo "::endgroup::"
      recover_simulator
      continue
    fi

    echo "::error::Maestro flow ${name} failed."
    failed=1
    # A driver that never starts produces no JUnit file at all, which reads as
    # "flow never ran" in the artifact. Record the reason instead.
    if [[ ! -f "${report_dir}/${name}.xml" ]]; then
      cat > "${report_dir}/${name}.xml" <<XML
<?xml version='1.0' encoding='UTF-8'?>
<testsuites>
  <testsuite name="${name}" tests="1" failures="1">
    <testcase name="${name}" classname="${name}" file="${flow}">
      <failure message="Maestro produced no report; the iOS driver never started.">$(tail -c 2000 "$log" | tr -d '\000' | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')</failure>
    </testcase>
  </testsuite>
</testsuites>
XML
    fi
    # The view hierarchy names the screen the flow actually ended on, which the
    # JUnit assertion message alone never says. It carries no credentials and no
    # screenshot, so it is safe to publish from a public repository.
    echo "View hierarchy at failure:"
    maestro hierarchy > "${report_dir}/${name}-hierarchy.json" 2>&1 || true
    head -c 20000 "${report_dir}/${name}-hierarchy.json" || true
    echo "::endgroup::"
    break
  done

  rm -f "$log"
done

exit "$failed"
