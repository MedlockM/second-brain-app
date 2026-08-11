#!/usr/bin/env bash

# iOS entry point for the shared Maestro flow-runner. Everything about
# per-flow reporting, resume markers and retries lives in lib/maestro-flows.sh;
# this file holds only what is specific to the simulator.

set -euo pipefail

readonly report_dir="maestro-ios-reports"
readonly passed_file="${MAESTRO_PASSED_FILE:-.maestro-ios-passed}"
readonly platform_label="iOS"
readonly build_dir="mobile/ios/build"

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
recover_device() {
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

source "$(dirname "$0")/lib/maestro-flows.sh"

run_flows
