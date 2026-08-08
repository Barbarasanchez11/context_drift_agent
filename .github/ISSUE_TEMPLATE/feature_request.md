---
name: Feature request
about: Suggest an idea or improvement
title: '[Feature] '
labels: enhancement
assignees: ''
---

## Is your feature request related to a problem?

A clear description of what the problem is.
Example: "I have to manually check whether drift results have been written back..."

## Proposed solution

A clear description of what you want to happen.

## Alternatives considered

Any alternative solutions or features you've considered.

## Scope check

Before proposing, please check [`DECISIONS.md`](../../DECISIONS.md) for scope
boundaries. In particular:

- This project detects drift in **existing** context — it does not generate new
  context (that's DataHub Cloud's Context Curator).
- This project uses polling, not the Actions Framework, for schema change
  detection (Decision 007).
- Metadata is written to `customProperties`, not Structured Properties (Decision 006).

If your proposal conflicts with these decisions, please open a discussion in
the issue explaining why the decision should change.

## Additional context

Any mockups, examples, or references that illustrate the feature.
