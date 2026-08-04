# Provider-agnostic Handoff Adapter Boundary

## Status

Accepted

## Context

HOME compiles reviewed local authority into a purpose-scoped Context Handoff. Users may later
want to present that handoff to different compatible tools, but the boundary must not turn a
tool integration into a second authority or memory system.

The adapter boundary is therefore a transport and compatibility seam. It is not a model
integration, a chat interface, or a mechanism for preserving an AI system's identity. Context
continuity does not imply AI memory, identity persistence, or consciousness persistence.

## Decision

Use this one-way architecture:

```text
HOME Workspace
    |
    | validate and compile
    v
Validated Handoff Package
    |
    v
Handoff Adapter
    |
    v
External Tool
```

An adapter receives only a validated, user-approved handoff artifact. The user decides whether
to provide the adapter output to an external tool. Creating adapter output does not send,
upload, or share it automatically.

The future provider-agnostic contract must identify the adapter and its version, target type,
accepted Handoff schema and format, declared capabilities, limitations, human-review
requirement, and provenance-preservation behavior. Version compatibility must be explicit; an
unsupported schema is rejected rather than guessed or silently converted.

## Adapter responsibilities

An adapter may:

- transform an approved handoff into a target-compatible representation without changing its
  semantic content;
- validate target-tool and accepted-schema constraints;
- add non-semantic transport metadata;
- preserve the handoff ID, source fingerprint, schema version, and adapter identity;
- produce deterministic output or fail closed when deterministic output is not possible.

## Adapter prohibitions

An adapter must not:

- select authority or decide what belongs in a handoff;
- promote or reject memory candidates;
- read the workspace, chat history, credentials, or files outside the input artifact;
- write memories or modify HOME authority files;
- infer user intent or add facts;
- invoke the compiler to obtain additional context;
- transmit, upload, or share output automatically.

## Security invariants

- The adapter boundary accepts artifacts, not a workspace or repository handle.
- Schema or capability mismatches fail closed and produce no deliverable output.
- Equal approved inputs and adapter versions produce equal output.
- Every output remains traceable to its handoff ID, source fingerprint, schema version, and
  adapter identity and version.
- Candidate content and recall decisions are excluded before the boundary; the adapter cannot
  reintroduce them.
- Network access, credentials, and provider-specific runtime dependencies are outside the core
  boundary and require a separate decision.

## Rejected alternatives

### HOME → Adapter → generate Handoff

Rejected because the adapter would participate in authority selection and could expose
unreviewed or candidate content. It would also make the adapter a hidden compiler and weaken
deterministic provenance.

### Provider-specific logic inside the compiler

Rejected because compiler behavior would become coupled to external tools, credentials, and
changing provider formats. The compiler must continue to produce the same provider-neutral
handoff for the same approved inputs.

### Adapter with workspace access

Rejected because filesystem access would allow an adapter to bypass the reviewed Handoff
boundary, read unrelated or sensitive files, and make complete provenance difficult to audit.

## Future implementation order

Implementation is intentionally deferred. When approved, proceed in this order:

1. Define provider-agnostic protocol types and compatibility validation.
2. Add tests for artifact-only input, fail-closed schema handling, deterministic output, and
   provenance retention.
3. Implement a local, read-only Markdown pass-through adapter as a reference.
4. Add inspection and validation tooling only after the protocol is stable.
5. Consider provider-specific adapters later, each with its own security and approval review.

No provider integration, network dependency, database, UI, or compiler change is part of this
decision.

## Consequences

- HOME remains the authority and compilation layer; adapters remain downstream consumers.
- A handoff can be adapted without granting an external tool access to the workspace.
- Provenance and user approval remain visible at the boundary.
- Future integrations require an explicit contract and cannot silently expand HOME's authority.
