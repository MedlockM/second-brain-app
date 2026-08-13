
<!-- BACKLOG.MD MCP GUIDELINES START -->

<CRITICAL_INSTRUCTION>

## BACKLOG WORKFLOW INSTRUCTIONS

This project uses Backlog.md MCP for all task and project management activities.

**CRITICAL GUIDANCE**

- If your client supports MCP resources, read `backlog://workflow/overview` to understand when and how to use Backlog for this project.
- If your client only supports tools or the above request fails, call `backlog.get_workflow_overview()` tool to load the tool-oriented overview (it lists the matching guide tools).

- **First time working here?** Read the overview resource IMMEDIATELY to learn the workflow
- **Already familiar?** You should have the overview cached ("## Backlog.md Overview (MCP)")
- **When to read it**: BEFORE creating tasks, or when you're unsure whether to track work

These guides cover:
- Decision framework for when to create tasks
- Search-first workflow to avoid duplicates
- Links to detailed guides for task creation, execution, and completion
- MCP tools reference

You MUST read the overview resource to understand the complete workflow. The information is NOT summarized here.

</CRITICAL_INSTRUCTION>

<!-- BACKLOG.MD MCP GUIDELINES END -->

## Onboarding

Read `README.md` for project overview and V1 scope. Read `docs/CANONICAL_MEDIA_API_CONTRACT.md` for API contracts.

## Do NOT touch

- Any code related to: Spotify sync, email delivery, quiz generation, Whisper transcription, credit-based billing
- `/api/v1/` endpoints — canonical endpoints are `/api/media/*` and `/api/artifacts/*`

## Delivery rules

- Pre-production: no backward compatibility required. Remove obsolete code directly.
- No automated tests unless explicitly requested.
- Hexagonal architecture when already in place. KISS otherwise.
- Benchmarks must be exhaustive and based on internet research.
- LLM model, OCR service, cloud provider, and pricing model are all open choices — never hardcode a specific solution without a benchmark justifying it.
- Debug instrumentation is temporary. When you add `console.log` / `console.error` / `print` / extra log lines to diagnose a specific bug, **remove them as soon as the bug is fixed**, in the same session. Do not leave them in the codebase as "useful future logs" — they pollute the signal in real logs and rot. Keep only logs that belong to the permanent observability story (structured logger calls, telemetry events) and were already there before the investigation.

## Never write secrets or account identity into backlog tasks

**This repository is public and `main` is unprotected.** Anything you write into a task file, a research README, a dispatch summary or a commit message is published the moment `main` is pushed, and stays in the git history even if a later commit removes it. Task files are the highest-risk surface because agents naturally paste command output into `Implementation Notes` as proof of work.

Never write the following into any tracked file:

- **Root/login emails of cloud accounts**, including `+alias` forms. An AWS root email is half of a password reset on the account that runs production. This is not rotatable — it is the owner's billing identity.
- **Any credential or credential-shaped string**: access keys (`AKIA…`, `ASIA…`), secret access keys, session tokens, API keys, bearer tokens, OAuth client secrets, `ghp_`/`xox…` tokens, private keys, connection strings with a password, real user passwords.
- **Support/quota/case request identifiers** and any other opaque handle that identifies a session with a provider's support system.
- **Raw dumps of `aws sts get-caller-identity`, `create-organization`, `create-account`, `secretsmanager get-secret-value`, `terraform output`, or `.env` files.** Summarise the outcome; never paste the payload.

Write the *outcome* and the *way to retrieve the value*, not the value:

> Bad: `email owner+aws-prod@example.com`, request `a1b2c3d4e5f6…`
> Good: the member account's login is a `+aws-prod` alias of the management account's root email — deliberately not recorded here (public repo); retrieve it from the Organizations console. Quota `L-B99A9384`, PENDING; find the request via `aws service-quotas list-requested-service-quota-change-history --service-code lambda`.

**Resource identifiers that Terraform needs are not secrets and must stay.** AWS account IDs already appear in `allowed_account_ids`, state-bucket names and IAM ARNs across `infrastructure/terraform/`, so redacting them from a task note protects nothing and desynchronises the note from the code. Same for resource names, table names, region, ARNs and log-group names. The line is: *does this value let someone authenticate, reset a credential, or impersonate the owner?* If yes, it never gets written down. If it is just a name a `terraform plan` would print anyway, write it.

If a task genuinely cannot be documented without a secret, say so in the note and point to task-252 (`Provision the 37 runtime credentials of the prod secret`) — the owner holds those values.

Before you commit, grep your own diff. If you added an email, a token-shaped string or a support id, remove it before `git add`.

## Task creation convention

When creating a new task in the backlog, split it in two when the work requires a technology/architecture decision not yet made:

1. A **benchmark task** (label `benchmark`) — research, comparison, recommendation. Produces `docs/research/task-XX-<short-description>/README.md`.
2. An **implementation task** with `dependencies: [task-XX]` — generic description that tells the implementer to read the owner's final `Decision` from the README.

When the task is a bug fix, refactor, or well-understood feature with no open technology/architecture question, create a single task — do NOT create a dummy benchmark task.

### An acceptance criterion must be satisfiable by the agent that implements the task

This is the single rule behind everything below. An implementer runs **inside an isolated git worktree, on its own branch**. It does not merge, it does not push, and nothing it writes is deployed while it works. So an AC is only writable if the agent can satisfy it **from that worktree, during that run**. Anything else parks the task `In Progress` forever and silently blocks every dependent task.

Two families of ACs break this rule. Both are common and both must stop.

**1. ACs that require the code to be deployed.** "The dev API returns 204", "Lambda image rebuilt and redeployed", "the deployed endpoint answers". These are unsatisfiable *by construction*: `deploy-lambda.yml` only fires on push to `main`, and the implementer's code is on a branch that has been neither merged nor pushed. The agent cannot make its own change deployed — the ordering is impossible, not merely inconvenient. Today 34 of the 36 deploy-dependent ACs in the backlog are unticked, which is what this rule exists to stop.

**2. ACs written as unit tests.** "Function X returns Y for input Z", "the handler raises on an empty payload", "calling the service twice is idempotent". Beyond being a test spec masquerading as an AC, this contradicts the delivery rule above: **no automated tests unless explicitly requested**. An AC is a statement about *observable behaviour or the state of the codebase*, not an assertion an agent is expected to encode as a test it has been forbidden from writing.

**Write instead what the agent can actually reach from its worktree:**

- the code path exists and is wired: "every library read goes through `user_media`; no remaining call site reads `processing_jobs` as the library source of truth"
- a check the agent can run locally: `ruff`/`mypy` clean, `terraform validate` and `plan` exit 0, a targeted script exits 0
- a direct check against real infrastructure, which needs no deploy: DynamoDB/S3/SQS calls against `-dev` resources, an AWS CLI query, a table's TTL/PITR setting, an alarm driven to `ALARM` and back to `OK`
- the app exercised **in-process**: import the FastAPI app and call the route through it. This validates the route, its wiring and its status codes without any deploy, and is the honest version of "the endpoint answers".
- documentation and configuration are readable facts: the file says what it must say, the workflow invokes what it must invoke

**When a deploy genuinely matters, it belongs in the description, not in an AC.** Write it as a note to the owner: "LAUNCH PREREQUISITE: after this merges and `main` is pushed, verify `DELETE /api/account` answers 204 against the deployed dev image." The owner performs the push and can then check it. An AC that depends on an action only the owner can take is the owner's checklist item, not the agent's gate.

Same rule for **Maestro**: never write "a full E2E run passes on both platforms" or "the Maestro flows are green". Maestro is owner-triggered (`workflow_dispatch`), takes 10-50 minutes and is flaky on the iOS simulator. Carve-out: tasks whose deliverable *is* the Maestro suite legitimately reference it, because the flow's existence and its CI wiring are readable in the YAML — prefer "the flow exists and the job invokes it" over "the run is green". The rule targets a run used as a validation gate on unrelated work.

**This applies to task creation AND to task execution.** An implementer must not add such an AC either, and — the harder half — **must not rewrite an existing AC to match what it managed to achieve.** Editing "returns 0" into "returns 2", truncating a clause, or ticking a criterion your own evidence contradicts is falsification: it converts an honest blocker into a silent lie, and it has happened. When an AC turns out to be unsatisfiable, the correct move is to leave it unticked, state plainly in the Implementation Notes *why* it cannot be reached, and say so in the final summary. An unticked AC with a documented reason is a good outcome. A ticked AC that is not true is the worst possible one.

## Benchmark lifecycle

The owner signals their decision through the `owner_decision` field in the front-matter of the main `README.md` of the research directory. Five values are supported:

- `pending` — default, owner has not reviewed yet. Dispatcher does nothing.
- `ok` — benchmark accepted. Dispatcher marks the benchmark task `Done`, which unblocks the implementation task via its dependency.
- `abandoned` — benchmark rejected and task abandoned. Dispatcher archives the benchmark task and its directly paired implementation task. Other tasks that list this benchmark in their dependencies just get the dependency removed (not archived).
- `redo` — benchmark unsatisfactory, needs a new pass. Dispatcher archives the current README as `README.owner-rejected-<date>.md`, reopens the benchmark task, and the research agent produces a new recommendation that integrates the owner's feedback from the archived README(s).
- `more` — benchmark needs complementary information before the owner can decide. Dispatcher extracts the owner's consignes into a `complement-request-<date>.md`, resets the main README to `pending`, and reopens the benchmark task. The research agent produces a `complement-response-<date>.md` at the next run without touching the main README.

**Only the main `README.md` is authoritative.** Complement files and archived rejections are consultation material. Owner writes feedback/consignes in the `Decision` field of the main README's `Owner Validation` section.

See `docs/BENCHMARK_OWNER_WORKFLOW.md` for the owner-facing decision table and full workflow. Internal implementation details (Phase 0 / Phase 1 dispatcher logic, mode detection by the research agent) are in `CLAUDE.md` and `.claude/agents/`.
