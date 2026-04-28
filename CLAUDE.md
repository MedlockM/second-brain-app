# CLAUDE.md

Instructions specific to Claude working on this repository. Read `AGENTS.md` first for general project rules.

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
   - `owner_decision: abandoned` → Phase 0 archives the benchmark task and every task that depends on it (including the implementation task).
   - `owner_decision: redo` + precise feedback in the `Decision` field (what was unsatisfactory, which alternatives to re-evaluate, which additional criteria to consider) → Phase 0 archives the current README as `README.owner-rejected-<date>.md`, reopens the benchmark task to `To Do`, and the next dispatch relaunches `task-research` on it. The research agent reads the archived README(s) to pick up the owner's feedback and produce a new recommendation that takes it into account.
   - `owner_decision: more` + consignes in the `Decision` field describing what additional information is needed → Phase 0 extracts the consignes into a `complement-request-<date>.md` file in the same directory, resets the README front-matter to `pending`, and reopens the benchmark task. At the next dispatch, `task-research` runs in "complement mode": it produces a `complement-response-<date>.md` addressing the consignes, without touching the main README. The main README stays the baseline. The owner can then re-decide among ok/abandoned/redo/more using the complement as additional context.
   - `owner_decision: pending` → no-op (default after the research agent finishes; the owner has not reviewed yet).
3. **Only the main `README.md` front-matter is authoritative**. Complement files (`complement-request-*.md`, `complement-response-*.md`) and archived rejections (`README.owner-rejected-*.md`) are consultation material — they have no active front-matter. Once the owner is satisfied (possibly after several `more` rounds), they set `owner_decision: ok` on the main README to unlock implementation. The `Decision` field can reference complements explicitly (e.g. "accept recommendation X as refined by complement-response-2026-05-05.md").
4. Implementation task dispatched after its benchmark dependency resolves. The implementer reads the owner's `Decision` from the main README (and follows any references it makes to complement files) to know what to build.

## Dispatching tasks

To run the dispatcher on the backlog: `./scripts/dispatch_backlog.sh --max-dispatch N`.

Before dispatching, commit all tracked changes. The script guards against uncommitted tracked files.
