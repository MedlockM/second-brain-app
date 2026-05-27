# Backlog Subagent Orchestration

The launcher now has three visible launch behaviors:

1. `--dry-run`
2. `--plan-only-real`
3. default execution mode

There is no longer a `plan / prepare / verify / execute` pipeline.

## What The Script Does

On every run, the script:

- reads the local Backlog task files by default
- classifies tasks as ready, dispatchable, deferred, or blocked
- selects a conflict-free `dispatch_now` set
- decides, for each selected task, whether its top-level owner should be a `simple_subagent` or an `agent_team`
- distills repository context for each selected task
- generates one subagent prompt per selected task
- generates the orchestration prompt in a separate final LLM call
- writes a timestamped run bundle incrementally after each phase
- either simulates the LLM calls in `--dry-run`, runs the real pipeline in planning-only mode with `--plan-only-real`, or performs the full real Claude run

## Dry Run

Use `--dry-run` when you want to test the launcher itself without calling Claude.

What it does:

- computes the real selected task set
- simulates the execution-mode decision for each selected task
- simulates context distillation for each selected task
- simulates prompt generation for each selected task
- simulates orchestration prompt generation
- simulates orchestration output
- writes the same artifact shape as a real run

What it does **not** do:

- no Claude Code call
- no real subagent creation
- no task execution

Command:

```bash
python3 scripts/backlog_agent_orchestrator.py --dry-run
```

Optional cap:

```bash
python3 scripts/backlog_agent_orchestrator.py \
  --dry-run \
  --max-dispatch 4
```

## Real Execution

Without `--dry-run`, the script performs the real Claude-backed flow.

What it does:

- computes the selected task set locally
- asks Claude to decide, task by task, between `simple_subagent` and `agent_team`
- asks Claude to distill repository context for each selected task
- asks Claude to generate the agent prompt for each selected task
- asks Claude to generate the orchestration prompt
- writes `claude-agents.json` and per-task prompt files from that LLM output
- asks Claude to run the multi-agent orchestration with `--dangerously-skip-permissions`
- writes the real orchestration result

Command:

```bash
python3 scripts/backlog_agent_orchestrator.py
```

## Real Plan-Only

Use `--plan-only-real` when you want the real Claude pipeline to run, but you do
not want the subagents or agent teams to implement anything yet.

What it does:

- computes the selected task set locally
- asks Claude to decide, task by task, between `simple_subagent` and `agent_team`
- asks Claude to generate the agent prompts
- launches the real top-level orchestration
- forces subagents and teammates to stop at planning
- runs the orchestration call in `permission_mode=plan`

What it does **not** do:

- no file edits
- no task implementation

Command:

```bash
python3 scripts/backlog_agent_orchestrator.py --plan-only-real
```

## Artifact Bundle

Each run writes a timestamped bundle under `.claude/dispatch-runs` by default.

The bundle contains:

- `README.md`
- `dispatch-plan.json`
- `dispatch-plan.txt`
- `execution-mode-result.json`
- `context-distillation-result.json`
- `claude-agents.json`
- `orchestration-prompt.md`
- `orchestration-prompt-result.json`
- `orchestration-prompt-raw.json`
- `prompt-generation-result.json`
- `prompt-generation-raw.json`
- `orchestrator-result.json`
- `orchestrator-raw.json`
- `execution-mode-raw.json`
- `context-distillation-raw.json`
- `run-failure.json` when a real run fails
- one prompt file per selected task

## Artifact Roles

- `dispatch-plan.json`
  The machine-readable selection result: ready tasks, dispatchable tasks, selected tasks, and reasons.

- `dispatch-plan.txt`
  The human-readable summary of the same selection.

- `execution-mode-result.json`
  The structured result of the decision phase that chooses, for each selected task,
  between `simple_subagent` and `agent_team`.
  In `--dry-run`, this is simulated.
  In real mode, this is Claude-generated.

- `execution-mode-raw.json`
  The raw Claude payload captured for the execution-mode phase.

- `context-distillation-result.json`
  The structured result of the repository-context distillation phase.
  In `--dry-run`, this is simulated.
  In real mode, this is Claude-generated per task.

- `context-distillation-raw.json`
  The raw Claude payloads captured for the context-distillation phase.

- `claude-agents.json`
  The custom agent definitions actually sent to Claude for orchestration.

- `orchestration-prompt.md`
  The main prompt for the top-level Claude orchestration session.

- `orchestration-prompt-result.json`
  The structured result of the orchestration-prompt generation phase.
  In `--dry-run`, this is simulated.
  In real mode, this is Claude-generated.

- `orchestration-prompt-raw.json`
  The raw Claude payload captured for orchestration-prompt generation.

- `prompt-generation-result.json`
  The structured result of the subprompt generation phase.
  In `--dry-run`, this is simulated.
  In real mode, this is Claude-generated per task.

- `prompt-generation-raw.json`
  The raw Claude payloads captured for subprompt generation.

- `orchestrator-result.json`
  The structured orchestration result.
  In `--dry-run`, this is simulated.
  In real mode, this comes from the real Claude orchestration call.

- `orchestrator-raw.json`
  The raw orchestration call payload or the dry-run simulation metadata.

- `run-failure.json`
  Written when a run fails after bundle creation. It records the failing call,
  the captured stdout/stderr, and any raw JSON payload that Claude returned.

## Notes

- `--dry-run` is the safe mode for validating script behavior and artifact shape.
- The default mode is intentionally the real launch mode.
- The number of selected tasks determines the number of expected subagents.
- The script instructs Claude to spawn exactly `N` top-level subagents for `N` selected tasks.
- Each selected task gets exactly one top-level subagent.
- The execution-mode decision only determines whether that top-level subagent works
  alone or becomes the lead of an internal agent team.
- In real mode, every Claude call uses full-autonomy permissions.
- In `--plan-only-real`, the real Claude pipeline runs but the orchestration step is forced into planning-only behavior.
- In `--plan-only-real`, if Claude reports a top-level agent as `completed` while still running under `permission_mode=plan`, the launcher normalizes that status to `planned` instead of failing the whole run.
- The LLM workload is intentionally split into 4 sequential phases:
  execution-mode decision, context distillation, subprompt generation, and orchestration prompt generation.
- The bundle is written progressively, so a failed real run still leaves behind
  the completed phase outputs and the raw failure payload for diagnosis.
