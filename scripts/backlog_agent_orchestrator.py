#!/usr/bin/env python3
"""Launch Claude Code multi-agent backlog orchestration with optional dry-run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Task:
    """Normalized task representation used by the orchestrator."""

    task_id: str
    title: str
    status: str
    priority: str
    dependencies: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    assignee: str | None = None
    lane_hint: str | None = None
    write_scope: List[str] = field(default_factory=list)
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    implementation_notes: str = ""
    source_path: str | None = None


@dataclass
class ClaudePromptPacket:
    """Prompt packet generated for one selected task."""

    task_id: str
    title: str
    lane: str
    write_scope: List[str]
    session_name: str
    summary: str
    execution_mode: str
    team_shape: List[str]
    prompt_markdown: str
    prompt_filename: str
    agent_name: str


class ClaudeRunError(RuntimeError):
    """Structured Claude invocation failure with captured payload details."""

    def __init__(
        self,
        call_name: str,
        message: str,
        *,
        stdout: str = "",
        stderr: str = "",
        payload: Any | None = None,
    ) -> None:
        super().__init__(f"{call_name}: {message}")
        self.call_name = call_name
        self.stdout = stdout
        self.stderr = stderr
        self.payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "call_name": self.call_name,
            "message": str(self),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "payload": self.payload,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute dispatchable backlog tasks, generate Claude Code "
            "subagent prompts, and launch orchestration. Use --dry-run to "
            "simulate all LLM calls."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate prompt generation and orchestration without calling Claude.",
    )
    parser.add_argument(
        "--plan-only-real",
        action="store_true",
        help=(
            "Run the real Claude pipeline but stop at planning: subagents and "
            "agent teams may inspect and plan, but must not implement."
        ),
    )
    parser.add_argument(
        "--snapshot",
        help=(
            "Path to a JSON file containing tasks or an object with a "
            "top-level 'tasks' key."
        ),
    )
    parser.add_argument(
        "--backlog-dir",
        default="backlog/tasks",
        help=(
            "Directory containing Backlog task markdown files. Used by default "
            "when --snapshot is not provided."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=".claude/dispatch-runs",
        help="Base directory where the timestamped run bundle will be written.",
    )
    parser.add_argument(
        "--max-dispatch",
        type=int,
        default=0,
        help=(
            "Maximum number of tasks to select for immediate dispatch. "
            "Use 0 for no explicit cap."
        ),
    )
    parser.add_argument(
        "--mobile-repo-present",
        action="store_true",
        help="Allow mobile implementation tasks to be considered dispatchable.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Console output format.",
    )
    parser.add_argument(
        "--claude-model",
        default="sonnet",
        help="Model alias or name passed to Claude Code.",
    )
    parser.add_argument(
        "--claude-effort",
        default="high",
        choices=("low", "medium", "high", "max"),
        help="Effort level passed to Claude Code.",
    )
    parser.add_argument(
        "--claude-timeout-sec",
        type=int,
        default=180,
        help="Timeout in seconds for each Claude Code call.",
    )
    return parser.parse_args()


def normalize_status(raw_status: Any) -> str:
    text = str(raw_status or "").strip().lower()
    if text in {"to do", "todo", "open"}:
        return "todo"
    if text in {"in progress", "in_progress", "doing", "wip"}:
        return "in_progress"
    if text in {"done", "completed", "complete"}:
        return "done"
    if "done" in text:
        return "done"
    if "progress" in text:
        return "in_progress"
    return "todo"


def normalize_priority(raw_priority: Any) -> str:
    text = str(raw_priority or "").strip().lower()
    return text if text in PRIORITY_ORDER else "medium"


def normalize_list(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return []
        if "," in raw_value:
            parts = raw_value.split(",")
        else:
            parts = [raw_value]
        return [part.strip() for part in parts if part.strip()]
    return [str(raw_value).strip()]


def timestamp_slug() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def launch_mode_for_args(args: argparse.Namespace) -> str:
    if args.dry_run and args.plan_only_real:
        raise SystemExit("--dry-run and --plan-only-real cannot be used together")
    if args.dry_run:
        return "dry-run"
    if args.plan_only_real:
        return "plan-only"
    return "execute"


def write_json_file(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_text_file(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load_tasks(snapshot_path: Path) -> List[Task]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    raw_tasks = payload["tasks"] if isinstance(payload, dict) else payload
    tasks: List[Task] = []

    for raw_task in raw_tasks:
        tasks.append(
            Task(
                task_id=str(raw_task["id"]),
                title=str(raw_task["title"]),
                status=normalize_status(raw_task.get("status")),
                priority=normalize_priority(raw_task.get("priority")),
                dependencies=normalize_list(
                    raw_task.get("dependencies") or raw_task.get("depends_on")
                ),
                labels=normalize_list(raw_task.get("labels")),
                assignee=raw_task.get("assignee"),
                lane_hint=raw_task.get("lane_hint"),
                write_scope=normalize_list(raw_task.get("write_scope")),
                description=str(raw_task.get("description") or "").strip(),
                acceptance_criteria=normalize_list(
                    raw_task.get("acceptance_criteria")
                ),
                implementation_notes=str(
                    raw_task.get("implementation_notes") or ""
                ).strip(),
                source_path=raw_task.get("source_path"),
            )
        )

    return tasks


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if text == "[]":
        return []
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    return text


def parse_front_matter(markdown_text: str) -> Dict[str, Any]:
    if not markdown_text.startswith("---\n"):
        raise ValueError("missing opening front matter delimiter")

    try:
        _, front_matter, _ = markdown_text.split("---", 2)
    except ValueError as exc:
        raise ValueError("invalid front matter block") from exc

    result: Dict[str, Any] = {}
    lines = front_matter.strip("\n").splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if ":" not in line:
            raise ValueError(f"invalid front matter line: {line}")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        index += 1

        if raw_value in {"|", "|-", ">", ">-"}:
            folded_lines: List[str] = []
            while index < len(lines):
                continuation = lines[index]
                if continuation.startswith("  "):
                    folded_lines.append(continuation.strip())
                    index += 1
                    continue
                break
            result[key] = " ".join(part for part in folded_lines if part).strip()
            continue

        if raw_value == "":
            list_items: List[str] = []
            while index < len(lines):
                continuation = lines[index]
                stripped = continuation.strip()
                if continuation.startswith("  - "):
                    list_items.append(continuation[4:].strip())
                    index += 1
                    continue
                if not stripped:
                    index += 1
                    continue
                break
            result[key] = list_items
            continue

        result[key] = _parse_scalar(raw_value)

    return result


def extract_marked_section(
    markdown_text: str, start_marker: str, end_marker: str
) -> str:
    start_index = markdown_text.find(start_marker)
    end_index = markdown_text.find(end_marker)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return ""
    start_index += len(start_marker)
    return markdown_text[start_index:end_index].strip()


def parse_acceptance_criteria(markdown_text: str) -> List[str]:
    block = extract_marked_section(
        markdown_text, "<!-- AC:BEGIN -->", "<!-- AC:END -->"
    )
    if not block:
        return []

    criteria: List[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"- \[[ xX]\] #?\d+\s*(.*)", line)
        if match:
            criteria.append(match.group(1).strip())
            continue
        if criteria:
            criteria[-1] = f"{criteria[-1]} {line}".strip()
        else:
            criteria.append(line)
    return criteria


def load_tasks_from_backlog_dir(backlog_dir: Path) -> List[Task]:
    tasks: List[Task] = []

    for task_path in sorted(backlog_dir.glob("*.md")):
        markdown_text = task_path.read_text(encoding="utf-8")
        metadata = parse_front_matter(markdown_text)
        tasks.append(
            Task(
                task_id=str(metadata["id"]),
                title=str(metadata["title"]),
                status=normalize_status(metadata.get("status")),
                priority=normalize_priority(metadata.get("priority")),
                dependencies=normalize_list(metadata.get("dependencies")),
                labels=normalize_list(metadata.get("labels")),
                assignee=metadata.get("assignee"),
                description=extract_marked_section(
                    markdown_text,
                    "<!-- SECTION:DESCRIPTION:BEGIN -->",
                    "<!-- SECTION:DESCRIPTION:END -->",
                ),
                acceptance_criteria=parse_acceptance_criteria(markdown_text),
                implementation_notes=extract_marked_section(
                    markdown_text,
                    "<!-- SECTION:NOTES:BEGIN -->",
                    "<!-- SECTION:NOTES:END -->",
                ),
                source_path=str(task_path),
            )
        )

    return tasks


def infer_lane(task: Task) -> str:
    if task.lane_hint:
        return task.lane_hint

    title_text = " ".join([task.title, *task.labels]).lower()
    full_text = " ".join([task.title, task.description, *task.labels]).lower()

    if any(
        token in full_text
        for token in (
            "benchmark",
            "analyse",
            "analysis",
            "pricing",
            "provider",
            "recherche internet requise",
            "web research required",
            "competitor",
            "persona",
        )
    ) and not any(
        token in title_text
        for token in (
            "endpoint",
            "worker",
            "terraform",
            "docker-compose",
            "api/",
            "implement ",
            "implément",
            "supprimer",
            "remove ",
        )
    ):
        return "research-doc"

    if any(
        token in title_text
        for token in (
            "privacy",
            "terms",
            "data safety",
            "app store",
            "testflight",
            "internal testing",
            "publish",
            "listing metadata",
            "pre-review qa",
            "manual e2e",
        )
    ):
        return "manual-release-compliance"

    if "rename" in title_text and "codebase" in title_text:
        return "cross-cutting-refactor"

    if any(
        token in title_text
        for token in (
            "mobile",
            "android",
            "ios",
            "share extension",
            "share intent",
            "maestro",
            "testflight",
            "internal distribution",
        )
    ):
        return "mobile-implementation"

    if any(
        token in full_text
        for token in (
            "dashboard",
            "slo",
            "alert",
            "observability",
            "cost guardrail",
            "budget",
        )
    ):
        return "infra-observability"

    return "backend-runtime"


def default_write_scope(lane: str, task: Task) -> List[str]:
    if lane == "research-doc":
        return [f"docs/research/{task.task_id}"]
    if lane == "backend-runtime":
        return [
            "media_summarizer/api",
            "media_summarizer/core",
            "media_summarizer/workers",
            "media_summarizer/infrastructure",
        ]
    if lane == "infra-observability":
        return [".github/workflows", "docs", "infrastructure"]
    if lane == "mobile-implementation":
        return ["mobile-repo(external)"]
    if lane == "manual-release-compliance":
        return ["docs", "store-portals(external)", "release-ops(external)"]
    if lane == "cross-cutting-refactor":
        return ["repo-wide"]
    return ["repo-wide"]


def task_number(task_id: str) -> int:
    match = re.search(r"(\d+)$", task_id)
    return int(match.group(1)) if match else sys.maxsize


def scopes_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    for left_item in left:
        for right_item in right:
            if left_item == right_item:
                return True
            if left_item.startswith(right_item + "/") or right_item.startswith(
                left_item + "/"
            ):
                return True
            if left_item == "repo-wide" or right_item == "repo-wide":
                return True
    return False


def classify_tasks(
    tasks: Iterable[Task], mobile_repo_present: bool
) -> Dict[str, List[Dict[str, Any]]]:
    tasks = list(tasks)
    known_ids = {task.task_id for task in tasks}
    done_ids = {task.task_id for task in tasks if task.status == "done"}
    records: List[Dict[str, Any]] = []

    for task in tasks:
        lane = infer_lane(task)
        write_scope = task.write_scope or default_write_scope(lane, task)
        reasons: List[str] = []
        blocked_by = [
            dep for dep in task.dependencies if dep in known_ids and dep not in done_ids
        ]
        unknown_dependencies = [
            dep for dep in task.dependencies if dep not in known_ids
        ]

        if task.status != "todo":
            reasons.append(f"status is '{task.status}', expected 'todo'")
        if blocked_by:
            reasons.append(
                "blocked by unfinished dependencies: " + ", ".join(blocked_by)
            )
        if unknown_dependencies:
            reasons.append(
                "missing dependencies in snapshot: " + ", ".join(unknown_dependencies)
            )

        ready = not reasons
        dispatchable = ready

        if lane == "mobile-implementation" and not mobile_repo_present:
            dispatchable = False
            reasons.append(
                "mobile implementation repo is not present in this workspace"
            )
        if lane == "manual-release-compliance":
            dispatchable = False
            reasons.append("requires external/manual store or compliance operations")
        if lane == "cross-cutting-refactor":
            dispatchable = False
            reasons.append(
                "broad refactor should stay mono-agent and centrally coordinated"
            )

        records.append(
            {
                "id": task.task_id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "dependencies": task.dependencies,
                "lane": lane,
                "write_scope": write_scope,
                "ready": ready,
                "dispatchable": dispatchable,
                "reasons": reasons,
            }
        )

    records.sort(
        key=lambda record: (
            PRIORITY_ORDER[record["priority"]],
            task_number(record["id"]),
            record["title"].lower(),
        )
    )
    return {"records": records}


def select_dispatch_now(
    records: Sequence[Dict[str, Any]], max_dispatch: int
) -> Dict[str, List[Dict[str, Any]]]:
    dispatch_now: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []

    for record in records:
        if not record["dispatchable"]:
            continue

        if max_dispatch > 0 and len(dispatch_now) >= max_dispatch:
            deferred.append(
                {
                    **record,
                    "reasons": record["reasons"]
                    + ["dispatch limit reached for this run"],
                }
            )
            continue

        if any(
            scopes_overlap(record["write_scope"], item["write_scope"])
            for item in dispatch_now
        ):
            deferred.append(
                {
                    **record,
                    "reasons": record["reasons"]
                    + ["write scope overlaps with an already selected task"],
                }
            )
            continue

        dispatch_now.append(record)

    return {"dispatch_now": dispatch_now, "deferred_dispatchable": deferred}


def render_text(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    summary = payload["summary"]
    lines.append("Backlog Subagent Dispatch Run")
    lines.append("=" * 28)
    lines.append(
        "Snapshot summary: "
        f"{summary['total']} tasks, "
        f"{summary['ready']} ready, "
        f"{summary['dispatchable']} dispatchable, "
        f"{summary['selected']} selected now"
    )
    lines.append("")

    lines.append("Dispatch now")
    lines.append("-" * 12)
    if payload["dispatch_now"]:
        for record in payload["dispatch_now"]:
            lines.append(f"* {record['id']} [{record['priority']}] {record['title']}")
            lines.append(
                "  lane="
                f"{record['lane']} | write_scope="
                f"{', '.join(record['write_scope'])}"
            )
    else:
        lines.append("* No task selected for immediate dispatch")
    lines.append("")

    lines.append("Deferred but dispatchable")
    lines.append("-" * 24)
    if payload["deferred_dispatchable"]:
        for record in payload["deferred_dispatchable"]:
            lines.append(f"* {record['id']} [{record['priority']}] {record['title']}")
            lines.append("  reasons=" + "; ".join(record["reasons"]))
    else:
        lines.append("* None")
    lines.append("")

    lines.append("Skipped or blocked")
    lines.append("-" * 18)
    blocked_records = [
        record
        for record in payload["records"]
        if not record["dispatchable"] and record not in payload["deferred_dispatchable"]
    ]
    if blocked_records:
        for record in blocked_records:
            lines.append(f"* {record['id']} [{record['priority']}] {record['title']}")
            lines.append(
                f"  lane={record['lane']} | reasons=" + "; ".join(record["reasons"])
            )
    else:
        lines.append("* None")

    return "\n".join(lines)


def task_to_dict(task: Task) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "dependencies": list(task.dependencies),
        "labels": list(task.labels),
        "assignee": task.assignee,
        "lane_hint": task.lane_hint,
        "write_scope": list(task.write_scope),
        "description": task.description,
        "acceptance_criteria": list(task.acceptance_criteria),
        "implementation_notes": task.implementation_notes,
        "source_path": task.source_path,
    }


def task_from_dict(payload: Dict[str, Any]) -> Task:
    return Task(
        task_id=str(payload["task_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        priority=str(payload["priority"]),
        dependencies=normalize_list(payload.get("dependencies")),
        labels=normalize_list(payload.get("labels")),
        assignee=payload.get("assignee"),
        lane_hint=payload.get("lane_hint"),
        write_scope=normalize_list(payload.get("write_scope")),
        description=str(payload.get("description") or "").strip(),
        acceptance_criteria=normalize_list(payload.get("acceptance_criteria")),
        implementation_notes=str(payload.get("implementation_notes") or "").strip(),
        source_path=payload.get("source_path"),
    )


def packet_to_dict(packet: ClaudePromptPacket) -> Dict[str, Any]:
    return {
        "task_id": packet.task_id,
        "title": packet.title,
        "lane": packet.lane,
        "write_scope": list(packet.write_scope),
        "session_name": packet.session_name,
        "summary": packet.summary,
        "execution_mode": packet.execution_mode,
        "team_shape": list(packet.team_shape),
        "prompt_markdown": packet.prompt_markdown,
        "prompt_filename": packet.prompt_filename,
        "agent_name": packet.agent_name,
    }


def packet_from_dict(payload: Dict[str, Any]) -> ClaudePromptPacket:
    return ClaudePromptPacket(
        task_id=str(payload["task_id"]),
        title=str(payload["title"]),
        lane=str(payload["lane"]),
        write_scope=normalize_list(payload.get("write_scope")),
        session_name=str(payload["session_name"]),
        summary=str(payload["summary"]),
        execution_mode=str(payload.get("execution_mode") or "simple_subagent"),
        team_shape=normalize_list(payload.get("team_shape")),
        prompt_markdown=str(payload["prompt_markdown"]),
        prompt_filename=str(payload["prompt_filename"]),
        agent_name=str(payload["agent_name"]),
    )


def build_dispatch_payload(
    tasks_by_id: Dict[str, Task], planning_payload: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "dispatch_version": 1,
        "generated_at": timestamp_slug(),
        "summary": planning_payload["summary"],
        "dispatch_now": planning_payload["dispatch_now"],
        "deferred_dispatchable": planning_payload["deferred_dispatchable"],
        "records": planning_payload["records"],
        "selected_tasks": [
            {
                "task": task_to_dict(tasks_by_id[record["id"]]),
                "dispatch": record,
            }
            for record in planning_payload["dispatch_now"]
        ],
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "task"


def recommended_reading(task: Task, record: Dict[str, Any]) -> List[str]:
    reading = ["README.md"]
    lane = record["lane"]

    if task.source_path:
        try:
            reading.append(str(Path(task.source_path).relative_to(Path.cwd())))
        except ValueError:
            reading.append(task.source_path)

    if lane == "research-doc":
        reading.append("docs/MOBILE_APP_IMPLEMENTATION_PLAN.md")
        reading.append("docs/CANONICAL_MEDIA_API_CONTRACT.md")
    if lane in {"backend-runtime", "mobile-implementation"}:
        reading.append("docs/CANONICAL_MEDIA_API_CONTRACT.md")
    if lane == "backend-runtime":
        reading.append("docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md")
    if lane == "infra-observability":
        reading.append("docs/LOGGING_SYSTEM.md")
        reading.append("docs/HORIZONTAL_SCALING.md")

    deduped: List[str] = []
    for path in reading:
        if path not in deduped:
            deduped.append(path)
    return deduped


def repo_guardrails() -> List[str]:
    return [
        "Use Backlog task files as the task source of truth for this repo.",
        "Do not touch `front/`; it is legacy and scheduled for replacement.",
        (
            "Do not work on Spotify sync, email delivery, quiz generation, "
            "Whisper transcription, or credit-based billing."
        ),
        "Use canonical endpoints only: `/api/media/*` and `/api/artifacts/*`.",
        (
            "Pre-production policy: remove obsolete code directly, no "
            "backward-compatibility layer required."
        ),
        "Do not add automated tests unless explicitly requested.",
        (
            "Use hexagonal architecture where already present, otherwise keep "
            "the solution simple."
        ),
    ]


def agent_name_for_task(task: Task) -> str:
    return f"{task.task_id}_{slugify(task.title)[:40]}"


def prompt_filename_for_task(task: Task) -> str:
    return f"{task.task_id}-{slugify(task.title)[:80]}.md"


def packet_blueprint(task: Task, record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "lane": record["lane"],
        "write_scope": list(record["write_scope"]),
        "session_name": f"{task.task_id}: {task.title}"[:120],
        "agent_name": agent_name_for_task(task),
        "prompt_filename": prompt_filename_for_task(task),
        "source_path": task.source_path or "",
        "required_reading": recommended_reading(task, record),
        "description": task.description or "No description captured.",
        "acceptance_criteria": task.acceptance_criteria,
        "implementation_notes": task.implementation_notes or "",
        "dependencies": list(record["dependencies"]),
    }


def build_static_prompt_packet(
    task: Task, record: Dict[str, Any]
) -> ClaudePromptPacket:
    acceptance = (
        "\n".join(f"- {item}" for item in task.acceptance_criteria)
        if task.acceptance_criteria
        else "- No acceptance criteria captured"
    )
    reading = "\n".join(
        f"- {path}" for path in recommended_reading(task, record)
    )
    constraints = "\n".join(f"- {rule}" for rule in repo_guardrails())
    notes = task.implementation_notes or "No implementation notes captured."
    dependencies = (
        ", ".join(record["dependencies"]) if record["dependencies"] else "None"
    )

    prompt_markdown = textwrap.dedent(
        f"""
        ## Task

        Execute `{task.task_id}`: {task.title}

        ## Why Now

        This task is currently dispatchable from the backlog. Its known
        dependencies are satisfied in the current planning snapshot: {dependencies}.

        ## Scope

        {task.description or "No description captured."}

        ## Required Reading

        {reading}

        ## Constraints

        - Recommended write scope: {", ".join(record["write_scope"])}
        {constraints}

        ## Acceptance Criteria

        {acceptance}

        ## Deliverables

        - Complete the task within the recommended write scope.
        - Report any blocker that would require expanding scope or revisiting
          dependency assumptions.
        - Summarize concrete changes or findings before finishing.

        ## First Step

        Read the task file and the required documents, then restate a concrete
        execution plan for this task only.

        ## Implementation Notes

        {notes}
        """
    ).strip()

    return ClaudePromptPacket(
        task_id=task.task_id,
        title=task.title,
        lane=record["lane"],
        write_scope=list(record["write_scope"]),
        session_name=f"{task.task_id}: {task.title}"[:120],
        summary=(
            f"Task {task.task_id} in lane {record['lane']} with write scope "
            f"{', '.join(record['write_scope'])}."
        ),
        execution_mode="simple_subagent",
        team_shape=[],
        prompt_markdown=prompt_markdown,
        prompt_filename=prompt_filename_for_task(task),
        agent_name=agent_name_for_task(task),
    )


def build_custom_agent_prompt(
    packet: ClaudePromptPacket, task: Task, launch_mode: str
) -> str:
    task_file = task.source_path or "N/A"
    reading = "\n".join(
        f"- {path}"
        for path in recommended_reading(
            task, {"lane": packet.lane, "write_scope": packet.write_scope}
        )
    )
    guardrails = "\n".join(f"- {rule}" for rule in repo_guardrails())
    execution_mode_text = (
        "simple_subagent"
        if packet.execution_mode == "simple_subagent"
        else "agent_team"
    )
    team_shape_text = (
        ", ".join(packet.team_shape)
        if packet.team_shape
        else "No team shape suggested."
    )
    execution_brief = (
        """
        Execution model:
        - You are a single focused subagent for this task.
        - Plan first, then execute the task yourself.
        - Do not create a teammate structure for this task.
        """
        if packet.execution_mode == "simple_subagent"
        else f"""
        Execution model:
        - You are the top-level owner for this task, but this task has been
          classified as better suited to an agent team.
        - First, inspect the repository context and form a task-local plan.
        - Then create an agent team for this task.
        - Decompose the task into internal sub-tasks, assign them to teammates,
          and have teammates communicate when useful.
        - Require plan approval for teammates before they make changes.
        - Suggested team shape: {team_shape_text}
        - Synthesize the team outcome before finishing.
        """
    ).strip()
    runtime_mode_brief = (
        """
        Runtime mode for this run:
        - plan-only
        - You must inspect and plan only.
        - Do not edit files, do not implement, and do not execute the task body.
        - If you are an `agent_team` lead, you may create teammates for planning,
          but teammates must also stop at planning and must not implement.
        """
        if launch_mode == "plan-only"
        else """
        Runtime mode for this run:
        - execute
        - After planning, you are expected to carry the task forward.
        """
    ).strip()

    return textwrap.dedent(
        f"""
        You are the dedicated owner for {task.task_id}: {task.title}.

        You are not a generalist helper for the whole backlog. You own only this
        task. Stay inside the recommended write scope unless the orchestrator
        explicitly expands it.

        Execution sequence:
        - First, inspect the relevant repository context and produce a short,
          task-local implementation plan.
        - Second, validate that the plan fits the task scope and repository
          guardrails.
        - Third, only after that planning step, execute the task.
        - Do not jump straight into edits without first forming the plan.

        Selected execution mode:
        - {execution_mode_text}

        {execution_brief}

        {runtime_mode_brief}

        Recommended write scope:
        - {", ".join(packet.write_scope)}

        Task file:
        - {task_file}

        Required reading:
        {reading}

        Repository guardrails:
        {guardrails}

        Primary execution brief:

        {packet.prompt_markdown}
        """
    ).strip()


def build_custom_agents_json(
    packets: Sequence[ClaudePromptPacket],
    tasks_by_id: Dict[str, Task],
    launch_mode: str,
) -> Dict[str, Dict[str, str]]:
    agents: Dict[str, Dict[str, str]] = {}
    for packet in packets:
        task = tasks_by_id[packet.task_id]
        agents[packet.agent_name] = {
            "description": (
                f"{packet.summary} execution_mode={packet.execution_mode}"
            ),
            "prompt": build_custom_agent_prompt(packet, task, launch_mode),
        }
    return agents


def build_orchestrator_prompt(
    packets: Sequence[ClaudePromptPacket], launch_mode: str
) -> str:
    mode_instruction = {
        "dry-run": (
            "This is a simulated launch review. Treat the listed agents and "
            "assignments as a fake run generated without real subagent work."
        ),
        "plan-only": (
            "Spawn one subagent per selected task in parallel using the exact "
            "custom agent names below. Each subagent must inspect repository "
            "context and build a short task-local plan only. No implementation "
            "or file edits are allowed in this run."
        ),
        "execute": (
            "Spawn one subagent per selected task in parallel using the exact "
            "custom agent names below. Each subagent owns its task and must "
            "first build a short task-local plan from repository evidence, then "
            "execute within its write scope, then report outcome succinctly."
        ),
    }[launch_mode]

    task_listing = "\n".join(
        (
            f"- Agent `{packet.agent_name}` owns `{packet.task_id}`: "
            f"{packet.title} | lane={packet.lane} | "
            f"execution_mode={packet.execution_mode} | "
            f"write_scope={', '.join(packet.write_scope)}"
        )
        for packet in packets
    )

    return textwrap.dedent(
        f"""
        You are the main orchestration session for backlog-selected work.

        {mode_instruction}

        Selected task count: {len(packets)}

        Rules:
        - Spawn exactly {len(packets)} subagents: one per selected task, no more
          and no fewer.
        - Use the custom agent assigned to each task; do not invent different owners.
        - Each subagent must plan before implementing.
        - If a task is marked `simple_subagent`, its owner executes it directly.
        - If a task is marked `agent_team`, its owner must act as a lead,
          create an internal agent team for that task, and coordinate teammates.
        - In `plan-only`, neither the top-level subagents nor any teammates may
          implement or edit files.
        - Keep the tasks isolated. Do not merge scopes unless a subagent
          proves a blocker.
        - Wait for all subagents before returning.
        - Your final response must be exactly one JSON object matching the
          provided schema.
        - Do not return prose, Markdown, code fences, or explanatory text.
        - The final JSON must contain exactly these top-level keys:
          `launch_mode`, `selected_task_count`, `overall_summary`, `agents`.
        - `selected_task_count` must be {len(packets)}.
        - Each item in `agents` must include exactly:
          `agent_name`, `task_id`, `execution_mode`, `status`,
          `assignment_summary`, `first_step`.
        - Preserve the assigned `execution_mode` value for each task exactly.
        - In `plan-only`, use `status = planned` for every agent.

        Selected tasks:
        {task_listing}
        """
    ).strip()


def subprompt_generation_schema() -> str:
    schema = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "agent_name": {"type": "string"},
            "execution_mode": {
                "type": "string",
                "enum": ["simple_subagent", "agent_team"],
            },
            "summary": {"type": "string"},
            "description": {"type": "string"},
            "team_shape": {
                "type": "array",
                "items": {"type": "string"},
            },
            "prompt_markdown": {"type": "string"},
        },
        "required": [
            "task_id",
            "agent_name",
            "execution_mode",
            "summary",
            "description",
            "team_shape",
            "prompt_markdown",
        ],
        "additionalProperties": False,
    }
    return json.dumps(schema, separators=(",", ":"))


def execution_mode_decision_schema() -> str:
    schema = {
        "type": "object",
        "properties": {
            "overall_summary": {"type": "string"},
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "execution_mode": {
                            "type": "string",
                            "enum": ["simple_subagent", "agent_team"],
                        },
                        "reasoning_summary": {"type": "string"},
                        "team_shape": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "task_id",
                        "execution_mode",
                        "reasoning_summary",
                        "team_shape",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["overall_summary", "decisions"],
        "additionalProperties": False,
    }
    return json.dumps(schema, separators=(",", ":"))


def task_context_schema() -> str:
    schema = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "context_summary": {"type": "string"},
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
            },
            "repo_findings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "task_id",
            "context_summary",
            "relevant_files",
            "repo_findings",
        ],
        "additionalProperties": False,
    }
    return json.dumps(schema, separators=(",", ":"))


def orchestration_prompt_schema() -> str:
    schema = {
        "type": "object",
        "properties": {
            "overall_summary": {"type": "string"},
            "orchestration_prompt": {"type": "string"},
        },
        "required": ["overall_summary", "orchestration_prompt"],
        "additionalProperties": False,
    }
    return json.dumps(schema, separators=(",", ":"))


def claude_orchestrator_schema() -> str:
    schema = {
        "type": "object",
        "properties": {
            "launch_mode": {"type": "string"},
            "selected_task_count": {"type": "integer"},
            "overall_summary": {"type": "string"},
            "agents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_name": {"type": "string"},
                        "task_id": {"type": "string"},
                        "execution_mode": {
                            "type": "string",
                            "enum": ["simple_subagent", "agent_team"],
                        },
                        "status": {
                            "type": "string",
                            "enum": [
                                "planned",
                                "completed",
                                "blocked",
                                "failed",
                            ],
                        },
                        "assignment_summary": {"type": "string"},
                        "first_step": {"type": "string"},
                    },
                    "required": [
                        "agent_name",
                        "task_id",
                        "execution_mode",
                        "status",
                        "assignment_summary",
                        "first_step",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "launch_mode",
            "selected_task_count",
            "overall_summary",
            "agents",
        ],
        "additionalProperties": False,
    }
    return json.dumps(schema, separators=(",", ":"))


def build_task_context_request(blueprint: Dict[str, Any]) -> str:
    acceptance = blueprint["acceptance_criteria"] or [
        "No acceptance criteria captured."
    ]
    acceptance_block = "\n".join(f"- {item}" for item in acceptance)
    reading_block = "\n".join(
        f"- {item}" for item in blueprint["required_reading"]
    )
    dependencies = blueprint["dependencies"] or ["None"]
    dependency_block = ", ".join(dependencies)
    notes = blueprint["implementation_notes"] or "No implementation notes captured."
    return textwrap.dedent(
        f"""
        You are distilling repository context for one backlog task.

        Return JSON only, matching the provided schema.

        First inspect the repository in read-only mode:
        - read the task file first
        - read the listed required documents
        - inspect any additional repository files that are truly relevant

        Then produce a concise context brief that will be used by a later LLM call
        to generate the task's subagent prompt.

        Focus only on:
        - what code or docs matter most
        - what constraints or architecture choices matter
        - what the future task owner must know before planning

        Task:
        - Task id: {blueprint["task_id"]}
        - Title: {blueprint["title"]}
        - Lane: {blueprint["lane"]}
        - Write scope: {", ".join(blueprint["write_scope"])}
        - Task file: {blueprint["source_path"] or "N/A"}
        - Dependencies already satisfied: {dependency_block}

        Description:
        {blueprint["description"]}

        Required reading:
        {reading_block}

        Acceptance criteria:
        {acceptance_block}

        Implementation notes:
        {notes}
        """
    ).strip()


def build_subprompt_generation_request(
    blueprint: Dict[str, Any],
    decision: Dict[str, Any],
    context_brief: Dict[str, Any],
    launch_mode: str,
) -> str:
    acceptance = blueprint["acceptance_criteria"] or [
        "No acceptance criteria captured."
    ]
    acceptance_block = "\n".join(f"- {item}" for item in acceptance)
    team_shape = decision["team_shape"] or ["No team suggested."]
    team_shape_block = "\n".join(f"- {item}" for item in team_shape)
    launch_mode_instruction = (
        """
        Runtime launch mode:
        - plan-only
        - The generated prompt must force the task owner to stop at planning.
        - If the task uses `agent_team`, teammates may be created for planning only.
        """
        if launch_mode == "plan-only"
        else """
        Runtime launch mode:
        - execute
        - The generated prompt must make the task owner plan first, then execute.
        """
    ).strip()
    guardrails = "\n".join(f"- {rule}" for rule in repo_guardrails())
    findings = context_brief["repo_findings"] or ["No additional findings captured."]
    relevant_files = context_brief["relevant_files"] or ["No files captured."]
    findings_block = "\n".join(f"- {item}" for item in findings)
    relevant_files_block = "\n".join(f"- {item}" for item in relevant_files)
    return textwrap.dedent(
        f"""
        You are generating the final subagent prompt for one backlog task.

        Return JSON only, matching the provided schema.

        Preserve exactly:
        - task_id = {blueprint["task_id"]}
        - agent_name = {blueprint["agent_name"]}
        - execution_mode = {decision["execution_mode"]}

        Your only job is to write one high-quality prompt for this task owner.

        Repository guardrails:
        {guardrails}

        {launch_mode_instruction}

        Task metadata:
        - Title: {blueprint["title"]}
        - Lane: {blueprint["lane"]}
        - Write scope: {", ".join(blueprint["write_scope"])}
        - Prompt file: {blueprint["prompt_filename"]}
        - Session name: {blueprint["session_name"]}
        - Task file: {blueprint["source_path"] or "N/A"}

        Execution mode decision:
        - execution_mode: {decision["execution_mode"]}
        - why: {decision["reasoning_summary"]}
        - suggested team shape:
        {team_shape_block}

        Distilled repository context:
        - summary: {context_brief["context_summary"]}
        - relevant files:
        {relevant_files_block}
        - repo findings:
        {findings_block}

        Description:
        {blueprint["description"]}

        Acceptance criteria:
        {acceptance_block}

        Requirements:
        - make the prompt concrete, task-specific, and operationally useful
        - make the task owner plan before doing anything else
        - if `simple_subagent`, the owner should work alone
        - if `agent_team`, the owner should create and lead an internal agent team
        - if `agent_team`, require plan approval for teammates before changes
        """
    ).strip()


def build_orchestration_prompt_generation_request(
    packets: Sequence[ClaudePromptPacket],
    launch_mode: str,
) -> str:
    task_blocks = "\n".join(
        (
            f"- {packet.agent_name} owns {packet.task_id} | "
            f"execution_mode={packet.execution_mode} | "
            f"write_scope={', '.join(packet.write_scope)}"
        )
        for packet in packets
    )
    launch_mode_instruction = (
        "This run is plan-only. Top-level subagents and any teammates "
        "must stop at planning."
        if launch_mode == "plan-only"
        else "This run is execute. Top-level subagents must plan first, then execute."
    )
    return textwrap.dedent(
        f"""
        You are generating the orchestration prompt for a Claude Code multi-agent run.

        Return JSON only, matching the provided schema.

        You must write one orchestration prompt that:
        - spawns exactly {len(packets)} top-level subagents
        - assigns each task to the provided custom agent name
        - preserves each task's execution_mode exactly
        - tells `simple_subagent` owners to work directly
        - tells `agent_team` owners to create and lead an internal agent team
        - keeps task scopes isolated
        - tells the main session to wait for all top-level subagents before returning
        - forces the final response to be one JSON object only, with the exact
          top-level keys `launch_mode`, `selected_task_count`,
          `overall_summary`, and `agents`
        - forces every agent record to include exactly:
          `agent_name`, `task_id`, `execution_mode`, `status`,
          `assignment_summary`, `first_step`
        - forbids prose, Markdown, and code fences in the final response

        Runtime mode:
        - {launch_mode}
        - {launch_mode_instruction}

        Selected tasks:
        {task_blocks}
        """
    ).strip()


def build_execution_mode_decision_request(
    blueprints: Sequence[Dict[str, Any]],
) -> str:
    task_blocks: List[str] = []
    for blueprint in blueprints:
        acceptance = blueprint["acceptance_criteria"] or [
            "No acceptance criteria captured."
        ]
        acceptance_block = "\n".join(f"- {item}" for item in acceptance)
        reading_block = "\n".join(
            f"- {item}" for item in blueprint["required_reading"]
        )
        dependencies = blueprint["dependencies"] or ["None"]
        dependency_block = ", ".join(dependencies)
        notes = blueprint["implementation_notes"] or "No implementation notes captured."
        task_blocks.append(
            textwrap.dedent(
                f"""
                ## {blueprint["task_id"]} / {blueprint["agent_name"]}

                - Title: {blueprint["title"]}
                - Lane: {blueprint["lane"]}
                - Write scope: {", ".join(blueprint["write_scope"])}
                - Task file: {blueprint["source_path"] or "N/A"}
                - Dependencies already satisfied: {dependency_block}

                Description:
                {blueprint["description"]}

                Required reading:
                {reading_block}

                Acceptance criteria:
                {acceptance_block}

                Implementation notes:
                {notes}
                """
            ).strip()
        )

    task_blocks_text = "\n\n".join(task_blocks)
    return textwrap.dedent(
        f"""
        You are deciding the execution mode for backlog-selected tasks.

        Return JSON only, matching the provided schema.

        For every selected task, choose exactly one execution mode:
        - `simple_subagent`: one focused owner can plan and execute the task alone
        - `agent_team`: the top-level owner should create and lead an internal
          agent team because the task materially benefits from teammate
          communication, internal decomposition, and collaboration

        Before deciding:
        - inspect the repository in read-only mode
        - read the task file first
        - read the listed required documents
        - inspect any additional repository files you judge relevant

        Decision standard:
        - choose `agent_team` only when the task would materially benefit from
          internal teammate collaboration
        - choose `simple_subagent` when a single strong owner should be enough
        - do not use cost-agnostic maximalism; choose `agent_team` only when the
          coordination overhead is justified by the task structure

        If you choose `agent_team`, also provide a suggested `team_shape` with a
        small set of concrete teammate roles.
        If you choose `simple_subagent`, return an empty `team_shape` list.

        Selected task blueprints:
        {task_blocks_text}
        """
    ).strip()


def _coerce_structured_output(payload: Any, schema: str) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    structured_output = payload.get("structured_output")
    if isinstance(structured_output, dict):
        return structured_output

    result_payload = payload.get("result")
    if isinstance(result_payload, dict):
        payload = result_payload

    try:
        schema_payload = json.loads(schema)
    except json.JSONDecodeError:
        return None

    required_keys = schema_payload.get("required", [])
    if isinstance(required_keys, list) and all(key in payload for key in required_keys):
        return payload
    return None


def run_claude_json(
    prompt: str,
    schema: str,
    model: str,
    effort: str,
    timeout_sec: int,
    permission_mode: str = "plan",
    agents_json: Dict[str, Dict[str, str]] | None = None,
    dangerously_skip_permissions: bool = False,
    enable_agent_teams: bool = False,
    call_name: str = "claude_call",
) -> Dict[str, Any]:
    command = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--json-schema",
        schema,
        "--model",
        model,
        "--effort",
        effort,
        "--permission-mode",
        permission_mode,
    ]
    if dangerously_skip_permissions:
        command.append("--dangerously-skip-permissions")
    if agents_json is not None:
        command.extend(["--agents", json.dumps(agents_json, ensure_ascii=False)])
    command.append(prompt)
    env = os.environ.copy()
    if enable_agent_teams:
        env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=max(timeout_sec, 1),
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeRunError(
            call_name,
            f"Claude call timed out after {max(timeout_sec, 1)} seconds",
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
        ) from exc
    if result.returncode != 0:
        raise ClaudeRunError(
            call_name,
            "Claude command failed: "
            f"{result.stderr.strip() or result.stdout.strip()}",
            stdout=result.stdout,
            stderr=result.stderr,
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeRunError(
            call_name,
            "Claude returned invalid JSON output",
            stdout=result.stdout,
            stderr=result.stderr,
        ) from exc
    structured_output = _coerce_structured_output(payload, schema)
    if not isinstance(structured_output, dict):
        raise ClaudeRunError(
            call_name,
            "Claude returned no structured_output payload",
            stdout=result.stdout,
            stderr=result.stderr,
            payload=payload,
        )
    return {"structured_output": structured_output, "raw_output": payload}


def simulate_execution_mode_decision(
    selected_items: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    decisions = []
    for item in selected_items:
        task = task_from_dict(item["task"])
        decisions.append(
            {
                "task_id": task.task_id,
                "execution_mode": "simple_subagent",
                "reasoning_summary": (
                    "Dry-run simulation defaults to simple_subagent. "
                    "No real LLM execution-mode decision was made."
                ),
                "team_shape": [],
            }
        )

    return {
        "mode": "dry-run",
        "overall_summary": (
            f"Simulated execution-mode decisions for {len(decisions)} selected tasks."
        ),
        "decisions": decisions,
        "raw_output": {
            "simulated": True,
            "call": "execution_mode_decision",
            "selected_task_count": len(decisions),
        },
    }


def simulate_context_distillation(
    selected_items: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    contexts = []
    for item in selected_items:
        task = task_from_dict(item["task"])
        record = item["dispatch"]
        contexts.append(
            {
                "task_id": task.task_id,
                "context_summary": (
                    "Dry-run simulated context brief based on task metadata only."
                ),
                "relevant_files": recommended_reading(task, record),
                "repo_findings": [
                    "No real repository inspection was performed in dry-run mode."
                ],
            }
        )
    return {
        "mode": "dry-run",
        "overall_summary": (
            f"Simulated context distillation for {len(contexts)} selected tasks."
        ),
        "contexts": contexts,
        "raw_output": {
            "simulated": True,
            "call": "task_context_distillation",
            "selected_task_count": len(contexts),
        },
    }


def decide_execution_modes_with_claude(
    selected_items: Sequence[Dict[str, Any]],
    model: str,
    effort: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    blueprints = [
        packet_blueprint(task_from_dict(item["task"]), item["dispatch"])
        for item in selected_items
    ]
    if not blueprints:
        return {
            "mode": "execute",
            "overall_summary": (
                "No selected tasks, so no execution-mode decision was needed."
            ),
            "decisions": [],
            "raw_output": {
                "simulated": False,
                "call": "execution_mode_decision",
                "selected_task_count": 0,
            },
        }

    prompt = build_execution_mode_decision_request(blueprints)
    result = run_claude_json(
        prompt=prompt,
        schema=execution_mode_decision_schema(),
        model=model,
        effort=effort,
        timeout_sec=timeout_sec,
        permission_mode="plan",
        dangerously_skip_permissions=True,
        enable_agent_teams=True,
        call_name="execution_mode_decision",
    )
    structured = result["structured_output"]
    decisions = structured.get("decisions", [])
    if len(decisions) != len(blueprints):
        raise RuntimeError(
            "Execution-mode decision returned "
            f"{len(decisions)} decisions for {len(blueprints)} selected tasks"
        )

    selected_task_ids = {item["task_id"] for item in blueprints}
    seen_task_ids: set[str] = set()
    for decision in decisions:
        task_id = decision["task_id"]
        if task_id not in selected_task_ids:
            raise RuntimeError(
                f"Execution-mode decision returned unexpected task_id {task_id}"
            )
        seen_task_ids.add(task_id)
    if seen_task_ids != selected_task_ids:
        missing = sorted(selected_task_ids - seen_task_ids)
        raise RuntimeError(
            "Execution-mode decision omitted selected tasks: " + ", ".join(missing)
        )

    return {
        "mode": "execute",
        "overall_summary": structured["overall_summary"],
        "decisions": decisions,
        "raw_output": result["raw_output"],
    }


def distill_task_contexts_with_claude(
    selected_items: Sequence[Dict[str, Any]],
    model: str,
    effort: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    blueprints = [
        packet_blueprint(task_from_dict(item["task"]), item["dispatch"])
        for item in selected_items
    ]
    contexts = []
    raw_outputs = []
    for blueprint in blueprints:
        result = run_claude_json(
            prompt=build_task_context_request(blueprint),
            schema=task_context_schema(),
            model=model,
            effort=effort,
            timeout_sec=timeout_sec,
            permission_mode="plan",
            dangerously_skip_permissions=True,
            call_name=f"task_context_distillation:{blueprint['task_id']}",
        )
        structured = result["structured_output"]
        if structured["task_id"] != blueprint["task_id"]:
            raise RuntimeError(
                "Task context distillation returned unexpected task_id "
                f"{structured['task_id']} for {blueprint['task_id']}"
            )
        contexts.append(structured)
        raw_outputs.append(result["raw_output"])

    return {
        "mode": "execute",
        "overall_summary": (
            f"Distilled repository context for {len(contexts)} selected tasks."
        ),
        "contexts": contexts,
        "raw_output": raw_outputs,
    }


def simulate_prompt_generation(
    selected_items: Sequence[Dict[str, Any]],
    execution_mode_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
) -> Dict[str, Any]:
    decisions_by_task_id = {
        decision["task_id"]: decision
        for decision in execution_mode_payload.get("decisions", [])
    }
    contexts_by_task_id = {
        context["task_id"]: context
        for context in context_payload.get("contexts", [])
    }
    packets: List[ClaudePromptPacket] = []
    for item in selected_items:
        task = task_from_dict(item["task"])
        record = item["dispatch"]
        packet = build_static_prompt_packet(task, record)
        decision = decisions_by_task_id.get(task.task_id, {})
        context = contexts_by_task_id.get(task.task_id, {})
        packet.execution_mode = decision.get("execution_mode", "simple_subagent")
        packet.team_shape = normalize_list(decision.get("team_shape"))
        if context.get("context_summary"):
            packet.summary = (
                f"{packet.summary} context_summary={context['context_summary']}"
            )
        packets.append(packet)

    return {
        "mode": "dry-run",
        "overall_summary": (
            f"Simulated prompt generation for {len(packets)} selected tasks."
        ),
        "packets": [packet_to_dict(packet) for packet in packets],
        "raw_output": {
            "simulated": True,
            "call": "prompt_generation",
            "selected_task_count": len(packets),
        },
    }


def generate_prompts_with_claude(
    selected_items: Sequence[Dict[str, Any]],
    execution_mode_payload: Dict[str, Any],
    context_payload: Dict[str, Any],
    launch_mode: str,
    model: str,
    effort: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    blueprints = [
        packet_blueprint(task_from_dict(item["task"]), item["dispatch"])
        for item in selected_items
    ]
    if not blueprints:
        return {
            "mode": "execute",
            "overall_summary": "No selected tasks, so no prompt generation was needed.",
            "packets": [],
            "raw_output": {
                "simulated": False,
                "call": "prompt_generation",
                "selected_task_count": 0,
            },
        }

    blueprint_by_task_id = {item["task_id"]: item for item in blueprints}
    decisions_by_task_id = {
        decision["task_id"]: decision
        for decision in execution_mode_payload.get("decisions", [])
    }
    contexts_by_task_id = {
        context["task_id"]: context
        for context in context_payload.get("contexts", [])
    }
    packets: List[ClaudePromptPacket] = []
    raw_outputs = []
    for task_id, blueprint in blueprint_by_task_id.items():
        decision = decisions_by_task_id[task_id]
        context = contexts_by_task_id[task_id]
        result = run_claude_json(
            prompt=build_subprompt_generation_request(
                blueprint,
                decision,
                context,
                launch_mode,
            ),
            schema=subprompt_generation_schema(),
            model=model,
            effort=effort,
            timeout_sec=timeout_sec,
            permission_mode="plan",
            dangerously_skip_permissions=True,
            call_name=f"subprompt_generation:{task_id}",
        )
        agent = result["structured_output"]
        raw_outputs.append(result["raw_output"])
        if agent["task_id"] != task_id:
            raise RuntimeError(
                f"Prompt generation returned unexpected task_id {agent['task_id']}"
            )
        if agent["agent_name"] != blueprint["agent_name"]:
            raise RuntimeError(
                f"Prompt generation changed agent_name for {task_id}: "
                f"{agent['agent_name']} != {blueprint['agent_name']}"
            )
        if agent["execution_mode"] != decision["execution_mode"]:
            raise RuntimeError(
                f"Prompt generation changed execution_mode for {task_id}: "
                f"{agent['execution_mode']} != {decision['execution_mode']}"
            )
        packets.append(
            ClaudePromptPacket(
                task_id=task_id,
                title=blueprint["title"],
                lane=blueprint["lane"],
                write_scope=list(blueprint["write_scope"]),
                session_name=blueprint["session_name"],
                summary=agent["summary"],
                execution_mode=agent["execution_mode"],
                team_shape=normalize_list(agent["team_shape"]),
                prompt_markdown=agent["prompt_markdown"],
                prompt_filename=blueprint["prompt_filename"],
                agent_name=blueprint["agent_name"],
            )
        )

    return {
        "mode": "execute",
        "overall_summary": (
            f"Generated {len(packets)} subagent prompts from distilled context."
        ),
        "packets": [packet_to_dict(packet) for packet in packets],
        "raw_output": raw_outputs,
    }


def simulate_orchestration_prompt_generation(
    packets: Sequence[ClaudePromptPacket],
    launch_mode: str,
) -> Dict[str, Any]:
    return {
        "mode": "dry-run",
        "overall_summary": (
            f"Simulated orchestration prompt generation for {len(packets)} tasks."
        ),
        "orchestration_prompt": build_orchestrator_prompt(packets, launch_mode),
        "raw_output": {
            "simulated": True,
            "call": "orchestration_prompt_generation",
            "selected_task_count": len(packets),
        },
    }


def generate_orchestration_prompt_with_claude(
    packets: Sequence[ClaudePromptPacket],
    launch_mode: str,
    model: str,
    effort: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    if not packets:
        return {
            "mode": "execute",
            "overall_summary": (
                "No selected tasks, so no orchestration prompt was needed."
            ),
            "orchestration_prompt": build_orchestrator_prompt([], launch_mode),
            "raw_output": {
                "simulated": False,
                "call": "orchestration_prompt_generation",
                "selected_task_count": 0,
            },
        }
    result = run_claude_json(
        prompt=build_orchestration_prompt_generation_request(packets, launch_mode),
        schema=orchestration_prompt_schema(),
        model=model,
        effort=effort,
        timeout_sec=timeout_sec,
        permission_mode="plan",
        dangerously_skip_permissions=True,
        call_name="orchestration_prompt_generation",
    )
    structured = result["structured_output"]
    return {
        "mode": "execute",
        "overall_summary": structured["overall_summary"],
        "orchestration_prompt": structured["orchestration_prompt"],
        "raw_output": result["raw_output"],
    }


def simulate_orchestration(
    packets: Sequence[ClaudePromptPacket],
    launch_mode: str,
) -> Dict[str, Any]:
    return {
        "launch_mode": launch_mode,
        "selected_task_count": len(packets),
        "overall_summary": (
            f"Simulated orchestration for {len(packets)} selected tasks."
        ),
        "agents": [
            {
                "agent_name": packet.agent_name,
                "task_id": packet.task_id,
                "execution_mode": packet.execution_mode,
                "status": "planned" if launch_mode == "plan-only" else "completed",
                "assignment_summary": (
                    f"Simulated assignment for {packet.task_id} in lane {packet.lane}."
                ),
                "first_step": (
                    "Read the task file and required documents, then restate the "
                    "task-local execution plan."
                ),
            }
            for packet in packets
        ],
    }


def call_claude_multi_agent_orchestrator(
    agents_json: Dict[str, Dict[str, str]],
    orchestration_prompt: str,
    packets: Sequence[ClaudePromptPacket],
    expected_agent_count: int,
    enable_agent_teams: bool,
    launch_mode: str,
    model: str,
    effort: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    result = run_claude_json(
        prompt=orchestration_prompt,
        schema=claude_orchestrator_schema(),
        model=model,
        effort=effort,
        timeout_sec=timeout_sec,
        permission_mode="plan" if launch_mode == "plan-only" else "default",
        agents_json=agents_json,
        dangerously_skip_permissions=True,
        enable_agent_teams=enable_agent_teams,
        call_name="orchestration",
    )
    structured_output = result["structured_output"]
    if structured_output.get("selected_task_count") != expected_agent_count:
        raise RuntimeError(
            "Claude orchestrator returned selected_task_count="
            f"{structured_output.get('selected_task_count')} for "
            f"{expected_agent_count} selected tasks"
        )
    if len(structured_output.get("agents", [])) != expected_agent_count:
        raise RuntimeError(
            "Claude orchestrator returned "
            f"{len(structured_output.get('agents', []))} agent assignments for "
            f"{expected_agent_count} selected tasks"
        )
    expected_by_agent = {packet.agent_name: packet for packet in packets}
    plan_only_completed_agents: List[str] = []
    for agent in structured_output.get("agents", []):
        expected_packet = expected_by_agent.get(agent["agent_name"])
        if expected_packet is None:
            raise RuntimeError(
                "Claude orchestrator returned unexpected agent_name "
                f"{agent['agent_name']}"
            )
        if agent["task_id"] != expected_packet.task_id:
            raise RuntimeError(
                f"Claude orchestrator mapped {agent['agent_name']} to "
                f"{agent['task_id']} instead of {expected_packet.task_id}"
            )
        if agent["execution_mode"] != expected_packet.execution_mode:
            raise RuntimeError(
                f"Claude orchestrator changed execution_mode for "
                f"{agent['agent_name']}: {agent['execution_mode']} != "
                f"{expected_packet.execution_mode}"
            )
        if launch_mode == "plan-only":
            if agent["status"] == "completed":
                plan_only_completed_agents.append(agent["agent_name"])
                agent["status"] = "planned"
            elif agent["status"] not in {"planned", "blocked", "failed"}:
                raise RuntimeError(
                    "Claude orchestrator returned unexpected status in "
                    f"plan-only mode for {agent['agent_name']}: {agent['status']}"
                )
    if plan_only_completed_agents:
        structured_output["overall_summary"] = (
            f"{structured_output['overall_summary']} "
            "Normalized `completed` to `planned` for: "
            f"{', '.join(plan_only_completed_agents)}."
        ).strip()
    return result


def create_dispatch_bundle_dir(output_base_dir: Path) -> Path:
    bundle_dir = output_base_dir / f"claude-dispatch-{timestamp_slug()}"
    bundle_dir.mkdir(parents=True, exist_ok=False)
    return bundle_dir


def raw_artifact_filename(call_name: str) -> str:
    base_name = call_name.split(":", 1)[0]
    mapping = {
        "execution_mode_decision": "execution-mode-raw.json",
        "task_context_distillation": "context-distillation-raw.json",
        "subprompt_generation": "prompt-generation-raw.json",
        "orchestration_prompt_generation": "orchestration-prompt-raw.json",
        "orchestration": "orchestrator-raw.json",
    }
    return mapping.get(base_name, f"{slugify(base_name)}-raw.json")


def build_bundle_readme(
    dispatch_payload: Dict[str, Any],
    launch_mode: str,
    prompt_payload: Dict[str, Any] | None,
    execution_mode_payload: Dict[str, Any] | None,
    failure_payload: Dict[str, Any] | None,
) -> str:
    packets = []
    if prompt_payload is not None:
        packets = [
            packet_from_dict(packet_payload)
            for packet_payload in prompt_payload.get("packets", [])
        ]

    decisions_by_task_id = {}
    if execution_mode_payload is not None:
        decisions_by_task_id = {
            decision["task_id"]: decision
            for decision in execution_mode_payload.get("decisions", [])
        }

    lines = [
        "# Claude Code Dispatch Batch",
        "",
        f"- Generated at: `{dispatch_payload['generated_at']}`",
        f"- Mode: `{launch_mode}`",
        f"- Selected task count: `{len(dispatch_payload['selected_tasks'])}`",
    ]
    if failure_payload is not None:
        lines.extend(
            [
                "- Run status: `failed`",
                f"- Failed call: `{failure_payload.get('call_name', 'unknown')}`",
                "",
                "## Failure",
                "",
                failure_payload.get("message", "Unknown failure."),
            ]
        )
    else:
        lines.extend(["- Run status: `in_progress_or_complete`"])

    lines.extend(["", "## Tasks", ""])

    if packets:
        for packet in packets:
            lines.extend(
                [
                    f"### {packet.task_id} - {packet.title}",
                    "",
                    f"- Prompt file: `{packet.prompt_filename}`",
                    f"- Agent name: `{packet.agent_name}`",
                    f"- Execution mode: `{packet.execution_mode}`",
                    f"- Lane: `{packet.lane}`",
                    f"- Write scope: `{', '.join(packet.write_scope)}`",
                    "",
                ]
            )
    else:
        for item in dispatch_payload["selected_tasks"]:
            task = item["task"]
            dispatch = item["dispatch"]
            decision = decisions_by_task_id.get(task["task_id"])
            execution_mode = (
                decision["execution_mode"] if decision is not None else "pending"
            )
            lines.extend(
                [
                    f"### {task['task_id']} - {task['title']}",
                    "",
                    f"- Execution mode: `{execution_mode}`",
                    f"- Lane: `{dispatch['lane']}`",
                    f"- Write scope: `{', '.join(dispatch['write_scope'])}`",
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def update_dispatch_bundle(
    bundle_dir: Path,
    *,
    dispatch_payload: Dict[str, Any] | None = None,
    dispatch_text: str | None = None,
    execution_mode_payload: Dict[str, Any] | None = None,
    context_payload: Dict[str, Any] | None = None,
    prompt_payload: Dict[str, Any] | None = None,
    orchestration_prompt_payload: Dict[str, Any] | None = None,
    tasks_by_id: Dict[str, Task] | None = None,
    launch_mode: str | None = None,
    orchestrator_payload: Dict[str, Any] | None = None,
    orchestrator_raw: Dict[str, Any] | None = None,
    failure_payload: Dict[str, Any] | None = None,
) -> None:
    if dispatch_payload is not None:
        write_json_file(bundle_dir / "dispatch-plan.json", dispatch_payload)
    if dispatch_text is not None:
        write_text_file(bundle_dir / "dispatch-plan.txt", dispatch_text)
    if execution_mode_payload is not None:
        write_json_file(
            bundle_dir / "execution-mode-result.json", execution_mode_payload
        )
        if "raw_output" in execution_mode_payload:
            write_json_file(
                bundle_dir / "execution-mode-raw.json",
                execution_mode_payload["raw_output"],
            )
    if context_payload is not None:
        write_json_file(
            bundle_dir / "context-distillation-result.json", context_payload
        )
        if "raw_output" in context_payload:
            write_json_file(
                bundle_dir / "context-distillation-raw.json",
                context_payload["raw_output"],
            )
    if prompt_payload is not None:
        write_json_file(bundle_dir / "prompt-generation-result.json", prompt_payload)
        if "raw_output" in prompt_payload:
            write_json_file(
                bundle_dir / "prompt-generation-raw.json",
                prompt_payload["raw_output"],
            )
        packets = [
            packet_from_dict(packet_payload)
            for packet_payload in prompt_payload.get("packets", [])
        ]
        for packet in packets:
            write_text_file(bundle_dir / packet.prompt_filename, packet.prompt_markdown)
        if tasks_by_id is not None and launch_mode is not None:
            agents_json = build_custom_agents_json(packets, tasks_by_id, launch_mode)
            write_json_file(bundle_dir / "claude-agents.json", agents_json)
    if orchestration_prompt_payload is not None:
        write_json_file(
            bundle_dir / "orchestration-prompt-result.json",
            orchestration_prompt_payload,
        )
        if "raw_output" in orchestration_prompt_payload:
            write_json_file(
                bundle_dir / "orchestration-prompt-raw.json",
                orchestration_prompt_payload["raw_output"],
            )
        orchestration_prompt = orchestration_prompt_payload.get("orchestration_prompt")
        if isinstance(orchestration_prompt, str):
            write_text_file(
                bundle_dir / "orchestration-prompt.md", orchestration_prompt
            )
    if orchestrator_payload is not None:
        write_json_file(bundle_dir / "orchestrator-result.json", orchestrator_payload)
    if orchestrator_raw is not None:
        write_json_file(bundle_dir / "orchestrator-raw.json", orchestrator_raw)
    if failure_payload is not None:
        write_json_file(bundle_dir / "run-failure.json", failure_payload)
        call_name = failure_payload.get("call_name")
        if isinstance(call_name, str) and call_name:
            raw_filename = raw_artifact_filename(call_name)
            raw_payload = failure_payload.get("payload")
            if raw_payload is not None:
                write_json_file(bundle_dir / raw_filename, raw_payload)
            else:
                write_json_file(
                    bundle_dir / raw_filename,
                    {
                        "call_name": call_name,
                        "stdout": failure_payload.get("stdout", ""),
                        "stderr": failure_payload.get("stderr", ""),
                    },
                )
    if dispatch_payload is not None and launch_mode is not None:
        write_text_file(
            bundle_dir / "README.md",
            build_bundle_readme(
                dispatch_payload=dispatch_payload,
                launch_mode=launch_mode,
                prompt_payload=prompt_payload,
                execution_mode_payload=execution_mode_payload,
                failure_payload=failure_payload,
            ),
        )


def main() -> int:
    args = parse_args()
    launch_mode = launch_mode_for_args(args)

    if args.snapshot:
        tasks = load_tasks(Path(args.snapshot))
    else:
        tasks = load_tasks_from_backlog_dir(Path(args.backlog_dir))

    tasks_by_id = {task.task_id: task for task in tasks}
    classified = classify_tasks(
        tasks=tasks,
        mobile_repo_present=args.mobile_repo_present,
    )
    selection = select_dispatch_now(
        records=classified["records"],
        max_dispatch=max(args.max_dispatch, 0),
    )
    payload = {**classified, **selection}
    payload["summary"] = {
        "total": len(payload["records"]),
        "ready": sum(1 for record in payload["records"] if record["ready"]),
        "dispatchable": sum(
            1 for record in payload["records"] if record["dispatchable"]
        ),
        "selected": len(payload["dispatch_now"]),
    }
    dispatch_payload = build_dispatch_payload(tasks_by_id, payload)
    dispatch_text = render_text(payload)
    bundle_dir = create_dispatch_bundle_dir(Path(args.output_dir))

    execution_mode_payload: Dict[str, Any] | None = None
    context_payload: Dict[str, Any] | None = None
    prompt_payload: Dict[str, Any] | None = None
    orchestration_prompt_payload: Dict[str, Any] | None = None
    orchestrator_payload: Dict[str, Any] | None = None
    orchestrator_raw: Dict[str, Any] | None = None
    failure_payload: Dict[str, Any] | None = None

    update_dispatch_bundle(
        bundle_dir,
        dispatch_payload=dispatch_payload,
        dispatch_text=dispatch_text,
        launch_mode=launch_mode,
    )

    selected_items = dispatch_payload["selected_tasks"]
    try:
        if launch_mode == "dry-run":
            execution_mode_payload = simulate_execution_mode_decision(selected_items)
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                launch_mode=launch_mode,
            )
            context_payload = simulate_context_distillation(selected_items)
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                launch_mode=launch_mode,
            )
            prompt_payload = simulate_prompt_generation(
                selected_items,
                execution_mode_payload,
                context_payload,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                prompt_payload=prompt_payload,
                tasks_by_id=tasks_by_id,
                launch_mode=launch_mode,
            )
            packets = [
                packet_from_dict(packet_payload)
                for packet_payload in prompt_payload["packets"]
            ]
            orchestration_prompt_payload = simulate_orchestration_prompt_generation(
                packets,
                launch_mode,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                prompt_payload=prompt_payload,
                orchestration_prompt_payload=orchestration_prompt_payload,
                tasks_by_id=tasks_by_id,
                launch_mode=launch_mode,
            )
            orchestrator_payload = simulate_orchestration(packets, "dry-run")
            orchestrator_raw = {
                "simulated": True,
                "call": "orchestration",
                "selected_task_count": len(packets),
            }
        else:
            execution_mode_payload = decide_execution_modes_with_claude(
                selected_items=selected_items,
                model=args.claude_model,
                effort=args.claude_effort,
                timeout_sec=args.claude_timeout_sec,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                launch_mode=launch_mode,
            )
            context_payload = distill_task_contexts_with_claude(
                selected_items=selected_items,
                model=args.claude_model,
                effort=args.claude_effort,
                timeout_sec=args.claude_timeout_sec,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                launch_mode=launch_mode,
            )
            prompt_payload = generate_prompts_with_claude(
                selected_items=selected_items,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                launch_mode=launch_mode,
                model=args.claude_model,
                effort=args.claude_effort,
                timeout_sec=args.claude_timeout_sec,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                prompt_payload=prompt_payload,
                tasks_by_id=tasks_by_id,
                launch_mode=launch_mode,
            )
            packets = [
                packet_from_dict(packet_payload)
                for packet_payload in prompt_payload["packets"]
            ]
            agents_json = build_custom_agents_json(packets, tasks_by_id, launch_mode)
            orchestration_prompt_payload = generate_orchestration_prompt_with_claude(
                packets=packets,
                launch_mode=launch_mode,
                model=args.claude_model,
                effort=args.claude_effort,
                timeout_sec=args.claude_timeout_sec,
            )
            update_dispatch_bundle(
                bundle_dir,
                dispatch_payload=dispatch_payload,
                execution_mode_payload=execution_mode_payload,
                context_payload=context_payload,
                prompt_payload=prompt_payload,
                orchestration_prompt_payload=orchestration_prompt_payload,
                tasks_by_id=tasks_by_id,
                launch_mode=launch_mode,
            )
            enable_agent_teams = any(
                packet.execution_mode == "agent_team" for packet in packets
            )
            if packets:
                orchestrator_result = call_claude_multi_agent_orchestrator(
                    agents_json=agents_json,
                    orchestration_prompt=orchestration_prompt_payload[
                        "orchestration_prompt"
                    ],
                    packets=packets,
                    expected_agent_count=len(packets),
                    enable_agent_teams=enable_agent_teams,
                    launch_mode=launch_mode,
                    model=args.claude_model,
                    effort=args.claude_effort,
                    timeout_sec=args.claude_timeout_sec,
                )
                orchestrator_payload = orchestrator_result["structured_output"]
                orchestrator_raw = orchestrator_result["raw_output"]
            else:
                orchestrator_payload = {
                    "launch_mode": launch_mode,
                    "selected_task_count": 0,
                    "overall_summary": (
                        "No selected tasks, so no Claude launch was needed."
                    ),
                    "agents": [],
                }
                orchestrator_raw = {
                    "simulated": False,
                    "call": "orchestration",
                    "selected_task_count": 0,
                    "skipped": True,
                }
    except Exception as exc:
        failure_payload = (
            exc.to_dict()
            if isinstance(exc, ClaudeRunError)
            else {
                "error_type": type(exc).__name__,
                "call_name": "internal_python",
                "message": str(exc),
            }
        )
        update_dispatch_bundle(
            bundle_dir,
            dispatch_payload=dispatch_payload,
            dispatch_text=dispatch_text,
            execution_mode_payload=execution_mode_payload,
            context_payload=context_payload,
            prompt_payload=prompt_payload,
            orchestration_prompt_payload=orchestration_prompt_payload,
            tasks_by_id=tasks_by_id,
            launch_mode=launch_mode,
            orchestrator_payload=orchestrator_payload,
            orchestrator_raw=orchestrator_raw,
            failure_payload=failure_payload,
        )
        print(f"Dispatch bundle written to: {bundle_dir}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    update_dispatch_bundle(
        bundle_dir,
        dispatch_payload=dispatch_payload,
        dispatch_text=dispatch_text,
        execution_mode_payload=execution_mode_payload,
        context_payload=context_payload,
        prompt_payload=prompt_payload,
        orchestration_prompt_payload=orchestration_prompt_payload,
        tasks_by_id=tasks_by_id,
        launch_mode=launch_mode,
        orchestrator_payload=orchestrator_payload,
        orchestrator_raw=orchestrator_raw,
    )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "bundle_dir": str(bundle_dir),
                    "dry_run": launch_mode == "dry-run",
                    "launch_mode": launch_mode,
                    "summary": dispatch_payload["summary"],
                    "selected_task_ids": [
                        item["task"]["task_id"] for item in selected_items
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(dispatch_text)
        print("")
        print(f"Run bundle written to: {bundle_dir}")
        print(f"Launch mode: {launch_mode}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
