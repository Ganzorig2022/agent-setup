---
name: frontend-patterns
description: Frontend development patterns for React, Next.js, state management, performance optimization, and accessible UI work.
origin: agent-stack
---

# Frontend Patterns

Modern frontend patterns for React, Next.js, and maintainable user interfaces.

## When To Activate

- building React components
- structuring client-side state
- implementing data fetching
- handling forms and validation
- improving rendering performance
- building accessible, responsive UI

## Component Patterns

### Composition Over Inheritance

- prefer small composable components
- pass `children` when structure should stay flexible
- avoid boolean-prop explosions when composition is clearer

### Compound Components

- use shared context for related subcomponents such as tabs, menus, or accordions
- keep the public API readable at the call site

### Custom Hooks

- extract repeated client logic into hooks
- keep hook responsibilities narrow
- make hook names describe the behavior they encapsulate

## State And Data

### Local State

- keep state as local as possible
- derive values instead of storing duplicate state
- use reducer-style state only when transitions are genuinely complex

### Async Data

- handle loading, error, and success states explicitly
- keep fetch logic predictable
- use parallel async work when requests are independent

### Forms

- validate at the boundary where data enters the system
- keep field state and submission state clear
- prefer schema-backed validation when the project already uses it

## Performance

- do not memoize by default
- optimize only where there is real cost or churn
- split large lists with virtualization when needed
- lazy-load heavy or rarely used UI

## Accessibility

- use semantic HTML first
- ensure keyboard access for interactive controls
- manage focus intentionally for dialogs, menus, and overlays
- do not rely on color alone to convey meaning

## Common Smells

- giant multi-purpose components
- prop drilling that should be composition or context
- duplicated async state logic across screens
- hidden side effects in render paths
- accessibility added as an afterthought

## Delivery Checklist

- component boundaries are clear
- state shape is minimal
- loading and error states exist where needed
- keyboard and focus behavior are considered
- the UI follows existing project conventions unless intentionally changed
