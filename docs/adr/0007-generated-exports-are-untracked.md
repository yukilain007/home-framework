# Keep generated exports untracked

## Status

Accepted

## Context

Authority files already provide the reproducible source for exports. Tracking generated Markdown
creates review noise and risks treating derived prose as a second authority source.

## Decision

Workspaces ignore `exports/*.md` by default. Authority files, handoffs, manifests, and intentional
candidate records belong in version control. Doctor reports a tracked export but never runs Git
mutation commands.

## Consequences

Exports may be deleted and rebuilt. Operators who intentionally track them receive a warning and
remain responsible for their own Git policy.
