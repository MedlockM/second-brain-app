#!/usr/bin/env bash
#
# tf_plan_guard.sh — refuse to let a Terraform plan for one environment touch
# another environment's resources.
#
# Implements layers 2, 3 and 4 of the proof suite from
# docs/research/task-221-terraform-multi-env-isolation/README.md §6. Layer 1 is
# structural (each envs/<env>/ directory pins a literal backend key, so a plan
# can only ever propose changes to resources present in its own state) and
# layer 5 is a post-apply refresh-only plan against the OTHER environments.
#
# Usage:
#   scripts/tf_plan_guard.sh <env> <planfile> [other-env ...]
#
# Examples:
#   # Gate a first staging plan and cross-check it against live dev names:
#   terraform -chdir=infrastructure/terraform/envs/staging plan -out=tfplan
#   scripts/tf_plan_guard.sh staging tfplan dev
#
#   # Gate a dev plan during the task-237 migration (no cross-check needed):
#   scripts/tf_plan_guard.sh dev tfplan
#
# Exit codes: 0 = plan is safe to apply, 1 = hard fail, do NOT apply.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <env> <planfile> [other-env ...]" >&2
  exit 64
fi

ENV_NAME="$1"
PLAN_FILE="$2"
shift 2
OTHER_ENVS=("$@")

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${REPO_ROOT}/infrastructure/terraform/envs/${ENV_NAME}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

case "${ENV_NAME}" in
  dev | staging | prod) ;;
  *)
    echo "FAIL: unknown environment '${ENV_NAME}' (expected dev, staging or prod)" >&2
    exit 1
    ;;
esac

if [[ ! -d "${ENV_DIR}" ]]; then
  echo "FAIL: ${ENV_DIR} does not exist" >&2
  exit 1
fi

for tool in terraform jq comm sort; do
  command -v "${tool}" >/dev/null || {
    echo "FAIL: ${tool} is not installed" >&2
    exit 1
  }
done

# Name-bearing attributes worth checking. S3 bucket names and the shared ECR
# repository are handled separately (see layer 3 below).
NAME_KEYS='[.name, .bucket, .function_name, .repository_name, .alarm_name, .dashboard_name, .queue_name]'

PLAN_JSON="${WORK_DIR}/plan.json"
terraform -chdir="${ENV_DIR}" show -json "${PLAN_FILE}" >"${PLAN_JSON}"

echo "== Layer 2: no destructive action in the ${ENV_NAME} plan =========="

DESTRUCTIVE=$(jq '[.resource_changes[]? | select(.change.actions | index("delete"))] | length' "${PLAN_JSON}")
if [[ "${DESTRUCTIVE}" -ne 0 ]]; then
  echo "FAIL: the plan contains ${DESTRUCTIVE} delete action(s):" >&2
  jq -r '.resource_changes[]? | select(.change.actions | index("delete")) | "  - \(.address) [\(.change.actions | join(","))]"' "${PLAN_JSON}" >&2
  echo >&2
  echo "A delete in an environment plan means either a rename of a ForceNew" >&2
  echo "attribute (data loss: follow the M3 runbook in" >&2
  echo "infrastructure/terraform/README.md instead) or the wrong state." >&2
  exit 1
fi
echo "OK: 0 delete actions."

echo
echo "== Layer 3: every created name carries the '-${ENV_NAME}' token ===="

# S3 bucket names already end with -<env> by their own convention, and the
# shared ECR repository is not managed by an environment root at all, so it can
# never appear here.
UNSUFFIXED="${WORK_DIR}/unsuffixed.txt"
jq -r "
  .resource_changes[]?
  | select(.change.actions | index(\"create\"))
  | .change.after // {}
  | ${NAME_KEYS}
  | .[] | select(. != null) | select(type == \"string\")
" "${PLAN_JSON}" | sort -u | grep -vE -- "-${ENV_NAME}\$" >"${UNSUFFIXED}" || true

# Whitelist: names that legitimately carry no environment token.
#   $default            — the API Gateway default stage, an AWS-reserved literal
#   <domain names>       — custom domains are already per-environment hostnames
grep -vE '^\$default$' "${UNSUFFIXED}" >"${UNSUFFIXED}.filtered" || true
mv "${UNSUFFIXED}.filtered" "${UNSUFFIXED}"

if [[ -s "${UNSUFFIXED}" ]]; then
  echo "FAIL: the plan creates resources whose name lacks the '-${ENV_NAME}' token:" >&2
  sed 's/^/  - /' "${UNSUFFIXED}" >&2
  exit 1
fi
echo "OK: every created name ends with -${ENV_NAME}."

if [[ ${#OTHER_ENVS[@]} -eq 0 ]]; then
  echo
  echo "== Layer 4: skipped (no other environment given) =================="
  echo
  echo "PASS: the ${ENV_NAME} plan is safe to apply."
  exit 0
fi

echo
echo "== Layer 4: no name collision with the live environments =========="

PLANNED="${WORK_DIR}/planned_names.txt"
jq -r "
  .resource_changes[]?
  | .change.after // {}
  | ${NAME_KEYS}
  | .[] | select(. != null) | select(type == \"string\")
" "${PLAN_JSON}" | sort -u >"${PLANNED}"

COLLISIONS=0
for other in "${OTHER_ENVS[@]}"; do
  OTHER_DIR="${REPO_ROOT}/infrastructure/terraform/envs/${other}"
  if [[ ! -d "${OTHER_DIR}" ]]; then
    echo "FAIL: cannot cross-check against '${other}': ${OTHER_DIR} does not exist" >&2
    exit 1
  fi

  LIVE="${WORK_DIR}/live_${other}.txt"
  # `show -json` with no plan file dumps the CURRENT state of that environment.
  terraform -chdir="${OTHER_DIR}" show -json |
    jq -r "
      [.values.root_module? // {} | .. | .values? // empty]
      | .[] | ${NAME_KEYS}
      | .[] | select(. != null) | select(type == \"string\")
    " | sort -u >"${LIVE}"

  FOUND="${WORK_DIR}/collisions_${other}.txt"
  comm -12 "${PLANNED}" "${LIVE}" >"${FOUND}"

  if [[ -s "${FOUND}" ]]; then
    echo "FAIL: the ${ENV_NAME} plan names resources that ${other} already owns:" >&2
    sed 's/^/  - /' "${FOUND}" >&2
    COLLISIONS=1
  else
    echo "OK: no collision with ${other} ($(wc -l <"${LIVE}") live names checked)."
  fi
done

if [[ "${COLLISIONS}" -ne 0 ]]; then
  echo >&2
  echo "Do NOT apply. A shared name means the two environments would fight over" >&2
  echo "the same physical AWS resource." >&2
  exit 1
fi

echo
echo "PASS: the ${ENV_NAME} plan is safe to apply."
