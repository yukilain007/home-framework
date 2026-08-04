# Handoff Package Protocol

## Status

Accepted

## Context

`CompiledContext` is an internal HOME compiler result. It is useful to the renderer and CLI, but
it is not a stable external interface and may evolve with implementation details. Adapters need
a smaller boundary that can be validated without access to a HOME workspace or compiler
runtime.

Without that boundary, an integration could accidentally read unreviewed files, make authority
decisions, or treat a mutable intermediate representation as permission to transmit context.

## Decision

Define `HandoffPackage` as the immutable, serialized artifact consumed by a Handoff Adapter.

```text
Reviewed authority + HandoffDocument
            ↓
     CompiledContext
            ↓ serialize
      HandoffPackage
            ↓
       Handoff Adapter
```

`CompiledContext` remains an internal compiler result. `HandoffPackage` is the external
provider-agnostic boundary. An Adapter must receive the Package itself, not a repository handle,
workspace path, or direct compiler object.

The Package is purpose-scoped and user-approved. Producing or adapting it does not transmit,
upload, or share it automatically.

## Schema principles

The protocol must keep these concerns explicit and independently versioned:

- `package_schema`: version of the external Package protocol;
- `handoff_schema`: version of the HOME Handoff content schema;
- `provenance`: producer, reviewed-authority status, and user-approval status;
- `source_fingerprint`: fingerprint of the reviewed inputs used to compile the Package;
- content digest: integrity digest of the serialized Handoff content.

The Package should carry its purpose, Handoff ID, context date, creation time, content media
type, and purpose-scoped content. A logical content reference may be included for auditability,
but it must not require an Adapter to read a local path or fetch a URL.

The minimum boundary must not include provider credentials, raw conversation history, workspace
paths, unreviewed candidates, or vendor-specific runtime fields.

## Security invariants

- An Adapter has no workspace or repository access.
- An Adapter cannot select authority or change the compiler's selection result.
- An Adapter cannot promote, reject, or rewrite a memory candidate.
- Schema, provenance, approval, or content-digest mismatches fail closed.
- The Package preserves the distinction between conversation and fact, suggestion and approval,
  and history and permission.
- An Adapter cannot infer user intent or additional authorization from Package content.
- No automatic transmission, upload, or sharing is part of the Package protocol.

## Mutation model

`HandoffPackage` is immutable.

An Adapter may produce a new target representation, but it must not edit the Package or change
its semantic content. If a user changes the content, HOME must review and compile a new Package
with a new creation time, content digest, and source fingerprint. The old Package remains a
separate historical artifact and is not updated in place.

## Versioning

The following versions are separate:

1. `package_schema` — the serialized Handoff Package protocol;
2. `handoff_schema` — the HOME Handoff document and content schema;
3. Adapter contract version — the capabilities and compatibility contract of an Adapter.

Major-version mismatches fail closed. Minor-version compatibility must be explicitly declared by
the consuming Adapter; it must not be guessed from field names. Package migration belongs to
HOME and produces a new Package. Adapters do not silently migrate or overwrite Packages.

## Rejected alternatives

### Adapter editing HandoffPackage

Rejected because edits would invalidate provenance and make user approval ambiguous. A changed
Package must be recompiled by HOME.

### Adapter generating authority

Rejected because authority selection and candidate promotion belong to the human-reviewed HOME
workflow, not to an external representation layer.

### Adapter reading workspace

Rejected because filesystem access could bypass the Package boundary, expose unrelated or
sensitive files, and make the resulting context impossible to audit as a bounded artifact.

## Consequences

- External integrations receive a stable, inspectable artifact rather than HOME internals.
- Adapter implementations remain provider-agnostic at the protocol layer.
- Provenance and approval remain visible across format conversion.
- Future changes require explicit schema compatibility decisions and new artifacts.
- This decision adds no adapter implementation, provider integration, network dependency, database,
  or compiler change.
