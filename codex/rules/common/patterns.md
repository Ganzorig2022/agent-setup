# Common Patterns

## Research and Reuse

Before implementing unfamiliar or high-risk functionality, prefer existing local patterns and battle-tested references over inventing architecture from scratch.

Use this pattern for:
- new applications
- unfamiliar frameworks
- authentication
- authorization
- payment flows
- file upload/download systems
- webhook handling
- external integrations
- infrastructure/deployment templates
- complex backend services
- cross-file architecture changes

Research order:
1. Search the local repository first.
2. Use official documentation for APIs, frameworks, and version-specific behavior.
3. Check package registries when dependency choice matters.
4. Use GitHub/code search when implementation examples reduce risk.
5. Use broader web research only when the above are insufficient.

Evaluation criteria:
- security posture
- maintenance activity
- framework compatibility
- extensibility
- simplicity
- licensing constraints
- testability

Do not use this pattern for:
- typo fixes
- formatting-only changes
- obvious one-file fixes
- small utility functions
- simple CRUD changes
- minor refactors

Prefer the smallest viable proven structure. Do not clone a large skeleton project unless the task actually requires it.