---
name: coding-standards
description: Baseline cross-project coding conventions for naming, readability, immutability, and code-quality review. Use narrower workflow skills when they fit better.
origin: agent-stack
---

# Coding Standards

Baseline coding conventions that apply across projects.

This skill is the shared floor, not the detailed framework playbook.

Use it for:

- naming and readability
- immutability defaults
- KISS, DRY, and YAGNI enforcement
- explicit error handling
- input validation at boundaries

Prefer a narrower skill when one exists for the current stack or workflow.

## Core Principles

### Readability First

- code is read more than written
- prefer clear names over terse names
- prefer self-documenting code over comments
- keep formatting and structure consistent

### KISS

- choose the simplest approach that works
- avoid premature optimization
- optimize for clarity over cleverness

### DRY

- extract real repetition into shared helpers
- avoid copy-paste drift
- do not create abstractions before repeated pressure exists

### YAGNI

- do not build speculative flexibility
- add complexity only when the current requirement demands it

## Coding Expectations

### Naming

- use descriptive names for variables and functions
- prefer verb-noun names for functions
- booleans should usually start with `is`, `has`, `can`, or `should`
- types, interfaces, and components should use `PascalCase`

### Immutability

- avoid mutating caller-owned data
- prefer immutable updates for shared state and request-scoped values
- local mutation is acceptable when it is contained and clearer

### Errors

- handle errors explicitly
- return or throw clear failures
- do not silently swallow failures
- do not expose secrets or internal stack details to users

### Validation

- validate at system boundaries
- do not trust user input or external API responses by default
- use schema validation when the project already has it

### Structure

- keep functions focused
- keep files cohesive
- prefer small, reversible edits over broad rewrites
- extract helpers when a function is doing multiple jobs

## Review Checklist

Before marking work complete, check:

- code is readable and well named
- functions are focused
- files remain cohesive
- errors are handled explicitly
- boundary input is validated
- no hardcoded secrets or environment-specific assumptions were added
- shared or caller-owned data is not mutated unexpectedly

## When Not To Use This Skill

Do not use this as the primary source for:

- framework-specific UI architecture
- backend layering guidance
- infrastructure-specific workflows
- specialized cleanup or migration procedures
