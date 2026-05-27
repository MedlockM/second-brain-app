#!/usr/bin/env python3
"""Dispatch backlog tasks to parallel Claude Code agents via git worktrees.

Each selected task gets its own worktree (branched from the current branch),
its own `claude -p` process, and is auto-merged back after completion.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
WORKTREE_BASE = ".claude/worktrees"

# ---------------------------------------------------------------------------
# Task type configuration
# ---------------------------------------------------------------------------

TYPE_MODEL = {
    "research": "sonnet", "feature": "sonnet", "cleanup": "haiku",
    "ingestion": "sonnet", "tooling": "sonnet", "implementation": "sonnet",
}
TYPE_EFFORT = {
    "research": "high", "feature": "high", "cleanup": "medium",
    "ingestion": "high", "tooling": "medium", "implementation": "high",
}
TYPE_TIMEOUT = {
    "research": 0, "feature": 0, "cleanup": 0,
    "ingestion": 0, "tooling": 0, "implementation": 0,
}

COMMON_GUARDRAILS = """\
Tu es un agent Claude Code dédié à une seule tâche du backlog.

Règles communes :
- Ne touche PAS au dossier `front/` — c'est du legacy qui sera remplacé.
- Ne travaille PAS sur : Spotify sync, email delivery, quiz generation, \
Whisper transcription, ou credit-based billing.
- Pré-production : supprime le code obsolète directement, pas de couche de \
backward-compatibility.
- Après avoir terminé, fais un git commit avec un message descriptif en anglais.
- Langue des commits et code : anglais. Commentaires si nécessaire uniquement.
"""

TYPE_GUARDRAILS = {
    "research": (
        "- Utilise WebFetch et WebSearch pour trouver des informations.\n"
        "- Produis un document markdown dans docs/research/.\n"
        "- Ne modifie PAS le code source.\n"
        "- Cite tes sources avec des URLs."
    ),
    "feature": (
        "- Utilise les endpoints canoniques : `/api/media/*` et `/api/artifacts/*`.\n"
        "- Respecte l'architecture hexagonale là où elle est déjà en place.\n"
        "- N'ajoute PAS de tests automatisés sauf si les critères d'acceptation le demandent."
    ),
    "cleanup": (
        "- Focus sur la suppression de code.\n"
        "- Cherche TOUTES les références (grep) avant de supprimer quoi que ce soit.\n"
        "- N'ajoute pas de nouveau code."
    ),
    "ingestion": (
        "- Suis le pattern resolver dans media_summarizer/infrastructure/resolvers/.\n"
        "- Gère les erreurs avec des enums stables.\n"
        "- Utilise les endpoints canoniques : `/api/media/*`."
    ),
    "tooling": (
        "- Reste dans le dossier scripts/ ou la zone tooling.\n"
        "- Garde les scripts autonomes et documentés."
    ),
    "implementation": (
        "- Utilise les endpoints canoniques : `/api/media/*` et `/api/artifacts/*`.\n"
        "- Architecture hexagonale là où elle est déjà en place, sinon garde ça simple.\n"
        "- N'ajoute PAS de tests automatisés sauf si les critères d'acceptation le demandent."
    ),
}

CONTEXT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "relevant_files": {"type": "array", "items": {"type": "string"}},
        "architecture_notes": {"type": "string"},
        "existing_patterns": {"type": "string"},
        "suggested_approach": {"type": "string"},
    },
    "required": ["relevant_files", "architecture_notes",
                  "existing_patterns", "suggested_approach"],
}, separators=(",", ":"))

VALIDATION_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "complete": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "missing_criteria": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["complete", "confidence", "missing_criteria", "summary"],
}, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Task:
    task_id: str
    title: str
    status: str
    priority: str
    dependencies: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    dispatchable: bool = True
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    implementation_notes: str = ""
    source_path: Optional[str] = None


@dataclass
class TaskResult:
    task_id: str
    status: str  # "completed", "failed", "timeout", "merge_conflict"
    branch: str
    worktree_path: str
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    duration_sec: float = 0.0


# ---------------------------------------------------------------------------
# YAML-ish front-matter parser
# ---------------------------------------------------------------------------


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if text == "[]":
        return []
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    return text


def _parse_list(value: Any) -> List[str]:
    if not value or str(value).strip() == "[]":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value
                if str(v).strip() and str(v).strip() != "[]"]
    s = str(value).strip()
    if "," in s:
        return [v.strip() for v in s.split(",") if v.strip() and v.strip() != "[]"]
    return [s] if s and s != "[]" else []


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
            folded: List[str] = []
            while index < len(lines):
                cont = lines[index]
                if cont.startswith("  "):
                    folded.append(cont.strip())
                    index += 1
                else:
                    break
            result[key] = " ".join(p for p in folded if p).strip()
            continue

        if raw_value == "":
            items: List[str] = []
            while index < len(lines):
                cont = lines[index]
                if cont.startswith("  - "):
                    items.append(cont[4:].strip())
                    index += 1
                elif not cont.strip():
                    index += 1
                else:
                    break
            result[key] = items
            continue

        result[key] = _parse_scalar(raw_value)
    return result


def extract_section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    j = text.find(end)
    if i == -1 or j == -1 or j <= i:
        return ""
    return text[i + len(start):j].strip()


def parse_acceptance_criteria(text: str) -> List[str]:
    block = extract_section(text, "<!-- AC:BEGIN -->", "<!-- AC:END -->")
    if not block:
        return []
    criteria: List[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"- \[[ xX]\] #?\d+\s*(.*)", line)
        if m:
            criteria.append(m.group(1).strip())
        elif criteria:
            criteria[-1] = f"{criteria[-1]} {line}".strip()
        else:
            criteria.append(line)
    return criteria


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------


def normalize_status(raw: Any) -> str:
    t = str(raw or "").strip().lower()
    if t in {"to do", "todo", "open"}:
        return "todo"
    if t in {"in progress", "in_progress", "doing", "wip"}:
        return "in_progress"
    if t in {"done", "completed", "complete"} or "done" in t:
        return "done"
    if "progress" in t:
        return "in_progress"
    return "todo"


def normalize_priority(raw: Any) -> str:
    t = str(raw or "").strip().lower()
    return t if t in PRIORITY_ORDER else "medium"


def task_number(task_id: str) -> int:
    m = re.search(r"(\d+)$", task_id.split(".")[0])
    return int(m.group(1)) if m else sys.maxsize


def load_tasks(backlog_dir: Path) -> List[Task]:
    tasks: List[Task] = []
    for path in sorted(backlog_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = parse_front_matter(text)
        deps_raw = meta.get("dependencies", [])
        deps = _parse_list(deps_raw)
        labels = _parse_list(meta.get("labels", []))
        disp_raw = str(meta.get("dispatchable", "true")).strip().lower()
        dispatchable = disp_raw not in {"false", "no", "0"}

        tasks.append(Task(
            task_id=str(meta["id"]),
            title=str(meta["title"]),
            status=normalize_status(meta.get("status")),
            priority=normalize_priority(meta.get("priority")),
            dependencies=deps,
            labels=labels,
            dispatchable=dispatchable,
            description=extract_section(
                text, "<!-- SECTION:DESCRIPTION:BEGIN -->",
                "<!-- SECTION:DESCRIPTION:END -->"),
            acceptance_criteria=parse_acceptance_criteria(text),
            implementation_notes=extract_section(
                text, "<!-- SECTION:NOTES:BEGIN -->",
                "<!-- SECTION:NOTES:END -->"),
            source_path=str(path),
        ))
    return tasks


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def select_dispatchable(
    tasks: List[Task],
    mobile_repo_present: bool = False,
    max_dispatch: int = 0,
) -> tuple[List[Task], List[Dict[str, Any]]]:
    done_ids = {t.task_id for t in tasks if t.status == "done"}
    candidates: List[Task] = []
    skipped: List[Dict[str, Any]] = []

    for task in tasks:
        reasons: List[str] = []
        if task.status == "done":
            continue
        if task.status not in ("todo", "in_progress"):
            reasons.append(f"status inconnu: {task.status}")
        if not task.dispatchable:
            reasons.append("dispatchable: false")
        blockers = [d for d in task.dependencies if d not in done_ids]
        if blockers:
            reasons.append(f"deps: {', '.join(blockers)}")
        is_mobile = ("mobile" in task.labels
                     or "mobile" in task.title.lower())
        if is_mobile and not mobile_repo_present:
            reasons.append("mobile, repo absent")
        if reasons:
            skipped.append({"task_id": task.task_id, "title": task.title,
                            "reasons": reasons})
            continue
        candidates.append(task)

    candidates.sort(key=lambda t: (PRIORITY_ORDER.get(t.priority, 1),
                                   task_number(t.task_id)))
    if max_dispatch > 0:
        for t in candidates[max_dispatch:]:
            skipped.append({"task_id": t.task_id, "title": t.title,
                            "reasons": ["max_dispatch atteint"]})
        candidates = candidates[:max_dispatch]
    return candidates, skipped


# ---------------------------------------------------------------------------
# Task type classification & helpers
# ---------------------------------------------------------------------------


def infer_task_type(task: Task) -> str:
    labels = set(task.labels)
    if "benchmark" in labels:
        return "research"
    if labels & {"pricing", "product", "scoping"}:
        return "research"
    if "cleanup" in labels:
        return "cleanup"
    if labels & {"tooling", "orchestration", "agents"}:
        return "tooling"
    if "ingestion" in labels:
        return "ingestion"
    if "feature" in labels:
        return "feature"
    return "implementation"


def get_guardrails(task_type: str) -> str:
    specific = TYPE_GUARDRAILS.get(task_type, TYPE_GUARDRAILS["implementation"])
    return f"{COMMON_GUARDRAILS}\nRègles spécifiques ({task_type}) :\n{specific}"


def get_model_and_effort(
    task_type: str, args: argparse.Namespace,
) -> tuple[str, str]:
    model = args.model if args.model else TYPE_MODEL.get(task_type, "sonnet")
    effort = args.effort if args.effort else TYPE_EFFORT.get(task_type, "high")
    return model, effort


def get_timeout(task_type: str, args: argparse.Namespace) -> int:
    if args.timeout is not None:
        return args.timeout
    return TYPE_TIMEOUT.get(task_type, 900)


# ---------------------------------------------------------------------------
# Context distillation
# ---------------------------------------------------------------------------


def run_parallel_distillations(
    tasks: List[Task], task_types: Dict[str, str],
) -> Dict[str, Optional[dict]]:
    procs: Dict[str, tuple[subprocess.Popen, str]] = {}
    for task in tasks:
        prompt = (
            f"Analyse le contexte du repo pour la tâche {task.task_id}: "
            f"{task.title}\n\nDescription:\n{task.description[:1500]}\n\n"
            f"Type: {task_types[task.task_id]}\n"
            f"Labels: {', '.join(task.labels)}\n\n"
            "Inspecte le repo (lecture seule) et retourne le JSON structuré."
        )
        cmd = [
            "claude", "--bare", "-p", "--model", "sonnet",
            "--effort", "medium", "--max-turns", "3",
            "--output-format", "json", "--json-schema", CONTEXT_SCHEMA,
            "--dangerously-skip-permissions",
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        proc.stdin.write(prompt)
        proc.stdin.close()
        procs[task.task_id] = proc

    results: Dict[str, Optional[dict]] = {}
    for task_id, proc in procs.items():
        try:
            stdout, _ = proc.communicate(timeout=120)
            if proc.returncode == 0:
                payload = json.loads(stdout)
                results[task_id] = payload.get("structured_output")
            else:
                results[task_id] = None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            proc.kill()
            proc.wait()
            results[task_id] = None
    return results


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------


def build_prompt(task: Task, briefing: Optional[dict] = None) -> str:
    ac = ("\n".join(f"- {c}" for c in task.acceptance_criteria)
          if task.acceptance_criteria else "- Aucun critère capturé")
    notes = task.implementation_notes or "Aucune note."
    source = task.source_path or "N/A"

    parts = [
        f"## Tâche assignée\n\n**{task.task_id}** : {task.title}",
        "## Séquence obligatoire\n\n"
        f"1. Lis le fichier de tâche : `{source}`\n"
        "2. Lis les documents pertinents référencés dans la description\n"
        "3. Inspecte le code existant lié à cette tâche\n"
        "4. Formule un plan d'exécution concret (affiche-le)\n"
        "5. Implémente le plan\n"
        "6. Fais un `git add` des fichiers modifiés puis `git commit`",
    ]

    if briefing:
        files = ", ".join(briefing.get("relevant_files", [])[:10]) or "N/A"
        parts.append(
            "## Briefing contextuel\n\n"
            f"**Fichiers pertinents :** {files}\n\n"
            f"**Architecture :** {briefing.get('architecture_notes', 'N/A')}\n\n"
            f"**Patterns existants :** {briefing.get('existing_patterns', 'N/A')}\n\n"
            f"**Approche suggérée :** {briefing.get('suggested_approach', 'N/A')}"
        )

    parts.extend([
        f"## Description\n\n{task.description or 'Pas de description.'}",
        f"## Critères d'acceptation\n\n{ac}",
        f"## Notes d'implémentation existantes\n\n{notes}",
        "## Rappel\n\n"
        "- Tu travailles dans un worktree git isolé. Commite tes changements.\n"
        "- Reste focalisé sur cette tâche uniquement.",
    ])
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Git worktree management
# ---------------------------------------------------------------------------


def current_branch() -> str:
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def has_uncommitted_changes() -> bool:
    r = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True, check=True)
    tracked = [l for l in r.stdout.splitlines() if not l.startswith("??")]
    return bool(tracked)


def create_worktree(task_id: str, base_branch: str) -> tuple[str, str]:
    branch = f"worktree-{task_id}"
    wt_path = str(Path(WORKTREE_BASE) / task_id)
    if Path(wt_path).exists():
        subprocess.run(["git", "worktree", "remove", "--force", wt_path],
                       capture_output=True, check=False)
    subprocess.run(["git", "branch", "-D", branch],
                   capture_output=True, check=False)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, wt_path, base_branch],
        capture_output=True, text=True, check=True)
    return os.path.abspath(wt_path), branch


def cleanup_worktree(wt_path: str, branch: str) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", wt_path],
                   capture_output=True, check=False)
    subprocess.run(["git", "branch", "-D", branch],
                   capture_output=True, check=False)


# ---------------------------------------------------------------------------
# Task status update
# ---------------------------------------------------------------------------


def update_task_status(task: Task, new_status: str = "Done") -> bool:
    if not task.source_path:
        return False
    path = Path(task.source_path)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    updated = re.sub(r"(?m)^status:\s*.*$", f"status: {new_status}", text, count=1)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Dispatch & execution
# ---------------------------------------------------------------------------


def dispatch_task(
    task: Task, base_branch: str, args: argparse.Namespace,
    bundle_dir: Path, task_type: str, briefing: Optional[dict] = None,
) -> dict:
    wt_path, branch = create_worktree(task.task_id, base_branch)
    prompt = build_prompt(task, briefing=briefing)
    (bundle_dir / f"{task.task_id}-prompt.txt").write_text(prompt, encoding="utf-8")

    model, effort = get_model_and_effort(task_type, args)
    timeout = get_timeout(task_type, args)

    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--effort", effort,
        "--dangerously-skip-permissions",
    ]
    if args.max_turns > 0:
        cmd.extend(["--max-turns", str(args.max_turns)])
    cmd.extend(["--append-system-prompt", get_guardrails(task_type)])

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=wt_path)
    proc.stdin.write(prompt)
    proc.stdin.close()

    return {
        "task": task, "proc": proc, "branch": branch,
        "wt_path": wt_path, "started_at": time.time(),
        "deadline": (time.time() + timeout) if timeout > 0 else None,
    }


def poll_processes(
    inflight: List[dict], bundle_dir: Path,
) -> List[TaskResult]:
    results: List[TaskResult] = []
    while inflight:
        still_running = []
        for info in inflight:
            proc: subprocess.Popen = info["proc"]
            task: Task = info["task"]
            ret = proc.poll()

            if ret is None:
                if info["deadline"] and time.time() > info["deadline"]:
                    proc.kill()
                    proc.wait()
                    results.append(TaskResult(
                        task_id=task.task_id, status="timeout",
                        branch=info["branch"], worktree_path=info["wt_path"],
                        error=f"timeout ({int(info['deadline'] - info['started_at'])}s)",
                        duration_sec=time.time() - info["started_at"]))
                else:
                    still_running.append(info)
                continue

            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            duration = time.time() - info["started_at"]

            (bundle_dir / f"{task.task_id}-result.json").write_text(
                stdout or "{}", encoding="utf-8")
            if stderr.strip():
                (bundle_dir / f"{task.task_id}-stderr.txt").write_text(
                    stderr, encoding="utf-8")

            status = "completed" if ret == 0 else "failed"
            results.append(TaskResult(
                task_id=task.task_id, status=status,
                branch=info["branch"], worktree_path=info["wt_path"],
                stdout=stdout, stderr=stderr,
                error="" if ret == 0 else f"exit code {ret}",
                duration_sec=duration))

        inflight = still_running
        if inflight:
            time.sleep(2)
    return results


# ---------------------------------------------------------------------------
# Post-merge validation
# ---------------------------------------------------------------------------


def validate_merge(
    task: Task, pre_merge_ref: str, bundle_dir: Path,
) -> Optional[dict]:
    diff_stat = subprocess.run(
        ["git", "diff", f"{pre_merge_ref}..HEAD", "--stat"],
        capture_output=True, text=True, check=False)
    diff_detail = subprocess.run(
        ["git", "diff", f"{pre_merge_ref}..HEAD"],
        capture_output=True, text=True, check=False)

    ac = ("\n".join(f"- {c}" for c in task.acceptance_criteria)
          if task.acceptance_criteria else "Aucun critère")
    prompt = (
        f"Vérifie si cette tâche est complète.\n\n"
        f"Tâche: {task.task_id}: {task.title}\n\n"
        f"Critères d'acceptation:\n{ac}\n\n"
        f"Résumé des changements:\n{diff_stat.stdout}\n\n"
        f"Diff détaillé (tronqué):\n{diff_detail.stdout[:4000]}"
    )
    cmd = [
        "claude", "--bare", "-p", "--model", "haiku", "--max-turns", "1",
        "--output-format", "json", "--json-schema", VALIDATION_SCHEMA,
    ]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=30, check=False)
        if r.returncode != 0:
            return None
        payload = json.loads(r.stdout)
        result = payload.get("structured_output")
        if result:
            (bundle_dir / f"{task.task_id}-validation.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
        return result
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Merge & finalize (3-pass)
# ---------------------------------------------------------------------------


def probe_merge(branch: str) -> tuple[bool, str]:
    r = subprocess.run(["git", "merge", "--no-commit", "--no-ff", branch],
                       capture_output=True, text=True, check=False)
    subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
    detail = r.stderr.strip() or r.stdout.strip()
    if r.returncode != 0:
        print(f"    probe_merge({branch}) failed: rc={r.returncode} "
              f"— {detail[:200]}", file=sys.stderr)
    return r.returncode == 0, detail


def resolve_conflicts_with_llm(
    branch: str, base_branch: str, bundle_dir: Path,
) -> tuple[bool, str]:
    subprocess.run(["git", "merge", "--no-commit", "--no-ff", branch],
                   capture_output=True, check=False)
    conflicts = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        capture_output=True, text=True, check=False)
    if not conflicts.stdout.strip():
        subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
        return False, "no conflict files detected"

    diff_r = subprocess.run(["git", "diff"], capture_output=True, text=True, check=False)
    prompt = (
        f"Résous ce conflit de merge entre {branch} et {base_branch}.\n\n"
        f"Fichiers en conflit:\n{conflicts.stdout.strip()}\n\n"
        f"Diff avec marqueurs de conflit:\n{diff_r.stdout[:5000]}\n\n"
        "Pour chaque fichier en conflit, lis-le, résous le conflit intelligemment, "
        "et écris la version résolue. Puis fais git add des fichiers résolus."
    )
    cmd = ["claude", "--bare", "-p", "--model", "sonnet", "--max-turns", "5",
           "--dangerously-skip-permissions"]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=120, check=False)
    except subprocess.TimeoutExpired:
        subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
        return False, "LLM resolution timed out"

    if r.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
        return False, f"LLM resolution failed (exit {r.returncode})"

    check = subprocess.run(["git", "diff", "--check"],
                           capture_output=True, text=True, check=False)
    if check.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
        return False, "conflict markers remain after LLM resolution"

    subprocess.run(["git", "add", "-A"], capture_output=True, check=False)
    subprocess.run(
        ["git", "commit", "--no-edit", "-m",
         f"Merge {branch} (conflict resolved by LLM)"],
        capture_output=True, check=False)
    return True, "resolved"


def _get_head_ref() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _has_commits_ahead(base: str, branch: str) -> bool:
    r = subprocess.run(["git", "log", f"{base}..{branch}", "--oneline"],
                       capture_output=True, text=True, check=False)
    return bool(r.stdout.strip())


def _do_merge(branch: str, target: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["git", "merge", branch, "--no-edit", "-m",
         f"Merge {branch} into {target}"],
        capture_output=True, text=True, check=False)
    if r.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], capture_output=True, check=False)
        return False, r.stderr.strip() or r.stdout.strip()
    return True, "ok"


def merge_and_finalize(
    results: List[TaskResult],
    tasks_by_id: Dict[str, Task],
    base_branch: str,
    bundle_dir: Path,
    task_types: Dict[str, str],
) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []

    # Stash untracked files to prevent merge conflicts with new files
    stash_result = subprocess.run(
        ["git", "stash", "push", "-u", "-m", "dispatch-merge-stash"],
        capture_output=True, text=True, check=False)
    has_stash = "dispatch-merge-stash" in (stash_result.stdout or "")

    # Separate completed from failed/timeout
    completed = []
    for r in results:
        entry: Dict[str, Any] = {
            "task_id": r.task_id, "status": r.status,
            "branch": r.branch, "duration_sec": round(r.duration_sec, 1),
        }
        if r.status == "completed":
            # Debug: check branch state
            ref = subprocess.run(
                ["git", "rev-parse", r.branch],
                capture_output=True, text=True, check=False)
            wt_check = subprocess.run(
                ["git", "worktree", "list"],
                capture_output=True, text=True, check=False)
            print(f"    debug {r.task_id}: branch={r.branch} "
                  f"ref={ref.stdout.strip()[:8] or 'MISSING'} "
                  f"rc={ref.returncode}", file=sys.stderr)
        if r.status != "completed":
            entry["error"] = r.error
            cleanup_worktree(r.worktree_path, r.branch)
            summary.append(entry)
        elif not _has_commits_ahead(base_branch, r.branch):
            entry["status"] = "no_changes"
            entry["error"] = "aucun commit produit"
            cleanup_worktree(r.worktree_path, r.branch)
            summary.append(entry)
        else:
            completed.append((r, entry))

    # Pass 1: probe merges
    clean, conflicting = [], []
    for r, entry in completed:
        ok, detail = probe_merge(r.branch)
        if ok:
            clean.append((r, entry))
        else:
            entry["probe_error"] = detail
            conflicting.append((r, entry))

    # Pass 2: merge clean branches
    for r, entry in clean:
        pre_ref = _get_head_ref()
        ok, msg = _do_merge(r.branch, base_branch)
        if not ok:
            entry["status"] = "merge_conflict"
            entry["error"] = msg
        else:
            validation = validate_merge(
                tasks_by_id[r.task_id], pre_ref, bundle_dir)
            is_complete = validation.get("complete", True) if validation else True
            new_status = "Done" if is_complete else "In Progress"
            task = tasks_by_id[r.task_id]
            if update_task_status(task, new_status):
                subprocess.run(["git", "add", task.source_path],
                               capture_output=True, check=False)
                subprocess.run(
                    ["git", "commit", "-m",
                     f"backlog: mark {task.task_id} as {new_status}"],
                    capture_output=True, check=False)
            entry["status"] = "merged"
            entry["task_status"] = new_status
            if validation:
                entry["validation"] = validation.get("summary", "")
        cleanup_worktree(r.worktree_path, r.branch)
        summary.append(entry)

    # Pass 3: attempt LLM conflict resolution
    for r, entry in conflicting:
        ok, msg = resolve_conflicts_with_llm(r.branch, base_branch, bundle_dir)
        if ok:
            pre_ref = _get_head_ref()
            validation = validate_merge(
                tasks_by_id[r.task_id], pre_ref, bundle_dir)
            is_complete = validation.get("complete", True) if validation else True
            new_status = "Done" if is_complete else "In Progress"
            task = tasks_by_id[r.task_id]
            if update_task_status(task, new_status):
                subprocess.run(["git", "add", task.source_path],
                               capture_output=True, check=False)
                subprocess.run(
                    ["git", "commit", "-m",
                     f"backlog: mark {task.task_id} as {new_status}"],
                    capture_output=True, check=False)
            entry["status"] = "merged_after_resolution"
            entry["task_status"] = new_status
        else:
            entry["status"] = "merge_conflict"
            entry["error"] = msg
        cleanup_worktree(r.worktree_path, r.branch)
        summary.append(entry)

    # Restore stashed untracked files
    if has_stash:
        subprocess.run(["git", "stash", "pop"],
                       capture_output=True, check=False)

    return summary


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_plan(
    selected: List[Task], skipped: List[Dict[str, Any]],
    task_types: Dict[str, str],
) -> None:
    print("=" * 60)
    print(f"  Dispatch plan — {len(selected)} tâche(s) sélectionnée(s)")
    print("=" * 60)
    for t in selected:
        tt = task_types.get(t.task_id, "?")
        model = TYPE_MODEL.get(tt, "sonnet")
        timeout = TYPE_TIMEOUT.get(tt, 0)
        timeout_str = f"{timeout}s" if timeout > 0 else "∞"
        print(f"  + {t.task_id} [{t.priority}] ({tt}) {t.title[:55]}")
        print(f"      model={model} timeout={timeout_str}")
    if skipped:
        print(f"\n  {len(skipped)} tâche(s) non sélectionnée(s) :")
        for s in skipped[:12]:
            print(f"  - {s['task_id']} — {'; '.join(s['reasons'])}")
        if len(skipped) > 12:
            print(f"  ... et {len(skipped) - 12} autre(s)")
    print()


def print_summary(summary: List[Dict[str, Any]]) -> None:
    merged = [e for e in summary if e["status"] in ("merged", "merged_after_resolution")]
    failed = [e for e in summary
              if e["status"] not in ("merged", "merged_after_resolution", "no_changes")]
    no_op = [e for e in summary if e["status"] == "no_changes"]
    print("=" * 60)
    print(f"  Résultats — {len(merged)} merged, {len(failed)} failed, {len(no_op)} no-op")
    print("=" * 60)
    icons = {"merged": "+", "merged_after_resolution": "~", "no_changes": "o",
             "failed": "X", "timeout": "T", "merge_conflict": "!"}
    for e in summary:
        icon = icons.get(e["status"], "?")
        line = f"  {icon} {e['task_id']} [{e['status']}] ({e['duration_sec']}s)"
        if e.get("task_status"):
            line += f" -> {e['task_status']}"
        if e.get("error"):
            line += f" — {e['error'][:70]}"
        if e.get("validation"):
            line += f" | {e['validation'][:50]}"
        print(line)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Dispatch backlog tasks to parallel Claude Code agents.")
    p.add_argument("--dry-run", action="store_true",
                   help="Affiche le plan sans lancer les agents.")
    p.add_argument("--backlog-dir", default="backlog/tasks")
    p.add_argument("--max-dispatch", type=int, default=5)
    p.add_argument("--model", default=None,
                   help="Override modèle pour tous (défaut: par type).")
    p.add_argument("--effort", default=None, choices=("low", "medium", "high"),
                   help="Override effort pour tous (défaut: par type).")
    p.add_argument("--max-turns", type=int, default=0,
                   help="Limite de turns par agent (0 = pas de limite).")
    p.add_argument("--timeout", type=int, default=None,
                   help="Override timeout pour tous (défaut: par type).")
    p.add_argument("--mobile-repo-present", action="store_true")
    p.add_argument("--output-dir", default=".claude/dispatch-runs")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    backlog_dir = Path(args.backlog_dir)
    if not backlog_dir.is_dir():
        print(f"Erreur : {backlog_dir} n'existe pas.", file=sys.stderr)
        return 1

    tasks = load_tasks(backlog_dir)
    tasks_by_id = {t.task_id: t for t in tasks}
    selected, skipped = select_dispatchable(
        tasks, mobile_repo_present=args.mobile_repo_present,
        max_dispatch=args.max_dispatch)

    if not selected:
        print("Aucune tâche dispatchable.")
        return 0

    task_types = {t.task_id: infer_task_type(t) for t in selected}
    print_plan(selected, skipped, task_types)

    if args.dry_run:
        if args.format == "json":
            print(json.dumps({
                "dry_run": True,
                "selected": [
                    {"task_id": t.task_id, "title": t.title,
                     "priority": t.priority, "type": task_types[t.task_id],
                     "model": TYPE_MODEL.get(task_types[t.task_id], "sonnet"),
                     "timeout": TYPE_TIMEOUT.get(task_types[t.task_id], 900)}
                    for t in selected],
                "skipped": skipped,
            }, indent=2, ensure_ascii=False))
        return 0

    # Pre-flight
    base = current_branch()
    if has_uncommitted_changes():
        print("Erreur : changements non commités.", file=sys.stderr)
        print("Commite ou stash avant de lancer.", file=sys.stderr)
        return 1

    ts = time.strftime("%Y%m%d-%H%M%S")
    bundle_dir = Path(args.output_dir) / f"dispatch-{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "dispatch-plan.json").write_text(json.dumps({
        "timestamp": ts, "base_branch": base,
        "selected": [
            {"task_id": t.task_id, "title": t.title,
             "type": task_types[t.task_id],
             "model": TYPE_MODEL.get(task_types[t.task_id], "sonnet"),
             "timeout": TYPE_TIMEOUT.get(task_types[t.task_id], 900)}
            for t in selected],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Phase 1: context distillation
    print("  Phase 1 : distillation de contexte...")
    briefings = run_parallel_distillations(selected, task_types)
    ok_count = sum(1 for v in briefings.values() if v)
    print(f"    {ok_count}/{len(selected)} briefings obtenus\n")

    # Phase 2: dispatch
    print(f"  Phase 2 : dispatch de {len(selected)} agent(s) en parallèle...")
    inflight = []
    for task in selected:
        tt = task_types[task.task_id]
        briefing = briefings.get(task.task_id)
        try:
            info = dispatch_task(task, base, args, bundle_dir,
                                 task_type=tt, briefing=briefing)
            inflight.append(info)
            if info["deadline"]:
                timeout = int(info["deadline"] - info["started_at"])
                print(f"    -> {task.task_id} ({tt}) timeout={timeout}s")
            else:
                print(f"    -> {task.task_id} ({tt}) timeout=∞")
        except subprocess.CalledProcessError as exc:
            print(f"    X {task.task_id} : worktree failed — {exc.stderr}",
                  file=sys.stderr)

    if not inflight:
        print("Aucun agent lancé.", file=sys.stderr)
        return 1

    print(f"\n    En attente de {len(inflight)} agent(s)...\n")
    results = poll_processes(inflight, bundle_dir)

    # Phase 3: merge & validate
    print("  Phase 3 : merge et validation...")
    summary = merge_and_finalize(results, tasks_by_id, base, bundle_dir, task_types)

    (bundle_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print_summary(summary)
    print(f"Bundle : {bundle_dir}")

    if args.format == "json":
        print(json.dumps({"bundle_dir": str(bundle_dir), "summary": summary},
                         indent=2, ensure_ascii=False))

    has_failures = any(
        e["status"] not in ("merged", "merged_after_resolution", "no_changes")
        for e in summary)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
