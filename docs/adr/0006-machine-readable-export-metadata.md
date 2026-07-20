# Embed machine-readable export metadata

## Status

Accepted

## Context

Stale detection cannot safely depend on headings or prose in generated Markdown. Display metadata
such as generation time must not affect deterministic fingerprints.

## Decision

Every Markdown export begins with one fixed-prefix HTML comment containing canonical JSON for
schema version, handoff ID, context date, and fingerprint. Parsing is limited to that first line.
Malformed, missing, and unsupported metadata is reported rather than guessed.

## Consequences

Older exports require rebuilding. `generated_at` remains human-readable but does not enter the
machine marker or fingerprint. General Markdown and HTML parsers are unnecessary.
