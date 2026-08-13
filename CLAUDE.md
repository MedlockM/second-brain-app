# CLAUDE.md

Instructions specific to Claude working on this repository. Read `AGENTS.md` first for general project rules.

## Nothing is deployed yet — scope tasks as deletions, not migrations

Full rule in `AGENTS.md`, section "Nothing is deployed yet". The fact: **the app has never shipped** — not on the App Store, not on Google Play, not in TestFlight. Zero users besides the owner, zero production data, zero active subscriptions; AWS `prod` is a dormant shell that has never served traffic. There is no installed base.

This changes how you *write* tasks, not just how they are implemented:

- **Never scope a compatibility layer.** No "keep the old map as a fallback", no "support both shapes during a transition", no dual-write, no deprecation window. A cleanup task deletes the old thing in the same run. If you catch yourself writing an AC that preserves an artifact so that "existing behaviour is unaffected", the premise is wrong — check whether anything actually reads it.
- **Never justify keeping something by invoking users, customers, or production data.** There are none. That reasoning is a factual error about this project, and it produces tasks that carry dead code forever.
- **Order cleanups first.** When one task restructures a layout (a schema, a set of third-party entitlements, a naming convention) and others populate it, the restructure comes **first** and the others depend on it. The reverse ordering makes the populating tasks do their work twice and leaves their ACs stale.
- **Legacy includes third-party dashboards**, not just code: RevenueCat entitlements/offerings/packages, store product identifiers, EAS variables, Algolia indices. Provider-generated scaffolding nobody reads gets deleted too.

Two things are *not* legacy and must be kept when scoping: **input contracts you do not control** (a third-party webhook whose payload version varies — handle every shape it may send) and **fixtures a test flow depends on** (the RevenueCat Test Store products behind `mobile/.maestro/07_paywall.yaml`, the persistent "Commonplace book" article on dev).

## Task creation convention

When the owner asks you to create a new task in the backlog, decide whether it needs a benchmark before implementation:

### Does this task need a benchmark?

A benchmark is required when the task involves a **non-trivial technology/architecture decision** that has not yet been made:
- Choosing an external service or provider (OCR, LLM, search engine, cloud provider, email service, etc.)
- Choosing a library or framework among several viable options
- Defining a pricing model or quota policy
- Scoping a new feature whose shape is not yet obvious

A benchmark is NOT required for:
- Bug fixes
- Refactoring
- Implementing a well-understood feature whose design is already clear
- Documentation work
- Follow-up tasks built on an already-validated benchmark

When in doubt, ask the owner before creating the task(s).

### Every AC must be satisfiable by the agent that will implement the task

The implementer runs in an isolated worktree on its own branch: it never merges, never pushes, and its code is never deployed while it works. Write only ACs it can satisfy from there, during that run. Three forms to never write:

- **"The deployed endpoint answers X" / "Lambda image redeployed".** Unsatisfiable by construction — the deploy happens on push to `main`, long after the agent is gone. Push the deploy check into the description as an owner note.
- **ACs shaped like unit tests** ("function X returns Y for input Z"), and equally an in-process call on the FastAPI app. Only the AWS backend is functional; a local harness is just another test written during development, which this project forbids unless explicitly requested. The runs that count are the owner's manual E2E runs.
- **"The Maestro suite is green".** Owner-triggered, 10-50 minutes, flaky on the iOS simulator.

Reachable instead: the code path exists and is wired, `ruff`/`mypy`/`terraform validate` clean, a direct check against real `-dev` DynamoDB/S3/SQS or the AWS CLI, an alarm driven to `ALARM` then `OK`, a documented fact readable in a file.

When a deploy or a mobile visual check genuinely matters, put it in the description as a note to the owner — never as an AC. The full rule is in `AGENTS.md` under the same heading.

### If the task needs a benchmark: create two linked tasks

1. **Benchmark task** — labels include `benchmark`, title starts with an action verb describing the research (e.g. "Benchmark OCR services for…"). No implementation scope in this task; only research, comparison, and recommendation.
2. **Implementation task** — depends on the benchmark task via `dependencies: [task-XX]`. Title references the benchmark task (e.g. "Implement OCR ingestion worker per validated benchmark (task-XX)"). Description stays generic and instructs the implementer to read `docs/research/task-XX-*/README.md` for the owner's final decision and the architecture to follow.

**Never** embed the benchmark recommendation directly in the implementation task description — the owner's decision may differ from the initial recommendation, and the implementation task must always defer to what the README says.

### If the task does NOT need a benchmark: create a single task

Just create one task with a clear scope and acceptance criteria. No benchmark overhead.

See `docs/BENCHMARK_OWNER_WORKFLOW.md` for the owner-facing reference of the decision values (`pending`, `ok`, `abandoned`, `redo`, `more`) and the full workflow table.

## Benchmark lifecycle (summary for task creation context)

This lifecycle is enforced by the dispatcher in `.claude/agents/backlog-dispatcher.md` and the `task-research` agent. Summary for awareness when creating tasks:

1. Benchmark task dispatched → `task-research` agent produces `docs/research/task-XX-<short-description>/README.md` with `owner_decision: pending` in the front-matter. Benchmark task stays `To Do`.
2. Owner reviews the README and edits the front-matter with one of five values:
   - `owner_decision: ok` + fills the `Decision` and `Validated at` fields under `Owner Validation` → at the next dispatch, Phase 0 marks the benchmark task `Done`, which unblocks the implementation task via its dependency.
   - `owner_decision: abandoned` → Phase 0 archives the benchmark task and its directly paired implementation task. Other tasks that list this benchmark in their dependencies just get the dependency removed (not archived).
   - `owner_decision: redo` + precise feedback in the `Decision` field (what was unsatisfactory, which alternatives to re-evaluate, which additional criteria to consider) → Phase 0 archives the current README as `README.owner-rejected-<date>.md`, reopens the benchmark task to `To Do`, and the next dispatch relaunches `task-research` on it. The research agent reads the archived README(s) to pick up the owner's feedback and produce a new recommendation that takes it into account.
   - `owner_decision: more` + consignes in the `Decision` field describing what additional information is needed → Phase 0 extracts the consignes into a `complement-request-<date>.md` file in the same directory, resets the README front-matter to `pending`, and reopens the benchmark task. At the next dispatch, `task-research` runs in "complement mode": it produces a `complement-response-<date>.md` addressing the consignes, without touching the main README. The main README stays the baseline. The owner can then re-decide among ok/abandoned/redo/more using the complement as additional context.
   - `owner_decision: pending` → no-op (default after the research agent finishes; the owner has not reviewed yet).
3. **Only the main `README.md` front-matter is authoritative**. Complement files (`complement-request-*.md`, `complement-response-*.md`) and archived rejections (`README.owner-rejected-*.md`) are consultation material — they have no active front-matter. Once the owner is satisfied (possibly after several `more` rounds), they set `owner_decision: ok` on the main README to unlock implementation. The `Decision` field can reference complements explicitly (e.g. "accept recommendation X as refined by complement-response-2026-05-05.md").
4. Implementation task dispatched after its benchmark dependency resolves. The implementer reads the owner's `Decision` from the main README (and follows any references it makes to complement files) to know what to build.

## Dispatching tasks

To run the dispatcher on the backlog: `./scripts/dispatch_backlog.sh --max-dispatch N`.

Before dispatching, commit all tracked changes. The script guards against uncommitted tracked files.
