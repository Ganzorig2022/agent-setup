#!/bin/bash
# PostToolUse(ExitPlanMode) — fires when a plan is approved ("Yes, ..." in plan mode).
# Executors here are Codex/OpenCode, not Claude, so instead of implementing directly,
# prompt Claude to offer a self-contained executor handoff brief from the approved plan.

input=$(cat)  # consume stdin (PostToolUse JSON: tool_name/tool_input/tool_response)

# Best-effort pointer to the most recently written plan file.
plan_dir="$HOME/.claude/plans"
latest_plan=""
[ -d "$plan_dir" ] && latest_plan=$(ls -t "$plan_dir"/*.md 2>/dev/null | head -1)

ctx="A plan was just approved (ExitPlanMode). In this workspace the executors are Codex and OpenCode, not Claude. Do NOT start implementing yet. First ask the user with AskUserQuestion whether to generate an executor handoff prompt, and for which target: Codex, OpenCode, both, or skip (let Claude implement). If they pick an executor, produce a self-contained handoff brief from the approved plan using the handoff-impl skill."
[ -n "$latest_plan" ] && ctx="$ctx Approved plan file: $latest_plan."

# jq -n builds valid, properly-escaped JSON (jq is available in this environment).
jq -n --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$c}}'
exit 0
