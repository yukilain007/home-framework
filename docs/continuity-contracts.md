# Continuity contracts

Continuity contracts are an optional, local-first protocol for carrying reviewed
context between AI windows and tools. They are a clean-room, independent implementation
for HOME Framework; this project does not copy code, prompts, documentation, or implementation
details from any other repository.

The protocol is model-agnostic. It adds data contracts, validation, inspection, deterministic
rendering, and examples. It does not add a chat UI, a model API, a database, or automatic
conversation import. The existing workspace layout and default initialization remain valid.

Context continuity does not imply AI memory, identity persistence, or consciousness persistence.
HOME manages user-controlled context artifacts and approved handoffs. It does not preserve,
transfer, or claim continuity of an AI system's identity.

## Where contracts live

Optional YAML contracts live under `continuity/`. A handoff includes them only when its
`include.continuity_ids` selector explicitly names them. A missing `continuity/` directory is
valid for existing workspaces.

The six contract kinds are:

| Kind | Purpose | May enter a handoff |
| --- | --- | --- |
| `persona_autonomy` | Judgment anchor and boundary precedence | Yes |
| `window_state_card` | Dated context note for a window | Yes |
| `lifeline` | Explicitly bounded recent timeline | Yes |
| `memory_candidate` | Human-review queue item | No |
| `recall_decision` | Model-agnostic recall record | No |
| `maintenance_channel` | Boundary for review/maintenance output | Yes |

## Protocol classification

| Type | Renderable to Handoff | Review Required |
| --- | --- | --- |
| `PersonaAutonomy` | Yes | Yes |
| `WindowStateCard` | Yes | Yes |
| `LifeLine` | Yes | Yes |
| `Maintenance` | Yes | Yes |
| `MemoryCandidate` | No | Promotion required |
| `RecallDecision` | No | Decision artifact |

The renderer never promotes a candidate or recall decision. Those records remain inspectable
and editable in the local workspace, but they are not facts and are not handoff content.

## Contract fields

Every contract has `kind`, `schema_version` (`1.0`), and a stable `id`.

### PersonaAutonomy

`independentJudgment`, `mayDisagree`, `mayDeclineInteraction`,
`roleplayDoesNotOverrideBoundaries`, `currentRealityOverridesStoredPersona`, and optional `notes`.
This is an anchor for independent judgment, not a script that every response must perform.

### WindowStateCard

`topic`, `confirmedFacts`, `toneAndMood`, `openThreads`, `anchors`, `avoidAssumptions`,
`generatedAt`, and `sourceWindow`. It is a context note, not a command or task list.

### LifeLine

`coverageStart`, `coverageEnd`, `generatedAt`, `recentEvents`, `activeProjects`, and
`currentConcerns`. Any relative description must be translated into the explicit coverage date
range; the protocol does not infer an unbounded timeline.

### MemoryCandidate

`content`, `category`, `source`, `rationale`, `confidence`, `status`, and `reviewedAt`.
`status` is one of `proposed`, `accepted`, or `rejected`. An accepted candidate is still not a
long-term authority document: it requires a separate, human-reviewed integration into the
existing authority model. No candidate is automatically promoted.

### RecallDecision

`action` (`none`, `reuse`, `supplement`, or `refresh`), `reason`, `requestedScopes`,
`selectedMemoryIds`, and `generatedAt`. It records a decision for inspection; it does not grant
permission or contain a model/vendor field.

### MaintenanceChannel

`purpose`, `allowedOutputs`, `requiresHumanReview`, and optional `modelHint`. The hint is
descriptive only and does not bind HOME to a provider.

## Precedence and review

- The current user instruction has priority over stored context.
- Current reality has priority over a stored persona anchor when the contract says so.
- A persona anchor must not be treated as a fixed performance checklist.
- A state card must not be interpreted as the next action or a task queue.
- Memory candidates are viewable, editable, and rejectable; they remain outside final handoffs.
- Unconfirmed psychology, identity, or relationship labels are not inferred from these files.
- A user approves the final handoff before it is supplied to another compatible tool.

## Commands

Existing commands continue to work unchanged:

```text
home init <path> --name <name>
home validate <path>
home build <path> --handoff <id> --as-of YYYY-MM-DD
home doctor <path> --as-of YYYY-MM-DD
```

The optional example set can be created on a fresh workspace with:

```text
home init <path> --name <name> --with-continuity
```

`home inspect <path>` reads and prints continuity contracts without compiling or changing
files. The default `home init` path does not create `continuity/`, preserving backward
compatibility and the existing workflow.

## Package workflow

Continuity contracts are selected and rendered before a Package is created. The Package commands
operate on explicit inputs and do not deliver or upload anything:

```text
home package create <workspace> --handoff <id> --as-of YYYY-MM-DD --dry-run \
  --approval-source explicit_user_confirmation \
  --approval-handoff-id <id> \
  --approval-context-date YYYY-MM-DD \
  --approval-fingerprint <compiled fingerprint> \
  --approval-confirmed-at 2026-08-04T12:00:00Z

home package create <workspace> --handoff <id> --as-of YYYY-MM-DD --output <directory> \
  --approval-source explicit_user_confirmation \
  --approval-handoff-id <id> \
  --approval-context-date YYYY-MM-DD \
  --approval-fingerprint <compiled fingerprint> \
  --approval-confirmed-at 2026-08-04T12:00:00Z

home package verify <package.json>
home package export <package.json> --output <directory>
home package adapt <package.json> --adapter local-markdown
```

`--dry-run` keeps the Package in memory. `--output` creates or reuses one immutable local
artifact after verification. `verify` checks an artifact but grants no approval or authority;
`export` performs an atomic local copy and is not delivery; `adapt` creates an in-memory external
representation and is not send. The current adapter is only `local-markdown`.

The internal `CompiledContext` is not the same object as the external `HandoffPackage`, and an
`ExternalRepresentationArtifact` is derived from that Package rather than fed back into the
compiler. Memory candidates and recall decisions remain inspect-only and cannot be promoted by
these commands.

JSON Schemas are exported as `schemas/*-*.schema.json` files for the six contract kinds. They
are generated from the Pydantic model authority and checked for drift in the normal quality
gate.

## License and provenance

Continuity contracts are distributed under this repository's Apache-2.0 license. The protocol
and implementation are an independent clean-room design. No third-party code, prompts, field
combinations, or documentation are copied into HOME Framework.
