# Continuity contracts as optional reviewed context

## Status

Accepted

## Context

HOME already has reviewed `core` and time-bounded `current` authority, plus candidates that are
intentionally excluded from compilation. Long-running AI work also needs a small, inspectable way
to carry an autonomy anchor, a window note, a date-bounded lifeline, memory proposals, recall
decisions, and maintenance-channel boundaries without turning any of them into a script or an
automatic memory store.

Context continuity does not imply AI memory, identity persistence, or consciousness persistence.
HOME manages user-controlled context artifacts and approved handoffs. It does not preserve,
transfer, or claim continuity of an AI system's identity.

## Decision

Add an independent `continuity/` protocol family. Each YAML object has a strict kind, schema
version, stable ID, explicit fields, and human-readable validation errors. The repository loader
loads these objects separately from core/current authority. Handoffs may opt in to selected
renderable continuity IDs; memory candidates and recall decisions are always excluded from
compiled handoffs. Accepted candidates remain candidates until a human explicitly writes reviewed
authority elsewhere.

`PersonaAutonomy` is an anchor for independent judgment, not a roleplay script. `WindowStateCard`
is a dated context note, not a command or task list. `LifeLine` requires an explicit coverage date
range. `MaintenanceChannel` separates allowed background outputs from live user interaction and
records whether human review is required. `RecallDecision` records a model-agnostic decision but
does not grant permission by itself.

The default initializer and existing handoff behavior remain unchanged. An opt-in initializer
flag may create fictional continuity examples. `home inspect` is read-only; `home validate` and
`home doctor` validate and report continuity objects without promoting or uploading anything.

## Consequences

- Existing workspaces remain valid without a `continuity/` directory.
- Every new contract is inspectable, editable, and rejectable as a local YAML file.
- Current user input is outside the repository and therefore takes precedence over stored data.
- Rendering is purpose-scoped and explicit; candidates cannot leak into handoffs.
- New schemas are generated from the Pydantic model authority and tested for drift.
- No chat UI, model API, database, vendor field, or vendor runtime dependency is added.
