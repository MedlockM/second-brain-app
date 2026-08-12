
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
