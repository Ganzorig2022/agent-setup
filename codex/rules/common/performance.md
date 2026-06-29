# Performance Optimization

## Agent and Model Selection

Use the lightest capable reasoning mode or model for the task. Prefer higher-reasoning models only when the work involves architecture, security-sensitive tradeoffs, ambiguous debugging, or multi-step planning.

Good defaults:

- Lightweight reasoning: documentation updates, small focused edits, simple command output analysis.
- Standard coding reasoning: implementation, test repair, normal refactoring, review.
- Highest reasoning: architecture decisions, migrations, production-impacting risk, security review, complex debugging.

## Context Window Management

Avoid starting broad implementation work near the end of a context window. For large changes, summarize current state and continue from a handoff instead of relying on stale implicit context.

Lower context sensitivity tasks:

- Single-file edits
- Independent utility creation
- Documentation updates
- Simple bug fixes

Higher context sensitivity tasks:

- Large-scale refactoring
- Feature implementation spanning multiple files
- Debugging complex interactions
- Security-sensitive changes

## Planning and Review

For complex tasks:

1. Create a plan before editing.
2. Inspect existing repository patterns before proposing changes.
3. Use separate reviewer perspective after meaningful implementation work.
4. Keep validation commands explicit.

## Build Troubleshooting

If build fails:

1. Use the `build-error-resolver` agent prompt or equivalent role.
2. Analyze error messages before editing.
3. Fix incrementally.
4. Verify after each fix.
