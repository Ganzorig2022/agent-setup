# Coding Style

## Immutability

Prefer immutable updates for application state, shared data, function inputs, and values passed across module boundaries.

Do not mutate:

- function inputs
- UI framework state directly
- store state directly unless the framework explicitly supports controlled mutation
- cached/shared objects
- objects reused across requests or sessions

Local mutation is acceptable when:

- it is confined to a function
- it does not mutate caller-owned data
- it improves clarity or performance
- it cannot leak hidden side effects

Language note: This rule may be overridden by language-specific rules where mutation is idiomatic or required.

## Core Principles

### KISS

- Prefer the simplest solution that actually works.
- Avoid premature optimization.
- Optimize for clarity over cleverness.

### DRY

- Extract repeated logic into shared functions or utilities.
- Avoid copy-paste implementation drift.
- Introduce abstractions when repetition is real, not speculative.

### YAGNI

- Do not build features or abstractions before they are needed.
- Avoid speculative generality.
- Start simple, then refactor when pressure is real.

## File Organization

Prefer many focused files over a few large files.

Guidelines:

- High cohesion, low coupling.
- 200-400 lines is typical.
- 800 lines is a soft maximum.
- Extract utilities from large modules.
- Organize by feature/domain when practical, not only by technical type.

## Error Handling

Handle errors explicitly.

- Provide user-friendly errors in UI-facing code.
- Log useful diagnostic context on the server side.
- Never silently swallow errors.
- Do not expose stack traces, secrets, tokens, or sensitive internals to users.

## Input Validation

Validate at system boundaries.

- Validate user input before processing.
- Validate external API responses before trusting them.
- Use schema-based validation where available.
- Fail fast with clear errors.
- Never trust external data by default.

## Naming Conventions

- Variables and functions: `camelCase` with descriptive names.
- Booleans: prefer `is`, `has`, `should`, or `can` prefixes.
- Interfaces, types, and components: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Custom hooks: `camelCase` with a `use` prefix.

Language note: Language-specific idioms override these defaults.

## Code Smells to Avoid

- Deep nesting: prefer early returns once logic starts stacking.
- Magic numbers: use named constants for meaningful thresholds, delays, and limits.
- Long functions: split large functions into focused pieces with clear responsibilities.
- Broad rewrites: avoid replacing working architecture without explicit reason.
- Speculative abstraction: do not generalize before repetition is real.

## Code Quality Checklist

Before marking work complete:

- [ ] Code is readable and well-named.
- [ ] Functions are focused.
- [ ] Files are cohesive.
- [ ] No unnecessary deep nesting.
- [ ] Errors are handled explicitly.
- [ ] Boundary input is validated.
- [ ] No hardcoded secrets or environment-specific values.
- [ ] Shared/caller-owned data is not mutated unexpectedly.
