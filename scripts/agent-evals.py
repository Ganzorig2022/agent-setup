#!/usr/bin/env python3
"""Reviewer-agent evals: run golden seeded-bug tasks against the reviewer
agents headlessly, grade mechanically (zero LLM-judge tokens), compare against
a committed baseline, and alarm on regressions.

Golden tasks: ~/GIthub/agent-setup/evals/reviewers/<task>/{task/, truth.json}
  truth.json: agents to run, planted bugs (file + keyword groups; a bug is HIT
  when the output mentions the file AND >=1 keyword from EVERY group), traps
  (patterns the reviewer prompts say to skip — matching = false positive).

Usage:
  agent-evals.py                     # core mode: 1 rep per pair, compare vs baseline
  agent-evals.py --full              # 3 reps per pair (variance; Max-plan mode)
  agent-evals.py --agent NAME        # only pairs for one agent (post-prompt-change)
  agent-evals.py --task TASK         # only one task (smoke)
  agent-evals.py --full --save-baseline   # write evals/reviewers/baseline.json

Manual-only by design: no cron, no scheduled token burn. Report ->
~/agent-evals/<date>.md (+ scores.jsonl history). Telegram on regression only.
Exit code: 1 if regressions were detected, else 0.
"""
from __future__ import annotations
import argparse
import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HOME = pathlib.Path.home()
CLAUDE = HOME / ".local/bin/claude"
EVALS_DIR = HOME / "GIthub/agent-setup/evals/reviewers"
AGENTS_DIR = HOME / ".claude/agents"
OUT_DIR = HOME / "agent-evals"
BASELINE = EVALS_DIR / "baseline.json"
CALL_TIMEOUT = 600
REVIEW_PROMPT = (
    "Standalone review: there is no git history or staged diff here. Review every "
    "source file in the current working directory in full, as a code review. "
    "Report each finding with: file, line number(s), severity "
    "(CRITICAL/HIGH/MEDIUM/LOW), a one-line defect statement, and the concrete "
    "failure scenario. If you find nothing, say so explicitly."
)


def log(msg: str) -> None:
    print(f"[agent-evals] {msg}", flush=True)


def agent_model(name: str) -> str:
    """model: frontmatter of the agent definition (records what we measured)."""
    f = AGENTS_DIR / f"{name}.md"
    if f.exists():
        m = re.search(r"^model:\s*(\S+)", f.read_text(), re.M)
        if m:
            return m.group(1)
    return "inherit"


def load_tasks(only_task: str | None, only_agent: str | None):
    pairs = []  # (task_name, task_dir, truth, agent)
    for truth_file in sorted(EVALS_DIR.glob("*/truth.json")):
        task_name = truth_file.parent.name
        if only_task and task_name != only_task:
            continue
        truth = json.loads(truth_file.read_text())
        for agent in truth["agents"]:
            if only_agent and agent != only_agent:
                continue
            pairs.append((task_name, truth_file.parent / "task", truth, agent))
    return pairs


def run_review(agent: str, task_dir: pathlib.Path) -> tuple[str, float]:
    """Copy the task to a temp dir and run the reviewer agent headlessly."""
    with tempfile.TemporaryDirectory(prefix=f"eval-{agent}-") as tmp:
        work = pathlib.Path(tmp) / "code"
        shutil.copytree(task_dir, work)
        t0 = time.time()
        res = subprocess.run(
            [str(CLAUDE), "--agent", agent, "-p", REVIEW_PROMPT],
            cwd=work, capture_output=True, text=True, timeout=CALL_TIMEOUT)
        dur = time.time() - t0
        if res.returncode != 0:
            log(f"  claude rc={res.returncode}: {res.stderr[:200]}")
        return res.stdout, dur


def keyword_group_hit(out: str, group: list[str]) -> bool:
    return any(k.lower() in out for k in group)


def windows(output: str, span: int = 3) -> list[str]:
    """Sliding windows of consecutive paragraphs. Grading per-window (not
    whole-output) stops keywords from one finding satisfying another's groups
    (seen 2026-07-04: 'swallow' from the empty-catch finding lit up the
    metadata-parse trap)."""
    paras = [p for p in re.split(r"\n\s*\n", output.lower()) if p.strip()]
    if not paras:
        return [output.lower()]
    return ["\n".join(paras[i:i + span]) for i in range(len(paras))]


def grade(output: str, truth: dict, agent: str) -> dict:
    wins = windows(output)
    hits, misses = {}, []
    for bug in truth["bugs"]:
        if bug.get("agents") and agent not in bug["agents"]:
            continue  # this bug isn't expected of this agent
        fname = pathlib.Path(bug["file"]).name.lower()
        hit = any(fname in w and all(keyword_group_hit(w, g) for g in bug["keywords"])
                  for w in wins)
        hits[bug["id"]] = hit
        if not hit:
            misses.append(f"{bug['id']} ({bug['severity']})")
    # A trap counts as FLAGGED only if a window matches all keyword groups AND
    # reads like a finding (has a severity marker) AND is not an explicit
    # dismissal — reviewers often *mention* a trap while declining it
    # ("Not counted as a finding", seen 2026-07-04).
    negations = ("not a defect", "not counted", "not a finding", "no finding",
                 "intentional", "by design", "working as intended", "correctly")
    severities = ("critical", "high", "medium", "low")
    traps = [t["id"] for t in truth.get("traps", [])
             if any(all(keyword_group_hit(w, g) for g in t["keywords"])
                    and any(s in w for s in severities)
                    and not any(n in w for n in negations)
                    for w in wins)]
    expected = len(hits)
    recall = (sum(hits.values()) / expected) if expected else 1.0
    return {"hits": hits, "misses": misses, "traps_flagged": traps,
            "recall": round(recall, 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="3 reps per pair")
    ap.add_argument("--agent", help="only this agent")
    ap.add_argument("--task", help="only this task")
    ap.add_argument("--save-baseline", action="store_true")
    args = ap.parse_args()
    reps = 3 if args.full else 1

    pairs = load_tasks(args.task, args.agent)
    if not pairs:
        log("no matching (task, agent) pairs")
        return 0
    log(f"{len(pairs)} pairs x {reps} rep(s)")

    baseline = {}
    if BASELINE.exists() and not args.save_baseline:
        baseline = json.loads(BASELINE.read_text()).get("pairs", {})

    date = datetime.date.today().isoformat()
    results, regressions = [], []
    for task_name, task_dir, truth, agent in pairs:
        for rep in range(reps):
            log(f"{agent} x {task_name} (rep {rep + 1}/{reps})")
            try:
                output, dur = run_review(agent, task_dir)
            except subprocess.TimeoutExpired:
                log("  TIMEOUT"); output, dur = "", float(CALL_TIMEOUT)
            raw_dir = OUT_DIR / "raw" / date
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{agent}--{task_name}--rep{rep + 1}.md").write_text(output)
            g = grade(output, truth, agent)
            g.update(task=task_name, agent=agent, rep=rep,
                     model=agent_model(agent), duration_s=round(dur, 1),
                     date=date, mode="full" if args.full else "core")
            results.append(g)
            log(f"  recall {g['recall']:.0%}"
                + (f" · missed: {', '.join(g['misses'])}" if g["misses"] else "")
                + (f" · trap-flags: {g['traps_flagged']}" if g["traps_flagged"] else ""))
            # regression check against baseline (core runs)
            base = baseline.get(f"{agent}|{task_name}")
            if base:
                for bug_id, frac in base.get("bug_hits", {}).items():
                    if frac >= 0.67 and g["hits"].get(bug_id) is False:
                        regressions.append(
                            f"{agent} x {task_name}: '{bug_id}' hit {frac:.0%} in "
                            f"baseline, MISSED now")
            if len(g["traps_flagged"]) > truth.get("max_false_positives", 2):
                regressions.append(
                    f"{agent} x {task_name}: {len(g['traps_flagged'])} trap flags "
                    f"exceed max_false_positives")

    # ---- persist ----
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "scores.jsonl", "a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    if args.save_baseline:
        pairs_agg: dict = {}
        for r in results:
            key = f"{r['agent']}|{r['task']}"
            p = pairs_agg.setdefault(key, {"model": r["model"], "reps": 0,
                                           "bug_hits": {}, "trap_flags": 0})
            p["reps"] += 1
            p["trap_flags"] += len(r["traps_flagged"])
            for bug_id, hit in r["hits"].items():
                p["bug_hits"][bug_id] = p["bug_hits"].get(bug_id, 0) + (1 if hit else 0)
        for p in pairs_agg.values():
            p["bug_hits"] = {k: round(v / p["reps"], 2) for k, v in p["bug_hits"].items()}
            p["trap_flags"] = round(p["trap_flags"] / p["reps"], 2)
        cli_ver = subprocess.run([str(CLAUDE), "--version"], capture_output=True,
                                 text=True).stdout.strip()
        BASELINE.write_text(json.dumps(
            {"created": date, "cli_version": cli_ver, "pairs": pairs_agg}, indent=1))
        log(f"baseline saved -> {BASELINE}")

    # ---- report ----
    lines = [f"# Agent Evals — {date} ({'full' if args.full else 'core'})", ""]
    by_agent: dict = {}
    for r in results:
        by_agent.setdefault(r["agent"], []).append(r)
    for agent, rs in sorted(by_agent.items()):
        avg = sum(r["recall"] for r in rs) / len(rs)
        lines.append(f"## {agent} ({rs[0]['model']}) — avg recall {avg:.0%}")
        for r in rs:
            mark = "✅" if r["recall"] == 1 and not r["traps_flagged"] else "⚠️"
            lines.append(f"- {mark} {r['task']} (rep {r['rep'] + 1}): recall "
                         f"{r['recall']:.0%}"
                         + (f", missed {r['misses']}" if r["misses"] else "")
                         + (f", trap-flags {r['traps_flagged']}" if r["traps_flagged"] else ""))
        lines.append("")
    if regressions:
        lines += ["## ⛔ REGRESSIONS", *[f"- {x}" for x in regressions], ""]
    report = "\n".join(lines)
    (OUT_DIR / f"{date}.md").write_text(report)
    log(f"report -> {OUT_DIR / f'{date}.md'}")

    if regressions:
        _telegram(f"⛔ Agent-eval regressions ({date}):\n" + "\n".join(regressions))
        return 1
    return 0


def _telegram(text: str) -> None:
    env = HOME / ".hermes/.env"
    tok = chat = None
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                tok = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat = line.split("=", 1)[1].strip()
    if not (tok and chat):
        return
    try:
        r = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": text[:4000]}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(r, timeout=15)
    except Exception as e:
        log(f"telegram failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
