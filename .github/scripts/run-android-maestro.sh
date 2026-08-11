#!/usr/bin/env bash

# Android entry point for the shared Maestro flow-runner. Everything about
# per-flow reporting, resume markers and retries lives in lib/maestro-flows.sh;
# this file holds only what is specific to the emulator.

set -euo pipefail

readonly report_dir="maestro-android-reports"
readonly passed_file="${MAESTRO_PASSED_FILE:-.maestro-android-passed}"
readonly platform_label="Android"
readonly apk_path="mobile/android/app/build/outputs/apk/debug/app-debug.apk"

# The emulator drops out of adb often enough to matter, and a lost device is a
# runner fault rather than a product fault: retry it against a reconnected
# device instead of reporting a failing flow.
readonly infrastructure_errors='device offline|device .* not found|no devices/emulators found|adb: device|DeviceUnreachableException|became unreachable'

# adb usually recovers on its own once the server is restarted; the app is
# reinstalled afterwards because a dropped device can lose the install.
recover_device() {
  adb kill-server 2>/dev/null || true
  sleep 5
  adb start-server 2>/dev/null || true
  adb wait-for-device
  # Give the framework time to come back before driving the UI again.
  adb shell 'while [[ "$(getprop sys.boot_completed)" != "1" ]]; do sleep 2; done' 2>/dev/null || true
  adb install -r "$apk_path" || true
}

# The debug APK embeds its JS bundle and does not need Metro.
adb install -r "$apk_path"
adb wait-for-device
sleep 10

source "$(dirname "$0")/lib/maestro-flows.sh"

run_flows
