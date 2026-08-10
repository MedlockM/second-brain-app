#!/usr/bin/env bash

set -euo pipefail

readonly flow_dir="mobile/.maestro"

# The debug APK embeds its JS bundle and does not need Metro.
adb install -r mobile/android/app/build/outputs/apk/debug/app-debug.apk
adb wait-for-device
sleep 10

flow_path="$flow_dir"
if [[ -n "${FLOW_FILTER:-}" ]]; then
  flow_path="$flow_dir/${FLOW_FILTER}.yaml"
fi

maestro test "$flow_path" \
  --env=TEST_USER_EMAIL="$TEST_USER_EMAIL" \
  --env=TEST_USER_PASSWORD="$TEST_USER_PASSWORD" \
  --env=MAESTRO_RUN_ID="$MAESTRO_RUN_ID" \
  --env=SEARCH_TEST_TERM="$SEARCH_TEST_TERM" \
  --env=API_BASE_URL="$API_BASE_URL" \
  --env=SHARE_TEST_URL="$SHARE_TEST_URL" \
  --format=junit \
  --output=maestro-report.xml
