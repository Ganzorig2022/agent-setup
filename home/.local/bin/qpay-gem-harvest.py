#!/usr/bin/env python3
"""Harvest engineering docs ("gems") from local QPay repos into the PRIVATE vault
for agent / coding recall (qmd). Consolidates each repo's README + docs/ + CLAUDE/AGENT
+ design docs into one note under knowledge-base/qpay/.

INTERNAL ONLY. This folder is deliberately EXCLUDED from the public-facing content
factory (x-draft-factory reads decisions/ + profile/ only). Re-run any time to refresh.
"""
from __future__ import annotations
import datetime
import json
import pathlib
import re

SRC = pathlib.Path("/Users/dev/QPay")
VAULT = pathlib.Path("/Users/dev/GIthub/knowledge-base")
OUT = VAULT / "qpay"
OUT.mkdir(parents=True, exist_ok=True)

REPO_RE = re.compile(r"^(qpay|qcard|qp2p)-")
TOP_DOCS = ["README.md", "ARCHITECTURE*.md", "DESIGN*.md", "CLAUDE.md",
            "AGENTS.md", "AGENT_GUIDE.md"]
STACK_KEYS = ["fastify", "express", "mongoose", "qpay-sequelize-postgres", "next",
              "react", "antd", "@radix-ui/react-slot", "bull", "bullmq", "zod", "joi",
              "@tanstack/react-query", "zustand", "redux"]
MAX_NOTE = 60_000  # cap per repo note


def stack_of(repo: pathlib.Path) -> str:
    pj = repo / "package.json"
    if not pj.exists():
        return ""
    try:
        d = json.loads(pj.read_text(errors="ignore"))
    except Exception:
        return ""
    deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
    return ", ".join(k for k in STACK_KEYS if k in deps)


def collect_docs(repo: pathlib.Path) -> list[pathlib.Path]:
    docs: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for pat in TOP_DOCS:
        for f in sorted(repo.glob(pat)):
            if f.is_file() and f not in seen:
                docs.append(f); seen.add(f)
    for f in sorted(repo.glob("docs/**/*.md")):
        if f.is_file() and "node_modules" not in f.parts and f not in seen:
            docs.append(f); seen.add(f)
    return docs


def main() -> int:
    repos = sorted(p for p in SRC.iterdir()
                   if p.is_dir() and REPO_RE.match(p.name))
    index = [
        "# QPay internal knowledge — harvested gems\n",
        f"_Harvested {datetime.date.today()} from local repos. **INTERNAL / private** — "
        "excluded from the content pipeline. For agent + coding recall via qmd._\n",
        "## Repos\n",
    ]
    count = 0
    for repo in repos:
        parts = []
        for f in collect_docs(repo):
            try:
                txt = f.read_text(errors="ignore").strip()
            except Exception:
                continue
            if len(txt) < 80:        # skip stubs / near-empty
                continue
            parts.append(f"\n\n## {f.relative_to(repo)}\n\n{txt}")
        if not parts:
            continue
        stack = stack_of(repo)
        note = (
            f"---\ntype: qpay-internal\nrepo: {repo.name}\n"
            f"tags: [qpay, internal, architecture]\nstack: {stack}\n"
            f"harvested: {datetime.date.today()}\n---\n\n# {repo.name}\n"
            + "".join(parts)
        )[:MAX_NOTE]
        (OUT / f"{repo.name}.md").write_text(note)
        index.append(f"- **{repo.name}** — {stack or 'n/a'}")
        count += 1
    (OUT / "INDEX.md").write_text("\n".join(index))
    print(f"harvested {count} repos -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
