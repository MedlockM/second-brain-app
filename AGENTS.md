
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

### Never make a Maestro run an acceptance criterion

Do NOT write acceptance criteria of the form "a full E2E run passes on both platforms" or "the Maestro flows pass". A Maestro run is owner-triggered (`workflow_dispatch`), takes 10-50 minutes, and is flaky on the iOS simulator — an agent cannot satisfy such an AC, so the task stays `In Progress` forever and blocks everything downstream. This applies to task creation AND to task execution: an implementer must not add one either.

Validate the behaviour through what an agent can actually reach: the code path, the deployed endpoint, a direct AWS/API check, or a targeted script. When a change genuinely needs mobile visual confirmation, say so in the description as a note to the owner — not as an AC.

Two carve-outs:

- **Tasks whose deliverable *is* the Maestro suite** (write a flow, wire the CI job) legitimately reference it — the flow's existence and its wiring are readable in the YAML. Even there, prefer "the flow exists and the job invokes it" over "the run is green". The rule targets a Maestro run used as a *validation gate on unrelated work*.
- **An AC requiring a *deployed* backend endpoint is fine**: the deploy is automatic on merge to `main`, so an agent can verify it once the workflow finishes. Check the deployed image digest against the merge commit before ticking it — `deploy-lambda.yml` is `paths`-filtered, and it never fires at all while `main` is unpushed.

## Benchmark lifecycle

The owner signals their decision through the `owner_decision` field in the front-matter of the main `README.md` of the research directory. Five values are supported:

- `pending` — default, owner has not reviewed yet. Dispatcher does nothing.
- `ok` — benchmark accepted. Dispatcher marks the benchmark task `Done`, which unblocks the implementation task via its dependency.
- `abandoned` — benchmark rejected and task abandoned. Dispatcher archives the benchmark task and its directly paired implementation task. Other tasks that list this benchmark in their dependencies just get the dependency removed (not archived).
- `redo` — benchmark unsatisfactory, needs a new pass. Dispatcher archives the current README as `README.owner-rejected-<date>.md`, reopens the benchmark task, and the research agent produces a new recommendation that integrates the owner's feedback from the archived README(s).
- `more` — benchmark needs complementary information before the owner can decide. Dispatcher extracts the owner's consignes into a `complement-request-<date>.md`, resets the main README to `pending`, and reopens the benchmark task. The research agent produces a `complement-response-<date>.md` at the next run without touching the main README.

**Only the main `README.md` is authoritative.** Complement files and archived rejections are consultation material. Owner writes feedback/consignes in the `Decision` field of the main README's `Owner Validation` section.

See `docs/BENCHMARK_OWNER_WORKFLOW.md` for the owner-facing decision table and full workflow. Internal implementation details (Phase 0 / Phase 1 dispatcher logic, mode detection by the research agent) are in `CLAUDE.md` and `.claude/agents/`.
