# Authority files over chat history

## Status

Accepted

## Context

Chat history is incomplete, model-specific, difficult to audit, and may contain unreviewed private
information.

## Decision

Only authority YAML files under the explicitly supplied repository root are eligible build inputs.
The framework does not import or scan conversations.

## Consequences

Operators must deliberately maintain authority files. Missing context remains missing instead of
being inferred from chat logs.
